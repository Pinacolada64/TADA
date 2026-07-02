# FIXME: PLAYERS.PY IS OUTDATED. MIGRATE BETTER CODE TO PLAYER.PY, THEN DELETE IT.

import doctest
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# TADA-specific:
import flags
from flags import PlayerFlags
from base_classes import Gender, PlayerMoneyTypes, PlayerMoneyCategory, PlayerStat


# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/


@dataclass
class Character(object):
    import flags  # new_player_default_flags
    name: str
    flags: dict[flags.PlayerFlags, flags.Flag] = field(default_factory=lambda: {i[0] for i in
                                                                                flags.new_player_default_flags})

@dataclass
class Player:
    # TODO: THIS DOES NOT WORK ANYMORE. compare player.py and players.py; MOVE BETTER CODE INTO PLAYER.PY
    # Copy list of Flag defaults from PlayerFlag enum on Player instantiation:
    from flags import Flag
    flags: dict[flags.PlayerFlags, flags.Flag] = field(default_factory=lambda: {i[0]: flags.Flag(*i) for i in flags.player_flag_data})
    stat: dict[PlayerStat, int] = field(default_factory=lambda: {i: 0 for i in PlayerStat})
    silver: dict[PlayerMoneyTypes, int] = field(default_factory=lambda: {i: 1_000 for i in PlayerMoneyTypes})

    def get_flag(self, name: PlayerFlags) -> Flag:
        """
        Given a PlayerFlagName, return the Flag object
        :param name: name of flag
        :return: Flag object
        """
        logging.debug("%s" % self.flags.get(name))
        return self.flags.get(name)

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
            logging.debug("show_flag: enter: flag: %s" % flag_name)
            temp = self.get_flag(flag)
            # flag_name = temp.name
            display_type = temp.display_type
            status = temp.status
            logging.debug("flag_name=%s, display_type=%s, status=%s" % (flag_name, display_type, status))
            result = self.show_flag_status(flag)
            return f"{flag_name}: {result}"
        except KeyError:
            logging.warning("show_flag: unknown flag: %s" % flag.name)

    def show_flag_line_item(self, flag: PlayerFlags, leading_num: int) -> str | None:
        """
        Display the flag status based on its display_type string.
        The flag is listed prefixed with leading_number, "...:" and the status.

        :param flag: Flag name to display
        :param leading_num: used with dot_leader, True prefixes the flag display with this number
        :param max_width: how many dot leaders to display between the flag and its status
        :return: str
        """
        """
        >>> test_player = Player()
        
        >>> test_player.clear_flag(PlayerFlag.UNCONSCIOUS)

        >>> print(test_player.show_flag_line_item(PlayerFlagName.UNCONSCIOUS, leading_num=1))
         1. Unconscious...............: No
        """
        try:
            """
            >>> print(PlayerFlagName.UNCONSCIOUS.value)
            'Unconscious'
            """
            max_width = flags.longest_flag_name()
            logging.debug("show_flag_line_item: enter: flag: %s, leading_num: %i, max_width: %i" % (flag, leading_num, max_width))
            temp = self.get_flag(flag)
            flag_name, display_type, status = temp.name.value, temp.display_type, temp.status
            logging.debug("show_flag_line_item: flag_name=%s, display_type=%s, status=%s" % (flag_name, display_type, status))
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

        >>> rulan.show_flag_status(PlayerFlags.UNCONSCIOUS)
        'No'
        """
        from flags import FlagDisplayTypes
        temp = self.flags[flag]
        if temp.display_type is FlagDisplayTypes.YESNO:
            result = "Yes" if temp.status else "No"
        elif temp.display_type is FlagDisplayTypes.ONOFF:
            result = "On" if temp.status else "Off"
        else:
            logging.error("show_flag_status: invalid type %s for flag %s" % (temp.display_type, temp.name))
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

    def show_stat(self, stat_name: PlayerStat) -> str:
        logging.debug(f"show_stat: %s" % stat_name.value)
        x = self.get_stat(stat_name)
        return f"{stat_name.value}: {x}"

    def adjust_stat(self, stat_name: PlayerStat, adjustment):
        current = self.get_stat(stat_name)
        new = current + adjustment
        logging.debug("adjust_stat: current: %s: %i, adjusted: %i" % (stat_name.name, current, new))
        self.put_stat(stat_name, new)

    def get_stat(self, stat_name: PlayerStat) -> int | None:
        for key, value in self.stat.items():
            if stat_name.value == key:
                logging.debug("get_stat: get %s: %i" % (stat_name.value, value))
                return value
        return None

    def put_stat(self, stat_name: PlayerStat, value) -> None:
        logging.debug("put_stat: put %s: %i" % (stat_name.value, value))
        self.stat[stat_name] = value

@dataclass
class TodoPlayer(Character):
    super().__init__()
    """
    Attributes, flags and other stuff about players.
    """
    """
    There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
            (is it important to know whether the player or ally is carrying an item?)
            maybe return Player or Ally object if they hold it, or None if no-one holds it
    """

    # this code is called when creating a new character
    connection_id: int
    gender: Gender
    # specifying e.g., 'hit_points=None' makes it a required parameter

    # FIXME: probably just forget this, net_server.py handles connected_users(set)
    """
    connection_id: list of CommodoreServer IDs: {'connection_id': id, 'login_name': 'name'}
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
    connection_id: int  # TODO: keep this until I figure out where it is in net_server.py
    login_name: str

    gender: Gender
    """
    # stats: str = "abc"
    # set with Player.set_stat(PlayerStat.Enum, val)
    logging.debug("Player.__init__: stats: %s" % stats)
    """
    logging.debug("Player.__init__: flags: %s" % flags)

    # creates a new silver dict for each Player:
    # in_bank may be cleared on character death (TODO: look in TLOS source)
    # in_bar should be preserved after character's death (TODO: same)
    # use Player.set_silver("kind", value)
    # logging.info(f'Player.__init__: Silver in hand: {self.silver["in_hand"]}')

    # client settings - set up some defaults
    client: dict[ClientSettings, int | str] = field(default_factory=lambda: {i for i in ClientSettings})

    age: int
    birthday: datetime.date
    """
    proposed stats:
    some (not all) other stats, still collecting them:
    """
    times_played: int
    last_play_date: datetime # (month, day, year) like birthday

    special_items: list
    # Weapon(weapon_percentage{'weapon': percentage [, ...]}
    # weapon_ammunition{'weapon': ammo_count [, ...]}
    # bad_hombre_rating is calculated from stats, not stored in player log
        
    once_per_day: list  # things you can only do once per day (file_formats.txt)
    # 'pr'    has PRAYed once
    # 'pr2'   can PRAY twice per day (only if player class is Druid)


    def __str__(self):
        """print formatted Player object (double-quoted since ' in string)"""
        _ = f"Name: {self.name}\t\t"
        f"Age: {'Undetermined' if self.age == 0 else '{self.age}'}"
        f'\tBirthday: {self.birthday[0]}/{self.birthday[1]}/{self.birthday[2]}\n'
        f"Silver: In hand: {self.gold['in_hand']}\n"
        f'Guild: {self.guild}\n'
        return _

    def set_stat(self, stat: str, adj: int):
        """
        :param stat: statistic in stats{} dict to adjust
        :param adj: adjustment (+x or -x)
        :return: stat, maybe also 'success': True if 0 > stat > <limit>

        TODO: example for doctest:
        >>> rulan = Player()

        >>> rulan.set_stat[PlayerStat.STR, -5]  # decrement Rulan's strength by 5
        """
        try:
            # adjust stat by <adjustment>:
            before = self.stats[stat]
            after = before + adj
            logging.info(f"set_stat: Before: {stat=} {before=} {adj=}")
            if self.query_flag(PlayerFlags.EXPERT_MODE) is False:
                descriptive = zip(['chr', 'con', 'dex', 'int', 'str', 'wis', 'egy'],
                                  ['influential', 'hearty', 'agile', 'intelligent',
                                   'strong', 'wise', 'energetic'])
                # TODO: jwhoag suggested adding 'confidence' -> 'brave' -- good idea,
                #  not sure where it can be added yet.
                # returns ('con', 'hearty') -- etc.
                for n in descriptive:
                    # FIXME: I don't know of a more efficient way to refer to a subscript in this case.
                    #  This may be good enough, it's a small loop
                    if n[0] == stat:
                        print(f"You feel {'more' if after > before else 'less'} {n[1]}.")
            logging.info(f"set_stat: After: {stat=} {after=}")
            self.stats[stat] = after
        except KeyError:
            # TODO: raise ValueError?
            logging.warning("Player.set_stat: Stat %s doesn't exist." % stat)

    def get_stat(self, stat):
        """
        if 'stat' is str: return value of single stat as str: 'stat'
        TODO: if 'stat' is list: sum up contents of list: ['str', 'wis', 'int']...
        -- avoids multiple function calls
        """
        if type(stat) is list:
            total = 0
            for k in stat:
                if stat not in self.stats:
                    logging.warning(f"get_stat: Stat {stat} doesn't exist.")
                    # TODO: raise ValueError?
                    return None
                total += self.stats[k]
            logging.info(f'get_stat[list]: {stat=} {total=}')
            return total
        # otherwise, get just a single stat:
        if stat not in self.stats:
            logging.warning(f"get_stat: Stat {stat} doesn't exist.")
            # TODO: raise ValueError?
            return None
        return self.stats[stat]

    def print_stat(self, stat: str):
        """
        # print player stat in title case: '<Stat>: <value>'

        # for doctest
        >>> rulan = Player(name="rulan")

        >>> rulan.print_stat(PlayerStat.INT, abbreviate=True)
        Int: 5
        """
        if stat not in self.stats:
            logging.warning(f"get_stat: Stat {stat} doesn't exist.")
            # TODO: raise ValueError?
            return None
        # return e.g., "Int: 4"
        return f'{stat.title()}: {self.stats[stat]}'

    def print_all_stats(self):
        """
        print all player stats in title case: '<Stat>: <value>'

        for doctest eventually
        >>> Rulan = Player(name="rulan")

        >>> rulan.print_all_stats()
        Chr:  8   Int:  5   Egy:  3
        Con: 15   Str:  8
        Dex:  3   Wis:  3
        """
        for stat in ['chr', 'int', 'egy']:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in ['con', 'str']:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in ['dex', 'wis']:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()

    def get_silver(self, kind):
        """
        get and return amount of silver player has
        'kind': 'in_hand', 'in_bank', or 'in_bar'
        """
        if kind not in self.silver:
            logging.info(f"get_silver: Bad type '{kind}'.")
            return None
        logging.info(f'get_silver: {self.silver[kind]}')
        return self.silver[kind]

    def set_silver(self, kind: str, adj: int):
        """
        :param kind: 'in_hand', 'in_bank' or 'in_bar'
        :param adj: amount to add (<adj>) or subtract (-<adj>)
        :return: None
        """
        before = self.silver[kind]
        # TODO: check for negative amount
        after = before + adj
        if after < 0:
            logging.info(f'set_silver: {after=}, negative amount not allowed')
            return
        self.silver[kind] = after


