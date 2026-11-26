"""Bounded compact video navigation; raw measurements stay inside SEA."""
from __future__ import annotations
import json
from collections import defaultdict
from .engine import resolve_media
from .video_understanding import source, plan_page, source_revision
from .video_perception import scan_page
from .scene_index import visual_data, audio_data
from .scan_cache import CACHE, enabled
from . import __version__

MIN_BUDGET=2048
MAX_BUDGET=16000
MAX_SEGMENTS=6


def encode(value):
    """ASCII JSON: exact byte length, also the number of JSON characters."""
    return json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(',',':'))


def merged(ranges):
    result=[]
    for a,b in ranges:
        if b<=a:
            continue
        if result and a<=result[-1][1]:
            result[-1][1]=max(b,result[-1][1])
        else:
            result.append([a,b])
    return result


def compact_row(row,fps):
    a,b=row['start_s'],row['end_s']
    n=row.get('sample_count',0)
    out={'i':row['index'],'end_s':b,'v':row['visual_status'],
         'a':row['audio_status'],'boundary':row['preceding_boundary_status'],
         'samples':n,'expected':row.get('expected_sample_count')}
    if row['visual_status'] in ('sampled','partial'):
        times,cuts,changes=visual_data(row,fps,row['preceding_boundary_status']=='observed')
        tick=lambda t:round((t-a)*fps)
        out['cuts']=[tick(t) for t in sorted(cuts)]
        if changes:
            t=max(changes,key=lambda t:(changes[t],-t))
            out['peak']=[tick(t),changes[t]]
        if times:
            # Three navigation hints at most; all candidate cut ticks remain separate.
            review={tick(times[0]),tick(times[len(times)//2]),tick(times[-1])}
            if changes:
                review.add(out['peak'][0])
            out['review']=sorted(review)
    length_ms=round((b-a)*1000)
    if row['audio_status'] in ('measured','partial'):
        data=audio_data(row)
        obs=[]
        low=[]
        freqs=defaultdict(float)
        for x,y,is_low,f in data:
            start=max(0,round((x-a)*1000))
            end=min(length_ms,round((y-a)*1000))
            obs.append((start,end))
            if is_low:
                low.append((start,end))
            elif f is not None:
                freqs[f]+=y-x
        out['observed_ms']=merged(obs)
        out['low_ms']=merged(low)
        out['freq_hz']=[f for f in sorted(freqs,key=lambda f:(-freqs[f],f))[:3]]
    # Not-present and unknown are distinct; no invented audio samples.
    return out


def overview(path,cursor=0,segment_seconds=12,max_segments=3,sample_fps=4,
             output_budget_bytes=6000,expected_revision=None):
    """Scan and project locally. Page by segment cursor, never by hidden truncation."""
    if (type(cursor) is not int or cursor<0
            or type(segment_seconds) is not int or segment_seconds not in (4,8,12)
            or type(max_segments) is not int or not 1<=max_segments<=MAX_SEGMENTS
            or type(sample_fps) is not int or sample_fps not in (1,2,4)
            or type(output_budget_bytes) is not int
            or not MIN_BUDGET<=output_budget_bytes<=MAX_BUDGET):
        raise ValueError('Invalid compact video settings.')
    p=resolve_media(path)
    rev,meta=source(p,expected_revision)
    plan=plan_page(meta['duration_s'],segment_seconds,cursor,max_segments)
    total=plan['total_segments']
    requested=len(plan['segments'])
    report={'schema':1,'source_revision':rev,'duration_s':meta['duration_s'],
            'segment_seconds':segment_seconds,'fps':sample_fps,'total_segments':total,
            'cursor':cursor,'next_cursor':cursor if cursor<total else None,
            'raw_rows_json_bytes':2,'rows':[],
            'units':'start_s=i*segment_seconds; cuts/review/peak[0] are relative frame ticks / fps; audio ranges are relative ms.',
            'note':'Sampled navigation only. Unobserved audio is not silence. No semantic or native-frame coverage. Details: analyze_target with same revision/settings and row i as cursor.'}
    raw_bytes=2
    # Each scan is bounded; do not send raw records or ask the host to echo them.
    pos=cursor
    use_cache=enabled()
    # Include the source revision and sampling settings, not output budget/page size.
    # Permission and current revision have already been checked before any lookup.
    def key(i):
        return (__version__,rev,segment_seconds,sample_fps,i)
    pending={}
    while pos<cursor+requested:
        cached=pending.pop(pos,None)
        if cached is None and use_cache:
            cached=CACHE.get(key(pos))
        if cached is None:
            count=min(3,cursor+requested-pos)
            page=scan_page(p,segment_seconds,pos,count,sample_fps,rev)
            rows=page['results']
            if len(rows)!=count or any(row['index']!=pos+j for j,row in enumerate(rows)):
                raise RuntimeError('Unexpected local scan cursor.')
            if source_revision(p)!=rev:
                raise RuntimeError('Video changed during compact analysis.')
            for row in rows:
                value=[compact_row(row,sample_fps),len(encode(row))]
                pending[row['index']]=value
                # Never cache incomplete or unavailable measurements; a retry may recover.
                if (use_cache and row['visual_status']=='sampled'
                        and row['audio_status'] in ('measured','not_present')
                        and row['preceding_boundary_status'] in ('observed','start_of_video')):
                    CACHE.put(key(row['index']),value)
            cached=pending.pop(pos)
        compact,row_bytes=cached
        candidate_raw=raw_bytes+row_bytes+(1 if report['rows'] else 0)
        next_cursor=pos+1 if pos+1<total else None
        candidate={**report,'rows':report['rows']+[compact],
                   'raw_rows_json_bytes':candidate_raw,'next_cursor':next_cursor}
        if len(encode(candidate))>output_budget_bytes:
            if not report['rows']:
                raise ValueError('Output budget too small for one segment; increase it.')
            break
        report=candidate
        raw_bytes=candidate_raw
        pos+=1
    if source_revision(p)!=rev:
        raise RuntimeError('Video changed during compact analysis.')
    if len(encode(report))>output_budget_bytes:
        raise RuntimeError('Compact output budget exceeded.')
    return report
