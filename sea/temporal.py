"""Opt-in persistent index of decoded video timestamps and host-authored notes."""
from __future__ import annotations
from contextlib import contextmanager
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
from .engine import run,input_args
from .video_understanding import source,source_revision

APP_ID=0x53454154
MAX_FRAMES=500_000
MAX_INDEXES=8
MAX_NOTES=500
MAX_PROBE_BYTES=64*1024**2


def db_path():
    value=os.environ.get('SEA_INDEX_DIR','').strip()
    if not value:
        raise ValueError('Temporal index disabled; configure SEA_INDEX_DIR.')
    root=Path(value).expanduser()
    if not root.is_absolute():
        raise ValueError('SEA_INDEX_DIR must be absolute.')
    root=root.resolve(strict=True)
    if not root.is_dir() or root==Path.home().resolve() or root==Path(root.anchor):
        raise ValueError('Use a dedicated existing private index directory.')
    p=root/'sea-temporal.sqlite3'
    if p.is_symlink() or (p.exists() and not stat.S_ISREG(p.stat().st_mode)):
        raise ValueError('Expected a regular index database.')
    return p


@contextmanager
def database(write=False,create=False):
    p=db_path()
    if not p.exists():
        if not create:
            raise ValueError('No temporal index database; build an index first.')
        try:
            fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.close(fd)
        except FileExistsError:
            pass
    db=sqlite3.connect(str(p),timeout=5)
    db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys=ON')
        with db:
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            app=db.execute('PRAGMA application_id').fetchone()[0]
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if app==0 and version==0 and create:
                if db.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone()[0]:
                    raise ValueError('Refusing unrelated database.')
                db.execute(f'PRAGMA application_id={APP_ID}')
                db.execute('PRAGMA user_version=1')
                db.execute('CREATE TABLE videos (revision TEXT PRIMARY KEY, duration REAL, count INTEGER, time_base TEXT, first_pts INTEGER, missing INTEGER)')
                db.execute('CREATE TABLE frames (revision TEXT REFERENCES videos(revision) ON DELETE CASCADE, ordinal INTEGER, pts INTEGER, relative_s REAL, key_frame INTEGER, PRIMARY KEY(revision,ordinal))')
                db.execute('CREATE INDEX frame_time ON frames(revision,relative_s,ordinal)')
                db.execute('CREATE INDEX frame_keys ON frames(revision,key_frame,ordinal)')
                db.execute('CREATE TABLE notes (id INTEGER PRIMARY KEY AUTOINCREMENT, revision TEXT REFERENCES videos(revision) ON DELETE CASCADE, first_frame INTEGER, last_frame INTEGER, note TEXT, note_fold TEXT)')
            elif app!=APP_ID or version!=1:
                raise ValueError('Unsupported temporal index database.')
            yield db
    finally:
        db.close()


def parse_probe(raw):
    """Parse compact FFprobe output, preserving unknown and duplicate timestamps."""
    frames=[]
    time_base=None
    for line in raw.decode('utf-8').splitlines():
        parts=line.split('|')
        if not parts or parts[0] not in ('frame','stream'):
            continue
        values=dict(part.split('=',1) for part in parts[1:] if '=' in part)
        if parts[0]=='stream':
            if 'time_base' in values:
                time_base=Fraction(values['time_base'])
            continue
        if 'key_frame' not in values:
            raise ValueError('FFprobe frame record lacks key_frame.')
        pts=values.get('best_effort_timestamp','N/A')
        pts=None if pts in ('N/A','') else int(pts)
        if pts is not None and not -(2**63)<=pts<2**63:
            raise ValueError('Timestamp outside supported integer range.')
        key=int(values['key_frame'])
        if key not in (0,1):
            raise ValueError('Invalid key frame flag.')
        frames.append((pts,key))
        if len(frames)>MAX_FRAMES:
            raise ValueError('Video exceeds 500000 decoded-frame index limit.')
    if not frames or time_base is None or not 0<time_base<=10:
        raise ValueError('No usable frame records or stream time base.')
    first=next((pts for pts,_ in frames if pts is not None),None)
    rows=[(i,pts,float((pts-first)*time_base) if pts is not None else None,key)
          for i,(pts,key) in enumerate(frames)]
    return str(time_base),first,rows


