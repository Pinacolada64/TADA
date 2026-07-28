"""encounters/gollum.py — Gollum guards the ring in his cave (level 4,
room 17 "Gollum's Cave", monsters.json #71).

Room 17 has both the monster and the ring (objects.json #67 "ring") sitting
in it together, but nothing previously stopped a player from just GETting
the ring out from under a live Gollum. This gives him what SPUR-flavored
guard monsters elsewhere already do for their own treasure (see
quests/tuts_treasure.py's King Tut, encounters/dwarf.py's hoard): a refusal
plus a real fight, not just a rebuff message.
"""
from __future__ import annotations

RING_ITEM_ID     = 67
MONSTER_NUMBER   = 71
QUOTE            = "You cannot have my precioussssss!"


def guards_ring(item_id, monster: dict | None) -> bool:
    """True if *monster* is a living Gollum guarding item #67."""
    try:
        if int(item_id) != RING_ITEM_ID:
            return False
    except (TypeError, ValueError):
        return False

    if not monster or int(monster.get('number', 0) or 0) != MONSTER_NUMBER:
        return False

    # Not "monster.get('strength') or monster.get('hit_points') or 1"
    # (get.py's own _try_get_living uses that chain) -- 0 is falsy, so
    # that pattern would treat a dead (strength=0) monster as alive again.
    hp = monster.get('strength')
    if hp is None:
        hp = monster.get('hit_points', 1)
    return int(hp) > 0
