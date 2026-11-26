"""Model-free visual and acoustic navigation for an external reasoning agent."""
from __future__ import annotations
import io
import math
from pathlib import Path
import wave
import numpy as np
from PIL import Image, ImageDraw
from .engine import run, input_args, decode, audio_features, RATE
from .video_understanding import source, source_revision, plan_page, sample_frames
from .spatial import region_pixels
from .images import compare_pixels
from .acoustics import png

MAX_INDEX=100_000
MAX_NATIVE_PAGE=8


def check_revision(p,rev):
    if source_revision(p)!=rev:
        raise RuntimeError('Source changed during perception; discard earlier results.')


def dimensions(meta,max_side):
    stream=next(s for s in meta['streams'] if s['codec_type']=='video')
    w,h=int(stream['width']),int(stream['height'])
    if min(w,h)<1 or w*h>40_000_000:
        raise ValueError('Unsupported source dimensions.')
    scale=min(1,max_side/max(w,h))
    return max(1,round(w*scale)),max(1,round(h*scale))


def native_page(p:Path,index:int=0,count:int=4,max_side:int=640,expected_revision=None):
    """Exact zero-based decoded frame ordinals, without time seeking or FPS resampling."""
    if not 0<=index<MAX_INDEX or not 1<=count<=MAX_NATIVE_PAGE or not 128<=max_side<=960:
        raise ValueError('Frame index 0–99999, count 1–8, max_side 128–960.')
    rev,meta=source(p,expected_revision)
    w,h=dimensions(meta,max_side)
    n=min(count,MAX_INDEX-index)
    # Decode from the beginning to retain ordinal identity, including variable-rate sources.
    # One extra frame distinguishes EOF from another page, within the supported index range.
    last=min(MAX_INDEX-1,index+n)
    vf=f'select=between(n\\,{index}\\,{last}),scale={w}:{h},format=rgb24'
    raw=run('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-max_alloc','134217728',
        '-threads','2',*input_args(p)[:-1],'-noautorotate','-i',str(p),'-map','0:v:0','-an',
        '-filter_threads','1','-threads','2','-vf',vf,'-fps_mode','passthrough',
        '-frames:v',str(last-index+1),'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],
        (last-index+1)*w*h*3,timeout=45)
    check_revision(p,rev)
    if len(raw)%(w*h*3):
        raise RuntimeError('Incomplete native RGB frame.')
    decoded=np.frombuffer(raw,dtype=np.uint8).reshape(-1,h,w,3)
    frames=decoded[:n]
    end=index+len(frames)
    boundary=end>=MAX_INDEX
    return {'file':p.name,'source_revision':rev,'first_frame_index':index,
            'frame_indices':list(range(index,end)),'returned_count':len(frames),
            'next_frame_index':end if len(decoded)>n and not boundary else None,
            'end_of_stream':len(decoded)<last-index+1,
            'index_limit_reached':boundary,'sample_size_px':[w,h],
            'limitations':['Zero-based decoded presentation order, not compressed packet order or a timestamp.',
                           'No frames intentionally skipped or duplicated by a sampling filter.',
                           'Decoder errors or corruption can affect ordinal identity. Images are downscaled.',
                           'Decoding from the beginning costs time; requests can time out, and index navigation is bounded at 100000.',
                           'Use time-based segment navigation for longer files. No semantic inference.']},frames


