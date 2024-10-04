import logging
from dataclasses import dataclass, field
from enum import Enum
import doctest


class PlayerFlagName(str, Enum):
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
    return len(max([x for x in PlayerFlagName], key=len)) + 4


class PlayerMoneyTypes(str, Enum):
    # this is the dict element to reference money amounts
    IN_HAND = "IN_HAND"
    IN_BANK = "IN_BANK"
    IN_BAR = "IN_BAR"


class PlayerMoneyCategory(str, Enum):
    # this refers to Player.gold{PlayerMoneyTypes.Enum} printable names
    IN_HAND = "In hand"
    IN_BANK = "In bank"
    IN_BAR = "In bar"


class PlayerStatName(str, Enum):
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
    (PlayerFlagName.ADMIN, FlagDisplayTypes.YESNO, False),
    # can build things later:
    (PlayerFlagName.ARCHITECT, FlagDisplayTypes.YESNO, False),
    # a level lower than Admin, different permissions to be determined:
    (PlayerFlagName.DUNGEON_MASTER, FlagDisplayTypes.YESNO, False),
    # guild stuff:
    (PlayerFlagName.GUILD_AUTODUEL, FlagDisplayTypes.ONOFF, False),
    (PlayerFlagName.GUILD_FOLLOW_MODE, FlagDisplayTypes.ONOFF, False),
    (PlayerFlagName.GUILD_MEMBER, FlagDisplayTypes.YESNO, False),
    # option toggles:
    (PlayerFlagName.EXPERT_MODE, FlagDisplayTypes.ONOFF, False),
    (PlayerFlagName.HOURGLASS, FlagDisplayTypes.ONOFF, True),
    (PlayerFlagName.ORATOR, FlagDisplayTypes.YESNO, False),
    (PlayerFlagName.ROOM_DESCRIPTIONS, FlagDisplayTypes.ONOFF, True),
    (PlayerFlagName.UNCONSCIOUS, FlagDisplayTypes.YESNO, False),
    # game states:
    (PlayerFlagName.AMULET_OF_LIFE_ENERGIZED, FlagDisplayTypes.YESNO, False),
    (PlayerFlagName.COMPASS_USED, FlagDisplayTypes.YESNO, False),
    (PlayerFlagName.DWARF_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlagName.GAUNTLETS_WORN, FlagDisplayTypes.YESNO, False),
    (PlayerFlagName.RING_WORN, FlagDisplayTypes.YESNO, False),
    (PlayerFlagName.SPUR_ALIVE, FlagDisplayTypes.YESNO, True),
    (PlayerFlagName.THUG_ATTACK, FlagDisplayTypes.YESNO, False),
    (PlayerFlagName.WRAITH_KING_ALIVE, FlagDisplayTypes.YESNO, True),
]


@dataclass
class Flag(object):
    name: str
    display_type: FlagDisplayTypes
    status: bool

