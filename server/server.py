#!/bin/env python3

import os
import json
import random
import threading
from dataclasses import dataclass, field
import textwrap
import logging
from datetime import datetime

import net_server
import net_common
import common

from flags import Player, PlayerFlags, PlayerMoneyTypes

K = common.K
Mode = net_server.Mode
Message = net_server.Message

# fake data - make sure keys match those in Room class
# these are nice room descriptions, but not sure where they can be used
"""
roomsData = [
    {K.number: 1,
     K.name: 'Brookdale',
     K.desc: "You find yourself in the lovely upper left corner of the map. "
             "A small town nestles in the valley, a day's travel most likely. "
             "A dirt path leads south, and a babbling brook flows eastwards.",
     K.exits: {'s': 3, 'e': 2},
     K.monster: 0,
     K.item: 1,
     K.weapon: 1,
     K.food: 1,
     K.alignment: 'Claw'},

    {K.number: 2,
     K.name: 'Suntop Lookout',
     K.desc: "The sun shines brightly overhead. A dirt path meanders eastwards "
             "towards more tranquil scenery. A foreboding forest of dark, evil "
             "trees looms to the south.",
     K.exits: {'s': 4, 'w': 1},
     K.monster: 0,
     K.item: 1,
     K.weapon: 1,
     K.food: 1,
     K.alignment: 'Sword'},

    {K.number: 3,
     K.name: 'Near Castle',
     K.desc: "Behold, the castle Brackenwald can be spied beyond some "
             "rolling hills. Eastwards is the reputedly haunted forest.",
     K.exits: {'n': 1, 'e': 4},
     K.monster: 0,
     K.item: 1,
     K.weapon: 1,
     K.food: 1,
     K.alignment: 'Fist'},

    {K.number: 4,
     K.name: 'Dark Forest',
     K.desc: "The sun overhead filters dimly through twisted branches. There is "
             "a rusty sword on the ground--looks like you're going to need it.",
     K.exits: {'n': 2, 'w': 3},
     K.monster: 1,
     K.item: 0,
     K.weapon: 1,
     K.food: 0,
     K.alignment: '+'},
]
"""

room_start = 1
money_start = 1000

compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West', 'u': 'Up', 'd': 'Down'}


@dataclass
class Room(object):
    number: int
    name: str
    desc: str
    exits: dict = field(default_factory=lambda: {})  # {n e s w rc rt}
    monster: int = 0
    item: int = 0
    weapon: int = 0
    food: int = 0
    alignment: str = "neutral"  # default unless set to another guild

    def __str__(self):
        return f'#{self.number} {self.name}\n' \
               f'{self.desc}\n{self.exits}'

    def exits_txt(self, debug: bool):
        """
        Display exits in a comma-delimited list.
        :param debug: display room #s if True
        :return: joined list of exits
        """
        # connection/transport names, index by (connection, transport)
        # rc = 1: Up     rt != 0: Room #
        # rc = 2: Down   rt == 0: Shoppe
        extra_txts = {(1, 0): 'Up to Shoppe',
                      (2, 0): 'Down to Shoppe'}
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:
                exit_txts.append(compass_txts[k])
        room_connection = self.exits.get('rc', 0)
        room_transport = self.exits.get('rt', 0)
        exit_extra = extra_txts.get((room_connection, room_transport))
        if exit_extra:  # is not None:
            exit_txts.append(exit_extra)
        # example: level 1, room 20
        if room_connection == 1 and room_transport != 0:
            exit_txts.append(f"Up to #{room_transport}" if debug else "Up")
        if room_connection == 2 and room_transport != 0:
            exit_txts.append(f"Down to #{room_transport}" if debug else "Down")
        return ", ".join(exit_txts)


class Item(object):
    def __init__(self, number, name, kind, price, **flags):
        logging.debug("Item.__init__: Instantiate item '%s'" % name)
        self.number = number
        self.name = name
        self.kind = kind
        self.price = price
        # this field is optional:
        if flags:
            logging.debug("Flags:")
            self.flags = flags
            for key, value in flags.items():
                logging.debug("item_init: %s %s" % (key, value))

    @staticmethod
    def read_items(filename: str):
        try:
            with open(filename) as jsonF:
                items: object = json.load(jsonF)
                logging.debug("read_items: JSON data read")
                return items
        except FileNotFoundError:
            logging.error(">>> read_items: %s not found" % filename)
            return None


