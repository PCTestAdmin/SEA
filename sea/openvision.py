"""Optional local text-conditioned object localization using OWLv2."""
from __future__ import annotations
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import numpy as np
from PIL import Image
from .images import load_still
from .spatial import load_image, IMAGE_EXT
from .engine import window
from .detector import annotate

MODEL='google/owlv2-base-patch16-ensemble'
REVISION='27d9485a27e88c5f0435d0ed8382dcb3b911ab46'
MAX_MODEL_BYTES=2*1024**3


def model_dir() -> Path:
    value=os.environ.get('SEA_OPEN_VISION_DIR','').strip()
    if not value:
        raise ValueError('Open Vision is disabled. Configure SEA_OPEN_VISION_DIR.')
    p=Path(value).expanduser()
    if not p.is_absolute() or not p.is_dir():
        raise ValueError('SEA_OPEN_VISION_DIR must be an existing absolute directory.')
    for name in ('config.json','preprocessor_config.json','model.safetensors'):
        f=p/name
        if not f.is_file() or not 0<f.stat().st_size<=(MAX_MODEL_BYTES if name.endswith('.safetensors') else 1024**2):
            raise ValueError('Incomplete or oversized local OWLv2 model files.')
    return p


def status() -> dict:
    deps={name:importlib.util.find_spec(name) is not None for name in ('torch','torchvision','transformers','safetensors','scipy')}
    result={'recommended_model':MODEL,'dependencies_discoverable':deps,
            'directory_configured':bool(os.environ.get('SEA_OPEN_VISION_DIR','').strip()),
            'model_files_present':False,'ready_to_attempt':False,
            'note':'File discovery only; no inference or authenticity check.'}
    if result['directory_configured']:
        try:
            model_dir()
        except (ValueError,OSError) as e:
            result['error']=str(e) if isinstance(e,ValueError) else 'Cannot inspect model directory.'
        else:
            result['model_files_present']=True
    result['ready_to_attempt']=all(deps.values()) and result['model_files_present']
    return result


def validate_queries(queries: list[str],threshold: float,limit: int) -> list[str]:
    if not 1<=len(queries)<=8:
        raise ValueError('Supply 1–8 short visual object descriptions.')
    q=[s.strip() for s in queries]
    if any(not 1<=len(s)<=80 or any(ord(c)<32 for c in s) for s in q) or len(set(s.casefold() for s in q))!=len(q):
        raise ValueError('Queries must be distinct, printable and 1–80 characters.')
    if not math.isfinite(threshold) or not .05<=threshold<=1 or not 1<=limit<=50:
        raise ValueError('Threshold must be 0.05–1 and limit 1–50.')
    return q


def iou(a,b):
    overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    area=lambda x:(x[2]-x[0])*(x[3]-x[1])
    return overlap/(area(a)+area(b)-overlap) if overlap else 0.


def normalize(boxes,scores,labels,queries,width,height,threshold,limit):
    rows=[]
    for box,score,label in zip(boxes,scores,labels):
        score=float(score)
        if not math.isfinite(score) or not threshold<=score<=1 or label not in queries:
            continue
        if len(box)!=4 or any(not math.isfinite(float(x)) for x in box):
            continue
        b=[max(0.,min(1.,float(v)/n)) for v,n in zip(box,(width,height,width,height))]
        if b[0]>=b[2] or b[1]>=b[3]:
            continue
        rows.append({'label':label,'score':round(score,6),'box':b})
    rows.sort(key=lambda x:-x['score'])
    kept=[]
    for r in rows:
        if any(r['label']==k['label'] and iou(r['box'],k['box'])>.5 for k in kept):
            continue
        kept.append(r)
    detections=kept[:limit]
    for i,r in enumerate(detections,1):
        r['id']=f'Q{i:03d}'
    return {'detections':detections,'matching_count':len(kept),'returned_count':len(detections),
            'truncated':len(kept)>limit,'nms_iou_threshold':.5}


def search(p: Path,queries: list[str],time_s: float=0,threshold: float=.2,limit: int=20):
    q=validate_queries(queries,threshold,limit)
    window(time_s,.25)
    directory=model_dir()
    try:
        import torch
        import transformers
        from transformers import Owlv2Processor, Owlv2ForObjectDetection
    except (ImportError,RuntimeError,OSError) as e:
        raise RuntimeError('Install the optional openvision dependencies in the SEA environment.') from e
    if p.suffix.lower() in IMAGE_EXT:
        if time_s!=0:
            raise ValueError('Still images require time_s=0.')
        rgb,_=load_still(p,1024)
    else:
        rgb=load_image(p,time_s)
    processor=Owlv2Processor.from_pretrained(str(directory),local_files_only=True,use_fast=False)
    model=Owlv2ForObjectDetection.from_pretrained(str(directory),local_files_only=True,use_safetensors=True)
    model.eval()
    # OWLv2 text encoder has a short context. Reject truncation rather than silently changing a query.
    max_tokens=model.config.text_config.max_position_embeddings
    for query in q:
        if len(processor.tokenizer(query,add_special_tokens=True,truncation=False)['input_ids'])>max_tokens:
            raise ValueError('A visual query exceeds the model token limit; use shorter English phrases.')
    h,w=rgb.shape[:2]
    inputs=processor(text=[q],images=Image.fromarray(rgb),return_tensors='pt')
    with torch.inference_mode():
        out=model(**inputs)
        r=processor.post_process_grounded_object_detection(outputs=out,
             target_sizes=torch.tensor([(h,w)]),threshold=threshold,text_labels=[q])[0]
    result=normalize(r['boxes'].cpu().tolist(),r['scores'].cpu().tolist(),r['text_labels'],q,w,h,threshold,limit)
    with (directory/'model.safetensors').open('rb') as f:
        digest=hashlib.file_digest(f,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else _digest(f)
    return {'file':p.name,'requested_time_s':time_s,'queries':q,'threshold':threshold,
            'model_architecture':'OWLv2','recommended_model':MODEL,'weights_sha256':digest,
            'transformers_version':transformers.__version__,'sample_size_px':[w,h],'device':'cpu',**result,
            'limitations':['Text-conditioned predictions, not verified identities or calibrated probabilities.',
                           'English short object descriptions recommended; abstract or relational queries may fail.',
                           'Overlapping different labels may refer to the same object. Absence of a box is not proof of absence.',
                           'No face identification, tracking, physical depth or exact video timestamps.',
                           'Local checkpoint digest identifies weights; it is not an authenticity check.']},rgb


def _digest(f):
    h=hashlib.sha256()
    for block in iter(lambda:f.read(1024*1024),b''):
        h.update(block)
    return h.hexdigest()


def overlay(report,rgb):
    return annotate(rgb,report['detections'])
