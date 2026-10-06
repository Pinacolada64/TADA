"""tests/commands/test_helpstaff.py — Unit tests for commands/helpstaff.py"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.base_command import CommandResult, Mode
from commands.helpstaff import HelpstaffCommand, tagged_name
from flags import PlayerFlags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(name: str, *, available: bool = False, admin: bool = False,
                 map_level: int = 1, map_room: int = 10) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.map_level = map_level
    p.map_room = map_room
    p.unsaved_changes = False

    flags = {PlayerFlags.HELPSTAFF: available, PlayerFlags.ADMIN: admin}
    p.query_flag.side_effect = lambda flag: flags.get(flag, False)
    p.set_flag.side_effect   = lambda flag: flags.__setitem__(flag, True)
    p.clear_flag.side_effect = lambda flag: flags.__setitem__(flag, False)
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
                                 virtual_location='Reading mail')
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
        self.assertIn('Reading mail', sent_to_staffer)
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

        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        self.assertTrue(result.success)
        self.assertNotIn('Newbie', staffer.ctx.server.pending_help_requests)
        mock_teleport.assert_awaited_once()
        call = mock_teleport.await_args
        # Moves the ACCEPTING STAFFER's ctx, to the REQUESTER's room/level.
        self.assertIs(call.args[0], staffer.ctx)
        self.assertEqual(call.args[1], 42)
        self.assertEqual(call.kwargs.get('level'), 3)
        self.assertIn('arrived to help', _sent_text(requester.ctx).lower())

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_accept_for_virtual_location_routes_to_real_room(self, mock_teleport):
        # Inside a virtual area (bar, mail, ...) the requester still has a
        # real room under them; the staffer lands there.
        staffer   = make_client(make_player('Sam', available=True), room=99)
        requester = make_client(make_player('Newbie', map_level=2),
                                 virtual_location='Reading mail', room=17)
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'How do I fight?'

        await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        call = mock_teleport.await_args
        self.assertEqual(call.args[1], 17)
        self.assertEqual(call.kwargs.get('level'), 2)

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_blocked_teleport_reopens_request(self, mock_teleport):
        mock_teleport.return_value = CommandResult.fail('The teleport is blocked!',
                                                        error='teleport_blocked')
        staffer   = make_client(make_player('Sam', available=True), room=99)
        requester = make_client(make_player('Newbie'), room=42)
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        self.assertFalse(result.success)
        self.assertEqual(staffer.ctx.server.pending_help_requests.get('Newbie'), 'help')
        self.assertNotIn('arrived', _sent_text(requester.ctx).lower())
        self.assertIn('still open', _sent_text(staffer.ctx))

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_accept_same_room_skips_teleport(self, mock_teleport):
        staffer   = make_client(make_player('Sam', available=True), room=42)
        requester = make_client(make_player('Newbie'), room=42)
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        self.assertTrue(result.success)
        mock_teleport.assert_not_awaited()
        self.assertIn('here to help', _sent_text(requester.ctx))

    async def test_cannot_accept_own_request(self):
        sam = make_client(make_player('Sam', available=True))
        make_server(sam)
        sam.ctx.server.pending_help_requests['Sam'] = 'help'
        result = await HelpstaffCommand().execute(sam.ctx, '#accept', 'sam')
        self.assertFalse(result.success)
        self.assertIn('Sam', sam.ctx.server.pending_help_requests)

    async def test_non_staffer_cannot_accept(self):
        staffer   = make_client(make_player('Sam', available=False))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        staffer.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        self.assertFalse(result.success)
        self.assertIn('not marked as available', _sent_text(staffer.ctx).lower())
        self.assertIn('Newbie', staffer.ctx.server.pending_help_requests)

    async def test_accept_unknown_request_fails(self):
        staffer = make_client(make_player('Sam', available=True))
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Nobody')
        self.assertFalse(result.success)
        self.assertIn('no longer open', _sent_text(staffer.ctx).lower())

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_second_staffer_accept_after_claim_fails(self, mock_teleport):
        sam       = make_client(make_player('Sam', available=True), room=1)
        tara      = make_client(make_player('Tara', available=True), room=2)
        requester = make_client(make_player('Newbie'), room=42)
        make_server(sam, tara, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        first  = await HelpstaffCommand().execute(sam.ctx, '#accept', 'Newbie')
        second = await HelpstaffCommand().execute(tara.ctx, '#accept', 'Newbie')

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertIn('no longer open', _sent_text(tara.ctx).lower())
        self.assertIn('claimed by Sam', _sent_text(tara.ctx))
        mock_teleport.assert_awaited_once()

    async def test_decline_unknown_request_fails(self):
        staffer = make_client(make_player('Sam', available=True))
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, '#decline', 'Nobody')
        self.assertFalse(result.success)

    async def test_decline_leaves_request_open(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, '#decline', 'Newbie')

        self.assertTrue(result.success)
        self.assertIn('Newbie', staffer.ctx.server.pending_help_requests)

    async def test_accept_missing_name_fails(self):
        staffer = make_client(make_player('Sam', available=True))
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, '#accept')
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# list / cancel / on / off
# ---------------------------------------------------------------------------

class TestHelpstaffManagement(unittest.IsolatedAsyncioTestCase):

    async def test_request_replaces_earlier_request(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['newbie'] = 'old'
        requester.ctx.prompt = AsyncMock(return_value='new')

        await HelpstaffCommand().execute(requester.ctx)

        self.assertEqual(requester.ctx.server.pending_help_requests, {'Newbie': 'new'})

    async def test_staffer_does_not_relay_to_self(self):
        sam = make_client(make_player('Sam', available=True))
        make_server(sam)
        result = await HelpstaffCommand().execute(sam.ctx)
        self.assertTrue(result.success)
        self.assertIn('No staff are currently available', _sent_text(sam.ctx))

    async def test_cancel_withdraws_and_notifies_staff(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(requester.ctx, '#cancel')

        self.assertTrue(result.success)
        self.assertEqual(requester.ctx.server.pending_help_requests, {})
        self.assertIn('withdrawn', _sent_text(staffer.ctx))

    async def test_cancel_without_request_fails(self):
        requester = make_client(make_player('Newbie'))
        make_server(requester)
        result = await HelpstaffCommand().execute(requester.ctx, '#cancel')
        self.assertFalse(result.success)

    async def test_list_shows_open_requests(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'), virtual_location='Reading mail')
        make_server(staffer, requester)
        staffer.ctx.server.pending_help_requests['Newbie'] = 'Where is the bar?'

        result = await HelpstaffCommand().execute(staffer.ctx, '#list')

        self.assertTrue(result.success)
        text = _sent_text(staffer.ctx)
        self.assertIn('Newbie (Reading mail): Where is the bar?', text)

    async def test_list_requires_staffer(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#list')
        self.assertFalse(result.success)

    async def test_admin_can_go_on_duty(self):
        admin = make_client(make_player('Ryan', admin=True))
        make_server(admin)
        admin.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(admin.ctx, '#on')

        self.assertTrue(result.success)
        self.assertTrue(admin.ctx.player.query_flag(PlayerFlags.HELPSTAFF))
        self.assertIn('1 open request', _sent_text(admin.ctx))

    async def test_plain_player_cannot_go_on_duty(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#on')
        self.assertFalse(result.success)
        self.assertFalse(player.ctx.player.query_flag(PlayerFlags.HELPSTAFF))

    async def test_staffer_can_go_off_duty(self):
        # Marked helpstaff via editplayer without being Admin/DM: can
        # still step off duty themselves.
        staffer = make_client(make_player('Sam', available=True))
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, '#off')
        self.assertTrue(result.success)
        self.assertFalse(staffer.ctx.player.query_flag(PlayerFlags.HELPSTAFF))

    async def test_show_lists_on_duty_staff(self):
        tara   = make_client(make_player('Tara', available=True))
        sam    = make_client(make_player('Sam', available=True))
        newbie = make_client(make_player('Newbie'))
        make_server(tara, sam, newbie)

        result = await HelpstaffCommand().execute(newbie.ctx, '#show')

        self.assertTrue(result.success)
        self.assertIn('On helpstaff duty: Sam, Tara', _sent_text(newbie.ctx))
        newbie.ctx.prompt.assert_not_awaited()

    async def test_show_with_nobody_on_duty(self):
        newbie = make_client(make_player('Newbie'))
        make_server(newbie)
        result = await HelpstaffCommand().execute(newbie.ctx, '#show')
        self.assertTrue(result.success)
        self.assertIn('No one is on helpstaff duty', _sent_text(newbie.ctx))

    async def test_unknown_switch_fails(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#bogus')
        self.assertFalse(result.success)

    async def test_bare_word_subcommand_rejected(self):
        # Subcommands are #switches only; the old bare-word form is an error.
        staffer = make_client(make_player('Sam', available=True))
        make_server(staffer)
        staffer.ctx.server.pending_help_requests['Newbie'] = 'help'
        result = await HelpstaffCommand().execute(staffer.ctx, 'list')
        self.assertFalse(result.success)
        staffer.ctx.prompt.assert_not_awaited()

    async def test_relay_mentions_switch_form(self):
        staffer   = make_client(make_player('Sam', available=True))
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.prompt = AsyncMock(return_value='help')
        await HelpstaffCommand().execute(requester.ctx)
        self.assertIn('helpstaff #accept Newbie', _sent_text(staffer.ctx))

    async def test_unknown_option_fails(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, 'bogus')
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# Command metadata
# ---------------------------------------------------------------------------

class TestHelpstaffTag(unittest.TestCase):

    def test_on_duty_staffer_is_tagged(self):
        self.assertEqual(tagged_name(make_player('Sam', available=True)), 'Sam [[Helpstaff]]')

    def test_off_duty_player_is_not_tagged(self):
        self.assertEqual(tagged_name(make_player('Newbie')), 'Newbie')


class TestHelpstaffMeta(unittest.TestCase):

    def test_name(self):
        self.assertEqual(HelpstaffCommand.name, 'helpstaff')

    def test_game_mode_only(self):
        # Character creation runs inside ctx.prompt() (no command
        # dispatch) and pre-login players are all "Generic Name", so
        # Mode.LOGIN can't usefully reach it -- see the module docstring.
        self.assertEqual(HelpstaffCommand.modes, {Mode.GAME})

    def test_has_help(self):
        self.assertIsNotNone(HelpstaffCommand.help)
        self.assertGreater(len(HelpstaffCommand.help.summary), 0)


if __name__ == '__main__':
    unittest.main()
