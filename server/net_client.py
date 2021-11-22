#!/bin/env python3

import socket
import sys
import json
from dataclasses import dataclass, field
import enum

import net_common as nc

K = nc.K
Mode = nc.Mode

class Action(str, enum.Enum):
    quit = 'quit'
    unknown = 'unknown'

@dataclass
class Init(object):
   app: str = nc.app
   key: str = nc.key
   protocol: int = 1

@dataclass
class Login(object):
   login : list

@dataclass
class Cmd(object):
    cmd: str

@dataclass
class LocalAction(object):
    action: str

class Client(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.status = {K.room_name: '', K.money: 0, K.health: 0, K.xp: 0}

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.clientSocket:
            try:
                self.clientSocket.connect((self.host, self.port))
                self.clientSocket.sendall(nc.toJSONB(Init()))
                running = True
                while running:
                    request = nc.fromJSONB(self.clientSocket.recv(1024))
                    if request is None:
                        running = False
                        break
                    response = self.processMessage(request)
                    if isinstance(response, LocalAction):
                        running = self.processLocal(response)
                    else:
                        self.sendData(response)
            except ConnectionRefusedError as e:
                print(f"ERROR: unable to connect to {self.host}:{self.port}. Is server running?")

    def sendData(self, data):
        self.clientSocket.sendall(nc.toJSONB(data))

    def processMessage(self, request):
        if request['error'] > 0:
            error_line = request['error_line']
            print(f"ERROR: {error_line}")
        for f in [K.room_name, K.money, K.health, K.xp]:
            v = request.get('changes', {}).get(f)
            if v:  self.status[f] = v
        mode = request.get('mode')
        if mode == Mode.cmd:
            print(f"---< {self.status[K.room_name]} | health {self.status[K.health]} | xp {self.status[K.xp]} | {self.status[K.money]} gold >---")
        for m in request['lines']:  print(m)
        if mode == Mode.login:
            user = input("user? ")
            if user != '': 
                return Login(login=[user, "123"])
            else:
                return LocalAction(action=Action.quit)
        elif mode == Mode.bye:
            return LocalAction(action=Action.quit)
        elif mode == Mode.cmd:
            text = input("> ")
            return Cmd(cmd=text)
        else:
            print(request)
            return LocalAction(action=Action.unknown)

    def processLocal(self, response):
        running = True
        if isinstance(response, LocalAction):
            if response.action == Action.quit:
                running = False
            elif response.action == Action.unknown:
                print("unknown mode")
                running = False
        return running

if __name__ == "__main__":
    host = "localhost"
    client = Client(host, nc.serverPort)
    client.start()

