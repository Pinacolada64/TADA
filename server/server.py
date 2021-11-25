#!/bin/env python3

import threading
from dataclasses import dataclass, field

import net_server
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

playersData = [
    {K.id: 'ryan', K.name: 'Ryan', K.money: 1000, K.room: 'ul',
            K.health: 100, K.xp: 0},
    {K.id: 'core', K.name: 'Core', K.money: 10, K.room: 'ul',
            K.health: 99, K.xp: 0},
    {K.id: 'jam', K.name: 'Jam', K.money: 10000, K.room: 'ul',
            K.health: 101, K.xp: 7},
    {K.id: 'x', K.name: 'Mr. X', K.money: 1, K.room: 'ul',
            K.health: 2, K.xp: 3},
]

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

@dataclass
class Player(object):
    id: str
    name: str
    money: int
    room: str
    health: int
    xp: int

rooms = {}
for info in roomsData:
    room = Room(id=info[K.id], name=info[K.name], exits=info[K.exits])
    rooms[room.id] = room

players = {}
for info in playersData:
    player = Player(id=info[K.id], name=info[K.name], money=info[K.money],
            room=info[K.room], health=info[K.health], xp=info[K.xp])
    players[player.id] = player

server_lock = threading.Lock()
room_players = {id: set() for id in rooms.keys()}

class PlayerHandler(net_server.UserHandler):

    def initSucessLines(self):
        return ['TADA!', 'Please log in.']

    def loginFailLines(self):
        return ['please try again.']

    def roomMsg(self, lines=[], changes={}):
        room = rooms[self.player.room]
        room_name = room.name
        exitsTxt = room.exitsTxt()
        lines2 = list(lines)
        lines2.append(f"You are in {room_name} with exits to {exitsTxt}")
        with server_lock:
            other_player_ids = room_players[room.id].difference(set([self.player.id]))
        if len(other_player_ids) > 0:
            other_players = ', '.join([players[id].name for id in other_player_ids])
            lines2.append(f"Other adventurers in the room:  {other_players}")
        return Message(lines=lines2, changes=changes)

    def processLoginSuccess(self, user_id):
        self.player = players[user_id]
        print(f"login {user_id} '{self.player.name}' (addr={self.sender})")
        money = self.player.money
        lines = [f"Welcome {self.player.name}.", f"You have {money} gold."]
        changes = {K.room_name: rooms[self.player.room].name,
                K.money: money, K.health: self.player.health,
                K.xp: self.player.xp}
        with server_lock:
            room_players[self.player.room].add(self.player.id)
        return self.roomMsg(lines, changes)

    def processMessage(self, data):
        if 'cmd' in data:
            cmd = data['cmd'].split(' ')
            #TODO: handle commands with parser etc.
            if cmd[0] in compass_txts:  cmd.insert(0, 'go')
            print(f"{self.player.id} {cmd=}")
            if cmd[0] in ['g', 'go']:
                direction = cmd[1]
                last_room_id = self.player.room
                room = rooms[last_room_id]
                if direction in room.exits:
                    self.player.room = next_room_id = room.exits[direction]
                    with server_lock:
                        room_players[last_room_id].remove(self.player.id)
                        room_players[next_room_id].add(self.player.id)
                    room_name = rooms[self.player.room].name
                    return self.roomMsg(changes={'room_name': room_name})
                else:
                    return Message(lines=["You cannot go that direction."])
            if cmd[0] in ['look']:
                return self.roomMsg()
            if cmd[0] in ['bye', 'logout']:
                with server_lock:
                    room_players[self.player.room].remove(self.player.id)
                return Message(lines=["Bye for now."], mode=Mode.bye)
            if cmd[0] in ['help', 'cheatcode']:
                return Message(lines=["Wouldn't that be nice."])
            else:
                return Message(lines=["I didn't understand that.  Try something else."])
        else:
            print("ERROR: unexpected message")
            return Message(lines=["Unexpected message."], mode=Mode.bye)

if __name__ == "__main__":
    host = "localhost"
    net_server.start(host, common.server_port, common.app_id, common.app_key,
            common.app_protocol, PlayerHandler)

