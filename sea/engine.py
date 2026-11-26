"""Bounded, read-only media analysis. No remote inputs or model inference."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import numpy as np

MAX_FILE = 2 * 1024**3
RATE = 16000
# Maximum reported audio-duration shortfall for a measured video segment.
AUDIO_COVERAGE_TOLERANCE_S = .03
FPS = 4
WIDTH, HEIGHT = 160, 90
FORMATS = {'.wav':'wav', '.mp3':'mp3', '.flac':'flac', '.mp4':'mov', '.mov':'mov',
           '.m4a':'mov', '.mkv':'matroska', '.webm':'matroska', '.ogg':'ogg', '.opus':'ogg', '.avi':'avi'}


IMAGE_FORMATS = {'.png':'png_pipe', '.jpg':'jpeg_pipe', '.jpeg':'jpeg_pipe'}


def resolve_media(path: str, *, allow_image: bool = False, allow_csv: bool = False) -> Path:
    roots = [Path(p).expanduser().resolve(strict=True) for p in os.environ.get('SEA_MEDIA_ROOTS','').split(os.pathsep) if p.strip()]
    if not roots or any(not r.is_dir() for r in roots):
        raise ValueError('Set SEA_MEDIA_ROOTS to one or more existing media directories before using SEA.')
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raise ValueError('Supply an absolute local media path.')
    p = raw.resolve(strict=True)
    if not any(p.is_relative_to(r) for r in roots):
        raise ValueError('Media is outside the configured directories.')
    info = p.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE:
        raise ValueError('Expected a regular non-empty media file no larger than 2 GiB.')
    if p.suffix.lower() not in FORMATS and not (allow_image and p.suffix.lower() in IMAGE_FORMATS) and not (allow_csv and p.suffix.lower()=='.csv'):
        raise ValueError('Unsupported media extension.')
    return p


def run(binary: str, args: list[str], cap: int, timeout: int = 45) -> bytes:
    exe = shutil.which(binary)
    if not exe:
        raise RuntimeError(f'{binary} is required. Install FFmpeg and add it to PATH.')
    # Output goes to a temporary file, not to unbounded process-memory buffers.
    # The fixed decode duration/size caps normal media output. No shell invocation.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            result = subprocess.run([exe, *args], stdin=subprocess.DEVNULL, stdout=out,
                                    stderr=err, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f'{binary} timed out; try a shorter segment.') from None
        if result.returncode:
            raise RuntimeError(f'{binary} could not decode this media (exit {result.returncode}).')
        if out.tell() > cap:
            raise RuntimeError('Decoder output exceeded the analysis limit.')
        out.seek(0)
        return out.read(cap+1)


def input_args(p: Path) -> list[str]:
    # Whitelist demuxers; refuse playlists and network protocols.
    return ['-protocol_whitelist','file,pipe','-f',(FORMATS | IMAGE_FORMATS)[p.suffix.lower()], str(p)]


def probe(p: Path) -> dict:
    raw = run('ffprobe', ['-v','error','-max_alloc','134217728','-show_entries',
              'format=duration:stream=index,codec_type,codec_name,width,height,sample_rate,channels,duration',
              '-of','json',*input_args(p)], 256*1024)
    data = json.loads(raw)
    streams = data.get('streams', [])
    duration = data.get('format',{}).get('duration')
    try:
        duration = float(duration)
        if not math.isfinite(duration) or duration <= 0: duration = None
    except (TypeError,ValueError): duration = None
    return {'file':p.name,'duration_s':duration,'streams':streams,
            'audio':any(s.get('codec_type')=='audio' for s in streams),
            'video':any(s.get('codec_type')=='video' for s in streams)}


def window(start: float, seconds: float, max_seconds=60) -> tuple[float,float]:
    if not math.isfinite(start) or not math.isfinite(seconds) or not 0 <= start <= 86400 or not 0.25 <= seconds <= max_seconds:
        raise ValueError(f'Choose start 0–86400 s and duration 0.25–{max_seconds} s.')
    return start,seconds


def decode(p: Path, start: float, seconds: float, options: list[str], cap: int, *, autorotate: bool = True) -> bytes:
    return run('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-max_alloc','134217728',
               '-threads','2','-ss',str(start),*input_args(p)[:-1],*([] if autorotate else ['-noautorotate']),'-i',str(p),'-t',str(seconds),
               '-filter_threads','1','-threads','2',*options,'pipe:1'],cap)


def db(value: float) -> float | None:
    return round(20*math.log10(value),2) if value > 0 else None


def audio_features(p: Path, start: float, seconds: float) -> tuple[dict,list[dict]]:
    raw = decode(p,start,seconds,['-map','0:a:0','-vn','-ac','1','-ar',str(RATE),'-f','f32le'], int(seconds*RATE*4)+RATE*4)
    samples = np.frombuffer(raw,dtype='<f4')
    if not samples.size or not np.all(np.isfinite(samples)):
        raise ValueError('No finite audio samples in requested segment.')
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples.astype(np.float64)**2)))
    bins=[]
    for offset in range(0,len(samples),RATE//2):
        s = samples[offset:offset+RATE//2].astype(np.float64)
        level = float(np.sqrt(np.mean(s*s)))
        freq = None
        if len(s)>=RATE//4 and level>=0.01:
            spec = np.abs(np.fft.rfft((s-np.mean(s))*np.hanning(len(s))))
            spec[0]=0
            k=int(np.argmax(spec))
            if spec[k]>0: freq=round(k*RATE/len(s),1)
        bins.append({'start_s':round(start+offset/RATE,3), 'end_s':round(start+(offset+len(s))/RATE,3),
                     'rms_dbfs':db(level),'peak_dbfs':db(float(np.max(np.abs(s)))),
                     'dominant_frequency_hz':freq,'low_level':level<0.01})
    return {'sample_rate_hz':RATE,'channels':'mono mix','analyzed_s':round(len(samples)/RATE,3),
            'rms_dbfs':db(rms),'peak_dbfs':db(peak),'near_full_scale_fraction':round(float(np.mean(np.abs(samples)>=.999)),6),
            'note':'Digital sample levels, not calibrated loudness or proof of clipping. Null dBFS means zero amplitude.'}, bins


def video_features(p: Path, start: float, seconds: float) -> tuple[dict,list[dict]]:
    size=WIDTH*HEIGHT
    raw = decode(p,start,seconds,['-map','0:v:0','-an','-vf',f'fps={FPS},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray',
                                '-pix_fmt','gray','-f','rawvideo'],(math.ceil(seconds*FPS)+4)*size)
    frames = np.frombuffer(raw,dtype=np.uint8).reshape(-1,HEIGHT,WIDTH).astype(np.float32)
    if len(frames)==0:
        raise ValueError('No sampled video frames in requested segment.')
    rows=[]
    for i,frame in enumerate(frames):
        change = float(np.mean(np.abs(frame-frames[i-1]))/255) if i else None
        rows.append({'time_s':round(start+i/FPS,3),'mean_luma':round(float(frame.mean())/255,4),
                     'frame_change':round(change,4) if change is not None else None})
    return {'sample_rate_fps':FPS,'frames':len(frames),'sample_size':[WIDTH,HEIGHT],
            'note':'Frame change measures pixel differences, not object motion; cuts, exposure and camera motion can look similar.'},rows


def analyze(p: Path, start: float=0, seconds: float=15) -> dict:
    start,seconds=window(start,seconds)
    before=p.stat()
    meta=probe(p)
    if meta['duration_s'] is not None and start>=meta['duration_s']:
        raise ValueError('Start is outside the media duration.')
    if not meta['audio'] and not meta['video']:
        raise ValueError('No audio or video streams.')
    audio,abins=audio_features(p,start,seconds) if meta['audio'] else (None,[])
    video,vbins=video_features(p,start,seconds) if meta['video'] else (None,[])
    # Shared half-second timeline: temporal co-occurrence, never causal inference.
    timeline=[]
    for i in range(math.ceil(seconds*2)):
        t=start+i/2
        a=abins[i] if i<len(abins) else None
        v=[r for r in vbins if t-.0001<=r['time_s']<t+.4999]
        if not a and not v: continue
        changes=[r['frame_change'] for r in v if r['frame_change'] is not None]
        change=max(changes,default=None)
        timeline.append({'start_s':round(t,3),'end_s':round(min(t+.5,start+seconds),3),
                         'audio_rms_dbfs':a['rms_dbfs'] if a else None,'audio_observed':a is not None,
                         'dominant_frequency_hz':a['dominant_frequency_hz'] if a else None,
                         'low_level':a['low_level'] if a else None,'max_frame_change':change,
                         'video_frames':len(v),'visual_change_flag':change>=.12 if change is not None else None})
    after=p.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise RuntimeError('Media changed during analysis; retry on a stable copy.')
    return {'media':meta,'requested_window_s':[start,start+seconds],'audio':audio,'video':video,
            'timeline':timeline,'observations':{'low_level_bins':sum(r['low_level'] is True for r in timeline),
            'visual_change_bins':sum(r['visual_change_flag'] is True for r in timeline)},
            'limitations':['First audio/video stream only; audio downmixed to mono.','Approximate timestamps from sampled decoded streams; not exact A/V sync or source PTS.','Sub-frame events may be missed; pixel change does not establish motion or causation.','No speech transcription, source identification, music understanding or diagnosis.']}


def frame(p: Path, time_s: float) -> bytes:
    window(time_s,0.25)
    return decode(p,time_s,1,['-map','0:v:0','-an','-frames:v','1','-vf','scale=960:540:force_original_aspect_ratio=decrease','-c:v','png','-f','image2pipe'],4*1024*1024)
