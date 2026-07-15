"""starting_equipment.py — beginner shield/armor/weapon assignment at character creation.

Not part of original SPUR: SPUR.LOGON.S:158-159 rolls shield+armor together
with a single 50% check, and whichever passes is rated random(30) (a 0-29%
intactness). This module is a deliberate deviation, per Ryan: independent
50/50 rolls for shield and armor, a <70% intactness rating, and a starter
weapon chosen by class/race proficiency.

No standalone shield/armor proficiency table exists anywhere in the port
(only item_system.weapon_bonus() has class/race weapon affinities), so
eligibility here is a light gate grounded in existing class/race flavor
text (base_classes.py's PlayerClassText/PlayerRaceText) rather than an
invented table:
  - Wizards are "physically frail" and need their hands free to cast --
    ineligible for both shield and armor.
  - Archers need both hands to draw a bow -- ineligible for a shield only.
  - Pixies are "no taller than a human hand" -- too small for standard-scale
    gear, ineligible for both.

The starter weapon table reuses item_system.weapon_bonus()'s existing
per-class name/weapon_class affinities instead of inventing new proficiency
data -- each pick below is a weapons.json entry that already lines up with
that class's bonus condition.
"""
import random
from typing import Optional

from base_classes import PlayerClass, PlayerRace

_SHIELD_INELIGIBLE_CLASSES = {PlayerClass.WIZARD, PlayerClass.ARCHER}
_ARMOR_INELIGIBLE_CLASSES = {PlayerClass.WIZARD}
_EQUIPMENT_INELIGIBLE_RACES = {PlayerRace.PIXIE}

# weapons.json "number" -> class.  Picks line up with item_system.weapon_bonus():
_STARTER_WEAPON_BY_CLASS = {
    PlayerClass.WIZARD:   3,   # WOOD STAFF   -- "TAFF" match  (+2 hit / +1 dmg)
    PlayerClass.DRUID:    27,  # WOODEN CLUB  -- "CLUB" match  (+1 / +1)
    PlayerClass.FIGHTER:  1,   # LONG SWORD   -- flat class bonus (+2 / +1)
    PlayerClass.PALADIN:  8,   # MORNING STAR -- flat class bonus (+0 / +1)
    PlayerClass.RANGER:   5,   # SLING        -- projectile, no penalty
    PlayerClass.THIEF:    7,   # DAGGER       -- poke/jab match (+1 / +1)
    PlayerClass.ARCHER:   6,   # LONG BOW     -- " BOW" match   (+2 / +2)
    PlayerClass.ASSASSIN: 18,  # NASTY KNIFE  -- poke/jab match (+2 / +1)
    PlayerClass.KNIGHT:   43,  # SABRE        -- "ABRE" match   (+2 / +3)
}

_INTACTNESS_MIN = 10
_INTACTNESS_MAX = 69  # "<70%" per spec

# objects.json #4 "small shield" -- cheapest shield item (price 2), used as
# the beginner shield so a real, identifiable item backs player.shield's
# condition rating (needed for per-item shield_proficiency tracking; see
# player.py's active_shield_id / gain_shield_proficiency()).
STARTER_SHIELD_ITEM_NUMBER = 4


def _roll_intactness() -> int:
    return random.randint(_INTACTNESS_MIN, _INTACTNESS_MAX)


def roll_shield(char_class, char_race) -> Optional[int]:
    """Return an intactness rating (10-69) on a successful 50/50 roll for an
    eligible class/race, else None (no shield)."""
    if char_class in _SHIELD_INELIGIBLE_CLASSES or char_race in _EQUIPMENT_INELIGIBLE_RACES:
        return None
    return _roll_intactness() if random.random() < 0.5 else None


def roll_armor(char_class, char_race) -> Optional[int]:
    """Return an intactness rating (10-69) on a successful 50/50 roll for an
    eligible class/race, else None (no armor)."""
    if char_class in _ARMOR_INELIGIBLE_CLASSES or char_race in _EQUIPMENT_INELIGIBLE_RACES:
        return None
    return _roll_intactness() if random.random() < 0.5 else None


def starter_weapon_number(char_class) -> Optional[int]:
    """Return the weapons.json 'number' for this class's starter weapon."""
    return _STARTER_WEAPON_BY_CLASS.get(char_class)
