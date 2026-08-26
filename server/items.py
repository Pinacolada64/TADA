import json
import logging
from dataclasses import dataclass, field
from enum import auto
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any, Dict, Tuple

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

# TADA-specific imports:
if TYPE_CHECKING:
    from base_classes import WeaponClass
    from player import Player

from flags import PlayerFlags


class ItemCategory(StrEnum):
    ITEM      = "Item"
    FOOD      = "Food"
    DRINK     = "Drink"
    WEAPON    = "Weapon"
    SPELL     = "Spell"
    ARMOR     = "Armor"
    CONTAINER = "Container"


class IDNumber:
    """Save from having to manually specify an ID#"""
    def __init__(self, value: int):
        self.value = value
        logging.debug(" init: id=%i", self.value)

    def increment(self):
        logging.debug("enter: id=%i", self.value)
        self.value += 1
        logging.debug(" exit: id=%i", self.value)
        return self.value


@dataclass
class BoobyTrap:
    room: int
    level: int
    combination: str  # letter A-I
    buried_by: str  # Player  # so we can determine if they're DIGging up their own or someone else's stuff


@dataclass
class BaseItem:
    """Base class for all items"""
    id_prefix: str = "I"
    id_number: int = 0
    name: str = None
    description: str = None
    location: int = 0
    owner = None  # could be a Player instance if a monster joins the party
    # Accept either list or dict for flags (some data files use a dict)
    flags: Any = field(default_factory=list)
    category: Optional[ItemCategory] = None


class Item(BaseItem):
    def __init__(self, **kwargs):
        # item_id: int, name: str, description: str, owner: Optional[str],  id_prefix: str = "I"):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.id_prefix = "I"
        if not hasattr(self, 'category'):
            self.category = ItemCategory.ITEM
        # capacity > 0 makes this a container (bag of holding, etc.)
        if not hasattr(self, 'capacity'):
            self.capacity: int = 0
        # BaseItem dataclass __repr__ always reads self.flags; guarantee it exists.
        if not hasattr(self, 'flags'):
            self.flags = []

    @staticmethod
    def read(filename: str) -> dict | None:
        try:
            with open(filename) as json_file:
                data = json.load(json_file)
                logging.info("Read JSON data '%s'" % filename)
                # objects.json historically has a top-level dict with key 'items': [...]
                if isinstance(data, dict) and 'items' in data:
                    return data['items']
                # otherwise return the top-level structure (could already be a list)
                return data
        except FileNotFoundError:
            logging.error(">>> %s not found" % filename)
            return None

    """
    # TODO: re-implement this method in a way that works with the current Player class
    def __str__(self, player: Player):
        print(f"From {player.name}'s perspective:")
        print(f"\t{player.query_flag(PlayerFlags.DEBUG_MODE)=}, {player.query_flag(PlayerFlags.DUNGEON_MASTER)=}, {self.owner=}")
        if player and (player.has_item(self) or player.query_flag(PlayerFlags.DEBUG_MODE) or player.query_flag(PlayerFlags.DEBUG_MODE) or player == self.owner):
            return f"{self.name} [{self.prefix}#{self.item_id}]"
        else:
            return f"{self.name}"
    """

