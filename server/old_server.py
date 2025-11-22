#!/bin/env python3

import threading
from dataclasses import dataclass, field
import textwrap
import logging
from datetime import datetime
from typing import Optional

import net_common
# TADA-specific imports
import net_server
import common

from flags import PlayerFlags
from player import Player
from base_classes import PlayerMoneyTypes, Map, compass_txts
from items import Weapon, Rations, Item
from tada_utilities import list_players_in_room
from net_common import Message

K = common.K
Mode = net_common.Mode
# Message = net_server.Message
# room_start = 1
# money_start = 1000

server_lock = threading.Lock()


def players_in_room(room_id: int, exclude_id: str | None) -> list:
    """
    Return a list of player login id's in the room

    :param room_id: room number
    :param exclude_id: player to exclude (often the player executing the command) to not be listed
    :return: list of players
    """
    with server_lock:
        players_in_room = room_players[room_id]
    if exclude_id is not None:
        players_in_room = players_in_room.difference({exclude_id})
        logging.debug("Excluding %s" % exclude_id)
    logging.debug("Players in room %i: %s" % (room_id, players_in_room))
    return list(players_in_room)


players = {}

"""
@dataclass
class OldPlayer:
    '''
    Attributes, flags and other stuff about characters.
    '''
    from characters import Monster
    # inventory:
    armor: list[Armor]  # list of Armor objects

    honor_rating: int  # helps determine current_alignment
    formal_training: int
    monsters_killed: list[Monster]
    '''
    monsters_killed is not always the same as dead_monsters[];
    still increment it if you re-kill a re-animated monster
    '''
    dead_monsters: list[Monster]  # keeps track of monsters for Zelda in the bar to resurrect
    monster_at_quit: Optional[Monster]

    # class VinneyLoan(self):
    #     self.loan_amount: int
    #     self.due_date: datetime

    # inventory
    '''
    # TODO: There should be methods here for Inventory:
        Inventory.item_held(item): check player/ally inventory, return True or False
     (is it important to know whether the player or ally is carrying an item?)
     maybe return Character or Ally object if they hold it, or None if no-one holds it
     Or could be written:

     if 'armor' in Character.inventory and 'armor' in Character.used:
     # meaning 'armor' is in 'inventory' and 'used' lists?
     # could this be shortened? perhaps:
     # if Character.ItemHeldUsed('armor'):
    '''
    max_inv: int
    # also see weapons[], armor[], shields[]
    food: list
    drink: list
    spells: list  # list of dicts('spell_name': str, 'charges', 'chance_to_cast': int)
    booby_traps: list

    # FIXME: how to distinguish between offline characters and online?
    last_connection: datetime

    special_items: dict
    # SCRAP OF PAPER is randomly placed on level 1 with a random elevator combination
    # TODO: avoid placing objects in map "holes" where no room exists
    # DINGHY  # does not actually need to be carried around in inventory, I don't suppose, just a flag?

    last_command: list

    def __init__(self):
        self.silver = None
"""


