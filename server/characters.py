import logging
from dataclasses import dataclass, field
from typing import Optional
import doctest

# TADA-specific imports:
from base_classes import (
    Alignment, Size, PlayerMoneyTypes, PlayerMoneyCategory, PlayerStat,
    PlayerClass, PlayerClassBonuses,
    PlayerRace, PlayerRaceBonuses,
)
# from server import server_lock, room_players, compass_txts, players
from tada_utilities import make_random_id

# from server.user_settings import ClientSettingsNames, ClientValues

# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/


class BaseCharacter:
    """
    Base class for all Characters, whether a Player, Monster or NPC, to hold common attributes.
    Override the class to display a different id_prefix.

    :param id_prefix: default 'C". Subclass and set to 'M' for a Monster, 'P' for a Player, etc.
    :param id_number: item number from JSON file
    :param name: Character name
    :param max_inventory: max number of items in inventory
    :param inventory: Items in inventory
    """
    def __init__(self, **kwargs) -> None:
        self.id_prefix = kwargs.get('id_prefix', "C")
        self.id_number = kwargs.get('id_number', make_random_id())
        self.name = kwargs.get('name')
        self.max_inventory = kwargs.get('max_inventory', 5)
        self.inventory = kwargs.get('inventory')

    def __str__(self):
        """
        P = Player
        M = Monster
        etc.
        """
        return f'{self.name} [{self.id_prefix}#{self.id_number}]'


@dataclass
class Pixie(BaseCharacter):
    can_fly: bool = True
    size: Size = Size.TINY
    max_inventory: int = 4


@dataclass
class Ally(BaseCharacter):
    inventory: list[str] = field(default_factory=list)  # TODO: list[Item]
    abilities: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


class Horse(BaseCharacter):
    armor: list = field(default_factory=list)
    # if Horse.has_saddlebags is True, Horse can carry additional things (via GIVE?):
    has_saddlebags: bool
    in_saddlebags: list[str] = field(default_factory=list)  # TODO: list[Item]
    has_saddle: bool
    has_lasso: bool
    """
    TODO: additional things to be implemented later:
    training: bool (I think)
    lasso: bool
    # allowed foods: mash, hay, oats, apples, sugar_cubes
    flags: 'can_fly': pegasus (male), maybe?
    """


