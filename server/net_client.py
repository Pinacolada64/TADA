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
   id: str
   key: str
   protocol: int

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
    def start(self, host, port, id, key, protocol):
        self.host = host
        self.port = port
        init_params = {'id': id, 'key': key, 'protocol': protocol}
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.clientSocket:
            try:
                self.clientSocket.connect((self.host, self.port))
                print(f"client connected ({self.host}:{self.port})")
                self.clientSocket.sendall(nc.toJSONB(Init(**init_params)))
                running = True
                while running:
                    request = nc.fromJSONB(self.clientSocket.recv(1024))
                    if request is None:
                        running = False
                        break
                    response = self._processMode(request)
                    if isinstance(response, LocalAction):
                        running = self.processLocal(response)
                    else:
                        self._sendData(response)
            except ConnectionRefusedError as e:
                print(f"ERROR: unable to connect to {self.host}:{self.port}. Is server running?")

    def _sendData(self, data):
        self.clientSocket.sendall(nc.toJSONB(data))

    def _printCommon(self, request):
        if request['error'] > 0:
            error_code = request['error']
            error_line = request['error_line']
            print(f"ERROR: {error_code} - {error_line}")
        for m in request['lines']:  print(m)

    def _processMode(self, request):
        mode = request.get('mode')
        if mode == Mode.login:
            self._printCommon(request)
            user = input("user? ")
            password = input("password? ")
            return Login(login=[user, password])
        elif mode == Mode.bye:
            self._printCommon(request)
            return LocalAction(action=Action.quit)
        elif mode == Mode.cmd:
            return self.nextCmd(request)
        else:
            print(request)
            self._printCommon(request)
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

    def nextCmd(self, request):
        """OVERRIDE THIS in subclass"""
        self._printCommon(request)
        text = input("nc> ")
        return Cmd(cmd=text)

if __name__ == "__main__":
    host = "localhost"
    client = Client()
    client.start(host, nc.Test.server_port, nc.Test.id, nc.Test.key, nc.Test.protocol)

