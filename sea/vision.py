"""Sampled visual evidence and bounded cross-modal investigations."""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from .engine import decode, probe, window, WIDTH, HEIGHT, FPS
from .acoustics import analyze_audio

MAX_VIDEO_SECONDS = 120
MAX_INVESTIGATION_SECONDS = 30


def fingerprint(p: Path) -> tuple:
    s = p.stat()
    return (s.st_size, s.st_mtime_ns, s.st_ino)


def load_frames(p: Path, start: float, seconds: float) -> np.ndarray:
    window(start, seconds, MAX_VIDEO_SECONDS)
    before = fingerprint(p)
    if not probe(p)['video']:
        raise ValueError('Media contains no video stream.')
    # Use the same grayscale and letterbox sampling convention as sense_media.
    size = WIDTH * HEIGHT
    raw = decode(p, start, seconds, [
        '-map', '0:v:0', '-an', '-vf',
        f'fps={FPS},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray',
        '-pix_fmt', 'gray', '-f', 'rawvideo'],
        (math.ceil(seconds * FPS) + 4) * size)
    if before != fingerprint(p):
        raise RuntimeError('Media changed during video analysis.')
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, HEIGHT, WIDTH)
    if not len(frames):
        raise ValueError('No video frames decoded in the requested window.')
    return frames[:math.ceil(seconds * FPS)]


