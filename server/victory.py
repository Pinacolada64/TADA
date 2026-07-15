"""victory.py — Win/escape detection, SPUR.MISC7.S's `win`/`win2`/`win5`/
`nowin` labels.

SPUR trigger (SPUR.MISC.S:454, the `travel3`/`no.shop` labels): attempting
to go "Up" (di=5) while on level 6 (cl=6) intercepts the normal level
transition and links to spur.misc7's win check instead. In this port that
maps to room 117 "Shimmering Portal" on level 6 ("A Brave New World") --
the only room in the dataset with exits.rc==1 (Ladder Up); see
commands/movement.py's rc/rt handling for the call site.

Three gates, checked in SPUR's order:
  1. King of the Wraiths must be dead (SPUR: mid$(zu$,7,1) instr "12";
     here: PlayerFlags.WRAITH_KING_ALIVE must be False). Applies
     unconditionally, regardless of victory_type.
  2. If config.victory_type is 'item' or 'both': player must be carrying
     objects.json item #config.victory_item_number (SPUR's og/xi$).
  3. If config.victory_type is 'gold' or 'both': player must have at least
     config.victory_gold_amount silver in hand (SPUR's Tut's-treasure gold
     flag, deliberately generalized by config.py into a plain silver
     threshold -- see config.py's victory_gold_amount docstring; this port
     never wired up a Tut-specific flag, so there's nothing SPUR-literal
     to check here beyond the amount).

On success (SPUR's win5): prints a congratulations message, records the
win (winners.py), appends a battle.log entry, and posts a permanent news
item. On failure (SPUR's nowin): prints the same in-fiction refusal SPUR
used and blocks the move -- the caller (commands/movement.py) simply
doesn't move the player into room 117's "up" exit.
"""
from __future__ import annotations

import datetime
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from flags import PlayerFlags

if TYPE_CHECKING:
    from player import Player

log = logging.getLogger(__name__)


@dataclass
class VictoryResult:
    won: bool
    lines: list[str] = field(default_factory=list)


def _carries_item(player: "Player", item_number: int) -> bool:
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return False
    return any(
        getattr(entry.item, 'id_number', None) == item_number
        for entry in inv.entries()
    )


def _silver_in_hand(player) -> int:
    from base_classes import PlayerMoneyTypes
    return int(player.get_silver(PlayerMoneyTypes.IN_HAND) or 0)


def _append_battle_log(entry: str) -> None:
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    path = os.path.join(str(base or './run/server'), 'battle.log')
    try:
        with open(path, 'a') as fh:
            stamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            fh.write(f'[{stamp}] {entry}\n')
    except Exception:
        log.exception('Failed to write battle.log')


def _post_win_news(player_name: str) -> None:
    from news import load_news, next_id, save_news
    items = load_news()
    items.append({
        'id': next_id(items),
        'title': 'A Winner!',
        'body': [f'{player_name} has escaped SPUR and won the game!'],
        'author': 'SPUR',
        'posted_at': datetime.datetime.utcnow().isoformat(),
        'lifetime': 'permanent',
    })
    save_news(items)


def evaluate_victory(player: "Player") -> VictoryResult:
    """Check the three win gates against *player*'s current state and
    config.py's victory_type/victory_gold_amount/victory_item_number.

    Does NOT record the win or apply any side effects -- call
    declare_victory() for that once this returns won=True.
    """
    from config import config

    if player.query_flag(PlayerFlags.WRAITH_KING_ALIVE):
        return VictoryResult(False, [
            "A voice echoes in your ear..",
            "'Thou may not leave my land until the King of the Wraiths is slain!'",
        ])

    victory_type = config.victory_type

    if victory_type in ('item', 'both'):
        item_number = config.victory_item_number
        if item_number and not _carries_item(player, item_number):
            return VictoryResult(False, [
                "A voice echoes in your ear..",
                "'Ye does not have the Object I have sought! Ye may not pass!'",
            ])

    if victory_type in ('gold', 'both'):
        amount = config.victory_gold_amount
        if _silver_in_hand(player) < amount:
            return VictoryResult(False, [
                "A voice echoes in your ear..",
                "'Ye has not found riches enough to pass through!'",
            ])

    lines = ["A voice echoes in your ear.."]
    if victory_type in ('item', 'both') and config.victory_item_number:
        lines.append("'Ye have found the Object I have sought!'")
    if victory_type in ('gold', 'both'):
        lines.append("'Ye have found Riches enough to pass through!'")
    return VictoryResult(True, lines)


def declare_victory(player: "Player") -> list[str]:
    """Apply win side effects (winners list, battle log, news) and return
    the celebration lines to show the player. Caller's job to have already
    confirmed evaluate_victory(player).won is True."""
    import winners

    winners.record_win(player)
    _append_battle_log(f'{player.name} has WON THE GAME!')
    _post_win_news(player.name)

    return [
        '',
        'CONGRATULATIONS! YOU HAVE WON!!',
        "Adding to conqueror's list..",
        '',
    ]
