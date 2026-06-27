import logging
import random
from dataclasses import dataclass
import datetime
from enum import Enum, auto
import textwrap
import doctest

import terminal
from flags import Flag, new_player_default_flags, FlagDisplayTypes
from base_classes import Combination, CombinationTypes, Alignment, Gender, PlayerMoneyTypes, PlayerStat, Guild
from terminal import KeyboardKeyName, Translation, ClientSettings


class Color(Enum):
    BLACK = auto()
    WHITE = auto()


@dataclass
class Client:
    name: str = "Generic Client"
    rows: int = 40
    columns: int = 25
    translation: Translation = Translation.ANSI
    # colors for [bracket reader] text highlighting on C64/128:
    text: Color = Color.WHITE
    highlight: Color = Color.BLACK
    background: Color = Color.BLACK
    border: Color = Color.BLACK

    def __str__(self):
        """Return a formatted string showing all client settings"""
        settings = f"""{'Client Settings:'.rjust(17)}
{'Client Name:'.rjust(17)} {self.name.title()}
{'Screen Rows:'.rjust(17)} {self.rows}
{'Screen Columns:'.rjust(17)} {self.columns}
{'Translation:'.rjust(17)} {self.translation.name.title()}
{'Text Color:'.rjust(17)} {self.text.name.title()}
{'Highlight Color:'.rjust(17)} {self.highlight.name.title()}
{'Background Color:'.rjust(17)} {self.background.name.title()}
{'Border Color:'.rjust(17)} {self.border.name.title()}
"""
        return textwrap.dedent(settings)


def make_random_id():
    random_number = random.randint(1, 65_535)
    logging.debug("%i", random_number)
    return random_number


def make_random_stat():
    random_number = random.randint(1, 18)
    logging.debug("%i", random_number)
    return random_number


def set_up_combinations():
    combos = [
        Combination(CombinationTypes.CASTLE),
        Combination(CombinationTypes.ELEVATOR),
        Combination(CombinationTypes.LOCKER)
    ]
    return combos


def set_up_flags():
    flags = {i[0]: Flag(*i) for i in new_player_default_flags}
    logging.info("flags: %s" % flags)
    return flags


def set_up_silver() -> dict:
    silver_types = {v: k * 1_000 for k, v in enumerate(PlayerMoneyTypes, start=1)}
    logging.info("%s" % silver_types)
    return silver_types


def set_up_stats() -> dict:
    stats = {k: make_random_stat() for k in PlayerStat}
    logging.debug("%s" % stats)
    return stats


def set_up_rulan() -> dict:
    birthday = datetime.date(1976, 6, 16)
    last_play_date = datetime.date.today()
    logging.info("Setting up Rulan.")
    return {'name': 'Rulan',
            'times_played': None,  # this marks a new player
            'guild': Guild.FIST,
            'birthday': birthday,
            'last_play_date': last_play_date,
            }