def transfer_money(receiver: Player, giver: Player, kind: str, adj: int):
    """
    :param receiver: Player to transfer <adj> gold to
    :param giver: Player to transfer <adj> gold from
    :param kind: classification ('in_hand' most likely)
    :param adj: amount to transfer
    :return: none
    """
    # as suggested by Shaia:
    # (will be useful for future bank, or future expansion: gold transfer spell?)
    if giver.silver[kind] >= adj:
        receiver.set_silver(kind, adj)
        giver.set_silver(kind, -adj)
        logging.info(f'transfer_money: {giver.name} {adj} {kind} -> {giver.name}: {giver.silver[kind]}')
        print(f'{giver.name} transferred {adj} silver {kind} to {receiver.name}.')
        print(f'{receiver.name} now has {receiver.silver[kind]}.')
    else:
        print(f"{giver.name} doesn't have {adj} silver to give.")


class Ally(object):
    def __init__(self):
        """
        Ally['name'][stat], position: str
        where (as in TLOS): empty=0, lurking=1, point=2, flank=2, rear=3,
            (guard=4?), unconscious=5 (in python I will spell out positions as strings)
        abilities[

        flags[              # | = TLOS ally string postfix, then:
            'elite': bool   # !
            'mount': bool   # =
            'body_build': bool  # #nn <nn=1...25?> Not clear what this is for, Str improvement?
             # TODO: find ally guild code
            ]
        silver: int
        """
        pass


