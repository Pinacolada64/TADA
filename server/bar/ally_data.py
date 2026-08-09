import collections
import json
import logging
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from base_classes import Gender, Alignment, HorseBreed, HorseColor

_ROSTER_FILE = Path('run') / 'server' / 'net' / 'ally-roster.json'


class AllyFlags(Enum):
    GOD = auto()
    GODDESS = auto()
    ELITE = auto()
    MECHANICAL = auto()
    # Can track other characters:
    TRACKING = auto()
    FIND_THINGS = auto()
    MOUNT = auto()
    BODY_BUILD = auto()
    # Allys Guild training (SPUR.MISC8.S s.armor/s.wep, skip branch):
    ARMORED = auto()
    COMBAT_TRAINED = auto()
    # Jake's Stable mount equipping (SPUR.USE.S eq.horse "@" sigil).
    # ARMORED ("$") doubles as horse armor -- same sigil, same flag either way.
    SADDLED = auto()
    # New in TADA -- no SPUR precedent (checked SPUR.USE.S's eq.horse and
    # every "saddle"/"bag" mention in the source, nothing). Gates a
    # mount's own carrying capacity (see commands/give.py's
    # _MOUNT_CAPACITY_WITH_SADDLEBAGS) -- a mount with no saddlebags
    # can't carry anything at all, unlike other allies (ally.items has
    # never had a capacity limit). Ryan's request.
    SADDLEBAGS = auto()

class AllyPosition(Enum):
    """Tactical position"""
    EMPTY = auto()
    POINT = auto()
    FLANK = auto()
    REAR = auto()


class AllyStatus(Enum):
    FREE        = auto()   # available for sale; also free spirits (not purchasable back)
    SERVANT     = auto()   # bought from Olaf; reverts to FREE if they desert
    UNCONSCIOUS = auto()   # knocked out in combat
    DEAD        = auto()   # killed in combat


# 1. Define a clear and robust data structure
@dataclass
class Ally:
    """
    :param name: name
    :param gender: gender
    :param strength: strength
    :param to_hit: to-hit probability (x10, so 4 x10 = 40)
    :param flags: AllyFlags class [optional]
    :param breed: horse breed, only meaningful when AllyFlags.MOUNT is set
        (base_classes.HorseBreed is the shared vocabulary source -- see
        that enum's docstring)
    :param color: horse coat colour, same MOUNT-only scope as breed
        (base_classes.HorseColor)
    :param description: flavor text shown by LOOK <ally> (commands/look.py's
        describe_ally()), with substitute_tokens() %-tokens for pronouns
        (e.g. "%n is ready to fight at %p side."). None for allies that
        don't have one yet -- LOOK falls back to a generic line.
    """
    from base_classes import Alignment

    # 1. Define fields in the order your data provides them, e.g.:
    # Ally("ALAN OF YOR", "m", 9, 4),
    name: str
    gender: str  # Accept the raw string 'm' or 'f' first
    strength: int
    to_hit: int
    flags: Optional[List[AllyFlags]] = field(default_factory=list)
    breed: Optional[HorseBreed] = None
    color: Optional[HorseColor] = None
    description: Optional[str] = None

    def __post_init__(self):
        """
        This special method runs after the object is created.
        It's the perfect place to transform input data.
        """
        from base_classes import Alignment, Gender
        self.status = self.AllyStatus = AllyStatus.FREE  # Enum
        self.owner: Optional[str] = None                 # player name when SERVANT
        # # in TLoS: '(' good, ')' evil
        self.alignment: Alignment = Alignment.NEUTRAL
        self.position: AllyPosition = AllyPosition.EMPTY

        # 2. Convert the gender string to the correct Gender enum
        if self.gender == 'm':
            self.gender = Gender.MALE
        elif self.gender == 'f':
            self.gender = Gender.FEMALE

        self.hit_points: int = 0
        self.items: list = []   # items given by player via GIVE (persisted, see party.py)
        # Weapon combat (TADA-only extension -- SPUR allies never carry a
        # weapons.json entry, see combat/resolution.py ally_attacks()).
        # Auto-readied by commands/give.py when the player GIVEs a Weapon.
        self.readied_weapon = None       # items.Weapon or None
        self.ammo_rounds: int = 0        # rounds currently loaded
        self.ammo_max:    int = 0        # capacity, for recovery/display
        self.ammo_damage: int = 0        # per-round damage bonus (SPUR vm), set by commands/give.py
        # 'ayf': int  # ally has a 1-ayf% chance of randomly finding sack of gold/diamond/etc.
        self.find_percentage: int = 0
        # TODO: look at Skip's branch on GitHub, it has more TRACKing stuff:
        """
        # https://github.com/Pinacolada64/TADA-old/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.MISC9.S
        # number of rooms away an ally can detect a target
        # TLOS: distance between tracker and target determined track strength.
        # target's last play date delta compared to date.today determines
        # "strength" of tracks: 1-3 days: very fresh, >3 days: weak (?)
        # https://docs.python.org/3/library/datetime.html
        """
        self.tracking_range: int = 0
        self.body_build: int = 0
        # 3. Use an f-string for safer and more readable logging
        #    Using .name on enums provides a clean string like "MALE"
        logging.debug(
            f"ALLY CREATED: name={self.name}, gender={self.gender.name}, "
            f"str={self.strength}, to_hit={self.to_hit}, flags={self.flags}, "
            f"status={self.status.name}, hp={self.hit_points}"
        )


