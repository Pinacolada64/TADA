"""command_version.py — Per-command "last changed" info for #version/#ver.

Every command supports a bare '#version' or '#ver' switch (e.g. 'attack
#version') that reports when that command's own source file was last
committed, instead of actually running the command. See
commands/command_processor.py's process_command(), which intercepts the
switch centrally so no individual command needs to implement it itself.

Resolved via one lazy `git log -1` call per command file (each result is
cached for the life of the process, so a command's version is looked up
at most once per run). Falls back to the file's own mtime if git isn't
available -- e.g. a production deploy that ships the code without a
.git directory.
"""
from __future__ import annotations

import inspect
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

log = logging.getLogger(__name__)

_cache: dict[str, str] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _git_log_date(filepath: Path) -> Optional[str]:
    """Return the short-form date (YYYY-MM-DD) of filepath's last commit,
    or None if git isn't available, the file isn't tracked, or anything
    else goes wrong."""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ad', '--date=short', '--', str(filepath)],
            cwd=str(_repo_root()),
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            out = result.stdout.strip()
            return out or None
    except Exception:
        log.exception('command_version: git log failed for %s', filepath)
    return None


def _mtime_date(filepath: Path) -> str:
    ts = os.path.getmtime(filepath)
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')


def get_command_version(command: Union[type, object]) -> str:
    """Return a human-readable "last changed" date for *command*'s own
    source file (a Command instance or class).

    Prefers the file's last git-committed date; falls back to the file's
    own mtime (clearly labeled) if git is unavailable or the file isn't
    tracked -- e.g. a brand-new command that hasn't been committed yet.
    """
    cls = command if isinstance(command, type) else type(command)
    try:
        filepath = Path(inspect.getfile(cls)).resolve()
    except (TypeError, OSError):
        return 'unknown'

    key = str(filepath)
    if key in _cache:
        return _cache[key]

    date = _git_log_date(filepath)
    if date:
        result = date
    else:
        result = f'{_mtime_date(filepath)} (uncommitted or git unavailable -- file mtime)'

    _cache[key] = result
    return result
