import logging
import random
from dataclasses import dataclass, field
from enum import Enum
import doctest
from typing import Any

class ClientSettings(str, Enum):
    """
    NAME = "name"
    ROWS = "rows"
    COLUMNS = "columns"
    TRANSLATION = "Character translation"
    # colors for [bracket reader] text highlighting on C64/128:
    TEXT_COLOR = "Text color"
    HIGHLIGHT_COLOR = "Highlight color"
    BACKGROUND = "Background"
    BORDER = "border"
    """
    def __init__(self):
        self.name = "name"
        self.rows = 25
        self.columns = 40
        self.translation = "PetSCII"
        self.return_key = "Return"

class Gender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"


class PlayerFlags(str, Enum):
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
    AMULET_OF_LIFE_ENERGIZED = "Amulet of Life energized",
    COMPASS_USED = "Compass used",
    DWARF_ALIVE = "Dwarf alive",
    GAUNTLETS_WORN = "Gauntlets worn",
    RING_WORN = "Ring worn",
    SPUR_ALIVE = "SPUR alive",
    THUG_ATTACK = "Thug attack",
    WRAITH_KING_ALIVE = "Wraith King alive",


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
    INT = "Intelligence"
    STR = "Strength"
    WIS = "Wisdom"


@dataclass
class FlagDisplayTypes(str, Enum):
    # different flag states should be displayed with different wording.
    # Displaying "Dungeon Master: Yes" reads better than "Dungeon Master: True",
    # even though that's how the flag state is represented internally.
    # Similarly, "Guild Follow: Off" reads better than "Guild Follow: False"
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
]


@dataclass
class Flag(object):
    name: str
    display_type: FlagDisplayTypes
    status: bool


