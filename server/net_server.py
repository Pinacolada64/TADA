#!/bin/env python3

import os
import socketserver
import json
from dataclasses import dataclass, field
from typing import ClassVar
import enum

import net_common as nc
import util

K = nc.K
Mode = nc.Mode

server_id = None
server_key = None
server_protocol = None
net_dir = 'run/net'

@dataclass
class User(object):
    name: str
    password: str

usersData = {
    'ryan': {K.password: 'swordfish'},
    'core': {K.password: 'joshua'},
    'x': {K.password: 'x'},
}

@dataclass
class Message(object):
    lines: list
    mode: Mode = Mode.cmd
    changes: dict = field(default_factory=lambda: {})
    error: int = 0
    error_line: str = ''

users = {}
for name, info in usersData.items():
    user = User(name=name, password=info[K.password])
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
        return os.path.join(net_dir, f"client-{addr}.json")

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

class UserHandler(socketserver.BaseRequestHandler):
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
                print(e)
                print(f"WARNING: ignore malformed JSON: {e}")
                self._sendData(Message(lines=["malformed JSON"], error=1,
                        mode=Mode.bye))
        user_id = self.user.name if self.user is not None else '?'
        print(f"disconnect {user_id} (addr={self.sender})")

    def _sendData(self, data):
        self.request.sendall(nc.toJSONB(data))

    def _processInit(self, data):
        client_id = data.get('id')
        if client_id == server_id:
            client_key = data.get('key')
            if client_key == server_key:
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
            self.user = users[user_id]
            self.login_history.succeedUser(user_id, save=True)
            return self.processLoginSuccess(user_id)

    def initSucessLines(self):
        """OVERRIDE THIS in subclass"""
        return ['Generic Server.', 'Please log in.']

    def loginFailLines(self):
        """OVERRIDE THIS in subclass"""
        return ['please try again.']

    def processLoginSuccess(self, user_id):
        """OVERRIDE THIS in subclass"""
        return Message(lines=['Welcome.'])

    def processMessage(self, data):
        """OVERRIDE THIS in subclass"""
        if 'cmd' in data:
            cmd = data['cmd'].split(' ')
            if cmd[0] in ['bye', 'logout']:
                return Message(lines=["Goodbye."], mode=Mode.bye)
            else:
                return Message(lines=["Unknown command."])

def start(host, port, id, key, protocol, handler_class):
    global server_id, server_key, server_protocol
    server_id = id
    server_key = key
    server_protocol = protocol
    util.makeDirs(net_dir)
    with socketserver.TCPServer((host, port), handler_class) as server:
        print(f"server running ({host}:{port})")
        server.serve_forever()

if __name__ == "__main__":
    """a test of the stub net server"""
    host = "localhost"
    start(host, nc.Test.server_port, nc.Test.id, nc.Test.key, nc.Test.protocol,
            UserHandler)

