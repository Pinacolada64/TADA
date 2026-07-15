"""winners.py — Persisted list of players who have won the game.

SPUR source: SPUR.MISC7.S's `win5` label writes the victor to a
`spur.winners` file ("Adding to conqueror's list.."). This is the
persistence half of that -- see victory.py's declare_victory(), which
calls record_win() after all three win gates pass.

Storage schema (run/server/winners.json), a plain list, oldest-first:
  [
    {"name": "...", "char_class": "...", "char_race": "...",
     "xp_level": N, "won_at": "<ISO datetime>"}
  ]
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from player import Player

log = logging.getLogger(__name__)

_WINNERS_FILE = Path('run') / 'server' / 'winners.json'


def load_winners() -> list[dict]:
    try:
        if _WINNERS_FILE.exists():
            return json.loads(_WINNERS_FILE.read_text())
    except Exception:
        log.exception('Failed to load winners list')
    return []


def save_winners(winners: list[dict]) -> None:
    _WINNERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WINNERS_FILE.write_text(json.dumps(winners, indent=2))


def record_win(player: "Player") -> None:
    winners = load_winners()
    char_class = getattr(player, 'char_class', None)
    char_race = getattr(player, 'char_race', None)
    winners.append({
        'name': player.name,
        'char_class': str(char_class).split('.')[-1].title() if char_class else 'Unknown',
        'char_race': str(char_race).split('.')[-1].title() if char_race else 'Unknown',
        'xp_level': getattr(player, 'xp_level', 1),
        'won_at': datetime.datetime.utcnow().isoformat(),
    })
    save_winners(winners)
