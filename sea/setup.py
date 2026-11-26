"""Explicit, preview-first MCP registration for persistent SEA installations."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from . import __version__


def config_path(client: str) -> Path:
    if client == 'cursor':
        return Path.home() / '.cursor' / 'mcp.json'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Claude' / 'claude_desktop_config.json'
    if sys.platform == 'win32' and os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'Claude' / 'claude_desktop_config.json'
    raise ValueError('No default Claude Desktop config on this platform. Supply --config explicitly.')


def media_root(value: str) -> Path:
    p = Path(value).expanduser().resolve(strict=True)
    if not p.is_dir() or p == Path.home().resolve() or p == Path(p.anchor) or os.pathsep in str(p):
        raise ValueError('Choose a dedicated existing media directory, not a home or drive root.')
    return p


def entry(root: Path) -> dict:
    # Keep the virtual-environment executable path; resolving symlinks can escape a venv.
    return {'command': os.path.abspath(sys.executable), 'args': ['-m', 'sea.server'],
            'env': {'SEA_MEDIA_ROOTS': str(root)}}


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON keys; repair the config manually first.')
        obj[key] = value
    return obj


def read_config(path: Path):
    if path.is_symlink():
        raise ValueError('Refusing to edit a symbolic-link config.')
    if not path.exists():
        return None, {}, 0o600
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 2 * 1024 * 1024:
        raise ValueError('Expected a regular JSON config no larger than 2 MiB.')
    raw = path.read_bytes()
    data = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object)
    if not isinstance(data, dict) or not isinstance(data.get('mcpServers', {}), dict):
        raise ValueError('Expected a JSON object with an optional mcpServers object.')
    return raw, data, stat.S_IMODE(info.st_mode)


def register(path: Path, root: Path, *, apply=False, replace=False) -> dict:
    path = Path(os.path.abspath(path.expanduser()))
    raw, data, mode = read_config(path)
    servers = data.setdefault('mcpServers', {})
    new = entry(root)
    if servers.get('sea') == new:
        return {'status': 'unchanged', 'config': str(path), 'entry': new}
    if 'sea' in servers and not replace:
        raise ValueError('A different SEA entry exists. Review it; use --replace to authorize replacing only that entry.')
    servers['sea'] = new
    plan = {'status': 'preview', 'config': str(path), 'entry': new, 'backup': None}
    if not apply:
        return plan
    encoded = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive temporary backup containing the exact original bytes. Never print secrets.
    if raw is not None:
        with tempfile.NamedTemporaryFile(mode='wb', prefix=path.name + '.', suffix='.bak', dir=path.parent, delete=False) as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
            plan['backup'] = f.name
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.sea-', dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        if read_config(path)[0] != raw:
            raise ValueError('Configuration changed during setup; retry after closing the client.')
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
    plan['status'] = 'configured'
    return plan


def doctor(root: Path | None = None) -> dict:
    checks = {name: shutil.which(name) is not None for name in ('ffmpeg', 'ffprobe')}
    checks.update({name: importlib.util.find_spec(name) is not None for name in ('mcp', 'numpy', 'PIL')})
    if root is not None:
        checks['media_root'] = root.is_dir()
    return {'version': __version__, 'python': sys.executable, 'checks': checks,
            'ready_for_setup': all(checks.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='sea', description='Sensory Extension for Agents')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='action', required=True)
    setup = sub.add_parser('setup', help='Preview or apply local MCP registration')
    setup.add_argument('--client', choices=['claude-desktop', 'cursor'], default='claude-desktop')
    setup.add_argument('--config', type=Path, help='Explicit JSON config path for compatible clients')
    setup.add_argument('--media-root', required=True, help='Existing dedicated media folder')
    setup.add_argument('--apply', action='store_true', help='Authorize writing the previewed config')
    setup.add_argument('--replace', action='store_true', help='Authorize replacing a different SEA entry')
    check = sub.add_parser('doctor', help='Check local prerequisites without modifying anything')
    check.add_argument('--media-root')
    analyze = sub.add_parser('analyze', help='Analyze an authorized target; portable JSON evidence')
    analyze.add_argument('path')
    analyze.add_argument('--cursor',type=int,default=0)
    analyze.add_argument('--segment-seconds',type=int,default=8)
    analyze.add_argument('--page-size',type=int,default=2)
    analyze.add_argument('--sample-fps',type=int,default=4)
    analyze.add_argument('--start',type=float,default=0)
    analyze.add_argument('--duration',type=float,default=10)
    analyze.add_argument('--time-column')
    analyze.add_argument('--channels',nargs='+')
    analyze.add_argument('--expected-revision')
    analyze.add_argument('--json',action='store_true',help='JSON output (also the default)')
    views = sub.add_parser('inspect-evidence',help='Project a saved analyze_target JSON report')
    views.add_argument('path',type=Path)
    views.add_argument('--view',choices=['summary','page'],default='summary')
    views.add_argument('--offset',type=int,default=0)
    views.add_argument('--limit',type=int,default=20)
    audit = sub.add_parser('audit-video-coverage',help='Check coverage of 1–16 saved video evidence pages')
    audit.add_argument('paths',type=Path,nargs='+')
    relations = sub.add_parser('relate-video-events',help='Relate measured events from 1–16 saved video evidence pages')
    relations.add_argument('paths',type=Path,nargs='+')
    relations.add_argument('--offset',type=int,default=0)
    relations.add_argument('--limit',type=int,default=50)
    guides = sub.add_parser('guided-workflows',help='List workflows or render agent guidance')
    guides.add_argument('workflow',nargs='?',default='')
    args = parser.parse_args(argv)
    try:
        if args.action == 'analyze':
            from .analysis import analyze_target
            result=analyze_target(args.path,args.cursor,args.segment_seconds,args.page_size,args.sample_fps,
                                  args.start,args.duration,args.time_column,args.channels,args.expected_revision)
            print(json.dumps(result,indent=2,allow_nan=False))
            return 0
        if args.action == 'inspect-evidence':
            from .analysis import inspect_view,MAX_EVIDENCE
            with args.path.open('rb') as f:
                raw=f.read(4*MAX_EVIDENCE+1)
            if len(raw)>4*MAX_EVIDENCE:
                raise ValueError('Report file exceeds CLI input limit.')
            result=inspect_view(json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_object),args.view,args.offset,args.limit)
            print(json.dumps(result,indent=2,allow_nan=False))
            return 0
        if args.action in ('audit-video-coverage','relate-video-events'):
            from .analysis import audit_video_coverage,MAX_EVIDENCE
            if not 1<=len(args.paths)<=16:
                raise ValueError('Supply 1–16 complete video evidence envelopes.')
            pages=[]
            for path in args.paths:
                with path.open('rb') as f:
                    raw=f.read(4*MAX_EVIDENCE+1)
                if len(raw)>4*MAX_EVIDENCE:
                    raise ValueError('Report file exceeds CLI input limit.')
                pages.append(json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_object))
            if args.action=='relate-video-events':
                from .event_relations import relate
                report=relate(pages,args.offset,args.limit)
            else:
                report=audit_video_coverage(pages)
            print(json.dumps(report,indent=2,allow_nan=False))
            return 0
        if args.action == 'guided-workflows':
            from .workflows import guidance
            print(json.dumps(guidance(args.workflow),indent=2))
            return 0
        root = media_root(args.media_root) if args.media_root else None
        if args.action == 'doctor':
            result = doctor(root)
        else:
            result = register(args.config or config_path(args.client), root, apply=args.apply, replace=args.replace)
        print(json.dumps(result, indent=2))
        if result.get('status') == 'preview':
            print('No files changed. Repeat with --apply to register SEA.', file=sys.stderr)
        if result.get('status') == 'configured':
            print('Restart your MCP client. Run sea doctor if tools do not appear.', file=sys.stderr)
        return 0 if result.get('ready_for_setup', True) else 1
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f'SEA: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