@dataclass
class Player(object):
    # TODO: make some of these stats part of a generic Character base class
    # generate a dict of 3 {<combination_type>, tuple(three random digits ranging from 0-99)}:
    combinations: dict[CombinationTypes, tuple] = field(
        default_factory=lambda: {
            combination_type: (random.randrange(99) for _ in range(3))
            for combination_type in CombinationTypes
        }
    )
    name: str = None
    # FIXME: just for test purposes:
    gender: Gender = Gender.MALE
    once_per_day: list[str] = field(default_factory=list)
    # Copy list of Flag defaults from PlayerFlag enum on Player instantiation:
    flags: dict[PlayerFlags, Flag] = field(default_factory=lambda: {i[0]: Flag(*i) for i in player_flag_data})
    # creates a new stats dict for each Player, zero all stats:
    stat: dict[PlayerStat, int] = field(default_factory=lambda: {i: 0 for i in PlayerStat})
    # same with silver:
    silver: dict[PlayerMoneyTypes, int] = field(default_factory=lambda: {i: 1000 for i in PlayerMoneyTypes})
    hit_points: int = 0
    client_settings: dict[ClientSettings, Any] = field(default_factory=lambda: {k: v for k, v in ClientSettings})

    def adjust_silver(self, kind: PlayerMoneyTypes, adjustment: int):
        try:
            current_total = self.silver[kind]
            adjusted_total = current_total + adjustment
            gold_kind = PlayerMoneyCategory[kind.name]
            logging.debug("adjust_gold: kind: %s, adjustment: %i, total: %i" % (gold_kind, adjustment,
                                                                                adjusted_total))
            self.silver[kind] = adjusted_total
        except IndexError:
            logging.debug("adjust_gold: %s does not exist" % kind)

    def get_flag(self, name: PlayerFlags) -> Flag:
        """
        Given a PlayerFlagName Enum, return the Flag object
        :param name: name of flag
        :return: Flag object
        """
        try:
            logging.debug("get_flag: %s" % self.flags.get(name))
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
            logging.debug("set_flag: setting flag %s to True" % flag.name)
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
            logging.debug("clear_flag: clearing flag %s to False" % flag.name)
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
            logging.debug("show_flag: flag_name=%s, display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            return f"{flag_name}: {result}"
        except KeyError:
            logging.warning("show_flag: unknown flag: %s" % flag.name)

    def show_flag_line_item(self, flag: PlayerFlags, leading_num: int) -> str:
        """
        Display the flag status based on its display_type string.
        The flag is listed prefixed with leading_number, "...:" and the status.

        :param flag: PlayerFlag name to display
        :param leading_num: used with dot_leader, True prefixes the flag display with this number
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
            logging.debug("show_flag_line_item: enter: flag: %s, "
                          "leading_num: %i, max_width: %i" % (flag, leading_num, max_width))
            temp = self.get_flag(flag)
            flag_name, display_type, status = temp.name.value, temp.display_type, temp.status
            logging.debug("show_flag_line_item: flag_name=%s, "
                          "display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            return f"{leading_num:>2}. {flag_name:.<{max_width}}: {result}"
        except KeyError:
            logging.warning("show_flag_line_item: unknown flag: %s" % flag.name)

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
            logging.error("show_flag_status: invalid type %s for flag %s" % (temp.display_type, temp.name))
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
            logging.debug("toggle_flag: Flag: %s before toggle: %s" % (flag.value, result.status))
            result.status = not result.status
            logging.debug("toggle_flag: Flag: %s after toggle: %s" % (flag.value, result.status))
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
        logging.debug("put_flag: %s put as %s" % (name, status))
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
        logging.debug("adjust_stat: current: %s: %i, adjusted: %i" % (stat_name.name, current, new))
        self.put_stat(stat_name, new)

    def get_stat(self, stat_name: PlayerStat) -> int:
        for key, value in self.stat.items():
            if stat_name.value == key:
                logging.debug("get_stat: get %s: %i" % (stat_name.value, value))
                return value

    def put_stat(self, stat_name: PlayerStat, value) -> None:
        logging.debug("put_stat: put %s: %i" % (stat_name.value, value))
        self.stat[stat_name] = value


def flag_editor(player: Player):
    print("- Toggling an indexed flag:")
    while True:
        for k, v in enumerate(player.flags, start=1):
            print(player.show_flag_line_item(flag=v, leading_num=k))
        option = input(f"1-{len(player.flags)}, [Q]uit: ").lower()
        try:
            if option[0] == 'q':
                print("Done.")
                break
            value = int(option)
            if 0 < value < len(player.flags) + 1:
                # look up the flag index in player_flag_data:
                # value-1 accounts for lists being 0-indexed
                # TODO: toggle_flag_by_index() function?
                logging.debug("flag_editor: value: %i" % value)
                player.toggle_flag(player_flag_data[value - 1][0], verbose=True)
        except ValueError:
            print(f"Please enter a number 1-{len(player.flags)}.")


if __name__ == '__main__':
    # thanks to you, volca. code has been simplified
    # set up logging level (this level or higher will output to console):
    logging.basicConfig(level=logging.DEBUG)

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
    print(f"- Set gold in hand to {wealth:,}")
    rulan.silver[PlayerMoneyTypes.IN_HAND] = wealth

    rulan.adjust_silver(PlayerMoneyTypes.IN_HAND, 100)
    rulan.adjust_silver(PlayerMoneyTypes.IN_BANK, 385)

    print(f"- Show money types and values:")
    for k, v in enumerate(PlayerMoneyTypes, start=1):
        # element_name is an Enum shared between PlayerMoneyTypes and PlayerMoneyCategory
        # to make printing prefixes and gold amounts easier -- at least that's the idea
        col_1 = PlayerMoneyCategory[v].value
        col_2 = rulan.silver[PlayerMoneyTypes[v]]
        """
        >>> PlayerMoneyCategory.IN_HAND.value, rulan.gold[PlayerMoneyTypes.IN_HAND]
        ('In hand', 50000)
        """
        print(f"{k:2>}. {name:.<10}: {amount:>9,}")

    print("- Show random combinations:")
    for combination_name, combination_tuple in rulan.combinations.items():
        print(f"{combination_name.value:>15}: {'-'.join(str(digit) for digit in combination_tuple)}")

    choice = input("Want to run the flag editor [y/n]")[0].lower()
    if choice == 'y':
        flag_editor(player=rulan)
    else:
        print("Done.")
