#!/usr/bin/env python3
"""One-off setup for the horse-journey bot demo (see bot_horse_journey.py).

Creates three throwaway accounts (bypassing the interactive character-
creation wizard) so bot_horse_journey.py can log straight in over the wire:

  botdummy  (Fighter) -- keeps a fight open so botlasso can join as a
                         bystander (LASSO is only reachable that way; the
                         fight's own leader is blocked in its own prompt
                         loop for the whole encounter)
  botlasso  (Fighter) -- captures the wild horse via LASSO
  botdruid  (Druid)   -- captures it via the passive class-affinity tame

All three: ADMIN flag on (for the '#<room>' teleport command), a known
elevator combination pre-seeded (normally learned from reading the SCRAP OF
PAPER item), and plenty of gold for Jake's Stable's saddle/armor/training.

Run from anywhere (paths are resolved relative to this file's location,
not the current working directory):
    .venv/bin/python tools/setup_bot_accounts.py

Re-running just overwrites the three accounts with fresh, empty-party state.
"""
import json
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

from base_classes import Combination, CombinationTypes, Gender, PlayerClass, PlayerMoneyTypes
from flags import PlayerFlags
from player import Player
from bot_credentials import DEFAULT_PASSWORD, set_password

import net_common
net_common.run_server_dir = str(_SERVER_DIR / 'run' / 'server')

_USER_DIR = _SERVER_DIR / 'run' / 'server' / 'net'
_PASSWORD = DEFAULT_PASSWORD
_ELEVATOR_COMBO = (11, 22, 33)

ACCOUNTS = [
    ('botdummy', PlayerClass.FIGHTER, Gender.MALE),
    ('botlasso', PlayerClass.FIGHTER, Gender.MALE),
    ('botdruid', PlayerClass.DRUID,   Gender.FEMALE),
]


def make_account(name: str, char_class, gender) -> None:
    player = Player(id=name, name=name, char_class=char_class, gender=gender,
                     map_level=1, map_room=1)
    player.set_flag(PlayerFlags.ADMIN)
    player.silver[PlayerMoneyTypes.IN_HAND] = 100_000
    # A fresh level-1 character's default 10 HP dies in 1-2 hits against a
    # WILD HORSE (it hit for 6+ in testing) -- bump survivability so the
    # demo can actually run several rounds instead of dying mid-fight.
    player.hit_points = 500
    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = _ELEVATOR_COMBO
    player.combinations[CombinationTypes.ELEVATOR] = combo
    player.unsaved_changes = True

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
