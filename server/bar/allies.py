"""bar/allies.py — Shared ally query helpers.

Imported by bar.fat_olaf, commands.editplayer, and any other module that
needs to query player party membership or filter the master ally list.
"""
from typing import List, Optional

from bar.ally_data import Ally, AllyStatus


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
