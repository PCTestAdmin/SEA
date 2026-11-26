"""Model-free reusable visual fingerprints and bounded template search."""
from __future__ import annotations
import math
import numpy as np
from PIL import Image
from . import temporal
from .engine import run,input_args
from .images import load_still,template_match
from .video_understanding import source,source_revision,plan_page,sample_frames
from .vision import fingerprint

SIDE=32
MAX_SAMPLES=12000
SIGNATURE_VERSION=1


def signatures(frames):
    """48 coarse RGB values plus 56 luminance comparison bits, packed in 7 bytes."""
    if frames.ndim!=4 or frames.shape[1:]!=(SIDE,SIDE,3):
        raise ValueError('Expected 32x32 RGB frames.')
    n=len(frames)
    color=np.rint(frames.reshape(n,4,8,4,8,3).mean(axis=(2,4))).astype(np.uint8).reshape(n,48)
    small=frames.reshape(n,8,4,8,4,3).mean(axis=(2,4))
    gray=small@np.array([.2126,.7152,.0722])
    bits=(gray[:,:,1:]>gray[:,:,:-1]).reshape(n,56)
    return color,np.packbits(bits,axis=1)


def image_signature(p):
    arr,_=load_still(p,1024)
    resized=np.asarray(Image.fromarray(arr).resize((SIDE,SIDE),Image.Resampling.BILINEAR))
    color,bits=signatures(resized[None])
    return color[0],bits[0]


def tables(db):
    db.execute('CREATE TABLE IF NOT EXISTS visual_indexes (revision TEXT PRIMARY KEY REFERENCES videos(revision) ON DELETE CASCADE, stride INTEGER NOT NULL, count INTEGER NOT NULL, algorithm INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS visual_frames (revision TEXT REFERENCES visual_indexes(revision) ON DELETE CASCADE, ordinal INTEGER NOT NULL, color BLOB NOT NULL, bits BLOB NOT NULL, PRIMARY KEY(revision,ordinal))')


def existing(db,rev):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='visual_indexes'").fetchone():
        return None
    return db.execute('SELECT * FROM visual_indexes WHERE revision=?',(rev,)).fetchone()


def info(row):
    return {'source_revision':row['revision'],'sample_stride_frames':row['stride'],
            'indexed_sample_count':row['count'],'signature_version':row['algorithm'],
            'descriptor':'4x4 coarse RGB means and 56 luminance difference bits',
            'note':'Sampled decoded ordinals, not a semantic index. Descriptors may reveal coarse colors/layout.'}


