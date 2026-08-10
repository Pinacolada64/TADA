#!/usr/bin/env python3
"""tools/setup_swarm_accounts.py — one-off setup for tools/bot_swarm.py's
10-bot concurrent stress test.

Creates ten throwaway accounts (bypassing the interactive character-
creation wizard) so bot_swarm.py can log straight in over the wire and
hammer the server concurrently: wandering, combat, page, whisper, shout,
item pickup, PvP duels, and giving/looting items between each other. A mix
of classes so combat exercises more than one code path (Wizard/Druid can
eventually CAST, though bot_swarm.py itself only attacks for now).

All ten: ADMIN flag on (for the '#<level> <room>' teleport command used to
scatter/regroup bots quickly), a known elevator combination pre-seeded,
generous HP so a swarm of 10 simultaneous attackers doesn't wipe itself out
on early monsters, plenty of gold, a LONG SWORD in inventory (bot_swarm.py
READYs it right after login -- player.readied_weapon is session-only, see
player.py's _SESSION_ONLY, so it can't be pre-seeded readied and must be
readied fresh every run; DUEL requires both sides to have one readied),
and 3 large rubies to give away (commands/give.py).

Targets tools/run_throwaway_server.py's isolated instance's save directory
(default run/epic_battle_server) -- NEVER the real run/server save
directory that the normal dev server on port 34083 uses.

Run from anywhere (paths are resolved relative to this file's location,
not the current working directory):
    .venv/bin/python tools/setup_swarm_accounts.py [--dir PATH]

Re-running just overwrites all ten accounts with fresh, empty-party state.
"""
import argparse
import json
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

parser = argparse.ArgumentParser()
parser.add_argument('--dir', default=str(_SERVER_DIR / 'run' / 'epic_battle_server'))
args = parser.parse_args()

from base_classes import Combination, CombinationTypes, Gender, PlayerClass, PlayerMoneyTypes
from flags import PlayerFlags
from player import Player
from bot_credentials import DEFAULT_PASSWORD, set_password

import net_common
net_common.run_server_dir = args.dir

_USER_DIR = Path(args.dir) / 'net'
_PASSWORD = DEFAULT_PASSWORD
_ELEVATOR_COMBO = (11, 22, 33)

# A spread of classes so the swarm isn't all melee -- ten bots, ten names.
ACCOUNTS = [
    ('botswarm01', PlayerClass.FIGHTER,   Gender.MALE),
    ('botswarm02', PlayerClass.FIGHTER,   Gender.FEMALE),
    ('botswarm03', PlayerClass.FIGHTER,   Gender.MALE),
    ('botswarm04', PlayerClass.PALADIN,   Gender.FEMALE),
    ('botswarm05', PlayerClass.RANGER,    Gender.MALE),
    ('botswarm06', PlayerClass.DRUID,     Gender.FEMALE),
    ('botswarm07', PlayerClass.DRUID,     Gender.MALE),
    ('botswarm08', PlayerClass.WIZARD,    Gender.FEMALE),
    ('botswarm09', PlayerClass.THIEF,     Gender.MALE),
    ('botswarm10', PlayerClass.ARCHER,    Gender.FEMALE),
]


def _seed_gear(player) -> None:
    """LONG SWORD (weapons.json #1) to READY live for DUEL, plus 3 large
    rubies (objects.json #6) to GIVE away. See _seed_botlasso_gun in
    setup_bot_accounts.py for the same construction pattern."""
    from inventory import Inventory
    from items import Item, ItemCategory, Weapon

    # Re-seed fresh, same reasoning as setup_bot_accounts.py's
    # _seed_railbender_allies: Player.__init__ loads any pre-existing save
    # (including a prior run's inventory) before this runs.
    player.inventory = Inventory(capacity=player.max_inventory_size)

    sword = Weapon(id_number=1, name='LONG SWORD', category=ItemCategory.WEAPON,
                    kind='standard', weapon_class='bash/slash',
                    stability=50, to_hit=60, price=250,
                    sound_effect=['SWISH!', 'SLASH!'])
    player.inventory.add(sword)
    for _ in range(3):
        ruby = Item(id_number=6, name='large ruby', category=ItemCategory.ITEM, price=8)
        player.inventory.add(ruby)


def make_account(name: str, char_class, gender) -> None:
    player = Player(id=name, name=name, char_class=char_class, gender=gender,
                     map_level=1, map_room=1)
    player.set_flag(PlayerFlags.ADMIN)
    player.silver[PlayerMoneyTypes.IN_HAND] = 100_000
    # A fresh level-1 character's default 10 HP dies in a hit or two against
    # even an early monster -- bump survivability so ten simultaneous
    # attackers churning through fights for an extended run don't just wipe
    # out in the first few minutes.
    player.hit_points = 500
    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = _ELEVATOR_COMBO
    player.combinations[CombinationTypes.ELEVATOR] = combo
    player.unsaved_changes = True
    _seed_gear(player)

    ok = player.save(force=True)
    if not ok:
        print(f'FAILED to save {name}')
        return

    _USER_DIR.mkdir(parents=True, exist_ok=True)
    (_USER_DIR / f'login-{name}.json').write_text(
        json.dumps({'password': net_common.hash_password(_PASSWORD)}, indent=2)
    )
    set_password(name, _PASSWORD)   # tools/.bot_credentials.json (gitignored)
    print(f'Created {name} ({char_class.value}, {gender.value}) -- '
          f'password {_PASSWORD!r}, elevator combo {"-".join(f"{n:02}" for n in _ELEVATOR_COMBO)}')


if __name__ == '__main__':
    for name, char_class, gender in ACCOUNTS:
        make_account(name, char_class, gender)
