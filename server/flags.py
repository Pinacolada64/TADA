import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import doctest
from typing import Optional


class ClientSettings(str, Enum):
    NAME = "name"
    ROWS = "rows"
    COLUMNS = "columns"
    RETURN_KEY = "Return key"
    TRANSLATION = "Character translation"
    # colors for [bracket reader] text highlighting on C64/128:
    TEXT_COLOR = "Text color"
    HIGHLIGHT_COLOR = "Highlight color"
    BACKGROUND = "Background"
    BORDER = "border"


@dataclass
class ClientValues(int, Enum):
    name: str
    rows: int
    columns: int
    return_key: str
    translation: str
    # '1' or "white", possibly:
    text_color: int | str
    background: int | str
    border: int | str

    """
    class ClientCommodore(BaseClient):
        def __init__(self):
            self.name = "name"
            self.rows = 25
            self.columns = 40
            self.translation = TranslationType.PETSCII
            self.return_key = KeyName.RETURN | KeyName.ENTER
    """


class Gender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"


class PlayerClass(str, Enum):
    """
    In the original Apple code, this was the variable 'pc' which could range from 1-9.
    The class number is in a comment.
    """
    #  TODO: if player.gender == Gender.MALE else 'Witch'
    WIZARD = "Wizard" # 1
    DRUID = "Druid"   # 2
    FIGHTER = "Fighter"  # 3
    PALADIN = "Paladin"  # 4
    RANGER = "Ranger"  # 5
    THIEF = "Thief"  # 6
    ARCHER = "Archer"  # 7
    ASSASSIN = "Assassin"  # 8
    KNIGHT = "Knight"  # 9


@dataclass
class PlayerRace(str, Enum):
    """
    In the original Apple code, this was the variable 'pr' which could range from 1-9.
    The race number is in a comment.
    """
    HUMAN = "Human"  # 1
    OGRE = "Ogre"  # 2
    GNOME = "Gnome"  # 3
    ELF = "Elf"  # 4
    HOBBIT = "Hobbit"  # 5
    HALFLING = "Halfling"  # 6
    DWARF = 'Dwarf'  # 7
    ORC = 'Orc'  # 8
    HALF_ELF = 'Half-Elf'  # 9


class PlayerFlags(str, Enum):
    """Names of flags"""
    ADMIN = "Administrator"
    ARCHITECT = "Architect"
    DUNGEON_MASTER = "Dungeon Master"
    # guild stuff:
    GUILD_AUTODUEL = "Guild AutoDuel"
    GUILD_FOLLOW_MODE = "Guild Follow Mode"
    GUILD_MEMBER = "Guild Member"
    # speaker on a chat channel or in an amphitheater (public chat room):
    ORATOR = "Orator"
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


def longest_flag_name() -> int:
    """
    Determine length of the longest PlayerFlagName string, so the maximum
    number of ellipses to display (including some padding) can be printed
    by the calling routine; e.g.:

    item_one......: foo
    item_two......: bar
    item_three....: baz
    """
    return len(max([x for x in PlayerFlags], key=len)) + 4


class PlayerMoneyTypes(str, Enum):
    # this is the dict element to reference money amounts
    """
    in_bank: may be cleared on character death (TODO: look in TLOS source)
    in_bar: should be preserved after character's death (TODO: same)
    use Character.set_silver(PlayerMoneyTypes.<kind>, value)
    """
    """
    Silver is a more reasonable default currency than gold -- most people in the Middle Ages didn't have gold.

    The Florentine florin was a gold coin struck from 1252 to 1533 with no significant change in its design or 
    metal content standard during that time. - Wikipedia

    The shilling is a historical coin, and the name of a unit of modern currencies formerly used in the United 
    Kingdom, Australia, New Zealand, other British Commonwealth countries and Ireland, where they were generally 
    equivalent to 12 pence or one-twentieth of a pound before being phased out during the 1960s and 1970s. - Wikipedia

    TODO: Also possibly introduce platinum, electrum, copper pieces.
    """
    IN_HAND = "IN_HAND"
    IN_BANK = "IN_BANK"
    IN_BAR = "IN_BAR"


class PlayerMoneyCategory(str, Enum):
    # this refers to Player.silver{PlayerMoneyTypes.Enum} printable names
    IN_HAND = "In hand"
    IN_BANK = "In bank"
    IN_BAR = "In bar"


