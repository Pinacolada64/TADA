import json
import logging
import os
import random
import textwrap
import datetime
from typing import Any, Optional, TYPE_CHECKING

from bar.ally_data import Ally

if TYPE_CHECKING:
    import net_common
    import terminal
    from base_classes import CombinationTypes, PlayerMoneyTypes, PlayerStat, Gender, compass_txts, Guild, Alignment
    from base_variables import STAT_DATA
    from flags import Flag, new_player_default_flags, PlayerFlags, FlagDisplayTypes
    from net_server import Message
    from server import server_lock, room_players, players
    from tada_utilities import make_random_id


def set_up_flags():
    from flags import Flag, new_player_default_flags
    # make a dict of Flag() objects
    flags = {flag_elements[0]: Flag(*flag_elements) for flag_elements in new_player_default_flags}
    return flags


def make_random_id():
    random_id = random.randint(1, 256 * 256)
    logging.debug("%i", random_id)
    return random_id


def make_random_stat():
    random_number = random.randint(1, 18)
    logging.debug("%i", random_number)
    return random_number


def set_up_client_settings():
    import terminal
    logging.debug("Calling terminal.ClientSettings()")
    terminal_settings = terminal.ClientSettings
    logging.debug(terminal_settings)
    return terminal_settings


def set_up_combinations():
    from base_classes import Combination, CombinationTypes
    # returns a list of 3 combinations: [<CombinationTypes.CASTLE: (40,10,5)]
    combinations = [Combination(combination_type) for combination_type in CombinationTypes]
    # >>> print(Combination(CombinationTypes.LOCKER))
    #   Locker: 21-83-91
    logging.debug(combinations)
    return combinations


def set_up_rulan() -> dict:
    from base_classes import Guild
    birthday = datetime.datetime(1976, 6, 16)
    last_play_date = datetime.date.today()
    logging.info("Setting up Rulan.")
    return {'name': 'Rulan',
            'times_played': None,  # this marks a new player
            'guild': Guild.FIST,
            'birthday': birthday,
            'last_play_date': last_play_date,
            }


def set_up_silver() -> dict:
    from base_classes import PlayerMoneyTypes
    # numeric values can have underscores in them to separate thousands, trillions places in a localization-
    # agnostic way: 1_000 represents 1,000.00 or 1.000,00 depending on locale.
    # make a dict: {PlayerMoneyType.IN_BAR: 1_000, PlayerMoneyType.IN_BANK: 2_000, PlayerMoneyType.IN_HAND: 3_000}
    #
    silver_types = {v: k * 1_000 for k, v in enumerate(PlayerMoneyTypes, start=1)}
    logging.info("%s" % silver_types)
    return silver_types


def set_up_stats() -> dict:
    from base_classes import PlayerStat
    stats = {k: make_random_stat() for k in PlayerStat}
    logging.debug("%s" % stats)
    return stats


def longest_flag_name() -> int:
    """
    Determine the length of the longest PlayerFlag string, so the calling routine
    can print the maximum number of ellipses to display (including some padding); e.g.:

    item_one......: foo
    item_two......: bar
    item_three....: baz
    """
    return len(max([x for x in PlayerFlags], key=len)) + 4


