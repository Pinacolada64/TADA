import asyncio
from shoppe import elevator
from player import Player
from base_classes import Combination, CombinationTypes
from net_common import from_jsonb


class FakeWriter:
    def __init__(self):
        self.buf = []

    def write(self, data: bytes):
        # store raw bytes
        self.buf.append(data)

    async def drain(self):
        await asyncio.sleep(0)

    def get_messages(self):
        out = []
        for b in self.buf:
            try:
                out.append(from_jsonb(b))
            except Exception:
                out.append(b)
        return out


class FakeReader:
    async def readline(self):
        # no interactive replies by default
        await asyncio.sleep(0)
        return b''


def make_player_with_combo(tpl=(1, 2, 3)) -> Player:
    p = Player(name='TestPlayer')
    comb = Combination(CombinationTypes.ELEVATOR)
    comb.combination = tpl
    # player.combinations may be a mapping keyed by enum
    p.combinations = {CombinationTypes.ELEVATOR: comb}
    return p


def run_coro(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Running inside an asyncio loop (pytest-asyncio). Use asyncio.run for isolation.
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def test_get_combination_accepts_valid_provided():
    player = make_player_with_combo((1, 2, 3))
    writer = FakeWriter()
    reader = FakeReader()

    # Call with explicit keyword args so parameters map correctly
    res = run_coro(elevator.get_combination(reader=reader, writer=writer, player=player,
                                            is_interactive=False, provided_ans='1-2-3'))
    assert res is True
    msgs = writer.get_messages()
    # ensure no 'not the right combination' error was sent
    joined = repr(msgs)
    assert "not the right combination" not in joined


def test_get_combination_rejects_invalid_provided():
    player = make_player_with_combo((1, 2, 3))
    writer = FakeWriter()
    reader = FakeReader()

    res = run_coro(elevator.get_combination(reader=reader, writer=writer, player=player, provided_ans='9-9-9'))
    assert res is False
    msgs = writer.get_messages()
    joined = repr(msgs)
    assert "not the right combination" in joined


def test_execute_with_provided_combination_returns_success():
    player = make_player_with_combo((1, 2, 3))
    writer = FakeWriter()
    reader = FakeReader()
    context = {'player': player, 'elevator_combination': '1-2-3'}

    # elevator.execute(self, reader, writer, context, args) expects a 'self' parameter which isn't used; pass None
    result = run_coro(elevator.execute(None, reader, writer, context, []))
    # result should be a CommandResult-like object or dict; accept both
    if hasattr(result, 'success'):
        assert result.success is True
    elif isinstance(result, dict):
        assert result.get('success') is True
    else:
        # unexpected type
        assert False, f"Unexpected result type: {type(result)}"
