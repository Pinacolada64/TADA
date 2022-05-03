# supposed to handle passing "str | list" type-hinting to get_stat()
# but breaks print(f'string') because python 2.7? don't understand that
# from __future__ import annotations

import logging
from dataclasses import dataclass

# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/


@dataclass
class Character(object):
    """
    Attributes, flags and other stuff about characters.
    """
    """
    # TODO: There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
            (is it important to know whether the player or ally is carrying an item?)
            maybe return Character or Ally object if they hold it, or None if no-one holds it
            Or could be written:
            
            if 'armor' in Character.inventory and 'armor' in Character.used:
            # meaning 'armor' is in 'inventory' and 'used' lists?
            # could this be shortened? perhaps:
            # if Character.ItemHeldUsed('armor')
    """

    connection_id: int  # TODO: eventually, CommodoreServer Internet Protocol connection ID
    name: str
    gender: str  # male, female
    stats: dict
    flag: dict
    silver: dict  # TODO: money types may be expanded to platinum, electrum in future
    age: int
    birthday: tuple  # month, day, year
    guild: str  # [civilian | fist | sword | claw | outlaw]
    #                   1       2        3       4      5       6       7         8       9
    char_class: str  # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
    race: str  # ......Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf
    natural_alignment: str  # good | neutral | evil (depends on race?)

    client: dict  # client info: host (i.e., Python, C64, C128...?)

    hit_points: int
    experience: int

    # map stats:
    map_level: int
    room: int

    # client settings:
    client: dict

    # combat stats:
    armor: list  # e.g., should it be its own class with attributes?
    # Armor(object):
    # def __init__(name, percent_left, armor_class, ...)
    # TODO: weight (iron armor vs. padded leather armor will be different),
    #  could also define effectiveness, heavier armor absorbs more damage

    shield: dict
    # shield_used: int  # shield item being USEd
    # shield_skill{shield_item: int, shield_skill: int}
    # same:
    # Shield(object):
    # def __init__(name, percent_left, shield_size, ...)
    # TODO: weight (iron shield vs. wooden shield will be different),
    #  could also define effectiveness, heavier shields absorb more damage

    weapon: dict
    # weapon_used: int  # if != 0, this weapon READYed
    # weapon_skill{weapon_item: int, weapon_skill: int}
    # weapon_left: int  # map this to a rating

    honor_rating: int  # helps determine current_alignment
    formal_training: int
    monsters_killed: int
    # not always the sane as len(dead_monsters); still increment it if you re-kill a monster
    dead_monsters: list  # keeps track of monsters to resurrect for Zelda in the bar

    vinny_loan: dict  # {amount_payable: int, days_til_due: int}

    # inventory
    max_inv: int
    # also see weapons[], armor[], shields[]
    food: list
    drink: list
    spells: list  # tuple(spell_name: str, charges, chance_to_cast: int)
    booby_traps: list  # ['a' - 'i']

    def __init__(self, /, *args, **kwargs):  # args: tuple, kwargs: dict of keywords
        """this code is called when creating a new character"""
        # FIXME: true that specifying e.g., 'hit_points=None' makes it a positional parameter

        if args:
            for v in args:
                print(f'{v=}')
            print("-" * 40)
        for k, v in kwargs.items():
            print(f'{k=} {v=}')

        # FIXME: probably just forget this, net_server.py handles connected_users(set)
        """
        connection_id: list of CommodoreServer IDs: {'connection_id': id, 'name': 'name'}
        for k in len(connection_ids):
            if connection_id in connection_ids[1][k]:
                logging.info(f'Character.__init__: duplicate {connection_id['id']} assigned to '
                             f'{connection_ids[1][connection_id]}')
            return
        temp = {self.name, connection_id}
        connection_ids.append({'name': name, connection_id})
        logging.info(f'Character.__init__: Connections: {len(connection_ids)}, {connection_ids}')
        self.connection_id = connection_id  # 'id' shadows built-in name
        """
        if "name" in kwargs and kwargs['name'] is not None:
            self.name = kwargs['name']
        logging.info(f"Character {self.name} instantiated")

        if "" in kwargs and kwargs['connection_id'] is not None:
            self.connection_id = kwargs['connection_id']  # keep this until I figure out where it is in net_server.py
        if "gender" in kwargs and kwargs['gender'] is not None:
            self.gender = kwargs['gender']

        # creates a new kwargs dict for each Character, zero all kwargs:
        # set with Character.set_stats('xyz', val)
        if "stats" in kwargs and kwargs['stats'] is not None:
            self.stats = kwargs['stats']
        else:
            self.stats = {'chr': 0, 'con': 0, 'dex': 0, 'int': 0, 'str': 0, 'wis': 0, 'egy': 0}
        logging.info(f"stats: {self.stats}")

        # flags:
        if "flags" in kwargs and kwargs['flag'] is not None:
            self.flag = kwargs['flag']
        else:
            self.flag = {
                # status flags:
                'room_descriptions': bool, 'autoduel': bool, 'hourglass': bool,
                'expert': bool, 'more_prompt': bool, 'architect': bool,
                # 'orator_mode': bool  # TODO: define orator_mode more succinctly
                'hungry': bool, 'thirsty': bool, 'diseased': bool, 'poisoned': bool,
                'tired': bool, 'on_horse': bool, 'unconscious': bool,
                'debug': bool, 'dungeon_master': bool, 'compass_used': bool,
                'thug_attack': bool,
                # game objectives:
                'spur_alive': bool, 'dwarf_alive': bool, 'wraith_king_alive': bool,
                'wraith_master': bool,
                'tut_treasure': dict,  # {'examined': bool, 'taken': bool}
                # magic items:
                'gauntlets_worn': bool, 'ring_worn': bool, 'amulet_of_life': bool,
                # wizard_glow stuff:
                # 0 if inactive, != 0 is number of rounds left, decrement every turn
                'wizard_glow': int
            }
            """
            to check elsewhere, use 'if is_magic_user(self): do_blah()'

            228	1	Game info:
            Bit 7: Gauntlets worn
                6: Amulet of Life energized
                5: Thug attack
                4: Compass used
                3: Dwarf alive
                2: Wraith King alive
                1: Spur alive
                0: Ring worn

            229	1	Wizard's Glow active:
                        0: No
                          <>0: # of rounds
            
            230	1	*** Bits 7-3: Reserved for future expansion ***
                        Bit 2: Wraith Master of Spur   (0=no, 1=yes)
                        Bit 1: Tut's treasure taken	   (0=no, 1=yes)
                        Bit 0: Tut's treasure examined (0=no, 1=yes)
        """
            logging.info(f'{self.flag=}')

        # creates a new silver dict for each Character:
        # in_bank may be cleared on character death (TODO: look in TLOS source)
        # in_bar should be preserved after character's death (TODO: same)
        # use Character.set_silver("kind", value)
        if "silver" in kwargs and kwargs["silver"] is not None:
            self.silver = kwargs['silver']
        else:
            self.silver = {"in_hand": 0, "in_bank": 0, "in_bar": 0}
        logging.info(f'Character.__init__: Silver in hand: {self.silver["in_hand"]}')

        # client settings - set up some defaults
        if "client" in kwargs and kwargs["client"] is not None:
            self.client = kwargs['client']
        else:
            self.client = {'name': None, 'rows': None, 'columns': 80, 'translation': None,
                           # colors for [bracket reader] text highlighting on C64/128:
                           'text': None, 'highlight': None, 'background': None, 'border': None}

        if "age" in kwargs and kwargs["age"] is not None:
            self.age = kwargs['age']
        if "birthday" in kwargs and kwargs["birthday"] is not None:
            self.birthday = kwargs['birthday']  # tuple: (month, day, year)

        times_played: int  # TODO: increment at character.save()
        last_play_date: tuple  # (month, day, year) like birthday

        special_items: list
        # SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
        # TODO: avoid placing objects in map "holes" where no room exists
        # DINGHY  # does not actually need to be carried around in inventory, I don't suppose, just a flag?
        combinations: dict  # {'elevator', 'locker', 'castle'}  # tuple? combo is 3 digits: (nn, nn, nn)

        map_level: int  # cl
        map_room: int  # cr
        moves_made: int
        """
        if self.guild is not None:
            # [civilian | fist | sword | claw | outlaw | none]
            self.guild = kwargs['guild']
        if self.char_class is not None:
            # 1: Wizard|Witch 2: Druid 3: Fighter 4: Paladin 5: Ranger 6: Thief 7: Archer 8: Assassin 9: Knight
            self.char_class = kwargs['char_class']
        # 1: Human 2: Ogre 3: Pixie 4: Elf 5: Hobbit 6: Gnome 7: Dwarf 8: Orc 9: Half-Elf
        self.race = kwargs['race']

        self.hit_points = hit_points
        self.shield = shield
        self.armor = armor
        self.experience = experience
        """
        combat: list
        honor: int
        weapon_percentage: dict  # {'weapon': percentage [, ...]}
        weapon_ammunition: dict  # {'weapon': ammo_count [, ...]}
        # bad_hombre_rating is calculated from stats, not stored in player log
        monster_at_quit: int
        once_per_day: list  # flags:  # things you can only do once per day (file_formats.txt)
        """
        'pr'    has PRAYed once
        'pr2'   can PRAY twice per day (only if char_class is Druid)
        """
        # logging.info(f'{self}')

    def __str__(self):
        """print formatted Character object"""

        # FIXME: test of __str__ method:
        """
        StrTest = Character(name="StrTest", connection_id=1,
                            client={'name': 'Commodore 128', 'columns': 80},
                            gender="male",
                            flag={'dungeon_master': True, 'debug': True, 'expert_mode': False},
                            age=45, birthday=(4, 13, 22)
                            )

        >>> print(f"Test of __str__ method:\n{StrTest}")
        Test of __str__ method:
        Name: StrTest        Age: 45    Birthday" 4/13/2022
        _ += f"Age: {'Undetermined' if self.age == 0 else '{self.age}'}"
        # year / month / day
        _ += f'\tBirthday: {self.birthday[0]}/{self.birthday[1]}/{self.birthday[2] - }\n'
        _ += f"Silver: In hand: {self.silver['in_hand']}\n"
        _ += f'Guild: {self.guild}\n'
        """

        _ = f"Name: {self.name}\t\t"
        _ += f"Age: {'Undetermined' if self.age == 0 else '{self.age}'}"
        # day / month / year = date.year - self.age
        # TODO: make Character.get_birthday() / Character.print_birthday() functions
        _ += f'\tBirthday: {self.birthday[0]}/{self.birthday[1]}/{self.birthday[2]}\n'
        _ += f"Silver: In hand: {self.silver['in_hand']}\n"
        _ += f'Guild: {self.guild}\n'
        return _

    def set_stat(self, stat: str, adj: int):
        """
        :param stat: statistic in stats{} dict to adjust
        :param adj: adjustment (+x or -x)
        :return: stat, maybe also 'success': True if 0 > stat > limit
        """

        # TODO: example for doctest:
        # to instantiate Test character, must have stat{} key present

        """
        >>> Test = Character(stats={'str': 0})
        
        >>> Test.set_stat['str': 10]  # start out with strength 10
        
        >>> Test.set_stat['str': -5]  # decrement Test's strength by 5

        >>> Test.get_stat('str')  # should return 5
        5
        """
        if stat not in self.stats:
            logging.warning(f"Stat '{stat}' doesn't exist.")
            # raise ValueError?
            return
        # self.stats = {'con': 0, 'dex': 0, 'ego': 0, 'int': 0, 'str': 0, 'wis': 0}
        # adjust stat by <adjustment>:
        before = self.stats[stat]
        after = before + adj
        logging.info(f"set_stat: Before: {stat=} {before=} {adj=}")
        if not self.flag['expert_mode']:
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
                    logging.warning(f"get_stat: Stat '{stat}' doesn't exist.")
                    # TODO: raise ValueError?
                    return
                _sum += self.stats[k]
            logging.info(f'get_stat[list]: {stat=} {_sum=}')
            return _sum
        # otherwise, get just a single stat:
        if stat not in self.stats:
            logging.warning(f"get_stat: Stat '{stat}' doesn't exist.")
            # TODO: raise ValueError?
            return
        return self.stats[stat]

    def print_stat(self, stat: str):
        """
        print player stat in title case: '<Stat>: <value>'
        """

        # for doctest: if functions have a prerequisite function, call that first (just like real code)
        if stat not in self.stats:
            logging.warning(f"get_stat: Stat '{stat}' doesn't exist.")
            # TODO: raise ValueError?
            return
        # return e.g., "Int: 4"
        return f'{stat.title()}: {self.stats[stat]}'

    def print_all_stats(self):
        """
        print all player stats in title case: '<Stat>: <value>'
        """
        # for doctest eventually
        # FIXME: can't figure out how to test routines which have other function call prerequisites
        # note that print_all_stats returns three trailing spaces after integer
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
        :param self:
        :param kind: 'in_hand', 'in_bank' or 'in_bar'
        :param adj: amount to add (<adj>) or subtract (-<adj>)
        :return: True if succeeded, False if failed
        """
        before = self.silver[kind]
        # TODO: check (before?) for negative amount
        after = before + adj
        if after < 0:
            logging.info(f'set_silver: {after=}, negative amount not allowed')
            return False
        self.silver[kind] = after
        return True

    def is_magic_user(self, char):
        """
        Shorter than repeating 'if char.class_name == 'witch' or char.class_name == 'wizard'

        :param self: self object
        :param char: Character object
        :return: True if character class is witch (female) or wizard (male)
        """
        return char.char_class == 'witch' or char.char_class == 'wizard'

    def magic_user_class_name(self, char):
        """
        FIXME: justification for this routine's existence?

        :param self: self
        :param char: Character object
        :return: Title case character class name
        """
        if char.char_class == "wizard" or char.char_class == "witch":
            return char.char_class.title()

    @staticmethod
    def transfer_silver(from_char, to_char, where: str, adj: int):
        """
        :param from_char: Character to transfer <adj> silver from
        :param to_char: Character to transfer <adj> silver to
        :param where: where silver is ('in_hand' most likely)
        :param adj: amount to transfer
        :return: True if from_char has adj silver, False if not
        """
        # as suggested by Shaia:
        # (will be useful for future bank, or future expansion: silver transfer spell?)
        if from_char.silver[where] >= adj:
            to_char.set_silver(where, adj)
            from_char.set_silver(where, -adj)
            # e.g., transfer_silver: Shaia 100 in_hand -> Rulan 200
            logging.info(f'transfer_silver: {from_char.name} {adj} {where} -> {to_char.name}: {to_char.silver[where]}')
            print(f'{from_char.name} transferred {adj} silver {where} to {from_char.name}.')
            print(f'{from_char.name} now has {from_char.silver[where]}.')
            return True
        else:
            print(f"{from_char.name} doesn't have {adj} silver to give.")
            return False

    def get_birthday(self, character):
        """
        get character's birthday

        :param character: character object
        :return: str: month/day (year if age known)
        """
        from datetime import date
        """
        character.birthday[0=month, 1=day, 2=year]  # tuple
        
        1) determine if character.age is known (!= 0) or unknown (== 0):
           a) if age known: format birthday 'month/day/year'
           b) if age unknown: format birthday 'month/day'
        """

        """
        >>> TestBirthday = Character(age=45, birthday=(6, 16, 1976))
        6/16/1976
        >>> TestBirthday = Character(age=0, birthday=((6, 16, 1976))
        6/16
        """
        # TODO: locale stuff where dates are in year-month-day format?
        month = character.birthday[0]
        day = character.birthday[1]
        if character.age is None or character.age == 0:
            # year unknown, don't print it
            temp = f"{month}/{day}"
        else:
            # year known, get current year - age
            year = date.today().year - character.age
            temp = f"{month}/{day}/{year}"
        return temp


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
            'search': bool  # if True, can improve chances of finding things
            'servant': bool  # if True, was bought at Olaf's and needs to be paid weekly
                             # vs. joined party or charmed

             # TODO: look at Skip's branch on GitHub, it has more TRACKing stuff:
                # https://github.com/Pinacolada64/TADA-old/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.MISC9.S
            'ayf': int      # ally has a 1-ayf% chance of randomly finding sack of gold/diamond/etc.
            'alignment': str # in TLOS: '(' good, ')' evil
            ]
        flag[              # | = TLOS ally string postfix, then:
            'elite': bool   # !
            'mount': bool   # =
            'body_build': bool  # #nn <nn=1...25?> Not clear what this is for, Str improvement?
             # TODO: find ally guild code
            ]
        silver: int
        battle_exp: int

        # inventory:
        rations: list
        items: int

        weapon_experience: dict  # {weapon_item: weapon_skill}
        # randomly assigned when bought or joins party?:
        strength: int
        dexterity: int
        """
        pass


class Horse(object):
    def __init__(self):
        """
        horse[name: str, have_horse: bool, armor: int, saddlebags: bool,
        saddle: bool, armor: int, training: bool (I think), mounted_on_horse: bool,
        lasso: bool
        # if saddlebags is True, Horse can carry additional things (via GIVE?):
        inventory{}  # dict: mash, hay, oats, apples, sugar_cubes
        ]
        flags: 'can_fly': pegasus (male), maybe?
        """

        pass


if __name__ == '__main__':
    # import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    import doctest
    doctest.testmod(verbose=True)

    # connection_ids = []  # initialize empty list for logging connection_id's

    # test of Character.set_stat and print_stat methods:
    """
    >>> SetStatTest = Character(name="Test", \
                                connection_id=1, \
                                client={'name': 'Commodore 64'}, \
                                flag={'dungeon_master': True, 'debug': True, 'expert_mode': False} \
                                stat={'int': 5}
                                )

    >>> SetStatTest.set_stat('int', 5)
    
    >>> SetStatTest.print_stat('int')
    Int: 5
    
    >>> Test = Character(stat={'int': 9})
    
    >>> print(f"{Test.print_stat('int')}")
    Int: 9
    """

    # test of Character.set_silver:
    # Rulan.set_silver(kind='in_hand', adj=100)
    """
    >>> Test = Character(silver={'in_bank': 200})

    >>> print(f"Silver in bank: {Test.get_silver('in_bank')}")
    Silver in bank: 200
    """

    # test of Character.print_all_stats()
    """
    >>> Test = Character(name="Test", \
                         flag={'dungeon_master': True, 'debug': True, 'expert_mode': False}, \
                         stats={'chr': 8, 'con': 15, 'dex': 3, 'int': 5, 'str': 8, 'wis': 3, 'egy': 3}, \
                         age=45 \
                         )

    >>> Test.print_all_stats()
    Chr:  8   Int:  5   Egy:  3   
    Con: 15   Str:  8   
    Dex:  3   Wis:  3   
    """

    # test of Character.set_stat()
    """
    >>> Shaia = Character(name="Shaia",
                          connection_id=2,
                          client={'name': 'TADA', 'columns': 80, 'rows': 25},
                          gender="female",
                          stats={'int': 8},
                          flag={'expert_mode': True, 'debug': True})

    >>> Shaia.set_stat(stat='int', adj=18)

    >>> print(f"Shaia ...... {Shaia.print_stat('int')}")
    Shaia ...... Int: 18
    """

    # test of Character.set_silver:
    """
    >>> Test = Character(silver={'in_hand': 100)
    
    >>> Test.set_silver(kind='in_hand', adj=10)

    """

    # test of Character.transfer_silver:
    """
    >>> Shaia = Character(silver{'in_hand': 200})
    
    >>> Rulan = Character(silver{'in_hand': 200})
        
    >>> Character.transfer_silver(Shaia, Rulan, where="in_hand", adj=500)
    False
    >>> Character.transfer_silver(Shaia, Rulan, where="in_hand", adj=100)
    True
    """
