"""statues.py — Petrified-player room statues (SPUR.MISC.S/MISC6.S).

When a player is turned to stone (combat/engine.py's _player_petrified(),
death cause z=6), SPUR leaves a permanent statue sitting in that room --
a later GET or EXAMINE of it checks a room flag (wy$ containing "#") and
responds without letting anyone actually take it. This module is the
persisted, shared (not per-player) equivalent: which (level, room) pairs
currently have a statue, so every player who visits sees the same thing.

Distinct from combat/engine.py's _record_statue(), which only writes a
per-monster memorial text file (a list of past victims) -- that's a log,
not queryable room state. This is the queryable state commands/get.py
needs.

Design mirrors news.py: loaded/saved fresh on every call rather than
cached on the server object, so a petrification during one connection
is immediately visible to everyone else.

    [
      {"level": 6, "room": 234, "monster": "THE MEDUSA", "victim": "Alice"},
      ...
    ]
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

ROOM_STATUES_FILE = Path('run') / 'server' / 'room_statues.json'


def load_room_statues(path: Optional[Path] = None) -> list[dict]:
    """Return the list of room-statue records. [] if missing.

    path defaults to the module-level ROOM_STATUES_FILE, looked up at
    call time (not bound at import) so tests can patch
    statues.ROOM_STATUES_FILE directly.
    """
    path = path or ROOM_STATUES_FILE
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        log.exception('Failed to load room statues file %s', path)
    return []


def save_room_statues(statues: list[dict], path: Optional[Path] = None) -> None:
    path = path or ROOM_STATUES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(statues, indent=2))


def get_statue(level: int, room: int, path: Optional[Path] = None) -> Optional[dict]:
    """Return the statue record at (level, room), or None."""
    for s in load_room_statues(path):
        if s.get('level') == level and s.get('room') == room:
            return s
    return None


def has_statue(level: int, room: int, path: Optional[Path] = None) -> bool:
    """Whether (level, room) currently has a statue -- SPUR's
    instr("#", wy$) room-flag check."""
    return get_statue(level, room, path) is not None


def add_statue(level: int, room: int, monster: str, victim: str,
              path: Optional[Path] = None) -> None:
    """Record a new statue at (level, room). No-op if one is already
    recorded there (a room only ever has the one statue at a time in
    SPUR -- wy$ is a single flag, not a count)."""
    statues = load_room_statues(path)
    if any(s.get('level') == level and s.get('room') == room for s in statues):
        return
    statues.append({'level': level, 'room': room, 'monster': monster, 'victim': victim})
    save_room_statues(statues, path)
