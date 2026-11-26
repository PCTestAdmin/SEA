"""Bounded, conservative within-video track association using COCO detections."""
from __future__ import annotations
import math
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw
from .engine import probe, window
from .spatial import load_image
from .vision import fingerprint
from .detector import load_detector, validate_options
from .acoustics import png

MAX_SPAN=60
MAX_SAMPLES=12
SOFT_SECONDS=65
COLORS=['#00e5ff','#ffc66d','#b7f28b','#e4a6ff','#ff9a9a','#b9c6ff']


def iou(a,b):
    overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=lambda x:(x[2]-x[0])*(x[3]-x[1])
    return overlap/(area(a)+area(b)-overlap) if overlap else 0.


def sample_times(start,span,samples):
    window(start,span,MAX_SPAN)
    if not 2<=samples<=MAX_SAMPLES:
        raise ValueError('Sample count must be 2–12.')
    if start+span>86400:
        raise ValueError('Tracking window must end by 86400 seconds.')
    return [start+i*span/samples for i in range(samples)]


def associate(samples: list[dict], min_iou: float=.3) -> list[dict]:
    """Link only mutually unique same-label candidates in adjacent successful samples."""
    if not math.isfinite(min_iou) or not .1<=min_iou<=1:
        raise ValueError('Association IoU must be 0.1–1.')
    tracks=[]
    active={}
    for sample in samples:
        if sample['status']!='observed':
            active={}
            continue
        rows=sample['detections']
        forward={k:[] for k in active}
        backward=[[] for _ in rows]
        for k,prev in active.items():
            for j,row in enumerate(rows):
                overlap=iou(prev['box'],row['box'])
                if prev['label']==row['label'] and overlap>=min_iou:
                    forward[k].append((j,overlap))
                    backward[j].append(k)
        current={}
        for j,row in enumerate(rows):
            linked=None
            if len(backward[j])==1:
                candidate=backward[j][0]
                if len(forward[candidate])==1:
                    linked=candidate
            if linked is None:
                linked=len(tracks)
                tracks.append({'id':f'T{linked+1:03d}','label':row['label'],'observations':[]})
                reason='ambiguous_overlap' if backward[j] else 'new_or_unmatched'
                overlap=None
            else:
                reason='mutually_unique_overlap'
                overlap=round(forward[linked][0][1],6)
            b=row['box']
            item={'sample_id':sample['id'],'requested_time_s':sample['requested_time_s'],
                  'detection_id':row['id'],'box':b,'score':row['score'],
                  'center':[(b[0]+b[2])/2,(b[1]+b[3])/2],
                  'association':reason,'previous_iou':overlap}
            tracks[linked]['observations'].append(item)
            current[linked]=row
        active=current
    for t in tracks:
        obs=t['observations']
        first,last=obs[0],obs[-1]
        t['observation_count']=len(obs)
        t['first_requested_time_s']=first['requested_time_s']
        t['last_requested_time_s']=last['requested_time_s']
        t['net_center_shift']=[round(b-a,6) for a,b in zip(first['center'],last['center'])] if len(obs)>1 else None
        t['sampled_center_path_length']=round(sum(math.dist(a['center'],b['center']) for a,b in zip(obs,obs[1:])),6) if len(obs)>1 else None
    return tracks


