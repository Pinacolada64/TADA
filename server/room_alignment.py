"""room_alignment.py — Persistence for turf capture: a room's
RoomAlignment can be flipped to a duel winner's guild at runtime (see
combat/duel.py's DuelSession._end()), and needs to survive a server
restart. Not a SPUR mechanic -- SPUR's own turf is permanent, baked
into each room's name at map-build time and never mutated by combat
(see RoomAlignment's docstring in base_classes.py). This is Ryan's own
extension: guild territory is capturable via SPORT DUEL, except HQ
rooms, which stay immutable forever.

Room objects themselves are the live, shared, in-memory source of
truth (one Map, read once at startup -- see simple_server.py's
`self.game_map = Map()` / `read_map()` loop) with no save/serialize-
back-to-JSON capability, and the map JSON files are treated as
read-only asset data everywhere else in the codebase. So captures are
NOT written back into level_N.json; instead this module follows the
same run/server/*.json sidecar-state idiom as guild_standings.py/
encounters/dwarf.py's dwarf_state.json: overrides are persisted here
and re-applied onto the freshly-loaded Room objects once at startup,
right after read_map() (see simple_server.py).

Split one file per dungeon level (rather than a single file for the
whole game) since the room count across all levels is large and only
ever a handful of rooms in any given level will actually be under
contested guild control at once -- keeps each file small and avoids
rewriting unrelated levels' data on every capture.

Storage schema (run/server/room_alignment_level_<N>.json):
  {
    "<room_number>": "<RoomAlignment.value>"
  }
"""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_STATE_DIR = Path('run') / 'server'


def _state_file(level: int) -> Path:
    return _STATE_DIR / f'room_alignment_level_{level}.json'


def load_overrides(level: int) -> dict:
    """Return {"<room_number>": "<RoomAlignment.value>"} for one level."""
    try:
        state_file = _state_file(level)
        if state_file.exists():
            return json.loads(state_file.read_text())
    except Exception:
        log.exception('Failed to load room alignment overrides for level %d', level)
    return {}


def save_overrides(level: int, overrides: dict) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_file(level).write_text(json.dumps(overrides, indent=2))


def record_capture(level: int, room_number: int, alignment) -> None:
    """Persist a single room's new alignment (called after a live in-memory
    mutation, e.g. combat/duel.py's turf-capture on a decisive duel win)."""
    overrides = load_overrides(level)
    value = alignment.value if hasattr(alignment, 'value') else str(alignment)
    overrides[str(room_number)] = value
    save_overrides(level, overrides)


def apply_overrides(game_map) -> None:
    """Re-apply persisted captures onto the freshly-loaded Map at startup.

    Scans run/server/ for room_alignment_level_<N>.json files rather than
    assuming a fixed level range, so it stays correct as levels are added.
    Silently skips rooms that no longer exist (map data changed since the
    override was recorded) or whose current (fresh-from-JSON) alignment is
    HQ -- HQ is immutable even here, in case a bug or manual edit ever
    wrote one out (belt-and-suspenders on top of the same guard in
    combat/duel.py's capture logic).
    """
    from base_classes import RoomAlignment
    if game_map is None or not _STATE_DIR.exists():
        return
    for state_file in _STATE_DIR.glob('room_alignment_level_*.json'):
        try:
            level = int(state_file.stem.rsplit('_', 1)[-1])
        except ValueError:
            continue
        overrides = load_overrides(level)
        for room_str, value in overrides.items():
            try:
                room_number = int(room_str)
            except ValueError:
                continue
            room = game_map.get_room(level, room_number)
            if room is None or room.alignment == RoomAlignment.HQ:
                continue
            try:
                room.alignment = RoomAlignment(value)
            except ValueError:
                log.warning('Unknown RoomAlignment value %r for level %d room %d',
                             value, level, room_number)