class Player:
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
        from base_classes import Alignment, Guild, Gender, PlayerMoneyTypes
        import terminal
        """
        The point behind all this is that dataclasses can't account for unknown parameters, and I'll
        be adding attributes to the Player class definition for some time until the attributes stabilize.

        The .get() method avoids KeyErrors since it replaces missing parameters with the 2nd parameter,
        or None if not specified.
        """
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
        self.connection_id = kwargs.get('connection_id', make_random_id())
        # keep this until I figure out where it is in net_server.py:
        self.name = kwargs.get('name', "Generic Name")

        self.gender = kwargs.get('gender', Gender.MALE)

        # creates a new stats dict for each Player, creates random stats:
        # TODO: set with Player.set_stat_absolute(PlayerStat.xyz, value)
        self.stats = kwargs.get("stats", set_up_stats())
        # flags:
        self.flags = kwargs.get('flags', set_up_flags())
        # generate a dict of 3 {<combination_type>, tuple(three random digits ranging from 0-99)}:
        self.combinations = kwargs.get('combinations', set_up_combinations())
        # client settings - set up some defaults
        self.client_settings = kwargs.get('client_settings', set_up_client_settings())

        self.natural_alignment = kwargs.get('natural_alignment', Alignment.NEUTRAL)
        self.current_alignment = kwargs.get('current_alignment', Alignment.NEUTRAL)

        # creates a new silver dict for each Player:
        # IN_BANK may be cleared on character death (TODO: look in TLOS source)
        # IN_BAR should be preserved after character's death (TODO: same)
        self.silver = kwargs.get('silver', set_up_silver())
        if self.silver:
            """
            >>> print(f"{PlayerMoneyTypes.IN_HAND}: {silver_types[PlayerMoneyTypes.IN_HAND]:,}")
            In hand: 1,000
            """
            silver_in_hand = self.get_silver(PlayerMoneyTypes.IN_HAND)
            logging.info("Silver in hand: %i" % silver_in_hand)

        self.times_played = kwargs.get('times_played', None)
        # last_connection helps determine whether once_per_day events should be reset, but we just care about the day
        # rolling over, not that 24 hours have passed.
        # TODO: Also in the LASTON command to show when a player was last online.
        # Player.connect() should set last_connection to datetime.now().
        # Player.disconnect() should also set last_connection to datetime.now().
        self.last_connection = kwargs.get('last_connection', datetime.datetime.now())
        """
        proposed stats:
        some (not all) other stats, still collecting them:

        special_items[
            SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
            BOAT does not actually need to be carried around in inventory, I don't suppose, just a flag?
        """
        self.map_level = kwargs.get('map_level', 1)  # cl (current level)
        self.map_room = kwargs.get('map_room', 1)  # cr (current room)
        self.moves_made = kwargs.get('moves_made')
        # tracks how many moves made during the game session to calculate experience points awarded at quit:
        self.moves_today = kwargs.get('moves_today', 0)
        self.birthday = kwargs.get('birthday')  # TODO: use datetime
        self.guild = kwargs.get('guild', Guild.CIVILIAN)  # [civilian | fist | sword | claw | outlaw]
        # 1       2        3       4      5       6       7         8       9
        self.char_class = kwargs.get('char_class')
        # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
        self.char_race = kwargs.get('char_race')
        # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf

        self.inventory = kwargs.get('inventory')

        # combat stuff:
        self.hit_points = kwargs.get('hit_points', 0)
        # the lower the Honor score, the more evil the character has become.
        # TODO: look it up, but I think 1,000 honor points is equivalent to a Saintly Knight.
        self.honor = kwargs.get('honor', 1_000)

        self.shield = kwargs.get('shield')
        self.armor = kwargs.get('armor')
        self.experience = kwargs.get('experience', 0)
        self.dead_monsters = kwargs.get('dead_monsters', [])
        """
        Things you can only do once per day (file_formats.txt):
        'pr'        has PRAYed once
        'pr2'       has PRAYed twice per day (only if char_class is Druid)
        'birthday'  Player's birthday is today and they've already got their birthday present
                    (prevents them from logging on multiple times per day and getting multiple presents)
        # TODO: make these Enums, finish this list
        """
        self.once_per_day = kwargs.get('once_per_day', [])
        self.last_play_date = kwargs.get('last_play_date', datetime.datetime.now())

        self.party = kwargs.get('party', [])
        self.allies = kwargs.get('allies', [])

        self.guild = kwargs.get('guild', Guild.CIVILIAN)

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
        self.id = None  # account id

        # command history:
        self.command = None
        self.previous_command = None

        # flag whether a save is required:
        self.unsaved_changes: bool = False

    def __str__(self):
        """print formatted Player object (just random info for now to test)"""
        age = "Undetermined"
        birthday = "Undetermined"
        date_format_string = "%a %b %d, %Y"  # weekday month date, year
        combinations = [f'{c.name.rjust(15)}: {c.combination}' for c in self.combinations]
        if self.birthday:
            delta = datetime.datetime.now() - datetime.datetime(self.birthday)
            age = f"{delta.days // 365} years"
            date_format_string = "%a %b %d, %Y"  # weekday, month, date, year
            birthdate = self.birthday.strftime(date_format_string)
            year_delta = datetime.date.today().year - self.birthday.year
            age = f"{year_delta} years"
            birthday = self.birthday.strftime(date_format_string)
        if self.last_play_date:
            last_play_date = self.last_play_date.strftime(date_format_string)

        self.silver_total = self.silver[PlayerMoneyTypes.IN_HAND] + \
                            self.silver[PlayerMoneyTypes.IN_BAR] + \
                            self.silver[PlayerMoneyTypes.IN_BANK]

        _ = f"""
        {'Name:'.rjust(20)} {self.name}
        {'Age:'.rjust(20)} {age}
        {'Gender:'.rjust(20)} {self.gender.title()}
        {'Age:'.rjust(20)} {age}
        {'Birthday:'.rjust(20)} {birthday}
        {'Silver: In hand:'.rjust(20)} {self.silver[PlayerMoneyTypes.IN_HAND]: >12,}
        {'In bank:'.rjust(20)} {self.silver[PlayerMoneyTypes.IN_BANK]: >12,}
        {'In bar :'.rjust(20)} {self.silver[PlayerMoneyTypes.IN_BAR]: >12,}
        {'Total:'.rjust(20)} {self.silver_total: >12,}
        
        {'Guild:'.rjust(20)} {self.guild.title()}
        {'Combinations:'.rjust(20)} {self.show_combinations()}
        
        {'Last played:'.rjust(20)} {last_play_date}
        """
        return textwrap.dedent(_)

    def __repr__(self):
        return f"Player <{self.name}>"

    def set_stat(self, stat: "PlayerStat", adj: int):
        """
        :param stat: statistic in stats{} dict to adjust
        :param adj: adjustment (+x or -x)
        :return: stat, maybe also 'success': True if 0 > stat > <limit>

        >>> rulan = Player(**set_up_rulan())

        >>> rulan.adjust_stat(PlayerStat.STR, -5)  # decrement Rulan's strength by 5
        """
        if stat not in self.stats:
            logging.warning(f"Stat {stat} doesn't exist.")
            # raise ValueError?
            return
        # adjust stat by <adjustment>:
        before = self.stats[stat]
        after = before + adj
        logging.info("set_stat: Before: %s %i" % (stat, after))
        if not self.query_flag(PlayerFlags.EXPERT_MODE):
            pass
            # TODO: jwhoag suggested adding 'confidence' -> 'brave' -- good idea,
            #  not sure where it can be added yet.
        logging.info("set_stat: After: %s %i" % (stat, after))
        self.stats[stat] = after

    def has_item(self, item):
        """Check if player has item"""
        return item in self.inventory

    def add_to_party(self, player: "Player", party_addition: Ally) -> bool:
        """
        Check if party_addition exists in Player's party; if not, add them and return True

        :param player: Player object
        :param party_addition: Ally, Monster or Player
        :return: True: successful join, False: party_addition already exists in party (shouldn't happen but one
            never knows)
        """
        # FIXME: specifying 'party_addition: Ally | Monster | Player' leads to an unresolved reference error
        # check that party_addition is not self:
        if party_addition is self:
            player.output(f"This is getting a bit surreal. You can't add {self.name} to {self.name}'s party.")
            return False
        # make sure a party_addition is not already in the party:
        if party_addition in self.party:
            player.output(f"Seeing another {party_addition.name} is already in your party, they turn sadly away.")
            return False
        self.party.append(party_addition)
        player.output(f"{party_addition.name} joins {self.name}'s party!")
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

    def output(self, text_lines: str | list) -> "Message":
        """
        Print <text_lines> in client's Translation, word-wrapped to client's column width to Player.
        A null string outputs a blank line.

        :param text_lines: text to output (can be either a list of strings or a single string)
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
        
        if self.client_settings.translation == Translation.PETSCII:
            codec = "petscii_c64en_lc"
            temp = string.encode(codec)
            logging.debug(repr(temp))  # don't print Commodore color codes to Linux terminal
        """
        from server import Message
        from tada_utilities import text_pager

        final_output_lines = []

        if isinstance(text_lines, str):
            # Process a single string, which might result in multiple wrapped lines
            processed_lines = self.process_single_line(text_lines)
            final_output_lines.extend(processed_lines)  # Use extend for multiple lines from one input
        elif isinstance(text_lines, list):
            # Process each string in the list
            for line in text_lines:
                processed_lines = self.process_single_line(line)
                final_output_lines.extend(processed_lines)  # Use extend here too

        # Use text_pager if lines > screen rows
        if len(final_output_lines) >= self.client_settings.screen_rows:
            text_pager(final_output_lines, self)
        # otherwise, print each line from the flattened list without paging:
        for line in final_output_lines:
            if line == '':
                print()
            else:
                print(line)

        # The Message object should receive a flat list of strings
        return Message(lines=final_output_lines)

    def process_single_line(self, raw_input: str) -> list[str]:
        """
        Apply text wrapping, bullet point formatting and highlighting to a single string,
        returning a list of wrapped lines.

        :param self: Player object (to infer line ending options)
        :param raw_input: string to process
        """
        from colorama import Fore
        import re
        from tada_utilities import bulleted_list_format

        # turn empty string into newline (TODO: from player.client_settings.line_ending
        if raw_input == '':
            return [""]

        column_width = self.client_settings.screen_columns
        logging.debug("width: %i | raw_input: %s" % (column_width, raw_input))

        # Apply highlighting before wrapping to avoid breaking color codes
        # TODO: handle player's highlight / normal color preferences
        # This regex is correct for [text] -> RED text
        highlighted_line_content = re.sub(r'\[(.+?)]', f'{Fore.RED}' + r'\1' + f'{Fore.RESET}', string=raw_input)

        # textwrap.fill returns a single string, which might contain newline characters if the input
        # had them or if it needed to break lines itself.
        # To get a list of lines, use textwrap.wrap and then join or just handle it directly.
        # textwrap.fill already handles wrapping, but if you want lines as separate strings,
        # you might need to split it if it has internal newlines.
        # Assuming textwrap.fill always returns a single string *without* internal newlines
        # UNLESS the original raw_input had them, and we want to ensure each element in the
        # returned list is a single visual line.

        wrapped_text = textwrap.fill(text=highlighted_line_content, width=column_width)

        # process lines into bulleted text:
        if wrapped_text.startswith("* "):
            wrapped_text = bulleted_list_format(wrapped_text[2:], column_width)

        # textwrap.fill *might* introduce newlines. We want to return a list of distinct lines.
        # So, we split by newline to ensure each element is a single line.
        return wrapped_text.splitlines()

    def set_silver_absolute(self, kind: "PlayerMoneyTypes", amount: int):
        try:
            self.silver[kind] = amount
            logging.debug("kind: %s, amount: %i" % (kind, amount))
        except KeyError:
            logging.warning("kind: invalid type %s" % kind)

    def get_flag(self, flag_name: "PlayerFlags") -> Optional["Flag"]:
        """
        Given a PlayerFlagName Enum, return the Flag object
        :param flag_name: name of flag
        :return: Flag object

        >>> rulan = Player()  # instantiate p, show Admin flag object:

        >>> # - Show Admin flag object:
        
        >>> print(f"{rulan.get_flag(PlayerFlags.ADMIN)}")
        """
        current = self.flags.get(flag_name)
        if current:
            logging.debug("flag: %s" % current)
            return current
        else:
            logging.warning("get_flag: no flag %s" % flag_name)
            return None

    def set_flag(self, flag: "PlayerFlags") -> None:
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

    def clear_flag(self, flag: "PlayerFlags") -> None:
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

    def show_flag(self, flag: "PlayerFlags") -> str | None:
        """
        Display the flag name, ":", and its display_name status.
        :param flag: Flag name to display
        :return: str

        >>> test_player = Player(name="test")

        >>> print(test_player.show_flag(PlayerFlags.UNCONSCIOUS))
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

    def show_flag_line_item(self, flag: "PlayerFlags", leading_num: Optional[int]) -> str | None:
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
            display_type: FlagDisplayTypes = temp.display_type
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

    def show_flag_status(self, flag: "PlayerFlags") -> str:
        """
        Show a flag's status.
        :param flag: PlayerFlagName to display the status of
        :return: Appropriate string for flag DisplayType

        >>> rulan = Player()

        >>> rulan.show_flag_status(PlayerFlagName.UNCONSCIOUS)
        'No'
        """
        from flags import FlagDisplayTypes
        temp = self.flags[flag]
        if temp.display_type is FlagDisplayTypes.YESNO:
            result = "Yes" if temp.status else "No"
        elif temp.display_type is FlagDisplayTypes.ONOFF:
            result = "On" if temp.status else "Off"
        else:
            logging.error("invalid type %s for flag %s" % (temp.display_type, temp.name))
            result = "<<error>>"
        return result

    def toggle_flag(self, flag: "PlayerFlags", verbose=False):
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

    def put_flag(self, name: "PlayerFlags", display_type: "FlagDisplayTypes", status: bool):
        from flags import Flag
        # FIXME: seems like put_flag should know the display_type of the PlayerFlags object and
        #  not need to be specified in the function call
        logging.debug("%s put as %s" % (name, status))
        self.flags[name] = Flag(name, display_type, status)

    def query_flag(self, flag: "PlayerFlags") -> bool:
        """Returns the status (True/False) of specified Flag object to caller"""
        result = self.get_flag(flag)
        return result.status

    def show_stat(self, stat_name: "PlayerStat") -> str:
        logging.debug(f"show_stat: %s" % stat_name.value)
        x = self.get_stat(stat_name)
        return f"{stat_name.value}: {x}"

    def adjust_stat(self, stat: "PlayerStat", adjustment: int, verbose: bool = True, abbreviate: bool = True):
        from base_variables import STAT_DATA
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
            # 'You feel less intelligent. (Intelligence -4)'

    def get_multiple_stats(self, stat_list: list["PlayerStat"]) -> list | None:
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
                result = self.stats.get(i)
                results.append(result)
                logging.debug("get %s: %i" % (i, result))
            return results
        except IndexError:
            logging.warning("get_stat: no such statistic %s" % stat_list)
            return None

    def print_all_stats(self, abbreviate=False):
        """
        Print all player stats in title case: '<Stat>: <value>'
        Should call `print_stat()` to save overhead.
        Let the calling routine worry about string justification.

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
        Dex:  3   Wis:  3

        >>> for stat in rulan.stats:
        ...     print(f'{f"{stat}".rjust(15)}: {self.stats[stat]}')

           Charisma: 2
       Constitution: 2
          Dexterity: 15
             Energy: 18
       Intelligence: 5
           Strength: 15
             Wisdom: 18
