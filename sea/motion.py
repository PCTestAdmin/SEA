"""Small image translations for mechanical vibration studies; not audio recovery."""
from __future__ import annotations
from fractions import Fraction
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from .engine import decode, probe, run, input_args, window
from .spatial import region_pixels
from .vision import fingerprint
from .acoustics import png

MAX_SECONDS=8
MAX_SIDE=512


def native_rate(p):
    raw=run('ffprobe',['-v','error','-select_streams','v:0','-show_entries',
                       'stream=avg_frame_rate,r_frame_rate','-of','json',*input_args(p)],65536)
    streams=json.loads(raw).get('streams',[])
    if not streams:
        raise ValueError('No video stream.')
    try:
        rate=float(Fraction(streams[0]['avg_frame_rate']))
    except (ValueError,ZeroDivisionError,KeyError):
        raise ValueError('Source average frame rate unavailable.') from None
    if not math.isfinite(rate) or rate<=0:
        raise ValueError('Invalid source frame rate.')
    return rate


def load_motion_frames(p,start,seconds,fps):
    window(start,seconds,MAX_SECONDS)
    if fps not in (10,15,24,30,60):
        raise ValueError('Choose 10, 15, 24, 30 or 60 fps.')
    if seconds*fps>240:
        raise ValueError('Choose at most 240 requested samples.')
    before=fingerprint(p)
    meta=probe(p)
    stream=next((s for s in meta['streams'] if s.get('codec_type')=='video'),None)
    if stream is None:
        raise ValueError('Video required.')
    rate=native_rate(p)
    if fps>rate+0.001:
        raise ValueError('Choose a sample rate no higher than the source average frame rate.')
    w,h=int(stream['width']),int(stream['height'])
    if min(w,h)<1 or w*h>40_000_000:
        raise ValueError('Unsupported source dimensions.')
    scale=min(1,MAX_SIDE/max(w,h))
    w,h=max(1,round(w*scale)),max(1,round(h*scale))
    cap=(math.ceil(seconds*fps)+2)*w*h
    raw=decode(p,start,seconds,['-map','0:v:0','-an','-vf',f'fps={fps},scale={w}:{h},format=gray',
               '-pix_fmt','gray','-f','rawvideo'],cap,autorotate=False)
    if before!=fingerprint(p):
        raise RuntimeError('Source changed during motion analysis.')
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,h,w)[:math.ceil(seconds*fps)]
    if len(frames)<3:
        raise ValueError('At least three decoded samples required.')
    return frames,rate


def design(reference):
    a=reference.astype(np.float64)/255
    if min(a.shape)<16 or a.size>512*512:
        raise ValueError('Motion region must be at least 16 by 16 sampled pixels.')
    gy,gx=np.gradient(a)
    # Linearized brightness constancy, with an additive brightness offset.
    x=np.column_stack((-gx[2:-2,2:-2].ravel(),-gy[2:-2,2:-2].ravel(),
                       np.ones((a.shape[0]-4)*(a.shape[1]-4))))
    singular=np.linalg.svd(x,compute_uv=False)
    if singular[-1]<.01 or singular[0]/singular[-1]>500:
        raise ValueError('Region lacks two-dimensional texture for displacement measurement.')
    return a[2:-2,2:-2].ravel(),x,np.linalg.pinv(x)


def measure_region(frames,box):
    crop,bounds=region_pixels(frames[0],box)
    a,x,inv=design(crop)
    l,t,r,b=bounds
    rows=[]
    for frame in frames:
        y=frame[t+2:b-2,l+2:r-2].astype(np.float64).ravel()/255-a
        dx,dy,brightness=inv@y
        residual=float(np.sqrt(np.mean((y-x@np.array([dx,dy,brightness]))**2)))
        # Conservative operating envelope, not a calibrated uncertainty estimate.
        valid=math.hypot(dx,dy)<=1.5 and residual<=.035 and abs(brightness)<=.15
        rows.append({'dx_px':float(dx) if valid else None,'dy_px':float(dy) if valid else None,
                     'residual_rms':round(residual,6),'valid':bool(valid)})
    return rows,bounds


def frequency(values,fps):
    a=np.asarray(values,dtype=np.float64)
    if len(a)<2*fps:
        return None
    a=a-a.mean()
    rms=float(np.sqrt(np.mean(a*a)))
    if rms<.025:
        return None
    w=np.hanning(len(a))
    amp=np.abs(np.fft.rfft(a*w))*2/w.sum()
    freq=np.fft.rfftfreq(len(a),1/fps)
    # Exclude DC, first bin (drift) and Nyquist endpoint.
    candidates=np.arange(2,len(freq)-1)
    if not len(candidates):
        return None
    k=int(candidates[np.argmax(amp[candidates])])
    power=amp[candidates]**2
    share=float(amp[k]**2/power.sum()) if power.sum()>0 else 0
    if share<.25:
        return None
    return {'peak_hz':round(float(freq[k]),6),'amplitude_px_estimate':round(float(amp[k]),6),
            'frequency_bin_hz':round(fps/len(a),6),'peak_power_fraction':round(share,6),
            'demeaned_rms_px':round(rms,6)}


