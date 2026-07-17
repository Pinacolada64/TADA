#!/usr/bin/env python3
"""One-off setup for the horse-journey and monster-encounter bot demos
(see bot_horse_journey.py and bot_monster_encounter.py).

Creates four throwaway accounts (bypassing the interactive character-
creation wizard) so the bot scripts can log straight in over the wire:

  botdummy   (Fighter) -- keeps a fight open so other bots can join as a
                          bystander (LASSO is only reachable that way; the
                          fight's own leader is blocked in its own prompt
                          loop for the whole encounter)
  botlasso   (Fighter) -- captures the wild horse via LASSO; also
                          bot_monster_encounter.py's ranged attacker --
                          pre-seeded with a .357 MAGNUM and two boxes of
                          .357 ammo so it can READY the gun and USE a box
                          live, instead of melee-joining like the others
  botdruid   (Druid)   -- captures the wild horse via the passive
                          class-affinity tame
  railbender (Fighter) -- pre-seeded with 3 purchased servant allies
                          (one ELITE) for bot_monster_encounter.py's
                          ORDER/tactical-ambush demo -- normally these
                          come from Fat Olaf's Slave Trade in the bar,
                          seeded directly here so the live bot script can
                          skip straight to the ORDER command

All four: ADMIN flag on (for the '#<room>' teleport command), a known
elevator combination pre-seeded (normally learned from reading the SCRAP OF
PAPER item), and plenty of gold for Jake's Stable's saddle/armor/training.

Run from anywhere (paths are resolved relative to this file's location,
not the current working directory):
    .venv/bin/python tools/setup_bot_accounts.py

Re-running just overwrites the four accounts with fresh, empty-party state
(railbender's 3 servants are always re-seeded fresh too).
"""
import json
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

from base_classes import Combination, CombinationTypes, Gender, PlayerClass, PlayerMoneyTypes
from flags import PlayerFlags
from player import Player

import net_common
net_common.run_server_dir = str(_SERVER_DIR / 'run' / 'server')

_USER_DIR = _SERVER_DIR / 'run' / 'server' / 'net'
_PASSWORD = 'puppy123'
_ELEVATOR_COMBO = (11, 22, 33)
# Mirrors bar/fat_olaf.py's purchase math: strength +5 on hire, then
# hit_points seeded as strength x2 (TADA extension, no canonical SPUR
# source -- see fat_olaf.py's _HP_PER_STRENGTH comment).
_HP_PER_STRENGTH = 2

ACCOUNTS = [
    ('botdummy',   PlayerClass.FIGHTER, Gender.MALE),
    ('botlasso',   PlayerClass.FIGHTER, Gender.MALE),
    ('botdruid',   PlayerClass.DRUID,   Gender.FEMALE),
    ('railbender', PlayerClass.FIGHTER, Gender.MALE),
]

# Names must match bar/ally_data.py's load_allies() master roster exactly.
# BATMAN is ELITE-flagged -- demonstrates combat/engine.py's tactical-ambush
# ELITE immunity branch when posted at whichever slot gets ambushed.
_RAILBENDER_ALLY_NAMES = ('BATMAN', 'ARTHUR DENT', 'BETTY BOOP')


def _seed_botlasso_gun(player) -> None:
    """Give botlasso a .357 MAGNUM (weapon #11) and two boxes of .357 ammo
    (item #104, objects.json) so bot_monster_encounter.py can READY the gun
    and USE a box live -- exercises commands/use.py's ammo-loading branch
    (fixed in this same session: shop-bought ammo used to lose its
    rounds/damage/used_with flags on purchase, so USE could never load it;
    see commands/use.py's _apply_item docstring)."""
    from inventory import Inventory
    from items import Item, ItemCategory, Weapon

    # Same re-seed-fresh reasoning as _seed_railbender_allies: Player.__init__
    # loads any pre-existing save (including a prior run's inventory) before
    # this runs.
    player.inventory = Inventory(capacity=player.max_inventory_size)

    weapon = Weapon(id_number=11, name='.357 MAGNUM', category=ItemCategory.WEAPON,
                     kind='standard', weapon_class='projectile',
                     stability=50, to_hit=70, price=200,
                     sound_effect=['KA-PWING!', 'BLAM!'])
    player.inventory.add(weapon)
    for _ in range(2):
        ammo = Item(id_number=104, name='.357 ammo', category=ItemCategory.ITEM,
                     price=1, flags={'rounds': 6, 'damage': 4, 'used_with': '.357 magnum'})
        player.inventory.add(ammo)


def _seed_railbender_allies(player) -> None:
    from bar.ally_data import AllyStatus, load_allies, save_ally_roster
    from party import Party

    # Player.__init__ loads any pre-existing save (including a prior run's
    # party) before this runs -- reset to empty so re-running this script
    # doesn't stack duplicate servants onto an already-seeded railbender.
    player.party = Party()

    master_list = load_allies()
    by_name = {a.name: a for a in master_list}
    for name in _RAILBENDER_ALLY_NAMES:
        ally = by_name[name]
        ally.status = AllyStatus.SERVANT
        ally.owner = player.name
        ally.strength += 5
        ally.hit_points = ally.strength * _HP_PER_STRENGTH
        player.party.add_member(player, ally)
    save_ally_roster(master_list)


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

    if name == 'railbender':
        _seed_railbender_allies(player)
    if name == 'botlasso':
        _seed_botlasso_gun(player)

    ok = player.save(force=True)
    if not ok:
        print(f'FAILED to save {name}')
        return

    _USER_DIR.mkdir(parents=True, exist_ok=True)
    (_USER_DIR / f'login-{name}.json').write_text(
        json.dumps({'password': net_common.hash_password(_PASSWORD)}, indent=2)
    )
    extra = ''
    if name == 'railbender':
        extra = f' -- servants: {", ".join(_RAILBENDER_ALLY_NAMES)}'
    if name == 'botlasso':
        extra = ' -- carrying: .357 MAGNUM, 2x .357 ammo'
    print(f'Created {name} ({char_class.value}, {gender.value}) -- '
          f'password {_PASSWORD!r}, elevator combo {"-".join(f"{n:02}" for n in _ELEVATOR_COMBO)}{extra}')


if __name__ == '__main__':
    for name, char_class, gender in ACCOUNTS:
        make_account(name, char_class, gender)