def track(p: Path,start: float=0,span: float=10,samples: int=6,threshold: float=.5,
          min_iou: float=.3,labels: list[str]|None=None,limit: int=12,keep_frames: bool=False):
    sample_times(start,span,samples)
    validate_options(threshold,limit)
    if limit>20:
        raise ValueError('Tracking detection limit is 1–20 per sample.')
    if not math.isfinite(min_iou) or not .1<=min_iou<=1:
        raise ValueError('Association IoU must be 0.1–1.')
    if labels is not None and (not 1<=len(labels)<=8 or any(not 1<=len(s.strip())<=80 for s in labels)):
        raise ValueError('Choose 1–8 exact COCO class names or omit labels.')
    wanted={s.strip().casefold() for s in labels} if labels is not None else None
    before=fingerprint(p)
    meta=probe(p)
    if not meta['video']:
        raise ValueError('Tracking requires a video stream.')
    if meta['duration_s'] is not None:
        span=min(span,meta['duration_s']-start)
    times=sample_times(start,span,samples)
    predict,provenance,categories=load_detector()
    if wanted is not None and not wanted<={x.casefold() for x in categories if x not in ('N/A','__background__')}:
        raise ValueError('Unknown COCO class; use exact detector labels.')
    deadline=time.monotonic()+SOFT_SECONDS
    observations=[]
    frames={}
    for i,t in enumerate(times,1):
        item={'id':f'S{i:02d}','requested_time_s':t}
        if time.monotonic()>=deadline:
            observations.append(dict(item,status='not_attempted',reason='Scheduling budget reached.'))
            continue
        try:
            rgb=load_image(p,t)
        except (ValueError,RuntimeError,OSError) as exc:
            if before!=fingerprint(p):
                raise RuntimeError('Source changed during tracking.') from None
            observations.append(dict(item,status='decode_failed',reason=type(exc).__name__))
            continue
        # Inference failures are not confused with missing objects or failed decoding.
        pred=predict(rgb,threshold,50)
        matches=[r for r in pred['detections'] if wanted is None or r['label'].casefold() in wanted]
        rows=matches[:limit]
        observations.append(dict(item,status='observed',detections=rows,
                                 sample_size_px=[rgb.shape[1],rgb.shape[0]],
                                 detector_output_truncated=pred['truncated'],
                                 selected_output_truncated=len(matches)>limit))
        if keep_frames:
            frames[item['id']]=rgb
        if before!=fingerprint(p):
            raise RuntimeError('Source changed during tracking.')
    if before!=fingerprint(p):
        raise RuntimeError('Source changed during tracking.')
    tracks=associate(observations,min_iou)
    return {'schema_version':1,'file':p.name,'requested_range_s':[start,start+span],
            'requested_sample_count':samples,'observed_sample_count':sum(s['status']=='observed' for s in observations),
            'threshold':threshold,'association_iou':min_iou,'labels':sorted(wanted) if wanted is not None else None,
            'detection_limit_per_sample':limit,'samples':observations,'tracks':tracks,
            'track_count':len(tracks),'multi_observation_track_count':sum(t['observation_count']>1 for t in tracks),
            'provenance':provenance,
            'limitations':['Sparse requested timestamps, not exact presentation times or continuous tracking.',
                           'Only adjacent observed samples with mutually unique same-class overlap are linked.',
                           'Missed detections, ambiguous overlaps or failed frames break tracks. No re-identification.',
                           'Even unique overlap may connect different objects; track IDs are hypotheses local to this call.',
                           'Image-space center shifts include camera motion and perspective; no physical speed or distance.',
                           'Truncation and fixed COCO categories can hide detections; track counts are not unique object counts.',
                           '65-second soft scheduling budget excludes model loading; an operation already running may finish later.',
                           'No face identification or cross-video identity matching.']},frames


def contact_sheet(report: dict,frames: dict) -> bytes:
    """Display exactly the observations from one tracking invocation."""
    if not frames:
        raise ValueError('No observed frames to visualize; inspect the numeric tracking report.')
    width,height=256,190
    sheet=Image.new('RGB',(3*width,math.ceil(len(report['samples'])/3)*height),'#102331')
    draw=ImageDraw.Draw(sheet)
    by_sample={}
    for track in report['tracks']:
        for obs in track['observations']:
            by_sample.setdefault(obs['sample_id'],[]).append((track,obs))
    for i,sample in enumerate(report['samples']):
        x,y=(i%3)*width,(i//3)*height
        key=sample['id']
        draw.text((x+6,y+4),f"{key} | {sample['requested_time_s']:.2f}s | {sample['status']}",fill='white')
        if key not in frames:
            continue
        im=Image.fromarray(frames[key])
        im.thumbnail((width-12,height-30))
        px,py=x+(width-im.width)//2,y+22+(height-28-im.height)//2
        sheet.paste(im,(px,py))
        for tr,obs in by_sample.get(key,[]):
            l,t,r,b=[int(v*(n-1)) for v,n in zip(obs['box'],(im.width,im.height,im.width,im.height))]
            color=COLORS[(int(tr['id'][1:])-1)%len(COLORS)]
            draw.rectangle((px+l,py+t,px+r,py+b),outline=color,width=2)
            draw.text((px+l,py+max(0,t-12)),tr['id'],fill=color,stroke_width=1,stroke_fill='black')
    return png(np.asarray(sheet))
