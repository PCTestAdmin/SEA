"""Opt-in, content-addressed measurement reports from trusted SEA analyzers."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from . import __version__
from .engine import resolve_media, analyze
from .acoustics import analyze_audio
from .vision import analyze_video, investigate, fingerprint
from .spatial import sense_spatial

APP_ID=0x53454145
MAX_RECORDS=100
MAX_REPORT=512*1024
MAX_SOURCE=128*1024**2


def canonical(obj):
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def source_hash(p):
    before=fingerprint(p)
    if before[0]>MAX_SOURCE:
        raise ValueError('Evidence source exceeds 128 MiB.')
    h=hashlib.sha256()
    total=0
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            total+=len(block)
            if total>MAX_SOURCE:
                raise ValueError('Evidence source exceeds 128 MiB.')
            h.update(block)
    if total!=before[0] or before!=fingerprint(p):
        raise RuntimeError('Source changed while hashing.')
    return {'sha256':h.hexdigest(),'bytes':total}


def db_path():
    raw=Path(os.environ.get('SEA_EVIDENCE_DIR','')).expanduser()
    if not raw.is_absolute():
        raise ValueError('Evidence disabled: set SEA_EVIDENCE_DIR to an absolute private directory.')
    root=raw.resolve(strict=True)
    if not root.is_dir() or root==Path.home().resolve() or root==Path(root.anchor):
        raise ValueError('Choose a dedicated existing private evidence directory.')
    p=root/'sea-evidence.sqlite3'
    if p.is_symlink() or (p.exists() and not stat.S_ISREG(p.stat().st_mode)):
        raise ValueError('Expected a regular evidence database.')
    return p


@contextmanager
def database(write=False,create=False):
    p=db_path()
    if not p.exists():
        if not create:
            yield None
            return
        try:
            fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.close(fd)
        except FileExistsError:
            pass
    conn=sqlite3.connect(str(p),timeout=5)
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            app=conn.execute('PRAGMA application_id').fetchone()[0]
            version=conn.execute('PRAGMA user_version').fetchone()[0]
            if app==0 and version==0 and create:
                if conn.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone()[0]:
                    raise ValueError('Refusing to initialize unrelated database.')
                conn.execute(f'PRAGMA application_id={APP_ID}')
                conn.execute('PRAGMA user_version=1')
                conn.execute('CREATE TABLE evidence (id TEXT PRIMARY KEY, created TEXT, tool TEXT, payload BLOB NOT NULL)')
            elif app!=APP_ID or version!=1:
                raise ValueError('Unsupported evidence database.')
            yield conn
    finally:
        conn.close()


def capture(path,tool,start=0,duration=10,confirm=False):
    if not confirm:
        raise ValueError('Saving evidence requires explicit user approval and confirm=true.')
    db_path()
    runners={'sense_media':analyze,'sense_audio':analyze_audio,'sense_video':analyze_video,
             'investigate_media':investigate}
    if tool not in runners and tool!='inspect_spatial':
        raise ValueError('Unsupported evidence analyzer; choose a documented tool.')
    p=resolve_media(path,allow_image=tool=='inspect_spatial')
    before=fingerprint(p)
    source=source_hash(p)
    if tool=='inspect_spatial':
        report=sense_spatial(p,start,3)
        params={'time_s':start,'grid_size':3}
    else:
        report=runners[tool](p,start,duration)
        params={'start_s':start,'duration_s':duration}
    if before!=fingerprint(p) or source!=source_hash(p):
        raise RuntimeError('Source changed during evidence capture.')
    # Existing analyzers may return a source basename. Drop it at the top and nested media metadata.
    report=dict(report)
    report.pop('file',None)
    if isinstance(report.get('media'),dict):
        report['media']=dict(report['media'])
        report['media'].pop('file',None)
    envelope={'schema_version':1,'engine_version':__version__,
              'created_utc':datetime.now(timezone.utc).isoformat(),'tool':tool,
              'parameters':params,'source':source,'report':report}
    payload=canonical(envelope)
    if len(payload)>MAX_REPORT:
        raise ValueError('Evidence report exceeds 512 KiB.')
    key=hashlib.sha256(payload).hexdigest()
    with database(write=True,create=True) as db:
        if db.execute('SELECT count(*) FROM evidence').fetchone()[0]>=MAX_RECORDS:
            raise ValueError('Evidence store full; explicitly delete an old report.')
        db.execute('INSERT INTO evidence VALUES (?,?,?,?)',(key,envelope['created_utc'],tool,payload))
    return {'id':key,'envelope':envelope}


def validate_id(key):
    if not re.fullmatch('[0-9a-f]{64}',key):
        raise ValueError('Expected a SHA-256 evidence ID.')


def recall(key):
    validate_id(key)
    with database() as db:
        row=db.execute('SELECT payload FROM evidence WHERE id=?',(key,)).fetchone() if db else None
    if row is None:
        raise ValueError('Evidence record not found.')
    payload=row[0]
    if not isinstance(payload,bytes) or len(payload)>MAX_REPORT or hashlib.sha256(payload).hexdigest()!=key:
        raise ValueError('Stored evidence digest mismatch.')
    return {'id':key,'envelope':json.loads(payload)}


def list_records(limit=20):
    if not 1<=limit<=100:
        raise ValueError('Limit must be 1–100.')
    with database() as db:
        if db is None:
            return {'total':0,'records':[]}
        total=db.execute('SELECT count(*) FROM evidence').fetchone()[0]
        rows=db.execute('SELECT id,created,tool FROM evidence ORDER BY created DESC,id DESC LIMIT ?',(limit,)).fetchall()
        return {'total':total,'records':[dict(zip(('id','created_utc','tool'),r)) for r in rows]}


def verify(key,path):
    stored=recall(key)
    p=resolve_media(path,allow_image=True)
    actual=source_hash(p)
    return {'id':key,'report_digest_matches':True,
            'source_matches':actual==stored['envelope']['source'],
            'actual_source':actual,
            'limitations':['Hashes establish byte equality, not authenticity or measurement correctness.',
                           'Verification does not rerun the analyzer or authenticate the creator.']}


def delete(key,confirm=False):
    validate_id(key)
    if not confirm:
        raise ValueError('Deletion requires explicit approval and confirm=true.')
    with database(write=True) as db:
        if db is None or db.execute('DELETE FROM evidence WHERE id=?',(key,)).rowcount!=1:
            raise ValueError('Evidence record not found.')
    return {'id':key,'status':'deleted','note':'Logical deletion only; backups or disk remnants may remain.'}
