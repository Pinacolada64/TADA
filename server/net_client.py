#!/bin/env python3

import socket
import sys
import json
from dataclasses import dataclass, field

initMsg = '{"key":"TADA","protocol":1}'

@dataclass
class Login(object):
   login : list

@dataclass
class SendCmd(object):
    cmd: str

@dataclass
class LocalAction(object):
    action: str

class Client(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.clientSocket:
            self.clientSocket.connect((host, port))
            self.clientSocket.sendall(bytes(initMsg, 'utf-8'))
            running = True
            while running:
                jsonIn = str(self.clientSocket.recv(1024), 'utf-8')
                if len(jsonIn) == 0:  running = False
                data = json.loads(jsonIn)
                response = self.processMessage(data)
                if isinstance(response, LocalAction):
                    running = self.processLocal(response)
                else:
                    self.sendResponse(response)

    def sendResponse(self, response):
        jsonOut = json.dumps(response, default=lambda o: o.__dict__)
        self.clientSocket.sendall(bytes(jsonOut, 'utf-8'))

    def processMessage(self, data):
        request = data.get('request')
        if request == 'login':
            user = input("user? ")
            if user != '': 
                return Login(login=[user, "123"])
            else:
                return LocalAction(action='quit')
        elif request == 'cmd':
            if data['error'] > 0:  print("ERROR:")
            for m in data['lines']:  print(m)
            text = input("> ")
            if text == 'q':
                return LocalAction(action='quit')
            else:
                return SendCmd(cmd=text)
        else:
            print(data)
            return LocalAction(action='none')

    def processLocal(self, response):
        running = True
        if isinstance(response, LocalAction):
            if response.action == 'quit':  running = False
        return running

if __name__ == "__main__":
    host, port = "localhost", 5000
    client = Client(host, port)
    client.start()

