"""board/meta.py — Per-board settings storage (name, anonymous-posting
mode, access gating, admin list) for the message board -- see board/
__init__.py's module docstring for why this got split out of the old
top-level board.py.

One flat JSON file (run/server/board_meta.json, replacing the old
board_config.json), keyed by board id as a string (JSON object keys are
always strings):

    {
      "boards": {
        "1": {
          "id": 1,
          "name": "General",
          "anonymous_mode": "ask",      -- 'ask'/'yes'/'no', see get_board()
          "access": {"type": "any"},    -- Phase 3 (access.py) reads this;
                                            unused/unenforced this phase
          "admins": []                  -- board-local admins; Phase 2+
        }
      }
    }

load_config()/save_config() are a back-compat shim matching the old
board.py's flat-file API (`{'anonymous_mode': ...}`) -- Phase 1 keeps
'board #edit' (commands/board/edit.py) and 'board post'/'board reply's
own anonymous-posting prompt (commands/board/board.py's
resolve_anonymous()) working unchanged against the single default board
(id 1) that exists until Phase 2's SIG/board editor lands.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

META_FILE = Path('run') / 'server' / 'board_meta.json'

# Filled in for any board id looked up via get_board() that isn't (yet)
# present in the stored file -- same "missing file/key falls back to
# sane defaults" convention as the old board.py's load_config().
DEFAULT_BOARD_META = {
    'name': 'General',
    'anonymous_mode': 'ask',
    'access': {'type': 'any'},
    'admins': [],
}

# Phase 1: only one board exists (no SIG/board editor yet -- see
# commands/board/board.py), so every call site hardcodes this id until
# Phase 2 replaces them with real board selection.
DEFAULT_BOARD_ID = 1


def load_meta(path: Optional[Path] = None) -> dict:
    """Return {'boards': {...}}. {'boards': {}} if missing.

    path defaults to the module-level META_FILE, looked up at call time
    (not bound at import) so tests can patch meta.META_FILE directly."""
    path = path or META_FILE
    try:
        if path.exists():
            data = json.loads(path.read_text())
            data.setdefault('boards', {})
            return data
    except Exception:
        log.exception('Failed to load board meta file %s', path)
    return {'boards': {}}


def save_meta(meta: dict, path: Optional[Path] = None) -> None:
    path = path or META_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2))


def get_board(meta: dict, board_id: int) -> dict:
    """One board's settings, filled in with DEFAULT_BOARD_META for
    anything missing/never-saved (including the board not existing in
    *meta* at all yet)."""
    board = dict(DEFAULT_BOARD_META)
    board.update(meta.get('boards', {}).get(str(board_id), {}))
    board['id'] = board_id
    return board


def set_board(meta: dict, board_id: int, board: dict) -> None:
    meta.setdefault('boards', {})[str(board_id)] = board


def load_config(path: Optional[Path] = None) -> dict:
    """Back-compat shim: the old board.py's load_config() returned just
    `{'anonymous_mode': ...}` for the one board that existed. Reads that
    same setting off the default board's meta now."""
    board = get_board(load_meta(path), DEFAULT_BOARD_ID)
    return {'anonymous_mode': board.get('anonymous_mode', 'ask')}


def save_config(config: dict, path: Optional[Path] = None) -> None:
    """Back-compat shim: the old board.py's save_config() -- writes
    `config['anonymous_mode']` onto the default board's meta."""
    meta = load_meta(path)
    board = get_board(meta, DEFAULT_BOARD_ID)
    board['anonymous_mode'] = config.get('anonymous_mode', 'ask')
    set_board(meta, DEFAULT_BOARD_ID, board)
    save_meta(meta, path)
