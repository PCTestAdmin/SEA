"""Model-free temporal and spatial relations from caller-supplied video evidence."""
from __future__ import annotations
import math
from .analysis import audit_video_coverage

MAX_EVENT_PAGE=100
VISUAL_GAP_S=2.0
AUDIO_TOLERANCE_S=.5


def finite_number(value):
    return type(value) in (int,float) and math.isfinite(value)


def close(a,b):
    return finite_number(a) and finite_number(b) and abs(a-b)<=.0011


def relate(evidence_pages,offset=0,limit=50):
    if type(offset) is not int or not 0<=offset<=10000 or type(limit) is not int or not 1<=limit<=MAX_EVENT_PAGE:
        raise ValueError('Invalid event page bounds.')
    coverage=audit_video_coverage(evidence_pages)
    fps=coverage['sample_fps']
    segments=sorted([(row,page['evidence_id']) for page in evidence_pages
                     for row in page['record']['normalized_result']['results']],key=lambda pair:pair[0]['index'])
    events=[]
    audio_by_run={}
    visual=[]
    previous_visual=None
    previous_audio=None
    prior_index=None
    run=-1
    skipped=[]
    for row,evidence_id in segments:
        index=row['index']
        start,end=row['start_s'],row['end_s']
        usable=row['visual_status']=='sampled' and row['audio_status'] in ('measured','not_present')
        joined=usable and prior_index is not None and index==prior_index+1 and row['preceding_boundary_status']=='observed'
        if not joined:
            run+=1
            previous_visual=previous_audio=None
        if not usable:
            skipped.append(row['id'])
            prior_index=None
            continue
        prior_index=index
        times=row.get('sample_times_s')
        comparisons=row.get('comparisons')
        n=row['sample_count']
        if not isinstance(times,list) or len(times)!=n or any(not close(t,start+i/fps) for i,t in enumerate(times)):
            raise ValueError('Invalid sampled frame times.')
        first=0 if row['preceding_boundary_status']=='observed' else 1
        if not isinstance(comparisons,list) or len(comparisons)!=n-first:
            raise ValueError('Invalid visual comparison sequence.')
        for i,c in enumerate(comparisons,first):
            if not isinstance(c,dict) or not close(c.get('time_s'),times[i]) or c.get('boundary_comparison') is not (i==0):
                raise ValueError('Invalid visual comparison timestamp or boundary.')
            tiles=c.get('changed_tiles_4x4')
            if not isinstance(tiles,list) or any(type(t) is not int or not 0<=t<16 for t in tiles) or tiles!=sorted(set(tiles)):
                raise ValueError('Missing or invalid change grid; regenerate evidence with SEA v0.22 or newer.')
            fraction=c.get('changed_pixel_fraction')
            cut=c.get('scene_change_candidate')
            if not finite_number(fraction) or not 0<=fraction<=1 or type(cut) is not bool:
                raise ValueError('Invalid visual measurement.')
            if i==0 and not joined:
                continue  # Preceding evidence row is unavailable in this audit.
            if not cut and not tiles and fraction<.05:
                continue
            event={'id':f'V{index+1:06d}:{i:02d}','segment_id':row['id'],
                   'evidence_id':evidence_id,'time_s':times[i],
                   'kind':'scene_change_candidate' if cut else 'visual_change',
                   'changed_pixel_fraction':fraction,'changed_tiles_4x4':tiles,'relations':[]}
            if previous_visual is not None:
                gap=round(event['time_s']-previous_visual['time_s'],3)
                if 0<gap<=VISUAL_GAP_S:
                    relation={'kind':'follows_visual_change','target_id':previous_visual['id'],'lag_s':gap}
                    if event['kind']==previous_visual['kind']=='visual_change':
                        a,b=set(tiles),set(previous_visual['changed_tiles_4x4'])
                        if a and b:
                            relation['tile_jaccard']=round(len(a&b)/len(a|b),4)
                    event['relations'].append(relation)
            previous_visual=event
            events.append(event)
            visual.append((run,event))
        if row['audio_status']=='not_present':
            previous_audio=None
            continue
        bins=row.get('audio_bins')
        if not isinstance(bins,list) or not 1<=len(bins)<=math.ceil((end-start)*2)+1:
            raise ValueError('Invalid audio bin sequence.')
        for i,b in enumerate(bins):
            if not isinstance(b,dict):
                raise ValueError('Invalid audio bin.')
            a,z=b.get('start_s'),b.get('end_s')
            low=b.get('low_level')
            if (not close(a,start+i*.5) or not finite_number(z) or not a<z<=end+.031
                    or z-a>.5011 or type(low) is not bool):
                raise ValueError('Invalid audio bin bounds or level flag.')
            if previous_audio is not None and close(previous_audio['end_s'],a) and low!=previous_audio['low_level']:
                event={'id':f'A{index+1:06d}:{i:02d}','segment_id':row['id'],
                       'evidence_id':evidence_id,'time_s':a,
                       'kind':'audio_became_low' if low else 'audio_left_low_level','relations':[]}
                events.append(event)
                audio_by_run.setdefault(run,[]).append(event)
            previous_audio=b
    for run,event in visual:
        candidates=[a for a in audio_by_run.get(run,[]) if abs(a['time_s']-event['time_s'])<=AUDIO_TOLERANCE_S]
        if candidates:
            best=min(candidates,key=lambda a:(abs(a['time_s']-event['time_s']),a['time_s'],a['id']))
            event['relations'].append({'kind':'near_audio_transition','target_id':best['id'],
                                       'audio_minus_visual_s':round(best['time_s']-event['time_s'],3)})
    events.sort(key=lambda e:(e['time_s'],e['id']))
    if offset>len(events):
        raise ValueError('Offset beyond event collection.')
    stop=min(offset+limit,len(events))
    return {'schema_version':1,'source_revision':coverage['source_revision'],
            'evidence_ids':coverage['evidence_ids'],'duration_s':coverage['duration_s'],
            'sample_fps':fps,'missing_ranges':coverage['missing_ranges'],
            'incomplete_segments':coverage['incomplete_segments'],'skipped_segments':skipped,
            'event_count':len(events),'offset':offset,'next_offset':stop if stop<len(events) else None,
            'events':events[offset:stop],
            'thresholds':{'tile_grid':[4,4],'tile_changed_fraction':.10,'pixel_delta':25,
                          'global_changed_fraction':.05,'visual_gap_s':VISUAL_GAP_S,
                          'audio_tolerance_s':AUDIO_TOLERANCE_S,'audio_low_level_rms':.01},
            'limitations':['Only supplied complete sampled segments are used. Missing, partial or failed segments break continuity.',
                           'Boundary comparisons are omitted if the preceding submitted segment is unavailable.',
                           'Tiles are zero-based row-major in padded sample coordinates. Overlap is not object identity or tracking.',
                           'Visual differences can reflect camera motion, lighting, cuts or compression.',
                           'Audio low-level changes use 0.5 s bins; timestamps are approximate. Proximity is not causation.',
                           'Links target event IDs in the same input batch, possibly on another output page.',
                           'This is not a semantic event detector, native-frame coverage or source authentication.']}
