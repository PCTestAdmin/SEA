"""Optional offline COCO object detector; no automatic model downloads."""
from __future__ import annotations
from collections import Counter
import hashlib
import importlib.util
import io
import math
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from .images import load_still
from .spatial import load_image, IMAGE_EXT
from .engine import window
from .acoustics import png

MODEL = 'torchvision/ssdlite320_mobilenet_v3_large/COCO_V1'
WEIGHTS_URL = 'https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth'
HASH_PREFIX = 'a79551df'
MAX_BYTES = 32 * 1024 * 1024


def checkpoint() -> tuple[bytes,str]:
    configured=os.environ.get('SEA_VISION_WEIGHTS','').strip()
    if not configured:
        raise ValueError('Vision AI is disabled. Set SEA_VISION_WEIGHTS to the official local checkpoint.')
    path=Path(configured).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ValueError('SEA_VISION_WEIGHTS must point to an existing absolute local file.')
    with path.open('rb') as f:
        raw=f.read(MAX_BYTES+1)
    if not raw or len(raw)>MAX_BYTES:
        raise ValueError('Invalid checkpoint size.')
    digest=hashlib.sha256(raw).hexdigest()
    if not digest.startswith(HASH_PREFIX):
        raise ValueError('Checkpoint does not match the official weight hash prefix.')
    return raw,digest


def status() -> dict:
    dependencies={name:importlib.util.find_spec(name) is not None for name in ('torch','torchvision')}
    result={'model':MODEL,'dependencies_discoverable':dependencies,
            'weights_configured':bool(os.environ.get('SEA_VISION_WEIGHTS','').strip()),
            'weights_prefix_verified':False,'ready_to_attempt':False,
            'weights_url':WEIGHTS_URL,'note':'Discovery is not a live inference test.'}
    if result['weights_configured']:
        try:
            _,digest=checkpoint()
        except (ValueError,OSError) as e:
            result['checkpoint_error']=str(e) if isinstance(e,ValueError) else 'Cannot read checkpoint.'
        else:
            result['weights_prefix_verified']=True
            result['weights_sha256']=digest
    result['ready_to_attempt']=all(dependencies.values()) and result['weights_prefix_verified']
    return result


def validate_options(threshold: float, limit: int):
    if not math.isfinite(threshold) or not .1<=threshold<=1:
        raise ValueError('Score threshold must be 0.1–1.')
    if not 1<=limit<=50:
        raise ValueError('Detection limit must be 1–50.')


def normalize_predictions(prediction: dict, categories: list[str], width: int, height: int,
                          threshold: float, limit: int) -> dict:
    validate_options(threshold,limit)
    rows=[]
    for box,label,score in zip(prediction['boxes'],prediction['labels'],prediction['scores']):
        score=float(score); label=int(label)
        if not math.isfinite(score) or not threshold<=score<=1 or not 0<label<len(categories):
            continue
        name=categories[label]
        if name in ('N/A','__background__'):
            continue
        if len(box)!=4 or any(not math.isfinite(float(v)) for v in box):
            continue
        l,t,r,b=[max(0.,min(1.,float(v)/size)) for v,size in zip(box,(width,height,width,height))]
        if not l<r or not t<b:
            continue
        rows.append({'label':name,'class_id':label,'score':round(score,6),'box':[l,t,r,b]})
    rows.sort(key=lambda row:-row['score'])
    selected=rows[:limit]
    for i,row in enumerate(selected,1):
        row['id']=f'D{i:03d}'
    return {'detections':selected,'matching_count':len(rows),'returned_count':len(selected),
            'truncated':len(rows)>limit,'label_counts':dict(Counter(r['label'] for r in selected))}


def load_detector():
    """Load one CPU model for a single analysis or bounded multi-frame call."""
    raw,digest=checkpoint()
    try:
        import torch
        from torchvision.models.detection import (
            ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights)
    except (ImportError,RuntimeError,OSError) as e:
        raise RuntimeError('Install a compatible torch/torchvision pair in the SEA environment; see docs/vision-ai.md.') from e
    weights=SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
    model=ssdlite320_mobilenet_v3_large(weights=None,weights_backbone=None)
    state=torch.load(io.BytesIO(raw),map_location='cpu',weights_only=True)
    model.load_state_dict(state,strict=True)
    model.eval()
    del raw,state
    categories=weights.meta['categories']
    transform=weights.transforms()
    provenance={'model':MODEL,'weights_sha256':digest,'torch_version':str(torch.__version__),'device':'cpu'}

    def predict(rgb: np.ndarray, threshold: float, limit: int) -> dict:
        validate_options(threshold,limit)
        sample=transform(Image.fromarray(rgb))
        with torch.inference_mode():
            prediction=model([sample])[0]
        h,w=rgb.shape[:2]
        return normalize_predictions({k:v.cpu().tolist() for k,v in prediction.items()},
                                     categories,w,h,threshold,limit)
    return predict,provenance,categories


def infer(rgb: np.ndarray, threshold: float, limit: int) -> dict:
    validate_options(threshold,limit)
    predict,provenance,_=load_detector()
    h,w=rgb.shape[:2]
    return {**provenance,'sample_size_px':[w,h],'threshold':threshold,**predict(rgb,threshold,limit),
            'limitations':['Model predictions, not verified facts or calibrated probabilities.',
                           'Fixed COCO classes; unknown or small objects may be missed.',
                           'Counts describe returned boxes, not guaranteed object counts.',
                           'No face identity, individual recognition or physical depth.',
                           'Coordinates are normalized coded-image coordinates; no EXIF autorotation.']}


def detect(p: Path,time_s: float=0,threshold: float=.5,limit: int=20) -> tuple[dict,np.ndarray]:
    window(time_s,.25)
    validate_options(threshold,limit)
    if p.suffix.lower() in IMAGE_EXT:
        if time_s!=0:
            raise ValueError('Still images require time_s=0.')
        rgb,source=load_still(p,1024)
    else:
        rgb=load_image(p,time_s)
        source=None
    report=infer(rgb,threshold,limit)
    return {'file':p.name,'requested_time_s':time_s,'source_size_px':source,**report,
            'timestamp_note':'Video time is an approximate requested decoded offset.'},rgb


def annotate(rgb: np.ndarray, detections: list[dict]) -> bytes:
    im=Image.fromarray(rgb.copy())
    draw=ImageDraw.Draw(im)
    w,h=im.size
    for row in detections:
        l,t,r,b=[int(v*(size-1)) for v,size in zip(row['box'],(w,h,w,h))]
        draw.rectangle((l,t,r,b),outline='#00e5ff',width=max(1,w//320))
        label=f"{row['id']} {row['label']} {row['score']:.2f}"
        x,y=l,max(0,t-13)
        draw.rectangle((x,y,min(w-1,x+len(label)*7),min(h-1,y+13)),fill='#102331')
        draw.text((x,y),label,fill='white')
    return png(np.asarray(im))
