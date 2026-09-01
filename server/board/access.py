"""board/access.py — Permission checks shared across the board package.

is_board_admin() landed ahead of the rest of Phase 3 (full
player_can_access() access-gating enforcement) because freeze/unfreeze
needed "is this player a SIGop/subop for this board" right away.
player_can_access() is the read/post gate itself: it checks a board's
'access' dict (set via commands/board/edit.py's [A]nyone/[G]uild/
[F]lag/[O]r picker) against the player's guild/PlayerFlags.
accessible_board_ids()/visible_sigs() are the filtering helpers built
on top of it -- wired into commands/board/board.py's pick_board()/
_navigate() (so a gated board never appears in a picker or as a '>'/
'<'/'>>'/'<<' destination) and into _post()/_reply()/_delete()/
_read_one() (so a direct 'board <id>'/'board reply <id>'/'board delete
<id>' can't reach a thread on a board the player can't access either).
"""
from __future__ import annotations

import logging

from base_classes import Guild
from flags import PlayerFlags

log = logging.getLogger(__name__)


def _is_privileged(player) -> bool:
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def is_board_admin(player, board_meta: dict) -> bool:
    """Global ADMIN/DUNGEON_MASTER, or named in *board_meta*'s own
    'admins' list (a board-local admin -- ImageBBS's "SIGop"/"SubOp")."""
    return _is_privileged(player) or player.name in board_meta.get('admins', [])


def _guild_gate_matches(player, value: str) -> bool:
    try:
        return player.guild == Guild(value)
    except ValueError:
        log.warning("board access gate: unknown guild value %r", value)
        return False


def _flag_gate_matches(player, value: str) -> bool:
    try:
        return bool(player.query_flag(PlayerFlags[value]))
    except KeyError:
        log.warning("board access gate: unknown flag name %r", value)
        return False


def _single_gate_matches(player, gate: dict) -> bool:
    kind = gate.get('type')
    if kind == 'guild':
        return _guild_gate_matches(player, gate.get('value'))
    if kind == 'flag':
        return _flag_gate_matches(player, gate.get('value'))
    log.warning("board access gate: unknown gate type %r", kind)
    return False


def player_can_access(player, board_meta: dict) -> bool:
    """Can *player* see/read/post to a board with this metadata dict?

    Global ADMIN/DUNGEON_MASTER always can, regardless of 'access'.
    Otherwise dispatches on board_meta['access']['type']:
      'any'    -- everyone
      'guild'  -- player.guild matches access['value'] (a Guild.value)
      'flag'   -- player.query_flag(PlayerFlags[access['value']])
      'any_of' -- True if any sub-gate in access['values'] matches
                  (each a {'type': 'guild'|'flag', 'value': ...} dict,
                  same shape as a top-level single gate)

    An unrecognized gate type/value is treated as inaccessible rather
    than raising -- board_meta.json's strings aren't statically
    validated against Guild/PlayerFlags, so a stale or hand-edited
    value must fail closed, not crash the listing for everyone.
    """
    if _is_privileged(player):
        return True

    access = board_meta.get('access', {'type': 'any'})
    kind = access.get('type', 'any')

    if kind == 'any':
        return True
    if kind == 'any_of':
        return any(_single_gate_matches(player, gate) for gate in access.get('values', []))
    return _single_gate_matches(player, access)


def accessible_board_ids(player, meta_data: dict, board_ids: list[int]) -> list[int]:
    """*board_ids* filtered down to the ones *player* can access, order
    preserved -- used to filter a SIG's board list before it's shown in
    a picker or stepped through via '>'/'<' navigation."""
    from board.meta import get_board
    return [bid for bid in board_ids if player_can_access(player, get_board(meta_data, bid))]


def visible_sigs(player, sig_list: list[dict], meta_data: dict) -> list[dict]:
    """*sig_list* filtered down to SIGs holding at least one board
    *player* can access -- a SIG with nothing they're allowed into
    shouldn't appear as a choice at all (same anti-leak reasoning as
    player_can_access() itself: don't reveal that gated content exists
    behind a name they can't otherwise get to)."""
    return [sig for sig in sig_list
            if accessible_board_ids(player, meta_data, sig.get('board_ids', []))]
