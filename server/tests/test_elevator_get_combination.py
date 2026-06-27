import asyncio
import types
from base_classes import Combination, CombinationTypes
from shoppe import elevator
from net_common import to_jsonb
import simple_client
import commands.editplayer


class DummyWriter:
    def __init__(self):
        self.writes = []
    def write(self, data):
        self.writes.append(data)
    async def drain(self):
        return

class DummyReader:
    async def readline(self):
        return b''


async def _run_noninteractive_ok():
    # create fake player and attach combination
    class P:
        pass
    player = P()
    player.combinations = {}
    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = (4,5,9)
    player.combinations[CombinationTypes.ELEVATOR] = combo

    # call get_combination with matching provided_ans
    writer = DummyWriter()
    reader = DummyReader()
    ok = await elevator.get_combination(reader, writer, player, is_interactive=False, provided_ans='4 5 9')
    return ok

async def _run_noninteractive_bad():
    class P: pass
    player = P()
    player.combinations = {}
    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = (4,5,9)
    player.combinations[CombinationTypes.ELEVATOR] = combo
    writer = DummyWriter()
    reader = DummyReader()
    ok = await elevator.get_combination(reader, writer, player, is_interactive=False, provided_ans='1-2-3')
    return ok


def test_get_combination_noninteractive():
    # patch send_message to avoid errors
    async def fake_send(w, msg):
        return
    # monkeypatch in modules
    simple_client.send_message = fake_send

    ok = asyncio.run(_run_noninteractive_ok())
    assert ok is True
    bad = asyncio.run(_run_noninteractive_bad())
    assert bad is False