@dataclass
class Player(object):
    # TODO: make some of these stats part of a base class
    # Copy list of Flag defaults from PlayerFlag enum on Player instantiation:
    flags: dict[PlayerFlagName, Flag] = field(default_factory=lambda: {i[0]: Flag(*i) for i in player_flag_data})
    stat: dict[PlayerStatName, int] = field(default_factory=lambda: {i: 0 for i in PlayerStatName})
    gold: dict[PlayerMoneyTypes, int] = field(default_factory=lambda: {i: 1000 for i in PlayerMoneyTypes})

    def get_flag(self, name: PlayerFlagName) -> Flag:
        """
        Given a PlayerFlagName, return the Flag object
        :param name: name of flag
        :return: Flag object
        """
        logging.debug("get_flag: %s" % self.flags.get(name))
        return self.flags.get(name)

    def show_flag(self, flag: PlayerFlagName, ) -> str:
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
            logging.debug("show_flag: enter: flag: %s" % flag_name)
            temp = self.get_flag(flag)
            # flag_name = temp.name
            display_type = temp.display_type
            status = temp.status
            logging.debug("show_flag: flag_name=%s, display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            return f"{flag_name}: {result}"
        except KeyError:
            logging.warning("show_flag: unknown flag: %s" % flag.name)

    def show_flag_line_item(self, flag: PlayerFlagName, leading_num: int) -> str:
        """
        Display the flag status based on its display_type string.
        The flag is listed prefixed with leading_number, "...:" and the status.

        :param flag: Flag name to display
        :param leading_num: used with dot_leader, True prefixes the flag display with this number
        :param max_width: how many dot leaders to display between the flag and its status
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
            logging.debug("show_flag_line_item: enter: flag: %s, leading_num: %i, max_width: %i" % (flag, leading_num, max_width))
            temp = self.get_flag(flag)
            flag_name, display_type, status = temp.name.value, temp.display_type, temp.status
            logging.debug("show_flag_line_item: flag_name=%s, display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            return f"{leading_num:>2}. {flag_name:.<{max_width}}: {result}"
        except KeyError:
            logging.warning("show_flag_line_item: unknown flag: %s" % flag.name)

    def show_flag_status(self, flag: PlayerFlagName) -> str:
        """
        Show a flag's status.
        :param flag: PlayerFlagName to display the status of
        :return: Appropriate string for flag DisplayType
        """
        """
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

    def toggle_flag(self, flag: PlayerFlagName, verbose=False):
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
            self.put_flag(result.name, result.display_type, result.status)
            if verbose:
                # FIXME: I'm going to let this stand even though "UNCONSCIOUS are off"
                # will never be displayed directly, maybe in a player editor program...
                indefinite_article = "are" if flag.name.endswith("S") else "is"
                print(f"{flag.value} {indefinite_article} now {self.show_flag_status(flag)}.")
        except KeyError:
            logging.warning("toggle_flag: Can't toggle unknown flag: %s" % flag.name)

    def put_flag(self, name: PlayerFlagName, display_type: FlagDisplayTypes, status: bool):
        logging.debug("put_flag: %s put as %s" % (name, status))
        self.flags[name] = Flag(name, display_type, status)

    def query_flag(self, flag: PlayerFlagName) -> bool:
        result = self.get_flag(flag)
        # returned Flag object, return the status to caller:
        return result.status

    def show_stat(self, stat_name: PlayerStatName) -> str:
        logging.debug(f"show_stat: %s" % stat_name.value)
        x = self.get_stat(stat_name)
        return f"{stat_name.value}: {x}"

    def adjust_stat(self, stat_name: PlayerStatName, adjustment):
        current = self.get_stat(stat_name)
        new = current + adjustment
        logging.debug("adjust_stat: current: %s: %i, adjusted: %i" % (stat_name.name, current, new))
        self.put_stat(stat_name, new)

    def get_stat(self, stat_name: PlayerStatName) -> int:
        for key, value in self.stat.items():
            if stat_name.value == key:
                logging.debug("get_stat: get %s: %i" % (stat_name.value, value))
                return value

    def put_stat(self, stat_name: PlayerStatName, value) -> None:
        logging.debug("put_stat: put %s: %i" % (stat_name.value, value))
        self.stat[stat_name] = value


def flag_editor(player: Player):
    print("- Toggling an indexed flag:")
    while True:
        for k, v in enumerate(player.flags, start=1):
            print(player.show_flag_line_item(v, leading_num=k))
        option = input(f"1-{len(player.flags)}, [Q]uit: ").lower()
        if option == 'q':
            print("Done.")
            break
        value = int(option)
        try:
            if 1 < value < len(player.flags):
                print("ok")
                # look up the flag index in player_flag_data:
                # value-1 accounts for lists being 0-indexed
                # TODO: toggle_flag_by_index() function?
                player.toggle_flag(player_flag_data[value-1][0], verbose=True)
        except IndexError:
            print("Out of range")

if __name__ == '__main__':
    # thanks to you, volca. code has been simplified
    # set up logging level (this level or higher will output to console):
    logging.basicConfig(level=logging.DEBUG)

    # set up doctest
    doctest.testmod(verbose=True)

    rulan = Player()
    print(f"- Show Admin flag object:")
    print(f"{rulan.get_flag(PlayerFlagName.ADMIN)}")

    print(f"- show_flag 'Unconscious':")
    print(f"{rulan.show_flag(PlayerFlagName.UNCONSCIOUS)}")

    print("- Show all flags:")
    for i, flag in enumerate(rulan.flags, start=1):
        print(rulan.show_flag_line_item(flag=flag, leading_num=i))

    print("- Toggle 'Unconscious' flag, verbose=True:")
    rulan.toggle_flag(PlayerFlagName.UNCONSCIOUS, verbose=True)

    print("- Toggle 'Room Descriptions' flag, verbose=False:")
    rd_flag = PlayerFlagName.ROOM_DESCRIPTIONS
    rulan.toggle_flag(rd_flag, verbose=False)

    print("- Toggle 'Orator' flag, verbose=True:")
    rulan.toggle_flag(PlayerFlagName.ORATOR, verbose=True)

    print("- Different text for result of query 'Room Descriptions' flag:")
    print("Shazam [True]" if rulan.query_flag(rd_flag) else "Bazinga [False]")

    print("- Show stats object:")
    print(rulan.stat)
    # this worked before show_stat():
    """
    for key, value in rulan.stat.items():
        print(f"{key.value}: {value}")
    """
    print("- Show all stats:")
    for i in rulan.stat:
        print(rulan.show_stat(i))

    print("- Adjust & show DEX score:")
    print("- Current DEX score:")
    print(rulan.show_stat(PlayerStatName.DEX))
    add = 15
    print(f"- Adjust DEX to {add}:")
    rulan.adjust_stat(PlayerStatName.DEX, adjustment=add)
    print(rulan.show_stat(PlayerStatName.DEX))

    subtract = -9
    verify = add + subtract
    print(f"- Adjust DEX by {subtract}:")
    rulan.adjust_stat(PlayerStatName.DEX, adjustment=subtract)
    print(rulan.show_stat(PlayerStatName.DEX))
    # test = 5
    # print(f'{test.bit_count()}') # 2: bit 4 + bit 1

    if verify == add + subtract:
        print("* Math checks out!")
    else:
        print("* Somethin' ain't right.")

    wealth = 50000
    print(f"- Set gold in hand to {wealth:,}")
    rulan.gold[PlayerMoneyTypes.IN_HAND] = wealth

    print(f"- Show money types and values:")
    for k, v in enumerate(PlayerMoneyTypes, start=1):
        # element_name is an Enum shared between PlayerMoneyTypes and PlayerMoneyCategory
        # to make printing prefixes and gold amounts easier -- at least that's the idea
        col_1 = PlayerMoneyCategory[v].value
        col_2 = rulan.gold[PlayerMoneyTypes[v]]
        """
        >>> PlayerMoneyCategory.IN_HAND.value, rulan.gold[PlayerMoneyTypes.IN_HAND]
        ('In hand', 50000)
        """
        print(f"{k:2>}. {col_1}: {col_2:,}")

    choice = input("Want to run the flag editor [y/n]")[0].lower()
    if choice == 'y':
        flag_editor(player=rulan)
    else:
        print("Done.")
