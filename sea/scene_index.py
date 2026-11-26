"""Compact, model-free scene navigation over portable sampled evidence."""
from __future__ import annotations
import math
from collections import defaultdict
from .analysis import audit_video_coverage
from .event_relations import close, finite_number


def visual_data(row, fps, joined):
    """Validate sampled comparisons; never trust a cut across a missing boundary."""
    start,end=row['start_s'],row['end_s']
    n=row['sample_count']
    times=row.get('sample_times_s')
    comparisons=row.get('comparisons')
    first=0 if row['preceding_boundary_status']=='observed' else 1
    if (not isinstance(times,list) or len(times)!=n
            or any(not close(t,start+i/fps) for i,t in enumerate(times))
            or not isinstance(comparisons,list) or len(comparisons)!=n-first):
        raise ValueError('Invalid sampled visual timeline.')
    cuts={}
    changes={}
    for i,c in enumerate(comparisons,first):
        if (not isinstance(c,dict) or not close(c.get('time_s'),times[i])
                or c.get('boundary_comparison') is not (i==0)
                or not finite_number(c.get('changed_pixel_fraction'))
                or not 0<=c['changed_pixel_fraction']<=1
                or type(c.get('scene_change_candidate')) is not bool):
            raise ValueError('Invalid scene comparison.')
        if i==0 and not joined:
            continue
        t=start+i/fps
        if t>=end:
            continue
        if c['scene_change_candidate']:
            cuts[t]=c['changed_pixel_fraction']
        else:
            changes[t]=c['changed_pixel_fraction']
    return [start+i/fps for i in range(n) if start+i/fps<end],cuts,changes


def audio_data(row):
    """Return actual observed bin spans, not padded or fabricated samples."""
    start,end=row['start_s'],row['end_s']
    status=row['audio_status']
    if status not in ('measured','partial'):
        return []
    bins=row.get('audio_bins')
    if not isinstance(bins,list) or not 1<=len(bins)<=math.ceil((end-start)*2)+1:
        raise ValueError('Invalid audio bin sequence.')
    result=[]
    previous=None
    for i,b in enumerate(bins):
        if not isinstance(b,dict):
            raise ValueError('Invalid audio bin.')
        a,z=b.get('start_s'),b.get('end_s')
        low,freq=b.get('low_level'),b.get('dominant_frequency_hz')
        if (not close(a,start+i*.5) or not finite_number(z)
                or not a<z<=end+.031 or z-a>.5011 or type(low) is not bool
                or (freq is not None and (not finite_number(freq) or not 0<freq<=8000))
                or (previous is not None and a<previous-.0011)):
            raise ValueError('Invalid audio bin bounds or measurement.')
        a=max(start,a,previous if previous is not None else start)
        z=min(end,z)
        if z>a:
            result.append((a,z,low,freq))
            previous=z
    return result


