"""tests/e2e/test_graceful_shutdown.py

Server.graceful_shutdown() -- the SIGINT/SIGTERM handler wired up in
simple_server.py's __main__. Ryan asked whether SIGKILL saves connected
players (it can't -- see graceful_shutdown()'s own docstring for why)
and asked for an "Emergency shutdown" notice + save on the signals that
*can* be caught (SIGINT/SIGTERM).
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from simple_server import Server
from network_context import GuestPlayer


def _connected_client(player, room=1):
    ctx = MagicMock()
    ctx.player = player
    ctx.client.room = room
    ctx.client.active_editor = None
    ctx.send = AsyncMock()
    return SimpleNamespace(ctx=ctx)


def test_notifies_and_saves_each_real_player(tmp_path):
    import net_common
    run_dir = tmp_path / 'run' / 'server'
    run_dir.mkdir(parents=True)
    net_common.run_server_dir = run_dir

    from player import Player
    alice = Player(name='Alice')
    alice.id = 'alice'
    alice.unsaved_changes = True
    bob = Player(name='Bob')
    bob.id = 'bob'
    bob.unsaved_changes = True

    server = Server('127.0.0.1', 0)
    server.clients = {
        ('127.0.0.1', 1): _connected_client(alice),
        ('127.0.0.1', 2): _connected_client(bob),
    }

    asyncio.run(server.graceful_shutdown())

    for name, addr in (('Alice', ('127.0.0.1', 1)), ('Bob', ('127.0.0.1', 2))):
        ctx = server.clients[addr].ctx
        ctx.send.assert_awaited_once()
        sent_text = str(ctx.send.call_args)
        assert 'Emergency shutdown' in sent_text
        assert name in sent_text
        assert 'Bye' in sent_text

    assert (run_dir / 'player-alice.json').exists()
    assert (run_dir / 'player-bob.json').exists()
    with open(run_dir / 'player-alice.json') as f:
        assert json.load(f)['name'] == 'Alice'


def test_skips_guest_players_without_error():
    server = Server('127.0.0.1', 0)
    guest_ctx = MagicMock()
    guest_ctx.player = GuestPlayer()
    guest_ctx.send = AsyncMock()
    server.clients = {('127.0.0.1', 1): SimpleNamespace(ctx=guest_ctx)}

    asyncio.run(server.graceful_shutdown())

    guest_ctx.send.assert_not_awaited()


def test_no_connected_clients_does_not_raise():
    server = Server('127.0.0.1', 0)
    server.clients = {}
    asyncio.run(server.graceful_shutdown())   # should just return cleanly


def test_saves_in_progress_editor_buffer_and_notifies(tmp_path, monkeypatch):
    import net_common
    import text_editor
    run_dir = tmp_path / 'run' / 'server'
    run_dir.mkdir(parents=True)
    net_common.run_server_dir = run_dir

    from player import Player
    from network_context import PETSCIINetworkContext
    editing = Player(name='Editing')
    editing.id = 'editing'

    ctx = MagicMock()
    ctx.player = editing
    ctx.player.client_settings = SimpleNamespace(screen_columns=80)
    ctx.send = AsyncMock()

    editor = text_editor.Editor(ctx, initial_lines=['Some unsaved text.'])
    ctx.client.active_editor = editor

    server = Server('127.0.0.1', 0)
    server.clients = {('127.0.0.1', 1): SimpleNamespace(ctx=ctx)}

    asyncio.run(server.graceful_shutdown())

    sent_text = str(ctx.send.call_args_list)
    assert 'saved to a temporary file' in sent_text

    saved_files = list((tmp_path / 'run' / 'server' / 'editor_recovery').glob('Editing-*.json'))
    assert len(saved_files) == 1
    data = json.loads(saved_files[0].read_text())
    assert data['player'] == 'Editing'
    assert data['lines'][0]['text'] == 'Some unsaved text.'


def test_one_players_send_failure_does_not_block_others(tmp_path):
    import net_common
    run_dir = tmp_path / 'run' / 'server'
    run_dir.mkdir(parents=True)
    net_common.run_server_dir = run_dir

    from player import Player
    broken = Player(name='Broken')
    broken.id = 'broken'
    fine = Player(name='Fine')
    fine.id = 'fine'
    fine.unsaved_changes = True

    server = Server('127.0.0.1', 0)
    broken_client = _connected_client(broken)
    broken_client.ctx.send = AsyncMock(side_effect=RuntimeError('boom'))
    server.clients = {
        ('127.0.0.1', 1): broken_client,
        ('127.0.0.1', 2): _connected_client(fine),
    }

    asyncio.run(server.graceful_shutdown())

    assert (run_dir / 'player-fine.json').exists()
    # The broken player should still get saved even though notifying them failed.
    assert (run_dir / 'player-broken.json').exists()