class Map(object):
    def __init__(self):
        """
        Define the level map layout
        """
        self.rooms = {}

    def read_map(self, filename: str):
        """
        Data format on C64:
        * Room number        (rm)
        * Location name      (lo$)
        * items: monster, item, weapon, food
        * exits: north, east, south, west,
          RC (room command: 1=move up,
                            2=move down),
          RT (Room exit transports you to:
                 <>0: room #, or 0=Shoppe)
        https://github.com/Pinacolada64/TADA/blob/master/text/s_t_level-1-data.txt
        """
        try:
            with open(filename) as jsonF:
                map_data = json.load(jsonF)
                logging.debug("read_map: JSON data read")
                for room_data in map_data['rooms']:
                    room = Room(**room_data)
                    self.rooms[room.number] = room
                    logging.debug('%i: %s' % (room.number, room.name))
        except FileNotFoundError:
            logging.error(">>> read_map: File not found: '%s'" % filename)


class Monster(object):
    def __init__(self, number, status, name, size, strength, special_weapon, to_hit, **flags):
        self.number = number
        self.status = status
        self.name = name
        # this field is optional:
        if size is not None:
            self.size = size
        self.strength = strength
        # this field is optional:
        if special_weapon is not None:
            self.special_weapon = special_weapon
        self.to_hit = to_hit
        # this field is optional:
        if flags is not None:
            self.flags = flags

    @staticmethod
    def read_monsters(filename: str):
        try:
            with open(filename) as jsonF:
                monsters = json.load(jsonF)
                logging.debug("read_monsters: JSON data read")
                """
                'item' becomes a copy of each dict element on each iteration of the loop:
                for count, item in enumerate(items, start=1):
                    print(f'{count:3} {item["name"]}')  # this works
                _ = input("Pause: ")
                print(f'{items[61]["name"]}')  # Adventurer's Guide
                """
                return monsters
        except FileNotFoundError:
            logging.error(">>> read_monsters: File not found: %s" % filename)
            return None


class Weapons(object):
    def __init__(self, number, location, name, kind, sound_effect, stability, to_hit, price, weapon_class, **flags):
        self.number = number
        self.location = location
        self.name = name
        # this field is optional:
        self.kind = kind
        self.sound_effect = sound_effect
        self.stability = stability
        self.to_hit = to_hit
        self.price = price
        self.weapon_class = weapon_class
        # this field is optional:
        if flags is not None:
            self.flags = flags

    @staticmethod
    def read_weapons(filename: str):
        try:
            with open(filename) as jsonF:
                weapons = json.load(jsonF)
                logging.debug("read_weapons: JSON data read")
                return weapons
        except FileNotFoundError:
            logging.error(">>> read_weapons: File not found: %s" % filename)
            return None


@dataclass
class Rations(object):
    number: int
    name: str
    kind: str  # magical, standard, cursed
    price: int
    flags: list

    def __init__(self, number, name, kind, price, **flags):
        self.number = number
        self.name = name
        self.kind = kind
        self.price = price
        # this field is optional:
        if flags is not None:
            self.flags = flags

    @staticmethod
    def read_rations(filename: str):
        try:
            with open(filename) as jsonF:
                rations = json.load(jsonF)
                logging.debug("read_rations: JSON data read")
                return rations
        except FileNotFoundError:
            logging.error(">>> read_rations: File not found: %s" % filename)
            return None


server_lock = threading.Lock()

def players_in_room(room_id: int, exclude_id: str | None):
    """
    Return a dict of player login id's in the room

    :param room_id: room number
    :param exclude_id: player to exclude (often the player executing the command) to not be listed
    :return: dict of players
    """
    with server_lock:
        players_in_room = room_players[room_id]
    if exclude_id is not None:
        players_in_room = players_in_room.difference({exclude_id})
        logging.debug("players_in_room: excluding %s" % exclude_id)
    logging.debug("players_in_room: Players in room %i: %s" % (room_id, players_in_room))
    return players_in_room


players = {}


def random_number():
    number = random.randrange(1, 65535)
    logging.debug("random_number: %i" % number)
    return number


