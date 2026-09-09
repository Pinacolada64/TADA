"""tests/commands/test_helpstaff.py — Unit tests for commands/helpstaff.py"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.base_command import Mode
from commands.helpstaff import HelpstaffCommand
from commands.new_player import CREATION_ROOM
from flags import PlayerFlags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(name: str, *, available: bool = False,
                 map_level: int = 1, map_room: int = 10) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.map_level = map_level
    p.map_room = map_room
    p.unsaved_changes = False

    def _query_flag(flag):
        if flag == PlayerFlags.HELPSTAFF_AVAILABLE:
            return available
        return False
    p.query_flag.side_effect = _query_flag
    return p


def make_client(player, *, virtual_location=None, room=None) -> MagicMock:
    """A connected client with its own ctx wired back to itself, matching
    how commands see ctx.client/ctx.player/ctx.server in production."""
    client = MagicMock()
    client.virtual_location = virtual_location
    client.room = room
    client.ctx = MagicMock()
    client.ctx.client = client
    client.ctx.player = player
    client.ctx.send = AsyncMock()
    client.ctx.prompt = AsyncMock(return_value=None)
    return client


def make_server(*clients) -> MagicMock:
    server = MagicMock()
    server.clients = {i: c for i, c in enumerate(clients)}
    server.pending_help_requests = {}
    server.game_map = None
    for c in clients:
        c.ctx.server = server
    return server


def _sent_text(ctx) -> str:
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Request path (no args)
# ---------------------------------------------------------------------------

class TestHelpstaffRequest(unittest.IsolatedAsyncioTestCase):

    async def test_no_staff_available(self):
        requester = make_client(make_player('Newbie'))
        make_server(requester)
        result = await HelpstaffCommand().execute(requester.ctx)
        self.assertTrue(result.success)
        self.assertIn('No staff are currently available', _sent_text(requester.ctx))

    async def test_request_relayed_to_available_staffer(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'),
                                 virtual_location='Creating a character')
        make_server(staffer, requester)
        requester.ctx.prompt = AsyncMock(return_value='How do I fight?')

        result = await HelpstaffCommand().execute(requester.ctx)

        self.assertTrue(result.success)
        self.assertEqual(
            requester.ctx.server.pending_help_requests.get('Newbie'),
            'How do I fight?',
        )
        sent_to_staffer = _sent_text(staffer.ctx)
        self.assertIn('Newbie needs help', sent_to_staffer)
        self.assertIn('How do I fight?', sent_to_staffer)
        self.assertIn('Creating a character', sent_to_staffer)
        self.assertIn('Sam', _sent_text(requester.ctx))

    async def test_empty_response_cancels(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.prompt = AsyncMock(return_value='   ')

        result = await HelpstaffCommand().execute(requester.ctx)

        self.assertTrue(result.success)
        self.assertNotIn('Newbie', requester.ctx.server.pending_help_requests)
        self.assertIn('Never mind', _sent_text(requester.ctx))

    async def test_disconnect_response_cancels(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.prompt = AsyncMock(return_value=None)

        result = await HelpstaffCommand().execute(requester.ctx)

        self.assertTrue(result.success)
        self.assertNotIn('Newbie', requester.ctx.server.pending_help_requests)


# ---------------------------------------------------------------------------
# Accept / decline
# ---------------------------------------------------------------------------

class TestHelpstaffAccept(unittest.IsolatedAsyncioTestCase):

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_accept_moves_staffer_not_requester(self, mock_teleport):
        staffer   = make_client(make_player('Sam', available=True), room=99)
        requester = make_client(make_player('Newbie', map_level=3), room=42)
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'Where do I go?'

        result = await HelpstaffCommand().execute(staffer.ctx, 'accept', 'Newbie')

        self.assertTrue(result.success)
        self.assertNotIn('Newbie', staffer.ctx.server.pending_help_requests)
        mock_teleport.assert_awaited_once()
        call = mock_teleport.await_args
        # Moves the ACCEPTING STAFFER's ctx, to the REQUESTER's room/level.
        self.assertIs(call.args[0], staffer.ctx)
        self.assertEqual(call.args[1], 42)
        self.assertEqual(call.kwargs.get('level'), 3)
        self.assertIn('on the way', _sent_text(requester.ctx).lower())

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_accept_for_virtual_location_routes_to_creation_room(self, mock_teleport):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'),
                                 virtual_location='Creating a character')
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'How do I fight?'

        await HelpstaffCommand().execute(staffer.ctx, 'accept', 'Newbie')

        call = mock_teleport.await_args
        self.assertEqual(call.args[1], CREATION_ROOM)
        self.assertEqual(call.kwargs.get('level'), 1)

    async def test_non_staffer_cannot_accept(self):
        staffer   = make_client(make_player('Sam', available=False))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        staffer.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, 'accept', 'Newbie')

        self.assertFalse(result.success)
        self.assertIn('not marked as available', _sent_text(staffer.ctx).lower())
        self.assertIn('Newbie', staffer.ctx.server.pending_help_requests)

    async def test_accept_unknown_request_fails(self):
        staffer = make_client(make_player('Sam', available=True))
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, 'accept', 'Nobody')
        self.assertFalse(result.success)
        self.assertIn('no longer open', _sent_text(staffer.ctx).lower())

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_second_staffer_accept_after_claim_fails(self, mock_teleport):
        sam       = make_client(make_player('Sam', available=True))
        tara      = make_client(make_player('Tara', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(sam, tara, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        first  = await HelpstaffCommand().execute(sam.ctx, 'accept', 'Newbie')
        second = await HelpstaffCommand().execute(tara.ctx, 'accept', 'Newbie')

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertIn('no longer open', _sent_text(tara.ctx).lower())
        self.assertIn('claimed by Sam', _sent_text(tara.ctx))
        mock_teleport.assert_awaited_once()

    async def test_decline_leaves_request_open(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, 'decline', 'Newbie')

        self.assertTrue(result.success)
        self.assertIn('Newbie', staffer.ctx.server.pending_help_requests)

    async def test_accept_missing_name_fails(self):
        staffer = make_client(make_player('Sam', available=True))
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, 'accept')
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# Command metadata
# ---------------------------------------------------------------------------

class TestHelpstaffMeta(unittest.TestCase):

    def test_name(self):
        self.assertEqual(HelpstaffCommand.name, 'helpstaff')

    def test_reachable_mid_login(self):
        # The motivating case: a player still mid character-creation
        # (Mode.LOGIN) can still ask for help.
        self.assertIn(Mode.LOGIN, HelpstaffCommand.modes)
        self.assertIn(Mode.GAME, HelpstaffCommand.modes)

    def test_has_help(self):
        self.assertIsNotNone(HelpstaffCommand.help)
        self.assertGreater(len(HelpstaffCommand.help.summary), 0)


if __name__ == '__main__':
    unittest.main()