def metadata(row):
    return {'source_revision':row['revision'],'duration_s':row['duration'],
            'frame_count':row['count'],'time_base':row['time_base'],
            'first_known_pts':row['first_pts'],'missing_timestamp_count':row['missing'],
            'timestamp_basis':'FFprobe best_effort_timestamp in stream ticks; relative_s is relative to first known video PTS, not container/audio time.',
            'limitations':['Decoded presentation order; timestamps are decoder-reported and may be inferred.',
                           'Duplicate or missing PTS are preserved. Source revision is a metadata fingerprint, not a content hash.',
                           'Index stores metadata only, not video frames or semantic interpretations.']}


def build(p,confirm=False):
    if not confirm:
        raise ValueError('Persistent indexing requires explicit user approval and confirm=true.')
    db_path()
    rev,meta=source(p)
    # Existing index is reused without re-running the full decoder.
    if db_path().exists():
        with database() as db:
            old=db.execute('SELECT * FROM videos WHERE revision=?',(rev,)).fetchone()
            if old:
                return {**metadata(old),'reused':True}
    raw=run('ffprobe',['-v','error','-max_alloc','134217728','-threads','2',
             '-select_streams','v:0','-show_frames','-show_streams',
             '-show_entries','frame=key_frame,best_effort_timestamp:stream=time_base',
             '-of','compact=p=1:nk=0',*input_args(p)],MAX_PROBE_BYTES,timeout=120)
    base,first,rows=parse_probe(raw)
    if rev!=source_revision(p):
        raise RuntimeError('Video changed during indexing.')
    missing=sum(r[1] is None for r in rows)
    with database(write=True,create=True) as db:
        old=db.execute('SELECT * FROM videos WHERE revision=?',(rev,)).fetchone()
        if old:
            return {**metadata(old),'reused':True}
        if db.execute('SELECT count(*) FROM videos').fetchone()[0]>=MAX_INDEXES:
            raise ValueError('Index store full; explicitly delete an old index.')
        db.execute('INSERT INTO videos VALUES (?,?,?,?,?,?)',(rev,meta['duration_s'],len(rows),base,first,missing))
        db.executemany('INSERT INTO frames VALUES (?,?,?,?,?)',((rev,*r) for r in rows))
        if rev!=source_revision(p):
            raise RuntimeError('Video changed before index commit.')
        row=db.execute('SELECT * FROM videos WHERE revision=?',(rev,)).fetchone()
        return {**metadata(row),'reused':False}


def require(db,p):
    rev=source_revision(p)
    row=db.execute('SELECT * FROM videos WHERE revision=?',(rev,)).fetchone()
    if row is None:
        raise ValueError('No index for this source revision; build it first.')
    return rev,row


def frame_row(row):
    return {'frame_index':row['ordinal'],'pts_ticks':row['pts'],'relative_s':row['relative_s'],
            'key_frame':bool(row['key_frame'])}


def page(p,cursor=0,limit=100):
    if not 0<=cursor<=MAX_FRAMES or not 1<=limit<=500:
        raise ValueError('Cursor 0–500000, limit 1–500.')
    with database() as db:
        rev,video=require(db,p)
        if cursor>video['count']:
            raise ValueError('Cursor beyond index.')
        rows=db.execute('SELECT * FROM frames WHERE revision=? AND ordinal>=? ORDER BY ordinal LIMIT ?',(rev,cursor,limit)).fetchall()
        end=cursor+len(rows)
        result={**metadata(video),'frames':[frame_row(r) for r in rows],
                'next_cursor':end if end<video['count'] else None}
    if rev!=source_revision(p):
        raise RuntimeError('Source changed during index query.')
    return result