def add_ally_item(ally: 'Ally', item, quantity: int = 1) -> 'InventoryEntry':
    """Add *item* to *ally*.items, stacking onto an existing entry with the
    same id_number instead of always appending a new one. Returns the
    entry that now holds it (the existing, incremented one, or a freshly
    appended one).

    ally.items is a plain list (not an inventory.Inventory), so unlike
    player.inventory.add() nothing was merging duplicates -- every GIVE
    of the same item type appended yet another quantity-1 entry. Found
    live: Ryan gave the same item to an ally repeatedly and ended up with
    4 separate un-stacked "cloth armor" entries in that ally's pack
    instead of one entry at quantity 4, unlike how the player's own
    inventory (or another player's, via GIVE) already displays it.
    """
    from inventory import InventoryEntry
    item_id = getattr(item, 'id_number', None)
    if item_id is not None:
        for entry in ally.items:
            if getattr(entry.item, 'id_number', None) == item_id:
                entry.quantity += quantity
                return entry
    entry = InventoryEntry(item=item, quantity=quantity)
    ally.items.append(entry)
    return entry


def find_duplicate_allies(ally_list: List[Ally]) -> List[str]:
    """
    Checks for Allies with duplicate names in a list and prints a warning.

    Args:
        ally_list: The list of Ally objects to check.

    Returns:
        A list of names that were found to be duplicates.
    """
    # Create a list of all ally names
    names = [ally.name for ally in ally_list]

    # Count the occurrences of each name
    name_counts = collections.Counter(names)

    # Filter for names that appear more than once
    duplicates = [name for name, count in name_counts.items() if count > 1]

    if duplicates:
        print("⚠️ WARNING: Duplicate allies found!")
        for name in duplicates:
            print(f"  - '{name}' appears {name_counts[name]} times.")
    else:
        print("✅ No duplicate allies found.")

    return duplicates


def load_ally_roster() -> dict:
    """Return the persisted ally ownership/stat overrides.  Empty dict if missing."""
    try:
        if _ROSTER_FILE.exists():
            return json.loads(_ROSTER_FILE.read_text())
    except Exception:
        log.exception('Failed to load ally roster')
    return {}