class PlayerHandler(net_server.UserHandler):
    def init_success_lines(self):
        return ['Welcome to:\n', 'Totally\nAwesome\nDungeon\nAdventure\n', 'Please log in.']

    def login_fail_lines(self):
        return ['Please try again.']

    def output(self, lines):
        logging.info("output: %s" % lines)
        self._send_data(Message(lines=lines))

    def room_msg(self, lines: str | list, changes: dict, player: "Player"):
        """
        Display the room description and contents to the player in the room

        :param lines: text to output. each line is an element of a list.
        :param changes: K.Enum (common.py). what has changed and needs to be updated client-side
            (e.g., if moved to a new room: changes={K.name: room.name, K.desc: room.desc}
        :return: Message object
        """
        from player import Player
        # get room # that player is in
        room = None
        try:
            room = game_map.rooms[player.map_room]
        except KeyError:
            logging.warning("Room %i does not exist" % player.map_room)

        debug = player.query_flag(PlayerFlags.DEBUG_MODE)
        exits_txt = room.exits_Txt(debug)
        lines2 = list(lines)

        # display room header
        # check for/trim room flags (currently only '->' for "hidden exit to the east"):
        temp = room.name.rfind("|")
        room_name = room.name
        room_flags = ''
        if temp != -1:
            room_name = room.name[:temp]
            room_flags = room.name[temp + 1:]

        temp = str(room.alignment).title()
        lines2.append(f"{f'#{room.number} ' if debug else ''}{room_name} [{temp}]\n")

        # FIXME: is anything wrong with this?
        if player.query_flag(PlayerFlags.ROOM_DESCRIPTIONS):
            lines2.append(f'{wrapper.fill(text=room.desc)}')

        # is an item in the current room?
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

        # TODO: call tada_utilities.grammatical list item (SOME MELONS, AN ORANGE)

        debug = player.query_flag(PlayerFlags.DEBUG_MODE)
        exits_txt = room.exitsTxt(debug)
        if exits_txt is not None:
            lines2.append(f"Ye may travel: {exits_txt}")
            # ryan: list exit dirs and room #s
            if debug:
                for k, v in room.exits.items():
                    logging.debug("Exit '%s' to '%s'", (k, v))

        # show item in room:
        # num = 62  # zero-based numbering, so subtract one to get actual object
        # logging.info(f'item #{num} name: {items[num - 1]["name"]}')

        # setting 'exclude_id' excludes that player (i.e., yourself) from being listed
        other_player_ids = players_in_room(room.number, exclude_id=player.id)
        # TODO: "Alice is here." / "Alice and Bob are here." / "Alice, Bob and Mr. X are here."
        lines2.append(f"{list_players_in_room(other_player_ids)}")
        return Message(lines=lines2, changes=changes)

    def process_login_success(self, user_id):
        from player import Player
        player = Player.load(user_id)
        if player is None:
            player = self.create_new_player()
        players[user_id] = player
        logging.info("login %s ('%s', IP addr=%s)" % (user_id, player.name, self.sender))
        silver = player.silver[PlayerMoneyTypes.IN_HAND]
        lines = [f"Welcome, {player.name}.",
                 f"You have {silver:,} silver in hand.", ""]

        changes = {K.room_name: game_map.rooms[player.room].name,
                   K.silver: player.silver, K.hit_points: player.hit_points,
                   K.experience: player.experience}
        player.connect()
        return self.room_msg(lines, changes)

    def create_new_player(self) -> None:
        logging.info("No player data, entering create_new_player().")
        player = Player()
        import create_character
        from flags import PlayerFlags
        valid_name = False
        self.output(["create_new_player: This is a test of socket output."], player)
        self.flush_output()
        """
        while not valid_name:
            reply = self.prompt_request(["Choose your adventurer's name."], prompt='Name? ')
            name = reply['text'].strip()
            if name != '':  # TODO: limitations on valid names
                valid_name = True
        lines = ["Name: %s" % name]
        player.name = name
        """
        lines = [f"User ID: {player.id}"]
        player.set_flag(PlayerFlags.DEBUG_MODE)
        # *** Debug Mode: On
        lines.append(f"*** {player.show_flag(PlayerFlags.DEBUG_MODE)}")
        player.clear_flag(PlayerFlags.EXPERT_MODE)
        # *** Expert Mode: Off
        lines.append(f"*** {player.show_flag(PlayerFlags.EXPERT_MODE)}")
        player.set_flag(PlayerFlags.ROOM_DESCRIPTIONS)
        # *** Room Descriptions: On
        lines.append(f"*** {player.show_flag(PlayerFlags.ROOM_DESCRIPTIONS)}")
        self.output(lines, player)
        # Send accumulated output to client before entering debug menu
        self.flush_output()
        create_character.debug_menu(self, player)
        player.save()

        from player import Player
        # TODO: add more error-checking here:
        character = Player.load(user_id)
        if character is None:
            logging.info("No data; instantiating new player")
            character_setup = {"name": None, "attribute": "whatever"}
            character = Player(**character_setup)
        if character.last_play_date is None:
            logging.debug("Player 'last play date' is None; calling create_character.")
            import create_character
            create_character.main(character)
            # FIXME: this shows The Right Way to Do Responses server-side (i.e., it Works):
            """
            valid_name = False
            while not valid_name:
                reply = self.prompt_request(["Choose your adventurer's name."], prompt='Name? ', choices = {})
                name = reply['text'].strip()
                if name != '':  # TODO: limitations on valid names
                    valid_name = True
            # NEW: Player() takes dict of settings:
            player_settings = {'id': user_id, 'name': name, 'map_level': 1, 'map_room': 1, 'hit_points': 100,
                               'last_command': None}
            character = Player(**player_settings)
            """
            character.set_flag(PlayerFlags.DEBUG_MODE)
            character.clear_flag(PlayerFlags.EXPERT_MODE)
            character.set_flag(PlayerFlags.ROOM_DESCRIPTIONS)
            character.save()

        player = players[user_id] = character
        logging.info("Login %s ('%s', IP address: %s)" % (user_id, player.name, self.sender))
        silver = player.silver[PlayerMoneyTypes.IN_HAND]
        lines = [f"Welcome, {player.name}.",
                 f"You have {silver:,} silver in hand.\n"]

        # show/convert flags from JSON text 'true/false' to bool True/False
        # (otherwise they're not recognized and can't be toggled):
        # TODO: move this to Player.load() ? and do the reverse in Player.save() ?
        for k, v in player.flag.items():
            if player.flag[k] == 'true':
                player.flag[k] = True
            if player.flag[k] == 'false':
                player.flag[k] = False
            logging.debug("Updated json flag %s: %s" % (k, v))

        changes = {K.room_name: game_map.rooms[player.room].name,
                   K.silver: player.silver, K.hit_points: player.hit_points,
                   K.experience: player.experience}
        player.connect()
        return self.room_msg(lines, changes, character)

    def process_message(self, data, player: Player):
        if 'text' in data:
            cmd = data['text'].lower().split(' ')
            logging.debug("User ID=%s, command=%s" % (player.id, cmd))
            # update last command to repeat with Return/Enter
            # if an invalid command, set to None later
            # TODO: maybe maintain a history
            player.last_command = cmd
            logging.debug("User ID '%s' last cmd: %s" %
                         (player.id, player.last_command))

            # TODO: handle commands with parser etc.


            if cmd[0] in ['l', 'look']:
                room = game_map.rooms[player.room]
                # FIXME: not sure this works
                return self.room_msg(lines=K.desc, changes={K.room_name: room.name})

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
                # Konami code!
                return Message(lines=["↑ ↑ ↓ ↓ ← → ← → B A"])

            # toggle room descriptions:
            if cmd[0] in ['r', 'roo', 'room']:
                temp = player.query_flag(PlayerFlags.ROOM_DESCRIPTIONS)
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
            logging.error("parser: unexpected message '%s'" % player.last_command)
            return Message(lines=["parser: Unexpected message '{cmd}'."], mode=Mode.bye)


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

    def exitsTxt(self, debug: bool):
        """
        Display exits in a comma-delimited list.

        IMPORTANT: historical TADA/map semantics
        - 'rc' is the connection flag indicating an up/down connection type:
            rc == 1 => connection is 'Up'
            rc == 2 => connection is 'Down'
            rc == 0 or missing => no up/down connection
        - 'rt' is the transport target (room number) when an up/down connection exists:
            rt == 0 => special case (Shoppe)
            rt > 0  => the room number to transport the player to

        The combination (rc, rt) determines the textual output for special exits.
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
        # defensively coerce stored values to ints if they are strings from JSON
        try:
            room_connection = int(self.exits.get('rc', 0) or 0)
        except Exception:
            room_connection = 0
        try:
            room_transport = int(self.exits.get('rt', 0) or 0)
        except Exception:
            room_transport = 0

        exit_extra = extra_txts.get((room_connection, room_transport))
        if exit_extra:  # is not None:
            exit_txts.append(exit_extra)
        # example: level 1, room 20
        if room_connection == 1 and room_transport != 0:
            exit_txts.append(f"Up to #{room_transport}" if debug else "Up")
        if room_connection == 2 and room_transport != 0:
            exit_txts.append(f"Down to #{room_transport}" if debug else "Down")
        return ", ".join(exit_txts)

    def process_message(self, data, player: Player):
        if 'text' in data:
            cmd = data['text'].lower().split(' ')
            logging.debug("User ID=%s, command=%s" % (player.id, cmd))
            # update last command to repeat with Return/Enter
            # if an invalid command, set to None later
            # TODO: maybe maintain a history
            player.last_command = cmd
            logging.debug("User ID '%s' last cmd: %s" %
                         (player.id, player.last_command))

            # TODO: handle commands with parser etc.


            if cmd[0] in ['l', 'look']:
                room = game_map.rooms[player.room]
                # FIXME: not sure this works
                return self.room_msg(lines=K.desc, changes={K.room_name: room.name})

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
                # Konami code!
                return Message(lines=["↑ ↑ ↓ ↓ ← → ← → B A"])

            # toggle room descriptions:
            if cmd[0] in ['r', 'roo', 'room']:
                temp = player.query_flag(PlayerFlags.ROOM_DESCRIPTIONS)
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
            logging.error("parser: unexpected message '%s'" % player.last_command)
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
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() - %(message)s')

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
    from characters import Monster

    monsters = Monster.read_monsters("monsters.json")

    # load weapons
    weapons = Weapon.read_weapons("weapons.json")

    # load rations
    rations = Rations.read_rations("rations.json")

    host = "localhost"
    net_server.start(host, common.server_port, common.app_id, common.app_key,
                     common.app_protocol, PlayerHandler)