def set_up_terminal():
    client_settings = terminal.ClientSettings()
    logging.debug(client_settings)
    return client_settings


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
        # combinations:
        self.combinations = kwargs.get('combinations', set_up_combinations())

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

        # client settings - set up some defaults
        self.client_settings = kwargs.get('client', set_up_terminal())
        self.client_settings.return_key = KeyboardKeyName.ENTER

        self.times_played = kwargs.get('times_played')
        self.last_play_date = kwargs.get('last_play_date', datetime.datetime.today())  # like birthday

        """
        proposed stats:
        some (not all) other stats, still collecting them:

        special_items:
            SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
            BOAT does not actually need to be carried around in inventory, I don't suppose, just a flag?
        """
        self.map_level = kwargs.get('map_level', 1)  # cl (current level)
        self.map_room = kwargs.get('map_room', 1)  # cr (current room)
        self.moves_made = kwargs.get('moves_made', None)
        # tracks how many moves made during the game session to calculate experience points awarded at quit:
        self.moves_today = kwargs.get('moves_today', 0)
        self.birthday = kwargs.get('birthday', datetime.datetime.today())  # use datetime
        self.guild = kwargs.get('guild', Guild.CIVILIAN)  # [civilian | fist | sword | claw | outlaw]
        # 1       2        3       4      5       6       7         8       9
        self.char_class = kwargs.get('char_class')
        # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
        self.char_race = kwargs.get('char_race')
        # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf

        self.hit_points = kwargs.get('hit_points', 0)
        # combat stuff:
        # the lower the Honor score, the more evil the character has become.
        # TODO: look it up, but I think 1,000 honor points is equivalent to a Saintly Knight.
        self.honor = kwargs.get('honor', 1_000)
        self.natural_alignment = kwargs.get("natural_alignment", Alignment.NEUTRAL)
        self.current_alignment = kwargs.get("current_alignment", Alignment.NEUTRAL)

        self.allies = kwargs.get('allies')
        self.horse = kwargs.get('horse')

        self.shield = kwargs.get('shield')
        self.armor = kwargs.get('armor')
        self.experience = kwargs.get('experience', 0)
        self.monsters_killed: list[int] = kwargs.get('monsters_killed', [])
        """
        TODO: MORE CLASSES
        combat:
            honor: int
        class Weapon:
            percent_left: int
        class AmmoWeapon:
            ammunition_for: Weapon
            loaded_with: Ammunition
        class Ammunition:
            rounds_per_unit: int  # how many rounds

        bad_hombre_rating (BHR) is calculated from stats, not stored in player log

        once_per_day[] flags:  # things you can only do once per day (file_formats.txt)
            'pr'    has PRAYed once
            'pr2'   can PRAY twice per day (only if player class is Druid)
            'birthday' for preventing player from collecting birthday bonuses multiple times on birthday
                       by logging in/out multiple times
        """
        self.unsaved_changes = True

    def __str__(self):
        """print formatted Player object (just random info for now to test)"""
        age = "Undetermined"
        date_format_string = "%a %b %d, %Y"  # weekday month date, year
        combinations = [f'{c.name.rjust(15)}: {c.combination}' for c in self.combinations]
        if self.birthday:
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

    def set_stat(self, stat: PlayerStat, adj: int):
        """
        :param stat: statistic in stats{} dict to adjust
        :param adj: adjustment (+x or -x)
        :return: stat, maybe also 'success': True if 0 > stat > <limit>

        TODO: example for doctest:
        >>> rulan = Player(**set_up_rulan())

        >>> rulan.adjust_stat_relative(PlayerStat.STR, -5)  # decrement Rulan's strength by 5
        """
        from flags import PlayerFlags
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

    def flag_set(self):
        pass

    def set_stat_absolute(self, stat: PlayerStat, adj: int) -> None:
        current = self.stats.get(stat)
        if current:
            self.stats[stat] = adj
            logging.info("%s was %i, now %i" % (stat, current, adj))
        else:
            logging.info("Couldn't find stat %s" % stat)
        return None

    def adjust_stat_relative(self, stat: PlayerStat, adj: int) -> bool:
        current = self.stats.get(stat)
        if current:
            logging.info("%s was %i, now %i" % (stat, current, adj))
            self.stats[stat] = current - adj
            return True
        else:
            logging.info("Player stat %s does not exist" % stat)
            return False

    def get_stat(self, stat: PlayerStat):
        """
        if `stat` is str: return value of single stat as str: 'stat'
        if `stat` is list: return dict of stats: {PlayerStat.STR: 20, PlayerStat.WIS: 10, ...}
        -- this avoids multiple function calls
        """
        if type(stat) is list:
            total = {}
            for k in stat:
                try:
                    total.update({k: self.stats[k]})
                except KeyError:
                    logging.warning(f"Stat %s doesn't exist." % stat)
                    # TODO: raise ValueError?
            logging.info("[list]: %s total: %s" % (stat, total))
            return total
        # otherwise, get just a single stat:
        else:
            current = self.stats.get(stat)
            if current:
                return current
            else:
                logging.warning("Stat %s doesn't exist." % stat)
                # TODO: raise ValueError?
                return None

    def print_all_stats(self, abbreviate=False):
        """
        Print all player stats in title case: '<Stat>: <value>'
        Should call `print_stat()` to save overhead.
        Let the calling routine worry about string justification.
        """
        """
        >>> rulan = Player(**set_up_rulan())
        
        >>> rulan.set_stats_absolute({PlayerStat.CHR: 8,
        ...                           PlayerStat.CON: 15,
        ...                           PlayerStat.DEX: 3,
        ...                           PlayerStat.EGY: 3,
        ...                           PlayerStat.INT: 5,
        ...                           PlayerStat.STR: 8,
        ...                           PlayerStat.WIS: 3,
        ...                          })

        >>> rulan.print_all_stats(abbreviate=True)
        Chr:  8   Int:  5   Egy:  3
        Con: 15   Str:  8
        Dex:  3   Wis:  3
        """
        """
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
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in [PlayerStat.CON, PlayerStat.STR]:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in [PlayerStat.DEX, PlayerStat.WIS]:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()

    def show_combinations(self):
        _ = f"{self.combinations}"
        return _

    def get_silver(self, kind: PlayerMoneyTypes) -> int | None:
        """
        Get the amount of silver the player has for a specific money type.

        :param kind: Type of money storage (IN_HAND, IN_BANK, or IN_BAR)
        :returns int | None: Amount of silver if found, None if invalid money type

        >>> rulan = Player(**set_up_rulan())

        >>> rulan.get_silver(PlayerMoneyTypes.IN_HAND)
        1000
        """
        try:
            amount = self.silver[kind]
            logging.info("%s: %i" % (kind.value, amount))
            return amount
        except KeyError:
            logging.info("Invalid money type requested: %s" % kind.value)
            return None

    def show_silver(self, kind: PlayerMoneyTypes) -> str | None:
        """
        Show the amount of silver the player has for a specific money type.

        :param kind: Type of money storage (IN_HAND, IN_BANK, or IN_BAR)
        :returns str | None: Amount of silver if found, None if invalid money type

        >>> rulan = Player(**set_up_rulan())

        >>> rulan.show_silver(PlayerMoneyTypes.IN_HAND)
        "Silver In hand: 1,000"
        """
        try:
            amount = self.silver[kind]
            logging.info("%s: %i" % (kind.value, amount))
            return f"Silver {kind}: {amount:,}"
        except KeyError:
            logging.info("Invalid money type requested: %s" % kind.value)
            return None

    def adjust_silver(self, kind: PlayerMoneyTypes, adj: int):
        """
        Add to or subtract from a value relative to the amount already in the account.

        :param kind: PlayerMoneyTypes.IN_BANK | IN_BAR | IN_HAND
        :param adj: amount to add (<adj>) or subtract (-<adj>)
        :return: None if KeyError
        """
        before = self.silver[kind]
        # TODO: check for negative amount
        after = before + adj
        logging.info("Before: %s %i, after: %i" % (kind, before, after))
        if after < 0:
            logging.info('%i, negative amount not allowed' % after)
            return None
        self.silver[kind] = after
        return None

    def set_silver_absolute(self, kind: PlayerMoneyTypes, amount: int) -> bool:
        """
        Set the amount of silver to an absolute value for a specific type of money.

        :param kind: Type of money storage (IN_HAND, IN_BANK, or IN_BAR)
        :param amount: Amount to set
        :return: True if successful, False if invalid amount
        """
        if amount < 0:
            logging.warning("Cannot set negative silver amount: %i" % amount)
            return False

        before = self.silver[kind]
        self.silver[kind] = amount
        logging.info("Silver %s changed from %i to %i" % (kind.value, before, amount))
        return True

    def show_stat(self, stat: PlayerStat, abbreviate: bool = True) -> str | None:
        """
        Generates a string for a specific statistic.

        :param stat: The PlayerStat enum member to display.
        :param abbreviate: If True, use the short name (e.g., 'Wis').
                           If False, use the full name (e.g., 'Wisdom').
        :returns: A formatted string like "Wis: 14" or "Wisdom: 14".
        """
        try:
            # Get the stat's value from the dictionary
            stat_value = self.stats[stat]
            if abbreviate:
                # Use the enum member's built-in 'name' property (e.g., "WIS")
                stat_name = stat.name.title()
            else:
                # Use the enum member's built-in 'value' property (e.g., "Wisdom")
                stat_name = f"{stat.value}".rjust(15)
            # Return the formatted string
            return f"{stat_name}: {stat_value}"
        except AttributeError:
            # Handle cases where the stat doesn't exist for the player
            logging.error("Stat '%s' does not exist for player '%s'." % (stat.name, self.name))
            return None

    def query_flag(self, flag: Flag):
        if flag.display_type == FlagDisplayTypes.YESNO:
            return "Yes" if flag.status else "No"
        elif flag.display_type == FlagDisplayTypes.ONOFF:
            return "On" if flag.status else "Off"
        else:
            return "<Bad flag type>"

    def set_silver(self, kind: PlayerMoneyTypes, silver_amount: int):
        pass

    @classmethod
    def load(cls, user_id):
        pass


if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Info message")

    doctest.testmod(verbose=True)

    # birthday = datetime.date(1976, 6, 16)
    # print(datetime.date(2025, 6, 16).strftime("%a, %b %d %Y"))

    rulan = Player(**set_up_rulan())

    silver_amount = 499
    if not rulan.set_silver(PlayerMoneyTypes.IN_HAND, silver_amount):
        print(f"Could not set silver in hand to {silver_amount}")
    else:
        print(f"Set silver in hand to {silver_amount}.")
    if rulan.times_played is None:
        print("This is a new player.")
    print(rulan)
    print(rulan.client_settings)

    # Statistic adjusting tests:
    # 1. Create a player instance
    gandalf_settings = {'name': "Gandalf"}
    gandalf = Player(**gandalf_settings)

    right_spacing = 30

    # 2. Get the abbreviated stat string
    # Here we pass the enum member directly
    wis_abbr = gandalf.show_stat(PlayerStat.WIS, abbreviate=True)
    print(f"{'Abbreviated version: '.rjust(right_spacing)}{wis_abbr}")  # Output: Abbreviated version: WIS: 14

    # 3. Get the full name stat string
    wis_full = gandalf.show_stat(PlayerStat.WIS, abbreviate=False)
    print(f"{'Full name version: '.rjust(right_spacing)}{wis_full}")  # Output: Full name version: Wisdom: 14

    # 4. Example with another stat
    int_full = gandalf.show_stat(PlayerStat.INT, abbreviate=False)
    print(f"{'Another example: '.rjust(right_spacing)}{int_full}")  # Output: Another example: Intelligence: 18

    rulan.show_stat(PlayerStat.INT, True)
    rulan.show_stat(PlayerStat.WIS, False)
    # rulan.show_stat(PlayerStat.obviously_false, False)

    rulan.adjust_silver(PlayerMoneyTypes.IN_HAND, 3_000)
    print(rulan.show_silver(PlayerMoneyTypes.IN_HAND))

    rulan.print_all_stats()