@dataclass
class Monster(BaseCharacter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status = kwargs.get('status', 1)  # 1=alive, 0=dead?
        size: Optional[Size]
        self.strength = kwargs.get('strength', 0)
        self.to_hit = kwargs.get('to_hit', 0)
        self.special_weapon = kwargs.get('special_weapon')
        self.flags = kwargs.get('flags')
        # TODO: max_inventory: int, inventory: list, description: str, owner: Optional[None] = None
        # NOTE: alignment is in "flags": "evil", "good"
        self.id_prefix = "M"
        # TODO: the Owner is set only if the Monster joins the Player's party
        # FIXME: 'owner = Player' is unresolved reference
        self.owner = None

    def load(self, json_filename: str):
        pass

    @classmethod
    def read_monsters(cls, param):
        pass


# ---------------------------------------------------------------------------
# Starting stat generation
# ---------------------------------------------------------------------------

# Baseline before any race/class modifier.  All stats start at 10.
_BASE_STATS: dict[PlayerStat, int] = {stat: 10 for stat in PlayerStat}


def _as_dict(enum_member) -> dict[PlayerStat, int]:
    """Normalize PlayerRaceBonuses / PlayerClassBonuses values.

    Entries with a trailing comma in the Enum definition are stored as
    1-tuples; entries without are plain dicts.
    """
    v = enum_member.value
    return v[0] if isinstance(v, tuple) else v


def race_bonuses(race) -> dict[PlayerStat, int]:
    """Stat deltas for a race.  Returns {} for unknown races."""
    name = race.name if hasattr(race, 'name') else str(race).upper()
    try:
        return _as_dict(PlayerRaceBonuses[name])
    except KeyError:
        return {}


def class_bonuses(char_class) -> dict[PlayerStat, int]:
    """Stat deltas for a class.  Returns {} for unknown classes."""
    name = char_class.name if hasattr(char_class, 'name') else str(char_class).upper()
    try:
        return _as_dict(PlayerClassBonuses[name])
    except KeyError:
        return {}


def base_stats_for(race, char_class) -> dict[PlayerStat, int]:
    """Full starting stat block for a race/class combination.

    Applies race deltas first, then class deltas, on top of _BASE_STATS.
    Pure function — does not touch any Player object.
    """
    stats = dict(_BASE_STATS)
    for stat, delta in race_bonuses(race).items():
        stats[stat] = stats.get(stat, 0) + delta
    for stat, delta in class_bonuses(char_class).items():
        stats[stat] = stats.get(stat, 0) + delta
    return stats


def apply_race_class_deltas(player) -> None:
    """Add race and class stat deltas to whatever stats are already on the player.

    Used after stat rolling: the rolled values stay, and race/class adjustments
    are added on top.  Safe to call whenever race and class are both set.
    """
    stats = dict(getattr(player, 'stats', {}) or {})
    for stat, delta in race_bonuses(getattr(player, 'char_race', None)).items():
        stats[stat] = stats.get(stat, 0) + delta
    for stat, delta in class_bonuses(getattr(player, 'char_class', None)).items():
        stats[stat] = stats.get(stat, 0) + delta
    player.stats = stats


def apply_creation_bonuses(player) -> bool:
    """Set player.stats to the race/class starting values.

    Skipped if the player already has any non-zero stat (loaded from save
    or already initialised).  Returns True if applied, False if skipped.
    """
    existing = getattr(player, 'stats', {}) or {}
    if any(v != 0 for v in existing.values()):
        return False
    player.stats = base_stats_for(
        getattr(player, 'char_race',  None),
        getattr(player, 'char_class', None),
    )
    return True


# ---------------------------------------------------------------------------
# Class / race compatibility
# ---------------------------------------------------------------------------

# Race choices that don't make sense for a given class (flavor-driven, not a
# stat mechanic). Originally lived only in commands/new_player.py's
# validate_class_race_combo(); moved here so any editor (character creation,
# EditPlayer) checks the same table instead of maintaining its own copy.
_BAD_CLASS_RACE_COMBOS: dict[PlayerClass, list[PlayerRace]] = {
    PlayerClass.WIZARD:   [PlayerRace.OGRE, PlayerRace.DWARF, PlayerRace.ORC],
    PlayerClass.DRUID:    [PlayerRace.OGRE, PlayerRace.ORC],
    PlayerClass.THIEF:    [PlayerRace.ELF],
    PlayerClass.ARCHER:   [PlayerRace.OGRE, PlayerRace.GNOME, PlayerRace.HOBBIT],
    PlayerClass.ASSASSIN: [PlayerRace.GNOME, PlayerRace.ELF, PlayerRace.HOBBIT],
    PlayerClass.KNIGHT:   [PlayerRace.OGRE, PlayerRace.ORC],
}


def is_class_race_compatible(char_class, char_race) -> bool:
    """True if char_class/char_race is a sensible combination.

    True (nothing to flag) if either is None -- callers with a
    not-yet-fully-set-up character shouldn't treat that as an error.
    """
    if char_class is None or char_race is None:
        return True
    return char_race not in _BAD_CLASS_RACE_COMBOS.get(char_class, [])


# ---------------------------------------------------------------------------
# Natural alignment (from race, not class -- SPUR.MISC5.S lines 196-199)
# ---------------------------------------------------------------------------

# Original used "Bad" for Ogre/Orc, but this port's Alignment enum only has
# Good/Neutral/Evil, so "Bad" maps to EVIL. Moved here from the private copy
# in commands/stats.py so any editor (character creation, EditPlayer) shares
# the same table.
_RACE_NATURAL_ALIGNMENT: dict[str, Alignment] = {
    'Ogre':  Alignment.EVIL,
    'Orc':   Alignment.EVIL,
    'Pixie': Alignment.GOOD,
    'Elf':   Alignment.GOOD,
}


def natural_alignment_for_race(race) -> Alignment:
    """The natural alignment a given race implies (SPUR.MISC5.S:196-199).

    str(race) so both PlayerRace members and plain value-strings match;
    anything else (unset, unrecognized) is Neutral.
    """
    return _RACE_NATURAL_ALIGNMENT.get(str(race), Alignment.NEUTRAL)


def apply_natural_alignment(player) -> tuple[bool, Alignment]:
    """Recompute player.natural_alignment from their current char_race.

    Call this after char_race (or char_class, which doesn't itself affect
    the result but may prompt a recheck) changes. Mutates the player
    directly, no I/O -- mirrors apply_race_class_deltas()'s style. Returns
    (changed, new_alignment) so the caller can report whether anything
    actually changed instead of silently overwriting a player-visible value.
    """
    new_alignment = natural_alignment_for_race(getattr(player, 'char_race', None))
    old_alignment = getattr(player, 'natural_alignment', None)
    changed = new_alignment != old_alignment
    if changed:
        player.natural_alignment = new_alignment
    return changed, new_alignment


# ---------------------------------------------------------------------------
# Age / birthday
# ---------------------------------------------------------------------------

def birthday_for_age(age, month: int, day: int, today=None):
    """Build a birthday consistent with age (year = current_year - age).

    Character creation and EditPlayer used to let age and birthday drift
    out of sync -- a freely-entered birth year (EditPlayer), or the current
    year regardless of age (character creation) -- so age and birthday
    could openly contradict each other. Deriving the year here keeps them
    tied together; callers only ever collect month/day from the player.

    Falls back to Feb 28 if the derived year isn't a leap year and
    month/day is Feb 29.
    """
    from datetime import date, datetime
    today = today or date.today()
    year = today.year - int(age or 0)
    try:
        return datetime(year, month, day)
    except ValueError:
        return datetime(year, month, 28)


def parse_month(ans: str) -> Optional[int]:
    """Return 1-based month number from a typed number (1-12) or at least
    the first three letters of the month's name (case-insensitive, e.g.
    'jan', 'March', 'septem...'), else None.

    Shared by commands/new_player.py's _choose_age() birthday sub-prompt
    and commands/editplayer.py's edit_birthday() so both accept the same
    input, rather than each hand-rolling its own int()-only parsing.
    """
    import calendar
    text = ans.strip().lower()
    if not text:
        return None
    if text.isdigit():
        n = int(text)
        return n if 1 <= n <= 12 else None
    if len(text) < 3:
        return None
    for i in range(1, 13):
        if calendar.month_name[i].lower().startswith(text):
            return i
    return None


if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')

    doctest.testmod(verbose=True)

    # Use the central Player class from player.py for instantiation and testing
    from player import Player
    rulan = Player()

    print("- Adjust & show DEX score:")
    print("- Current DEX score:")
    print(rulan.show_stat(PlayerStat.DEX))
    add = 15
    print(f"- Adjust DEX to {add}:")
    rulan.adj_stat_relative(PlayerStat.DEX, adjustment=add)
    print(rulan.show_stat(PlayerStat.DEX))

    subtract = -9
    verify = add + subtract
    print(f"- Adjust DEX by {subtract}:")
    rulan.adj_stat_relative(PlayerStat.DEX, adjustment=subtract)
    print(rulan.show_stat(PlayerStat.DEX))
    # test = 5
    # print(f'{test.bit_count()}') # 2 bits set: bit 4 + bit 1

    if verify == add + subtract:
        print("* Math checks out!")
    else:
        print("* Somethin' ain't right.")

    wealth = 50_000
    print(f"\n- Set silver in hand to {wealth:,}")
    rulan.silver[PlayerMoneyTypes.IN_HAND] = wealth

    rulan.adj_silver_relative(PlayerMoneyTypes.IN_HAND, 100)
    rulan.adj_silver_relative(PlayerMoneyTypes.IN_BANK, 385)

    print(f"\n- Show money categories and values:")
    for k, category in enumerate(PlayerMoneyTypes, start=1):
        name = PlayerMoneyCategory[category].value
        amount = rulan.silver[name]  # Directly access the value using the enum member
        """
        >>> rulan.silver[PlayerMoneyTypes.IN_BAR]
        1000

        >>> PlayerMoneyCategory.IN_HAND.value, rulan.silver[PlayerMoneyTypes.IN_HAND]
        ('In hand', 50000)
        """
        print(f"{k:2>}. {name:.<10}: {amount:>9,}")

    print("\n- Show random combinations:")
    for combination_name, combination_tuple in rulan.combinations.items():
        print(f"{combination_name.value:>15}: {'-'.join(str(digit) for digit in combination_tuple)}")

    """
    # FIXME: doesn't work yet
    print("\n- Show client settings:")
    for i, client_setting in enumerate(ClientSettingsNames):
        value = ClientSettingsNames[client_setting]
        setting_name = client_setting.name.replace("_", " ").title()  # Improve readability
        print(f"{i + 1}. {setting_name}: {value}")
    """
