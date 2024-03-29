# supposed to handle passing "str | list" type-hinting to get_stat()
# but breaks print(f'string') because python 2.7? don't understand that
# from __future__ import annotations

import doctest
import logging


# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/


class Player(object):
    """
    Attributes, flags and other stuff about players.
    """
    """
    There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
            (is it important to know whether the player or ally is carrying an item?)
            maybe return Player or Ally object if they hold it, or None if no-one holds it
    """

    # def __init__(self, connection_id=None, name=None, gender=None, stats=None,
    #              flags=None, silver=None, client=None, age=None, birthday=None,
    #              guild=None, char_class=None, race=None, hit_points=None,
    #              shield=None, armor=None, experience=None):
    def __init__(self, connection_id, name, gender, stats,
                 flags, silver, client, age, birthday,
                 guild, char_class, race, hit_points,
                 shield, armor, experience):

        """this code is called when creating a new character"""
        # specifying e.g., 'hit_points=None' makes it a required parameter

        # FIXME: probably just forget this, net_server.py handles connected_users(set)
        # connection_id: list of CommodoreServer IDs: {'connection_id': id, 'name': 'name'}
        # for k in len(connection_ids):
        #     if connection_id in connection_ids[1][k]:
        #         logging.info(f'Player.__init__: duplicate {connection_id['id']} assigned to '
        #                      f'{connection_ids[1][connection_id]}')
        #     return
        # temp = {self.name, connection_id}
        # connection_ids.append({'name': name, connection_id})
        # logging.info(f'Player.__init__: Connections: {len(connection_ids)}, {connection_ids}')
        # self.connection_id = connection_id  # 'id' shadows built-in name

        self.connection_id = connection_id  # keep this until I figure out where it is in net_server.py
        self.name = name

        self.gender = gender

        # creates a new stats dict for each Player, zero all stats:
        # set with Player.set_stat('xyz', val)
        self.stats = stats
        # if self.stats is not None:
        #     self.stats = stats
        # else:
        #     self.stats = {'chr': 0, 'con': 0, 'dex': 0, 'int': 0, 'str': 0, 'wis': 0, 'egy': 0}
        print(f"stats: {self.stats}")

        # flags:
        if self.flags is not None:
            self.flags = flags
        else:
            self.flags = {'room_descriptions': bool, 'autoduel': bool, 'hourglass': bool,
                          'expert': bool, 'more_prompt': bool, 'architect': bool,
                          # TODO: orator_mode: bool # define orator_mode more succinctly
                          'hungry': bool, 'thirsty': bool, 'diseased': bool, 'poisoned': bool,
                          'debug': bool, 'dungeon_master': bool
                          }
        logging.info(f'{self.flags=}')

        # creates a new silver dict for each Player:
        # in_bank may be cleared on character death (TODO: look in TLOS source)
        # in_bar should be preserved after character's death (TODO: same)
        # use Player.set_silver("kind", value)
        if self.silver is not None:
            self.silver = silver
        else:
            self.silver = {"in_hand": 0, "in_bank": 0, "in_bar": 0}
        # logging.info(f'Player.__init__: Silver in hand: {self.silver["in_hand"]}')

        # client settings - set up some defaults
        if self.client is not None:
            self.client = client
        else:
            self.client = {'name': None, 'rows': None, 'columns': 80, 'translation': None,
                           # colors for [bracket reader] text highlighting on C64/128:
                           'text': None, 'highlight': None, 'background': None, 'border': None}

        self.age = age
        self.birthday = birthday  # tuple: (month, day, year)
        """
        proposed stats:
        some (not all) other stats, still collecting them:
    
        times_played: int
        last_play_date: tuple # (month, day, year) like birthday
    
        special_items[
            SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
            BOAT  # does not actually need to be carried around in inventory, I don't suppose, just a flag?
            combinations{'elevator', 'locker', 'castle'}  # tuple? combo is 3 digits: (nn, nn, nn)
            ]
                
        map_level: int  # cl
        map_room: int  # cr
        moves_made: int
        """
        self.guild = guild  # [civilian | fist | sword | claw | outlaw]
        #                      1       2        3       4      5       6       7         8       9
        self.char_class = char_class  # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
        self.race = race  # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf

        self.hit_points = hit_points
        self.shield = shield
        self.armor = armor
        self.experience = experience
        """
        combat:
            honor: int
            weapon_percentage{'weapon': percentage [, ...]}
            weapon_ammunition{'weapon': ammo_count [, ...]}
            bad_hombre_rating is calculated from stats, not stored in player log
        
        once_per_day[] flags:  # things you can only do once per day (file_formats.txt)
            'pr'    has PRAYed once
            'pr2'   can PRAY twice per day (only if player class is Druid)
        """

    def __str__(self):
        """print formatted Player object (double-quoted since ' in string)"""
        _ = f"Name: {self.name}\t\t"
        f"Age: {'Undetermined' if self.age == 0 else '{self.age}'}"
        f'\tBirthday: {self.birthday[0]}/{self.birthday[1]}/{self.birthday[2]}\n'
        f"Silver: In hand: {self.silver['in_hand']}\n"
        f'Guild: {self.guild}\n'
        return _

    def set_stat(self, stat: str, adj: int):
        """
        :param stat: statistic in stats{} dict to adjust
        :param adj: adjustment (+x or -x)
        :return: stat, maybe also 'success': True if 0 > stat > <limit>

        TODO: example for doctest:
        >>> Rulan.set_stat['str': -5]  # decrement Rulan's strength by 5
        """
        if stat not in self.stats:
            logging.warning(f"Stat {stat} doesn't exist.")
            # raise ValueError?
            return
        # self.stats = {'con': 0, 'dex': 0, 'ego': 0, 'int': 0, 'str': 0, 'wis': 0}
        # adjust stat by <adjustment>:
        before = self.stats[stat]
        after = before + adj
        logging.info(f"set_stat: Before: {stat=} {before=} {adj=}")
        if not self.flags['expert_mode']:
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

    def get_stat(self, stat):
        """
        if 'stat' is str: return value of single stat as str: 'stat'
        TODO: if 'stat' is list: sum up contents of list: ['str', 'wis', 'int']...
        -- avoids multiple function calls
        """
        if type(stat) is list:
            _sum = 0  # 'sum' shadows built-in type
            for k in stat:
                if stat not in self.stats:
                    logging.warning(f"get_stat: Stat {stat} doesn't exist.")
                    # TODO: raise ValueError?
                    return
                _sum += self.stats[k]
            logging.info(f'get_stat[list]: {stat=} {_sum=}')
            return _sum
        # otherwise, get just a single stat:
        if stat not in self.stats:
            logging.warning(f"get_stat: Stat {stat} doesn't exist.")
            # TODO: raise ValueError?
            return
        return self.stats[stat]

    def print_stat(self, stat: str):
        """
        print player stat in title case: '<Stat>: <value>'

        for doctest
        FIXME: eventually. can't figure out how to test functions which have a prerequisite function
        >>> Rulan = Player(name="Rulan",
                           connection_id=1,
                           client={'name': 'Commodore 64'},
                           flags={'dungeon_master': True, 'debug': True, 'expert_mode': False}
                           )

        >>> Rulan.print_stat('int')
        Int: 5
        """
        if stat not in self.stats:
            logging.warning(f"get_stat: Stat {stat} doesn't exist.")
            # TODO: raise ValueError?
            return
        # return e.g., "Int: 4"
        return f'{stat.title()}: {self.stats[stat]}'

    def print_all_stats(self):
        """
        print all player stats in title case: '<Stat>: <value>'

        for doctest eventually
        FIXME: can't figure out how to test routines which have other function call prerequisites
        >>> Rulan = Player(name="Rulan",
                           connection_id=1,
                           client={'name': 'Commodore 64'},
                           flags={'dungeon_master': True, 'debug': True, 'expert_mode': False}
                           )

        >>> Rulan.print_all_stats()
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
            return
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


def transfer_money(p1: Player, p2: Player, kind: str, adj: int):
    """
    :param p1: Player to transfer <adj> gold to
    :param p2: Player to transfer <adj> gold from
    :param kind: classification ('in_hand' most likely)
    :param adj: amount to transfer
    :return: none
    """
    # as suggested by Shaia:
    # (will be useful for future bank, or future expansion: gold transfer spell?)
    if p2.silver[kind] >= adj:
        p1.set_silver(kind, adj)
        p2.set_silver(kind, -adj)
        logging.info(f'transfer_money: {p2.name} {adj} {kind} -> {p1.name}: {p1.silver[kind]}')
        print(f'{p2.name} transferred {adj} silver {kind} to {p1.name}.')
        print(f'{p1.name} now has {p1.silver[kind]}.')
    else:
        print(f"{p2.name} doesn't have {adj} silver to give.")


class Ally(object):
    def __init__(self):
        """
        Ally['name'][stat], position: str
        where (as in TLOS): empty=0, lurking=1, point=2, flank=2, rear=3,
            (guard=4?), unconscious=5 (in python I will spell out positions as strings)
        abilities[
            'tracking': int  # number of rooms away an ally can detect a target
                             # TLOS: distance between tracker and target determined track strength.
                             # target's last play date delta compared to date.today determines
                             # "strength" of tracks: 1-3 days: very fresh, >3 days: weak (?)
                             # https://docs.python.org/3/library/datetime.html
             # TODO: look at Skip's branch on GitHub, it has more TRACKing stuff:
                # https://github.com/Pinacolada64/TADA-old/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.MISC9.S
            'ayf': int      # ally has a 1-ayf% chance of randomly finding sack of gold/diamond/etc.
            'alignment': str # in TLOS: '(' good, ')' evil
            ]
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

    Rulan = Player()
    Rulan.name = "Rulan"
    Rulan.connection_id = 1
    Rulan.client = {'name': 'Commodore 128', 'columns': 80}
    Rulan.flags = {'dungeon_master': True, 'debug': True, 'expert_mode': False}

    print(Rulan)
    Rulan.set_stat('int', 5)
    print(f"{Rulan.print_stat('int')}")  # show "Int: 5", this passes

    Rulan.set_stat('int', 4)  # add to Rulan's Intelligence of 5, total 9
    print(f"{Rulan.print_stat('int')}")  # show "Int: 9", this passes
    # when print_stat returned None, had to do this:
    # print(f'Rulan ...... ', end='')
    # Rulan.print_stat('int')  # should print 'Rulan ...... Int: 9'

    Rulan.set_silver(kind='in_hand', adj=100)
    Rulan.set_silver(kind='in_bank', adj=200)
    Rulan.set_silver(kind='in_bar', adj=300)

    print(f"Silver in bank: {Rulan.get_silver('in_bank')}")  # should print 200, this passes

    Rulan.print_all_stats()

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

    transfer_money(Shaia, Rulan, kind='in_hand', adj=500)  # should rightfully fail
    transfer_money(Shaia, Rulan, kind='in_hand', adj=100)  # this passes
