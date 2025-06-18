import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum, IntEnum, auto


class Guild(IntEnum):
    """Guild names"""
    CIVILIAN = auto()
    FIST = auto()
    SWORD = auto()
    CLAW = auto()
    OUTLAW = auto()


class Size(IntEnum):
    """
    Monster and Player sizes. These can be compared in combat to see if a taller monster misses over a shorter
    player's head, or vice versa
    """
    SWIFT = 0
    TINY = 1
    SHORT = 2
    SMALL = 3
    MEDIUM_SIZED = 4
    MAN_SIZED = 5
    BIG = 6
    LARGE = 7
    HUGE = 8


class Alignment(StrEnum):
    """Player and Monster alignments"""
    GOOD = "Good"
    NEUTRAL = "Neutral"
    EVIL = "Evil"


@dataclass
class BaseCharacterRace:
    """Base class for all Races; subclass for e.g., Pixie"""
    name: str = None
    """
    'can_fly' can be set to True if mounted on a Pegasus, also if the SPACE SUIT is fixed;
    this lets you navigate over bodies of water without the use of a DINGHY.
    Also the HOT AIR BALLOON in 'The Land of Oz' level could allow flight.
    If CharacterRace.PIXIE, 'can_fly' is also True.
    """
    can_fly: bool = False
    size: Size = Size.MAN_SIZED
    carrying_capacity: int = 10
    natural_alignment: Alignment = Alignment.NEUTRAL  # (depends on race)
    honor: int = 1_000  # TODO: look this up, I think that equates to Saintly for a Knight
    # current_alignment is based on Honor score (the lower it is, the more evil the character is)


class CombinationTypes(StrEnum):
    CASTLE = "Castle"
    ELEVATOR = "Elevator"  # Get this from the SCRAP OF PAPER item in the dungeon
    LOCKER = "Locker"


class PlayerMoneyTypes(StrEnum):
    # this is the dict element to reference money amounts
    IN_HAND = "IN_HAND"
    IN_BANK = "IN_BANK"
    IN_BAR = "IN_BAR"


class PlayerMoneyCategory(StrEnum):
    # this refers to Player.silver{PlayerMoneyTypes.Enum} printable names
    IN_HAND = "In hand"
    IN_BANK = "In bank"
    IN_BAR = "In bar"


class WeaponClass(StrEnum):
    ENERGY = "Energy"  # 1
    BASH_SLASH = "Bash/Slash"  # 2
    POKE_JAB = "Poke/Jab"  # 3
    CLASS_4 = "X"  # class 4 was unassigned in the original code
    POLE_RANGED = "Pole/Ranged"  # 5
    CLASS_6 = "X"  # class 6 was unassigned in the original code
    CLASS_7 = "X"  # class 7 was unassigned in the original code
    PROJECTILE = "Projectile"  # 8
    PROXIMITY = "Proximity"  # 9


class Gender(StrEnum):
    MALE = "Male"
    FEMALE = "Female"


class PlayerClass(StrEnum):
    """
    In the original Apple code, this was the variable 'pc' which could range from 1-9.
    The class number is in a comment.
    """
    # this player class will be referred to as PlayerClass.MAGIC_USER even if the player's gender is female, making her a witch:
    # FIXME: how do I do that? Python Player class can't be... inherited? from that i can see?
    #  TODO: "Wizard" if player.gender == Gender.MALE else 'Witch'
    WIZARD = "Wizard"  # 1
    DRUID = "Druid"  # 2
    FIGHTER = "Fighter"  # 3
    PALADIN = "Paladin"  # 4
    RANGER = "Ranger"  # 5
    THIEF = "Thief"  # 6
    ARCHER = "Archer"  # 7
    ASSASSIN = "Assassin"  # 8
    KNIGHT = "Knight"  # 9


@dataclass
class PlayerRace(StrEnum):
    """
    In the original Apple code, this was the variable 'pr' which could range from 1-9.
    The race number is in a comment.
    """
    """
    branch master/spur-code/LOGON.S:
    1) Human    4) Elf        7) Dwarf
    2) Ogre     5) Hobbit     8) Orc
    3) Pixie    6) Gnome      9) Half-Elf

    branch Skip/spur-code/SPUR.NEW.S:
    new4
     print \'Please Choose a Race:

    1) Human    4) Elf        7) Dwarf
    2) Ogre     5) Hobbit     8) Orc
    3) Pixie    6) Gnome      9) Half-Elf
    """
    HUMAN = "Human"  # 1
    OGRE = "Ogre"  # 2
    PIXIE = "Pixie"  # 3
    ELF = "Elf"  # 4
    HOBBIT = "Hobbit"  # 5
    # Apparently Halfling was a dream; could be added later
    # HALFLING = "Halfling"  # 6
    GNOME = "Gnome"  # 6
    DWARF = 'Dwarf'  # 7
    ORC = 'Orc'  # 8
    HALF_ELF = 'Half-Elf'  # 9


class PlayerStat(StrEnum):
    CHR = "Charisma"
    CON = "Constitution"
    DEX = "Dexterity"
    INT = "Intelligence"
    STR = "Strength"
    WIS = "Wisdom"
    EGY = "Energy"


@dataclass
class Room(object):
    number: int
    name: str
    desc: str
    exits: dict = field(default_factory=lambda: {})  # {n e s w rc rt}
    monster: int = 0
    item: int = 0
    weapon: int = 0
    food: int = 0
    alignment: str = "neutral"  # default unless set to another guild

    def __str__(self):
        return f'#{self.number} {self.name}\n' \
               f'{self.desc}\n{self.exits}'

    def exits_txt(self, debug: bool):
        """
        Display exits in a comma-delimited list.
        :param debug: display room #s if True
        :return: joined list of exits
        """
        # connection/transport names, index by (connection, transport)
        # rc = 1: Up     rt != 0: Room #
        # rc = 2: Down   rt == 0: Shoppe
        extra_txts = {(1, 0): 'Up to Shoppe',
                      (2, 0): 'Down to Shoppe'}
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:
                exit_txts.append(compass_txts[k])
        room_connection = self.exits.get('rc', 0)
        room_transport = self.exits.get('rt', 0)
        exit_extra = extra_txts.get((room_connection, room_transport))
        if exit_extra:  # is not None:
            exit_txts.append(exit_extra)
        # example: level 1, room 20
        if room_connection == 1 and room_transport != 0:
            exit_txts.append(f"Up to #{room_transport}" if debug else "Up")
        if room_connection == 2 and room_transport != 0:
            exit_txts.append(f"Down to #{room_transport}" if debug else "Down")
        return ", ".join(exit_txts)


class Map(object):
    def __init__(self):
        """
        Define the level map layout
        """
        self.rooms = {}

    def read_map(self, filename: str):
        """
        Data format on C64:
        * Room number        (rm)
        * Location name      (lo$)
        * items: monster, item, weapon, food
        * exits: north, east, south, west,
          RC (room command: 1=move up,
                            2=move down),
          RT (Room exit transports you to:
                 <>0: room #, or 0=Shoppe)
        https://github.com/Pinacolada64/TADA/blob/master/text/s_t_level-1-data.txt
        """
        try:
            with open(filename) as jsonF:
                map_data = json.load(jsonF)
                logging.debug("read_map: JSON data read")
                for room_data in map_data['rooms']:
                    room = Room(**room_data)
                    self.rooms[room.number] = room
                    logging.debug('%i: %s' % (room.number, room.name))
        except FileNotFoundError:
            logging.error(">>> read_map: File not found: '%s'" % filename)


compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West', 'u': 'Up', 'd': 'Down'}
