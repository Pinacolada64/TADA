#!/bin/env python3

from dataclasses import dataclass, field

import net_server
import common
import util

K = common.K
Mode = net_server.Mode
Message = net_server.Message

# fake data 
roomsData = {
    'ul': {K.name: 'Upper Left',  K.exits: {'s': 'll', 'e': 'ur'}},
    'ur': {K.name: 'Upper Right', K.exits: {'s': 'lr', 'w': 'ul'}},
    'll': {K.name: 'Lower Left',  K.exits: {'n': 'ul', 'e': 'lr'}},
    'lr': {K.name: 'Lower Right', K.exits: {'n': 'ur', 'w': 'll'}},
}

playersData = {
    'ryan': {K.name: 'Ryan', K.money: 1000, K.room: 'ul',
            K.health: 100, K.xp: 0},
    'core': {K.name: 'Core', K.money: 10, K.room: 'ul',
            K.health: 99, K.xp: 0},
    'jam': {K.name: 'Jam', K.money: 10000, K.room: 'ul',
            K.health: 101, K.xp: 7},
    'x': {K.name: 'Mr. X', K.money: 1, K.room: 'ul',
            K.health: 2, K.xp: 3},
}

compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West'}

@dataclass
class Room(object):
    name: str
    exits: dict

    def exitsTxt(self): 
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:  exit_txts.append(compass_txts[k])
        return ", ".join(exit_txts)

@dataclass
class Player(object):
    name: str
    money: int
    room: str
    health: int
    xp: int

rooms = {}
for id, info in roomsData.items():
    room = Room(name=info[K.name], exits=info[K.exits])
    rooms[id] = room

players = {}
for user_id, info in playersData.items():
    player = Player(name=info[K.name], money=info[K.money], room=info[K.room],
            health=info[K.health], xp=info[K.xp])
    players[user_id] = player

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
        return Message(lines=lines2, changes=changes)

    def processLoginSuccess(self, user_id):
        self.player = players[user_id]
        print(f"login {user_id} '{self.player.name}' (addr={self.sender})")
        money = self.player.money
        lines = [f"Welcome {self.player.name}.", f"You have {money} gold."]
        changes = {K.room_name: rooms[self.player.room].name,
                K.money: money, K.health: self.player.health,
                K.xp: self.player.xp}
        return self.roomMsg(lines, changes)

    def processMessage(self, data):
        if 'cmd' in data:
            cmd = data['cmd'].split(' ')
            #TODO: handle commands with parser etc.
            if cmd[0] in compass_txts:  cmd.insert(0, 'go')
            print(f"{cmd=}")
            if cmd[0] in ['g', 'go']:
                direction = cmd[1]
                room = rooms[self.player.room]
                if direction in room.exits:
                    self.player.room = room.exits[direction]
                    room_name = rooms[self.player.room].name
                    return self.roomMsg(changes={'room_name': room_name})
                else:
                    return Message(lines=["You cannot go that direction."])
            if cmd[0] in ['look']:
                return self.roomMsg()
            if cmd[0] in ['bye', 'logout']:
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

