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
from base_variables import STAT_DATA
from flags import PlayerFlags, FlagDisplayTypes, Flag, new_player_default_flags
from net_server import Message
from base_classes import Size, CombinationTypes, PlayerMoneyTypes, PlayerMoneyCategory, Gender, \
    PlayerClass, PlayerRace, PlayerStat, Guild
from server import server_lock, room_players, compass_txts, players
import net_common
from tada_utilities import make_random_id

# from server.user_settings import ClientSettingsNames, ClientValues

# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/

def set_up_flags():
    flags = {flag_elements[0]: Flag(*flag_elements) for flag_elements in new_player_default_flags}
    return flags

def make_random_stat():
    random_number = random.randint(1, 18)
    logging.debug("%i", random_number)
    return random_number

def set_up_combinations():
    combinations = {combination_name: {
                combination_type: (random.randint(1, 99) for _ in range(3))
                for combination_type in CombinationTypes
            }}
    logging.debug(combinations)
    return combinations

def set_up_silver() -> dict:
    silver_types = {v: k * 1_000 for k, v in enumerate(PlayerMoneyTypes, start=1)}
    logging.info("%s" % silver_types)
    return silver_types

def set_up_stats() -> dict:
    stats = {k: make_random_stat() for k in PlayerStat}
    logging.debug("%s" % stats)
    return stats

@dataclass
class Client:
    COLUMNS: int = 40


class BaseCharacter:
    """
    Base class for all Characters, whether a Player, Monster or NPC, to hold common attributes.
    Override the class to display a different id_prefix.

    :param id_prefix: default 'C". Subclass and set to 'M' for a Monster, 'P' for a Player, etc.
    :param id_number: item number from JSON file
    :param name: Character name
    :param max_inventory: max number of items in inventory
    :param inventory: Items in inventory
    """
    def __init__(self, **kwargs) -> None:
        self.id_prefix = kwargs.get('id_prefix', "C")
        self.id_number = kwargs.get('id_number', make_random_id())
        self.name = kwargs.get('name')
        self.max_inventory = kwargs.get('max_inventory', 5)
        self.inventory = kwargs.get('inventory')

    def __str__(self):
        """
        P = Player
        M = Monster
        etc.
        """
        return f'{self.name} [{self.id_prefix}#{self.id_number}]'


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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status = kwargs.get('status', 1)  # 1=alive, 0=dead?
        size: Optional[Size]
        self.strength = kwargs.get('strength', 0)
        self.to_hit = kwargs.get('to_hit', 0)
        self.special_weapon = kwargs.get('special_weapon')
        self.flags = kwargs.get('flags')
        # TODO: max_inventory: int, inventory: list, description: str, owner: Optional[None] = None
        # NOTE: alignment is in "flags": "evil", "good"
        self.id_prefix = "M"
        # TODO: the Owner is set only if the Monster joins the Player's party
        # FIXME: 'owner = Player' is unresolved reference
        self.owner = None

    def load(self, json_filename: str):
        pass


