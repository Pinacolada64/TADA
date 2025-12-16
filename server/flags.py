import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto, Enum
from typing import Optional

# Reuse PlayerFlag from player_flag.py to avoid duplication and circular imports
from player_flag import get_flag_display_type, PlayerFlag


class PlayerFlags(StrEnum):
    """Names of flags"""
    # game states:
    ADMIN = "Administrator"
    ARCHITECT = "Architect"
    DUNGEON_MASTER = "Dungeon Master"
    # speaker on a chat channel or in an amphitheater (public chat room):
    ORATOR = "Orator"
    # guild stuff:
    GUILD_AUTODUEL = "Guild AutoDuel"
    GUILD_FOLLOW_MODE = "Guild Follow Mode"
    GUILD_MEMBER = "Guild Member"
    # option toggles:
    DEBUG_MODE = "Debug Mode"
    EXPERT_MODE = "Expert Mode"
    HOURGLASS = "Hourglass"
    MORE_PROMPT = "More Prompt"
    ROOM_DESCRIPTIONS = "Room Descriptions"
    # health:
    DISEASE = "Diseased"
    HUNGER = "Hungry"
    POISON = "Poisoned"
    THIRST = "Thirsty"
    TIRED = "Tired"
    UNCONSCIOUS = "Unconscious"
    # horse related:
    HAS_HORSE = "Has horse"
    MOUNTED = "Mounted on horse"
    # game states:
    AMULET_OF_LIFE_ENERGIZED = "Amulet of Life energized"
    COMPASS_USED = "Compass used"
    DWARF_ALIVE = "Dwarf alive"
    GAUNTLETS_WORN = "Gauntlets worn"
    RING_WORN = "Ring worn"
    SPUR_ALIVE = "SPUR alive"
    THUG_ATTACK = "Thug attack"
    WRAITH_KING_ALIVE = "Wraith King alive"
    WRAITH_MASTER = "Wraith Master"


class FlagDisplayTypes(Enum):
    """
    Different flag states should be displayed with different wording.
    Displaying "Dungeon Master: Yes" reads better than "Dungeon Master: True",
    even though that's how the flag state is represented internally.
    Similarly, "Guild Follow: Off" reads better than "Guild Follow: False"
    """
    YESNO = auto()
    ONOFF = auto()


# these are flag defaults for a new player:
new_player_default_flags = [
    # game state flags:
    (PlayerFlags.ADMIN, FlagDisplayTypes.YESNO, False),
    # can build things later:
    (PlayerFlags.ARCHITECT, FlagDisplayTypes.YESNO, False),
    # a level lower than Admin, different permissions to be determined:
    (PlayerFlags.DUNGEON_MASTER, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.ORATOR, FlagDisplayTypes.YESNO, False),
    # guild stuff:
    (PlayerFlags.GUILD_AUTODUEL, FlagDisplayTypes.ONOFF, False),
    (PlayerFlags.GUILD_FOLLOW_MODE, FlagDisplayTypes.ONOFF, False),
    (PlayerFlags.GUILD_MEMBER, FlagDisplayTypes.YESNO, False),
    # option toggles:
    (PlayerFlags.DEBUG_MODE, FlagDisplayTypes.ONOFF, True),
    (PlayerFlags.EXPERT_MODE, FlagDisplayTypes.ONOFF, False),
    (PlayerFlags.HOURGLASS, FlagDisplayTypes.ONOFF, True),
    (PlayerFlags.MORE_PROMPT, FlagDisplayTypes.ONOFF, True),
    (PlayerFlags.ROOM_DESCRIPTIONS, FlagDisplayTypes.ONOFF, True),
    # game states:
    (PlayerFlags.AMULET_OF_LIFE_ENERGIZED, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.COMPASS_USED, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.DWARF_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlags.GAUNTLETS_WORN, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.RING_WORN, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.SPUR_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlags.THUG_ATTACK, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.WRAITH_KING_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlags.WRAITH_MASTER, FlagDisplayTypes.YESNO, False),

    # health issues:
    (PlayerFlags.DISEASE, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.HUNGER, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.POISON, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.THIRST, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.TIRED, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.UNCONSCIOUS, FlagDisplayTypes.YESNO, False),

    # horse stuff:
    (PlayerFlags.HAS_HORSE, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.MOUNTED, FlagDisplayTypes.YESNO, False)
]

# TODO: flags:
@dataclass
class TutTreasure:
    examined: bool = False
    taken: bool = False



@dataclass
class Flag:
    name: str
    display_type: FlagDisplayTypes
    status: bool


