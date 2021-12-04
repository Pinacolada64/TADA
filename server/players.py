import doctest

# https://inventwithpython.com/blog/2014/12/02/why-is-object-oriented-programming-useful-with-a-role-playing-game-example/

# http://pythonfiddle.com/text-based-rpg-code-python/


class Player(object):
    """
    Gathering all the attributes, flags and other stuff about players.

    There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
            (is it important to know whether the player or ally is carrying an item?)
            maybe return Player or Ally object if they hold it, or None if no-one holds it
    """

    def __init__(self, player_id: int, name: str, stats: dict, flags: dict, silver: dict, terminal: dict):
        # this code is called when creating a new character
        self.player_id = player_id  # 'id' shadows built-in name
        self.name = name
        # creates a new stats dict for each Player:
        # FIXME: trying to apply the specified Con value here...
        # ...this can be done with self.silver but not here?
        self.stats = stats  # {'con': 0, 'dex': 0, 'ego': 0, 'int': 0, 'str': 0, 'wis': 0}

        # flags:
        self.flags = flags  # {'room_descriptions': bool}
        # autoduel_mode: bool, hourglass_mode: bool, expert_mode: bool, more_prompt: bool
        # architect_mode: bool, orator_mode: bool # TODO: define orator_mode more succinctly
        # hungry: bool, thirsty: bool, diseased: bool, poisoned: bool
        # debug_mode: bool, dungeon_master: bool]

        # creates a new silver dict for each Player:
        # in_bank may be cleared on character death (TODO: look in TLOS source)
        # in_bar should be preserved after character's death (TODO: same)
        self.silver = silver  # {"in_hand": 0, "in_bank": 0, "in_bar": 0}
        # test that it works
        logging.info("Silver in hand: " + str(self.silver["in_hand"]))

        # terminal settings:
        self.terminal = terminal
        """
        {'type': 'Commodore 64', 'rows': 24, 'columns': 40,
         # for [bracket reader] text highlighting on C64/128:
         'colors': {'text': 1, 'highlight': 13, 'background': 15, 'border': 15}
        }
        """

        """
        proposed stats:
        some (not all) other stats, still collecting them:
    
        times_played: str, last_play_date: str
    
        special_items[
            SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
            BOAT  # does not actually need to be carried around in inventory, I don't suppose, just a flag?
            combinations{'elevator', 'locker', 'castle'}  # tuple? combo is 3 digits: (nn, nn, nn)
            ]
                
        age: int, birthday: str, sex: [ male | female ]
        stats{'con': 0, 'dex': 0, 'ego': 0, 'int': 0, 'str': 0, 'wis': 0}
        map_level: int  # cl, map_room: int  # cr
        moves_made: int
        guild[civilian | fist | sword | claw | outlaw]
        #                      1       2        3       4      5       6       7         8       9
        player.class: int  # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight 
        player.race: int   # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf
        player.silver{in_hand: int, in_bank: int, in_bar: int}
    
        config stuff:
            colors{'highlight': 0, 'normal': 0}
            terminal{'type': str, 'columns': int, 'rows': int}  # c64: columns=40, rows=25
    
        combat:
            honor: int
            weapon_percentage{'weapon': percentage [, ...]}, weapon_ammunition{'weapon': ammo_count}
            bad_hombre_rating is calculated from stats, not stored in player log
        
        once_per_day[] flags:  # things you can only do once per day (file_formats.txt)
            'pr'    has PRAYed once
            'pr2'   can PRAYed twice (only if player class is Druid)
            
        """

    def __str__(self):
        """print formatted Player object (double-quoted since ' in string)"""
        return f"Name: {self.name}\tSilver in hand: {self.silver['in_hand']}"


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
            'body_build': bool  # #nn <nn=1...25?> Not clear what this is for, TODO: find ally guild code
            ]
        silver: int
        """


class Horse(object):
    def __init__(self):
        """
        horse[name: str, have_horse: bool, armor: int, saddlebags: bool,
        saddle: bool, armor: int, training: bool (I think), mounted_on_horse: bool,
        lasso: bool
        inventory[]  # mash, hay, oats, apples, sugar cubes
        ]
        """


# I think these functions should be outside the class so that it can modify other Player objects?
def set_stat(player: object, stat: str, adjustment: int):
    """
    :param player: Player object
    :param stat: statistic in stats{} dict to adjust
    :param adjustment: adjustment (+x or -x)
    :return: stat, maybe also 'success': True if 0 > stat > <limit>

    example:
    >>> Rulan.set_stat['str': -5]  # decrement Rulan's strength by 5
    """
    if stat not in player.stats:
        logging.warning(f"Stat {stat} doesn't exist.")
        # raise ValueError?
        return
    # self.stats = {'con': 0, 'dex': 0, 'ego': 0, 'int': 0, 'str': 0, 'wis': 0}
    # adjust stat by <adjustment>:
    before = player.stats[stat]
    after = before + adjustment
    logging.info(f"set_stat: Before: {stat=} {before=} {adjustment=}")
    if not player.flags['expert_mode']:
        if before < after:
            # FIXME: e.g., if Int, {descriptive} should say "intelligent". How to do?
            print("(You feel less {descriptive}.)")
        if before > after:
            print("(You feel more {descriptive}.)")
    logging.info(f"set_stat: After: {stat=} {after=}")
    # return self.stats(stat)


def get_stat(player: object, stat: str):
    """print stat 'stat'"""
    if stat not in player.stats:
        logging.warning(f"get_stat: Stat {stat} doesn't exist.")
        # TODO: raise ValueError?
        return
    return self.stats[stat]


def print_stat(self, player: object, stat: str):
    logging.info(f'print_stat: {get_stat(player=player, stat=stat)}')


def get_silver(self, player, kind):
    """
    get amount of silver player_name has
    TODO: allies too - Ally['silver': 100?]
    'kind' is 'in_hand', 'in_bank', or 'in_bar'
    """
    if kind not in player.silver:
        logging.info(f"get_silver: Bad type '{kind}'.")
        return
    # return player.silver{kind}
    print(f"player.silver[kind]")
    return


def set_silver(player, kind, adjustment):
    """adjustment can be either positive or negative"""
    before = player.silver[kind]
    # TODO: check for negative amount
    after = before + adjustment
    player.silver(kind, after)


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    Rulan = Player(name="Rulan", player_id=1, stats={'int': 5}, terminal={'type': 'Commodore 64'},
                   silver={'in_hand': 100, 'in_bank': 200, 'in_bar': 300},
                   flags={'dungeon_master': True, 'debug': True, 'expert_mode': False}
                   )
    print(Rulan)

    set_stat(Rulan, 'int', 4)  # set Rulan's Intelligence to 4
    show = Rulan.stats['int']
    print(f"{show}")  # show "Int: 4"

    set_silver(player=Rulan, kind='in_hand', adjustment=100)
    print(f"Silver in bank: {get_silver(player='Rulan', kind='in_bank')}")  # should print 100