@dataclass
class Player:
    """
    Attributes, flags and other stuff about characters.
    """
    name: str  # in-game name
    id: str  # handle, for Player.connect
    # TODO: eventually, CommodoreServer Internet Protocol connection ID
    connection_id: int  # field(default_factory=random_number)
    gender: str  # [ male | female ]
    # set stats with Character.set_stat('xyz', val)
    # stat: {'chr': int, 'con': int, 'dex': int, 'int': int,
    #        'str': int, 'wis': int, 'egy': int}
    stat: dict
    """
   'wraith_master': False,
   'tut_treasure': {'examined': False, 'taken': False},

   # magic items:
   'gauntlets_worn': False,
   'ring_worn': False,
   'amulet_of_life': False,

   # wizard_glow stuff:
   # 0 if inactive
   # != 0 is number of rounds left, decrement every turn
   wizard_glow: int

    # things you can only do once per day (file_formats.txt)
    once_per_day: list
    # 'pr'    has PRAYed once
    # 'pr2'   can PRAY twice per day (only if char_class is Druid)
    # TODO: finish this

    # TODO: money types may be expanded to platinum, electrum in future
    # creates a new silver dict for each Character:
    # in_bank: may be cleared on character death (TODO: look in TLOS source)
    # in_bar: should be preserved after character's death (TODO: same)
    # use Character.set_silver("kind", value)

    # 0 if unknown, otherwise age in years:
    # age is derived from datetime.now() - birthday
    birthday: datetime
    # [civilian | fist | sword | claw | outlaw]:
    guild: str

    #                  1       2       3       4       5       6       7       8        9
    char_class: str  # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
    race: str  # ......Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc      Half-Elf

    # client info:
    client: dict
    
    # host (i.e., Python, C64, C128...?)
    'name': str,
    # screen dimensions:
    'rows': int,
    'cols': int,
    # {'translation': None | ASCII | ANSI | Commodore }
    'translation': str,
    # colors for [bracket reader] text highlighting on C64/128:
    'text': int,
    'highlight': int,
    'background': int,
    'border': int]
    """
    hit_points: int
    experience: int

    # map stats:
    map_level: int  # cl = current level
    room: int  # cr = current room
    moves_made: int
    # tracks how many moves made today for experience at quit:
    moves_today: int

    # combat stats:
    armor: list
    # e.g., should it be its own class with attributes?
    # Armor(object):
    #     def __init__(name, percent_left, armor_class, ...)
    # TODO: weight (iron armor vs. padded leather armor will be different),
    #  could also define effectiveness, heavier armor absorbs more damage

    shield: dict
    shield_used: int  # shield item being USEd
    shield_skill: dict  # dict['item': int, 'skill': int]
    # same:
    # Shield(object):
    #     def __init__(name, percent_left, shield_size, ...)
    # TODO: weight (iron shield vs. wooden shield will be different),
    #  could also define effectiveness, heavier shields absorb more damage

    weapon: dict
    weapon_used: int  # if not None, this weapon READYed
    weapon_skill: dict  # {weapon_item: int, weapon_skill: int}
    weapon_left: int  # TODO: map this to a rating

    # bad_hombre_rating is calculated from stats, not stored in player log
    honor_rating: int  # helps determine current_alignment
    formal_training: int
    monsters_killed: list
    """
    monsters_killed is not always the same as dead_monsters[];
    still increment it if you re-kill a re-animated monster
    """
    dead_monsters: list  # keeps track of monsters for Zelda in the bar to resurrect
    monster_at_quit: str

    # ally stuff:
    allies: list  # (list of tuples?)
    ally_inv: list
    ally_abilities: list
    ally_flags: list

    # horse stuff:
    has_horse: bool
    horse_name: str
    horse_armor: dict  # {'name': name, 'armor_class': ac?}
    has_saddlebags: bool
    saddlebags: list  # these can carry items for GIVE and TAKE commands

    vinny_loan: dict  # {'amount_payable': int, 'days_til_due': int}

    # inventory
    """
    # TODO: There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
     (is it important to know whether the player or ally is carrying an item?)
     maybe return Character or Ally object if they hold it, or None if no-one holds it
     Or could be written:

     if 'armor' in Character.inventory and 'armor' in Character.used:
     # meaning 'armor' is in 'inventory' and 'used' lists?
     # could this be shortened? perhaps:
     # if Character.ItemHeldUsed('armor'):
    """
    max_inv: int
    # also see weapons[], armor[], shields[]
    food: list
    drink: list
    spells: list  # list of dicts('spell_name': str, 'charges', 'chance_to_cast': int)
    booby_traps: dict  # dict['room': int, 'combination': str]  # combo: '[a-i]'

    times_played: int  # TODO: increment at Character.save()
    # FIXME: how to distinguish between offline characters and online?
    last_connection: datetime

    special_items: dict
    # SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
    # TODO: avoid placing objects in map "holes" where no room exists
    # DINGHY  # does not actually need to be carried around in inventory, I don't suppose, just a flag?

    last_command: list

    def connect(self):
        with server_lock:
            # TODO: add last_connection as datetime.now()
            room_players[self.room].add(self.id)
            # TODO: notify other players of connection


    def move(self, next_room: int, direction=None):
        """
        remove player login id from list of players in current_room, add them to room next_room
        :param next_room: room to move to
        :param direction: direction being moved in, for notifying other players of movement
        if None, '#<room_number>' teleportation command (or, later, spell) was used and the
        "<player> disappears in a flash of light" message is used instead
        """
        current_room = self.room
        with server_lock:
            logging.debug("Player.move: Before remove: %s" % room_players[current_room])
            room_players[current_room].remove(self.id)
            logging.debug("Player.move: After remove: %s" % room_players[current_room])

            self.room = next_room
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
        try:
            path = Player._json_path(user_id)
            if os.path.exists(path):
                with open(path) as jsonF:
                    lh_data = json.load(jsonF)
                    logging.debug(f"Player.load: Loaded '%s'." % lh_data['name'])
                    return Player(**lh_data)
        except FileNotFoundError:
            # Failure
            logging.error("Player.load: '%s' not found" % user_id)
            return None


    def save(self):
        with open(Player._json_path(self.id), 'w') as json_file:
            json.dump(obj=self, fp=json_file, default=lambda o: {k: v for k, v
                                                      # in o.__dict__.items() if v}, indent=4)
                                                      in o.__dict__.items()}, indent=4)
            logging.debug("Player.save: Saved '%s'." % self.name)


    def make_random_id(self):
        """return a random connection id, same as random_number()"""
        # TODO: use one or the other; not both
        random_id = random.randrange(1, 65535)
        logging.debug("make_random_id: %i" % random_id)
        return random_id


