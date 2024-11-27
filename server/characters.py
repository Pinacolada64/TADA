import logging
from dataclasses import dataclass

from flags import Player


# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/
# http://pythonfiddle.com/text-based-rpg-code-python/


class Ally:
    @dataclass
    def __init__(self):
        name: str
        hit_points: int
        stat: list
        abilities: list
        """
        'tracking': int  # number of rooms away an ally can detect a target
        TLOS: distance between tracker and target determined track strength.
        target's last play date delta compared to date.today determines
        "strength" of tracks: 1-3 days: very fresh, >3 days: weak (?)
        https://docs.python.org/3/library/datetime.html
        'search': bool  # if True, can improve chances of finding things
        'servant': bool  # if True, was bought at Olaf's and needs to be paid weekly
        vs. joined party or charmed

        Ally['name'][stat], position: str
        where (as in TLoS): empty=0, lurking=1, point=2, flank=2, rear=3,
            (guard=4?), unconscious=5 (in python I will spell out positions as strings)
        
        # TODO: look at Skip's branch on GitHub, it has more TRACKing stuff:
        # https://github.com/Pinacolada64/TADA-old/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.MISC9.S
        'ayf': int      # ally has a 1-ayf% chance of randomly finding sack of gold/diamond/etc.
        """
        alignment: str  # in TLOS: '(': good, ')': evil
        flag: list  # | = TLOS ally string postfix, then:
        """
        'elite': bool   # !
        'mount': bool   # =
        'body_build': bool  # #nn <nn=1...25?> Not clear what this is for, Str improvement?
        # TODO: find ally guild code
        """
        silver: int
        battle_exp: int

        # inventory:
        rations: list
        items: int

        weapon_experience: dict  # {weapon_item: weapon_skill}
        # randomly assigned when bought or joins party?:
        strength: int
        dexterity: int


