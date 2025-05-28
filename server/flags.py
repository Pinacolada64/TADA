import logging
from dataclasses import dataclass
from enum import StrEnum
import doctest

# TADA-specific imports:
# from characters import Player

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


class FlagDisplayTypes(StrEnum):
    """
    Different flag states should be displayed with different wording.
    Displaying "Dungeon Master: Yes" reads better than "Dungeon Master: True",
    even though that's how the flag state is represented internally.
    Similarly, "Guild Follow: Off" reads better than "Guild Follow: False"
    """
    YESNO = "Yes/No"
    ONOFF = "On/Off"


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
"""
# TODO: flags:
'tut_treasure': {'examined': False, 'taken': False}
"""


@dataclass
class Flag:
    name: str
    display_type: FlagDisplayTypes
    status: bool


if __name__ == '__main__':
    # thanks to you, volca. code has been simplified
    # set up logging level (this level or higher will output to console):
    logging.basicConfig(format='%(levelname)10s | %(funcName)20s() | %(message)s',
                        level=logging.DEBUG)

    # set up doctest
    doctest.testmod(verbose=True)