class Weapon(BaseItem):
    def __init__(self, **kwargs):
        # Lazy import to avoid circular dependency
        from base_classes import WeaponClass
        # BaseItem is a dataclass — pass only the fields it declares.
        _base_fields = {'id_prefix', 'id_number', 'name', 'description', 'location', 'flags', 'category'}
        super().__init__(**{k: v for k, v in kwargs.items() if k in _base_fields})
        self.id_number: int = kwargs.get('id_number', 0)
        self.id_prefix: str = "W"
        self.location: int = kwargs.get('location', 0)
        self.name: str = kwargs.get('name', '')
        self.category = kwargs.get('category', ItemCategory.WEAPON)
        self.kind: Optional[str] = kwargs.get('kind')
        self.sound_effect: Tuple[str, str] = kwargs.get('sound_effect', ('', ''))
        self.stability: int = kwargs.get('stability', 0)
        self.to_hit: int = kwargs.get('to_hit', 0)
        self.price: int = kwargs.get('price', 0)
        self.weapon_class: WeaponClass = kwargs.get('weapon_class')

    @staticmethod
    def read_weapons(filename: str) -> Optional[Dict[str, Any]]:
        try:
            with open(filename) as json_file:
                weapons = json.load(json_file)
                logging.info("Read JSON data '%s'" % filename)
                return weapons
        except FileNotFoundError:
            logging.error(">>> File not found: '%s'" % filename)
            return None

    # Alias for code ported from item_system.py's old Weapon dataclass,
    # which used 'number' where this class uses 'id_number'.
    @property
    def number(self) -> int:
        return self.id_number

    @property
    def sfx(self) -> Tuple[str, str]:
        """Return (miss_sfx, hit_sfx) for this weapon."""
        from item_system import weapon_sfx
        return weapon_sfx(self)

    @property
    def is_storm_weapon(self) -> bool:
        return "STORM" in (self.name or '').upper()

    @property
    def is_magic(self) -> bool:
        return str(self.kind or '').lower() == "magic"

    @property
    def needs_ammo(self) -> bool:
        # weapon_class may be a base_classes.WeaponClass (StrEnum) or a raw
        # string from weapons.json -- both compare equal to "projectile".
        return str(self.weapon_class or '').lower() == "projectile"


def _weapons_by_number(weapons_data: Optional[list]) -> Dict[int, dict]:
    """Index raw weapons.json-shaped dicts by their 'number' key."""
    return {w['number']: w for w in (weapons_data or [])
            if isinstance(w, dict) and 'number' in w}


def build_weapon_from_raw(raw: dict, *, id_number: int, location: int = 0) -> 'Weapon':
    """Construct a fully-populated Weapon from one weapons.json record.

    Mirrors shoppe/armory.py's buy-path construction exactly, so a weapon
    built here carries the same real stats (sound_effect/stability/to_hit/
    weapon_class/price) as one bought from the armory.
    """
    return Weapon(
        id_number    = id_number,
        name         = raw.get('name', ''),
        location     = raw.get('location', location),
        kind         = raw.get('kind'),
        sound_effect = tuple(raw.get('sound_effect', ('', ''))),
        stability    = raw.get('stability', 0),
        to_hit       = raw.get('to_hit', 0),
        price        = raw.get('price', 0),
        weapon_class = raw.get('weapon_class'),
    )


def load_weapons(path: str) -> list['Weapon']:
    """
    Load weapons.json and return a list of Weapon instances.

    Ported from item_system.py's old load_weapons(), which built the
    now-removed item_system.Weapon dataclass; this builds real
    items.Weapon instances via build_weapon_from_raw() instead, so
    every field (sound_effect/stability/to_hit/weapon_class/price)
    matches what shoppe/armory.py's buy path constructs.

    Usage:
        weapons = load_weapons("weapons.json")
    """
    raw_list = Weapon.read_weapons(path)
    if raw_list is None:
        return []
    weapons = []
    for i, raw in enumerate(raw_list):
        id_number = raw.get('number', i)
        weapons.append(build_weapon_from_raw(raw, id_number=id_number))
    logging.debug("load_weapons: loaded %d weapons from '%s'", len(weapons), path)
    return weapons


