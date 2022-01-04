#!/bin/env python3

import socket
import sys
import os
import json
from dataclasses import dataclass, field
import enum

import net_common as nc
import util

K = nc.K
Mode = nc.Mode

run_dir = 'run/client'
net_dir = os.path.join(run_dir, 'net')


@dataclass
class Init(object):
    id: str
    key: str
    protocol: int


@dataclass
class Login(object):
    login: list

    @staticmethod
    def _json_path(user_id):
        util.makeDirs(net_dir)
        return os.path.join(net_dir, f"login-{user_id}.json")

    @staticmethod
    def load(user_id):
        path = Login._json_path(user_id)
        if os.path.exists(path):
            with open(path) as jsonF:
                lh_data = json.load(jsonF)
            return Login(**lh_data)
        else:
            return None

    def save(self):
        with open(Login._json_path(self.login[0]), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                                                      in o.__dict__.items() if v}, indent=4)


@dataclass
class Cmd(object):
    text: str


class Client(object):
    def __init__(self):
        self.user_id = None
        self.login = None

    def setUser(self, id):
        self.user_id = id

    def start(self, host, port, id, key, protocol):
        self.host = host
        self.port = port
        init_params = {'id': id, 'key': key, 'protocol': protocol}
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.clientSocket:
            try:
                self.clientSocket.connect((self.host, self.port))
                print(f"client connected ({self.host}:{self.port})")
                self.clientSocket.sendall(nc.toJSONB(Init(**init_params)))
                self.active = True
                while self.active:
                    request = nc.fromJSONB(self.clientSocket.recv(1024))
                    if request is None:
                        print('no request.')
                        self.active = False
                        break
                    response = self._processMode(request)
                    if response is not None:
                        self._sendData(response)
            except ConnectionRefusedError as e:
                print(f"ERROR: unable to connect to {self.host}:{self.port}. Is server running?")
        print('exiting.')

    def _sendData(self, data):
        self.clientSocket.sendall(nc.toJSONB(data))

    def _printCommon(self, request):
        if request['error'] != '':
            error_code = request['error']
            error_line = request['error_line']
            print(f"ERROR: {error_line} ({error_code})")
        for m in request['lines']:
            print(m)

    def _processMode(self, request):
        mode = request.get('mode')
        if mode == Mode.login:
            self._printCommon(request)
            user_id = input('user? ') if self.user_id is None else self.user_id
            login = Login.load(user_id)
            if login is None:
                print(f"Registering user '{user_id}'.")
                invite = nc.Invite.load(user_id)
                if invite is None:
                    print(f"WARN:  could not find invite code for '{user_id}'.")
                    is_registered = input('have you previously registered with server? [y/n] ')
                    if is_registered != 'y':
                        self.active = False
                        print(f"Server admin must generate invite for you.")
                        return None
                    print("Use same password used during previous registration.")
                    invite_code = ''
                else:
                    invite_code = invite.code
                password = None
                while password is None:
                    pw = input('password? ')
                    pw_again = input('   again? ')
                    if pw == pw_again:
                        password = pw
                    else:
                        print('Password did not match.  Try again.')
                login = Login(login=[user_id, password, invite_code])
            else:
                print('sending cached login info.')
            self.login = login
            return login
        elif mode == Mode.bye:
            self._printCommon(request)
            print('server said bye.')
            self.active = False
            return None
        elif mode == Mode.app:
            if self.login is not None:
                # save successful login then forget
                self.login.save()
                self.login = None
            return self.processRequest(request)
        else:
            self._printCommon(request)
            print('unexpected request.')
            self.active = False
            return None

    def processRequest(self, request):
        """OVERRIDE THIS in subclass"""
        self._printCommon(request)
        text = input('nc> ')
        return Cmd(text=text)


if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else None
    host = 'localhost'
    client = Client()
    client.setUser(user_id)
    client.start(host, nc.Test.server_port, nc.Test.id, nc.Test.key, nc.Test.protocol)
