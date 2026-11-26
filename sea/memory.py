"""Explicit opt-in, bounded, local measurement history. No raw media storage."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid
from . import __version__
from .acoustics import analyze_audio
from .signals import analyze_signals

MAX_RECORDS = 100
MAX_PAYLOAD = 128 * 1024
APP_ID = 0x53454138


def database_path() -> Path:
    value = os.environ.get('SEA_MEMORY_DIR','')
    if not value.strip():
        raise ValueError('Perception memory is disabled. Configure SEA_MEMORY_DIR explicitly.')
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raise ValueError('SEA_MEMORY_DIR must be absolute.')
    root = raw.resolve(strict=True)
    if not root.is_dir() or root == Path.home().resolve() or root == Path(root.anchor):
        raise ValueError('Choose a dedicated existing private memory directory.')
    p = root / 'sea-memory.sqlite3'
    if p.is_symlink() or (p.exists() and not stat.S_ISREG(p.stat().st_mode)):
        raise ValueError('Memory database must be a regular file.')
    return p


@contextmanager
def database(*, create=False):
    p = database_path()
    if not p.exists() and not create:
        yield None
        return
    if not p.exists():
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
    conn = sqlite3.connect(str(p),timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE' if create else 'BEGIN')
            app_id = conn.execute('PRAGMA application_id').fetchone()[0]
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            if app_id == 0 and version == 0 and create:
                if conn.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone()[0]:
                    raise ValueError('Refusing to initialize a non-SEA database.')
                conn.execute(f'PRAGMA application_id={APP_ID}')
                conn.execute('PRAGMA user_version=1')
                conn.execute('CREATE TABLE measurements (id TEXT PRIMARY KEY, created_utc TEXT NOT NULL, label TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)')
            elif app_id != APP_ID or version != 1:
                raise ValueError('Unsupported or uninitialized SEA memory database.')
            yield conn
    finally:
        conn.close()


def validate_label(label: str) -> str:
    label=label.strip()
    if not 1<=len(label)<=100 or any(ord(c)<32 or ord(c)==127 for c in label):
        raise ValueError('Label must contain 1–100 printable characters.')
    return label


def valid_id(value: str) -> str:
    if not re.fullmatch('[0-9a-f]{32}',value):
        raise ValueError('Invalid memory ID.')
    return value


def save(label: str, kind: str, measurements: dict) -> dict:
    label=validate_label(label)
    payload=json.dumps({'engine_version':__version__,'measurements':measurements},ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if len(payload.encode('utf-8'))>MAX_PAYLOAD:
        raise ValueError('Measurement summary exceeds memory limit.')
    record={'id':uuid.uuid4().hex,'created_utc':datetime.now(timezone.utc).isoformat(),
            'label':label,'kind':kind}
    with database(create=True) as db:
        if db.execute('SELECT count(*) FROM measurements').fetchone()[0]>=MAX_RECORDS:
            raise ValueError('Memory is full (100 records). Delete an old record explicitly.')
        db.execute('INSERT INTO measurements VALUES (?,?,?,?,?)',
                   (record['id'],record['created_utc'],label,kind,payload))
    return record


def remember_audio(p: Path,label: str,start: float=0,seconds: float=15) -> dict:
    database_path()
    validate_label(label)
    a=analyze_audio(p,start,seconds)
    keys=('analyzed_s','sample_rate_hz','rms_dbfs','peak_dbfs','spectral_centroid_hz',
          'frequency_peaks','band_power_fractions')
    return save(label,'audio',{k:a[k] for k in keys})


def remember_signals(p: Path,label: str,time_column: str,channels: list[str]) -> dict:
    database_path()
    validate_label(label)
    a=analyze_signals(p,time_column,channels)
    keys=('channel','min','max','mean','median','std_population','net_change')
    return save(label,'signals',{'rows':a['rows'],'time_range_s':a['time_range_s'],
                'channels':[{k:r[k] for k in keys} for r in a['channels']]})


def list_memory(limit: int=20) -> dict:
    if not 1<=limit<=100:
        raise ValueError('Limit must be 1–100.')
    with database() as db:
        if db is None:
            return {'total':0,'records':[]}
        total=db.execute('SELECT count(*) FROM measurements').fetchone()[0]
        rows=db.execute('SELECT id,created_utc,label,kind FROM measurements ORDER BY created_utc DESC,id DESC LIMIT ?', (limit,)).fetchall()
        return {'total':total,'records':[dict(r) for r in rows]}


def get_record(db,record_id: str) -> dict:
    valid_id(record_id)
    row=db.execute('SELECT * FROM measurements WHERE id=?',(record_id,)).fetchone() if db is not None else None
    if row is None:
        raise ValueError('Memory record not found.')
    result=dict(row)
    payload=result.pop('payload')
    return {**result,**json.loads(payload)}


def recall(record_id: str) -> dict:
    with database() as db:
        return get_record(db,record_id)


def compare_memory(id_a: str,id_b: str) -> dict:
    with database() as db:
        a,b=get_record(db,id_a),get_record(db,id_b)
    if a['kind']!=b['kind']:
        raise ValueError('Compare records of the same measurement kind.')
    if a['engine_version']!=b['engine_version']:
        raise ValueError('Records use different engine versions; create matching snapshots.')
    x,y=a['measurements'],b['measurements']
    def diff(k,u,v):
        return round(v[k]-u[k],6) if u[k] is not None and v[k] is not None else None
    if a['kind']=='audio':
        if x['sample_rate_hz']!=y['sample_rate_hz'] or abs(x['analyzed_s']-y['analyzed_s'])>1/x['sample_rate_hz']:
            raise ValueError('Audio snapshots must have matching sample rates and decoded durations.')
        delta={k:diff(k,x,y) for k in ('rms_dbfs','peak_dbfs','spectral_centroid_hz')}
    else:
        u={r['channel']:r for r in x['channels']}
        v={r['channel']:r for r in y['channels']}
        if u.keys()!=v.keys():
            raise ValueError('Signal snapshots must contain the same channel names.')
        delta=[{'channel':k,**{m:diff(m,u[k],v[k]) for m in ('min','max','mean','median','std_population','net_change')}} for k in u]
    return {'a':a,'b':b,'delta_b_minus_a':delta,
            'limitations':['Compare equivalent recording conditions and sensor units.',
                           'No automatic temporal alignment, calibration, anomaly probability or cause inference.',
                           'Historical records are snapshots, not verification of the current source file.']}


def forget(record_id: str,confirm: bool=False) -> dict:
    valid_id(record_id)
    if not confirm:
        raise ValueError('Deletion requires explicit user approval and confirm=true.')
    # Do not initialize a database just to delete a nonexistent record.
    if not database_path().exists():
        raise ValueError('Memory record not found.')
    with database(create=True) as db:
        if db.execute('DELETE FROM measurements WHERE id=?',(record_id,)).rowcount!=1:
            raise ValueError('Memory record not found.')
    return {'id':record_id,'status':'deleted','note':'Logical deletion only; backups or disk remnants may remain.'}
