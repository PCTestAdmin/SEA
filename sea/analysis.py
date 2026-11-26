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
    # Normalize API/MCP/CLI numeric representations before measurement and hashing.
    start_s, duration_s = float(start_s), float(duration_s)
    if start_s == 0:
        start_s = 0.0
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
        follow=['analyze_target','audit_video_coverage','relate_video_events','summarize_video_scenes','view_video_segment','read_video_frames','listen_video_segment']
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


def audit_video_coverage(evidence_pages):
    """Audit caller-supplied sampled timeline pages, without decoding or persistence."""
    from .video_understanding import plan_page
    if not isinstance(evidence_pages,list) or not 1<=len(evidence_pages)<=16:
        raise ValueError('Supply 1–16 complete video evidence envelopes.')
    signature=None
    observed={}
    ids=[]
    for envelope in evidence_pages:
        view=inspect_view(envelope)
        if view['target_kind']!='video' or view['collection']!='results':
            raise ValueError('Expected video analyze_target evidence.')
        record=envelope['record']
        params=record['parameters']
        result=record['normalized_result']
        duration=result.get('duration_s')
        segment=params.get('segment_seconds')
        fps=params.get('sample_fps')
        cursor=params.get('cursor')
        size=params.get('page_size')
        if (type(cursor) is not int or type(size) is not int or not 1<=size<=3
                or type(segment) is not int or type(fps) is not int or fps not in (1,2,4)
                or type(duration) not in (int,float)):
            raise ValueError('Invalid video page parameters.')
        plan=plan_page(duration,segment,cursor,size)
        key=(record['source_revision'],record['engine_version'],duration,segment,fps)
        if signature is None:
            signature=key
        elif signature!=key:
            raise ValueError('Video pages use different source revisions, engine versions or sampling settings.')
        if (result.get('source_revision')!=key[0] or result.get('sample_fps')!=fps
                or any(result.get(k)!=v for k,v in plan.items())
                or record['next_cursor']!=plan['next_cursor']):
            raise ValueError('Video evidence does not match its segment plan.')
        rows=result['results']
        if not rows or len(rows)!=len(plan['segments']):
            raise ValueError('Expected a nonempty, complete page of segment status rows.')
        for row,expected in zip(rows,plan['segments']):
            i=expected['index']
            if not isinstance(row,dict) or any(row.get(k)!=v for k,v in expected.items()):
                raise ValueError('Video segment does not match its plan.')
            if i in observed:
                raise ValueError('Overlapping or duplicate video segments.')
            visual=row.get('visual_status')
            audio=row.get('audio_status')
            boundary=row.get('preceding_boundary_status')
            if visual not in ('sampled','partial','failed') or audio not in ('measured','partial','failed','not_present'):
                raise ValueError('Unknown modality status.')
            if boundary not in ('observed','unavailable','start_of_video') or (boundary=='start_of_video')!=(i==0):
                raise ValueError('Invalid preceding boundary status.')
            if visual in ('sampled','partial'):
                n=row.get('sample_count')
                target=math.ceil((expected['end_s']-expected['start_s'])*fps)
                if (type(n) is not int or not 1<=n<=target or row.get('expected_sample_count')!=target
                        or (visual=='sampled')!=(n==target)):
                    raise ValueError('Inconsistent visual sample count.')
            observed[i]={'id':expected['id'],'start_s':expected['start_s'],'end_s':expected['end_s'],
                         'visual_status':visual,'audio_status':audio,'preceding_boundary_status':boundary}
        ids.append(envelope['evidence_id'])
    rev,version,duration,segment,fps=signature
    count=math.ceil(duration/segment)
    missing=[]
    start=0
    for i in sorted(observed):
        if i>start:
            missing.append({'start_cursor':start,'end_cursor_exclusive':i,'start_s':start*segment,
                            'end_s':min(duration,i*segment)})
        start=i+1
    if start<count:
        missing.append({'start_cursor':start,'end_cursor_exclusive':count,'start_s':start*segment,'end_s':duration})
    rows=[observed[i] for i in sorted(observed)]
    incomplete=[r for r in rows if r['visual_status']!='sampled' or r['audio_status'] not in ('measured','not_present')
                or r['preceding_boundary_status']=='unavailable']
    return {'source_revision':rev,'engine_version':version,'duration_s':duration,
            'segment_seconds':segment,'sample_fps':fps,'total_segments':count,'submitted_segments':len(rows),
            'missing_segments':count-len(rows),'missing_ranges':missing,'incomplete_segments':incomplete,
            'all_segment_rows_submitted':not missing,
            'all_sampled_measurements_reported_complete':not missing and not incomplete,
            'evidence_ids':sorted(ids),
            'limitations':['Only the supplied digested records are audited; no source is read and digests are not signatures.',
                           'Complete sampled coverage is not exhaustive native-frame inspection or semantic understanding.',
                           'Maximum 16 pages per audit; longer investigations may need separate range audits.']}