def build(p,stride=30,confirm=False):
    if not confirm:
        raise ValueError('Persistent visual indexing requires explicit user approval.')
    if not 1<=stride<=300:
        raise ValueError('Choose a frame stride from 1 to 300.')
    with temporal.database() as db:
        rev,video=temporal.require(db,p)
        count=video['count']
        old=existing(db,rev)
        if old:
            if old['stride']!=stride or old['algorithm']!=SIGNATURE_VERSION:
                raise ValueError('Visual index already exists with different settings; delete it explicitly before rebuilding.')
            return {**info(old),'reused':True}
    expected=math.ceil(count/stride)
    if expected>MAX_SAMPLES:
        raise ValueError('More than 12000 samples; choose a larger stride.')
    vf=f'select=not(mod(n\\,{stride})),scale={SIDE}:{SIDE}:flags=bilinear,format=rgb24'
    raw=run('ffmpeg',['-hide_banner','-loglevel','error','-xerror','-nostdin','-max_alloc','134217728',
        '-threads','2',*input_args(p)[:-1],'-noautorotate','-i',str(p),'-map','0:v:0','-an',
        '-filter_threads','1','-threads','2','-vf',vf,'-fps_mode','passthrough',
        '-frames:v',str(expected+1),'-pix_fmt','rgb24','-f','rawvideo','pipe:1'],
        (expected+1)*SIDE*SIDE*3,timeout=120)
    if len(raw)!=expected*SIDE*SIDE*3:
        raise RuntimeError('Decoded sample count differs from temporal index; no visual index saved.')
    if rev!=source_revision(p):
        raise RuntimeError('Video changed during visual indexing.')
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(expected,SIDE,SIDE,3)
    # Bound temporary float arrays by processing batches.
    with temporal.database(write=True) as db:
        current,video=temporal.require(db,p)
        if current!=rev or video['count']!=count:
            raise RuntimeError('Temporal index changed during visual indexing.')
        tables(db)
        old=existing(db,rev)
        if old:
            if old['stride']!=stride or old['algorithm']!=SIGNATURE_VERSION:
                raise ValueError('Different visual index was created concurrently.')
            return {**info(old),'reused':True}
        db.execute('INSERT INTO visual_indexes VALUES (?,?,?,?)',(rev,stride,expected,SIGNATURE_VERSION))
        for start in range(0,expected,128):
            colors,bits=signatures(frames[start:start+128])
            db.executemany('INSERT INTO visual_frames VALUES (?,?,?,?)',
                ((rev,(start+i)*stride,c.tobytes(),b.tobytes()) for i,(c,b) in enumerate(zip(colors,bits))))
        if rev!=source_revision(p):
            raise RuntimeError('Video changed before visual index commit.')
        return {**info(existing(db,rev)),'reused':False}


def score_rows(rows,color,bits,threshold,limit,exclude):
    hits=[]
    for row in rows:
        ordinal=row['ordinal']
        if ordinal==exclude:
            continue
        c=np.frombuffer(row['color'],dtype=np.uint8)
        h=np.frombuffer(row['bits'],dtype=np.uint8)
        if c.size!=48 or h.size!=7:
            raise ValueError('Corrupt visual descriptor; rebuild index.')
        color_score=1-float(np.abs(c.astype(np.int16)-color.astype(np.int16)).mean()/255)
        hash_score=1-float(np.unpackbits(np.bitwise_xor(h,bits)).mean())
        score=.7*color_score+.3*hash_score
        if score>=threshold:
            hits.append({'frame_index':ordinal,'relative_s':row['relative_s'],'pts_ticks':row['pts'],
                         'similarity':round(score,6),'color_similarity':round(color_score,6),
                         'hash_similarity':round(hash_score,6)})
    hits.sort(key=lambda r:(-r['similarity'],r['frame_index']))
    return hits[:limit],len(hits)


def search(p,reference_image=None,reference_frame=None,threshold=.9,limit=30):
    if (reference_image is None)==(reference_frame is None):
        raise ValueError('Choose exactly one reference image or indexed reference frame.')
    if not math.isfinite(threshold) or not 0<=threshold<=1 or not 1<=limit<=100:
        raise ValueError('Threshold 0–1, limit 1–100.')
    ref_before=fingerprint(reference_image) if reference_image is not None else None
    descriptor=image_signature(reference_image) if reference_image is not None else None
    with temporal.database() as db:
        rev,video=temporal.require(db,p)
        idx=existing(db,rev)
        if idx is None or idx['algorithm']!=SIGNATURE_VERSION:
            raise ValueError('Build a compatible visual index first.')
        if reference_frame is not None:
            ref=db.execute('SELECT color,bits FROM visual_frames WHERE revision=? AND ordinal=?',(rev,reference_frame)).fetchone()
            if ref is None:
                raise ValueError('Reference ordinal is not sampled in this index; choose a multiple of the stride.')
            descriptor=(np.frombuffer(ref['color'],dtype=np.uint8),np.frombuffer(ref['bits'],dtype=np.uint8))
        rows=db.execute('SELECT v.ordinal,v.color,v.bits,f.relative_s,f.pts FROM visual_frames v JOIN frames f ON f.revision=v.revision AND f.ordinal=v.ordinal WHERE v.revision=?',(rev,)).fetchall()
        if len(rows)!=idx['count']:
            raise RuntimeError('Visual index is incomplete; rebuild it.')
        hits,total=score_rows(rows,*descriptor,threshold,limit,reference_frame)
        result={**info(idx),'reference_frame':reference_frame,'reference_image':reference_image.name if reference_image else None,
                'threshold':threshold,'matches':hits,'matching_sample_count':total,
                'limitations':['Similarity is a heuristic, not probability or object identity.',
                               'Whole-frame appearance only; crops, viewpoints, illumination and aspect ratio changes can alter scores.',
                               'Images are stretched to a square in coded orientation; query images are resized with Pillow, video frames with FFmpeg.',
                               'Only indexed samples are searched; brief scenes and objects between samples may be missed.',
                               'relative_s is relative to first known video PTS, not necessarily audio/container time. Verify actual frames.']}
    if rev!=source_revision(p) or (reference_image is not None and ref_before!=fingerprint(reference_image)):
        raise RuntimeError('Source or reference changed during search.')
    return result