class Horse(object):
    def __init__(self):
        """
        horse[name: str, have_horse: bool, armor: int, saddlebags: bool,
        saddle: bool, armor: int, training: bool (I think), mounted_on_horse: bool,
        lasso: bool
        inventory[]  # mash, hay, oats, apples, sugar cubes
        ]
        """
        pass


if __name__ == '__main__':
    # import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    import doctest

    # doctest.testmod(verbose=True)

    # connection_ids = []  # initialize empty list for logging connection_id's

    rulan = Player()
    rulan.name = "Rulan"
    rulan.connection_id = 1
    rulan.client = {'name': 'Commodore 128', 'columns': 80}
    rulan.flags = {'dungeon_master': True, 'debug': True, 'expert_mode': False}

    print(rulan)
    rulan.set_stat('int', 5)
    print(f"{rulan.print_stat('int')}")  # show "Int: 5", this passes

    rulan.set_stat('int', 4)  # add to rulan's Intelligence of 5, total 9
    print(f"{rulan.print_stat('int')}")  # show "Int: 9", this passes
    # when print_stat returned None, had to do this:
    # print(f'rulan ...... ', end='')
    # rulan.print_stat('int')  # should print 'rulan ...... Int: 9'

    rulan.set_silver(kind='in_hand', adj=100)
    rulan.set_silver(kind='in_bank', adj=200)
    rulan.set_silver(kind='in_bar', adj=300)

    print(f"Silver in bank: {rulan.get_silver('in_bank')}")  # should print 200, this passes

    rulan.print_all_stats()

    Shaia = Player(name="Shaia",
                   connection_id=2)
    Shaia.client = {'name': 'TADA', 'columns': 80, 'rows': 25}
    Shaia.flags = {'expert_mode': True, 'debug': True}

    Shaia.set_stat(stat='int', adj=18)
    print(f"Shaia ...... {Shaia.print_stat('int')}")  # should print 'Shaia ...... Int: 18': passes

    # when print_stat returned None, did this:
    # print(f'Shaia ...... ', end='')
    # Shaia.print_stat('int')  # should print 'Shaia ...... Int: 18'

    Shaia.set_silver(kind='in_hand', adj=10)
    Shaia.set_silver(kind='in_bank', adj=200)
    Shaia.set_silver(kind='in_bar', adj=300)

    Shaia.print_all_stats()

    transfer_money(Shaia, rulan, kind='in_hand', adj=500)  # should rightfully fail
    transfer_money(Shaia, rulan, kind='in_hand', adj=100)  # this passes