class CombinationTypes(str, Enum):
    CASTLE = "Castle"
    ELEVATOR = "Elevator"  # Get this from SCRAP OF PAPER item in dungeon
    LOCKER = "Locker"


class PlayerStat(str, Enum):
    CHR = "Charisma"
    CON = "Constitution"
    DEX = "Dexterity"
    EGY = "Energy"
    INT = "Intelligence"
    STR = "Strength"
    WIS = "Wisdom"


@dataclass
class FlagDisplayTypes(str, Enum):
    """
    Different flag states should be displayed with different wording.
    Displaying "Dungeon Master: Yes" reads better than "Dungeon Master: True",
    even though that's how the flag state is represented internally.
    Similarly, "Guild Follow: Off" reads better than "Guild Follow: False"
    """
    YESNO: str = "Yes/No"
    TRUEFALSE: str = "true/false"
    ONOFF: str = "on/off"


player_flag_data = [
    (PlayerFlags.ADMIN, FlagDisplayTypes.YESNO, False),
    # can build things later:
    (PlayerFlags.ARCHITECT, FlagDisplayTypes.YESNO, False),
    # a level lower than Admin, different permissions to be determined:
    (PlayerFlags.DUNGEON_MASTER, FlagDisplayTypes.YESNO, False),
    # guild stuff:
    (PlayerFlags.GUILD_AUTODUEL, FlagDisplayTypes.ONOFF, False),
    (PlayerFlags.GUILD_FOLLOW_MODE, FlagDisplayTypes.ONOFF, False),
    (PlayerFlags.GUILD_MEMBER, FlagDisplayTypes.YESNO, False),
    # option toggles:
    (PlayerFlags.DEBUG_MODE, FlagDisplayTypes.ONOFF, True),
    (PlayerFlags.EXPERT_MODE, FlagDisplayTypes.ONOFF, False),
    (PlayerFlags.HOURGLASS, FlagDisplayTypes.ONOFF, True),
    (PlayerFlags.ORATOR, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.ROOM_DESCRIPTIONS, FlagDisplayTypes.ONOFF, True),
    (PlayerFlags.UNCONSCIOUS, FlagDisplayTypes.YESNO, False),
    # game states:
    (PlayerFlags.AMULET_OF_LIFE_ENERGIZED, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.COMPASS_USED, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.DWARF_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlags.GAUNTLETS_WORN, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.RING_WORN, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.SPUR_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlags.THUG_ATTACK, FlagDisplayTypes.YESNO, False),
    (PlayerFlags.WRAITH_KING_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlags.WRAITH_MASTER, FlagDisplayTypes.YESNO, True),
    ]
"""
# TODO: flags:
'tut_treasure': {'examined': False, 'taken': False}
"""


@dataclass
class Flag(object):
    name: str
    display_type: FlagDisplayTypes
    status: bool


@dataclass
class Size(int, Enum):
    TINY = 1
    SHORT = 2
    SMALL = 3
    MEDIUM_SIZED = 4
    MAN_SIZED = 5
    LARGE = 6
    HUGE = 7


@dataclass
class BaseCharacterClass(object):
    name: str
    """
    'can_fly' can be set to True if mounted on a Pegasus, also if the SPACE SUIT is fixed;
    this lets you navigate over bodies of water without the use of a DINGHY.
    Also the HOT AIR BALLOON in 'The Land of Oz' level could allow flight
    """
    can_fly: False
    size: Size.MAN_SIZED
    carrying_capacity: 10
    natural_alignment: str  # FIXME: [good | neutral | evil] (depends on race)
    honor: 1_000  # TODO: look this up, I think that equates to Saintly for a Knight
    # current_alignment is based on Honor score (the lower it is, the more evil the character is)

@dataclass
class Pixie(BaseCharacterClass):
    can_fly: True
    size: Size.TINY
    carrying_capacity: 4


