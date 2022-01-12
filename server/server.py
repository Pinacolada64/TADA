#!/bin/env python3

import os
import json
import threading
from dataclasses import dataclass, field
import textwrap
import collections  # for defaultdict behavior

import net_server
import net_common
import common
import util

# import players

K = common.K
Mode = net_server.Mode
Message = net_server.Message

# fake data - make sure keys match class Room
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

room_start = 1
money_start = 1000

compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West'}


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
    alignment: str = "neutral"

    def exitsTxt(self):
        # connection/transport names, index by (connection, transport)
        extra_txts = {(1, 0): 'Up to Shoppe', (1, 1): 'Up',
                      (2, 0): 'Down to Shoppe', (2, 1): 'Down'}
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:
                exit_txts.append(compass_txts[k])
        room_connection = self.exits.get('rc', 0)
        room_transport = self.exits.get('rt', 0)
        exit_extra = extra_txts.get((room_connection, room_transport))
        if exit_extra is not None:
            exit_txts.append(exit_extra)
        return ", ".join(exit_txts)


rooms = {}
for info in roomsData:
    room = Room(number=info[K.number], name=info[K.name], desc=info[K.desc], exits=info[K.exits])
    rooms[room.number] = room

server_lock = threading.Lock()
room_players = {id: set() for id in rooms.keys()}


def playersInRoom(room_id: int, exclude_id: str):
    """
    return a dict of player login id's in the room

    :param room_id: room number
    :param exclude_id: player to exclude (often yourself, to not be listed)
    :return: dict of players
    """
    with server_lock:
        players_in_room = room_players[room_id]
    if exclude_id is not None:
        players_in_room = players_in_room.difference(set([exclude_id]))
    logging.info(f'{players_in_room}')
    return players_in_room


players = {}


# @dataclass
class Player:
    """
    id: str  # login id
    name: str  # player's handle
    map_level: int = 1
    room: int = 1
    money: int = 1000
    health: int = 100
    xp: int = 0

    this is to create default values for missing player.flag['foo'],
    instead of hand-editing 'player-<foo>.json' or getting KeyErrors
    if dict key player.flag['foo'] is undefined in said file
    https://docs.python.org/3.8/library/dataclasses.html?highlight=dataclass#dataclasses.field
    
    this is useful also, but cannot be used in the dataclass context:
    https://docs.python.org/3/library/collections.html?highlight=default%20factory#collections.defaultdict

    # flag: dict = field(default_factory=dict)
    flag: dict = field(default_factory=lambda: {})
    # for saving previous command to repeat with Return/Enter
    # (it may be expanded to a list in the future):
    last_command: str = None
    """

    def __init__(self, id, name, map_level, room, money, health, xp,
                 flag, last_command):
        logging.info("Instantiating player.")
        self.id: str = id  # login id
        self.name: str = name  # player's handle
        self.map_level: int = map_level  # to differentiate between eXPerience level
        self.room: int = room  # default: room_start = 1
        self.money: int = money  # default: money_start = 1000
        self.health: int = health  # default 100
        self.xp: int = xp
        self.flag = dict(flag)
        self.last_command: str = last_command

    def connect(self):
        with server_lock:
            room_players[self.room].add(self.id)

    def move(self, next_room: int):
        """
        remove player from list of players in current_room, add them to room next_room
        """
        current_room = self.room
        with server_lock:
            room_players[current_room].remove(self.id)
            self.room = next_room
            room_players[self.room].add(self.id)
            logging.info(f'{self.room=}')

    def disconnect(self):
        with server_lock:
            room_players[self.room].remove(self.id)

        # FIXME: is this orphaned code?
        #  print(f"You are in {self.room}.\n{playersInRoom(self.room)} is here.")

    @staticmethod
    def _json_path(user_id):
        return os.path.join(net_common.run_server_dir, f"player-{user_id}.json")

    @staticmethod
    def load(user_id):
        path = Player._json_path(user_id)
        if os.path.exists(path):
            with open(path) as jsonF:
                lh_data = json.load(jsonF)
            return Player(**lh_data)
        else:
            return None

    def save(self):
        with open(Player._json_path(self.id), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                                                      in o.__dict__.items() if v}, indent=4)
        return Message(lines=[f'Saved {self.name}.'])


