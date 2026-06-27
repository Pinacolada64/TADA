"""
item_system.py
==============
Item and weapon system for the TADA server.

Translated from the original ACOS/BASIC source (SPUR.WEAPON.S, SPUR-data/)
into Python, following the ctx pattern used across this codebase.

All interactive functions are async and accept a ctx (GameContext or
TerminalContext). Pure data helpers are sync with no I/O.

Public async API (all take ctx as first arg):
    show_weapon(ctx, weapon)          -- display one weapon's stats
    list_weapons(ctx, weapon_list)    -- numbered list of weapons player carries
    ready_weapon(ctx, player, weapons_data)  -- let player choose a weapon to ready
    show_item(ctx, item)              -- display one item's details
    list_items(ctx, item_list)        -- numbered list of items player carries

Public sync helpers (no ctx, no I/O):
    load_weapons(path)        -> list[dict]
    load_items(path)          -> list[dict]
    weapon_bonus(weapon, player_class, player_race) -> tuple[int, int]
    weapon_sfx(weapon)        -> tuple[str, str]   (miss_sfx, hit_sfx)
    active_item_flags(item)   -> list[str]
"""

import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums — match base_classes.py / WeaponClass already in the codebase
# ---------------------------------------------------------------------------

class WeaponKind(StrEnum):
    MAGIC    = "magic"
    STANDARD = "standard"
    CURSED   = "cursed"


class WeaponClass(StrEnum):
    ENERGY     = "energy"       # 1
    BASH_SLASH = "bash/slash"   # 2
    POKE_JAB   = "poke/jab"     # 3
    POLE_RANGE = "pole/range"   # 5
    PROJECTILE = "projectile"   # 8  (+10% surprise, needs ammo)
    PROXIMITY  = "proximity"    # 9
    UNKNOWN    = "unknown"      # catch-all for unassigned classes


class ItemType(StrEnum):
    ARMOR    = "armor"
    BOOK     = "book"
    COMPASS  = "compass"
    CURSED   = "cursed"
    SHIELD   = "shield"
    TREASURE = "treasure"


# ---------------------------------------------------------------------------
# Sound effects table
# Matches SPUR.WEAPON.S variable vr = val(zz$)*6+1
# Index 0 = sfx class 0, index 1 = class 1, etc.
# ---------------------------------------------------------------------------