class Player(object):
    """
    Attributes, flags, and other stuff about players.
    """
    """
    TODO: There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
            (is it important to know whether the player or ally is carrying an item?)
            maybe return Player or Ally object if they hold it, or None if no-one holds it
    """

    def __init__(self, **kwargs):
        """this code is called when creating a new character"""
        # FIXME: probably just forget this, net_server.py handles connected_users(set)
        """
        connection_id: list of CommodoreServer IDs: {'connection_id': id, 'name': 'name'}
        for k in len(connection_ids):
            if connection_id in connection_ids[1][k]:
                logging.info(f'Player.__init__: duplicate {connection_id['id']} assigned to '
                             f'{connection_ids[1][connection_id]}')
            return
        temp = {self.name, connection_id}
        connection_ids.append({'name': name, connection_id})
        logging.info(f'Player.__init__: Connections: {len(connection_ids)}, {connection_ids}')
        self.connection_id = connection_id  # 'id' shadows built-in name
        """
        """
        The point behind all this is that dataclasses can't account for unknown parameters, and I'll
        be adding attributes to the Player class definition for some time until it gets stable.

        The .get() method avoids KeyErrors since it replaces missing parameters with the 2nd param
        """
        self.connection_id = kwargs.get('connection_id', make_random_id())
        # keep this until I figure out where it is in net_server.py
        self.name = kwargs.get('name', "Generic Name")

        self.gender = kwargs.get('gender', Gender.MALE)

        # creates a new stats dict for each Player, zero all stats:
        # set with Player.set_stat(PlayerStat.xyz, value)
        self.stat = kwargs.get("stat", set_up_stats())
        # flags:
        self.flags = kwargs.get('flags', set_up_flags())

        # creates a new silver dict for each Player:
        # in_bank may be cleared on character death (TODO: look in TLOS source)
        # in_bar should be preserved after character's death (TODO: same)
        self.silver = kwargs.get('silver', set_up_silver())
        if self.silver:
            """
            >>> print(f"{PlayerMoneyTypes.IN_HAND}: {silver_types[PlayerMoneyTypes.IN_HAND]:,}")
            In hand: 1,000
            """
            silver_in_hand = self.get_silver(PlayerMoneyTypes.IN_HAND)
            logging.info("Silver in hand: %i" % silver_in_hand)

        # generate a dict of 3 {<combination_type>, tuple(three random digits ranging from 0-99)}:
        self.combinations = kwargs.get('combinations', set_up_combinations())
        # client settings - set up some defaults
        self.client = kwargs.get('client', Client())

        self.times_played = kwargs.get('times_played', None)
        # last_connection helps determine whether once_per_day events should be reset, but we just care about the day
        # rolling over, not that 24 hours have passed.
        # Also in the LASTON command to show when a player was last online.
        # Player.connect() should set last_connection to datetime.now().
        # Player.disconnect() should also set last_connection to datetime.now().
        self.last_connection = kwargs.get('last_connection', None)  # TODO: use datetime

        """
        proposed stats:
        some (not all) other stats, still collecting them:

        special_items[
            SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
            BOAT  # does not actually need to be carried around in inventory, I don't suppose, just a flag?
            ]
        """
        self.map_level = kwargs.get('map_level', 1)  # cl: current_level
        self.map_room = kwargs.get('map_room', 1)  # cr: current_room
        self.moves_made = kwargs.get('moves_made')
        self.birthday = kwargs.get('birthday')  # TODO: use datetime
        self.guild = kwargs.get('guild')  # [civilian | fist | sword | claw | outlaw]
        #  1       2        3       4      5       6       7         8       9
        self.char_class = kwargs.get('char_class')
        # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
        self.race = kwargs.get('char_race')
        # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf

        self.inventory = kwargs.get('inventory')
        # self.shield = kwargs.get('shield')
        # self.armor = kwargs.get('armor')

        self.hit_points = kwargs.get('hit_points', 0)
        self.experience = kwargs.get('experience', 0)
        """
        Things you can only do once per day (file_formats.txt):
        'pr'        has PRAYed once
        'pr2'       has PRAYed twice per day (only if char_class is Druid)
        'birthday'  Player's birthday is today and they've already got their birthday present
                    (prevents them from logging on multiple times per day and getting multiple presents)
        # TODO: make these Enums, finish this list
        """
        self.once_per_day = kwargs.get('once_per_day')

        # FIXME: this is broken
        #  TODO: copy UserSetting class here:
        """
        settings: UserSetting = field(default_factory=lambda: UserSetting())
        # Copy list of client_settings defaults from user_settings.py:
        client_settings: dict[ClientSettingsNames, int | str] = field(
            default_factory=lambda: {i[0]: ClientValues for i in ClientSettingsNames})
        """
        self.party = kwargs.get('party')
        self.allies = kwargs.get('allies')

        self.guild = kwargs.get('guild')

        """
        TODO: MORE CLASSES
        combat:
            honor: int
        class Weapon:
            name: str
            percent_left: int
        class AmmoWeapon:
            ammunition_for: Weapon
            loaded_with: Ammunition
        class Ammunition:
            rounds_per_unit: int  # how many rounds

        bad_hombre_rating (BHR) is calculated from stats, not stored in player log
        """
        # using Dataclasses and updating attributes:
        # https://www.reddit.com/r/learnpython/comments/1gzmlqv/comment/lyxnpxc/

        # Wizard Glow stuff:
        # None if inactive, or non-magic user
        # != 0 is the number of rounds left, decrement at every turn
        self.wizard_glow = kwargs.get('wizard_glow')
        self.id = None

        self.unsaved_changes = False

    def __str__(self):
        """print formatted Player object (double-quoted since ' in string)"""
        # TODO: locale formatting (YYYY-MM-DD, MM/DD/YYYY)
        age = "Undetermined"
        birthdate = "None"
        if self.birthday:
            delta = datetime.now() - self.birthday
            age = f"{delta.days // 365} years"
            date_format_string = "%a %b %d, %Y"  # weekday, month, date, year
            birthdate = self.birthday.strftime(date_format_string)

        _ = f"""
        {'Name:'.rjust(20)} {self.name}
        {'Age:'.rjust(20)} {age}
        {'Gender:'.rjust(20)} {self.gender.title()}
        {'Birthday:'.rjust(20)} {birthdate}
        {'Silver: In hand:'.rjust(20)} {self.silver[PlayerMoneyTypes.IN_HAND]}
        {'Guild:'.rjust(20)} {self.guild.title()}
"""
        return textwrap.dedent(_)

    def __repr__(self):
        return f"Player <{self.name}>"

    def add_item(self, item):
        """Add item to inventory"""
        item.owner = self
        self.inventory.append(item)

    def has_item(self, item):
        """Check if player has item"""
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
        Print <string> in client's Translation, word-wrapped to client's column width to Player

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

    def adjust_stat(stat: PlayerStat, adjustment: int, verbose: bool = True, abbreviate: bool = True):
        """
        Adjusts a player's statistic and prints the outcome.

        :param stat: The statistic to be adjusted.
        :param adjustment: The adjustment to stat.
        :param verbose: Whether to tell about it or not (TODO: based on Expert Mode)
        :param abbreviate: whether to use short (True) or long (False) statistic names
        """
        # Step 1: Look up all data for the given stat
        if verbose:
            stat_info = STAT_DATA[stat]
            stat_name = stat_info["name"][abbreviate]

            # Get the correct phrase based on the adjustment being positive or negative,
            # using the 'is_positive' boolean as an index into the STAT_INFO dict:
            is_positive = adjustment > 0
            # print(f'{is_positive=}')
            phrase = stat_info["phrases"][is_positive]

            # Step 2: Display the updated outcome to the player
            print(f"You feel {phrase}. ({stat_name} {adjustment:+})")

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

    def get_one_stat(self, stat: PlayerStat) -> str | None:
        """
        :param stat: PlayerStat to retrieve
        :return: statistic value, or None if stat_list empty, or IndexError is encountered
        """
        if not stat:
            logging.error("No stats provided")
            return None
        try:
            return self.stat[stat]
        except IndexError:
            logging.error("No stat %s" % stat)
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

        try:
            print(f"{STAT_DATA['name'][abbreviated]}: {stat.value}")
        except IndexError:
            logging.warning("Stat '%s' doesn't exist." % stat)
            # TODO: raise ValueError?
            return None

    def print_multiple_stats(self, stat_list: list[PlayerStat],
                             abbreviate: bool):
        """
        :param stat_list: list of PlayerStat(s) to report
        :param abbreviate: False: 'Int', 'Str', 'Wis', etc. True: 'Intelligence', 'Strength', 'Wisdom', etc.
        """
        for stat in stat_list:
            self.print_stat(stat, abbreviate)

    def get_birthday(self):
        """
        get a character's birthday
        :return: str: "month/day" ("month/day/year" if age known)
        """
        """
        >>> test = Player()  # birthday = datetime.now()
        
        >>> self.get_birthday(age=0, birthday=datetime.date(6, 16, 1976))
        6/16
        """
        # TODO: locale stuff where dates are in either month-day-year / year-month-day format?
        year = self.birthday.year
        month = self.birthday.month
        day = self.birthday.day
        return f"{month}/{day}/{year}"

    def get_age(self):
        # TODO: datetime.now() - self.birthday
        pass


    def connect(self):
        with server_lock:
            # TODO: add last_connection as datetime.now()
            room_players[self.map_room].add(self.id)
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
        current_room = self.map_room
        with server_lock:
            logging.debug("Player.move: Before remove: %s" % room_players[current_room])
            room_players[current_room].remove(self.id)
            logging.debug("Player.move: After remove: %s" % room_players[current_room])

            self.map_room = destination_room
            logging.debug("Player.move: Before add: %s" % room_players[current_room])
            room_players[self.map_room].add(self.id)
            logging.debug("Player.move: After add: %s" % room_players[current_room])
            logging.debug('Player.move: Moved %s from %s to %s' % (self.name, current_room, self.map_room))
            if direction is None:
                return Message([f'[{self.name} disappears in a flash of light.'])
            else:
                return Message([f"{self.name} moves {compass_txts[direction]}."])

    def disconnect(self):
        with server_lock:
            room_players[self.map_room].remove(self.id)
            # increment times played:
            self.times_played += 1
            logging.info("Player.disconnect: %s disconnected. Times played: %i." % (players[self.id].name,
                                                                                    self.times_played))
            return Message([f'{players[self.id].name} falls asleep.'])

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