class PlayerHandler(net_server.UserHandler):
    def initSuccessLines(self):
        return ['Welcome to:\n', 'Totally\nAwesome\nDungeon\nAdventure\n', 'Please log in.']

    def loginFailLines(self):
        return ['Please try again.']

    def roomMsg(self, lines, changes):
        # if lines is None:
        #     lines = []
        # if changes is None:
        #     changes = {}
        lines.append(["above status line?"])
        room = rooms[self.player.room]
        exitsTxt = room.exitsTxt()
        lines2 = list(lines)
        lines2.append(f"{f'#{room.number} ' if self.player.flag['debug'] else ''}"
                      f"{room.name} [{room.alignment}]")
        # FIXME:
        if self.player.flag['room_descs'] is True:
            lines2.append(f'{wrapper.fill(text=room.desc)}')
        lines2.append(f"Ye may travel: {exitsTxt}\n")

        # setting 'exclude_id' excludes that player (i.e., yourself) from being listed
        other_player_ids = playersInRoom(room.number, exclude_id=self.player.id)
        # TODO: "Alice is here." / "Alice and Bob are here." / "Alice, Bob and Mr. X are here."
        # if len(other_player_ids) == 0:
        #     logging.info("No other players here.")
        # if len(other_player_ids) > 0:
        #     result_list = []
        #     result_list.append(i for i in other_player_ids)
        #     if len(result_list) == 1:
        #         result_list = f"{result_list} is"
        #     if len(result_list) > 1:
        #         # tanabi: Add 'and' if we need it
        #         # result_list = f"and {result_list[:-1]} are"
        #         pass
        # other_player_ids = playersInRoom(room.id, self.player.id)
        # lines2.append(f"{result_list} here.")
        if len(other_player_ids) > 0:
            other_players = ', '.join([players[id].name for id in other_player_ids])
            lines2.append(f"Other adventurers in the room:  {other_players}")
            return Message(lines=[lines, lines2], changes=changes)

    def processLoginSuccess(self, user_id):
        player = Player.load(user_id)
        if player is None:
            # TODO: create player
            valid_name = False
            while not valid_name:
                reply = self.promptRequest(lines=["Choose your adventurer's name."], prompt='Name? ')
                name = reply['text'].strip()
                if name != '':  # TODO: limitations on valid names
                    valid_name = True
            player = Player(id=user_id, name=name, room=room_start, money=money_start)
            player.save()
        self.player = players[user_id] = player
        logging.info(f"login {user_id} '{self.player.name}' (addr={self.sender})")
        money = self.player.money
        lines = [f"Welcome, {self.player.name}.", f"You have {money} gold.\n"]

        # show/convert flags from json text 'true/false' to bool True/False
        # (otherwise they're not recognized, and can't be toggled):
        for k, v in self.player.flag.items():
            if self.player.flag[k] == 'true':
                self.player.flag[k] = True
            if self.player.flag[k] == 'false':
                self.player.flag[k] = False
            logging.info(f'{k=} {v=}')

        changes = {K.room_name: rooms[self.player.room].name,
                   K.money: money, K.health: self.player.health,
                   K.xp: self.player.xp}
        self.player.connect()
        return self.roomMsg(lines, changes)

    def processMessage(self, data):
        logging.info('processMessage()')
        if 'text' in data:
            cmd = data['text'].lower().split(' ')
            logging.info(f"{self.player.id}: {cmd}")
            # update last command to repeat with Return/Enter
            # if an invalid command, set to None later
            # TODO: maybe maintain a history
            self.player.last_command = cmd
            logging.info(f'{self.player.last_cmd=}')
            # TODO: handle commands with parser etc.

            if cmd[0] in compass_txts:
                logging.info(f'current room: {self.player.room}')
                logging.info(f"direction: {cmd[0]}")
                # 'rooms' is a list of Room objects?
                logging.info(f'{rooms}')
                logging.info(f'exits: {self.player.room}')
                # >>> exits = {'n': 1, 's': 3}
                # >>> exits.keys()
                # dict_keys(['n', 's'])
                # cmd.insert(0, 'go') probably not necessary
                # json data (dict):
                direction = cmd[0]
                logging.info(f'{direction=} {self.player.room=}')
            """room = room.exits[direction]
                # check if it's a movable direction
                logging.info(f"dir: {direction} => {room.exits.keys(direction)=}")
                # delete player from list of players in current room,
                # add player to list of players in room being moved to
                self.player.move(room.exits[direction])
                # FIXME: maybe only at quit
                # self.player.save()
                self.player.room = room.exits[direction]
                return Message(lines=[f"You move {compass_txts[direction]}."])
            else:
                return Message(lines=["Ye cannot travel that way."])
            """
            if cmd[0] in ['l', 'look']:
                return self.roomMsg(lines=[], changes={})
            if cmd[0] in ['bye', 'logout', 'quit']:
                temp = net_server.UserHandler.promptRequest(self, lines=[], prompt='Really quit? ',
                                                            choices={'y': 'yes', 'n': 'no'})
                # returns a Cmd object?
                logging.info(f'{temp=}')
                # extract value from returned dict, e.g.: temp={'text': 'y'}
                if temp.get('text') == 'y':
                    self.player.save()
                    self.player.disconnect()
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
                logging.info(f"{self.player.flag['room_descs']}")
                self.player.flag['room_descs'] = not self.player.flag['room_descs']
                temp = self.player.flag['room_descs']
                logging.info(f'Room descriptions: {temp}.')
                return Message(lines=[f'Room descriptions are now '
                                      f'{"off" if temp is False else "on"}.'])
            else:
                # invalidate repeating last_command
                self.player.last_command = None
                return Message(lines=["I didn't understand that.  Try something else."])
        else:
            logging.error("unexpected message")
            return Message(lines=["Unexpected message."], mode=Mode.bye)


def break_handler(signal_received, frame):
    # Handle any cleanup here
    logging.warning(f'{signal_received} SIGINT or Ctrl-C detected. Shutting down server.')
    # TODO: broadcast shutdown message to all players
    print("Server going down. Bye.")
    exit(0)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    import signal

    # exit gracefully when SIGINT is received
    # signal(SIGINT, handler)  # for *nix
    signal.signal(signal.SIGINT, break_handler)  # for Windows

    wrapper = textwrap.TextWrapper(width=80)

    host = "localhost"
    net_server.start(host, common.server_port, common.app_id, common.app_key,
                     common.app_protocol, PlayerHandler)
