import json
import logging
import os
import random
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
import doctest

# TADA-specific imports:
from flags import PlayerFlags, FlagDisplayTypes, Flag, new_player_default_flags
from net_server import Message
from base_classes import BaseCharacter, Size, CombinationTypes, PlayerMoneyTypes, PlayerMoneyCategory, Gender, \
    PlayerClass, PlayerRace, PlayerStat
from server import net_common
from server.server import server_lock, room_players, compass_txts, players
from tada_utilities import make_random_id


# from server.user_settings import ClientSettingsNames, ClientValues

# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/


@dataclass
class Pixie(BaseCharacter):
    can_fly: bool = True
    size: Size = Size.TINY
    max_inventory: int = 4


def longest_flag_name() -> int:
    """
    Determine the length of the longest PlayerFlag string, so the calling routine
    can print the maximum number of ellipses to display (including some padding); e.g.:

    item_one......: foo
    item_two......: bar
    item_three....: baz
    """
    return len(max([x for x in PlayerFlags], key=len)) + 4


@dataclass
class Ally(BaseCharacter):
    inventory: list[str] = field(default_factory=list)  # TODO: list[Item]
    abilities: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


class Horse(BaseCharacter):
    armor: list = field(default_factory=list)
    # if Horse.has_saddlebags is True, Horse can carry additional things (via GIVE?):
    has_saddlebags: bool
    in_saddlebags: list[str] = field(default_factory=list)  # TODO: list[Item]
    has_saddle: bool
    has_lasso: bool
    """
    TODO: additional things to be implemted later:
    training: bool (I think)
    lasso: bool
    # allowed foods: mash, hay, oats, apples, sugar_cubes
    flags: 'can_fly': pegasus (male), maybe?
    """


@dataclass
class Monster(BaseCharacter):
    # number: int
    status: Optional[int]  # 1=alive, 0=dead?
    name: str
    size: Optional[Size]
    strength: int
    to_hit: int
    special_weapon: Optional[int]
    flags: list = field(default_factory=list)
    # TODO: max_inventory: int, inventory: list, description: str, owner: Optional[None] = None
    # alignment is in "flags": "evil", "good"
    item_type = "M"
    # TODO: the Owner is set only if the Monster joins the Player's party
    # FIXME: 'owner = Player' is unresolved reference
    owner = None

    def load(self, json_filename: str):
        pass


