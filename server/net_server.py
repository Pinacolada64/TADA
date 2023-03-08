#!/bin/env python3
import logging
import sys
import os
import traceback
import threading
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
server_lock = threading.Lock()


class Error(str, enum.Enum):
    server1 = 'server1'
    server2 = 'server2'
    user_id = 'user_id'
    login1 = 'login1'
    login2 = 'login2'
    multiple = 'multiple'


@dataclass
class Message:
    lines: list
    mode: Mode = Mode.app
    changes: dict = field(default_factory=lambda: {})
    choices: dict = field(default_factory=lambda: {})
    prompt: str = ''
    error: str = ''
    error_line: str = ''


connected_users = set()


@dataclass
class LoginHistory:
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
            if save:
                self.save()
        return is_banned

    def noUser(self, user_id, save=False):
        self.fail_count += 1
        attempts = self.no_user_attempts.get(user_id, 0)
        self.no_user_attempts[user_id] = attempts + 1
        if save:
            self.save()
        return self.banned(True, save=save)

    def failPassword(self, user_id, save=False):
        self.fail_count += 1
        attempts = self.bad_password_attempts.get(user_id, 0)
        self.bad_password_attempts[user_id] = attempts + 1
        if save:
            self.save()
        return self.banned(True, save=save)

    def succeedUser(self, user_id, save=False):
        self.fail_count = 0
        if user_id in self.bad_password_attempts:
            self.bad_password_attempts.pop(user_id)
        if save:
            self.save()

    @staticmethod
    def _json_path(addr):
        util.makeDirs(nc.net_dir)
        return os.path.join(nc.net_dir, f"client-{addr}.json")

    @staticmethod
    def load(addr):
        path = LoginHistory._json_path(addr)
        if os.path.exists(path):
            with open(path) as jsonF:
                logging.info(f'LoginHistory.load: {jsonF=}')
                try:
                    lh_data = json.load(jsonF)
                except:  # FIXME: JSONDecodeError not valid?
                    logging.error(f"LoginHistory.load: \"{lh_data['name']}\" JSON error")
            return LoginHistory(**lh_data)
        else:
            return LoginHistory(addr)

    def save(self):
        with open(LoginHistory._json_path(self.addr), 'w') as jsonF:
            json.dump(self, jsonF, default=lambda o: {k: v for k, v
                                                      in o.__dict__.items() if v}, indent=4)


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class UserHandler(socketserver.BaseRequestHandler):
    def handle(self):
        addr = self.client_address[0]
        self.login_history = LoginHistory.load(addr)
        if self.login_history.banned(True, save=True):
            logging.info(f"ignoring banned {addr}")
            return
        port = self.client_address[1]
        self.sender = f"{addr}:{port}"
        self.ready = None
        self.user = None
        logging.info(f"connect (addr={self.sender})")
        running = True
        while running:
            try:
                request = self._receiveData()
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
                    traceback.print_exc(file=sys.stdout)
                    # TODO: log error with message, error code to client
                    self._sendData(Message(lines=["Terminating session."],
                                           error_line=f"server side error ({e})",
                                           error=Error.server1, mode=Mode.bye))
                if response is None:
                    running = False
                else:
                    self._sendData(response)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                # TODO: log error with message, error code to client
                self._sendData(Message(lines=["Terminating session."],
                                       error_line=f"server side error ({e})",
                                       error=Error.server2, mode=Mode.bye))
        if self.user is not None:
            user_id = self.user.id
            with server_lock:
                connected_users.remove(user_id)
        else:
            user_id = '?'
        logging.info(f"disconnect {user_id} (addr={self.sender})")

    def _receiveData(self):
        return nc.fromJSONB(self.request.recv(1024))

    def _sendData(self, data):
        self.request.sendall(nc.toJSONB(data))

    def _processInit(self, data):
        client_id = data.get('id')
        if client_id == server_id:
            client_key = data.get('key')
            if client_key == server_key:
                # TODO: handle protocol difference
                self.ready = True
                return Message(lines=self.initSuccessLines(), mode=Mode.login)
            else:
                # TODO: record history in case want to ban
                return None  # poser, ignore them
        else:
            # TODO: record history in case want to ban
            return None  # poser, ignore them

    def _processLogin(self, data):
        user_id, password, invite_code = data['login']
        if user_id == '':
            return Message(lines=['User id required.'],
                           error_line='No user id.',
                           error=Error.user_id, mode=Mode.bye)

        def errorBan():
            return Message(lines=[],
                           error_line='Too many failed attempts.',
                           error=Error.login2, mode=Mode.bye)

        def errorLoginFailed():
            return Message(lines=self.loginFailLines(),
                           error_line='Login failed.',
                           error=Error.login1, mode=Mode.login)

        user = nc.User.load(user_id)
        if user is None:
            invite = nc.Invite.load(user_id)
            if invite is None:
                logging.warning(f"no user '{user_id}'")
                # when failing don't tell that have wrong user id
                banned = self.login_history.noUser(user_id, save=True)
                if banned:
                    logging.info(f"ban {self.sender}")
                    return errorBan()
                return errorLoginFailed()
            else:
                # process new user with invite
                if invite.code != invite_code:
                    logging.warning(f'invalid invite code {invite_code}')
                    banned = self.login_history.noUser(user_id, save=True)
                    if banned:
                        logging.info(f"ban {self.sender}")
                        return errorBan()
                    return errorLoginFailed()
                else:
                    # create and save user
                    user = nc.User(user_id)
                    user.hashPassword(password)
                    user.save()
                    invite.delete()
        with server_lock:
            if user_id in connected_users:
                return Message(lines=['One connection allowed at a time.'],
                               error_line='Multiple connections.',
                               error=Error.multiple, mode=Mode.bye)
        if not user.matchPassword(password):
            logging.warning(f"bad password for '{user_id}'")
            banned = self.login_history.failPassword(user_id, save=True)
            if banned:
                logging.info(f"ban {self.sender}")
                return errorBan()
            return errorLoginFailed()
        self.user = user
        with server_lock:
            connected_users.add(user_id)
        self.login_history.succeedUser(user_id, save=True)
        return self.processLoginSuccess(user_id)

    def promptRequest(self, lines, prompt='', choices=None):
        if choices is None:
            choices = {}
        self._sendData(Message(lines=lines, prompt=prompt, choices=choices))
        return self._receiveData()

    # base implementation for when testing net_client/net_server
    # NOTE: must be overridden by actual app (see client/server)

    def initSuccessLines(self):
        """OVERRIDE in subclass
        First server message lines that user sees.  Should tell them to log in.
        """
        return ['Generic Server.', 'Please log in.']

    def loginFailLines(self):
        """OVERRIDE in subclass
        Login failure message lines back to user.
        """
        return ['please try again.']

    def processLoginSuccess(self, user_id):
        """OVERRIDE in subclass
        First method called on successful login.
        Should do any user initialization and then return Message.
        """
        return Message(lines=[f"Welcome, {user_id}."])

    def processMessage(self, data):
        """OVERRIDE in subclass
        Called on all subsequent Cmd messages from client.
        Should do any processing and return Message.
        """
        if 'text' in data:
            cmd = data['text'].split(' ')
            if cmd[0] in ['bye', 'logout']:
                return Message(lines=["Goodbye."], mode=Mode.bye)
            else:
                return Message(lines=["Unknown command."])


def start(host, port, id, key, protocol, handler_class):
    global server_id, server_key, server_protocol
    server_id = id
    server_key = key
    server_protocol = protocol
    with Server((host, port), handler_class) as server:
        logging.info(f"server running ({host}:{port})")
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        running = True
        while running:
            text = input()
            if text in ['q', 'quit', 'exit']:
                running = False
        server.shutdown()
        logging.info('server shutdown.')


if __name__ == '__main__':
    """a test of the stub net server"""
    host = 'localhost'
    start(host, nc.Test.server_port, nc.Test.id, nc.Test.key, nc.Test.protocol,
          UserHandler)
