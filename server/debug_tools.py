"""debug_tools.py — Debug-mode prompts for tripping rare game options.

Centralizes the "if DEBUG_MODE, ask a quick Y/N and act on it" pattern
that bar/skip.py grew ad hoc for forcing its once-per-day gate open
during testing. Any command/encounter/shop module that wants a debug
hook for something otherwise hard to reach in normal play (a rare NPC
option, a one-shot event, a random-roll threshold) should use these
instead of rolling its own flag-check + prompt + parse boilerplate.

Usage pattern
-------------
    from debug_tools import debug_confirm, debug_toggle_once_per_day

    # generic yes/no debug hook -- caller decides what to do with it:
    if await debug_confirm(ctx, "Force the trap to trigger?"):
        await _spring_trap(ctx)

    # once_per_day is common enough (bar/skip.py, shoppe/pawn.py,
    # encounters/meteor.py, encounters/djinn_sighting.py,
    # encounters/little_girl.py all gate on it) to get its own helper:
    await debug_toggle_once_per_day(ctx, 'Skip')
"""
from __future__ import annotations

from flags import PlayerFlags
from network_context import GameContext


async def debug_confirm(ctx: GameContext, question: str) -> bool:
    """Ask *question* as a Y/N prompt if the player is in debug mode;
    return False without prompting otherwise.

    Centralizes the flag-check + prompt + yes/no parse that a debug
    hook needs -- callers only have to decide what the answer means.
    """
    player = ctx.player
    if not player.query_flag(PlayerFlags.DEBUG_MODE):
        return False
    raw = await ctx.prompt('Y/N', preamble_lines=[question])
    return raw is not None and raw.strip().lower() in ('y', 'yes')


async def debug_toggle_once_per_day(ctx: GameContext, key: str, label: str | None = None) -> bool:
    """Debug-mode helper: ask whether to add *key* to
    player.once_per_day (SPUR's ys$/"*XX" once-per-day flag family --
    see bar/skip.py, shoppe/pawn.py, encounters/meteor.py,
    encounters/djinn_sighting.py, encounters/little_girl.py), and do it
    if confirmed. A no-op outside debug mode.

    *label* defaults to *key* for the prompt text, for callers whose
    once_per_day key isn't itself human-readable.

    Returns True if *key* is (now) present in player.once_per_day --
    including if it already was, so callers can act on the resulting
    state either way rather than just "was it just toggled."
    """
    player = ctx.player
    once = getattr(player, 'once_per_day', None)
    if once is None:
        player.once_per_day = once = []

    if key in once:
        return True

    if not await debug_confirm(ctx, f"Add '{label or key}' to once-per-day activities?"):
        return False

    once.append(key)
    player.unsaved_changes = True
    await ctx.send('Appended.')
    return True
