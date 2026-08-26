"""board/access.py — Permission checks shared across the board package.

is_board_admin() is pulled forward from the sig-editor plan's Phase 3
(full player_can_access() access-gating enforcement) because freeze/
unfreeze needs "is this player a SIGop/subop for this board" *now* --
Phase 3's own player_can_access() (read/post gating by guild or
PlayerFlags) still isn't implemented; this file is where it'll land
alongside is_board_admin() when that phase happens, rather than being
scattered into commands/board/*.py ad hoc.
"""
from __future__ import annotations

from flags import PlayerFlags


def _is_privileged(player) -> bool:
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def is_board_admin(player, board_meta: dict) -> bool:
    """Global ADMIN/DUNGEON_MASTER, or named in *board_meta*'s own
    'admins' list (a board-local admin -- ImageBBS's "SIGop"/"SubOp")."""
    return _is_privileged(player) or player.name in board_meta.get('admins', [])
