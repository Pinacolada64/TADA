"""tests/e2e/test_monster_fight_e2e.py — live end-to-end check that a
monster attacks on sight and that the combat prompt behaves like SPUR's:
with a real Server and a real socket, walking south from room 1 into
room 13's TROLL starts a fight with the monster swinging first; INV at
the combat prompt shows the inventory without costing a turn; and a
client 'bye' mid-fight disconnects cleanly (no extra attack) with the
player saved in room 13.

The encounter rolls that could avoid the fight (surprise, spontaneous
charm, lost sight) and the ambush roll are pinned off so the run is
deterministic, and the character gets a big HP pool so the TROLL can't
end the test early.
"""
import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest

from conftest import perform_login, seed_test_account

# Starts a real Server + real sockets -- slow, excluded from local
# default runs (pyproject.toml addopts -m "not e2e"); CI overrides with
# -m "".
pytestmark = pytest.mark.e2e

_USERNAME = 'e2efighter'
_PASSWORD = 'e2epass'

# Monster narration from combat/engine.py's _narrate_monster_swing().
_MONSTER_SWING_MARKERS = ('TROLL hits you', 'TROLL misses you')


def test_monster_attacks_on_sight_inv_is_free_and_bye_disconnects(tmp_path, monkeypatch):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    seed_test_account(_USERNAME, _PASSWORD, map_room=1)

    from player import Player
    seeded = Player(name=_USERNAME, id=_USERNAME)
    seeded.hit_points = 500
    seeded.unsaved_changes = True
    assert seeded.save(force=True)

    import combat.engine as engine
    import encounters.monster as encounter
    monkeypatch.setattr(encounter, '_try_surprise', AsyncMock(return_value=False))
    monkeypatch.setattr(encounter, '_try_spontaneous_charm', AsyncMock(return_value=False))
    monkeypatch.setattr(engine, 'roll_tactical_ambush', AsyncMock(return_value=False))
    monkeypatch.setattr(engine, 'lost_sight_roll', lambda *a, **kw: False)

    # Count the player's real swings -- none should happen at all: entry
    # is the monster's swing, INV is free, and bye must not attack.
    swings = []
    real_swing = engine.CombatSession._swing

    def counting_swing(self, *a, **kw):
        swings.append(1)
        return real_swing(self, *a, **kw)
    monkeypatch.setattr(engine.CombatSession, '_swing', counting_swing)

    from net_common import Message, Mode
    from simple_server import Server

    server = Server('127.0.0.1', 0, 0)
    result = {}

    async def scenario():
        from simple_client import receive_message, send_message

        server_task = asyncio.create_task(server.start())
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        assert await perform_login(reader, writer, _USERNAME, _PASSWORD)

        async def _drain(*, quiet=0.4, max_wait=3.0):
            """Collect lines and prompts until `quiet` seconds of silence.
            ctx.prompt() text lands in "prompt", never "lines"."""
            lines, prompts = [], []
            deadline = time.time() + max_wait
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(receive_message(reader), timeout=quiet)
                except asyncio.TimeoutError:
                    break
                if not msg:
                    result['eof'] = True
                    break
                lines.extend(str(x) for x in (msg.get('lines') or []))
                if msg.get('prompt'):
                    prompts.append(str(msg['prompt']))
            return '\n'.join(lines), prompts

        await _drain()

        await send_message(writer, Message(lines=['s'], mode=Mode.app))
        result['entry_text'], result['entry_prompts'] = await _drain()

        await send_message(writer, Message(lines=['i'], mode=Mode.app))
        result['inv_text'], result['inv_prompts'] = await _drain()

        result['eof'] = False
        await send_message(writer, Message(lines=[], mode=Mode.bye))
        result['bye_text'], _ = await _drain(max_wait=5.0)

        writer.close()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))

    entry = result['entry_text']
    assert 'Combat begins!  The TROLL attacks you!' in entry
    assert any(m in entry for m in _MONSTER_SWING_MARKERS), entry
    assert entry.index('Combat begins!') < max(entry.find(m) for m in _MONSTER_SWING_MARKERS)
    assert any('Command' in p for p in result['entry_prompts'])

    # INV ran and re-prompted without the monster getting a swing.
    assert not any(m in result['inv_text'] for m in _MONSTER_SWING_MARKERS), result['inv_text']
    assert any('Command' in p for p in result['inv_prompts'])

    # bye: no parting attack, the server hung up, and the move was saved.
    assert swings == [], 'the player swung -- bye (or INV) was read as Attack'
    assert result['eof'], 'server never closed the connection after bye'
    path = Player(name='probe', id=_USERNAME)._json_path(_USERNAME)
    with open(path) as f:
        assert json.load(f).get('map_room') == 13
