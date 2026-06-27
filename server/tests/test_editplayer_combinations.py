import asyncio
import types

import menu_system
from commands.editplayer import EditPlayerCommand
from net_common import to_jsonb
from base_classes import CombinationTypes
import simple_client
import commands.editplayer


class FakeWriter:
    def __init__(self):
        self.writes = []
    def write(self, data):
        self.writes.append(data)
    async def drain(self):
        return

class FakeReader:
    def __init__(self, line_bytes):
        self._line = line_bytes
        self._called = False
    async def readline(self):
        if not self._called:
            self._called = True
            return self._line
        return b''

class FakePlayer:
    def __init__(self):
        self.combinations = {}
        self.name = 'combo_test'

    def get_combination(self, c):
        return getattr(self.combinations.get(c), 'combination', None) if self.combinations.get(c) else None


def test_combinations_set_and_display(monkeypatch):
    player = FakePlayer()
    # prepare client with fake reader/writer; reader returns the combination value when asked
    combo_value = '04-05-09'
    raw_bytes = to_jsonb({'lines':[combo_value]}) + b"\n"
    reader = FakeReader(raw_bytes)
    writer = FakeWriter()
    client = types.SimpleNamespace()
    client.writer = writer
    client.reader = reader
    client.return_key = 'Enter'
    client.client_settings = {'screen_columns': 80}

    # responses for menu navigation: choose 'co' for combinations, then select option '1' in submenu, then exit
    responses = [ {'lines':['co']}, {'lines':['1']}, {'lines':['']} ]
    async def fake_receive(reader_arg):
        if responses:
            return responses.pop(0)
        return {'lines':['']}
    async def fake_send(writer_arg, msg):
        return

    monkeypatch.setattr(menu_system, 'receive_message', fake_receive)
    monkeypatch.setattr(menu_system, 'send_message', fake_send)
    monkeypatch.setattr(simple_client, 'send_message', fake_send)
    monkeypatch.setattr(commands.editplayer, 'send_message', fake_send)

    # run command
    context = {'client': client, 'player': player}
    cmd = EditPlayerCommand()
    res = asyncio.run(cmd.execute(context, []))

    # After execution, the player's combinations dict should contain the first CombinationTypes key
    first_combo = list(CombinationTypes)[0]
    assert first_combo in player.combinations
    val = None
    obj = player.combinations[first_combo]
    # If stored as object with .combination tuple, format to canonical string
    if hasattr(obj, 'combination'):
        comb = obj.combination
        if isinstance(comb, (list, tuple)) and len(comb) == 3:
            val = f"{int(comb[0]):02d}-{int(comb[1]):02d}-{int(comb[2]):02d}"
        else:
            val = str(comb)
    else:
        val = obj
    assert val == combo_value, f"Expected combo {combo_value} but got {val}"