@dataclass
class Player(object):
    # TODO: make some of these stats part of a generic Character base class
    name: str = None
    birthday: datetime = datetime.today()  # age is derived from datetime.now - birthday
    gender: Gender = Gender.MALE  # no misogyny intended
    hit_points: int = 0
    experience: int = 0

    # map stats:
    map_level: int = 1 # cl = current level
    room: int = 1  # cr = current room
    # total moves made over the course of the character's life:
    moves_made: int = 0
    # tracks how many moves made during the game session to calculate experience points awarded at quit:
    moves_today: int = 0

    character_class: PlayerClass = None
    character_race: PlayerRace = None

    # the lower the Honor score, the more evil the character has become
    # I think 1,000 honor points is equivalent to a Saintly Knight
    honor: int = 1_000

    # https://www.reddit.com/r/learnpython/comments/1gzmlqv/comment/lyxnpxc/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button

    # Wizard Glow stuff:
    # None if inactive, or non-magic user
    # != 0 is number of rounds left, decrement every turn
    wizard_glow: Optional[int] = None

    """
    Things you can only do once per day (file_formats.txt):
    'pr'    has PRAYed once
    'pr2'   can PRAY twice per day (only if char_class is Druid)
    # TODO: make these Enums, finish this list
    """
    once_per_day: list[str] = field(default_factory=list)

    # Copy list of Flag defaults from PlayerFlag enum on Player instantiation:
    flags: dict[PlayerFlags, Flag] = field(default_factory=lambda: {i[0]: Flag(*i) for i in player_flag_data})
    # creates a new stats dict for each Player, zero all stats:
    stat: dict[PlayerStat, int] = field(default_factory=lambda: {i: 0 for i in PlayerStat})
    # same with silver FIXME: (set to 1_000 for testing purposes):
    # TODO: money types may be expanded to platinum, electrum in future
    silver: dict[PlayerMoneyTypes, int] = field(default_factory=lambda: {i: 1_000 for i in PlayerMoneyTypes})

    # generate a dict of 3 {<combination_type>, tuple(three random digits ranging from 0-99)}:
    combinations: dict[CombinationTypes, tuple] = field(
        default_factory=lambda: {
            combination_type: (random.randrange(99) for _ in range(3))
            for combination_type in CombinationTypes
        }
    )
    # FIXME: this is broken
    """
    client_settings: dict[ClientSettings, int | str] = field(
        default_factory=lambda: {
            client_option: {k: v for k, v in ClientValues}
            for client_option in ClientSettings
        }
    )
    """
    def adjust_silver(self, kind: PlayerMoneyTypes, adjustment: int):
        try:
            current_total = self.silver[kind]
            adjusted_total = current_total + adjustment
            silver_kind = PlayerMoneyCategory[kind.name]
            logging.debug("kind: %s, adjustment: %i, total: %i" % (silver_kind, adjustment,
                                                                                  adjusted_total))
            self.silver[kind] = adjusted_total
        except IndexError:
            logging.debug("%s does not exist" % kind)

    def get_flag(self, name: PlayerFlags) -> Flag:
        """
        Given a PlayerFlagName Enum, return the Flag object
        :param name: name of flag
        :return: Flag object
        """
        try:
            logging.debug("%s" % self.flags.get(name))
            return self.flags.get(name)
        except IndexError:
            logging.error("get_flag: no flag %s" % self.flags.get(name))

    def set_flag(self, flag: PlayerFlags) -> None:
        """
        # FIXME: fix this
        Directly set the flag status to True.

        :param flag: PlayerFlag to set
        :return: None
        """
        try:
            logging.debug("setting flag %s to True" % flag.name)
            temp = self.get_flag(flag)
            self.put_flag(flag, status=True, display_type=temp.display_type)
        except KeyError:
            logging.error("set_flag: flag %s not found" % flag.name)

    def clear_flag(self, flag: PlayerFlags) -> None:
        """
        # FIXME: fix this
        Directly clear the flag status to False.

        :param flag: PlayerFlag to clear
        :return: None
        """
        try:
            logging.debug("clearing flag %s to False" % flag.name)
            temp = self.get_flag(flag)
            self.put_flag(flag, status=False, display_type=temp.display_type)
        except KeyError:
            logging.error("clear_flag: flag %s not found" % flag.name)

    def show_flag(self, flag: PlayerFlags) -> str:
        """
        Display the flag name, ":", and its display_name status.
        :param flag: Flag name to display
        :return: str
        """
        """
        >>> test_player = Player(name="test")

        >>> print(test_player.show_flag(PlayerFlagName.UNCONSCIOUS))
        Unconscious: No
        """
        try:
            """
            >>> print(PlayerFlagName.UNCONSCIOUS.value)
            'Unconscious'
            """
            flag_name = flag.value
            temp = self.get_flag(flag)
            display_type, status = temp.display_type, temp.status
            logging.debug("flag_name=%s, display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            return f"{flag_name}: {result}"
        except KeyError:
            logging.warning("show_flag: unknown flag: %s" % flag.name)

    def show_flag_line_item(self, flag: PlayerFlags, leading_num: Optional[int]) -> str:
        """
        Display the flag status based on its display_type string.
        The flag is listed prefixed with leading_number, "...:" and the status.

        :param flag: PlayerFlag name to display
        :param leading_num: used with dot_leader, int prefixes the flag display with this number, None suppresses
         the number
        :return: str
        """
        """
        >>> test_player = Player(name="test")

        >>> print(test_player.show_flag_line_item(PlayerFlagName.UNCONSCIOUS, leading_num=1))
         1. Unconscious...............: No
        """
        try:
            """
            >>> print(PlayerFlagName.UNCONSCIOUS.value)
            'Unconscious'
            """
            max_width = longest_flag_name()
            logging.debug("%s, "
                          "leading_num: %s, "
                          "max_width: %i" % (flag, leading_num, max_width))
            temp = self.get_flag(flag)
            flag_name, display_type, status = temp.name.value, temp.display_type, temp.status
            logging.debug("flag_name=%s, "
                          "display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            # None is used here after building a menu of flag settings, the menu will number the items:
            number = f"{leading_num:>2}. " if isinstance(leading_num, int) else ""
            # return f"{leading_num:>2}. {flag_name:.<{max_width}}: {result}"
            return f"{number}{flag_name:.<{max_width}}: {result}"
        except KeyError:
            logging.warning("unknown flag: %s" % flag.name)

    def show_flag_status(self, flag: PlayerFlags) -> str:
        """
        Show a flag's status.
        :param flag: PlayerFlagName to display the status of
        :return: Appropriate string for flag DisplayType
        """
        """
        >>> rulan = Player()

        >>> rulan.show_flag_status(PlayerFlagName.UNCONSCIOUS)
        'No'
        """
        temp = self.flags[flag]
        if temp.display_type is FlagDisplayTypes.YESNO:
            result = "Yes" if temp.status else "No"
        elif temp.display_type is FlagDisplayTypes.ONOFF:
            result = "On" if temp.status else "Off"
        elif temp.display_type is FlagDisplayTypes.TRUEFALSE:
            result = "True" if temp.status else "False"
        else:
            logging.error("invalid type %s for flag %s" % (temp.display_type, temp.name))
            result = "<<error>>"
        return result

    def toggle_flag(self, flag: PlayerFlags, verbose=False):
        """
        Toggle the status of a flag. If verbose=True, tell about it (like when a player
        toggles an option on or off)
        :param flag: Flag to toggle
        :param verbose: True=tell that the flag is being toggled
        :return: None
        """
        try:
            result = self.get_flag(flag)
            logging.debug("Flag: %s before toggle: %s" % (flag.value, result.status))
            result.status = not result.status
            logging.debug("Flag: %s after toggle: %s" % (flag.value, result.status))
            self.put_flag(flag, result.display_type, result.status)
            if verbose:
                # FIXME: I'm going to let this stand even though "UNCONSCIOUS are off"
                #  will never be displayed directly except maybe in a player editor program...
                indefinite_article = "are" if flag.name.endswith("S") else "is"
                print(f"{flag.value} {indefinite_article} now {self.show_flag_status(flag)}.")
        except KeyError:
            logging.warning("toggle_flag: Can't toggle unknown flag: %s" % flag.name)

    def put_flag(self, name: PlayerFlags, display_type: FlagDisplayTypes, status: bool):
        # FIXME: seems like put_flag should know the display_type of the PlayerFlags object and
        #  not need to be specified in the function call
        logging.debug("%s put as %s" % (name, status))
        self.flags[name] = Flag(name, display_type, status)

    def query_flag(self, flag: PlayerFlags) -> bool:
        result = self.get_flag(flag)
        # returned Flag object, return the status (True/False) to caller:
        return result.status

    def show_stat(self, stat_name: PlayerStat) -> str:
        logging.debug(f"show_stat: %s" % stat_name.value)
        x = self.get_stat(stat_name)
        return f"{stat_name.value}: {x}"

    def adjust_stat(self, stat_name: PlayerStat, adjustment):
        current = self.get_stat(stat_name)
        new = current + adjustment
        logging.debug("current: %s: %i, adjusted: %i" % (stat_name.name, current, new))
        self.put_stat(stat_name, new)

    def get_stat(self, stat_name: PlayerStat) -> int:
        for key, value in self.stat.items():
            if stat_name.value == key:
                logging.debug("get %s: %i" % (stat_name.value, value))
                return value

    def put_stat(self, stat_name: PlayerStat, value) -> None:
        logging.debug("put %s: %i" % (stat_name.value, value))
        self.stat[stat_name] = value


def flag_editor(player: Player):
    print("- Toggling an indexed flag:")
    while True:
        max_options = len(player_flag_data)
        for k, v in enumerate(player.flags, start=1):
            print(player.show_flag_line_item(flag=v, leading_num=k))
        option = input(f"1-{max_options}, [Q]uit: ").lower()
        try:
            if option[0] == 'q':
                print("Done.")
                break
            value = int(option)
            if 0 < value < max_options + 1:
                # look up the flag index in player_flag_data:
                # value-1 accounts for lists being 0-indexed
                # TODO: toggle_flag_by_index() function?
                logging.debug("value: %i" % value)
                player.toggle_flag(player_flag_data[value - 1][0], verbose=True)
            else:
                raise ValueError
        except ValueError:
            print(f"Please enter a number 1-{max_options}.")


if __name__ == '__main__':
    # thanks to you, volca. code has been simplified
    # set up logging level (this level or higher will output to console):
    # set up logging level:
    logging.basicConfig(format='%(levelname)10s | %(funcName)20s() | %(message)s',
                        level=logging.DEBUG)

    # set up doctest
    doctest.testmod(verbose=True)

    # instantiate player:
    rulan = Player()
    print(f"- Show Admin flag object:")
    print(f"{rulan.get_flag(PlayerFlags.ADMIN)}")

    print(f"- show_flag 'Unconscious':")
    print(f"{rulan.show_flag(PlayerFlags.UNCONSCIOUS)}")

    print("- Show all flags:")
    for i, flag in enumerate(rulan.flags, start=1):
        print(rulan.show_flag_line_item(flag=flag, leading_num=i))

    print("- Toggle 'Unconscious' flag, verbose=True:")
    rulan.toggle_flag(PlayerFlags.UNCONSCIOUS, verbose=True)

    print("- Toggle 'Room Descriptions' flag, verbose=False:")
    room_desc_flag = PlayerFlags.ROOM_DESCRIPTIONS
    rulan.toggle_flag(room_desc_flag, verbose=False)

    print("- Toggle 'Orator' flag, verbose=True:")
    rulan.toggle_flag(PlayerFlags.ORATOR, verbose=True)

    print("- Set 'Expert Mode' flag to True:")
    rulan.set_flag(PlayerFlags.EXPERT_MODE)

    print("- Different text for result of query 'Room Descriptions' flag:")
    print("Shazam [True]" if rulan.query_flag(room_desc_flag) else "Bazinga [False]")

    print("- Show stats object:")
    print(rulan.stat)
    """
    # this worked before show_stat() was written:
    for key, value in rulan.stat.items():
        print(f"{key.value}: {value}")
    """
    print("- Show all stats:")
    for i in rulan.stat:
        print(rulan.show_stat(i))

    print("- Adjust & show DEX score:")
    print("- Current DEX score:")
    print(rulan.show_stat(PlayerStat.DEX))
    add = 15
    print(f"- Adjust DEX to {add}:")
    rulan.adjust_stat(PlayerStat.DEX, adjustment=add)
    print(rulan.show_stat(PlayerStat.DEX))

    subtract = -9
    verify = add + subtract
    print(f"- Adjust DEX by {subtract}:")
    rulan.adjust_stat(PlayerStat.DEX, adjustment=subtract)
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

    rulan.adjust_silver(PlayerMoneyTypes.IN_HAND, 100)
    rulan.adjust_silver(PlayerMoneyTypes.IN_BANK, 385)

    print(f"\n- Show money categories and values:")
    for k, element_name in enumerate(PlayerMoneyTypes, start=1):
        name = PlayerMoneyCategory[element_name].value
        amount = rulan.silver[element_name]  # Directly access the value using the enum member
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

    print("\n- Show client settings:")
    for i, client_setting in enumerate(ClientSettings):
        value = ClientSettings[client_setting]
        setting_name = client_setting.name.replace("_", " ").title()  # Improve readability
        print(f"{i + 1}. {setting_name}: {value}")

    choice = input("\nWant to run the flag editor [y/n]? ")[0].lower()
    if choice == 'y':
        flag_editor(player=rulan)
    else:
        print("Done.")
