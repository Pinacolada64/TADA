import asyncio
import types
import pytest

import menu_system
from commands.editplayer import EditPlayerCommand
from net_common import to_jsonb
from base_classes import PlayerStat
import simple_client
import commands.editplayer


class FakeWriter:
    def __init__(self):
        self.writes = []
    def write(self, data):
        # record bytes
        self.writes.append(data)
    async def drain(self):
        return

class FakeReader:
    def __init__(self, line_bytes):
        # line_bytes should be bytes returned by readline()
        self._line = line_bytes
        self._called = False
    async def readline(self):
        if not self._called:
            self._called = True
            return self._line
        return b''


class DummyHandler:
    def __init__(self, player):
        self.player = player


class FakePlayer:
    def __init__(self):
        # use dict keyed by PlayerStat enum or name
        self.stats = {}
        self.name = 'persist_test'
    def get_stat(self, s):
        # s may be enum; return value or 0
        return self.stats.get(s, self.stats.get(getattr(s,'name',None), 0))
    def set_stat(self, s, v):
        self.stats[s] = v


def test_attribute_edit_persists(monkeypatch):
    # Prepare fake player and client
    player = FakePlayer()
    # Pre-populate a stat
    some_stat = list(PlayerStat)[0]
    player.set_stat(some_stat, 5)

    # Fake reader will return JSON bytes representing the player's input '42'
    stat_value = '42'
    raw_bytes = to_jsonb({'lines':[stat_value]}) + b"\n"
    reader = FakeReader(raw_bytes)
    writer = FakeWriter()

    # client object passed into editplayer
    client = types.SimpleNamespace()
    client.writer = writer
    client.reader = reader
    client.return_key = 'Enter'
    client.client_settings = {'screen_columns': 80}

    # Monkeypatch menu_system send/receive so menu choices go to Attributes then first stat then exit
    responses = [ {'lines':['a']}, {'lines':['1']}, {'lines':['']} ]
    async def fake_receive(reader_arg):
        # ignore reader_arg, pop responses sequentially
        if responses:
            return responses.pop(0)
        return {'lines':['']}

    async def fake_send(writer_arg, msg):
        # no-op or record if needed
        return

    monkeypatch.setattr(menu_system, 'receive_message', fake_receive)
    monkeypatch.setattr(menu_system, 'send_message', fake_send)
    # Also patch simple_client.send_message and the send_message symbol imported in commands.editplayer
    monkeypatch.setattr(simple_client, 'send_message', fake_send)
    monkeypatch.setattr(commands.editplayer, 'send_message', fake_send)

    # Create a minimal client_manager in net_common with a handler referencing this player
    import net_common
    # ensure client_manager exists and has a clients mapping
    try:
        cm = getattr(net_common, 'client_manager')
    except Exception:
        cm = None
    # If there is a client_manager, inject a fake client entry to test propagation
    if cm is not None and hasattr(cm, 'clients'):
        # add an entry with handler referencing the same player
        cm.clients['testid'] = types.SimpleNamespace(handler=DummyHandler(player))

    # Build context expected by command
    context = {'client': client, 'player': player}

    # Run the command which will call _interactive_editplayer
    cmd = EditPlayerCommand()
    res = asyncio.run(cmd.execute(context, []))

    # After the interactive flow, stat should be updated
    val = player.get_stat(some_stat)
    assert val == 42, f"Expected stat to be updated to 42 but got {val}"

    # cleanup injected client
    if cm is not None and hasattr(cm, 'clients'):
        cm.clients.pop('testid', None)
