#!/usr/bin/env python3
"""seed_railbender_uzis.py — One-off seed for testing commands/stats.py's
new "Weapon readied" (player) and "[Wpn: ...] [Worn: ...]" (ally) STAT
display live against the running server.

Loads the existing railbender account (see setup_bot_accounts.py -- it
already carries 3 servant allies: BATMAN, ARTHUR DENT, BETTY BOOP) and adds
two UZIs + two boxes of 9 mm ammo to its inventory: one set for railbender
to READY/USE on itself, one to GIVE to an ally (ARTHUR DENT) so both the
player-side and ally-side STAT display can be exercised live in one
session. Does NOT touch railbender's allies/flags/gold -- just adds
inventory on top of whatever's already saved.

Run from anywhere:
    .venv/bin/python tools/seed_railbender_uzis.py
"""
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

import net_common
net_common.run_server_dir = str(_SERVER_DIR / 'run' / 'server')

from items import Item, ItemCategory, Weapon
from player import Player

_UZI_ID   = 46   # UZI (weapons.json)
_9MM_ID   = 108  # 9 mm ammo (objects.json) -- used_with: 'uzi'


def main() -> None:
    player = Player(id='railbender', name='railbender')
    if not player.inventory:
        print('railbender has no inventory object -- run setup_bot_accounts.py first.')
        return

    for _ in range(2):
        player.inventory.add(Weapon(
            id_number=_UZI_ID, name='UZI', category=ItemCategory.WEAPON,
            kind='standard', weapon_class='projectile',
            stability=50, to_hit=70, price=300,
            sound_effect=['click..', 'BRRRT!'],
        ))
        player.inventory.add(Item(
            id_number=_9MM_ID, name='9 mm', category=ItemCategory.ITEM,
            price=4, flags={'rounds': 50, 'damage': 3, 'used_with': 'uzi'},
        ))

    player.unsaved_changes = True
    ok = player.save(force=True)
    print('Saved railbender with 2x UZI + 2x 9 mm ammo.' if ok else 'FAILED to save railbender.')


if __name__ == '__main__':
    main()
