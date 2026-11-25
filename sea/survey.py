"""Budgeted deterministic coarse-to-fine investigation of local recordings."""
from __future__ import annotations
import time
import math
from pathlib import Path
from .engine import analyze, probe, window
from .vision import investigate, fingerprint

MAX_SPAN=1800
SCAN_SECONDS=6
REFINE_SECONDS=4
SCHEDULE_SECONDS=75


def plan_windows(start: float, span: float, max_windows: int) -> list[tuple[float,float]]:
    window(start,span,MAX_SPAN)
    if not 1<=max_windows<=5:
        raise ValueError('max_windows must be 1–5.')
    n=min(max_windows,max(1,math.ceil(span/SCAN_SECONDS)))
    stratum=span/n
    duration=min(SCAN_SECONDS,stratum)
    return [(start+i*stratum+(stratum-duration)/2,duration) for i in range(n)]


def candidate_events(report: dict, window_id: str) -> list[dict]:
    result=[]
    previous=None
    for row in report['timeline']:
        reasons=[]
        visual=row.get('max_frame_change')
        if row.get('visual_change_flag') and visual is not None:
            reasons.append({'kind':'visual_change','value':visual,'threshold':.12})
        if (previous is not None and row.get('audio_observed') and previous.get('audio_observed')
                and abs(row['start_s']-previous['end_s'])<=.001):
            a,b=previous.get('audio_rms_dbfs'),row.get('audio_rms_dbfs')
            a=max(-100,a if a is not None else -100)
            b=max(-100,b if b is not None else -100)
            if abs(b-a)>=12 and max(a,b)>=-40:
                reasons.append({'kind':'audio_level_change','delta_db':round(b-a,2),'threshold_db':12})
        if reasons:
            strength=max(r['value']/.12 if r['kind']=='visual_change' else abs(r['delta_db'])/12 for r in reasons)
            result.append({'window_id':window_id,'time_s':row['start_s'],'bin_end_s':row['end_s'],
                           'evidence':reasons,'priority':round(len(reasons)*10+min(9,strength),4)})
        previous=row
    return result


def investigate_recording(p: Path,start: float=0,span: float=60,
                          max_windows: int=5,max_refinements: int=2) -> dict:
    planned=plan_windows(start,span,max_windows)
    if not 0<=max_refinements<=2:
        raise ValueError('max_refinements must be 0–2.')
    before=fingerprint(p)
    meta=probe(p)
    if not meta['audio'] and not meta['video']:
        raise ValueError('No audio or video streams.')
    if meta['duration_s'] is not None:
        available=meta['duration_s']-start
        if available<.25:
            raise ValueError('Requested start is outside usable media duration.')
        span=min(span,available)
        planned=plan_windows(start,span,max_windows)
    deadline=time.monotonic()+SCHEDULE_SECONDS
    scanned,candidates,refinements=[],[],[]
    def check_source():
        if before!=fingerprint(p):
            raise RuntimeError('Source changed during investigation.')
    for i,(s,d) in enumerate(planned,1):
        wid=f'W{i:02d}'
        item={'id':wid,'requested_range_s':[round(s,4),round(s+d,4)]}
        if time.monotonic()>=deadline:
            scanned.append(dict(item,status='not_attempted',reason='Scheduling budget reached.'))
            continue
        try:
            r=analyze(p,s,d)
        except (ValueError,RuntimeError,OSError) as exc:
            check_source()
            scanned.append(dict(item,status='failed',reason=type(exc).__name__))
            continue
        check_source()
        observed=[x for x in r['timeline'] if x.get('audio_observed') or x.get('video_frames',0)>0]
        scanned.append(dict(item,status='scanned' if observed else 'no_observations',
                            observed_bins=len(observed),audio_bins=sum(bool(x.get('audio_observed')) for x in observed),
                            video_frames=sum(x.get('video_frames',0) for x in observed),
                            first_observed_bin_s=observed[0]['start_s'] if observed else None,
                            last_observed_bin_s=observed[-1]['start_s'] if observed else None))
        candidates.extend(candidate_events(r,wid))
    candidates.sort(key=lambda e:(-e['priority'],e['time_s'],e['window_id']))
    for i,c in enumerate(candidates,1):
        c['id']=f'C{i:04d}'
    selected=[]
    for c in candidates:
        if len(selected)>=max_refinements:
            break
        if any(abs(c['time_s']-x['time_s'])<REFINE_SECONDS/2 for x in selected):
            continue
        selected.append(c)
    for c in selected:
        duration=min(REFINE_SECONDS,span)
        offset=max(start,min(c['time_s']-duration/2,start+span-duration))
        item={'candidate_id':c['id'],'requested_range_s':[round(offset,4),round(offset+duration,4)]}
        if time.monotonic()>=deadline:
            refinements.append(dict(item,status='not_attempted',reason='Scheduling budget reached.'))
            continue
        try:
            r=investigate(p,offset,duration)
        except (ValueError,RuntimeError,OSError) as exc:
            check_source()
            refinements.append(dict(item,status='failed',reason=type(exc).__name__))
            continue
        check_source()
        refinements.append(dict(item,status='refined',report=r))
    check_source()
    gaps=[]
    cursor=start
    for w in scanned:
        if w['status']!='scanned':
            continue
        a,b=w['requested_range_s']
        if a>cursor+1e-4:
            gaps.append([round(cursor,4),a])
        cursor=max(cursor,b)
    if cursor<start+span-1e-4:
        gaps.append([round(cursor,4),round(start+span,4)])
    return {'schema_version':1,'file':p.name,'media':meta,'survey_range_s':[start,round(start+span,4)],
            'scan_windows':scanned,'unscanned_requested_ranges_s':gaps,'candidate_count':len(candidates),
            'candidates':candidates[:20],'refinements':refinements,
            'budget':{'max_windows':max_windows,'max_refinements':max_refinements,
                      'scan_window_max_s':SCAN_SECONDS,'refinement_max_s':REFINE_SECONDS,
                      'soft_scheduling_seconds':SCHEDULE_SECONDS},
            'limitations':['Deterministic sampled survey, not exhaustive video understanding.',
                           'Gaps and window boundaries may hide events; sampled windows are approximate.',
                           'Candidate priority is a heuristic, not a probability or severity score. At most 20 candidates returned.',
                           'Refinement reports have local evidence IDs; cite candidate ID and report ID together.',
                           'Temporal proximity is not causation. No semantic classification or diagnosis.',
                           'Scheduling deadline stops new operations; running decoders may take longer.',
                           'No candidate does not establish that nothing happened.']}