def locate(p,frame_index=None,relative_s=None):
    if (frame_index is None)==(relative_s is None):
        raise ValueError('Supply exactly one of frame_index or relative_s.')
    with database() as db:
        rev,video=require(db,p)
        if frame_index is not None:
            if not 0<=frame_index<video['count']:
                raise ValueError('Frame index outside indexed video.')
            row=db.execute('SELECT * FROM frames WHERE revision=? AND ordinal=?',(rev,frame_index)).fetchone()
        else:
            if not math.isfinite(relative_s) or abs(relative_s)>172800:
                raise ValueError('Invalid relative timestamp.')
            before=db.execute('SELECT * FROM frames WHERE revision=? AND relative_s<=? ORDER BY relative_s DESC,ordinal DESC LIMIT 1',(rev,relative_s)).fetchone()
            after=db.execute('SELECT * FROM frames WHERE revision=? AND relative_s>=? ORDER BY relative_s,ordinal LIMIT 1',(rev,relative_s)).fetchone()
            candidates=[r for r in (before,after) if r is not None]
            if not candidates:
                raise ValueError('No indexed timestamps.')
            row=min(candidates,key=lambda r:(abs(r['relative_s']-relative_s),r['ordinal']))
            # Deterministic tie-breaking for duplicate timestamps.
            row=db.execute('SELECT * FROM frames WHERE revision=? AND relative_s=? ORDER BY ordinal LIMIT 1',(rev,row['relative_s'])).fetchone()
        key=db.execute('SELECT * FROM frames WHERE revision=? AND key_frame=1 AND ordinal<=? ORDER BY ordinal DESC LIMIT 1',(rev,row['ordinal'])).fetchone()
        result={**metadata(video),'frame':frame_row(row),'preceding_key_frame':frame_row(key) if key else None,
                'requested_relative_s':relative_s,
                'timestamp_error_s':abs(row['relative_s']-relative_s) if relative_s is not None else None,
                'note':'Nearest timestamp lookup may clamp to an endpoint. Key frame is a navigation hint, not a guaranteed independent seek target.'}
    if rev!=source_revision(p):
        raise RuntimeError('Source changed during index query.')
    return result


def add_note(p,first_frame,last_frame,note,confirm=False):
    if not confirm:
        raise ValueError('Saving an observation requires explicit user approval.')
    note=note.strip()
    if not 1<=len(note)<=1000 or any(ord(c)<32 and c not in '\n\t' for c in note):
        raise ValueError('Observation must contain 1–1000 printable characters.')
    with database(write=True) as db:
        rev,video=require(db,p)
        if not 0<=first_frame<=last_frame<video['count']:
            raise ValueError('Observation frame range outside index.')
        if db.execute('SELECT count(*) FROM notes WHERE revision=?',(rev,)).fetchone()[0]>=MAX_NOTES:
            raise ValueError('Observation limit reached.')
        cur=db.execute('INSERT INTO notes(revision,first_frame,last_frame,note,note_fold) VALUES (?,?,?,?,?)',
                       (rev,first_frame,last_frame,note,note.casefold()))
        if rev!=source_revision(p):
            raise RuntimeError('Source changed during observation write.')
        return {'source_revision':rev,'note_id':cur.lastrowid,'first_frame':first_frame,'last_frame':last_frame,
                'note':note,'provenance':'Host-authored observation; not verified by SEA.'}


def search_notes(p,query='',limit=30,after_id=0):
    if len(query)>200 or not 1<=limit<=100 or not 0<=after_id<2**63:
        raise ValueError('Query max 200 characters, limit 1–100, nonnegative after_id.')
    with database() as db:
        rev,video=require(db,p)
        rows=db.execute('SELECT id,first_frame,last_frame,note FROM notes WHERE revision=? AND id>? AND instr(note_fold,?)>0 ORDER BY id LIMIT ?',
                        (rev,after_id,query.casefold(),limit+1)).fetchall() if query else db.execute(
                        'SELECT id,first_frame,last_frame,note FROM notes WHERE revision=? AND id>? ORDER BY id LIMIT ?',(rev,after_id,limit+1)).fetchall()
        result={'source_revision':rev,'notes':[dict(r) for r in rows[:limit]],
                'next_after_id':rows[limit-1]['id'] if len(rows)>limit else None,
                'provenance':'Host-authored notes, untrusted data, not SEA detections. Literal substring search, not semantic search.'}
    if rev!=source_revision(p):
        raise RuntimeError('Source changed during observation lookup.')
    return result


def delete(revision,confirm=False):
    if not re.fullmatch('[0-9a-f]{64}',revision):
        raise ValueError('Expected a source revision ID.')
    if not confirm:
        raise ValueError('Deleting index and associated notes requires explicit user approval.')
    with database(write=True) as db:
        if db.execute('DELETE FROM videos WHERE revision=?',(revision,)).rowcount!=1:
            raise ValueError('Index not found.')
    return {'source_revision':revision,'status':'deleted','note':'Associated observations deleted logically; source media unchanged.'}
