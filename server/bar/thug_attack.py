"""bar/thug_attack.py — Resolve a pending Blue Djinn hit contract at login.

bar/blue_djinn.py's HIRE flow sets PlayerFlags.THUG_ATTACK on the target
(online or offline, see set_thug_flag_on_target()) when a hit contract is
placed against them. This module carries out the actual ambush the next
time that target logs in -- called from simple_server.py's _game_loop(),
right before the room is shown.

The flag and hit_contracts.json are meant to move together, but treat
either one alone as sufficient to trigger the ambush (and clear/resolve
both once it does) rather than requiring both in lockstep -- an ambush
should never go permanently unresolved just because the two fell out of
sync somewhere (e.g. a contract recorded by code that predates the flag
being wired in, or the flag toggled directly via EditPlayer's
Flags/Counters menu). Either mismatch direction still logs a warning so
it's diagnosable.

Debug mode (PlayerFlags.DEBUG_MODE) gets an explicit Y/N to skip the
ambush for testing convenience, leaving the flag/contracts pending so it
can be re-tested on a later login. Everyone else just gets jumped -- no
prompt, no way to dodge it, same as any other surprise attack.
"""
from __future__ import annotations

import logging

from flags import PlayerFlags
from network_context import GameContext

log = logging.getLogger(__name__)

_THUG_MONSTER_NUMBER = 60  # monsters.json "THUG"


async def maybe_trigger_thug_attack(ctx: GameContext) -> None:
    """Ambush the player with a THUG if THUG_ATTACK is set and/or there's
    a pending hit contract against them -- see module docstring for why
    either one alone is enough to trigger.

    No-op if neither is present. Clears the flag and resolves every
    pending hit contract once the fight (win, lose, or flee) is over --
    unless a debug-mode player chooses to skip it, in which case both are
    left pending for next login.
    """
    player = ctx.player

    from bar.blue_djinn import pending_contracts, resolve_all_pending_contracts

    flagged   = player.query_flag(PlayerFlags.THUG_ATTACK)
    contracts = pending_contracts(player.name)

    if not flagged and not contracts:
        return

    if flagged and not contracts:
        # Flag set but no matching hit_contracts.json record -- e.g. the
        # flag was toggled directly via EditPlayer's Flags/Counters menu,
        # or a contract was deleted/resolved without clearing the flag.
        log.warning('%s has THUG_ATTACK set but no pending hit contract -- '
                     'ambushing anyway with a generic attacker', player.name)
    elif contracts and not flagged:
        # The reverse desync: a contract exists (e.g. placed by an older
        # build before set_thug_flag_on_target() existed) but the flag
        # was never set. Without this branch the contract would sit
        # unresolved forever, since nothing else ever calls in here.
        log.warning('%s has a pending hit contract but THUG_ATTACK is not '
                     'set -- ambushing anyway', player.name)

    if player.query_flag(PlayerFlags.DEBUG_MODE):
        raw = await ctx.prompt('[DEBUG] Thug Attack pending -- skip the ambush? (Y/N)')
        if raw and raw.strip().lower().startswith('y'):
            await ctx.send('[DEBUG] Skipping thug ambush -- left pending for next login.')
            return

    attacker = contracts[0].get('attacker_display', 'someone') if contracts else 'someone'

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