def save_ally_roster(allies: List['Ally']) -> None:
    """Persist ownership and mutable stats for every non-baseline ally.

    Only allies with a non-FREE status or a set owner are written; FREE allies
    with no owner and default stats are omitted so the file stays compact.
    """
    roster = {}
    for a in allies:
        if a.status != AllyStatus.FREE or a.owner:
            roster[a.name] = {
                'owner':      a.owner,
                'status':     a.status.name,
                'strength':   a.strength,
                'hit_points': a.hit_points,
            }
    _ROSTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ROSTER_FILE.write_text(json.dumps(roster, indent=2))


_ALLIES_FILE = Path(__file__).parent.parent / 'allies.json'


def load_allies() -> list:
    """Loads ally information from allies.json (name, gender, strength,
    to_hit, flags, and an optional description shown by LOOK <ally> --
    see commands/look.py's describe_ally()). Formerly a hardcoded Python
    literal list in this function; migrated to JSON so descriptions (and
    any other per-ally data) can be edited without a code change, the
    same reasoning as objects.json/weapons.json (see items.py).

    Some entries also carry a "comment" key -- Ryan's original research
    notes on who/what each ally is a reference to, restored here from the
    old hardcoded list's inline `#` comments (JSON has no comment syntax,
    so they moved into the data itself). Dev-only: not loaded onto the
    Ally object, never shown to players -- just documentation for editing
    "description" into a real bio later.
    """
    raw_list = json.loads(_ALLIES_FILE.read_text())
    ally_data = [
        Ally(
            entry['name'],
            entry['gender'],
            entry['strength'],
            entry['to_hit'],
            [AllyFlags[f] for f in entry.get('flags', [])],
            description=entry.get('description'),
        )
        for entry in raw_list
    ]
    logging.debug("servants: %i" % len(ally_data))

    # Merge persisted ownership/stat overrides from the roster file
    roster   = load_ally_roster()
    by_name  = {a.name: a for a in ally_data}
    for name, entry in roster.items():
        a = by_name.get(name)
        if a is None:
            continue
        a.owner = entry.get('owner')
        status_str = entry.get('status', 'FREE')
        if status_str in AllyStatus.__members__:
            a.status = AllyStatus[status_str]
        if 'strength' in entry:
            a.strength = entry['strength']
        if 'hit_points' in entry:
            a.hit_points = entry['hit_points']

    return ally_data


def assign_random_statuses(ally_data: List[Ally]) -> List[Ally]:
    """Iterates through a list of allies and assigns a random status."""
    status_options = list(AllyStatus)  # Convert Enum to a list once
    for ally in ally_data:
        ally.status = random.choice(status_options)
    # count how many SERVANT status allies there are:
    servant_status = len([ally for ally in ally_data if ally.status == AllyStatus.SERVANT])
    logging.debug("Servant status: %s" % servant_status)
    return ally_data


def print_allies(ally_data: list) -> None:
    """Prints a formatted list of allies, including their status."""
    # The header correctly includes "Status"
    print(
        f"## {'Name'.ljust(20)} {'Gender'.ljust(8)} {'Strength'.ljust(8)} {'To-hit %'.ljust(10)} {'Status'.ljust(12)} Flags")
    print(f"-- {'-' * 20} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 10} {'-' * 20}")

    for i, ally in enumerate(ally_data):
        name = ally.name
        gender = "Male" if ally.gender == 'm' else "Female"
        strength = ally.strength
        # Get the status's name (e.g., "FREE", "DEAD") for clean printing
        status = ally.status.name
        to_hit_str = f"{ally.to_hit * 10}%"

        if ally.flags:
            flag_str = ", ".join(f.name for f in ally.flags)
        else:
            flag_str = "None"

        # FIXED: Added the 'status' variable to the print statement
        print(
            f"{i + 1: >2} {name.ljust(20)} {gender.ljust(8)} {str(strength).rjust(8)} "
            f"{to_hit_str.rjust(8)} {status.ljust(12)} {flag_str}"
        )


if __name__ == '__main__':
    ally_list = load_allies()
    assign_random_statuses(ally_list)
    print_allies(ally_list)
    find_duplicate_allies(ally_list)
