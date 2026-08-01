#!/usr/bin/env python3
"""tools/setup_epic_battle_account.py — one-off setup for
tools/bot_epic_battle.py: a single throwaway hero, pre-seeded with
everything the demo needs to hit ammo, STORM weapon, mount/unmount, and
PC/monster spellcasting all in one run, short of the STORM BOW itself
(bought live from the Armory -- see _seed_gear()'s docstring for why it
can't be pre-seeded alongside the Death Amulet) and shop-visit detours.

SYLVANWYND, Druid/Elf: weapon_bonus(STORM BOW, 'Druid', 'Elf') = (2, 2) --
the single best class/race affinity for that weapon in item_system.py's
table -- so readying it live never triggers the "YOU ARE NOT MINE!!"
rejection blast (see commands/ready.py's STORM jealousy/rejection block).
Only ONE STORM weapon is ever carried: readying a second one while a
STORM weapon is already readied makes the current one "HOWL IN RAGE" and
disintegrate (commands/ready.py:201-230) -- so this demo commits to the
STORM BOW for the whole run rather than switching to a STORM STAFF
mid-fight for the Wizard staff-cast bonus.

Targets its own throwaway server (see tools/run_throwaway_server.py) via
net_common.run_server_dir -- NEVER the real run/server save directory.

Usage:
    .venv/bin/python tools/setup_epic_battle_account.py [--dir PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

parser = argparse.ArgumentParser()
parser.add_argument('--dir', default=str(_SERVER_DIR / 'run' / 'epic_battle_server'))
args = parser.parse_args()

import net_common
net_common.run_server_dir = args.dir

from base_classes import Combination, CombinationTypes, Gender, PlayerClass, PlayerRace, PlayerMoneyTypes
from flags import PlayerFlags
from player import Player
from bot_credentials import DEFAULT_PASSWORD, set_password
from items import Item, ItemCategory, Spell, Weapon
from inventory import Inventory

_USER_DIR = Path(args.dir) / 'net'
_PASSWORD = DEFAULT_PASSWORD
_HERO_NAME = 'sylvanwynd'
_ELEVATOR_COMBO = (11, 22, 33)
_HP_PER_STRENGTH = 2

# weapons.json #34 -- STORM BOW (projectile), bought live from the Armory
# instead of seeded here (see _seed_gear()'s docstring). Druid/Elf gets
# (skill+2, damage+2) from item_system.weapon_bonus(), the best affinity
# on the table, so it's always accepted, never rejected, once readied.

# objects.json #100 -- arrows, used_with ' bow' (matches "STORM BOW").
_ARROWS = dict(id_number=100, name='arrows', category=ItemCategory.ITEM, price=1,
               flags={'rounds': 10, 'damage': 1, 'used_with': ' bow'})

# objects.json #82 -- Crystal Pendant (blocks monster turn-to-stone).
_CRYSTAL_PENDANT_ID = 82

# weapons.json #56 -- DEATH AMULET: READYing it gambles a 20% instant-death
# chance, halved to 10% by carrying objects.json #76 Amulet of Life
# (commands/ready.py:261-291). Ready this FIRST, before the STORM BOW --
# once a STORM weapon is readied it can never be swapped away from without
# the current one "howling in rage" and disintegrating (ready.py:201-230),
# so this is the only slot in the run where a second weapon-ready is safe.
_DEATH_AMULET = dict(id_number=56, name='DEATH AMULET', category=ItemCategory.WEAPON,
                      kind='magic', weapon_class='proximity',
                      stability=50, to_hit=40, price=9000,
                      sound_effect=['CRACK!', 'CRACK!'])
_AMULET_OF_LIFE_ID = 76

# shoppe/wizard.py SPELLS -- monster-damage (M) and one stat (S) spell,
# seeded straight into the Spell Book (spellbook.py), same container
# shoppe/wizard.py's real purchase path uses.
_SPELLS = [
    dict(id_number=8, name='SLAUGHTER', cast_chance=90, effect_type='M', effect_magnitude=4),
    dict(id_number=4, name='KILL',      cast_chance=60, effect_type='M', effect_magnitude=6),
    dict(id_number=2, name='WHEATIES',  cast_chance=70, effect_type='S', effect_magnitude=6),
]

# Only 2 servants, not 3 -- owned_allies() caps a party at 3 total
# (bar.allies/combat.engine._mount_slot_available), so one slot must stay
# open for the WILD HORSE mount ally LASSO captures later in the run.
_ALLY_NAMES = ('BATMAN', 'ARTHUR DENT')  # BATMAN is ELITE-flagged


def _seed_gear(player) -> None:
    player.inventory = Inventory(capacity=player.max_inventory_size)

    # Nothing pre-readied -- the bot script READYs the Death Amulet live,
    # over the wire, so ready.py's Amulet-of-Life-halved gamble actually
    # runs instead of being short-circuited by pre-set player state.
    #
    # The STORM BOW is deliberately NOT seeded here at all -- carrying it
    # (readied or not) at the same time as the Death Amulet is readied
    # triggers ready.py's STORM jealousy/rejection mechanic regardless of
    # order (an unreadied STORM weapon "howls in jealous rage" the instant
    # anything else is readied; a READIED STORM weapon "refuses to be
    # replaced" the instant anything else is readied over it) -- either
    # way the STORM BOW disintegrates before the run ever reaches it. The
    # bot script instead has the hero BUY it live from the Armory
    # (shoppe/armory.py) after the Death Amulet gamble resolves, so it
    # only ever enters inventory once nothing else is fighting it for the
    # readied slot.
    player.inventory.add(Weapon(**_DEATH_AMULET))
    player.inventory.add(Item(id_number=_AMULET_OF_LIFE_ID, name='Amulet of Life',
                               category=ItemCategory.ITEM, price=0))

    for _ in range(3):
        player.inventory.add(Item(**_ARROWS))

    player.inventory.add(Item(id_number=_CRYSTAL_PENDANT_ID, name='CRYSTAL PENDANT',
                               category=ItemCategory.ITEM, price=0))


def _seed_spells(player) -> None:
    import spellbook
    book = spellbook.ensure_spellbook(player)
    target = book.contents if book is not None else player.inventory
    for sp in _SPELLS:
        target.add(Spell(charges=1, max_charges=1, **sp))


def _seed_allies(player) -> None:
    from bar.ally_data import AllyStatus, load_allies, save_ally_roster
    from party import Party

    player.party = Party()
    master_list = load_allies()
    by_name = {a.name: a for a in master_list}
    for name in _ALLY_NAMES:
        ally = by_name[name]
        ally.status = AllyStatus.SERVANT
        ally.owner = player.name
        ally.strength += 5
        ally.hit_points = ally.strength * _HP_PER_STRENGTH
        player.party.add_member(player, ally)
    save_ally_roster(master_list)


_ANCHOR_NAME = 'thornshield'


def make_anchor_account() -> None:
    """thornshield (Fighter, plain LONG SWORD): exists purely to be the
    fight's *leader* whenever sylvanwynd needs to act as a bystander
    instead -- LASSO and CAST are both top-level commands only reachable
    from the ordinary main-prompt loop (combat.engine.CombatSession.join()),
    never from the fight leader's own [A]ttack/[F]lee/[R]eady/e[X]it
    Command> menu (_run_loop() reads that menu directly, char-by-char,
    with no dispatch back to the general command processor at all -- see
    combat/engine.py's _run_loop vs. join()). One player has to hold the
    fight open via the leader loop so the other is free to type lasso/cast
    each round as a bystander.
    """
    player = Player(id=_ANCHOR_NAME, name=_ANCHOR_NAME, char_class=PlayerClass.FIGHTER,
                     char_race=PlayerRace.HUMAN, gender=Gender.MALE,
                     map_level=1, map_room=1)
    player.set_flag(PlayerFlags.ADMIN)
    player.silver[PlayerMoneyTypes.IN_HAND] = 100_000
    player.hit_points = 300
    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = _ELEVATOR_COMBO
    player.combinations[CombinationTypes.ELEVATOR] = combo
    player.unsaved_changes = True

    player.inventory = Inventory(capacity=player.max_inventory_size)
    # CROSSBOW + bolts, not the STORM BOW's melee-equivalent LONG SWORD --
    # weapons.json #34 STORM BOW flatly refuses ammo ("THE STORM BOW DOES
    # NOT USE PHYSICAL AMMO!", commands/use.py), so ammo loading/depletion
    # needs its own non-STORM ranged weapon to actually demonstrate, same
    # reasoning as the Death Amulet needing to stay off the STORM BOW.
    weapon = Weapon(id_number=4, name='CROSSBOW', category=ItemCategory.WEAPON,
                     kind='standard', weapon_class='projectile',
                     stability=80, to_hit=70, price=450,
                     sound_effect=['SWISH!', 'THUNK!'])
    player.inventory.add(weapon)
    for _ in range(3):
        player.inventory.add(Item(id_number=98, name='bolts', category=ItemCategory.ITEM, price=1,
                                   flags={'rounds': 4, 'damage': 2, 'used_with': 'crossbow'}))
    # readied_weapon is session-only (player.py:1021 _SESSION_ONLY) -- doesn't
    # survive save/load, so the bot script READYs it live over the wire
    # instead of setting it here.

    ok = player.save(force=True)
    if not ok:
        print(f'FAILED to save {_ANCHOR_NAME}')
        return

    _USER_DIR.mkdir(parents=True, exist_ok=True)
    (_USER_DIR / f'login-{_ANCHOR_NAME}.json').write_text(
        json.dumps({'password': net_common.hash_password(_PASSWORD)}, indent=2)
    )
    set_password(_ANCHOR_NAME, _PASSWORD)
    print(f'Created {_ANCHOR_NAME} (Fighter/Human) in {args.dir} -- password {_PASSWORD!r}, '
          f'carrying CROSSBOW + 3x bolts (unreadied)')


def make_account() -> None:
    player = Player(id=_HERO_NAME, name=_HERO_NAME, char_class=PlayerClass.DRUID,
                     char_race=PlayerRace.ELF, gender=Gender.FEMALE,
                     map_level=1, map_room=1)
    player.set_flag(PlayerFlags.ADMIN)
    player.silver[PlayerMoneyTypes.IN_HAND] = 100_000
    player.hit_points = 300
    player.stats['Intelligence'] = 18
    player.stats['Wisdom'] = 17
    player.stats['Dexterity'] = 16
    player.stats['Strength'] = 15

    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = _ELEVATOR_COMBO
    player.combinations[CombinationTypes.ELEVATOR] = combo
    player.unsaved_changes = True

    _seed_gear(player)
    _seed_spells(player)
    _seed_allies(player)

    ok = player.save(force=True)
    if not ok:
        print(f'FAILED to save {_HERO_NAME}')
        return

    _USER_DIR.mkdir(parents=True, exist_ok=True)
    (_USER_DIR / f'login-{_HERO_NAME}.json').write_text(
        json.dumps({'password': net_common.hash_password(_PASSWORD)}, indent=2)
    )
    set_password(_HERO_NAME, _PASSWORD)
    print(f'Created {_HERO_NAME} (Druid/Elf) in {args.dir} -- password {_PASSWORD!r}, '
          f'carrying DEATH AMULET + Amulet of Life (STORM BOW bought live from the Armory), '
          f'{len(_SPELLS)} spells, {len(_ALLY_NAMES)} allies, '
          f'elevator combo {"-".join(f"{n:02}" for n in _ELEVATOR_COMBO)}')


if __name__ == '__main__':
    make_account()
    make_anchor_account()