def summarize(evidence_pages, offset=0, limit=20):
    """Partition the timeline into candidate scenes and explicit unknown spans."""
    if type(offset) is not int or not 0<=offset<=10000 or type(limit) is not int or not 1<=limit<=50:
        raise ValueError('Invalid scene page bounds.')
    coverage=audit_video_coverage(evidence_pages)
    fps=coverage['sample_fps']
    duration=coverage['duration_s']
    pairs=sorted(((r,p['evidence_id']) for p in evidence_pages
                  for r in p['record']['normalized_result']['results']),key=lambda x:x[0]['index'])
    scenes=[]
    audio=[]
    absent=[]
    last_end=0
    previous_sampled=False

    def append(a,b,reason,visual,ref=None,samples=(),changes=(),cut=None,merge=False):
        if b<=a:
            return
        if merge and scenes and scenes[-1]['visual_status']==visual and scenes[-1]['end_s']==a:
            s=scenes[-1]
            s['end_s']=b
        else:
            s={'start_s':a,'end_s':b,'start_reason':reason,'visual_status':visual,
               'entry_cut_changed_fraction':cut,'refs':{},'samples':[],'changes':[]}
            scenes.append(s)
        if ref is not None:
            s['refs'][ref[0]]=ref[1]
            s['samples'].extend((t,ref[0],ref[1]) for t in samples)
        s['changes'].extend(changes)

    for row,eid in pairs:
        a,b=row['start_s'],row['end_s']
        ref=(row['id'],eid)
        if a>last_end:
            append(last_end,a,'missing_evidence','unavailable')
            previous_sampled=False
        joined=previous_sampled and last_end==a and row['preceding_boundary_status']=='observed'
        audio.extend(audio_data(row))
        if row['audio_status']=='not_present':
            absent.append((a,b))
        if row['visual_status']=='sampled':
            times,cuts,changes=visual_data(row,fps,joined)
            bounds=sorted({a,b,*cuts})
            for x,y in zip(bounds,bounds[1:]):
                is_cut=x in cuts
                reason=('scene_change_candidate' if is_cut else 'video_start' if x==0
                        else 'after_gap_or_unobserved_boundary')
                append(x,y,reason,'sampled',ref,
                       (t for t in times if x<=t<y),
                       (v for t,v in changes.items() if x<=t<y),
                       cuts.get(x),merge=(x==a and joined and not is_cut))
            previous_sampled=True
        else:
            append(a,b,'incomplete_visual_evidence','unavailable',ref)
            previous_sampled=False
        last_end=b
    if last_end<duration:
        append(last_end,duration,'missing_evidence','unavailable')
    if offset>len(scenes):
        raise ValueError('Offset beyond scene collection.')
    stop=min(offset+limit,len(scenes))
    output=[]
    for index in range(offset,stop):
        s=scenes[index]
        a,b=s['start_s'],s['end_s']
        length=b-a
        observed=low=0.
        frequencies=defaultdict(float)
        for x,y,is_low,freq in audio:
            overlap=max(0.,min(b,y)-max(a,x))
            if overlap:
                observed+=overlap
                if is_low:
                    low+=overlap
                elif freq is not None:
                    frequencies[freq]+=overlap
        no_audio=sum(max(0.,min(b,y)-max(a,x)) for x,y in absent)
        unknown=max(0.,length-observed-no_audio)
        samples=s['samples']
        chosen=sorted({0,len(samples)-1,min(range(len(samples)),key=lambda i:abs(samples[i][0]-(a+b)/2))}) if samples else []
        output.append({'id':f'S{index+1:06d}','start_s':a,'end_s':b,
                       'start_reason':s['start_reason'],'visual_status':s['visual_status'],
                       'entry_cut_changed_fraction':s['entry_cut_changed_fraction'],
                       'sample_count':len(samples),
                       'max_non_cut_changed_fraction':max(s['changes'],default=None),
                       'representative_samples':[{'time_s':round(samples[i][0],3),
                           'segment_id':samples[i][1],'evidence_id':samples[i][2]} for i in chosen],
                       'audio':{'observed_s':round(observed,6),'low_level_observed_s':round(low,6),
                                'no_stream_s':round(no_audio,6),'unknown_s':round(unknown,6),
                                'dominant_frequency_candidates_hz':[
                                    {'frequency_hz':f,'bin_overlap_s':round(frequencies[f],6)}
                                    for f in sorted(frequencies,key=lambda f:(-frequencies[f],f))[:3]]},
                       'evidence_segments':[{'segment_id':k,'evidence_id':v} for k,v in s['refs'].items()]})
    return {'schema_version':1,'source_revision':coverage['source_revision'],
            'engine_version':coverage['engine_version'],'duration_s':duration,'sample_fps':fps,
            'evidence_ids':coverage['evidence_ids'],'missing_ranges':coverage['missing_ranges'],
            'incomplete_segments':coverage['incomplete_segments'],
            'all_sampled_measurements_reported_complete':coverage['all_sampled_measurements_reported_complete'],
            'scene_count':len(scenes),'offset':offset,'next_offset':stop if stop<len(scenes) else None,
            'scenes':output,
            'limitations':['Candidate scenes are bounded by sampled pixel changes, not semantic scene recognition.',
                           'Unavailable visual spans do not hide independently measured audio; unknown audio is not silence.',
                           'Audio level and frequency summaries use overlap with half-second bins, not exact within-bin timing.',
                           'Representative samples are navigation hints; inspect actual frames for interpretation.',
                           'Scene IDs are local to this exact evidence batch; separate batches can split scenes.',
                           'No source decoding, persistent writes, model inference, or proof of source authenticity.']}
