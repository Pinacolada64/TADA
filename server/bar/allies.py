"""bar/allies.py — Shared ally query helpers.

Imported by bar.fat_olaf, commands.editplayer, and any other module that
needs to query player party membership or filter the master ally list.
"""
from typing import List, Optional, TYPE_CHECKING

from bar.ally_data import Ally, AllyFlags, AllyStatus

if TYPE_CHECKING:
    from network_context import GameContext


def filter_allies(
    ally_list: List[Ally],
    filter_by_status: Optional[AllyStatus] = None,
) -> List[Ally]:
    """Return allies matching an optional status filter.

    Pass filter_by_status=None to get all allies unfiltered.
    Examples:
        filter_allies(all_allies, AllyStatus.FREE)     # available for sale
        filter_allies(all_allies, AllyStatus.SERVANT)  # owned by someone
        filter_allies(all_allies)                       # everyone
    """
    if filter_by_status is None:
        return list(ally_list)
    return [a for a in ally_list if a.status == filter_by_status]


def owned_allies(player) -> List[Ally]:
    """Allies currently in this player's party."""
    return [m for m in player.party if isinstance(m, Ally)]


def purchased_allies(player) -> List[Ally]:
    """Allies this player purchased (SERVANT status), excluding free spirits (FREE)."""
    return [
        m for m in player.party
        if isinstance(m, Ally)
        and m.status == AllyStatus.SERVANT
    ]


async def pick_ally(
    ctx: 'GameContext',
    allies: List[Ally],
    prompt: str = 'Choose a servant',
    extra_fn=None,
) -> Optional[Ally]:
    """Display a numbered ally list and return the chosen Ally, or None on cancel.

    Callers build the list however they like (owned_allies, purchased_allies,
    filter_allies, etc.) and pass it here.  extra_fn(ally) -> str appends
    caller-specific info to each row (e.g. offer price, HP, strengthen cost).

        chosen = await pick_ally(ctx, purchased_allies(player), 'Sell which?',
                                 extra_fn=lambda a: f'(offer: {sellback(a)}s)')
    """
    if not allies:
        return None

    lines = ['']
    for i, a in enumerate(allies, 1):
        elite_tag  = '  [Elite]' if AllyFlags.ELITE in (a.flags or []) else ''
        status_tag = f'  [{a.status.name}]' if a.status not in (AllyStatus.FREE, AllyStatus.SERVANT) else ''
        extra      = f'  {extra_fn(a)}' if extra_fn else ''
        lines.append(f'  {i:>2}. {a.name:<22}  Str {a.strength:>2}  {a.to_hit * 10:>3}%{elite_tag}{status_tag}{extra}')
    lines.append('')
    await ctx.send(lines)

    raw = await ctx.prompt(f'{prompt} (1-{len(allies)}, Enter to cancel)')
    if not raw or not raw.strip():
        return None
    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(allies)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return None
    return allies[idx]
