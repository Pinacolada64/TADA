"""visited_rooms.py — per-player "have you been here" bitfield tracking.

Ryan's idea: rather than a list of visited room numbers (unbounded growth
as a player explores more of the game), track visited rooms the same way
GBBS Pro's own message-store header tracks "populated room" slots (see
LEVEL_AUDIT.md's room-renumbering investigation, §17/§18) -- one bit per
room number in the level's grid, packed MSB-first per byte, stored as a
hex string. Fixed size per level regardless of how much has actually been
explored: level 6 (the biggest grid, 900 rooms) costs 113 bytes / 226 hex
characters; a fully-explored small level costs the same as a
barely-touched one.

Used by commands/map.py's `map #visited [<level>]` (only rooms the
player has actually been to, unlike `map #overview`'s full level dump)
and by the mark_visited() calls wired into every place a player's
map_room actually changes (movement, teleport, elevator, vehicle launch,
admin teleport/editplayer -- see player.py's Player.__init__ and the
call sites listed there).
"""
from __future__ import annotations

# Grid width (SPUR's `ri`, "Room Incr.") per level -- hardcoded from
# D.LEVEL{N}.TXT's own header, same source LEVEL_AUDIT.md's room-
# renumbering investigation (§17) used. Not tracked anywhere on the
# runtime Map/Room objects. commands/map.py imports this same table
# (as _OVERVIEW_GRID_WIDTH) rather than keeping its own copy.
GRID_WIDTH = {1: 12, 2: 15, 3: 10, 4: 7, 5: 20, 6: 30, 7: 10}


def grid_capacity(level: int) -> int | None:
    """Total grid slots for *level* (SPUR's `nr` = ri*ri), or None if the
    level's grid width isn't known."""
    ri = GRID_WIDTH.get(level)
    return ri * ri if ri else None


def _bit_position(room: int) -> tuple[int, int]:
    """(byte_index, bitmask) for *room* (1-indexed), MSB-first per byte --
    matches SPUR-data/level-2/tada_level_builder.py's LevelHeader bitmap
    reader: room 1 is bit 7 of byte 0, room 8 is bit 7 of byte 1, etc."""
    byte_index, bit_in_byte = divmod(room - 1, 8)
    return byte_index, 1 << (7 - bit_in_byte)


def mark_visited(player, level: int, room: int) -> None:
    """Set the visited bit for (level, room). No-op if the level's grid
    width isn't known, the room number is out of range, or the bit was
    already set (avoids churning player.unsaved_changes on every step
    through already-explored territory)."""
    nr = grid_capacity(level)
    if not nr or not (1 <= room <= nr):
        return

    # isinstance check (not just "is None") on purpose: a MagicMock-based
    # test player that never set .visited_rooms explicitly returns an
    # auto-generated MagicMock attribute here, not None -- treat anything
    # that isn't a real dict the same as "not set yet" rather than
    # crashing deep in the hex/bytearray logic below.
    visited = getattr(player, 'visited_rooms', None)
    if not isinstance(visited, dict):
        visited = {}
        player.visited_rooms = visited

    key = str(level)
    n_bytes = (nr + 7) // 8
    existing = visited.get(key)
    raw = bytearray.fromhex(existing) if existing else bytearray(n_bytes)
    if len(raw) < n_bytes:
        raw.extend(b'\x00' * (n_bytes - len(raw)))

    byte_index, mask = _bit_position(room)
    if raw[byte_index] & mask:
        return

    raw[byte_index] |= mask
    visited[key] = raw.hex()
    player.unsaved_changes = True


def is_visited(player, level: int, room: int) -> bool:
    nr = grid_capacity(level)
    if not nr or not (1 <= room <= nr):
        return False
    visited = getattr(player, 'visited_rooms', None)
    if not isinstance(visited, dict):
        return False
    hex_str = visited.get(str(level))
    if not hex_str:
        return False
    raw = bytearray.fromhex(hex_str)
    byte_index, mask = _bit_position(room)
    return byte_index < len(raw) and bool(raw[byte_index] & mask)


def visited_room_numbers(player, level: int) -> set[int]:
    """Every room number marked visited on *level* -- used by `map
    #visited` to know which grid cells to render."""
    nr = grid_capacity(level)
    if not nr:
        return set()
    visited = getattr(player, 'visited_rooms', None)
    if not isinstance(visited, dict):
        return set()
    hex_str = visited.get(str(level))
    if not hex_str:
        return set()
    raw = bytearray.fromhex(hex_str)
    rooms = set()
    for byte_index, byte in enumerate(raw):
        if not byte:
            continue
        for bit_in_byte in range(8):
            if byte & (1 << (7 - bit_in_byte)):
                room = byte_index * 8 + bit_in_byte + 1
                if room <= nr:
                    rooms.add(room)
    return rooms