def analyze_frames(frames,box,fps,start=0,reference_box=None):
    target,bounds=measure_region(frames,box)
    ref=None; ref_bounds=None
    if reference_box is not None:
        ref,ref_bounds=measure_region(frames,reference_box)
        l,t,r,b=bounds; a,c,d,e=ref_bounds
        if max(l,a)<min(r,d) and max(t,c)<min(b,e):
            raise ValueError('Target and reference regions must not overlap.')
    rows=[]
    for i,row in enumerate(target):
        other=ref[i] if ref is not None else None
        ok=row['valid'] and (other is None or other['valid'])
        rows.append({'time_s':round(start+i/fps,6),'valid':bool(ok),
                     'dx_px':round(row['dx_px']-(other['dx_px'] if other else 0),6) if ok else None,
                     'dy_px':round(row['dy_px']-(other['dy_px'] if other else 0),6) if ok else None,
                     'target_residual_rms':row['residual_rms'],
                     'reference_residual_rms':other['residual_rms'] if other else None})
    complete=all(r['valid'] for r in rows)
    return {'sample_rate_fps':fps,'sample_size_px':[frames.shape[2],frames.shape[1]],
            'target_bounds_sample_px':bounds,'reference_bounds_sample_px':ref_bounds,
            'frame_count':len(rows),'valid_count':sum(r['valid'] for r in rows),
            'relative_to_reference':ref is not None,'samples':rows,
            'frequency_x':frequency([r['dx_px'] for r in rows],fps) if complete else None,
            'frequency_y':frequency([r['dy_px'] for r in rows],fps) if complete else None,
            'limitations':['First-order translation estimates relative to first frame; small motions only, not full optical flow.',
                           'Displacements use downsampled image pixels, not physical distance.',
                           'Fixed camera, textured planar target, stable light recommended. Reference subtraction only compensates common translation.',
                           'Approximate uniformly resampled timestamps; variable frame rate, aliasing, exposure and rolling shutter can distort frequency.',
                           'No frequencies inferred across invalid samples; low-amplitude or non-dominant spectral peaks suppressed.',
                           'Residual/texture thresholds are heuristics, not validated uncertainty bounds.',
                           'No audio reconstruction, medical monitoring, or diagnosis.']}


def analyze_motion(p: Path,box:list[float],start:float=0,seconds:float=4,fps:int=24,reference_box:list[float]|None=None):
    frames,native=load_motion_frames(p,start,seconds,fps)
    return {'file':p.name,'source_average_fps':native,'requested_window_s':[start,start+seconds],
            **analyze_frames(frames,box,fps,start,reference_box)}


def waveform(report):
    im=Image.new('RGB',(900,350),'#102331')
    draw=ImageDraw.Draw(im)
    draw.text((20,12),'SEA | Small-motion estimates (sample pixels)',fill='white')
    rows=report['samples']
    values=[abs(r[k]) for r in rows if r['valid'] for k in ('dx_px','dy_px')]
    scale=max(.1,max(values,default=0))
    left,right,top,bottom=65,875,55,285
    mid=(top+bottom)/2
    for v in (-scale,0,scale):
        y=mid-v/scale*(bottom-top)/2
        draw.line((left,y,right,y),fill='#456071')
        draw.text((4,int(y)-5),f'{v:.2f}',fill='white')
    for k,color in [('dx_px','#67e8f9'),('dy_px','#ffc66d')]:
        prev=None
        for i,row in enumerate(rows):
            if not row['valid']:
                prev=None
                continue
            x=left+(right-left)*i/max(1,len(rows)-1)
            y=mid-row[k]/scale*(bottom-top)/2
            if prev is not None:
                draw.line((*prev,x,y),fill=color,width=2)
            else:
                draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
            prev=(x,y)
    draw.text((left,300),f"{rows[0]['time_s']:.2f}s",fill='white')
    draw.text((right-55,300),f"{rows[-1]['time_s']:.2f}s",fill='white')
    draw.text((left,325),'X displacement',fill='#67e8f9')
    draw.text((left+180,325),'Y displacement',fill='#ffc66d')
    draw.text((left+370,325),'Gaps = rejected samples',fill='white')
    return png(np.asarray(im))