class PlayerHandler(net_server.UserHandler):
    def init_success_lines(self):
        return ['Welcome to:\n', 'Totally\nAwesome\nDungeon\nAdventure\n', 'Please log in.']

    def login_fail_lines(self):
        return ['Please try again.']

    def room_msg(self, lines: list, changes: dict):
        """
        Display the room description and contents to the player in the room

        :param lines: text to output. each line is an element of a list.
        :param changes: ...?
        :return: Message object
        """
        # get room # that player is in
        try:
            room = game_map.rooms[self.player.room]
        except KeyError:
            logging.warning("room_msg: Room %i does not exist" % player.room)

        debug = player.query_flag(PlayerFlags.DEBUG_MODE)
        exits_txt = room.exits_Txt(debug)
        lines2 = list(lines)

        # display room header
        # check for/trim room flags (currently only '->'):
        temp = room.name.rfind("|")
        room_name = room.name
        room_flags = ''
        if temp != -1:
            room_name = room.name[:temp]
            room_flags = room.name[temp + 1:]

        temp = str(room.alignment).title()
        lines2.append(f"{f'#{room.number} ' if debug else ''}{room_name} [{temp}]\n")

        # FIXME: is anything wrong with this?
        if player.flag['room_descs']:
            lines2.append(f'{wrapper.fill(text=room.desc)}')

        # is an item in current room?
        logging.debug('room_msg: %s' % room)  # raw room info
        obj_list = []  # TODO: for grammatical list and .join(",") later
        item = room.item
        if item:
            obj_name = items[item - 1]["name"]
            obj_list.append(obj_name)
            lines2.append(f'You see item #{item} {obj_name}')

        food = room.food
        if food:
            food_name = rations[room.food - 1]["name"]
            # TODO: obj_list.append(food_name)
            lines2.append(f'You see food #{food} {food_name}')

        monster = room.monster
        if monster:
            m = monsters[monster - 1]
            monster_name = m["name"]
            # optional info:
            try:
                monster_size = m["size"]
            except KeyError:
                monster_size = None
            # TODO: obj_list.append(mon_name)
            lines2.append(f"You see monster #{monster}: "
                          f"{f'{monster_size} ' if monster_size else ''}"
                          f"{monster_name}")

        weapon = room.weapon  # weapon number
        if weapon:
            w = weapons[weapon - 1]
            weapon_name = w["name"]
            # TODO: obj_list.append(weapon_name)
            lines2.append(f'You see weapon #{weapon} {weapon_name}')

        # TODO: add grammatical list item (SOME MELONS, AN ORANGE)

        debug = player.flag['debug']
        exits_txt = room.exitsTxt(debug)
        if exits_txt is not None:
            lines2.append(f"Ye may travel: {exits_txt}\n")
            # ryan: list exit dirs and room #s
            if debug:
                for k, v in room.exits.items():
                    logging.debug("room_msg: Exit '%s' to '%s'", (k, v))

        # show item in room:
        # num = 62  # zero-based numbering, so subtract one to get actual object
        # logging.info(f'item #{num} name: {items[num - 1]["name"]}')

        # setting 'exclude_id' excludes that player (i.e., yourself) from being listed
        other_player_ids = players_in_room(room.number, exclude_id=player.id)
        # TODO: "Alice is here." / "Alice and Bob are here." / "Alice, Bob and Mr. X are here."
        """
        if len(other_player_ids) == 0:
            logging.info("No other players here.")
        if len(other_player_ids) > 0:
            result_list = []
            result_list.append(i for i in other_player_ids)
            if len(result_list) == 1:
                result_list = f"{result_list} is"
            if len(result_list) > 1:
                # tanabi: Add 'and' if we need it
                # result_list = f"and {result_list[:-1]} are"
                pass
        other_player_ids = playersInRoom(room.id, player.id)
        lines2.append(f"{result_list} here.")
        """

        if len(other_player_ids) > 0:
            other_players = ', '.join([players[id].name for id in other_player_ids])
            temp = 'is' if len(other_players) == 1 else 'are'
            lines2.append(f"{other_players} {temp} here.")
        return Message(lines=lines2, changes=changes)

    def process_login_success(self, user_id):
        player = Player.load(user_id)
        logging.info("process_login_success: Login %s ('%s') (IP: %s)" \
                     % (user_id, player.name, self.sender))
        if player is None:
            logging.debug("process_login_success: No player data, creating new character.")
            # TODO: create player
            import create_player
            logging.debug("process_login_success: Running create_player...")
            valid_name = False
            while not valid_name:
                reply = net_server.prompt_request(lines=["Choose your adventurer's name."], prompt='Name? ')
                name = reply['text'].strip()
                if name != '':  # TODO: limitations on valid names
                    valid_name = True
            player = Player(id=user_id,
                            name=name,
                            map_level=1,
                            room=room_start,
                            hit_points=100,
                            last_command=None)
            player.set_flag(PlayerFlags.DEBUG_MODE)
            player.clear_flag(PlayerFlags.EXPERT_MODE)
            player.set_flag(PlayerFlags.ROOM_DESCRIPTIONS)

            player.save()
        player = players[user_id] = player
        logging.info("login %s ('%s', IP addr=%s)" %
                     (user_id, player.name, self.sender))
        silver = player.silver[PlayerMoneyTypes.IN_HAND]
        lines = [f"Welcome, {player.name}.",
                 f"You have {silver:,} silver in hand.\n"]

        # show/convert flags from json text 'true/false' to bool True/False
        # (otherwise they're not recognized, and can't be toggled):
        for k, v in player.flag.items():
            if player.flag[k] == 'true':
                player.flag[k] = True
            if player.flag[k] == 'false':
                player.flag[k] = False
            logging.debug("%s: %s" % (k, v))

        changes = {K.room_name: game_map.rooms[player.room].name,
                   K.silver: player.silver, K.hit_points: player.hit_points,
                   K.experience: player.experience}
        player.connect()
        return self.room_msg(lines, changes)

    def process_message(self, data, player: Player):
        if 'text' in data:
            cmd = data['text'].lower().split(' ')
            logging.debug("process_message: ID=%s, command=%s" % (player.id, cmd))
            # update last command to repeat with Return/Enter
            # if an invalid command, set to None later
            # TODO: maybe maintain a history
            player.last_command = cmd
            logging.debug("process_message: Player %s last cmd: %s" %
                         (player.name, player.last_command))

            # TODO: handle commands with parser etc.

            # movement
            if cmd[0] in compass_txts:
                room = game_map.rooms[player.room]
                logging.debug("parser: current room #: %s" % player.room)
                direction = cmd[0]
                logging.debug("parser: direction: %s" % direction)
                # 'rooms' is a list of Room objects?
                logging.debug("parser: exits: %s" % room.exits)
                """
                >>> exits = {'n': 1, 's': 3}
                
                >>> exits.keys()
                dict_keys(['n', 's'])
                >>> exits['n']
                1
                """
                # cmd.insert(0, 'go') probably not necessary
                # json data (dict):
                # check if 'direction' is in room exits
                if direction in room.exits:  # rooms[player.room].exits.keys():
                    logging.debug("parser: move %s => %s" % (direction, player.room))
                    # delete player from list of players in current room, then
                    # add player to list of players in room they moved to
                    player.move(room.exits[direction], direction)
                    # FIXME: maybe only at quit
                    # player.save()
                    room_name = game_map.rooms[player.room].name
                    return self.room_msg(lines=[f"You move {compass_txts[direction]}."],
                                        changes={K.room_name: room_name})

            """
            This is the way the original Apple code handled up/down exits.
            I'm fully aware up/down exits could just be a room number, or 0
            for no connection--my -written level 8 map does exactly this.
            """
            if cmd[0][:1] == 'u' or cmd[0][:1] == 'd':
                room = game_map.rooms[player.room]
                room_exits = room.exits
                room_connection = room_exits.get('rc', 0)
                room_transport = room_exits.get('rt', 0)
                # example: level 1, room 20
                if cmd[0] == 'u' and room_connection == 1:
                    if room_transport != 0:
                        logging.debug("parser: %s moves Up to %i" % (player.name, room_transport))
                        # player.room = room_transport
                        player.move(next_room=room_transport, direction='u')
                        return
                    else:
                        logging.debug("parser: %s moves Up to Shoppe" % player.name)
                        player.move(next_room=room_transport, direction='u')
                        # don't change player.room, return them to where they left
                        return Message(lines=["TODO: write Shoppe routine..."])
                if cmd[0] == 'd' and room_connection == 2:
                    if room_transport != 0:
                        logging.debug("parser: %s moves Down to %i" % (player.name, room_transport))
                        player.move(next_room=room_transport, direction='d')

                        # get new room desc:
                        # FIXME: TypeError: 'Room' object is not subscriptable
                        """
                        temp = game_map.rooms[number]
                        logging.info(f"room info: {temp}")
                        desc = temp["desc"]
                        logging.info(f"desc: {desc}")
                        """
                        # FIXME: see server.py, line 24:
                        #  thought maybe this would show the new room desc
                        return Message(lines=["You move down."],
                                       changes={K.room_name: room.name,
                                                K.room: room.desc}
                        )
                    else:
                        logging.debug("parser: %s moves Down to Shoppe" % player.name)
                        player.move(next_room=room_transport, direction='d')

                        # don't change player.room, return them to where they left
                        return Message(lines=["TODO: write Shoppe routine..."])

                else:
                    return Message(lines=["Ye cannot travel that way."])

            if cmd[0] in ['l', 'look']:
                room = game_map.rooms[player.room]
                return self.room_msg(lines=room.desc)

            if cmd[0] in ['bye', 'logout', 'quit']:
                temp = net_server.UserHandler.prompt_request(self, lines=[], prompt='Really quit? ',
                                                            choices={'y': 'yes', 'n': 'no'})
                # returns a Cmd object?
                logging.info(f'{temp=}')
                # extract value from returned dict, e.g.: temp={'text': 'y'}
                if temp.get('text') == 'y':
                    player.save()
                    player.disconnect()
                    return Message(lines=["Bye for now."], mode=Mode.bye)
                else:
                    return Message(lines=["Thanks for sticking around."])

            if cmd[0] in ['?', 'hel', 'help']:
                from tada_utilities import game_help
                game_help(self, cmd)
                return Message(lines=["Done."])

            if cmd[0] in ['cheatcode']:
                return Message(lines=["↑ ↑ ↓ ↓ ← → ← → B A"])

            # toggle room descriptions:
            if cmd[0] in ['r']:
                player.toggle_flag(PlayerFlags.ROOM_DESCRIPTIONS, verbose=True)
                return Message(lines=[f'[Room descriptions are now '
                                      f'{"off" if temp is False else "on"}.]'])

            if cmd[0] == 'who':
                # TODO: add login time, calculate how long player has been on
                import net_server as ns
                lines = ["\nWho's on:\n"]
                for count, login_id in enumerate(ns.connected_users, start=1):
                    lines.append(f'{count:2}) {players[login_id].name}')
                return Message(lines=lines)

            # really this is just a debugging tool to save shoe leather:
            if cmd[0][:1] == "#":
                temp = cmd[0][1:]
                if temp.isdigit() is False:
                    return Message(lines=["(Room number required after '#'.)"])
                val = int(temp)
                try:
                    # get destination room data:
                    dest = game_map.rooms[val]
                    room_num = dest.number
                    # delete player id from list of players in current room,
                    # add player id to list of players in room they moved to
                    # 'direction' is None, so display "{player} disappears in a flash of light."
                    player.move(room_num, direction=None)

                    # move player there:
                    player.room = room_num
                    logging.debug("parser: moved to room #%i, %s" % (room_num, player.room))
                    # TODO: something like this displayed to other players would be nice to indicate teleportation:
                    #  Message([f"{player.name} disappears in a flash of light.")
                    # TODO: display new room description
                    return Message(lines=[f"You teleport to room #{val}, {dest.name}.\n"])
                    # changes={"prompt": "Prompt:", "status_line": 'Status Line'})
                except KeyError:
                    return Message(lines=[f'Teleport: No such room yet (#{val}, '
                                          f'max of {max(game_map.rooms)}).'])

            """
            FIXME: Under consideration, but not sure how to set this up
            if cmd[0] == 'petscii':
                header = 'PetSCII Strings:'
                midline = b'\xc0' * len(header)  # solid '-'
                lines = [f'{header}', f'{midline}',
                         'HELLO 123 @!\x5c = HELLO 123 @!£',
                         '\x12 \uf11a',  # reverse video
                         '\xd3 ♥',
                         '\xff π',
                         '✓'
                         ]
                for line in lines:
                    # must ignore \x0a (linefeed), gives MappingError
                    temp = line + '\n'
                    # data = temp.encode(encoding='petscii-c64en-lc', errors='ignore')
                    data = temp.encode(encoding='utf-8', errors='ignore')
                    logging.info("parser: data=%s" % type(data))  # type = bytes
                    data_dict = dict(data)
                    net_server.UserHandler.message(net_common.toJSONB(data_dict))
                    net_server.UserHandler.message(, "This should be PetSCII.\r")  # socket: request.sendall(data)
            """
            # invalidate repeating last_command
            player.last_command = None
            return Message(lines=["I didn't understand that.  Try something else."])
        else:
            # otherwise, not a valid server message?:
            logging.error("parser: unexpected message '%s'" % cmd)
            return Message(lines=["parser: Unexpected message '{cmd}'."], mode=Mode.bye)


