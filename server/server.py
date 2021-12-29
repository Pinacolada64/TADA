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
    {K.id: 'ul', K.name: 'Upper Left',  K.exits: {'s': 'll', 'e': 'ur'}},
    {K.id: 'ur', K.name: 'Upper Right', K.exits: {'s': 'lr', 'w': 'ul'}},
    {K.id: 'll', K.name: 'Lower Left',  K.exits: {'n': 'ul', 'e': 'lr'}},
    {K.id: 'lr', K.name: 'Lower Right', K.exits: {'n': 'ur', 'w': 'll'}},
]

room_start = 'ul'
money_start = 1000

compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West'}

@dataclass
class Room(object):
    id: str
    name: str
    exits: dict

    def exitsTxt(self): 
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:  exit_txts.append(compass_txts[k])
        return ", ".join(exit_txts)

rooms = {}
for info in roomsData:
    room = Room(id=info[K.id], name=info[K.name], exits=info[K.exits])
    rooms[room.id] = room

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
    id: str
    name: str
    room: str
    money: int
    health: int = 100
    xp: int = 0

    def connect(self):
        with server_lock:
            room_players[self.room].add(self.id)

    def move(self, next_room):
        prev_room = self.room
        with server_lock:
            room_players[self.room].remove(self.id)
            self.room = next_room
            room_players[self.room].add(self.id)

    def disconnect(self):
        with server_lock:
            room_players[self.room].remove(self.id)

        print(f"room {self.room} players:  {playersInRoom(self.room)}")

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

players = {}

class PlayerHandler(net_server.UserHandler):

    def initSuccessLines(self):
        return ['TADA!', 'Please log in.']

    def loginFailLines(self):
        return ['please try again.']

    def roomMsg(self, lines=[], changes={}):
        room = rooms[self.player.room]
        room_name = room.name
        exitsTxt = room.exitsTxt()
        lines2 = list(lines)
        lines2.append(f"You are in {room_name} with exits to {exitsTxt}")
        other_player_ids = playersInRoom(room.id, self.player.id)
        if len(other_player_ids) > 0:
            other_players = ', '.join([players[id].name for id in other_player_ids])
            lines2.append(f"Other adventurers in the room:  {other_players}")
        return Message(lines=lines2, changes=changes)

    def processLoginSuccess(self, user_id):
        player = Player.load(user_id)
        if player is None:
            # create player
            valid_name = False
            while not valid_name:
                reply = self.promptRequest(lines=["Choose your adventurer's name."], prompt='name? ')
                name = reply['text'].strip()
                if name != '':  #TODO: limitations on valid names
                    valid_name = True
            player = Player(id=user_id, name=name, room=room_start, money=money_start)
            player.save()
        self.player = players[user_id] = player
        print(f"login {user_id} '{self.player.name}' (addr={self.sender})")
        money = self.player.money
        lines = [f"Welcome {self.player.name}.", f"You have {money} gold."]
        changes = {K.room_name: rooms[self.player.room].name,
                K.money: money, K.health: self.player.health,
                K.xp: self.player.xp}
        self.player.connect()
        return self.roomMsg(lines, changes)

    def processMessage(self, data):
        if 'text' in data:
            cmd = data['text'].split(' ')
            #TODO: handle commands with parser etc.
            if cmd[0] in compass_txts:  cmd.insert(0, 'go')
            print(f"{self.player.id} {cmd=}")
            if cmd[0] in ['g', 'go']:
                direction = cmd[1]
                room = rooms[self.player.room]
                if direction in room.exits:
                    self.player.move(room.exits[direction])
                    self.player.save()
                    room_name = rooms[self.player.room].name
                    return self.roomMsg(changes={'room_name': room_name})
                else:
                    return Message(lines=["You cannot go that direction."])
            if cmd[0] in ['look']:
                return self.roomMsg()
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
                return Message(lines=["I didn't understand that.  Try something else."])
        else:
            print("ERROR: unexpected message")
            return Message(lines=["Unexpected message."], mode=Mode.bye)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    host = "localhost"
    net_server.start(host, common.server_port, common.app_id, common.app_key,
            common.app_protocol, PlayerHandler)

