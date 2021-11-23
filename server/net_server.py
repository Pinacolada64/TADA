#!/bin/env python3

import os
import socketserver
import json
from dataclasses import dataclass, field
from typing import ClassVar
import enum

import net_common as nc

K = nc.K
Mode = nc.Mode

run_dir = 'run'

# fake data 
roomsData = {
    'ul': {K.name: 'Upper Left',  K.exits: {'s': 'll', 'e': 'ur'}},
    'ur': {K.name: 'Upper Right', K.exits: {'s': 'lr', 'w': 'ul'}},
    'll': {K.name: 'Lower Left',  K.exits: {'n': 'ul', 'e': 'lr'}},
    'lr': {K.name: 'Lower Right', K.exits: {'n': 'ur', 'w': 'll'}},
}
usersData = {
    'ryan': {K.password: 'swordfish', K.money: 1000, K.room: 'ul',
            K.health: 100, K.xp: 0},
    'core': {K.password: 'joshua', K.money: 10, K.room: 'ul',
            K.health: 99, K.xp: 0},
    'x': {K.password: 'x', K.money: 1, K.room: 'ul',
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
class User(object):
    name: str
    password: str
    money: int
    room: str
    health: int
    xp: int

@dataclass
class Message(object):
    lines: list
    mode: Mode = Mode.cmd
    changes: dict = field(default_factory=lambda: {})
    error: int = 0
    error_line: str = ''

rooms = {}
for id, info in roomsData.items():
    room = Room(name=info[K.name], exits=info[K.exits])
    rooms[id] = room
users = {}
for name, info in usersData.items():
    user = User(name=name, password=info[K.password], money=info[K.money],
            room=info[K.room], health=info[K.health], xp=info[K.xp])
    users[name] = user

@dataclass
class LoginHistory(object):
    addr: str
    no_user_attempts: dict = field(default_factory=lambda: {})
    bad_password_attempts: dict = field(default_factory=lambda: {})
    fail_count: int = 0
    ban_count: int = 0

    _fail_limit: ClassVar[int] = 10

    def banned(self, update, save=False):
        is_banned = self.fail_count >= LoginHistory._fail_limit
        if is_banned and update:
            self.ban_count += 1
            if save:  self.save()
        return is_banned

    def noUser(self, user_id, save=False):
        self.fail_count += 1
        attempts = self.no_user_attempts.get(user_id, 0)
        self.no_user_attempts[user_id] = attempts + 1
        if save:  self.save()
        return self.banned(True, save=save)

    def failPassword(self, user_id, save=False):
        self.fail_count += 1
        attempts = self.bad_password_attempts.get(user_id, 0)
        self.bad_password_attempts[user_id] = attempts + 1
        if save:  self.save()
        return self.banned(True, save=save)

    def succeedUser(self, user_id, save=False):
        self.fail_count = 0
        if user_id in self.bad_password_attempts:
            self.bad_password_attempts.pop(user_id)
        if save:  self.save()

    @staticmethod
    def _json_path(addr):
        return os.path.join(run_dir, f"client-{addr}.json")

    @staticmethod
    def load(addr):
        path = LoginHistory._json_path(addr)
        if os.path.exists(path):
            with open(path) as jsonF:
                lh_data = json.load(jsonF)
            return LoginHistory(**lh_data)
        else:
            return LoginHistory(addr)

    def save(self):
        with open(LoginHistory._json_path(self.addr), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                    in o.__dict__.items() if v}, indent=4)
            
class PlayerServer(socketserver.BaseRequestHandler):
    def handle(self):
        addr = self.client_address[0]
        self.login_history = LoginHistory.load(addr)
        if self.login_history.banned(True, save=True):
            print(f"ignoring banned {addr}")
            return
        port = self.client_address[1]
        self.sender = f"{addr}:{port}"
        self.ready = None
        self.user = None
        print(f"connect (addr={self.sender})")
        running = True
        while running:
            try:
                request = nc.fromJSONB(self.request.recv(1024))
                if request is None:
                    running = False
                    break
                try:
                    if self.ready is None:  # assume init message
                        response = self._processInit(request)
                    elif self.user is None:
                        response = self._processLogin(request)
                    else:
                        response = self.processMessage(request)
                except Exception as e:
                    print(f"{e=}")
                    self._sendData(Message(lines=["server side error"],
                            error=1, mode=Mode.bye))
                if response is None:  running = False
                else:  self._sendData(response)
            except Exception as e:
                print(f"WARNING: ignore malformed JSON: {e}")
                self._sendData(Message(lines=["malformed JSON"], error=1,
                        mode=Mode.bye))
        user_id = self.user.name if self.user is not None else '?'
        print(f"disconnect {user_id} (addr={self.sender})")

    def _sendData(self, data):
        self.request.sendall(nc.toJSONB(data))

    def _processInit(self, data):
        app = data.get('app')
        if app == nc.app:
            key = data.get('key')
            if key == nc.key:
                #TODO: handle protocol difference
                self.ready = True
                return Message(lines=self.initSucessLines(), mode=Mode.login)
            else:
                #TODO: record history in case want to ban
                return None # poser, ignore them
        else:
            #TODO: record history in case want to ban
            return None # poser, ignore them

    def _processLogin(self, data):
        user_id, password = data['login']
        if user_id not in users:
            print(f"WARN: no user '{user_id}'")
            # when failing don't tell that have wrong user id
            banned = self.login_history.noUser(user_id, save=True)
            if banned:
                print(f"ban {self.sender}")
                return Message(error_line='Too many failed attempts.',
                        error=1, lines=[], mode=Mode.bye)
            return Message(error_line='Login failed.', error=1,
                    lines=self.loginFailLines, mode=Mode.login)
        else:
            if password != users[user_id].password:
                print(f"WARN: badd password '{user_id}' '{password}'")
                banned = self.login_history.failPassword(user_id, save=True)
                if banned:
                    print(f"ban {self.sender}")
                    return Message(error_line='Too many failed attempts.',
                            error=1, lines=[], mode=Mode.bye)
                return Message(error_line='Login failed.', error=1,
                        lines=self.loginFailLines, mode=Mode.login)
            self.login_history.succeedUser(user_id, save=True)
            return self.processLoginSuccess(user_id)

    ### TADA specific methods

    def initSucessLines(self):
        return ['TADA!', 'Please log in.']

    def loginFailLines(self):
        return ['please try again.']

    def roomMsg(self, lines=[], changes={}):
        room = rooms[self.user.room]
        room_name = room.name
        exitsTxt = room.exitsTxt()
        lines2 = list(lines)
        lines2.append(f"You are in {room_name} with exits to {exitsTxt}")
        return Message(lines=lines2, changes=changes)

    def processLoginSuccess(self, user_id):
        self.user = users[user_id]
        print(f"login {self.user.name} (addr={self.sender})")
        money = self.user.money
        lines = [f"Welcome {self.user.name}.", f"You have {money} gold."]
        changes = {K.room_name: rooms[self.user.room].name,
                K.money: money, K.health: self.user.health,
                K.xp: self.user.xp}
        return self.roomMsg(lines, changes)

    def processMessage(self, data):
        if 'cmd' in data:
            cmd = data['cmd'].split(' ')
            print(f"{cmd=}")
            #TODO: handle commands with parser etc.
            if cmd[0] in compass_txts:  cmd.insert(0, 'go')
            if cmd[0] in ['g', 'go']:
                direction = cmd[1]
                room = rooms[self.user.room]
                if direction in room.exits:
                    self.user.room = room.exits[direction]
                    room_name = rooms[self.user.room].name
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

def startServer(host, port):
    nc.makeDirs(run_dir)
    with socketserver.TCPServer((host, port), PlayerServer) as server:
        print(f"server running ({host}:{port})")
        server.serve_forever()

if __name__ == "__main__":
    host = "localhost"
    startServer(host, nc.serverPort)