# Player.set_flag() and Player.query_flag() should use PlayerFlags enum values.
# mock call would be:
# player.set_flag(PlayerFlags.ADMIN) # assumed True
# player.clear_flag(PlayerFlags.ADMIN) # assumed False
# is_admin = player.query_flag(PlayerFlags.ADMIN) # returns bool
# player.toggle_flag(PlayerFlags.ADMIN) # flips value
# player.query_flag(PlayerFlags.ADMIN) # returns bool


# --- Centralized flag helpers -------------------------------------------------
def _make_flag_from_tuple(tup):
    """Create a Flag from the new_player_default_flags tuple entry."""
    try:
        flag_enum, display_type, default_status = tup
        return Flag(name=flag_enum.value, display_type=display_type, status=bool(default_status))
    except Exception:
        return None


def ensure_player_flags(player):
    """Ensure a player object has a populated flags mapping.

    The mapping is: PlayerFlags -> Flag dataclass instance.
    If the player already has flags, return them unchanged.
    """
    if player is None:
        return {}
    try:
        existing = getattr(player, 'flags', None)
        if existing and isinstance(existing, dict) and len(existing) > 0:
            return existing
        # build defaults
        mapping = {}
        for tup in new_player_default_flags:
            f = _make_flag_from_tuple(tup)
            if f is not None:
                # find the enum used as key by matching name
                # prefer using PlayerFlags member as key
                try:
                    # reverse lookup: PlayerFlags member for this name
                    key = next((pf for pf in PlayerFlags if pf.value == f.name), None)
                except Exception:
                    key = None
                if key is None:
                    # fallback to storing by string name
                    mapping[f.name] = f
                else:
                    mapping[key] = f
        # attach to player
        try:
            player.flags = mapping
        except Exception:
            pass
        return mapping
    except Exception:
        return {}


def set_flag(player, flag: PlayerFlags):
    """Set the named flag on player to True (create it if missing).

    Use `clear_flag(player, flag)` to clear it. This keeps the API simple: callers
    without an explicit boolean parameter should use set_flag/clear_flag.
    """
    if player is None or flag is None:
        return False
    try:
        flags_map = ensure_player_flags(player)
        # Find existing Flag by enum key
        existing = flags_map.get(flag)
        if existing:
            existing.status = True
            return True
        default_entry = next((t for t in new_player_default_flags if t[0] == flag), None)
        if default_entry:
            f = _make_flag_from_tuple(default_entry)
            f.status = True
        else:
            f = Flag(name=flag.value, display_type=FlagDisplayTypes.ONOFF, status=True)
        flags_map[flag] = f
        try:
            player.flags = flags_map
        except Exception:
            pass
        return True
    except Exception:
        return False


def clear_flag(player, flag: PlayerFlags):
    """Clear (set False) the named flag on player."""
    if player is None or flag is None:
        return False
    try:
        flags_map = ensure_player_flags(player)
        existing = flags_map.get(flag)
        if existing:
            existing.status = False
            return False
        # If missing, create it with False status (so future queries are consistent)
        default_entry = next((t for t in new_player_default_flags if t[0] == flag), None)
        if default_entry:
            f = _make_flag_from_tuple(default_entry)
            f.status = False
        else:
            f = Flag(name=flag.value, display_type=FlagDisplayTypes.ONOFF, status=False)
        flags_map[flag] = f
        try:
            player.flags = flags_map
        except Exception:
            pass
        return False
    except Exception:
        return False


def toggle_flag(player, flag: PlayerFlags):
    """Toggle the named flag and return the new boolean status."""
    if player is None or flag is None:
        return False
    try:
        flags_map = ensure_player_flags(player)
        f = flags_map.get(flag)
        if f:
            f.status = not bool(f.status)
            return bool(f.status)
        # if missing, set to True
        set_flag(player, flag)
        return True
    except Exception:
        return False


def query_flag(player, flag: PlayerFlags) -> bool:
    """Return True/False for the given PlayerFlags member on the player."""
    if player is None or flag is None:
        return False
    try:
        flags_map = ensure_player_flags(player)
        f = flags_map.get(flag)
        if f:
            return bool(f.status)
        return False
    except Exception:
        return False


def serialize_flags_for_save(player) -> dict:
    """Return a JSON-serializable mapping of flag-name -> {name,status} for saving."""
    out = {}
    try:
        flags_map = ensure_player_flags(player)
        for k, v in list(flags_map.items()):
            try:
                name = v.name if hasattr(v, 'name') else (k.value if hasattr(k, 'value') else str(k))
                out[name] = {'name': name, 'status': bool(getattr(v, 'status', False))}
            except Exception:
                continue
    except Exception:
        pass
    return out

# --- end helpers -------------------------------------------------------------


if __name__ == '__main__':
    # thanks to you, volca. code has been simplified
    # set up logging level (this level or higher will output to console):
    logging.basicConfig(format='%(levelname)10s | %(funcName)20s() | %(message)s',
                        level=logging.DEBUG)