"""

        for stat in [PlayerStat.CHR, PlayerStat.INT, PlayerStat.EGY]:
            print(f'Method 1: {self.print_stat(stat, False)}', end='')
            print(f'Method 2: {stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in [PlayerStat.CON, PlayerStat.STR]:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in [PlayerStat.DEX, PlayerStat.WIS]:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()

    def print_one_stat(self, stat_name: "PlayerStat", abbreviations: bool = False):
        """
        Print a single statistic. This is a convenience method for print_all_stats().

        :param stat_name: stat to print
        :param abbreviations: use full word for stat name (True: e.g., "Intelligence", False: "Int")
        """
        print(f'{stat_name.name}: {self.stats[stat_name]}')
        if abbreviations:
            print(f'{stat_name.title()}: {self.stats[stat_name]}')

    def get_silver(self, kind: "PlayerMoneyTypes") -> int | None:
        """
        Get the amount of silver the player has for a specific money type.

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

    def add_silver(self, kind: "PlayerMoneyTypes", amount: int) -> bool:
        """
        Adds a specified amount of silver to an account.

        :param kind: The account to modify (e.g., in_hand, in_bank).
        :param amount: The positive amount of silver to add.
        :return: True, as adding silver should always succeed.
        """
        from flags import PlayerFlags
        # Use abs() to ensure the amount is always positive
        original_amount = self.silver[kind]
        amount_to_add = abs(amount)
        total = original_amount + amount_to_add

        self.silver[kind] += amount_to_add
        logging.info("Before: %i, Added %i silver, total %i" % (original_amount, amount_to_add, total))
        if not self.query_flag(PlayerFlags.EXPERT_MODE):
            self.output(f"({amount_to_add:,} was added to your silver.)")

        return True

    def subtract_silver(self, kind: "PlayerMoneyTypes", amount: int) -> bool:
        """
        Subtracts a specified amount of silver from an account.

        :param kind: The account to modify.
        :param amount: The positive amount of silver to subtract.
        :return: True if the subtraction was successful, False if there were insufficient funds.
        """
        from flags import PlayerFlags
        from base_classes import PlayerMoneyTypes

        logging.info("silver in hand: %i" % self.silver[PlayerMoneyTypes.IN_HAND])
        # Use abs() to ensure the amount is always positive
        amount_to_subtract = abs(amount)

        # Check if the player has enough silver
        logging.debug("price: %i, silver: %i" % (amount_to_subtract, self.silver[kind]))
        if self.silver[kind] >= amount_to_subtract:
            self.silver[kind] -= amount_to_subtract
            if not self.query_flag(PlayerFlags.EXPERT_MODE):
                self.output(f"({amount_to_subtract:,} was subtracted from your silver.)")
            return True
        else:
            # Not enough silver
            if not self.query_flag(PlayerFlags.EXPERT_MODE):
                self.output("(You do not have enough silver for that.)")
            return False

    def adj_silver_relative(self, kind: "PlayerMoneyTypes", relative_amt: int) -> bool:
        """
        Adjusts silver by calling the add or subtract functions.
        This maintains backward compatibility.
        """
        from flags import PlayerFlags
        if relative_amt >= 0:
            return self.add_silver(kind, relative_amt)
        else:
            # Pass the absolute value to subtract_silver
            return self.subtract_silver(kind, abs(relative_amt))

    def is_magic_user(self):
        """
        Shorter than repeating "if char.class_name == 'witch' or char.class_name == 'wizard'"

        :param self: self object
        :return: gender-appropriate magic user class name (Witch or Wizard)
        """
        # FIXME: this is still undergoing testing - I want to have character creation display appropriate class
        #   when gender changes -- can this be done with some logic in the __str__() method?
        return "Wizard" if self.gender is Gender.MALE else "Witch"

    def set_stat_absolute(self, stat: "PlayerStat", value: int):
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
        
        >>> set_stat_test = Player()

        >>> set_stat_test.set_stat_absolute(PlayerStat.INT, 15)

        >>> set_stat_test.print_stat(PlayerStat.INT, abbreviated=True)
        Int: 15

        >>> set_stat_test.set_stat_absolute(PlayerStat.WIS, 9)

        >>> set_stat_test.print_stat(PlayerStat.WIS, abbreviated=False))
        Wisdom: 9

        # test of Character.set_stat()
        >>> shaia = Player(name="Shaia",
        ...                connection_id=2,
        ...                client={'name': 'TADA', 'columns': 80, 'rows': 25},
        ...                gender=Gender.FEMALE)

        >>> shaia.set_stat_absolute(PlayerStat.INT, 18)

        >>> print(f"{shaia.name} ...... {shaia.print_stat([PlayerStat.INT])}")  # the longer method
        Shaia ...... Int: 18
        """

    def get_stat(self, stat: "PlayerStat") -> int | None:
        """
        if 'stat' is str: return value of single stat as str: 'stat'

        :return: value of single stat as int: 'stat', or None if stat doesn't exist
        TODO: if 'stat' is list: sum up contents of list: [PlayerStat.STR, PlayerStat.WIS, PlayerStat.INT]...
        TODO: refactor get_multiple_stats() to accept a list of PlayerStats, then for each stat, call get_stat()
            -- avoids multiple confusing function calls trying to do too much
        """
        try:
            return self.stats[stat]
        except KeyError:
            logging.warning("Stat '%s' doesn't exist." % k)
            # TODO: raise ValueError?
            return None

    def get_one_stat(self, stat: "PlayerStat") -> str | None:
        """
        :param stat: PlayerStat to retrieve
        :return: statistic value, or None if stat_list empty, or IndexError is encountered
        """
        if not stat:
            logging.error("No stats provided")
            return None
        try:
            return self.stats[stat]
        except IndexError:
            logging.error("No stat %s" % stat)
            return None

    def print_stat(self, stat: "PlayerStat", abbreviated: bool):
        """
        Print player stat in title case: '<Stat>: <value>' on a single line.
        Cha: 10

        print_multiple_stats() uses this function as a helper:
        Cha: 10   Dex: 15   Int: 9

        :param stat: a single PlayerStat Enum(s) to report
        :param abbreviated: False: 'Int', 'Str', 'Wis', etc. True: 'Intelligence', 'Strength', 'Wisdom', etc.
        :return: None

        >>> test = Player()
        
        >>> test.set_stat_absolute(PlayerStat.CHR, 10)  # set Charisma to 10

        >>> test.print_stat(stat=PlayerStat.CHR, abbreviated=False)
        Charisma: 10
        """
        from base_variables import STAT_DATA
        try:
            print(f"{STAT_DATA['name'][abbreviated]}: {stat.value}")
        except IndexError:
            logging.warning("Stat '%s' doesn't exist." % stat)
            # TODO: raise ValueError?
            return None

    def print_multiple_stats(self, stat_list: list["PlayerStat"],
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
            self.last_connection = datetime.datetime.now()
            logging.info("%s connected at %s" % (self.name, self.last_connection))
            # TODO: notify other players in same room of connection ("%s wakes up.")
            # TODO: watchfor list: ("[Somewhere in the land, ]%s has woken up / fallen asleep.")
            #    ("Somewhere in the land, " printed if not in the same room.)

    def move(self, destination_room: int, direction=None):
        """
        remove player login id from list of players in current_room, add them to room next_room

        :param destination_room: room to move to
        :param direction: the direction being moved in, for notifying other players of movement
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
            logging.error("Player ID '%s' not found" % user_id)
            return None

    def save(self):
        # TODO: should a 'changes' flag be implemented to prevent saving if changes haven't been made?
        with open(Player._json_path(self.id), 'w') as json_file:
            json.dump(obj=self, fp=json_file, default=lambda o: {k: v for k, v
                                                                 # in o.__dict__.items() if v}, indent=4)
                                                                 in o.__dict__.items()}, indent=4)
            logging.debug("Player.save: Saved '%s'." % self.name)

    def adj_stat_relative(self, stat: "PlayerStat", adjustment: int):
        logging.debug("TODO: move this in")

    def show_combinations(self):
        logging.info("Finish this")


def transfer_silver(from_char: "Player", to_char: "Player", amount: int,
                    from_where: "PlayerMoneyTypes" = "PlayerMoneyTypes.IN_HAND",
                    to_where: "PlayerMoneyTypes" = "PlayerMoneyTypes.IN_HAND",
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
    >>> transfer_silver(from_char=shaia, to_char=rulan, amount=500,
    ...                 from_where=PlayerMoneyTypes.IN_HAND,
    ...                 to_where=PlayerMoneyTypes.IN_HAND)
    False

    # Rulan has 100 silver in hand, so this will succeed:
    >>> transfer_silver(from_char=shaia, to_char=rulan, amount=100,
    ...                 from_where=PlayerMoneyTypes.IN_HAND,
    ...                 to_where=PlayerMoneyTypes.IN_HAND)
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
    from base_classes import PlayerStat

    rulan_settings = {"name": "Rulan"}
    rulan = Player(**rulan_settings)
    rulan.adjust_stat(PlayerStat.WIS, -5, True, True)
