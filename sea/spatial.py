"""Bounded image-space measurements; no physical depth or object recognition."""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from .engine import decode, probe, window
from .acoustics import png
from .vision import fingerprint

SIZE = 512
IMAGE_EXT = {'.png', '.jpg', '.jpeg'}


def load_image(p: Path, time_s: float) -> np.ndarray:
    window(time_s,.25)
    if p.suffix.lower() in IMAGE_EXT and time_s != 0:
        raise ValueError('Still images require time_s=0.')
    before=fingerprint(p)
    meta=probe(p)
    stream=next((s for s in meta['streams'] if s.get('codec_type')=='video'),None)
    if stream is None:
        raise ValueError('No visual stream.')
    w,h=int(stream['width']),int(stream['height'])
    if w<1 or h<1 or w*h>40_000_000:
        raise ValueError('Unsupported source dimensions.')
    # Explicit output dimensions, without letterboxing. Autorotation is disabled.
    scale=min(1,SIZE/max(w,h))
    width,height=max(1,round(w*scale)),max(1,round(h*scale))
    raw=decode(p,time_s,1,['-map','0:v:0','-an','-frames:v','1','-vf',
               f'scale={width}:{height},format=rgb24','-pix_fmt','rgb24','-f','rawvideo'],
               width*height*3, autorotate=False)
    if before!=fingerprint(p):
        raise RuntimeError('Media changed during analysis.')
    if len(raw)!=width*height*3:
        raise ValueError('No complete frame at requested time.')
    return np.frombuffer(raw,dtype=np.uint8).reshape(height,width,3)


def region_pixels(image: np.ndarray, box: list[float]) -> tuple[np.ndarray,list[int]]:
    if len(box)!=4 or any(not math.isfinite(x) or not 0<=x<=1 for x in box):
        raise ValueError('Region must contain four normalized coordinates in [0,1].')
    l,t,r,b=box
    if not l<r or not t<b:
        raise ValueError('Region must have positive width and height.')
    h,w=image.shape[:2]
    x0,y0,x1,y1=math.floor(l*w),math.floor(t*h),math.ceil(r*w),math.ceil(b*h)
    return image[y0:y1,x0:x1],[x0,y0,x1,y1]


def features(rgb: np.ndarray) -> dict:
    a=rgb.astype(np.float64)/255
    y=a @ np.array([.2126,.7152,.0722])
    # Mean gradient on adjacent samples; density is a simple contrast heuristic.
    dx=np.abs(np.diff(y,axis=1)).ravel()
    dy=np.abs(np.diff(y,axis=0)).ravel()
    d=np.concatenate([dx,dy])
    return {'mean_rgb_8bit':[round(float(v),2) for v in rgb.mean(axis=(0,1))],
            'mean_luma':round(float(y.mean()),5),
            'luma_std':round(float(y.std()),5),
            'edge_fraction':round(float(np.mean(d>=.1)),5) if len(d) else None}


def spatial_grid(image: np.ndarray, grid: int) -> dict:
    if grid not in (2,3,4,5,6):
        raise ValueError('Grid size must be 2–6.')
    h,w=image.shape[:2]
    if min(h,w)<grid:
        raise ValueError('Sample is smaller than the selected grid.')
    xs=np.linspace(0,w,grid+1,dtype=int)
    ys=np.linspace(0,h,grid+1,dtype=int)
    cells=[]
    for row in range(grid):
        for col in range(grid):
            l,t,r,b=int(xs[col]),int(ys[row]),int(xs[col+1]),int(ys[row+1])
            cells.append({'id':f'R{row+1}C{col+1}','box':[l/w,t/h,r/w,b/h],
                          **features(image[t:b,l:r])})
    return {'sample_size_px':[w,h],'grid_size':grid,'overall':features(image),
            'regions':cells,
            'coordinate_system':'Normalized image coordinates; origin top-left.',
            'limitations':['Downsampled RGB frame; approximate timestamp for video.',
                           'Edge fraction is adjacent luma contrast, not object detection.',
                           'No depth, physical dimensions, distance or semantic layout inference.']}


def sense_spatial(p: Path,time_s: float=0,grid: int=3) -> dict:
    return {'file':p.name,'requested_time_s':time_s,**spatial_grid(load_image(p,time_s),grid)}


def crop_region(p: Path,time_s: float,box: list[float]) -> bytes:
    crop,_=region_pixels(load_image(p,time_s),box)
    return png(np.ascontiguousarray(crop))
