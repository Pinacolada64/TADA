"""bar/thug_attack.py — Resolve a pending Blue Djinn hit contract at login.

bar/blue_djinn.py's HIRE flow sets PlayerFlags.THUG_ATTACK on the target
(online or offline, see set_thug_flag_on_target()) when a hit contract is
placed against them. This module carries out the actual ambush the next
time that target logs in -- called from simple_server.py's _game_loop(),
right before the room is shown.

Debug mode (PlayerFlags.DEBUG_MODE) gets an explicit Y/N to skip the
ambush for testing convenience, leaving the flag set so it can be
re-tested on a later login. Everyone else just gets jumped -- no prompt,
no way to dodge it, same as any other surprise attack.
"""
from __future__ import annotations

import logging

from flags import PlayerFlags
from network_context import GameContext

log = logging.getLogger(__name__)

_THUG_MONSTER_NUMBER = 60  # monsters.json "THUG"


async def maybe_trigger_thug_attack(ctx: GameContext) -> None:
    """Ambush the player with a THUG if PlayerFlags.THUG_ATTACK is set.

    No-op if the flag isn't set. Clears the flag and resolves every
    pending hit contract against this player once the fight (win, lose,
    or flee) is over -- unless a debug-mode player chooses to skip it,
    in which case the flag and contracts are left pending for next login.
    """
    player = ctx.player
    if not player.query_flag(PlayerFlags.THUG_ATTACK):
        return

    if player.query_flag(PlayerFlags.DEBUG_MODE):
        raw = await ctx.prompt('[DEBUG] Thug Attack flag is set -- skip the ambush? (Y/N)')
        if raw and raw.strip().lower().startswith('y'):
            await ctx.send('[DEBUG] Skipping thug ambush -- flag left set for next login.')
            return

    from bar.blue_djinn import pending_contracts, resolve_all_pending_contracts

    contracts = pending_contracts(player.name)
    attacker  = contracts[0].get('attacker_display', 'someone') if contracts else 'someone'

    await ctx.send([
        '',
        f'A thug leaps out of the shadows -- hired by {attacker}!',
        '',
    ])

    from monsters import get_monster
    monsters = getattr(ctx.server, 'monsters', []) or []
    monster  = get_monster(monsters, _THUG_MONSTER_NUMBER)

    if monster is None:
        log.error('THUG monster (#%d) not found -- skipping ambush combat, '
                   'still clearing the flag/contracts', _THUG_MONSTER_NUMBER)
    else:
        from combat import enter_combat
        await enter_combat(ctx, monster)

    player.clear_flag(PlayerFlags.THUG_ATTACK)
    player.unsaved_changes = True
    resolve_all_pending_contracts(player.name)