async def show_weapon(ctx, weapon: 'Weapon') -> None:
    """
    Display full stats for a single weapon.

    Async — sends output via ctx.send().
    Mirrors the stat display in SPUR.WEAPON.S `rdy.wep` section.

    Usage:None
        await show_weapon(ctx, sword)
    """
    miss_sfx, hit_sfx = weapon.sfx
    kind_label = str(weapon.kind or '').capitalize()
    wc = weapon.weapon_class
    class_label = (wc.value if hasattr(wc, 'value') else str(wc or '')).capitalize()

    lines = [
        f"  #{weapon.number}  {weapon.name}  [{kind_label}]",
        f"  Class    : {class_label}",
        f"  Stability: {weapon.stability}%   (ease of use)",
        f"  To-hit   : {weapon.to_hit}%",
        f"  Price    : {weapon.price} silver",
        f"  On miss  : {miss_sfx}    On hit: {hit_sfx}",
    ]
    if weapon.needs_ammo:
        lines.append("  * Projectile weapon — requires ammunition")
    if weapon.is_storm_weapon:
        lines.append("  *** STORM WEAPON — handle with care! ***")
    if weapon.flags:
        lines.append(f"  Flags    : {', '.join(weapon.flags)}")

    await ctx.send(*lines)


async def list_weapons(ctx, weapon_list: list['Weapon']) -> None:
    """
    Display a numbered list of weapons (e.g. the player's inventory).

    Async — sends output via ctx.send().

    Usage:
        await list_weapons(ctx, player_weapons)
    """
    if not weapon_list:
        await ctx.send("  (No weapons.)")
        return

    lines = ["  Weapons:"]
    for i, w in enumerate(weapon_list, start=1):
        miss_sfx, hit_sfx = w.sfx
        wc = w.weapon_class
        wc_str = wc.value if hasattr(wc, 'value') else str(wc or '')
        lines.append(
            f"  {i}) {w.name:<22} "
            f"[{wc_str:<10}]  "
            f"Stab:{w.stability}%  Hit:{w.to_hit}%  "
            f"Price:{w.price}"
        )
    await ctx.send(*lines)


async def ready_weapon(ctx, player, weapons_data: list['Weapon']) -> Optional['Weapon']:
    """
    Interactive 'READY a weapon' flow — mirrors SPUR.WEAPON.S `rdy.wep`.

    Prompts the player to choose a weapon from their inventory,
    validates the choice, displays the weapon stats and any
    class/race bonuses, then returns the chosen Weapon (or None
    if the player cancelled).

    Async — uses ctx.prompt() and ctx.send().

    NOTE: commands/ready.py is the actual READY command used in-game
    (STORM/Excalibur/Death Amulet special-casing, battle-exp badges,
    etc.) — this is the earlier, simpler flow it superseded. Kept
    (moved here from item_system.py rather than deleted) as source
    reference/for any caller that wants the plain version without the
    special-case handling.

    Usage:
        readied = await ready_weapon(ctx, player, all_weapons)
        if readied:
            player.readied_weapon = readied
    """
    # Filter to weapons this player is carrying (location == 0)
    carried = [w for w in weapons_data if w.location == 0]

    if not carried:
        await ctx.send("You have no weapons to ready.")
        return None

    await list_weapons(ctx, carried)

    while True:
        raw = await ctx.prompt(f"Ready which weapon number? (or {ctx.player.client_settings.return_key} to cancel) ")
        if not raw or raw.strip() == "":
            return None

        raw = raw.strip()
        if " " in raw:
            await ctx.send("Please enter a single number, no spaces.")
            continue

        if not raw.isdigit():
            await ctx.send("Please enter a number.")
            continue

        choice = int(raw)
        if choice < 1 or choice > len(carried):
            await ctx.send(f"You don't have weapon #{choice}. Pick 1–{len(carried)}.")
            continue

        chosen = carried[choice - 1]

        # Class/race bonus display
        player_class = getattr(player, "player_class", "Fighter")
        player_race  = getattr(player, "player_race",  "Human")

        # Normalise enum values to plain strings if needed
        if hasattr(player_class, "value"):
            player_class = player_class.value
        if hasattr(player_race, "value"):
            player_race = player_race.value

        from item_system import weapon_bonus
        skill_b, dmg_b = weapon_bonus(chosen, player_class, player_race)

        await show_weapon(ctx, chosen)

        bonus_lines = []
        if skill_b != 0:
            sign = "+" if skill_b > 0 else ""
            bonus_lines.append(f"  Skill bonus  : {sign}{skill_b} (your class/race)")
        if dmg_b != 0:
            sign = "+" if dmg_b > 0 else ""
            bonus_lines.append(f"  Damage bonus : {sign}{dmg_b} (your class/race)")
        if not bonus_lines:
            bonus_lines.append("  No special class/race bonus for this weapon.")

        await ctx.send(*bonus_lines)
        await ctx.send(f"{chosen.name} readied.")
        return chosen