def delete(p,confirm=False):
    if not confirm:
        raise ValueError('Visual index deletion requires explicit user approval.')
    with temporal.database(write=True) as db:
        rev,_=temporal.require(db,p)
        if not existing(db,rev):
            raise ValueError('No visual index.')
        db.execute('DELETE FROM visual_indexes WHERE revision=?',(rev,))
    return {'source_revision':rev,'status':'deleted','note':'Temporal timestamps and observation notes retained; logical deletion only.'}


def template_page(p,reference,cursor=0,sample_fps=2,threshold=.9,expected_revision=None):
    if sample_fps not in (1,2,4) or not math.isfinite(threshold) or not .5<=threshold<=1:
        raise ValueError('Choose 1, 2 or 4 fps and threshold 0.5–1.')
    rev,meta=source(p,expected_revision)
    plan=plan_page(meta['duration_s'],4,cursor,1)
    before=fingerprint(reference)
    template,size=load_still(reference,448)
    h,w=template.shape[:2]
    if size!=[w,h] or not 4<=w<=224 or not 4<=h<=126:
        raise ValueError('Use a 4x4 to 224x126 template at the 448x252 sampled-video scale.')
    gray=template.astype(np.float64)@np.array([.2126,.7152,.0722])
    if gray.std()<1e-4:
        raise ValueError('Template needs nonconstant luminance.')
    matches=[]
    status='complete_cursor' if not plan['segments'] else 'failed'
    count=0
    error=None
    if plan['segments']:
        seg=plan['segments'][0]
        try:
            frames=sample_frames(p,seg['start_s'],seg['end_s'],sample_fps)
            count=len(frames)
            status='sampled' if count==math.ceil((seg['end_s']-seg['start_s'])*sample_fps) else 'partial'
            for i,frame in enumerate(frames):
                hit=template_match(frame,template,threshold)
                if hit['matches']:
                    matches.append({'approximate_time_s':round(seg['start_s']+i/sample_fps,3),
                                    'matches':hit['matches']})
        except (ValueError,RuntimeError,OSError) as exc:
            status='failed'
            error=type(exc).__name__
    if rev!=source_revision(p) or before!=fingerprint(reference):
        raise RuntimeError('Video or reference changed during template search.')
    return {'source_revision':rev,**plan,'sample_fps':sample_fps,'sample_count':count,
            'status':status,'error':error,'template_size_px':size,'threshold':threshold,'matches':matches,
            'limitations':['Same-scale grayscale normalized cross-correlation on letterboxed 448x252 frames.',
                           'Normalized boxes refer to the sampled letterboxed image, not the original coded frame.',
                           'No rotation, perspective, scale or semantic object recognition. Scores are not probabilities.',
                           'Follow next_cursor across all pages; retry failed/partial pages. No match is not proof of absence.']}