def break_handler(msg, event):
    # TODO: also 'shutdown' admin command could call this code
    logging.warning("break_handler: Shutting down on thread id: %x" %
                    id(threading.current_thread()))
    # TODO: broadcast shutdown message to all players
    logging.info("break_handler: Server going down. Bye.")
    # TODO: Handle any cleanup here; try to save player/server state
    logging.info("break_handler: Shutdown complete.")
    event.set()


if __name__ == "__main__":
    # set up logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    import signal

    # exit gracefully when SIGINT is received
    # https://stackoverflow.com/questions/17550389/shut-down-socketserver-on-sig/18243619#18243619
    doneEvent = threading.Event()
    logging.info("init: Main thread id: %x" % id(threading.current_thread()))

    wrapper = textwrap.TextWrapper(width=80)

    # load game data
    # load map
    game_map = Map()
    game_map.read_map("level_1.json")

    # rooms = {}
    # for data in game_map.rooms:
    #     print(type(data.number))
    #     n = int(data.number)
    #     room = Room(number=n, name=data.name, desc=data.desc, exits=data.exits,
    #                 monster=data.monster, item=data.item, weapon=data.weapon, food=data.food,
    #                 alignment=data.alignment)
    #     rooms[data.number] = room
    # FIXME: determine how this works, it just copies 'set()' for each item in the list:
    room_players = {number: set() for number in game_map.rooms.keys()}
    logging.debug('init: %s' % room_players)

    # load items
    items = Item.read_items("objects.json")

    # load monsters
    monsters = Monster.read_monsters("monsters.json")

    # load weapons
    weapons = Weapons.read_weapons("weapons.json")

    # load rations
    rations = Rations.read_rations("rations.json")

    host = "localhost"
    net_server.start(host, common.server_port, common.app_id, common.app_key,
                     common.app_protocol, PlayerHandler)
