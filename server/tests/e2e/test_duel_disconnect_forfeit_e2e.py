"""tests/e2e/test_duel_disconnect_forfeit_e2e.py — live end-to-end check
of combat/duel.py's DuelSession.forfeit(): with a real Server, two real
socket connections, and an actual live SPORT DUEL in progress, abruptly
closing one duelist's connection should hand the other an automatic win
(SPUR.DUEL.S's "dropped" label) instead of leaving them stuck waiting on
a tactic that will never arrive.
"""
import asyncio
import time

import pytest

from conftest import perform_login, seed_test_account

# Starts a real Server + real sockets -- slow, excluded from local
# default runs (pyproject.toml addopts -m "not e2e"); CI overrides with
# -m "" so both ci.yml's full suite and e2e-tests.yml's dedicated run
# still cover it.
pytestmark = pytest.mark.e2e

_USERNAME_A = 'e2eduela'
_USERNAME_B = 'e2eduelb'
_PASSWORD = 'e2epass'


def test_disconnecting_mid_duel_hands_opponent_an_automatic_win(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    # Both accounts seed to the same default room (map_room=1, map_level=1),
    # so they land in the same room on login without any movement commands.
    seed_test_account(_USERNAME_A, _PASSWORD)
    seed_test_account(_USERNAME_B, _PASSWORD)

    from simple_server import Server
    from items import Weapon

    server = Server('127.0.0.1', 0, 0)

    result = {}

    async def run_scenario():
        server_task = asyncio.create_task(server.start())
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]

        reader_a, writer_a = await asyncio.open_connection('127.0.0.1', port)
        assert await perform_login(reader_a, writer_a, _USERNAME_A, _PASSWORD)
        reader_b, writer_b = await asyncio.open_connection('127.0.0.1', port)
        assert await perform_login(reader_b, writer_b, _USERNAME_B, _PASSWORD)

        # Grab the live Player objects straight out of the running server --
        # readied_weapon is session-only (never persisted, see combat/duel.py's
        # module docstring), so it has to be set post-login on the real
        # in-memory objects rather than seeded into the JSON save file.
        def _find_player(name):
            for client in server.clients.values():
                ctx = getattr(client, 'ctx', None)
                player = getattr(ctx, 'player', None)
                if player is not None and getattr(player, 'name', None) == name:
                    return player
            return None

        player_a = _find_player('e2eduela')
        player_b = _find_player('e2eduelb')
        assert player_a is not None and player_b is not None
        sword = lambda: Weapon(id_number=1, name='LONG SWORD', stability=50,
                                to_hit=60, weapon_class='bash/slash')
        player_a.readied_weapon = sword()
        player_b.readied_weapon = sword()

        async def _drain(reader, *, quiet=0.4, max_wait=3.0):
            """Collect every message until `quiet` seconds pass with
            nothing new arriving (not just the first prompt-bearing
            message) -- the server can split one command's response
            across several pushed messages, and unrelated broadcasts
            (room-entry announcements, etc.) can interleave with them."""
            from simple_client import receive_message
            lines = []
            overall_deadline = time.time() + max_wait
            while time.time() < overall_deadline:
                try:
                    msg = await asyncio.wait_for(receive_message(reader), timeout=quiet)
                except asyncio.TimeoutError:
                    break
                if not msg:
                    break
                lines.extend(msg.get('lines') or [])
            return '\n'.join(str(x) for x in lines)

        # perform_login() returns as soon as it sees the 'Welcome, <name>!'
        # line -- the room-entry push that follows login is still sitting
        # unread in the socket buffer at this point. Flush it now so the
        # next _drain() call (after the actual 'duel' command below) reads
        # that command's response instead of this leftover backlog.
        await _drain(reader_a)
        await _drain(reader_b)

        async def _send(writer, text):
            from net_common import Message, Mode
            from simple_client import send_message
            await send_message(writer, Message(lines=[text], mode=Mode.app))

        await _send(writer_a, f'duel {player_b.name}')
        await _drain(reader_a)

        await _send(writer_b, 'duel accept')
        await _drain(reader_b)
        await _drain(reader_a)  # unprompted push announcing the duel began

        assert player_a.active_duel is not None
        assert player_b.active_duel is not None
        assert player_a.active_duel is player_b.active_duel

        # Abruptly close B's connection mid-duel -- no 'bye', no graceful quit.
        try:
            writer_b.transport.abort()
        except Exception:
            writer_b.close()

        # Give the server's connection-cleanup finally block a moment to
        # detect the closure and run DuelSession.forfeit().
        forfeit_text = ''
        deadline = time.time() + 5
        while time.time() < deadline:
            forfeit_text += await _drain(reader_a, quiet=0.3, max_wait=0.6)
            if 'forfeit' in forfeit_text.lower():
                break

        result['forfeit_text'] = forfeit_text
        result['a_active_duel_cleared'] = player_a.active_duel is None
        result['b_active_duel_cleared'] = player_b.active_duel is None
        result['a_duel_wins'] = getattr(player_a, 'duel_wins', 0)
        result['b_duel_losses'] = getattr(player_b, 'duel_losses', 0)
        result['b_hit_points'] = getattr(player_b, 'hit_points', None)

        writer_a.close()
        try:
            await writer_a.wait_closed()
        except Exception:
            pass

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(asyncio.wait_for(run_scenario(), timeout=20))

    assert 'forfeit' in result['forfeit_text'].lower(), (
        f'Opponent never got a forfeit notice; last output: {result["forfeit_text"]!r}'
    )
    assert result['a_active_duel_cleared']
    assert result['b_active_duel_cleared']
    assert result['a_duel_wins'] == 1
    assert result['b_duel_losses'] == 1
    assert result['b_hit_points'] == 15  # _MIN_HP_AFTER_LOSS, same as a fair loss
