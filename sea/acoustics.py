"""Bounded acoustic measurement, without semantic sound classification."""
from __future__ import annotations
import math
from pathlib import Path
import struct
import zlib
import numpy as np
from .engine import RATE, decode, window, db, probe

NFFT = 1024
HOP = 256
BIN = RATE // 10
MAX_SECONDS = 30
BANDS = [(0, 125), (125, 500), (500, 2000), (2000, 4000), (4000, 8000)]


def load_audio(p: Path, start: float, seconds: float) -> np.ndarray:
    window(start, seconds, MAX_SECONDS)
    before = p.stat()
    if not probe(p)['audio']:
        raise ValueError('Media contains no audio stream.')
    raw = decode(p, start, seconds,
                 ['-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(RATE), '-f', 'f32le'],
                 int(seconds * RATE * 4) + RATE * 4)
    x = np.frombuffer(raw, dtype='<f4').astype(np.float64)
    after = p.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise RuntimeError('Media changed during analysis.')
    if not len(x) or not np.all(np.isfinite(x)):
        raise ValueError('No finite decoded audio samples.')
    return x[:math.ceil(seconds * RATE)]


def spectrum(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """One-sided amplitude spectrum; Hann window coherent-gain correction."""
    if len(x) < NFFT:
        x = np.pad(x, (0, NFFT - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, NFFT)[::HOP]
    w = np.hanning(NFFT)
    centered = frames - frames.mean(axis=1, keepdims=True)
    amp = np.abs(np.fft.rfft(centered * w, axis=1)) * (2 / w.sum())
    amp[:, [0, -1]] *= .5
    return np.fft.rfftfreq(NFFT, 1 / RATE), amp


def analyze_samples(x: np.ndarray, start: float) -> dict:
    freq, amp = spectrum(x)
    power = np.mean(amp**2, axis=0)
    power[0] = 0
    total = float(power.sum())
    peaks = []
    if total > 1e-18:
        candidates = [i for i in range(1, len(power)-1)
                      if power[i] > power[i-1] and power[i] >= power[i+1]
                      and power[i] >= power.max() * .001]
        for i in sorted(candidates, key=lambda i: power[i], reverse=True)[:5]:
            peaks.append({'frequency_hz': round(float(freq[i]), 2),
                          'relative_power_db': round(10 * math.log10(float(power[i] / power.max())), 2)})
    bands = []
    for lo, hi in BANDS:
        mask = (freq >= lo) & ((freq <= hi) if hi == RATE/2 else (freq < hi))
        bands.append({'range_hz': [lo, hi],
                      'fraction': round(float(power[mask].sum()/total), 5) if total > 1e-18 else None})
    levels = []
    events = []
    previous = None
    active_start = None
    for offset in range(0, len(x), BIN):
        chunk = x[offset:offset+BIN]
        level = float(np.sqrt(np.mean(chunk**2)))
        t = start + offset / RATE
        end = start + (offset+len(chunk))/RATE
        active = level >= .01
        levels.append({'start_s': round(t, 4), 'end_s': round(end, 4),
                       'rms_dbfs': db(level), 'peak_dbfs': db(float(np.max(np.abs(chunk))))})
        if active and active_start is None:
            active_start = t
        if not active and active_start is not None:
            events.append({'kind': 'above_threshold_interval', 'start_s': round(active_start, 4), 'end_s': round(t, 4)})
            active_start = None
        if previous is not None:
            change = 20 * math.log10(max(level, 1e-5)/max(previous, 1e-5))
            if abs(change) >= 12 and max(level, previous) >= .01:
                events.append({'kind': 'level_rise' if change > 0 else 'level_drop',
                               'time_s': round(t, 4), 'delta_db': round(change, 2)})
        previous = level
    if active_start is not None:
        events.append({'kind': 'above_threshold_interval', 'start_s': round(active_start, 4),
                       'end_s': round(start+len(x)/RATE, 4)})
    events.sort(key=lambda row: row.get('time_s', row.get('start_s', 0)))
    return {'sample_rate_hz': RATE, 'analyzed_s': round(len(x)/RATE, 4),
            'rms_dbfs': db(float(np.sqrt(np.mean(x**2)))),
            'peak_dbfs': db(float(np.max(np.abs(x)))),
            'spectral_centroid_hz': round(float(np.dot(freq, power)/total), 2) if total > 1e-18 else None,
            'frequency_peaks': peaks, 'band_power_fractions': bands,
            'frequency_bin_hz': RATE/NFFT, 'level_bin_s': .1,
            'event_rules': {'active_rms_dbfs': -40, 'adjacent_change_db': 12, 'change_floor_dbfs': -100},
            'events': events, 'levels': levels,
            'limitations': ['First audio stream, mono mix at 16 kHz; frequencies above 8 kHz are unavailable.',
                            'FFT peaks use 15.625 Hz bins, not exact pitch estimates. Power spectrum excludes DC.',
                            'Events are fixed-threshold digital level changes, not semantic sounds or statistical anomalies.',
                            'Timestamps are approximate decoded offsets; final incomplete FFT window may be omitted.',
                            'Digital level is not calibrated loudness or a diagnosis. Null dBFS denotes silence.']}


def analyze_audio(p: Path, start: float = 0, seconds: float = 15) -> dict:
    return {'file': p.name, 'start_s': start, **analyze_samples(load_audio(p, start, seconds), start)}


def compare_audio(a: Path, b: Path, start_a: float, start_b: float, seconds: float) -> dict:
    first = analyze_audio(a, start_a, seconds)
    second = analyze_audio(b, start_b, seconds)
    if abs(first['analyzed_s']-second['analyzed_s']) > 1/RATE:
        raise ValueError('Comparison requires equal decoded durations; choose a shorter window.')
    def delta(key):
        u, v = first[key], second[key]
        return round(v-u, 2) if u is not None and v is not None else None
    keys = ('file', 'start_s', 'analyzed_s', 'rms_dbfs', 'peak_dbfs', 'spectral_centroid_hz',
            'frequency_peaks', 'band_power_fractions')
    return {'a': {k:first[k] for k in keys}, 'b': {k:second[k] for k in keys},
            'delta_b_minus_a': {'rms_db': delta('rms_dbfs'), 'peak_db': delta('peak_dbfs'),
                                'spectral_centroid_hz': delta('spectral_centroid_hz')},
            'limitations': ['No automatic alignment, similarity score, source identification or quality judgment.',
                            'Equal decoded durations do not imply corresponding events. Compare equivalent recording conditions.',
                            'Null difference means at least one measurement is unavailable. Mono 16 kHz.']}


def png(rgb: np.ndarray) -> bytes:
    h, w, channels = rgb.shape
    if channels != 3:
        raise ValueError('Expected RGB image.')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    scan = b''.join(b'\0'+row.tobytes() for row in rgb)
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(scan)) + chunk(b'IEND', b''))


def spectrogram(p: Path, start: float, seconds: float, max_hz: int = 8000) -> bytes:
    if not 125 <= max_hz <= RATE//2:
        raise ValueError('max_hz must be 125–8000.')
    freq, amp = spectrum(load_audio(p, start, seconds))
    amp = amp[:, freq <= max_hz]
    # Preserve narrow peaks when compressing time to at most 900 columns.
    if len(amp) > 900:
        groups = np.array_split(amp, 900, axis=0)
        amp = np.stack([g.max(axis=0) for g in groups])
    level = np.clip(20*np.log10(np.maximum(amp, 1e-12)), -90, 0)
    value = (level+90)/90
    palette = np.array([[8,17,31],[25,63,103],[23,153,163],[114,227,208],[255,247,201]])
    rgb = np.stack([np.interp(value*4, np.arange(5), palette[:, i]) for i in range(3)], axis=-1)
    # Left to right time; bottom to top frequency. No interpolation of values.
    return png(np.ascontiguousarray(rgb.transpose(1,0,2)[::-1], dtype=np.uint8))