def analyze_frames(frames: np.ndarray, start: float, seconds: float) -> dict:
    rows, events = [], []
    stable_start = None
    previous = None
    previous_hist = None
    for i, frame in enumerate(frames):
        t = round(start + i / FPS, 4)
        current = frame.astype(np.float32)
        hist = np.bincount((frame.ravel() // 16), minlength=16).astype(np.float64)
        hist /= hist.sum()
        row = {'time_s': t, 'mean_luma': round(float(current.mean()/255), 4),
               'mean_pixel_change': None, 'changed_pixel_fraction': None,
               'histogram_distance': None, 'change_region': None}
        if previous is not None:
            difference = np.abs(current - previous)
            mask = difference >= 25.5
            fraction = float(mask.mean())
            mean = float(difference.mean()/255)
            distance = float(np.abs(hist-previous_hist).sum()/2)
            row.update(mean_pixel_change=round(mean,4),
                       changed_pixel_fraction=round(fraction,4),
                       histogram_distance=round(distance,4))
            if fraction >= .005:
                y, x = np.where(mask)
                row['change_region'] = [round(float(x.min()/WIDTH),4),
                                        round(float(y.min()/HEIGHT),4),
                                        round(float((x.max()+1)/WIDTH),4),
                                        round(float((y.max()+1)/HEIGHT),4)]
            if mean >= .12 and distance >= .35:
                kind = 'large_global_change'
            elif fraction >= .05:
                kind = 'pixel_activity'
            else:
                kind = None
            if kind:
                events.append({'kind': kind, 'time_s': t, 'previous_sample_s': rows[-1]['time_s'],
                               'mean_pixel_change': row['mean_pixel_change'],
                               'changed_pixel_fraction': row['changed_pixel_fraction'],
                               'histogram_distance': row['histogram_distance'],
                               'change_region': row['change_region']})
            if mean <= .005:
                if stable_start is None:
                    stable_start = rows[-1]['time_s']
            elif stable_start is not None:
                if rows[-1]['time_s'] - stable_start >= 1:
                    events.append({'kind':'low_change_interval','start_s':stable_start,
                                   'end_s':rows[-1]['time_s']})
                stable_start = None
        rows.append(row)
        previous, previous_hist = current, hist
    if stable_start is not None and rows[-1]['time_s']-stable_start >= 1:
        events.append({'kind':'low_change_interval','start_s':stable_start,
                       'end_s':rows[-1]['time_s']})
    events.sort(key=lambda e: e.get('time_s', e.get('start_s', 0)))
    for i, e in enumerate(events, 1):
        e['id'] = f'V{i:04d}'
    return {'sample_rate_fps': FPS, 'sample_size':[WIDTH,HEIGHT],
            'requested_window_s':[start,start+seconds],
            'sampled_range_s':[rows[0]['time_s'],rows[-1]['time_s']],
            'frames':len(rows), 'events':events, 'samples':rows,
            'rules':{'pixel_delta_threshold':.1,'region_min_changed_fraction':.005,
                     'activity_min_changed_fraction':.05,'global_mean_difference':.12,
                     'global_histogram_distance':.35,'low_change_mean_difference':.005,
                     'low_change_min_span_s':1},
            'limitations':['Approximate 4 fps decoded offsets, not exact source PTS.',
                           'Grayscale pixel and histogram differences, not object tracking or confirmed scene cuts.',
                           'Change regions are normalized bounding boxes in the padded sample, not object coordinates.',
                           'Low change does not prove a frozen video; static scenes also qualify.']}


def analyze_video(p: Path, start: float=0, seconds: float=15) -> dict:
    return {'file':p.name, **analyze_frames(load_frames(p,start,seconds),start,seconds)}


def correlate(audio: list[dict], visual: list[dict], tolerance: float) -> list[dict]:
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 2:
        raise ValueError('Correlation tolerance must be 0–2 seconds.')
    points = [e for e in visual if 'time_s' in e]
    result=[]
    for a in audio:
        if 'time_s' not in a or not points:
            continue
        v=min(points,key=lambda v: (abs(v['time_s']-a['time_s']),v['time_s']))
        delta=v['time_s']-a['time_s']
        if abs(delta) <= tolerance + 1e-9:
            result.append({'audio_id':a['id'],'video_id':v['id'],
                           'audio_time_s':a['time_s'],'video_time_s':v['time_s'],
                           'video_minus_audio_s':round(delta,4),
                           'relationship':'temporal_proximity_only'})
    return result


def investigate(p: Path, start: float=0, seconds: float=15, tolerance: float=.5) -> dict:
    window(start, seconds, MAX_INVESTIGATION_SECONDS)
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 2:
        raise ValueError('Correlation tolerance must be 0–2 seconds.')
    before=fingerprint(p)
    meta=probe(p)
    if not meta['audio'] and not meta['video']:
        raise ValueError('No audio or video streams.')
    a=analyze_audio(p,start,seconds) if meta['audio'] else None
    v=analyze_video(p,start,seconds) if meta['video'] else None
    if before!=fingerprint(p):
        raise RuntimeError('Media changed during investigation.')
    ae=[dict(e,id=f'A{i:04d}') for i,e in enumerate(a['events'],1)] if a else []
    ve=v['events'] if v else []
    links=correlate(ae,ve,tolerance)
    matched={link['video_id'] for link in links}
    points=[e for e in ve if 'time_s' in e]
    # Prioritize cross-modal matches, then larger visual changes. Stable tie order.
    points.sort(key=lambda e:(e['id'] not in matched,-e['mean_pixel_change'],e['time_s']))
    recommendations=[{'time_s':e['time_s'],'evidence_id':e['id'],
                      'tool':'view_frame','reason':'Inspect the sampled visual change.'}
                     for e in points[:8]]
    return {'schema_version':1,'file':p.name,'requested_window_s':[start,start+seconds],
            'available_modalities':{'audio':a is not None,'video':v is not None},
            'audio_summary':{k:a[k] for k in ('analyzed_s','rms_dbfs','peak_dbfs','frequency_peaks')} if a else None,
            'video_summary':{k:v[k] for k in ('frames','sampled_range_s','sample_rate_fps')} if v else None,
            'audio_events':ae,'visual_events':ve,'correlations':links,
            'correlation_tolerance_s':tolerance,
            'recommended_followups':recommendations,
            'limitations':['Event IDs are local to this report; thresholds are heuristic.',
                           'Correlation is nearest visual point per audio level transition, not a one-to-one alignment.',
                           'Temporal proximity is not causation. Stream offsets and sampling can affect timestamps.',
                           'No semantic event classification or object identification.',
                           'An empty event list does not establish that nothing happened.',
                           *(a['limitations'] if a else []),*(v['limitations'] if v else [])]}