@dataclass
class Player(BaseCharacter):
    # put some of these stats in a generic BaseCharacter class
    super().__init__(item_type="Player", max_inventory=5, inventory=[])
    id_number: int = field(default_factory=lambda: make_random_id)
    # TODO: get user_id from json.load(user_id) somehow so we don't have to continually look up user_id by scanning the
    #  player data directory
    user_id: str = ""
    # FIXME: self.get_age() method will use datetime.timedelta(datetime.today() - birthday)
    birthday: datetime = datetime.today()
    gender: Gender = Gender.MALE  # no misogyny intended
    hit_points: int = 0
    experience: int = 0

    # map stats:
    map_level: int = 1  # cl = current level
    room: int = 1  # cr = current room
    # total moves made over the course of the character's life:
    moves_made: int = 0
    # tracks how many moves made during the game session to calculate experience points awarded at quit:
    moves_today: int = 0

    size: Size = field(default_factory=lambda: Size.MAN_SIZED)

    character_class: PlayerClass = None
    character_race: PlayerRace = None

    # the lower the Honor score, the more evil the character has become
    # TODO: check this - I think 1,000 honor points is equivalent to a Saintly Knight
    honor: int = 1_000

    # https://www.reddit.com/r/learnpython/comments/1gzmlqv/comment/lyxnpxc/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button

    # Wizard Glow stuff:
    # None if inactive, or non-magic user
    # != 0 is the number of rounds left, decrement at every turn
    wizard_glow: Optional[int] = None

    """
    Things you can only do once per day (file_formats.txt):
    'pr'        has PRAYed once
    'pr2'       has PRAYed twice per day (only if char_class is Druid)
    'birthday'  Player's birthday is today and they've already got their birthday present
                (prevents them from logging on multiple times per day and getting multiple presents)
    # TODO: make these Enums, finish this list
    """
    once_per_day: list[str] = field(default_factory=list)

    # Copy the list of Flag defaults from the PlayerFlag enum on Player instantiation:
    flags: dict[PlayerFlags, Flag] = field(default_factory=lambda: {i[0]: Flag(*i) for i in new_player_default_flags})
    # creates a new stats dict for each Player, plus zero all stats:
    stat: dict[PlayerStat, int] = field(default_factory=lambda: {i: 0 for i in PlayerStat})
    # same with silver FIXME: (set to 1_000 for testing purposes):
    # TODO: money types may be expanded to platinum, electrum in future
    silver: dict[PlayerMoneyTypes, int] = field(default_factory=lambda: {i: 1_000 for i in PlayerMoneyTypes})

    # generate a dict of 3 {<combination_type>, tuple(three random digits ranging from 0-99)}:
    combinations: dict[CombinationTypes, tuple] = field(
        default_factory=lambda: {
            combination_type: (random.randint(1, 99) for _ in range(3))
            for combination_type in CombinationTypes
        }
    )

    # FIXME: this is broken
    #  TODO: copy UserSetting class here:
    """
    settings: UserSetting = field(default_factory=lambda: UserSetting())
    Copy list of Flag defaults from PlayerFlag enum on Player instantiation:
    flags: dict[PlayerFlags, Flag] = field(default_factory=lambda: {i[0]: Flag(*i) for i in new_player_default_flags})

    # Copy list of client_settings defaults from user_settings.py:
    client_settings: dict[ClientSettingsNames, int | str] = field(
        default_factory=lambda: {i[0]: ClientValues for i in ClientSettingsNames})
    """
    party: list = field(default_factory=list)  # TODO: list[Player or Monster]
    allies: list = field(default_factory=list)  # TODO: list[Ally]

    guild: str = "Blah"  # FIXME: Guild Enum

    def __init__(self, id_prefix: str, id_number: int, name: str, max_inventory: int, inventory: list):
        super().__init__(id_prefix, id_number, name, max_inventory, inventory)
        # last_connection helps determine whether once_per_day events should be reset, but we just care about the day
        # rolling over, not that 24 hours have passed.
        # Also in the LASTON command to show when a player was last online.
        # Player.connect() should set last_connection to datetime.now().
        # Player.disconnect() should also set last_connection to datetime.now().
        self.last_connection: datetime = datetime.now()
        self.times_played = None
        self.id = None

    def __post_init__(self):
        self.client_settings = None

    def add_item(self, item):
        item.owner = self
        self.inventory.append(item)

    def has_item(self, item):
        return item in self.inventory

    def add_to_party(self, party_addition) -> bool:
        # FIXME: specifying 'party_addition: Monster | Player' leads to an unresolved reference error
        # check that party_addition is not self:
        if party_addition is self:
            print(f"This is getting a bit surreal. You can't add {self.name} to {self.name}'s party.")
            return False
        # make sure a party_addition is not already in the party:
        if party_addition in self.party:
            print(f"Seeing another {party_addition.name} is already in your party, they turn sadly away.")
            return False
        self.party.append(party_addition)
        print(f"{party_addition.name} joins {self.name}'s party!")
        return True

    def is_in_party(self, member, verbose: bool = True) -> bool:
        """
        Checks if 'member' already in 'party', returns bool
        :param member: Player | Monster
        :param verbose: whether to tell about it
        """
        party_member = member in self.party
        if party_member and verbose:
            print(f"{member.name} beams with pride.")
        elif verbose:
            print(f"{member.name} scowls!")
        return party_member

    def list_party_members(self):
        if not self.party:
            print(f"There are no other members in {self.name}'s party.")
            return
        else:
            print(f"Members of {self.name}'s party:")
            for num, member in enumerate(self.party, start=1):
                print(f"{num}. {member.name}")

    def __repr__(self):
        return f"Player <{self.name}>"

    def look_at(self, item: Any):
        """
        Print a string that shows the name of the object. If the Player owns the item,
        or the Player's DEBUG or ADMIN flags are True, also show the ID prefix and number.
        Example:
            'Sword [Weapon #4]' if the Player owns the item, or the DEBUG or ADMIN flags are True
            'Sword' if the Player does not own the item, or the DEBUG or ADMIN flags are False
        """
        if item.owner is self or (self.query_flag(PlayerFlags.DEBUG_MODE) or self.query_flag(PlayerFlags.ADMIN)):
            print(f"{item.name} [{item.item_type} #{item.item_id}]")
        else:
            print(f"{item.name}")
        if item.description:
            print(item.description)

    def output(self, string: str) -> Message:
        """
        Print <string> word-wrapped to client's column width to Player

        :param: string: string to output
        :return: Message
        """
        """
        TODO: implement cbmcodec2 ASCII -> PETSCII translation

        TODO: implement different success messages for Player originating action vs. other Players in room
        use player.
        for cxn in all_players_in_room:
            if char.(something, idk what at this point) == Player.who_performed_action:
                output(f"You throw the snowball at {target}.")
            else:
                output(f"{actor} throws the snowball at {target}.")
        """
        """
        if self.client_settings.translation == Translation.PETSCII:
            codec = "petscii_c64en_lc"
            temp = string.encode(codec)
            logging.debug(repr(temp))  # don't print Commodore color codes to Linux terminal
        """
        return Message(lines=[textwrap.fill(text=string,
                                            width=self.client_settings.SCREEN_COLUMNS)])

    def set_silver_absolute(self, kind: PlayerMoneyTypes, amount: int):
        try:
            self.silver[kind] = amount
            logging.debug("kind: %s, amount: %i" % (kind, amount))
        except KeyError:
            logging.warning("kind: invalid type %s" % kind)

    def get_flag(self, flag_name: PlayerFlags) -> Flag | None:
        """
        Given a PlayerFlagName Enum, return the Flag object
        :param flag_name: name of flag
        :return: Flag object
        """
        """
        # instantiate player, show Admin flag object:
        
        >>> rulan = Player()
        
        >>> print(f"- Show Admin flag object:")
        
        >>> print(f"{rulan.get_flag(PlayerFlags.ADMIN)}")

        """
        try:
            logging.debug("flag: %s" % self.flags.get(flag_name))
            return self.flags.get(flag_name)
        except IndexError:
            logging.warning("get_flag: no flag %s" % flag_name)
            return None

    def set_flag(self, flag: PlayerFlags) -> None:
        """
        # FIXME: fix this
        Directly set the flag status to True.

        :param flag: PlayerFlag to set
        :return: None
        """
        try:
            logging.debug("setting flag %s to True" % flag.name)
            current_flag = self.get_flag(flag)
            self.put_flag(flag, status=True, display_type=current_flag.display_type)
        except KeyError:
            logging.error("flag %s not found" % flag.name)

    def clear_flag(self, flag: PlayerFlags) -> None:
        """
        # FIXME: fix this
        Directly clear the flag status to False.

        :param flag: PlayerFlag to clear
        :return: None
        """
        try:
            logging.debug("clearing flag %s to False" % flag.name)
            current_flag = self.get_flag(flag)
            self.put_flag(flag, status=False, display_type=current_flag.display_type)
        except KeyError:
            logging.error("flag %s not found" % flag.name)

    def show_flag(self, flag: PlayerFlags) -> str | None:
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
            current_flag = self.get_flag(flag)
            display_type, status = current_flag.display_type, current_flag.status
            logging.debug("flag_name=%s, display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            return f"{flag_name}: {result}"
        except KeyError:
            logging.warning("unknown flag: %s" % flag.name)
            return None

    def show_flag_line_item(self, flag: PlayerFlags, leading_num: Optional[int]) -> str | None:
        """
        Display the flag name, a dot leader, and the flag status.
        The flag is shown (optionally prefixed with <leading_number> if `leading_num` is of type `int`),
         a dot leader ("...:") and the status: On/Off, Yes/No

        :param flag: PlayerFlag Enum member to display
        :param leading_num: used with `dot_leader`, type `int` prefixes the flag display with this number,
         type `None` suppresses the number from being displayed
        :return: a string displaying the flag status
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
            flag_name: str = temp.name
            display_type: str = temp.display_type
            status: bool = temp.status
            logging.debug("flag_name=%s, "
                          "display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            # leading_num=None is used here with character_editor.py to display a menu of flag settings.
            # print_menu() will number the items:
            number = f"{leading_num:>2}. " if isinstance(leading_num, int) else ""
            return f"{number}{flag_name.ljust(max_width, '.')}: {result}"
        except KeyError:
            logging.warning("unknown flag: %s" % flag.name)
            return None

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
        """Returns the status (True/False) of specified Flag object to caller"""
        result = self.get_flag(flag)
        return result.status

    def show_stat(self, stat_name: PlayerStat) -> str:
        logging.debug(f"show_stat: %s" % stat_name.value)
        x = self.get_stat(stat_name)
        return f"{stat_name.value}: {x}"

    def adj_stat_relative(self, stat_name: PlayerStat, adjustment: int) -> None:
        """adjust stat_name +/- the value of adjustment
        set_stat_absolute(value) will set the stat to <value>
        """
        try:
            # adjust stat by <adjustment>:
            current_value = self.get_stat(stat_name)
            new_value = current_value + adjustment
            logging.info("Stat: %s, Before: %i, After: %i" % (stat_name, current_value, new_value))
            # self.flag.get("flag_name") returns None instead of KeyError if key doesn't exist:
            if self.query_flag(PlayerFlags.EXPERT_MODE):
                # returns tuples, is not subscriptable:
                descriptive = zip([stat for k, stat in enumerate(PlayerStat)],
                                  ['influential', 'hearty', 'agile', 'intelligent',
                                   'strong', 'wise', 'energetic'])
                # TODO: jwhoag suggested adding 'confidence' -> 'brave' -- good idea,
                #  not sure where it can be added yet.
                for n in descriptive:
                    # returns a tuple: e.g., (PlayerStat.CON, 'hearty') -- etc.
                    # FIXME: I don't know of a more efficient way to refer to a subscript in this case.
                    #  This may be good enough, it's a small loop
                    if n[0] == stat_name:
                        print(f"You feel {'more' if new_value > current_value else 'less'} {n[1]}.")
            self.stat[stat_name] = new_value
        except IndexError:
            logging.warning("Stat '%s' doesn't exist." % stat_name)
            # TODO: raise ValueError?
            return None
        try:
            current_value = self.get_stat(stat_name)
            new_value = current_value + adjustment
            logging.debug("current %s: %i, adjusted: %i" %
                          (stat_name.name, stat_name.value, new_value))
            self.set_stat_absolute(stat_name, new_value)
            return None
        except KeyError:
            logging.warning("%s not found" % stat_name)
            return None

    def get_multiple_stats(self, stat_list: list[PlayerStat]) -> list | None:
        """get player stat <stat_list>

        :param stat_list: PlayerStat(s) to retrieve
        :return: list of statistic values, None if stat_list is empty, or IndexError is encountered
        """
        if not stat_list:
            logging.error("No stats provided")
            return None
        try:
            results = []
            for i in stat_list:
                result = self.stat.get(i)
                results.append(result)
                logging.debug("get %s: %i" % (i, result))
            return results
        except IndexError:
            logging.warning("get_stat: no such statistic %s" % stat_list)
            return None

    def set_stat(self, stat_name: PlayerStat, new_value: int) -> None:
        """Directly set a statistic to new_value--contrast with adjust_stat()"""
        original = self.get_stat(stat_name)
        logging.debug("put %s: original: %i, new_value: %i" % (stat_name, original, new_value))
        self.stat[stat_name] = new_value

    def __str__(self):
        """print formatted Character object"""

        # FIXME: test of __str__ method:
        """
        >>> str_test = Player(name="str_test", connection_id=1,
        ...                   client={'name': 'Commodore 128', 'columns': 80},
        ...                   gender=Gender.MALE,
        ...                   birthday=date(year=2022, month=4, day=13),
        ...                   silver{PlayerMoneyTypes.IN_HAND: 2000},
        ...                   guild="fist")

        >>> str_test
        
        >>> print(f"Test of __str__ method:\n{StrTest}")
        Test of __str__ method:
        Name: StrTest        Age: 45    Birthday: 4/13/2022
        Silver: In hand: 2,000
        
        _ += f'\tBirthday: {self.birthday[0]}/{self.birthday[1]}/{self.birthday[2] - }\n'
        _ += f"Silver: In hand: {self.silver[PlayerMoneyTypes.IN_HAND]}\n"
        _ += f'Guild: {self.guild}\n'
        """

        print(f"Name: {self.name:<30}"
              f"Age: {'Unknown' if self.get_age() is None else '{self.age}'}"
              # day / month / year (year = date.year - self.age)
              # TODO: locale formatting (YYYY-MM-DD, MM/DD/YYYY)
              f'\tBirthday: {self.birthday.month}/{self.birthday.day}/{self.birthday.year}\n'
              f"Silver: In hand: {self.silver[PlayerMoneyTypes.IN_HAND]}\n"
              f'Guild: {self.guild}\n')

    def print_all_stats(self):
        """
        >>> test = Player(stats={PlayerStat.CHR: 8,
        ...                      PlayerStat.CON: 15,
        ...                      PlayerStat.DEX: 3,
        ...                      PlayerStat.INT: 5,
        ...                      PlayerStat.STR: 8,
        ...                      PlayerStat.WIS: 3,
        ...                      PlayerStat.EGY: 3})

        >>> test.print_all_stats()
        Chr:  8   Int:  5   Egy:  3
        Con: 15   Str:  8
        Dex:  3   Wis:  3   '

        # TODO: for doctest eventually
        """

        for stat in [PlayerStat.CHR, PlayerStat.INT, PlayerStat.EGY]:
            print(f'Method 1: {self.print_stat(stat, False)}', end='')
            print(f'Method 2: {stat.title()}: {self.stat[stat]:2}   ', end='')
        print()
        for stat in [PlayerStat.CON, PlayerStat.STR]:
            print(f'{stat.title()}: {self.stat[stat]:2}   ', end='')
        print()
        for stat in [PlayerStat.DEX, PlayerStat.WIS]:
            print(f'{stat.title()}: {self.stat[stat]:2}   ', end='')
        print()

    def print_one_stat(self, stat_name: PlayerStat, abbreviations: bool = False):
        """
        Print a single statistic. This is a convenience method for print_all_stats().

        :param stat_name: stat to print
        :param abbreviations: use full word for stat name (True: e.g., "Intelligence", False: "Int")
        """
        print(f'{stat_name.name}: {self.stat[stat_name]}')
        if abbreviations:
            print(f'{stat_name.title()}: {self.stat[stat_name]}')

    def get_silver(self, kind: PlayerMoneyTypes) -> int | None:
        """
        get and return the amount of silver player has

        :param kind: PlayerMoneyTypes.IN_HAND, PlayerMoneyTypes.IN_BANK, PlayerMoneyTypes.IN_BAR
        :return int: value of silver in that category
        """
        try:
            silver = self.silver[kind]
            logging.info("silver [%s]: %i" % (kind, silver))
            return silver
        except IndexError:
            logging.info("Bad type '%s'" % kind)
            return None

    def adj_silver_relative(self, kind: PlayerMoneyTypes, relative_amt: int) -> int | None:
        """
        :param kind: PlayerMoneyTypes Enum
        :param relative_amt: amount to add to (<relative_amt>) or subtract from (-<relative_amt>) current silver total
        # FIXME: flesh out error checking
        """
        try:
            current_value = self.silver[kind]
            new_value = current_value + relative_amt
            self.silver[kind] = new_value
            logging.debug("new value: %i" % new_value)
            return new_value
        except IndexError:
            logging.warning("bad kind: %s" % kind)
            return None

    def is_magic_user(self):
        """
        Shorter than repeating "if char.class_name == 'witch' or char.class_name == 'wizard'"

        :param self: self object
        :return: gender-appropriate magic user class name (Witch or Wizard)
        """
        # FIXME: this is still undergoing testing - I want to have character creation display appropriate class
        #   when gender changes -- can this be done with some logic in the __str__() method?
        return "Wizard" if self.gender is Gender.MALE else "Witch"

    def set_stat_absolute(self, stat: PlayerStat, value: int):
        """
        Set a statistic to an absolute value: e.g., PlayerStat.CON = 10.
        To adjust a statistic +/- a certain number of points, use adj_stat_relative(PlayerStat.CON, -5) instead.

        :param stat: statistic in self.stat{} dict to adjust
        :param value: value to set PlayerStat to
        :return: stat
        """
        """
        TODO: maybe also return 'success': True if 0 > stat > limit)
        TODO: adj_stat_relative() to add/subtract value relative to its current value
            i.e., set_stat_absolute(PlayerStat.INT, 5)  # sets INT to 5
                  adj_stat_relative(PlayerStat.INT, 20)  # adds 20 to whatever INT is
        """
        """
        >>> set_stat_test = Player()

        >>> set_stat_test.set_stat_absolute(PlayerStat.INT, 15)

        >>> set_stat_test.print_stat(PlayerStat.INT, abbreviated=True)
        Int: 15

        >>> set_stat_test.set_stat_absolute(PlayerStat.WIS, 9)

        >>> set_stat_test.print_stat(PlayerStat.WIS, abbreviated=False))
        Wisdom: 9

        # test of Character.set_stat()
        >>> shaia = Player(name="Shaia",
        ...                   connection_id=2,
        ...                   client={'name': 'TADA', 'columns': 80, 'rows': 25},
        ...                   gender=Gender.FEMALE)

        >>> shaia.set_stat_absolute(stat=PlayerStat.INT, value=18)

        >>> print(f"{shaia.name} ...... {shaia.print_stat([PlayerStat.INT])}")  # the longer method
        Shaia ...... Int: 18
        """
        # TODO: example for doctest:
        #  to instantiate Test character, must have stat{} key present

    def get_stat(self, stat: PlayerStat) -> int | None:
        """
        if 'stat' is str: return value of single stat as str: 'stat'

        :return: value of single stat as int: 'stat', or None if stat doesn't exist
        TODO: if 'stat' is list: sum up contents of list: [PlayerStat.STR, PlayerStat.WIS, PlayerStat.INT]...
        TODO: refactor get_multiple_stats() to accept a list of PlayerStats, then for each stat, call get_stat()
            -- avoids multiple confusing function calls trying to do too much
        """
        try:
            return self.stat[stat]
        except KeyError:
            logging.warning("Stat '%s' doesn't exist." % k)
            # TODO: raise ValueError?
            return None

    def get_multiple_stats(self, stat_list: list[PlayerStat]) -> list | None:
        """
        :param stat_list: list of PlayerStat(s) to retrieve
        :return: list of statistic values, None if stat_list empty, or IndexError is encountered
        """
        if not stat_list:
            logging.error("No stats provided")
            return None
        try:
            return [self.stat[stat] for stat in stat_list]
        # FIXME: what is the difference between KeyError and IndexError?
        except KeyError:
            logging.warning("Stat '%s' doesn't exist." % stat_list)
            return None
        except IndexError:
            logging.warning("get_stat: no such statistic %s" % stat_list)
            return None

    def print_stat(self, stat: PlayerStat, abbreviated: bool):
        """
        Print player stat in title case: '<Stat>: <value>' on a single line.
        Cha: 10

        print_multiple_stats() uses this function as a helper:
        Cha: 10   Dex: 15   Int: 9

        :param stat: a single PlayerStat Enum(s) to report
        :param abbreviated: False: 'Int', 'Str', 'Wis', etc. True: 'Intelligence', 'Strength', 'Wisdom', etc.
        :return: None
        """
        # for doctest: if functions have a prerequisite function, call that first (just like real code)
        """
        >>> test = Player()
        
        >>> test.set_stat_absolute(PlayerStat.CHR, 10)  # set Charisma to 10

        >>> test.print_stat(stat=PlayerStat.CHR, abbreviated=False)
        Charisma: 10
        """
        long_stat_names = {PlayerStat.CON: "Constitution",
                           PlayerStat.DEX: "Dexterity",
                           PlayerStat.INT: "Intelligence",
                           PlayerStat.STR: "Strength",
                           PlayerStat.WIS: "Wisdom",
                           PlayerStat.EGY: "Energy"}
        try:
            # TODO: map long words to PlayerStat short words...
            if abbreviated:
                print(f"{stat}: {stat.value}")
            else:
                print(f"{long_stat_names[stat]}")
        except IndexError:
            logging.warning("Stat '%s' doesn't exist." % stat)
            # TODO: raise ValueError?
            return None
        # return e.g., "Int: 4"
        if abbreviated:
            stat_names = [s for s in PlayerStat.name]
            stat_format = f"{stat_names:<12}"
        else:
            # use abbreviations:
            stat_names = ["Chr", "Con", "Dex", "Int", "Str", "Wis", "Egy"]
            stat_format = f"{stat_names}"  # FIXME: finish this
        for k, stat in enumerate(self.stat):
            print(f'{stat_format:stat}: {self.stat[stat]:2} ', end='   ')
        print()
        return None

    def print_multiple_stats(self, stat_list: list[PlayerStat],
                             full_word: bool):
        """
        :param stat_list: list of PlayerStat(s) to report
        :param full_word: False: 'Int', 'Str', 'Wis', etc. True: 'Intelligence', 'Strength', 'Wisdom', etc.
        """
        """
        :param stat_list: list of PlayerStat(s) to report
        :param full_word: False: 'Int', 'Str', 'Wis', etc. True: 'Intelligence', 'Strength', 'Wisdom', etc.
        """
        for stat in stat_list:
            self.print_stat(stat, full_word)

    def get_birthday(self):
        """
        get a character's birthday
        :return: str: "month/day" ("month/day/year" if age known)
        """
        """
        >>> test = Player()  # birthday = datetime.now()
        
        >>> self.get_birthday()
        6/16/1976

        >>> self.get_birthday(age=0, birthday=(6, 16, 1976))
        6/16
        """
        # TODO: locale stuff where dates are in either month-day-year / year-month-day format?
        year = self.birthday.year
        month = self.birthday.month
        day = self.birthday.day
        """
        if age is None or age == 0:
            # year unknown, don't print it
            return f"{month}/{day}"
        else:
            # year known, get current year - age
            year = datetime.today().year - age
        """
        return f"{month}/{day}/{year}"

    def get_age(self):
        pass


    def connect(self):
        with server_lock:
            # TODO: add last_connection as datetime.now()
            room_players[self.room].add(self.id)
            self.last_connection = datetime.now()
            logging.info("%s connected at %s" % (self.name, self.last_connection))
            # TODO: notify other players in same room of connection ("%s wakes up.")
            # TODO: watchfor list: ("[Somewhere in the land, ]%s has woken up / fallen asleep.")
            #    ("Somewhere in the land, " printed if not in the same room.)

    def move(self, destination_room: int, direction=None):
        """
        remove player login id from list of players in current_room, add them to room next_room
        :param destination_room: room to move to
        :param direction: direction being moved in, for notifying other players of movement
        if None, '#<room_number>' teleportation command (or, later, spell) was used and the
        "<player> disappears in a flash of light" message is used instead
        """
        current_room = self.room
        with server_lock:
            logging.debug("Player.move: Before remove: %s" % room_players[current_room])
            room_players[current_room].remove(self.id)
            logging.debug("Player.move: After remove: %s" % room_players[current_room])

            self.room = destination_room
            logging.debug("Player.move: Before add: %s" % room_players[current_room])
            room_players[self.room].add(self.id)
            logging.debug("Player.move: After add: %s" % room_players[current_room])
            logging.debug('Player.move: Moved %s from %s to %s' % (self.name, current_room, self.room))
            if direction is None:
                print(f'[{self.name} disappears in a flash of light.')
            else:
                print(f"{self.name} moves {compass_txts[direction]}.")

    def disconnect(self):
        with server_lock:
            room_players[self.room].remove(self.id)
            # increment times played:
            self.times_played += 1
            logging.info("Player.disconnect: %s disconnected. Times played: %i." % (players[self.id].name,
                                                                                    self.times_played))
            return Message(lines=[f'{players[self.id].name} falls asleep.'])

    @staticmethod
    def _json_path(user_id):
        return os.path.join(net_common.run_server_dir, f"player-{user_id}.json")

    @staticmethod
    def load(user_id):
        """Load player from the JSON file based on the user ID"""
        try:
            path = Player._json_path(user_id)
            if os.path.exists(path):
                with open(path) as json_file:
                    lh_data = json.load(json_file)
                    logging.debug(f"Player.load: Loaded '%s'." % lh_data['name'])
                    return Player(**lh_data)
            return None
        except FileNotFoundError:
            # Failure
            logging.error("Player.load: '%s' not found" % user_id)
            return None

    def save(self):
        # TODO: should a 'changes' flag be implemented to prevent saving if changes haven't been made?
        with open(Player._json_path(self.id), 'w') as json_file:
            json.dump(obj=self, fp=json_file, default=lambda o: {k: v for k, v
                                                      # in o.__dict__.items() if v}, indent=4)
                                                      in o.__dict__.items()}, indent=4)
            logging.debug("Player.save: Saved '%s'." % self.name)


def transfer_silver(from_char: Player, to_char: Player, amount: int,
                    from_where: PlayerMoneyTypes = PlayerMoneyTypes.IN_HAND,
                    to_where: PlayerMoneyTypes = PlayerMoneyTypes.IN_HAND,
                    verbose: bool = True) -> bool:
    """
    Transfer silver from one Player to another Player.

    :param from_char: Character to transfer <amount> silver from
    :param to_char: Character to transfer <amount> silver to
    :param amount: amount to transfer
    :param from_where: which location is the money in? ('IN_HAND' is the default)
    :param to_where: where silver is ('IN_HAND' is the default)
    :param verbose: True if you want to announce the success (or failure) of a transfer
    :return: True if `from_char` has `amount` silver, False if not
    """
    """
    # test of Character.transfer_silver:
    >>> shaia = Player()

    >>> shaia.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 200)

    >>> rulan = Player()

    >>> rulan.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 200)

    # Shaia doesn't have 500 silver in hand, so this will fail:
    >>> shaia.transfer_silver(from_char=shaia, to_char=rulan, amount=500,
    ...                       from_where=PlayerMoneyTypes.IN_HAND,
    ...                       to_where=PlayerMoneyTypes.IN_HAND)
    False

    # Rulan has 100 silver in hand, so this will succeed:
    >>> shaia.transfer_silver(from_char=shaia, to_char=rulan, amount=100,
    ...                       from_where=PlayerMoneyTypes.IN_HAND,
    ...                       to_where=PlayerMoneyTypes.IN_HAND)
    True
    """
    # as suggested by Shaia:
    # (will be useful for a future bank, or future expansion: silver transfer spell?)
    if from_char.silver[from_where] >= amount:
        to_char.set_silver_absolute(to_where, amount)
        from_char.set_silver_absolute(from_where, -amount)
        logging.info(
            # e.g.: "Transfer 100 silver in hand from Shaia to Rulan in hand"
            "Transfer %i silver %s from %s to %s %s" % (
                amount, from_where, from_char.name, to_char.name, to_char.silver[to_where]))
        if verbose:
            print(f'{from_char.name} transferred {amount:,} silver {from_where} to {to_char.name}.')
            print(f'{to_char.name} now has {to_char.silver[to_where]}.')
        return True
    else:
        if verbose:
            print(f"{from_char.name} doesn't have {amount:,} silver to give.")
        return False


if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')

    doctest.testmod(verbose=True)

    rulan = Player()
    # connection_ids = []  # initialize empty list for logging connection_id's

    print("- Adjust & show DEX score:")
    print("- Current DEX score:")
    print(rulan.show_stat(PlayerStat.DEX))
    add = 15
    print(f"- Adjust DEX to {add}:")
    rulan.adj_stat_relative(PlayerStat.DEX, adjustment=add)
    print(rulan.show_stat(PlayerStat.DEX))

    subtract = -9
    verify = add + subtract
    print(f"- Adjust DEX by {subtract}:")
    rulan.adj_stat_relative(PlayerStat.DEX, adjustment=subtract)
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

    rulan.adj_silver_relative(PlayerMoneyTypes.IN_HAND, 100)
    rulan.adj_silver_relative(PlayerMoneyTypes.IN_BANK, 385)

    print(f"\n- Show money categories and values:")
    for k, category in enumerate(PlayerMoneyTypes, start=1):
        name = PlayerMoneyCategory[category].value
        amount = rulan.silver[name]  # Directly access the value using the enum member
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

    """
    # FIXME: doesn't work yet
    print("\n- Show client settings:")
    for i, client_setting in enumerate(ClientSettingsNames):
        value = ClientSettingsNames[client_setting]
        setting_name = client_setting.name.replace("_", " ").title()  # Improve readability
        print(f"{i + 1}. {setting_name}: {value}")
    """
