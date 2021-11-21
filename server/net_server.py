#!/bin/env python3

import socketserver
import json
from dataclasses import dataclass, field
import enum

# fake data 
K = enum.Enum('K', 'name exits password money room')
roomsData = {
    'ul': {K.name: 'Upper Left',  K.exits: {'s': 'll', 'e': 'ur'}},
    'ur': {K.name: 'Upper Right', K.exits: {'s': 'lr', 'w': 'ul'}},
    'll': {K.name: 'Lower Left',  K.exits: {'n': 'ul', 'e': 'lr'}},
    'lr': {K.name: 'Lower Right', K.exits: {'n': 'ur', 'w': 'll'}},
}
usersData = {
    'ryan': {K.password: 'swordfish', K.money: 1000, K.room: 'ul'},
}

@dataclass
class Room(object):
    name: str
    exits: dict

    def exitsTxt(self): 
        compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West'}
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:  exit_txts.append(compass_txts[k])
        return ", ".join(exit_txts)

@dataclass
class User(object):
    name: str
    password: str
    money: int
    room: str

@dataclass
class Message(object):
    lines: list
    request: str = 'cmd'
    error: int = 0

rooms = {}
for id, info in roomsData.items():
    room = Room(name=info[K.name], exits=info[K.exits])
    rooms[id] = room
users = {}
for name, info in usersData.items():
    user = User(name=name, password=info[K.password], money=info[K.money],
            room=info[K.room])
    users[name] = user

class PlayerServer(socketserver.BaseRequestHandler):
    def handle(self):
        self.sender = self.client_address[0]
        self.ready = None
        self.user = None
        print(f"connect {self.sender}")
        running = True
        while running:
            jsonIn = str(self.request.recv(1024).strip(), 'utf-8')
            if len(jsonIn) == 0:  running = False
            else:
                try:
                    data = json.loads(jsonIn)
                    try:
                        response = self.processMessage(data)
                    except Exception as e:
                        print(e)
                        self.sendResponse(Message(lines=["server side error"], error=1))
                    self.sendResponse(response)
                except:
                    print("WARNING: ignore malformed JSON")
                    self.sendResponse(Message(lines=["malformed JSON"], error=1))
        print(f"disconnect {self.sender}")

    def sendResponse(self, response):
        jsonOut = json.dumps(response, default=lambda o: o.__dict__)
        self.request.sendall(bytes(jsonOut, 'utf-8'))

    def roomMsg(self, lines=[]):
        room = rooms[self.user.room]
        roomName = room.name
        exitsTxt = room.exitsTxt()
        lines2 = list(lines)
        lines2.append(f"You are in {roomName} with exits to {exitsTxt}")
        return Message(lines=lines2)

    def processMessage(self, data):
        print(data)
        if self.ready is None:  # assume init message
            key, protocol = data
            print(f"{key=} {protocol=}")
            #TODO: verify key is expected and protocol match
            self.ready = True
            return Message(lines=['Welcome'], request='login')
        if self.user is None:
            userId, password = data['login']
            if userId not in users:
                return Message(lines=[f"unknown user '{userId}'"], error=1)
            else:
                self.user = users[userId]
                money = self.user.money
                lines = [f"Welcome {self.user.name}.", f"You have {money} gold."]
                return self.roomMsg(lines)
        if 'cmd' in data:
            cmd = data['cmd'].split(' ')
            if cmd[0] == 'go':
                direction = cmd[1]
                room = rooms[self.user.room]
                if direction in room.exits:
                    self.user.room = room.exits[direction]
                else:
                    return Message(lines=["You cannot go that direction."])
                return self.roomMsg()
            else:
                return Message(lines=["that didn't work"])

def startServer(host, port):
    with socketserver.TCPServer((host, port), PlayerServer) as server:
        server.serve_forever()

if __name__ == "__main__":
    host, port = "localhost", 5000
    startServer(host, port)