def native_sheet(report,frames):
    if not len(frames):
        raise ValueError('No decoded frame at the requested index.')
    w,h=480,300
    cols=2
    sheet=Image.new('RGB',(cols*w,math.ceil(len(frames)/cols)*h),'#102331')
    draw=ImageDraw.Draw(sheet)
    for i,frame in enumerate(frames):
        x,y=(i%cols)*w,(i//cols)*h
        im=Image.fromarray(frame)
        im.thumbnail((w-12,h-28))
        sheet.paste(im,(x+(w-im.width)//2,y+22+(h-28-im.height)//2))
        draw.text((x+6,y+5),f"Decoded frame #{report['frame_indices'][i]}",fill='white')
    return png(np.asarray(sheet))


def crop_frame(p,index,box,max_side=960,expected_revision=None):
    report,frames=native_page(p,index,1,max_side,expected_revision)
    if not len(frames):
        raise ValueError('No decoded frame at the requested index.')
    crop,bounds=region_pixels(frames[0],box)
    return {**report,'crop_bounds_sample_px':bounds},png(np.ascontiguousarray(crop))


def frame_pair(p,index_a,index_b,threshold=25,expected_revision=None):
    first,a=native_page(p,index_a,1,960,expected_revision)
    second,b=native_page(p,index_b,1,960,first['source_revision'])
    if not len(a) or not len(b):
        raise ValueError('One or both decoded frame indices are unavailable.')
    report,overlay=compare_pixels(a[0],b[0],threshold)
    return {'source_revision':first['source_revision'],'frame_a':index_a,'frame_b':index_b,**report},png(overlay)


def visual_changes(frames,start,fps,previous=None):
    events=[]
    prior=previous
    for i,frame in enumerate(frames):
        if prior is not None:
            delta=np.abs(frame.astype(np.int16)-prior.astype(np.int16))
            mad=float(delta.mean()/255)
            changed=float((delta.max(axis=2)>=25).mean())
            # Luma histogram distance reduces sensitivity to small pixel translations.
            luma=lambda x:np.rint(x.astype(np.float32)@np.array([.2126,.7152,.0722])).astype(np.uint8)
            a=np.bincount((luma(prior)//16).ravel(),minlength=16)/prior.shape[0]/prior.shape[1]
            b=np.bincount((luma(frame)//16).ravel(),minlength=16)/frame.shape[0]/frame.shape[1]
            hist=float(np.abs(a-b).sum()/2)
            events.append({'time_s':round(start+i/fps,3),'mean_rgb_difference':round(mad,5),
                           'changed_pixel_fraction':round(changed,5),'luma_histogram_distance':round(hist,5),
                           'boundary_comparison':i==0,
                           'scene_change_candidate':mad>=.12 and hist>=.15})
        prior=frame
    return events


def scan_page(p,segment_seconds=8,cursor=0,page_size=2,sample_fps=4,expected_revision=None):
    if not 1<=page_size<=3 or sample_fps not in (1,2,4):
        raise ValueError('Choose 1–3 segments per page and 1, 2 or 4 sampled fps.')
    rev,meta=source(p,expected_revision)
    plan=plan_page(meta['duration_s'],segment_seconds,cursor,page_size)
    previous=None
    prior_status='start_of_video' if cursor==0 else 'unavailable'
    if cursor and plan['segments']:
        # Re-read the previous segment's final sample so page boundaries are not silently ignored.
        prev=plan_page(meta['duration_s'],segment_seconds,cursor-1,1)['segments'][0]
        try:
            frames=sample_frames(p,prev['start_s'],prev['end_s'],sample_fps)
            if len(frames)==math.ceil((prev['end_s']-prev['start_s'])*sample_fps):
                previous=frames[-1]
                prior_status='observed'
        except (ValueError,RuntimeError,OSError):
            pass
        check_revision(p,rev)
    rows=[]
    for seg in plan['segments']:
        a,b=seg['start_s'],seg['end_s']
        row={**seg,'visual_status':'failed','audio_status':'not_present' if not meta['audio'] else 'failed',
             'preceding_boundary_status':prior_status}
        try:
            frames=sample_frames(p,a,b,sample_fps)
            expected=math.ceil((b-a)*sample_fps)
            comparisons=visual_changes(frames,a,sample_fps,previous)
            row.update(visual_status='sampled' if len(frames)==expected else 'partial',
                       sample_count=len(frames),expected_sample_count=expected,
                       sample_times_s=[round(a+i/sample_fps,3) for i in range(len(frames))],
                       comparisons=comparisons,scene_change_candidates=[x['time_s'] for x in comparisons if x['scene_change_candidate']])
            previous=frames[-1] if len(frames)==expected else None
            prior_status='observed' if previous is not None else 'unavailable'
        except (ValueError,RuntimeError,OSError) as exc:
            row['visual_error']=type(exc).__name__
            previous=None
            prior_status='unavailable'
        if meta['audio']:
            try:
                summary,bins=audio_features(p,a,b-a)
                row.update(audio_status='measured' if summary['analyzed_s']>=b-a-.03 else 'partial',
                           audio=summary,audio_bins=bins)
            except (ValueError,RuntimeError,OSError) as exc:
                row['audio_error']=type(exc).__name__
        check_revision(p,rev)
        rows.append(row)
    return {'source_revision':rev,'file':p.name,**plan,'results':rows,'sample_fps':sample_fps,
            'limitations':['Visit every page and inspect ordered visual evidence, not only flagged changes.',
                           'Scene candidates are heuristic pixel/histogram differences, not semantic scene labels.',
                           'Brief actions, fades, camera motion, variable frame rate and lighting can affect candidates.',
                           'Approximate resampled timestamps; audio/video offsets are not exact source PTS.',
                           'Missing and partial windows are explicit. A complete plan is not exhaustive frame inspection.',
                           'The host model interprets the evidence and relationships; SEA performs no model inference.']}


def audio_clip(p,start,seconds,expected_revision=None):
    if not math.isfinite(start) or not math.isfinite(seconds) or start<0 or not .25<=seconds<=12:
        raise ValueError('Choose a nonnegative start and 0.25–12 seconds.')
    rev,meta=source(p,expected_revision)
    if not meta['audio'] or start>=meta['duration_s']:
        raise ValueError('No audio in the requested video range.')
    duration=min(seconds,meta['duration_s']-start)
    raw=decode(p,start,duration,['-map','0:a:0','-vn','-ac','1','-ar',str(RATE),'-c:a','pcm_s16le','-f','s16le'],
               (math.ceil(duration*RATE)+RATE)*2)
    check_revision(p,rev)
    if not raw or len(raw)%2:
        raise ValueError('No complete audio samples in this range.')
    raw=raw[:math.ceil(duration*RATE)*2]
    buf=io.BytesIO()
    with wave.open(buf,'wb') as f:
        f.setparams((1,2,RATE,0,'NONE','not compressed'))
        f.writeframes(raw)
    return {'source_revision':rev,'requested_range_s':[start,start+duration],
            'decoded_duration_s':len(raw)/2/RATE,'sample_rate_hz':RATE,'channels':1,
            'note':'Approximate first-stream mono audio; client must support MCP audio content. No transcription.'},buf.getvalue()
