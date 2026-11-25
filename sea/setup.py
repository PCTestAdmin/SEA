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
    checks.update({name: importlib.util.find_spec(name) is not None for name in ('mcp', 'numpy')})
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
    args = parser.parse_args(argv)
    try:
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
    except (OSError, ValueError) as exc:
        print(f'SEA: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
