"""Read-only numeric sensor CSV analysis, without device access or unit inference."""
from __future__ import annotations
import csv
import io
import math
from pathlib import Path
from itertools import combinations
import numpy as np
from .vision import fingerprint

MAX_BYTES=2*1024*1024
MAX_ROWS=20_000
MAX_CHANNELS=8
MAX_MAGNITUDE=1e100


def number(value: str, row: int, col: str) -> float:
    try:
        x=float(value)
    except (ValueError,TypeError):
        raise ValueError(f'Invalid number in row {row}, column {col!r}.') from None
    if not math.isfinite(x) or abs(x)>MAX_MAGNITUDE:
        raise ValueError(f'Non-finite or out-of-range number in row {row}, column {col!r}.')
    return x


def read_signals(p: Path,time_column: str,channels: list[str]) -> tuple[np.ndarray,np.ndarray]:
    if p.suffix.lower()!='.csv':
        raise ValueError('Signal input must be a CSV file.')
    if not 1<=len(channels)<=MAX_CHANNELS or len(set(channels))!=len(channels) or time_column in channels:
        raise ValueError('Select 1–8 distinct numeric channels, excluding the time column.')
    before=fingerprint(p)
    with p.open('rb') as f:
        raw=f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError('CSV exceeds 2 MiB.')
    if before!=fingerprint(p):
        raise RuntimeError('CSV changed during read.')
    try:
        reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
        header=next(reader,None)
        if not header or len(header)>64 or len(header)!=len(set(header)) or any(not s or len(s)>128 for s in header):
            raise ValueError('CSV needs 1–64 unique nonempty header names (max 128 characters each).')
        if any(c not in header for c in [time_column,*channels]):
            raise ValueError('Selected columns are missing from the CSV header.')
        idx=[header.index(c) for c in [time_column,*channels]]
        rows=[]
        for line,row in enumerate(reader,2):
            if len(rows)>=MAX_ROWS:
                raise ValueError('CSV exceeds 20,000 data rows.')
            if len(row)!=len(header):
                raise ValueError(f'Incorrect column count in row {line}.')
            rows.append([number(row[i],line,header[i]) for i in idx])
    except (UnicodeError,csv.Error) as e:
        raise ValueError('Expected UTF-8 comma-separated numeric CSV.') from e
    if len(rows)<2:
        raise ValueError('At least two data rows required.')
    arr=np.asarray(rows,dtype=np.float64)
    t=arr[:,0]
    if np.any(np.diff(t)<=0):
        raise ValueError('Time column must contain strictly increasing seconds.')
    return t,arr[:,1:]


def describe_signals(t: np.ndarray, values: np.ndarray, names: list[str], thresholds: dict[str,float]|None=None) -> dict:
    thresholds={} if thresholds is None else thresholds
    for name,threshold in thresholds.items():
        if name not in names or not math.isfinite(threshold) or not 0<threshold<=MAX_MAGNITUDE:
            raise ValueError('Change thresholds must be positive finite values for selected channels.')
    dt=np.diff(t)
    summaries=[]
    for i,name in enumerate(names):
        x=values[:,i]
        dx=np.diff(x)
        order=np.argsort(-np.abs(dx),kind='stable')
        top=[int(k) for k in order[:8] if dx[k]!=0]
        hits=np.flatnonzero(np.abs(dx)>=thresholds[name]) if name in thresholds else np.array([],dtype=int)
        strongest=sorted((int(k) for k in hits),key=lambda k:(-abs(dx[k]),k))[:20]
        def event(k):
            return {'from_s':float(t[k]),'to_s':float(t[k+1]),'delta':float(dx[k]),
                    'previous':float(x[k]),'current':float(x[k+1])}
        summaries.append({'channel':name,'min':float(x.min()),'max':float(x.max()),
                          'mean':float(x.mean()),'median':float(np.median(x)),
                          'std_population':float(x.std()),'net_change':float(x[-1]-x[0]),
                          'largest_adjacent_changes':[event(k) for k in top],
                          'change_threshold':thresholds.get(name),
                          'threshold_hit_count':int(len(hits)) if name in thresholds else None,
                          'threshold_events':[event(k) for k in sorted(strongest)]})
    pairs=[]
    for i,j in combinations(range(len(names)),2):
        a,b=values[:,i],values[:,j]
        if np.all(a==a[0]) or np.all(b==b[0]):
            r=None
        else:
            # Scaling before centering avoids overflow and reduces underflow.
            a=a/max(abs(a));b=b/max(abs(b))
            a=a-a.mean();b=b-b.mean()
            denom=float(np.linalg.norm(a)*np.linalg.norm(b))
            r=float(np.clip(np.dot(a,b)/denom,-1,1)) if denom>0 else None
        pairs.append({'a':names[i],'b':names[j],'pearson_r':round(r,6) if r is not None else None})
    return {'rows':len(t),'time_range_s':[float(t[0]),float(t[-1])],
            'median_sample_interval_s':float(np.median(dt)),
            'min_sample_interval_s':float(dt.min()),'max_sample_interval_s':float(dt.max()),
            'channels':summaries,'same_row_correlations':pairs,
            'limitations':['Time column is assumed to be seconds; channel units are supplied by the user, not inferred.',
                           'Largest changes and optional thresholds use adjacent sample differences, not rates or statistical anomalies.',
                           'At most eight largest changes and twenty strongest threshold events per channel are returned; counts include all hits.',
                           'Pearson coefficients use paired rows, not time weighting or lag alignment; correlation is not causation.',
                           'No live sensor access, calibration or physical diagnosis.']}


def analyze_signals(p: Path,time_column: str,channels: list[str],thresholds: dict[str,float]|None=None) -> dict:
    t,x=read_signals(p,time_column,channels)
    return {'file':p.name,**describe_signals(t,x,channels,thresholds)}
