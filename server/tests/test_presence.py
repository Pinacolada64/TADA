"""tests/test_presence.py — Unit tests for presence.py"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

import presence


def run(coro):
    return asyncio.run(coro)


def make_client(name: str, area: str | None = None) -> MagicMock:
    """Return a minimal server-side client mock."""
    client = MagicMock()
    client.virtual_location = area
    client.ctx = MagicMock()
    client.ctx.send = AsyncMock()
    client.ctx.player = MagicMock()
    client.ctx.player.name = name
    return client


def make_server(*clients) -> MagicMock:
    """Return a server mock whose clients dict contains the given clients."""
    server = MagicMock()
    server.clients = {i: c for i, c in enumerate(clients)}
    return server


def make_ctx(client, server) -> MagicMock:
    ctx = MagicMock()
    ctx.client = client
    ctx.server = server
    ctx.player = client.ctx.player
    ctx.send = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# occupants()
# ---------------------------------------------------------------------------

class TestOccupants(unittest.TestCase):

    def test_returns_clients_in_area(self):
        a = make_client('Alice', 'elevator')
        b = make_client('Bob',   'elevator')
        c = make_client('Carol', 'shoppe')
        server = make_server(a, b, c)

        result = presence.occupants(server, 'elevator')
        self.assertIn(a, result)
        self.assertIn(b, result)
        self.assertNotIn(c, result)

    def test_empty_when_no_one_in_area(self):
        a = make_client('Alice', 'shoppe')
        server = make_server(a)
        self.assertEqual(presence.occupants(server, 'elevator'), [])

    def test_clients_without_virtual_location_excluded(self):
        a = make_client('Alice')   # virtual_location is None
        server = make_server(a)
        self.assertEqual(presence.occupants(server, 'elevator'), [])

    def test_empty_server(self):
        server = make_server()
        self.assertEqual(presence.occupants(server, 'elevator'), [])


# ---------------------------------------------------------------------------
# broadcast_area()
# ---------------------------------------------------------------------------

class TestBroadcastArea(unittest.TestCase):

    def test_sends_to_other_occupants(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob',   'elevator')
        server = make_server(alice, bob)
        ctx = make_ctx(alice, server)

        run(presence.broadcast_area(ctx, 'elevator', 'Hello!'))

        bob.ctx.send.assert_awaited_once_with('Hello!')

    def test_does_not_send_to_sender(self):
        alice = make_client('Alice', 'elevator')
        server = make_server(alice)
        ctx = make_ctx(alice, server)

        run(presence.broadcast_area(ctx, 'elevator', 'Hello!'))

        alice.ctx.send.assert_not_awaited()

    def test_does_not_send_to_different_area(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob',   'shoppe')
        server = make_server(alice, bob)
        ctx = make_ctx(alice, server)

        run(presence.broadcast_area(ctx, 'elevator', 'Hello!'))

        bob.ctx.send.assert_not_awaited()

    def test_send_failure_does_not_raise(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob',   'elevator')
        bob.ctx.send = AsyncMock(side_effect=Exception('connection lost'))
        server = make_server(alice, bob)
        ctx = make_ctx(alice, server)

        # Should not propagate the exception
        run(presence.broadcast_area(ctx, 'elevator', 'Hello!'))

    def test_no_ctx_on_peer_is_skipped(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob',   'elevator')
        bob.ctx = None   # no context attached yet
        server = make_server(alice, bob)
        ctx = make_ctx(alice, server)

        run(presence.broadcast_area(ctx, 'elevator', 'Hello!'))
        # just assert no crash


# ---------------------------------------------------------------------------
# enter_area()
# ---------------------------------------------------------------------------

class TestEnterArea(unittest.TestCase):

    def test_sets_virtual_location(self):
        alice = make_client('Alice')
        server = make_server(alice)
        ctx = make_ctx(alice, server)

        run(presence.enter_area(ctx, 'elevator'))

        self.assertEqual(alice.virtual_location, 'elevator')

    def test_notifies_existing_occupants(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob')
        server = make_server(alice, bob)
        ctx = make_ctx(bob, server)

        run(presence.enter_area(ctx, 'elevator'))

        alice.ctx.send.assert_awaited_once_with('Bob steps into the elevator.')

    def test_does_not_notify_self(self):
        alice = make_client('Alice')
        server = make_server(alice)
        ctx = make_ctx(alice, server)

        run(presence.enter_area(ctx, 'elevator'))

        alice.ctx.send.assert_not_awaited()

    def test_enter_broadcasts_player_name(self):
        watcher = make_client('Watcher', 'shoppe')
        joiner  = make_client('Rulan')
        server  = make_server(watcher, joiner)
        ctx = make_ctx(joiner, server)

        run(presence.enter_area(ctx, 'shoppe'))

        watcher.ctx.send.assert_awaited_once_with('Rulan steps into the shoppe.')


# ---------------------------------------------------------------------------
# leave_area()
# ---------------------------------------------------------------------------

class TestLeaveArea(unittest.TestCase):

    def test_clears_virtual_location(self):
        alice = make_client('Alice', 'elevator')
        server = make_server(alice)
        ctx = make_ctx(alice, server)

        run(presence.leave_area(ctx, 'elevator'))

        self.assertIsNone(alice.virtual_location)

    def test_notifies_remaining_occupants(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob',   'elevator')
        server = make_server(alice, bob)
        ctx = make_ctx(alice, server)

        run(presence.leave_area(ctx, 'elevator'))

        # Alice's virtual_location is now None, so only Bob (still in elevator) gets the message
        bob.ctx.send.assert_awaited_once_with('Alice steps out of the elevator.')

    def test_does_not_notify_self(self):
        alice = make_client('Alice', 'elevator')
        server = make_server(alice)
        ctx = make_ctx(alice, server)

        run(presence.leave_area(ctx, 'elevator'))

        alice.ctx.send.assert_not_awaited()

    def test_does_not_notify_other_areas(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob',   'shoppe')
        server = make_server(alice, bob)
        ctx = make_ctx(alice, server)

        run(presence.leave_area(ctx, 'elevator'))

        bob.ctx.send.assert_not_awaited()


# ---------------------------------------------------------------------------
# enter + leave round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip(unittest.TestCase):

    def test_enter_then_leave_clears_location(self):
        alice = make_client('Alice')
        server = make_server(alice)
        ctx = make_ctx(alice, server)

        run(presence.enter_area(ctx, 'elevator'))
        self.assertEqual(alice.virtual_location, 'elevator')

        run(presence.leave_area(ctx, 'elevator'))
        self.assertIsNone(alice.virtual_location)

    def test_three_players_see_each_others_movements(self):
        alice = make_client('Alice', 'elevator')
        bob   = make_client('Bob',   'elevator')
        carol = make_client('Carol')
        server = make_server(alice, bob, carol)
        ctx_carol = make_ctx(carol, server)

        run(presence.enter_area(ctx_carol, 'elevator'))

        # Alice and Bob both see Carol arrive
        alice.ctx.send.assert_awaited_once_with('Carol steps into the elevator.')
        bob.ctx.send.assert_awaited_once_with('Carol steps into the elevator.')

        # Carol leaves
        alice.ctx.send.reset_mock()
        bob.ctx.send.reset_mock()
        run(presence.leave_area(ctx_carol, 'elevator'))

        alice.ctx.send.assert_awaited_once_with('Carol steps out of the elevator.')
        bob.ctx.send.assert_awaited_once_with('Carol steps out of the elevator.')
        carol.ctx.send.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
