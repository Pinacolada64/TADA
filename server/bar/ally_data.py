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


# ---------------------------------------------------------------------------
# Canonical stat ceilings
#
# SPUR's sysop editor (SPUR.SYSOP.S ed.a.str / ed.a.hit) let an operator set
# ally strength 1-20 and to-hit 1-9 (a percent-to-hit x10, so 9 == 90%).
# Fat Olaf's hire adds a flat +5 on top of the catalog value (SPUR.BAR.S
# buy: `a1 = x2 + 5`), so 25 is the highest strength a legitimately-obtained
# ally can reach. SPUR has no separate ally hit-point stat at all -- combat
# drains `a1` (strength) directly -- so the port's TADA-only
# `hit_points = strength * HP_PER_STRENGTH` is bounded by the same ceiling.
#
# These are the single source of truth: bar/fat_olaf.py, street/allies_guild.py,
# commands/editplayer.py, spells/charm.py and party.py all clamp against them,
# and load_allies() / Party.from_json() re-clamp on load so a save that
# predates the caps (or was hand-edited) self-heals on next login.
ALLY_HP_PER_STRENGTH = 2
ALLY_STRENGTH_MAX    = 25
ALLY_TO_HIT_MIN      = 0    # SPUR's range is 1-9; 0 == "unused" (mounts sit here)
ALLY_TO_HIT_MAX      = 9
ALLY_HP_MAX          = ALLY_STRENGTH_MAX * ALLY_HP_PER_STRENGTH   # 50


def clamp_ally_stats(ally: 'Ally') -> bool:
    """Clamp *ally*'s strength / to_hit / hit_points into the canonical
    ranges above, in place. Returns True if anything actually changed."""
    changed = False
    s = max(1, min(int(ally.strength or 1), ALLY_STRENGTH_MAX))
    if s != ally.strength:
        ally.strength = s
        changed = True
    t = max(ALLY_TO_HIT_MIN, min(int(ally.to_hit or 0), ALLY_TO_HIT_MAX))
    if t != ally.to_hit:
        ally.to_hit = t
        changed = True
    hp = max(0, min(int(ally.hit_points or 0), ALLY_HP_MAX))
    if hp != (ally.hit_points or 0):
        ally.hit_points = hp
        changed = True
    return changed


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
    # A MOUNT that bolted during an ambush (ally_events/horse_bolt.py) --
    # still owned by the player (owner stays set), just not with them right
    # now. bolt_room_no/bolt_map_level (below) say where it ended up.
    # Distinct from deserting (SERVANT -> FREE): a bolted mount can't be
    # re-purchased by anyone else and comes back via MOUNT once the player
    # finds it, rather than being lost for good.
    BOLTED      = auto()


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
        # A GIVEn weapon lands in self.items; the player chooses when the
        # ally actually wields it via READY (commands/ready.py's
        # _toggle_ally_weapon) -- alpha testers disliked auto-readying.
        self.readied_weapon = None       # items.Weapon or None
        self.ammo_rounds: int = 0        # rounds currently loaded
        self.ammo_max:    int = 0        # capacity, for recovery/display
        self.ammo_damage: int = 0        # per-round damage bonus (SPUR vm), set by commands/give.py
        # Armor/shield, same idea as readied_weapon above -- auto-worn by
        # commands/give.py when the player GIVEs an armor- or shield-type
        # Item (item_system.ItemType.ARMOR/SHIELD). Display-only for now
        # (no ally damage-mitigation model yet, see commands/stats.py's
        # long-parked "[Worn: None]" comment) -- just stops GIVE from
        # saying a worn piece was merely "tucked away".
        self.readied_armor  = None       # items.Item (type=ARMOR) or None
        self.readied_shield = None       # items.Item (type=SHIELD) or None
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
        # Only meaningful while status == AllyStatus.BOLTED (MOUNT-only,
        # see ally_events/horse_bolt.py) -- where the horse ended up after
        # bolting, so MOUNT can re-attach it once the player walks in.
        self.bolt_room_no: Optional[int] = None
        self.bolt_map_level: Optional[int] = None
        # True if the bolt walk was cut short at a water room's edge
        # (ally_events/horse_bolt.py never deposits a horse in the water
        # itself) -- lets the catch message read "at the water's edge"
        # instead of the generic "nearby".
        self.bolt_at_water: bool = False
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


def base_ally_strength(name: str) -> Optional[int]:
    """Return *name*'s pristine strength straight from allies.json, ignoring
    any roster or session overrides. SPUR's Fat Olaf MAINTAIN (SPUR.BAR.S
    `maint`) only restores a combat-drained ally back up to this catalog
    value -- it's a repair, never a growth mechanic -- so bar/fat_olaf.py
    needs the un-inflated number to know when to stop."""
    try:
        for entry in json.loads(_ALLIES_FILE.read_text()):
            if entry.get('name') == name:
                return entry.get('strength')
    except Exception:
        logging.exception('base_ally_strength: failed to read %s', _ALLIES_FILE)
    return None


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
        # A roster written before the stat caps existed (or hand-edited)
        # can carry a wildly inflated strength/HP -- pull it back into range
        # so the ally self-heals on this load rather than needing a manual
        # editplayer pass.
        if clamp_ally_stats(a):
            logging.info('load_allies: clamped out-of-range stats for %s', name)

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