@dataclass
class Character:
    """
    this code is called when creating a new character
    :param args: tuple
    :param kwargs: dict of keywords
    """
    name: str
    age: int
    flag: dict
    hit_points: int
    silver: dict  # dict({'in_hand': 0, 'in_bar': 0, 'in_bank': 0})

    # FIXME: probably just forget this, net_server.py handles connected_users(set)
    """
    connection_id: list of CommodoreServer IDs: {'connection_id': id, 'name': 'name'}
    for k in len(connection_ids):
        if connection_id in connection_ids[1][k]:
            logging.info(f'Character.__init__: duplicate {connection_id['id']} assigned to '
                         f'{connection_ids[1][connection_id]}')
        return

        temp = {self.name, self.id}
        ids.append({'name': self.name, 'connection': self.connection_id})
        logging.info(f'Character.__init__: Connections: {len(connection_ids)}, {connection_ids}')
        self.connection_id = connection_id  # 'id' shadows built-in name
        """

    stats: dict  # dict({'chr': 0, 'con': 0, 'dex': 0, 'int': 0, 'str': 0, 'wis': 0, 'egy': 0})

    age: int
    birthday: tuple
    combat: list
    # weapon_percentage: dict  # {'weapon': percentage [, ...]}
    # weapon_ammunition: dict  # {'weapon': ammo_count [, ...]}

    @classmethod
    def print_stat(cls, self, stats: list):
        """
        # print player stat in title case: '<Stat>: <value>'
        >>> test = Character(name='test', stats={'chr': 10})

        >>> test.print_stat(stat=['chr'])
        Chr: 10
        """

        # for doctest: if functions have a prerequisite function, call that first (just like real code)
        for stat in stats:
            try:
                if stat not in self.stats:
                    logging.warning(f"get_stat: Stat '{stats}' doesn't exist.")
                    # TODO: raise ValueError?
                    # return e.g., "Int: 4"
            except KeyError:
                output = ''
        for s in stats:
            print(f'{str(s).title()}: {self.stats[s]:2} ', end='')
        print()
        return

    def __str__(self):
        """print formatted Character object"""

        # FIXME: test of __str__ method:
        """
        StrTest = Character(name="StrTest", connection_id=1,
                            client={'name': 'Commodore 128', 'columns': 80},
                            gender="male",
                            flag={'dungeon_master': True, 'debug': True, 'expert_mode': False},
                            age=45, birthday=(4, 13, 22),
                            silver{"in_hand": 2000},
                            guild="fist")

        >>> print(f"Test of __str__ method:\n{StrTest}")
        Test of __str__ method:
        Name: StrTest        Age: 45    Birthday: 4/13/2022
        Silver: In hand: 2,000
        
        _ += f'\tBirthday: {self.birthday[0]}/{self.birthday[1]}/{self.birthday[2] - }\n'
        _ += f"Silver: In hand: {self.silver['in_hand']}\n"
        _ += f'Guild: {self.guild}\n'
        """

        print(f"Name: {self.name}\t\t"
              f"Age: {'Unknown' if self.age == 0 else '{self.age}'}"
              # day / month / year = date.year - self.age
              # TODO: make Character.get_birthday() / Character.print_birthday() functions
              f'\tBirthday: {self.birthday[0]}/{self.birthday[1]}/{self.birthday[2]}\n'
              f"Silver: In hand: {self.silver['in_hand']}\n"
              f'Guild: {self.guild}\n')

    def get_birthday(self, char: Character):
        """
        get character's birthday

        :param: age: Character age
        :param: birthday: tuple (month, day, year)
        :return: str: "month/day" ("month/day/year" if age known)

        character.birthday[0=month, 1=day, 2=year]  # tuple

        1) determine if character.age is known (!= 0) or unknown (== 0):
           a) if age known: format birthday 'month/day/year'
           b) if age unknown: format birthday 'month/day'

        >>> self.get_birthday(age=45, birthday=(6, 16, 1976))
        6/16/1976

        >>> self.get_birthday(age=0, birthday=(6, 16, 1976))
        6/16
        """
        from datetime import date

        # TODO: locale stuff where dates are in either month-day-year / year-month-day format?
        age = char.age
        birthday = char.birthday
        month = birthday[0]
        day = birthday[1]
        if age is None or age == 0:
            # year unknown, don't print it
            return f"{month}/{day}"
        else:
            # year known, get current year - age
            year = date.today().year - age
            return f"{month}/{day}/{year}"

    def print_all_stats(self, char: Player):
        """
        >>> test = Character(stats={'chr': 8,
                                    'con': 15,
                                    'dex': 3,
                                    'int': 5,
                                    'str': 8,
                                    'wis': 3,
                                    'egy': 3})

        >>> Character.print_all_stats(test)
        Chr:  8   Int:  5   Egy:  3
        Con: 15   Str:  8
        Dex:  3   Wis:  3   '

        # for doctest eventually
        # FIXME: can't figure out how to test routines which have other function call prerequisites
        # Programs\Python\Python38\Lib\test\test_doctest.py
        #   note that print_all_stats returns three trailing spaces after integer
        """

        for stat in ['chr', 'int', 'egy']:
            print(f'Method 1: {char.print_stat(self, stat)}', end='')
            print(f'Method 2: {stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in ['con', 'str']:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()
        for stat in ['dex', 'wis']:
            print(f'{stat.title()}: {self.stats[stat]:2}   ', end='')
        print()

    def get_silver(self, kind: str) -> int | None:
        """
        get and return amount of silver player has

        :param kind: 'in_hand', 'in_bank', or 'in_bar'
        :return int:
        """
        if kind not in self.silver:
            logging.info(f"get_silver: Bad type '{kind}'.")
            return None
        logging.info(f'get_silver: {self.silver[kind]}')
        return self.silver[kind]

    def set_silver(self, kind: str, adj: int) -> bool:
        """
        :param self:
        :param kind: 'in_hand', 'in_bank' or 'in_bar'
        :param adj: amount to add (<adj>) or subtract (-<adj>)
        :return: True if succeeded, False if failed

        # test of Character.set_silver:
        >>> test_silver = Character(silver={'in_bank': 200})

        >>> print(f"Silver in bank: {test_silver.get_silver('in_bank')}")
        Silver in bank: 200

        >>> test_silver.set_silver(kind='in_hand', adj= 100)

        # set to 110
        >>> test_silver.set_silver(kind='in_hand', adj=10)

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
        Shorter than repeating "if char.class_name == 'witch' or char.class_name == 'wizard'"

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
        :return: Title-case character class name ("Witch" or "Wizard")
        """
        if char.is_magic_user(self):
            return char.char_class.title()

        # @staticmethod

    def transfer_silver(self, from_char: Character, to_char: Character, where: str, adj: int):
        """
        :param: from_char: Character to transfer <adj> silver from
        :param: to_char: Character to transfer <adj> silver to
        :param: where: where silver is ('in_hand' most likely)
        :param: adj: amount to transfer
        :return: True if from_char has adj silver, False if not

        # test of Character.transfer_silver:
        >>> Shaia = Character()

        >>> Shaia.set_silver(kind='in_hand', adj=200)

        >>> Rulan = Character()

        >>> Rulan.set_silver(kind='in_hand', adj=200)

        # Shaia doesn't have 500 silver, so this will fail:
        >>> Shaia.transfer_silver(from_char=Shaia, to_char=Rulan, where="in_hand", adj=500)
        False

        # Rulan has 100 silver in hand, so this will succeed:
        >>> Rulan.transfer_silver(Shaia, Rulan, where="in_hand", adj=100)
        True
        """
        # as suggested by Shaia:
        # (will be useful for future bank, or future expansion: silver transfer spell?)
        if from_char.silver[where] >= adj:
            to_char.set_silver(where, adj)
            from_char.set_silver(where, -adj)
            # e.g., transfer_silver: Shaia 100 in_hand -> Rulan 200
            logging.info(
                f'transfer_silver: {from_char.name} {adj} {where} -> {to_char.name}: {to_char.silver[where]}')
            print(f'{from_char.name} transferred {adj} silver {where} to {from_char.name}.')
            print(f'{from_char.name} now has {from_char.silver[where]}.')
            return True
        else:
            print(f"{from_char.name} doesn't have {adj} silver to give.")
            return False

    def set_stat(self, stat: str, adj: int):
        """
        :param stat: statistic in stats{} dict to adjust
        :param adj: adjustment (+x or -x)
        :return: stat, maybe also 'success': True if 0 > stat > limit

        >>> set_stat_test = Character(name="Test", \
                                      connection_id=1, \
                                      client={'name': 'Commodore 64'}, \
                                      flag={'dungeon_master': True, 'debug': True, 'expert_mode': False}, \
                                      stat={'int': 5} \
                                      )

        >>> set_stat_test.set_stat(stat='int', adj=15)

        >>> set_stat_test.print_stat(['int'])
        Int: 15

        >>> set_stat_test.set_stat({'wis': 9})

        >>> print(f"{set_stat_test.print_stat(['wis'])}")
        Wis: 9

        # test of Character.set_stat()
        >>> Shaia = Character(name="Shaia", \
                              connection_id=2, \
                              client={'name': 'TADA', 'columns': 80, 'rows': 25}, \
                              gender="female", \
                              stats={'int': 8}, \
                              flag={'expert_mode': True, 'debug': True})

        >>> Shaia.set_stat(stat='int', adj=18)

        >>> print(f"Shaia ...... {Shaia.print_stat(['int'])}")
        Shaia ...... Int: 18
        """

        # TODO: example for doctest:
        #  to instantiate Test character, must have stat{} key present

        if stat not in self.stats:
            logging.warning(f"Stat '{stat}' doesn't exist.")
            # raise ValueError?
            return

        # template: self.stats = {'con': 0, 'dex': 0, 'ego': 0, 'int': 0, 'str': 0, 'wis': 0}
        # adjust stat by <adjustment>:
        before = self.stats[stat]
        after = before + adj
        logging.info(f"set_stat: Before: {stat=} {before=} {adj=}")
        # self.flag.get("flag_name") returns None instead of KeyError if key doesn't exist:
        if self.flag["expert_mode"]:
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
            total = 0  # 'sum' shadows built-in type
            for k in stat:
                if stat not in self.stats:
                    logging.warning(f"get_stat: Stat '{stat}' doesn't exist.")
                    # TODO: raise ValueError?
                    return
                total += self.stats[k]
            logging.info(f'get_stat[list]: {stat=} {total=}')
            return total
        # otherwise, get just a single stat:
        if stat not in self.stats:
            logging.warning(f"get_stat: Stat '{stat}' doesn't exist.")
            # TODO: raise ValueError?
            return
        return self.stats[stat]

    def print_stat(self, stat_list: list):
        """
        print player stat in title case: '<Stat>: <value>'

        >>> test = Character(name='test', stats={'chr': 10})

        >>> test.print_stat(stat=['chr'])
        Chr: 10
        """

        # for doctest: if functions have a prerequisite function, call that first (just like real code)
        if stat_list not in self.stats:
            logging.warning(f"get_stat: Stat '{stat_list}' doesn't exist.")
            # TODO: raise ValueError?
            return
        # return e.g., "Int: 4"
        output = ''
        for s in stat_list:
            print(f'{str(s).title()}: {self.stats[s]:2} ', end='')
        print()
        return

    def print_all_stats(self, character: object):
        """
        print all player stats in title case: '<Stat>: <value>'

        # test of Character.print_all_stats()
        >>> test = Character(name="Test", \
                             stats={'chr': 8, 'con': 15, 'dex': 3, 'int': 5, 'str': 8, 'wis': 3, 'egy': 3})

        >>> Character.print_all_stats(test)
        r'Chr:  8   Int:  5   Egy:  3\n
        Con: 15   Str:  8\n
        Dex:  3   Wis:  3   '

        # for doctest eventually
        # FIXME: can't figure out how to test routines which have other function call prerequisites
        #  note that print_all_stats returns three trailing spaces after integer
        """
        for stat in ['chr', 'int', 'egy']:
            print(f'Method 1: {character.print_stat(self, stat)}', end='')
            print(f'Method 2: {stat.title()}: {self.stats[stat]:2}   ', end='')
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
        :param kind: 'in_hand', 'in_bank', or 'in_bar'
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

        # test of Character.set_silver:
        >>> test_silver = Character(name="silver", silver={'in_bank': 200})

        >>> print(f"Silver in bank: {test_silver.get_silver('in_bank')}")
        Silver in bank: 200

        >>> test_silver.set_silver(kind='in_hand', adj= 100)

        # set to 110
        >>> test_silver.set_silver(kind='in_hand', adj=10)

        """

        before = self.silver[kind]
        # TODO: check (before?) for negative amount
        after = before + adj
        if after < 0:
            logging.info(f'set_silver: {after=}, negative amount not allowed')
            return False
        self.silver[kind] = after
        return True

    def is_magic_user(self, char: Character):
        """
        Shorter than repeating "if char.class_name == 'witch' or char.class_name == 'wizard'"

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
        :return: Title-case character class name ("Witch" or "Wizard")
        """
        if char.is_magic_user(self):
            return char.char_class.title()

    # @staticmethod
    def transfer_silver(self, from_char: Character, to_char: Character, where: str, adj: int):
        """
        :param: from_char: Character to transfer <adj> silver from
        :param: to_char: Character to transfer <adj> silver to
        :param: where: where silver is ('in_hand' most likely)
        :param: adj: amount to transfer
        :return: True if from_char has adj silver, False if not

        # test of Character.transfer_silver:
        >>> Shaia = Character()

        >>> Shaia.set_silver(kind='in_hand', adj=200)

        >>> Rulan = Character()

        >>> Rulan.set_silver(kind='in_hand', adj=200)

        # Shaia doesn't have 500 silver, so this will fail:
        >>> Shaia.transfer_silver(from_char=Shaia, to_char=Rulan, where="in_hand", adj=500)
        False

        # Rulan has 100 silver in hand, so this will succeed:
        >>> Rulan.transfer_silver(Shaia, Rulan, where="in_hand", adj=100)
        True
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

    def get_birthday(self, age: int, birthday: tuple):
        """
        get character's birthday

        :param: age: Character age
        :param: birthday: tuple (month, day, year)
        :return: str: "month/day" ("month/day/year" if age known)

        character.birthday[0=month, 1=day, 2=year]  # tuple

        1) determine if character.age is known (!= 0) or unknown (== 0):
           a) if age known: format birthday 'month/day/year'
           b) if age unknown: format birthday 'month/day'

        >>> self.get_birthday(age=45, birthday=(6, 16, 1976))
        6/16/1976

        >>> self.get_birthday(age=0, birthday=(6, 16, 1976))
        6/16
        """
        from datetime import date

        # TODO: locale stuff where dates are in either month-day-year / year-month-day format?
        month = birthday[0]
        day = birthday[1]
        if age is None or age == 0:
            # year unknown, don't print it
            return f"{month}/{day}"
        else:
            # year known, get current year - age
            year = date.today().year - age
            return f"{month}/{day}/{year}"


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
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    import doctest

    doctest.testmod(verbose=True)

    # connection_ids = []  # initialize empty list for logging connection_id's
