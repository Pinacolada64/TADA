"""tests/e2e/test_follow_me_e2e.py — live end-to-end check of FOLLOW ME
(guild_follow.py): with a real Server and two real socket connections,
a Claw leader recruits one online Claw guildmate and one logged-off Claw
guildmate parked in the same room, walks east, and the online follower
arrives with them; the leader then disconnects, which drops the carried
(offline) follower off in the new room -- SPUR's LOGON.STAY.
"""
import asyncio
import json
import time
from pathlib import Path

import pytest

from conftest import perform_login, seed_test_account

# Starts a real Server + real sockets -- slow, excluded from local
# default runs (pyproject.toml addopts -m "not e2e"); CI overrides with
# -m "".
pytestmark = pytest.mark.e2e

_LEADER = 'e2elead'
_MATE = 'e2emate'
_SLEEPER = 'e2esleep'
_PASSWORD = 'e2epass'
# Level 1 rooms 2 -> 3 (east): both plain neutral LABYRINTH rooms, no
# monster -- room 1 is free-fire, where STAY's strange force would block
# the drop-off.
_START_ROOM = 2
_DEST_ROOM = 3


def _make_claw_follower(run_dir: Path, username: str) -> None:
    path = run_dir / f'player-{username}.json'
    data = json.loads(path.read_text())
    data['guild'] = 'Mark of the Claw'
    data['flags']['Guild Follow Mode'] = {'name': 'Guild Follow Mode', 'status': True}
    path.write_text(json.dumps(data))


def test_follow_me_live_and_carried(tmp_path):
    import net_common
    run_dir = tmp_path / 'run' / 'server'
    net_common.run_server_dir = str(run_dir)
    for name in (_LEADER, _MATE, _SLEEPER):
        seed_test_account(name, _PASSWORD, map_room=_START_ROOM)
        _make_claw_follower(run_dir, name)

    from simple_server import Server
    server = Server('127.0.0.1', 0, 0)
    result = {}

    async def run_scenario():
        from net_common import Message, Mode
        from simple_client import receive_message, send_message

        server_task = asyncio.create_task(server.start())
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]

        reader_l, writer_l = await asyncio.open_connection('127.0.0.1', port)
        assert await perform_login(reader_l, writer_l, _LEADER, _PASSWORD)
        reader_m, writer_m = await asyncio.open_connection('127.0.0.1', port)
        assert await perform_login(reader_m, writer_m, _MATE, _PASSWORD)

        async def _drain(reader, *, quiet=0.4, max_wait=3.0):
            """Collect lines and prompts until `quiet` seconds of silence.
            ctx.prompt() text lands in the message's "prompt" field, never
            "lines" (see CLAUDE.md's Bot scripts section)."""
            lines, prompts = [], []
            deadline = time.time() + max_wait
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(receive_message(reader), timeout=quiet)
                except asyncio.TimeoutError:
                    break
                if not msg:
                    break
                lines.extend(str(x) for x in (msg.get('lines') or []))
                if msg.get('prompt'):
                    prompts.append(str(msg['prompt']))
            return '\n'.join(lines), prompts

        async def _send(writer, text):
            await send_message(writer, Message(lines=[text], mode=Mode.app))

        await _drain(reader_l)
        await _drain(reader_m)

        # FOLLOW ME: one "Take <name>? [Y]/n" prompt per same-guild
        # candidate -- the online mate first, then the logged-off sleeper.
        await _send(writer_l, 'follow me')
        text, prompts = await _drain(reader_l)
        answered = 0
        while any('Take' in p for p in prompts) and answered < 4:
            await _send(writer_l, 'y')
            answered += 1
            more, prompts = await _drain(reader_l)
            text += '\n' + more
        result['recruit_text'] = text
        result['mate_invite'], _ = await _drain(reader_m)

        await _send(writer_l, 'e')
        result['leader_move'], _ = await _drain(reader_l)
        result['mate_move'], _ = await _drain(reader_m)

        def _live(name):
            for client in server.clients.values():
                player = getattr(getattr(client, 'ctx', None), 'player', None)
                if player is not None and player.name == name:
                    return client, player
            return None, None

        mate_client, mate_player = _live(_MATE)
        result['mate_room'] = mate_client.room
        result['mate_following'] = mate_player.guild_following

        # Abrupt disconnect -- the connection's finally block runs the
        # LOGON.STAY drop-off and releases the live follower.
        try:
            writer_l.transport.abort()
        except Exception:
            writer_l.close()
        released = ''
        deadline = time.time() + 5
        while time.time() < deadline:
            chunk, _ = await _drain(reader_m, quiet=0.3, max_wait=0.6)
            released += chunk
            if 'left the realm' in released:
                break
        result['mate_released'] = released
        result['mate_following_after'] = mate_player.guild_following

        writer_m.close()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(asyncio.wait_for(run_scenario(), timeout=30))

    assert 'e2emate agrees to follow you..' in result['recruit_text'], result['recruit_text']
    assert 'e2esleep agrees to follow you..' in result['recruit_text'], result['recruit_text']
    assert 'leads the way' in result['mate_invite']
    assert 'You follow e2elead east.' in result['mate_move'], result['mate_move']
    assert result['mate_room'] == _DEST_ROOM
    assert result['mate_following'] == _LEADER
    assert 'left the realm' in result['mate_released']
    assert result['mate_following_after'] is None

    sleeper = json.loads((run_dir / f'player-{_SLEEPER}.json').read_text())
    assert sleeper['map_room'] == _DEST_ROOM
    assert sleeper['followed_leader_name'] == 'e2elead'
