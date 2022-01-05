#!/bin/env python3

import os
import json
import threading
from dataclasses import dataclass, field

import net_server
import net_common
import common
import util

K = common.K
Mode = net_server.Mode
Message = net_server.Message

# fake data
roomsData = [
    {K.number: 1, K.name: 'Upper Left',  K.exits: {'s': 3, 'e': 2}},
    {K.number: 2, K.name: 'Upper Right', K.exits: {'s': 4, 'w': 1}},
    {K.number: 3, K.name: 'Lower Left',  K.exits: {'n': 1, 'e': 4}},
    {K.number: 4, K.name: 'Lower Right', K.exits: {'n': 2, 'w': 3}},
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


def playersInRoom(room_id, exclude_id=None):
    with server_lock:
        players_in_room = room_players[room_id]
    if exclude_id is not None:
        players_in_room = players_in_room.difference(set([exclude_id]))
    return players_in_room


@dataclass
class Player(object):
    id: str  # login id
    name: str  # player's handle
    map_level: int = 1
    room: int = 1
    money: int = 1000
    health: int = 100
    xp: int = 0
    # for saving previous command to repeat with Return/Enter:
    last_command: str = None

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
class PlayerHandler(net_server.UserHandler):
    def initSuccessLines(self):
        return ['Welcome to:\n', 'Totally\nAwesome\nDungeon\nAdventure\n', 'Please log in.']

    def loginFailLines(self):
        return ['Please try again.']

    def roomMsg(self, lines=[], changes={}):
        room = rooms[self.player.room]
        room_name = room.name
        exitsTxt = room.exitsTxt()
        lines2 = list(lines)
        lines2.append(f"{room_name}\nYe may travel: {exitsTxt}")
        # setting exclude_id doesn't list that player (i.e., yourself)
        other_player_ids = playersInRoom(room.number, self.player.id)
        if len(other_player_ids) > 0:
            other_players = ', '.join([players[id].name for id in other_player_ids])
            lines2.append(f"Other adventurers in the room:  {other_players}")
        return Message(lines=lines2, changes=changes)

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
        lines = [f"Welcome, {self.player.name}.", f"You have {money} gold."]
        changes = {K.room_name: rooms[self.player.room].name,
                   K.money: money, K.health: self.player.health,
                   K.xp: self.player.xp}
        self.player.connect()
        return self.roomMsg(self, lines, changes)

    def processMessage(self, data):
        if 'text' in data:
            cmd = data['text'].lower().split(' ')
            logging.info(f"{self.player.id} {cmd=}")
            # update last command to repeat with Return/Enter
            # if an invalid command, set to None later
            # TODO: maybe maintain a history
            self.player.last_cmd = cmd
            # TODO: handle commands with parser etc.
            if cmd[0] in compass_txts:
                # cmd.insert(0, 'go') probably not necessary
                # json data (dict):
                direction = cmd[0:1]
                if direction in ['n', 'e', 's', 'w']:
                    # check room.exits for 'direction'
                    logging.info("dir: n/e/s/w")
                    if direction in room.exits:
                        try:
                            # FIXME: maybe only at quit
                            # self.player.save()
                            # delete player from list of players in current room,
                            # add player to list of players in room being moved to
                            self.player.move(room.exits[direction])
                            print(f"You move {compass_txts[direction]}.")
                            try:
                                self.player.room_id = room.exits[direction]
                            except KeyError:
                                logging.info("exception: No such room yet (37, Bar?).")
                        except ValueError:
                            print("exception: Ye cannot travel that way.")
                    else:
                        return Message(lines=["Ye cannot travel that way."])
            if cmd[0] in ['l', 'look']:
                return self.roomMsg(lines=[], changes={})
            if cmd[0] in ['bye', 'logout', 'quit']:
                temp = net_server.UserHandler.promptRequest(self, lines=[], prompt='Really quit? ',
                                                            choices={'y': 'yes', 'n': 'no'})
                # returns a Cmd object?
                logging.info(f'{temp=}')
                # extract value from returned dict, e.g.: temp={'text': 'y'}
                if temp.get('text') == 'y':
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
            else:
                # invalidate repeating last_command
                self.player.last_cmd = None
                return Message(lines=["I didn't understand that.  Try something else."])
        else:
            logging.error("unexpected message")
            return Message(lines=["Unexpected message."], mode=Mode.bye)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    host = "localhost"
    net_server.start(host, common.server_port, common.app_id, common.app_key,
                     common.app_protocol, PlayerHandler)
