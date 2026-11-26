"""Shared model-free analysis entry point and portable evidence projections."""
from __future__ import annotations
import math
from . import __version__
from .engine import resolve_media,probe,analyze
from .spatial import sense_spatial
from .signals import analyze_signals
from .video_perception import scan_page
from .video_understanding import source_revision
from .evidence import canonical,digest

MAX_EVIDENCE=512*1024


def analyze_target(path, cursor=0, segment_seconds=8, page_size=2, sample_fps=4,
                   start_s=0, duration_s=10, time_column=None, channels=None,
                   expected_revision=None):
    p=resolve_media(path,allow_image=True,allow_csv=True)
    rev=source_revision(p)
    if expected_revision is not None and rev!=expected_revision:
        raise ValueError('Source revision changed; restart the investigation.')
    if not math.isfinite(start_s) or not math.isfinite(duration_s):
        raise ValueError('Nonfinite time argument.')
    suffix=p.suffix.lower()
    if suffix in ('.png','.jpg','.jpeg'):
        kind='image'
    elif suffix=='.csv':
        kind='signals'
    else:
        meta=probe(p)
        kind='video' if meta['video'] else 'audio' if meta['audio'] else None
    if not kind:
        raise ValueError('No supported media streams.')
    if kind!='video' and cursor!=0:
        raise ValueError('Only video analysis is paginated.')
    if kind!='signals' and (time_column is not None or channels is not None):
        raise ValueError('Column arguments are only for CSV signals.')
    if kind=='video':
        if start_s!=0 or duration_s!=10:
            raise ValueError('For video use cursor, segment_seconds and page_size, not start_s/duration_s.')
        result=scan_page(p,segment_seconds,cursor,page_size,sample_fps,rev)
        params={'cursor':cursor,'segment_seconds':segment_seconds,'page_size':page_size,'sample_fps':sample_fps}
        collection='results'
        next_cursor=result['next_cursor']
        follow=['analyze_target','view_video_segment','read_video_frames','listen_video_segment']
        coverage='One sampled timeline page; follow next_cursor and inspect actual visual evidence.'
    elif kind=='audio':
        result=analyze(p,start_s,duration_s)
        params={'start_s':start_s,'duration_s':duration_s}
        collection='timeline'
        next_cursor=None
        follow=['sense_audio','audio_spectrogram','compare_recordings']
        coverage='Requested audio window only; decoded duration may be shorter.'
    elif kind=='image':
        if start_s!=0 or duration_s!=10:
            raise ValueError('Still image analysis does not use time arguments.')
        result=sense_spatial(p,0,3)
        params={'grid_size':3}
        collection=None
        next_cursor=None
        follow=['inspect_region','read_image_text','compare_images']
        coverage='Spatial measurements of one downsampled still image.'
    else:
        if not time_column or not channels:
            raise ValueError('CSV requires time_column and channels.')
        if start_s!=0 or duration_s!=10:
            raise ValueError('CSV analysis does not use time arguments.')
        result=analyze_signals(p,time_column,channels)
        params={'time_column':time_column,'channels':channels}
        collection=None
        next_cursor=None
        follow=['sense_signals','remember_signals']
        coverage='Bounded CSV measurements of explicitly selected channels.'
    if rev!=source_revision(p):
        raise RuntimeError('Source changed during analysis.')
    record={'schema_version':1,'engine_version':__version__,'operation':'analyze_target',
            'target_kind':kind,'source_revision':rev,'parameters':params,'normalized_result':result,
            'collection':collection,'next_cursor':next_cursor,'coverage':coverage,'follow_up_tools':follow,
            'limitations':['SEA measures evidence; the host interprets it. No model inference in this entry point.',
                           'Source revision is a path/stat fingerprint, not a source content hash.',
                           'Evidence digest checks record consistency, not authenticity or measurement correctness.',
                           'No persistent storage by this operation.']}
    if len(canonical(record))>MAX_EVIDENCE:
        raise ValueError('Evidence exceeds 512 KiB; reduce the page or window.')
    return {'evidence_id':digest(record),'record':record}


def inspect_view(evidence,view='summary',offset=0,limit=20):
    if not isinstance(evidence,dict) or set(evidence)!= {'evidence_id','record'}:
        raise ValueError('Expected a complete analyze_target evidence envelope.')
    record=evidence['record']
    if not isinstance(record,dict) or len(canonical(record))>MAX_EVIDENCE:
        raise ValueError('Invalid or oversized evidence record.')
    if evidence['evidence_id']!=digest(record):
        raise ValueError('Evidence digest mismatch.')
    if record.get('schema_version')!=1 or record.get('operation')!='analyze_target':
        raise ValueError('Unsupported evidence contract.')
    if not 0<=offset<=1_000_000 or not 1<=limit<=100:
        raise ValueError('Invalid evidence view bounds.')
    result=record.get('normalized_result')
    if not isinstance(result,dict):
        raise ValueError('Invalid normalized result.')
    name=record.get('collection')
    rows=result.get(name) if isinstance(name,str) else None
    if name is not None and not isinstance(rows,list):
        raise ValueError('Invalid collection.')
    common={'parent_evidence_id':evidence['evidence_id'],'view':view,'target_kind':record['target_kind'],
            'coverage':record['coverage'],'source_revision':record['source_revision'],
            'analysis_next_cursor':record['next_cursor'],
            'limitations':['Projection of caller-supplied evidence; hash is not a signature.']}
    if view=='summary':
        return {**common,'parameters':record['parameters'],'collection':name,'row_count':len(rows) if rows is not None else None,
                'follow_up_tools':record['follow_up_tools'],
                'result_keys':sorted(result)}
    if view=='page':
        if rows is None:
            raise ValueError('This record has no pageable collection.')
        if offset>len(rows):
            raise ValueError('Offset beyond collection.')
        end=min(len(rows),offset+limit)
        return {**common,'collection':name,'offset':offset,'rows':rows[offset:end],
                'next_offset':end if end<len(rows) else None}
    raise ValueError('Choose summary or page.')
