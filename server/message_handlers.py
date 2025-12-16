"""Minimal message handlers module used by tests.
This implements the functions and classes referenced by tests in a simple way.
"""
from typing import Dict, Callable
import logging

class Handler:
    def __init__(self, message_type: str, func: Callable):
        self.message_type = message_type
        self.func = func

class MessageRouter:
    def __init__(self):
        self._handlers: Dict[str, Handler] = {}

    def register_command(self, message_type: str):
        def decorator(fn):
            self._handlers[message_type] = Handler(message_type, fn)
            return fn
        return decorator

    def handle_message(self, message: dict, client) -> bool:
        mtype = message.get('type') or message.get('message')
        if not mtype:
            logging.warning('No message type')
            return False
        handler = self._handlers.get(mtype)
        if not handler:
            logging.debug('No handler for: %s', mtype)
            return False
        try:
            handler.func(message, client)
            return True
        except Exception:
            logging.exception('Handler failed')
            return False

# Example handlers

def handle_notification(msg, client):
    text = msg.get('text', '')
    # print and preserve prompt if client has it
    prompt = getattr(client, 'current_prompt', '')
    print(f"[Notification] {text}")
    if prompt:
        print(prompt, end='')


def handle_page(msg, client):
    frm = msg.get('from', 'unknown')
    text = msg.get('text', '')
    print(f"Page from {frm}")
    print(text)


def handle_system(msg, client):
    print(msg.get('text', ''))


def handle_new_player(msg, client):
    # simulate asking for player name
    print(msg.get('message', ''))
    print('Character Creation')
    # send back a command using client's send_message if available
    if getattr(client, 'send_message', None):
        cmd = {'type': 'command', 'character': {'name': input('Enter name: ')} }
        client.send_message(cmd)


def handle_player_created(msg, client):
    print(msg.get('message', ''))
    room = msg.get('room')
    print(f"You are in room {room}")
    print("Type 'help' for a list of commands")
    if hasattr(client, 'current_prompt'):
        client.current_prompt = msg.get('user_id', '') + '> '


# global router instance and registration
message_router = MessageRouter()
message_router.register_command('notification')(handle_notification)
message_router.register_command('page')(handle_page)
message_router.register_command('system')(handle_system)
message_router.register_command('new_player')(handle_new_player)
message_router.register_command('player_created')(handle_player_created)

__all__ = [
    'MessageRouter', 'message_router', 'handle_notification', 'handle_page', 'handle_system',
    'handle_new_player', 'handle_player_created'
]