WEAPON_SFX: list[tuple[str, str]] = [
    ("CRACK!",    "CRACK!"),    # 0 — default / unknown
    ("SWISH!",    "SLASH!"),    # 1 — Energy
    ("SWISH!",    "BASH!"),     # 2 — Bash/Slash
    ("SWISH!",    "THUNK!"),    # 3 — Poke/Jab
    ("SWISH!",    "STAB!"),     # 4 — (unassigned)
    ("KA-PWING!", "BLAM!"),     # 5 — Pole/Range (bullet ricochet)
    ("FIZZLE!",   "BOOOM!"),    # 6 — (unassigned)
    ("SIZZLE!",   "SIZZLE!"),   # 7 — Heat damage (FLAME THROWER, PHASER, etc.)
    ("SWISH!",    "CRASH!"),    # 8 — Projectile
    ("BRRRT!",    "BRRRT!"),    # 9 — Proximity
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Weapon:
    """
    Represents one weapon loaded from weapons.json.

    Fields mirror the JSON written by convert_weapon_data.py.
    """
    number:       int
    name:         str
    kind:         WeaponKind            = WeaponKind.STANDARD
    weapon_class: WeaponClass           = WeaponClass.UNKNOWN
    location:     int                   = 2        # 0=on player, 1=in room, 2=in shoppe
    stability:    int                   = 50       # ease-of-use %
    to_hit:       int                   = 50       # chance of causing damage %
    price:        int                   = 0
    sound_effect: Optional[list[str]]   = None     # [miss_sfx, hit_sfx]
    flags:        Optional[list[str]]   = None     # reserved for future expansion

    def __str__(self) -> str:
        return f"#{self.number} {self.name}"

    @property
    def sfx(self) -> tuple[str, str]:
        """Return (miss_sfx, hit_sfx) for this weapon."""
        return weapon_sfx(self)

    @property
    def is_storm_weapon(self) -> bool:
        return "STORM" in self.name.upper()

    @property
    def is_magic(self) -> bool:
        return self.kind == WeaponKind.MAGIC

    @property
    def needs_ammo(self) -> bool:
        return self.weapon_class == WeaponClass.PROJECTILE


@dataclass
class Item:
    """
    Represents one item (non-weapon object) loaded from objects.json.

    Fields mirror the JSON written by convert_object_data.py.
    """
    number:   int
    name:     str
    type:     ItemType
    price:    int                    = 0
    flags:    Optional[dict]         = None   # e.g. {"rounds": 6, "damage": 2, "used_with": "357"}

    def __str__(self) -> str:
        return f"#{self.number} {self.name}"

    @property
    def is_ammo_carrier(self) -> bool:
        """True if this item carries ammunition (has rounds/damage/used_with flags)."""
        return (self.flags is not None and
                "rounds" in self.flags and
                "used_with" in self.flags)


# ---------------------------------------------------------------------------
# Pure / sync helpers — no I/O, no ctx
# ---------------------------------------------------------------------------

def load_weapons(path: str) -> list[Weapon]:
    """
    Load weapons.json and return a list of Weapon instances.

    Usage:
        weapons = load_weapons("weapons.json")
    """
    try:
        with open(path) as f:
            raw: list[dict] = json.load(f)
        weapons = []
        for d in raw:
            # Normalise weapon_class string → WeaponClass enum value
            wc_str = d.get("weapon_class", "unknown")
            try:
                d["weapon_class"] = WeaponClass(wc_str)
            except ValueError:
                d["weapon_class"] = WeaponClass.UNKNOWN

            # Normalise kind string → WeaponKind enum value
            kind_str = d.get("kind", "standard")
            try:
                d["kind"] = WeaponKind(kind_str)
            except ValueError:
                d["kind"] = WeaponKind.STANDARD

            weapons.append(Weapon(**d))
        logging.debug("load_weapons: loaded %d weapons from '%s'", len(weapons), path)
        return weapons
    except FileNotFoundError:
        logging.error("load_weapons: file not found: '%s'", path)
        return []


def load_items(path: str) -> list[Item]:
    """
    Load objects.json and return a list of Item instances.

    The JSON has a top-level {"items": [...]} wrapper (see convert_object_data.py).

    Usage:
        items = load_items("objects.json")
    """
    try:
        with open(path) as f:
            raw = json.load(f)
        # Handle both {"items": [...]} and plain [...]
        records: list[dict] = raw.get("items", raw) if isinstance(raw, dict) else raw
        items = []
        for d in records:
            type_str = d.get("type", "treasure")
            try:
                d["type"] = ItemType(type_str)
            except ValueError:
                d["type"] = ItemType.TREASURE
            items.append(Item(**d))
        logging.debug("load_items: loaded %d items from '%s'", len(items), path)
        return items
    except FileNotFoundError:
        logging.error("load_items: file not found: '%s'", path)
        return []


def weapon_sfx(weapon: Weapon) -> tuple[str, str]:
    """
    Return (miss_sfx, hit_sfx) strings for a weapon.

    Uses the weapon's sound_effect field if present, otherwise
    falls back to the WEAPON_SFX table based on weapon_class.
    Mirrors the original ACOS logic: vr = val(zz$)*6+1.
    """
    if weapon.sound_effect and len(weapon.sound_effect) == 2:
        return tuple(weapon.sound_effect)  # type: ignore[return-value]

    # Fall back to class-based table
    class_to_index: dict[WeaponClass, int] = {
        WeaponClass.ENERGY:     1,
        WeaponClass.BASH_SLASH: 2,
        WeaponClass.POKE_JAB:   3,
        WeaponClass.POLE_RANGE: 5,
        WeaponClass.PROJECTILE: 8,
        WeaponClass.PROXIMITY:  9,
    }
    idx = class_to_index.get(weapon.weapon_class, 0)
    return WEAPON_SFX[idx]


def weapon_bonus(weapon: Weapon, player_class: str, player_race: str) -> tuple[int, int]:
    """
    Calculate the (skill_bonus, damage_bonus) for a player using this weapon.

    Translated directly from the `special` subroutine in SPUR.WEAPON.S.
    Returns (yz, yx) where:
        yz = extra skill (ease-of-use bonus)
        yx = extra damage bonus

    player_class: one of the PlayerClass enum string values from base_classes.py
    player_race:  one of the PlayerRace enum string values from base_classes.py

    Usage:
        skill_b, dmg_b = weapon_bonus(sword, "Fighter", "Human")
    """
    yz, yx = 0, 0
    # Use last 4 chars of name for suffix matching — mirrors ACOS `n$=right$(n$,4)`
    n = weapon.name.upper()
    n4 = n[-4:] if len(n) >= 4 else n.ljust(4)
    wc = weapon.weapon_class

    # --- Player class bonuses (pc in original) ---
    pc = player_class.upper()

    if pc == "WIZARD":
        if any(s in n for s in ["BALL", "TAFF", "BOLT"]):
            yz, yx = 2, 1
        else:
            yx = -2
            if any(s in n4 for s in ["GGER", "NIFE"]):
                yx = 1

    elif pc == "DRUID":
        if any(s in n for s in ["ABRE", "LING", "ELIN", "CLUB", "PEAR",
                                  "TAFF", "TAKE", " BOW", "ILUM"]):
            yz, yx = 1, 1

    elif pc == "FIGHTER":
        yz, yx = 2, 1
        if wc == WeaponClass.PROJECTILE:
            yz, yx = 0, -1
        if wc == WeaponClass.ENERGY:
            yx += 1

    elif pc == "PALADIN":
        yx = 1
        if wc == WeaponClass.PROJECTILE:
            yx = -1

    elif pc == "RANGER":
        if any(s in n for s in ["SBOW", "WORD", "ABRE"]):
            yz, yx = 1, 1
        if wc == WeaponClass.POLE_RANGE:
            yz, yx = -1, -1

    elif pc == "THIEF":
        if wc == WeaponClass.POKE_JAB:
            yz, yx = 1, 1
        else:
            yx = -1

    elif pc == "ARCHER":
        if any(s in n for s in ["SBOW", " BOW"]):
            yz, yx = 2, 2
        if wc in (WeaponClass.BASH_SLASH, WeaponClass.POLE_RANGE):
            yz, yx = -1, -2

    elif pc == "ASSASSIN":
        if wc == WeaponClass.POKE_JAB:
            yz, yx = 2, 1
        if any(s in n for s in ["SBOW", " BOW", "LING"]):
            yz, yx = -1, -1

    elif pc == "KNIGHT":
        if any(s in n for s in ["WORD", "ANCE", "ABRE"]):
            yz, yx = 2, 3
        if "IBUR" in n:          # EXCALIBUR
            yz, yx = 4, 4
        if wc == WeaponClass.PROJECTILE:
            yz, yx = 0, -1

    # --- Player race bonuses (pr in original) ---
    pr = player_race.upper()

    if pr == "HUMAN":
        if any(s in n for s in ["GNUM", "OWER", "POON", " GUN", "SKET",
                                  "NNON", " UZI", "MITE", "ASER", "IFLE"]):
            yx += 1
    elif pr == "OGRE":
        if any(s in n for s in ["CLUB", "MMER", "KLES"]):
            yz += 3
    elif pr == "PIXIE":
        if any(s in n4 for s in ["NIFE", "GGER"]):
            yz += 1; yx += 2
    elif pr == "ELF":
        if " BOW" in n:
            yz += 1; yx += 1
    elif pr == "HOBBIT":
        if "LING" in n:
            yz += 1; yx += 2
        if wc == WeaponClass.POLE_RANGE:
            yz += 1; yx += 2
    elif pr == "GNOME":
        if any(s in n for s in ["GGER", "NIFE", "TTLE"]):
            yz += 1; yx += 2
    elif pr == "DWARF":
        if any(s in n for s in ["EAXE", "KAXE", "CHET", "SBOW", " AXE"]):
            yz += 1; yx += 1
    elif pr == "ORC":
        if any(s in n4 for s in ["NIFE", "GGER", " UZI", "KLES"]):
            yz += 2
        if any(s in n for s in ["GNUM", "OWER", "POON", " GUN", "SKET", "NNON", " UZI"]):
            yx += 2
    elif pr == "HALF-ELF":
        if any(s in n for s in ["SBOW", " BOW", "WORD"]):
            yx += 1

    # PHASER minimum skill bonus
    if "PHASER" in n and yz < 1:
        yz = 1

    logging.debug(
        "weapon_bonus: '%s' for %s/%s -> skill_bonus=%d, dmg_bonus=%d",
        weapon.name, player_class, player_race, yz, yx
    )
    return yz, yx


def active_item_flags(item: Item) -> list[str]:
    """
    Return a human-readable list of active flags for an item.

    Usage:
        flags = active_item_flags(bandolier)
        # e.g. ["6 rounds", "2 damage", "used with: 357"]
    """
    if not item.flags:
        return []
    result = []
    if "rounds" in item.flags:
        result.append(f"{item.flags['rounds']} rounds")
    if "damage" in item.flags:
        result.append(f"{item.flags['damage']} damage per shot")
    if "used_with" in item.flags:
        result.append(f"used with: {item.flags['used_with']}")
    return result


# ---------------------------------------------------------------------------
# Async / ctx-aware display functions
# ---------------------------------------------------------------------------

async def show_weapon(ctx, weapon: Weapon) -> None:
    """
    Display full stats for a single weapon.

    Async — sends output via ctx.send().
    Mirrors the stat display in SPUR.WEAPON.S `rdy.wep` section.

    Usage:
        await show_weapon(ctx, sword)
    """
    miss_sfx, hit_sfx = weapon.sfx
    kind_label = weapon.kind.value.capitalize()
    class_label = weapon.weapon_class.value.capitalize()

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


async def list_weapons(ctx, weapon_list: list[Weapon]) -> None:
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
        lines.append(
            f"  {i}) {w.name:<22} "
            f"[{w.weapon_class.value:<10}]  "
            f"Stab:{w.stability}%  Hit:{w.to_hit}%  "
            f"Price:{w.price}"
        )
    await ctx.send(*lines)


async def ready_weapon(ctx, player, weapons_data: list[Weapon]) -> Optional[Weapon]:
    """
    Interactive 'READY a weapon' flow — mirrors SPUR.WEAPON.S `rdy.wep`.

    Prompts the player to choose a weapon from their inventory,
    validates the choice, displays the weapon stats and any
    class/race bonuses, then returns the chosen Weapon (or None
    if the player cancelled).

    Async — uses ctx.prompt() and ctx.send().

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
        raw = await ctx.prompt(f"Ready which weapon number? (or {ctx.player.return_key} to cancel) ")
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
        await ctx.send(f"{chosen.name} READIED.")
        return chosen


async def show_item(ctx, item: Item) -> None:
    """
    Display details for a single non-weapon item.

    Async — sends output via ctx.send().

    Usage:
        await show_item(ctx, compass)
    """
    lines = [
        f"  #{item.number}  {item.name}  [{item.type.value.capitalize()}]",
        f"  Price: {item.price} silver",
    ]
    flags = active_item_flags(item)
    if flags:
        lines.append(f"  Info : {', '.join(flags)}")
    await ctx.send(*lines)


async def list_items(ctx, item_list: list[Item]) -> None:
    """
    Display a numbered list of items (e.g. the player's inventory).

    Async — sends output via ctx.send().

    Usage:
        await list_items(ctx, player_items)
    """
    if not item_list:
        await ctx.send("  (No items.)")
        return

    lines = ["  Items:"]
    for i, item in enumerate(item_list, start=1):
        flags = active_item_flags(item)
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"  {i}) {item.name:<28} "
            f"[{item.type.value:<10}]  "
            f"Price:{item.price}"
            f"{flag_str}"
        )
    await ctx.send(*lines)


# ---------------------------------------------------------------------------
# Quick local test — run with: python item_system.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    from dataclasses import dataclass as dc

    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)8s | %(funcName)20s() | %(message)s")

    # --- Minimal TerminalContext stand-in for quick testing ---
    @dc
    class _FakeSettings:
        screen_columns: int = 80
        screen_rows:    int = 24

    class _FakePlayer:
        name           = "Rulan"
        player_class   = "Fighter"
        player_race    = "Human"
        client_settings = _FakeSettings()
        return_key:     str = "Return"

    class _FakeCtx:
        player = _FakePlayer()

        async def send(self, *lines):
            for line in lines:
                print(line)

        async def prompt(self, prompt_text: str) -> str:
            return input(prompt_text)

    async def _demo():
        ctx = _FakeCtx()

        # Load data
        weapons = load_weapons("weapons.json")
        items   = load_items("objects.json")

        if not weapons:
            print("No weapons loaded — make sure weapons.json is in the same directory.")
            return
        if not items:
            print("No items loaded — make sure objects.json is in the same directory.")
            return

        # Show first 3 weapons
        await ctx.send("=== First 5 weapons ===")
        for w in weapons[:5]:
            await show_weapon(ctx, w)
            await ctx.send("")

        # Show first 3 items
        await ctx.send("=== First 5 items ===")
        for item in items[:5]:
            await show_item(ctx, item)
            await ctx.send("")

        # Simulate carrying weapon #1 and #2
        weapons[0].location = 0
        weapons[1].location = 0
        await ctx.send("=== Weapon list (carried) ===")
        await list_weapons(ctx, [w for w in weapons if w.location == 0])

        # Interactive ready — comment out if running non-interactively
        await ready_weapon(ctx, ctx.player, weapons)

    asyncio.run(_demo())