def resolve_weapon(id_number: int, name: str, weapons_data: Optional[list],
                    *, flags=None, kind=None, location: int = 0) -> 'BaseItem':
    """Look up id_number in weapons_data and rebuild a real Weapon.

    Guards the lookup with a case-insensitive name match -- item numbering
    is only unique within its own category (weapons/items/rations each
    start back at 1, same rationale as inventory.py's _rations_by_number())
    -- so a bare id_number match could misidentify an unrelated record.
    Falls back to a bare Item (never None) when no confident match exists,
    so a carried weapon a caller can't resolve still round-trips safely --
    `kind` is threaded through to that fallback so it matches exactly what
    the pre-resolution bare-Item construction used to carry.
    """
    raw = _weapons_by_number(weapons_data).get(id_number)
    if raw and str(raw.get('name', '')).lower() == (name or '').lower():
        weapon = build_weapon_from_raw(raw, id_number=id_number, location=location)
        if flags:
            weapon.flags = flags
        return weapon
    return Item(id_number=id_number, name=name, category=ItemCategory.WEAPON,
                flags=flags or [], kind=kind)


class Rations(BaseItem):
    def __init__(self, number, name, kind, price, **flags):
        self.number = number
        self.id_number = number  # alias so inventory.remove() can match by id
        self.name = name
        self.kind = kind  # food, drink, cursed
        self.price = price
        # Without this, category stays BaseItem's default of None, which
        # made a freshly-bought ration (category=None) fail to stack onto
        # an already-carried one reloaded from a save file (category=
        # ItemCategory.ITEM, backfilled by inventory.py's from_json() --
        # see its comment on why item_kind takes priority there too)
        # since Inventory.add()'s stacking match requires both id_number
        # AND category to agree (found live: Railbender buying a second
        # loaf of bread never stacked onto the one from a prior session).
        if kind == 'food':
            self.category = ItemCategory.FOOD
        elif kind == 'drink':
            self.category = ItemCategory.DRINK
        # this field is optional:
        if flags is not None:
            self.flags = flags

    def __str__(self):
        # TODO: only display '[<kind> #<number>]' if Player's DEBUG or ADMIN flags are True
        if self.kind == "food":
            return f"{self.name} [Food #{self.number}]"
        elif self.kind == "drink":
            return f"{self.name} [Drink #{self.number}]"
        elif self.kind == "cursed":
            return f"{self.name} [Cursed #{self.number}]"
        else:
            # unknown kind:
            return f"{self.name} [Unknown #{self.number}]"

    @staticmethod
    def read_rations(filename: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(filename) as json_file:
                rations = json.load(json_file)
                logging.info("Read JSON data '%s'" % filename)
                return rations
        except FileNotFoundError:
            logging.error(">>> File not found: %s" % filename)
            return None


@dataclass
class Spell(BaseItem):
    """A spell that can be cast, with a finite number of charges.

    Fields ported from SPUR.MISC3.S spell records (q$, q2$, q3, q4):
      cast_chance     — probability of success, 0-100 (q3 * 10 in SPUR display)
      effect_type     — single letter: S=Str W=Wis D=Dex C=Con E=Egy I=Int
                        T=Transfer P=Player-HP M=Monster L=LevelDown U=LevelUp
                        R=Shop(teleport) G=SPUR(teleport) A=Aura
      effect_magnitude — numeric modifier applied on success (q2$ second char)
      aux_param        — extra parameter used by aura/time spells (q4)
    """
    charges: int = 0
    max_charges: int = 0
    cast_chance: int = 0       # 0-100 percent
    effect_type: str = ''
    effect_magnitude: int = 0
    aux_param: int = 0

    def __post_init__(self):
        self.id_prefix = "S"
        self.category  = ItemCategory.SPELL

    def use(self) -> bool:
        """Consume one charge. Returns False if already depleted."""
        if self.charges <= 0:
            return False
        self.charges -= 1
        return True

    @property
    def is_depleted(self) -> bool:
        return self.charges <= 0

    def __str__(self):
        charge_pct = int(self.charges / self.max_charges * 100) if self.max_charges else 0
        return (
            f"{self.name} "
            f"[{self.charges}/{self.max_charges} charges ({charge_pct}%)"
            f" | cast: {self.cast_chance}%]"
        )


# Lazy cache for _spells_by_number() -- unlike weapons.json/objects.json/
# rations.json (per-server files loaded once at startup onto ctx.server),
# spell data is a static, hardcoded Python list (shoppe/wizard.py's
# SPELLS), so no ctx.server plumbing is needed to resolve it -- just an
# in-process import, cached the same way inventory.py's
# _rations_by_number() caches rations.json.
_SPELLS_BY_NUMBER: Dict[int, dict] | None = None


def _spells_by_number() -> Dict[int, dict]:
    global _SPELLS_BY_NUMBER
    if _SPELLS_BY_NUMBER is None:
        from shoppe.wizard import SPELLS
        _SPELLS_BY_NUMBER = {s['number']: s for s in SPELLS if 'number' in s}
    return _SPELLS_BY_NUMBER


def build_spell_from_raw(raw: dict, *, id_number: int,
                          charges: int = 1, max_charges: int = 1) -> 'Spell':
    """Construct a fully-populated Spell from one shoppe/wizard.py SPELLS
    record. Mirrors shoppe/wizard.py's teaching-path construction exactly."""
    return Spell(
        id_number        = id_number,
        name             = raw.get('name', ''),
        cast_chance      = raw.get('cast_chance', 0),
        effect_type      = raw.get('effect', ''),
        effect_magnitude = raw.get('magnitude', 0),
        charges          = charges,
        max_charges      = max_charges,
    )


def resolve_spell(id_number: int, name: str, *, flags=None,
                   charges: int = 1, max_charges: int = 1) -> 'BaseItem':
    """Look up id_number in shoppe/wizard.py's SPELLS and rebuild a real
    Spell -- same case-insensitive name-match guard as resolve_weapon(),
    since numbering is only unique within its own category. Falls back to
    a bare Item (never None) when no confident match exists."""
    raw = _spells_by_number().get(id_number)
    if raw and str(raw.get('name', '')).lower() == (name or '').lower():
        spell = build_spell_from_raw(raw, id_number=id_number,
                                      charges=charges, max_charges=max_charges)
        if flags:
            spell.flags = flags
        return spell
    return Item(id_number=id_number, name=name, category=ItemCategory.SPELL,
                flags=flags or [])


if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    # from inventory import Inventory, InventoryEntry
    from player import Player

    # Example usage
    ylana = Player()

    rulan = Player()
    rulan.set_flag(PlayerFlags.DEBUG_MODE)

    sword = Weapon(id_number=101, name="Sword", description="A sharp, steel sword.")
    hammer = Weapon(id_number=102, name="Hammer", description="A metal claw on a stick.")

    rulan.inventory.add(sword)
    ylana.inventory.add(hammer)

    print(rulan.look_at(sword))  # Output: "Sword [W#1]" (because Rulan owns the item AND Debug Mode is on)
    print(rulan.look_at(hammer))  # Output: "Hammer" (because Rulan does not own the item)
