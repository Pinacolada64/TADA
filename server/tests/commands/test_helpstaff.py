"""tests/commands/test_helpstaff.py — Unit tests for commands/helpstaff.py
and the helpstaff/ package (duty, queue, faq, review) plus
logon_events/helpstaff.py's login check-in."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from commands.base_command import CommandResult, Mode
from commands.helpstaff import HelpstaffCommand
from flags import PlayerFlags
from helpstaff import duty, faq
from helpstaff import queue as help_queue
from helpstaff.duty import tagged_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(name: str, *, member: bool = False, admin: bool = False,
                 dm: bool = False, map_level: int = 1, map_room: int = 10) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.map_level = map_level
    p.map_room = map_room
    p.unsaved_changes = False
    p.return_key = 'Return'
    p.is_expert = False
    p.client_settings.screen_columns = 40   # a C64's width

    flags = {PlayerFlags.HELPSTAFF: member, PlayerFlags.ADMIN: admin,
             PlayerFlags.DUNGEON_MASTER: dm}
    p.query_flag.side_effect = lambda flag: flags.get(flag, False)
    return p


def make_client(player, *, on_duty: bool = False, virtual_location=None, room=None) -> MagicMock:
    """A connected client with its own ctx wired back to itself, matching
    how commands see ctx.client/ctx.player/ctx.server in production."""
    client = MagicMock()
    client.virtual_location = virtual_location
    client.room = room
    client.helpstaff_on_duty = on_duty
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


class _IsolatedStore(unittest.IsolatedAsyncioTestCase):
    """Fresh save directory per test for helpstaff_queue.json /
    helpstaff_faq.json (and mail -- conftest already isolates
    mail.MAIL_DIR, re-patched here per test so tests can read it)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.save_dir = Path(self._tmp.name)
        self._patches = [
            patch('net_common.run_server_dir', str(self.save_dir)),
            patch('mail.MAIL_DIR', self.save_dir / 'mail'),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def mailbox(self, name: str) -> list:
        import mail
        return mail.load_mailbox(name)


# ---------------------------------------------------------------------------
# Duty: membership vs. on duty
# ---------------------------------------------------------------------------

class TestDuty(_IsolatedStore):

    async def test_member_can_go_on_duty(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        result = await HelpstaffCommand().execute(sam.ctx, '#on')
        self.assertTrue(result.success)
        self.assertTrue(duty.on_duty(sam))

    async def test_going_on_duty_never_touches_saved_flags(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        await HelpstaffCommand().execute(sam.ctx, '#on')
        await HelpstaffCommand().execute(sam.ctx, '#off')
        sam.ctx.player.set_flag.assert_not_called()
        sam.ctx.player.clear_flag.assert_not_called()
        self.assertFalse(sam.ctx.player.unsaved_changes)

    async def test_admin_and_dm_can_go_on_duty(self):
        for kw in ({'admin': True}, {'dm': True}):
            c = make_client(make_player('Boss', **kw))
            make_server(c)
            result = await HelpstaffCommand().execute(c.ctx, '#on')
            self.assertTrue(result.success, kw)
            self.assertTrue(duty.on_duty(c), kw)

    async def test_plain_player_cannot_go_on_duty(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#on')
        self.assertFalse(result.success)
        self.assertFalse(duty.on_duty(player))

    async def test_on_duty_notice_counts_waiting(self):
        sam = make_client(make_player('Sam', member=True))
        server = make_server(sam)
        server.pending_help_requests['Newbie'] = 'help'
        help_queue.add('Offline', 'a question')
        await HelpstaffCommand().execute(sam.ctx, '#on')
        text = _sent_text(sam.ctx)
        self.assertIn('1 open request', text)
        self.assertIn('1 saved question waiting', text)

    async def test_off_duty(self):
        sam = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(sam)
        result = await HelpstaffCommand().execute(sam.ctx, '#off')
        self.assertTrue(result.success)
        self.assertFalse(duty.on_duty(sam))

    async def test_off_when_not_on_duty(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        await HelpstaffCommand().execute(sam.ctx, '#off')
        self.assertIn("aren't on helpstaff duty", _sent_text(sam.ctx))

    def test_on_duty_requires_real_true(self):
        # A stand-in's auto-created attribute must not count as on duty.
        self.assertFalse(duty.on_duty(MagicMock()))

    def test_tag(self):
        p = make_player('Sam', member=True)
        self.assertEqual(tagged_name(p, make_client(p, on_duty=True)), 'Sam [[Helpstaff]]')
        self.assertEqual(tagged_name(p, make_client(p)), 'Sam')   # member, off duty

    def test_sender_name(self):
        self.assertEqual(duty.sender_name(make_player('Sam')), 'Sam, Helpstaff member')


# ---------------------------------------------------------------------------
# Request path (no args)
# ---------------------------------------------------------------------------

class TestHelpstaffRequest(_IsolatedStore):

    async def test_no_staff_queues_the_question(self):
        requester = make_client(make_player('Newbie'), virtual_location='Reading mail')
        make_server(requester)
        requester.ctx.prompt = AsyncMock(return_value='How do I fight?')

        result = await HelpstaffCommand().execute(requester.ctx)

        self.assertTrue(result.success)
        entry = help_queue.find('Newbie')
        self.assertEqual(entry['question'], 'How do I fight?')
        self.assertEqual(entry['location'], 'Reading mail')
        self.assertIn('answer it by', _sent_text(requester.ctx))
        preamble = ' '.join(requester.ctx.prompt.await_args.kwargs['preamble_lines'])
        self.assertIn('No one is on helpstaff duty', preamble)

    async def test_no_staff_empty_answer_queues_nothing(self):
        requester = make_client(make_player('Newbie'))
        make_server(requester)
        requester.ctx.prompt = AsyncMock(return_value='  ')
        await HelpstaffCommand().execute(requester.ctx)
        self.assertEqual(help_queue.load(), [])
        self.assertIn('Never mind', _sent_text(requester.ctx))

    async def test_queue_file_lives_in_save_dir(self):
        requester = make_client(make_player('Newbie'))
        make_server(requester)
        requester.ctx.prompt = AsyncMock(return_value='help')
        await HelpstaffCommand().execute(requester.ctx)
        data = json.loads((self.save_dir / 'helpstaff_queue.json').read_text())
        self.assertEqual(data[0]['name'], 'Newbie')

    async def test_asking_again_replaces_queued_question(self):
        requester = make_client(make_player('Newbie'))
        make_server(requester)
        help_queue.add('newbie', 'old')
        requester.ctx.prompt = AsyncMock(return_value='new')
        await HelpstaffCommand().execute(requester.ctx)
        self.assertEqual([e['question'] for e in help_queue.load()], ['new'])

    async def test_member_off_duty_does_not_count_as_available(self):
        member    = make_client(make_player('Sam', member=True))
        requester = make_client(make_player('Newbie'))
        make_server(member, requester)
        requester.ctx.prompt = AsyncMock(return_value='help')
        await HelpstaffCommand().execute(requester.ctx)
        self.assertIsNotNone(help_queue.find('Newbie'))
        self.assertEqual(_sent_text(member.ctx), '')

    async def test_request_relayed_to_on_duty_staffer(self):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True)
        requester = make_client(make_player('Newbie'), virtual_location='Reading mail')
        make_server(staffer, requester)
        help_queue.add('Newbie', 'an older saved question')
        requester.ctx.prompt = AsyncMock(return_value='How do I fight?')

        result = await HelpstaffCommand().execute(requester.ctx)

        self.assertTrue(result.success)
        self.assertEqual(requester.ctx.server.pending_help_requests.get('Newbie'),
                         'How do I fight?')
        self.assertIsNone(help_queue.find('Newbie'))   # live request replaces it
        sent_to_staffer = _sent_text(staffer.ctx)
        self.assertIn('Newbie needs help', sent_to_staffer)
        self.assertIn('How do I fight?', sent_to_staffer)
        self.assertIn('Reading mail', sent_to_staffer)
        self.assertIn('helpstaff #accept Newbie', sent_to_staffer)
        self.assertIn('Sam', _sent_text(requester.ctx))

    async def test_empty_response_cancels(self):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True)
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.prompt = AsyncMock(return_value='   ')

        result = await HelpstaffCommand().execute(requester.ctx)

        self.assertTrue(result.success)
        self.assertNotIn('Newbie', requester.ctx.server.pending_help_requests)
        self.assertIn('Never mind', _sent_text(requester.ctx))

    async def test_disconnect_response_cancels(self):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True)
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.prompt = AsyncMock(return_value=None)

        result = await HelpstaffCommand().execute(requester.ctx)

        self.assertTrue(result.success)
        self.assertNotIn('Newbie', requester.ctx.server.pending_help_requests)

    async def test_staffer_does_not_relay_to_self(self):
        # Staff ask with #ask (a bare HELPSTAFF only shows a reminder).
        sam = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(sam)
        sam.ctx.prompt = AsyncMock(return_value='help')
        await HelpstaffCommand().execute(sam.ctx, '#ask')
        self.assertEqual(sam.ctx.server.pending_help_requests, {})
        self.assertIsNotNone(help_queue.find('Sam'))

    async def test_bare_helpstaff_from_staff_shows_a_reminder_not_a_question(self):
        for who in (dict(member=True), dict(admin=True), dict(dm=True)):
            with self.subTest(**who):
                staffer = make_client(make_player('Railbender', **who))
                make_server(staffer)
                result = await HelpstaffCommand().execute(staffer.ctx)
                self.assertTrue(result.success)
                staffer.ctx.prompt.assert_not_awaited()
                text = _sent_text(staffer.ctx)
                self.assertIn('You are helpstaff', text)
                self.assertIn('helpstaff #show', text)
                self.assertIn('helpstaff #list', text)
                self.assertIn('helpstaff #ask', text)
                self.assertIsNone(help_queue.find('Railbender'))

    async def test_bare_helpstaff_from_on_duty_staff_also_reminds(self):
        sam = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(sam)
        await HelpstaffCommand().execute(sam.ctx)
        sam.ctx.prompt.assert_not_awaited()
        self.assertIn('You are helpstaff', _sent_text(sam.ctx))

    async def test_ask_lets_staff_ask_and_reaches_another_staffer(self):
        other = make_client(make_player('Sam', member=True), on_duty=True)
        asker = make_client(make_player('Railbender', admin=True))
        make_server(other, asker)
        asker.ctx.prompt = AsyncMock(return_value='Can someone check room 5?')
        result = await HelpstaffCommand().execute(asker.ctx, '#ask')
        self.assertTrue(result.success)
        self.assertEqual(asker.ctx.server.pending_help_requests.get('Railbender'),
                         'Can someone check room 5?')
        self.assertIn('Railbender needs help', _sent_text(other.ctx))

    async def test_ask_works_for_a_plain_player_too(self):
        newbie = make_client(make_player('Newbie'))
        make_server(newbie)
        newbie.ctx.prompt = AsyncMock(return_value='How do I fight?')
        await HelpstaffCommand().execute(newbie.ctx, '#ask')
        self.assertEqual(help_queue.find('Newbie')['question'], 'How do I fight?')


# ---------------------------------------------------------------------------
# Accept / decline
# ---------------------------------------------------------------------------

class TestHelpstaffAccept(_IsolatedStore):

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_accept_moves_staffer_not_requester(self, mock_teleport):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True, room=99)
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
        staffer   = make_client(make_player('Sam', member=True), on_duty=True, room=99)
        requester = make_client(make_player('Newbie', map_level=2),
                                 virtual_location='Reading mail', room=17)
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'How do I fight?'

        await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        call = mock_teleport.await_args
        self.assertEqual(call.args[1], 17)
        self.assertEqual(call.kwargs.get('level'), 2)

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_accept_queued_question_from_online_player(self, mock_teleport):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True, room=99)
        requester = make_client(make_player('Newbie'), room=42)
        make_server(staffer, requester)
        help_queue.add('Newbie', 'saved while nobody was on')

        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'newbie')

        self.assertTrue(result.success)
        self.assertIsNone(help_queue.find('Newbie'))
        self.assertEqual(mock_teleport.await_args.args[1], 42)

    async def test_cannot_accept_queued_question_from_offline_player(self):
        staffer = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(staffer)
        help_queue.add('Gone', 'question')
        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Gone')
        self.assertFalse(result.success)
        self.assertIsNotNone(help_queue.find('Gone'))

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_blocked_teleport_reopens_request(self, mock_teleport):
        mock_teleport.return_value = CommandResult.fail('The teleport is blocked!',
                                                        error='teleport_blocked')
        staffer   = make_client(make_player('Sam', member=True), on_duty=True, room=99)
        requester = make_client(make_player('Newbie'), room=42)
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        self.assertFalse(result.success)
        self.assertEqual(staffer.ctx.server.pending_help_requests.get('Newbie'), 'help')
        self.assertNotIn('arrived', _sent_text(requester.ctx).lower())
        self.assertIn('still open', _sent_text(staffer.ctx))

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_blocked_teleport_requeues_saved_question(self, mock_teleport):
        mock_teleport.return_value = CommandResult.fail('The teleport is blocked!',
                                                        error='teleport_blocked')
        staffer   = make_client(make_player('Sam', member=True), on_duty=True, room=99)
        requester = make_client(make_player('Newbie'), room=42)
        make_server(staffer, requester)
        help_queue.add('Newbie', 'saved', 'FOREST')
        await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')
        self.assertEqual(help_queue.find('Newbie')['question'], 'saved')

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_accept_same_room_skips_teleport(self, mock_teleport):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True, room=42)
        requester = make_client(make_player('Newbie'), room=42)
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Newbie')

        self.assertTrue(result.success)
        mock_teleport.assert_not_awaited()
        self.assertIn('here to help', _sent_text(requester.ctx))

    async def test_cannot_accept_own_request(self):
        sam = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(sam)
        sam.ctx.server.pending_help_requests['Sam'] = 'help'
        result = await HelpstaffCommand().execute(sam.ctx, '#accept', 'sam')
        self.assertFalse(result.success)
        self.assertIn('Sam', sam.ctx.server.pending_help_requests)

    async def test_plain_player_cannot_accept(self):
        # Staff-only switches answer a plain player like an unknown option
        # (commands/helpstaff.py's STAFF_SWITCHES).
        player    = make_client(make_player('Bob'))
        requester = make_client(make_player('Newbie'))
        make_server(player, requester)
        player.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(player.ctx, '#accept', 'Newbie')

        self.assertFalse(result.success)
        self.assertIn("unknown option '#accept'", _sent_text(player.ctx).lower())
        self.assertIn('Newbie', player.ctx.server.pending_help_requests)

    async def test_member_off_duty_told_to_go_on_duty(self):
        member = make_client(make_player('Sam', member=True))
        make_server(member)
        member.ctx.server.pending_help_requests['Newbie'] = 'help'
        result = await HelpstaffCommand().execute(member.ctx, '#accept', 'Newbie')
        self.assertFalse(result.success)
        self.assertIn('helpstaff #on', _sent_text(member.ctx))

    async def test_accept_unknown_request_fails(self):
        staffer = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, '#accept', 'Nobody')
        self.assertFalse(result.success)
        self.assertIn('no longer open', _sent_text(staffer.ctx).lower())

    @patch('commands.teleport.TeleportCommand._teleport', new_callable=AsyncMock)
    async def test_second_staffer_accept_after_claim_fails(self, mock_teleport):
        sam       = make_client(make_player('Sam', member=True), on_duty=True, room=1)
        tara      = make_client(make_player('Tara', member=True), on_duty=True, room=2)
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

    async def test_decline_leaves_request_open(self):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True)
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(staffer.ctx, '#decline', 'Newbie')

        self.assertTrue(result.success)
        self.assertIn('Newbie', staffer.ctx.server.pending_help_requests)

    async def test_decline_unknown_request_fails(self):
        staffer = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, '#decline', 'Nobody')
        self.assertFalse(result.success)

    async def test_accept_missing_name_fails(self):
        staffer = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, '#accept')
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# #show / #list / #cancel
# ---------------------------------------------------------------------------

class TestHelpstaffManagement(_IsolatedStore):

    async def test_show_lists_on_duty_staff_only(self):
        tara   = make_client(make_player('Tara', member=True), on_duty=True)
        sam    = make_client(make_player('Sam', member=True), on_duty=True)
        offdut = make_client(make_player('Zed', member=True))
        newbie = make_client(make_player('Newbie'))
        make_server(tara, sam, offdut, newbie)

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

    async def test_cancel_withdraws_live_request_and_notifies_staff(self):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True)
        requester = make_client(make_player('Newbie'))
        make_server(staffer, requester)
        requester.ctx.server.pending_help_requests['Newbie'] = 'help'

        result = await HelpstaffCommand().execute(requester.ctx, '#cancel')

        self.assertTrue(result.success)
        self.assertEqual(requester.ctx.server.pending_help_requests, {})
        self.assertIn('withdrawn', _sent_text(staffer.ctx))

    async def test_cancel_withdraws_queued_question(self):
        requester = make_client(make_player('Newbie'))
        make_server(requester)
        help_queue.add('Newbie', 'saved')
        result = await HelpstaffCommand().execute(requester.ctx, '#cancel')
        self.assertTrue(result.success)
        self.assertIsNone(help_queue.find('Newbie'))

    async def test_cancel_without_request_fails(self):
        requester = make_client(make_player('Newbie'))
        make_server(requester)
        result = await HelpstaffCommand().execute(requester.ctx, '#cancel')
        self.assertFalse(result.success)

    async def test_list_shows_open_requests(self):
        staffer   = make_client(make_player('Sam', member=True), on_duty=True)
        requester = make_client(make_player('Newbie'), virtual_location='Reading mail')
        make_server(staffer, requester)
        staffer.ctx.server.pending_help_requests['Newbie'] = 'Where is the bar?'

        result = await HelpstaffCommand().execute(staffer.ctx, '#list')

        self.assertTrue(result.success)
        self.assertIn('Newbie (Reading mail): Where is the bar?', _sent_text(staffer.ctx))

    async def test_list_shows_online_queued_and_counts_offline(self):
        staffer = make_client(make_player('Sam', member=True), on_duty=True)
        online  = make_client(make_player('Newbie'), virtual_location='Reading mail')
        make_server(staffer, online)
        help_queue.add('Newbie', 'saved, online')
        help_queue.add('Gone', 'saved, offline')

        await HelpstaffCommand().execute(staffer.ctx, '#list')

        text = _sent_text(staffer.ctx)
        self.assertIn('Saved questions from players online now:', text)
        self.assertIn('Newbie (Reading mail): saved, online', text)
        self.assertNotIn('saved, offline', text)
        self.assertIn('1 more saved question', text)

    async def test_list_requires_on_duty(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#list')
        self.assertFalse(result.success)

    async def test_bare_word_subcommand_rejected(self):
        # Subcommands are #switches only; the old bare-word form is an error.
        staffer = make_client(make_player('Sam', member=True), on_duty=True)
        make_server(staffer)
        result = await HelpstaffCommand().execute(staffer.ctx, 'list')
        self.assertFalse(result.success)
        staffer.ctx.prompt.assert_not_awaited()

    async def test_unknown_switch_fails(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#bogus')
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# FAQ
# ---------------------------------------------------------------------------

class TestFaq(_IsolatedStore):

    def test_first_load_seeds_starter_answers(self):
        entries = faq.load()
        self.assertEqual([e['title'] for e in entries],
                         [e['title'] for e in faq.STARTER_ANSWERS])
        self.assertTrue((self.save_dir / 'helpstaff_faq.json').exists())

    def test_deleting_everything_does_not_reseed(self):
        for _ in range(len(faq.load())):
            faq.delete(1)
        self.assertEqual(faq.load(), [])

    async def test_list_and_show(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        await HelpstaffCommand().execute(sam.ctx, '#faq')
        self.assertIn('1. Getting started', _sent_text(sam.ctx))
        await HelpstaffCommand().execute(sam.ctx, '#faq', '2')
        self.assertIn('Hunger and thirst', _sent_text(sam.ctx))

    async def test_plain_player_cannot_use_faq(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#faq')
        self.assertFalse(result.success)

    async def test_dm_can_add(self):
        dm = make_client(make_player('Dee', dm=True))
        make_server(dm)
        dm.ctx.prompt = AsyncMock(return_value='Finding the bar')
        with patch('text_editor.run_editor', AsyncMock(return_value=['It is on level 1.'])):
            result = await HelpstaffCommand().execute(dm.ctx, '#faq', '#add')
        self.assertTrue(result.success)
        self.assertEqual(faq.load()[-1], {'title': 'Finding the bar', 'body': ['It is on level 1.']})

    async def test_edit_keeps_title_on_return(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        sam.ctx.prompt = AsyncMock(return_value='')
        with patch('text_editor.run_editor', AsyncMock(return_value=['New body.'])):
            await HelpstaffCommand().execute(sam.ctx, '#faq', '#edit', '1')
        self.assertEqual(faq.get(1), {'title': 'Getting started', 'body': ['New body.']})

    async def test_edit_aborted_changes_nothing(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        before = faq.get(1)
        sam.ctx.prompt = AsyncMock(return_value='Renamed')
        with patch('text_editor.run_editor', AsyncMock(return_value=None)):
            await HelpstaffCommand().execute(sam.ctx, '#faq', '#edit', '1')
        self.assertEqual(faq.get(1), before)

    async def test_delete_needs_yes(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        count = len(faq.load())
        sam.ctx.prompt = AsyncMock(return_value='n')
        await HelpstaffCommand().execute(sam.ctx, '#faq', '#delete', '1')
        self.assertEqual(len(faq.load()), count)
        sam.ctx.prompt = AsyncMock(return_value='y')
        await HelpstaffCommand().execute(sam.ctx, '#faq', '#delete', '1')
        self.assertEqual(len(faq.load()), count - 1)

    async def test_edit_bad_number(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        result = await HelpstaffCommand().execute(sam.ctx, '#faq', '#edit', '99')
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# #queue review and mailed answers
# ---------------------------------------------------------------------------

class TestReview(_IsolatedStore):

    async def test_answer_with_editor_mails_from_helpstaff_member(self):
        sam    = make_client(make_player('Sam', member=True))
        newbie = make_client(make_player('Newbie'))
        make_server(sam, newbie)
        help_queue.add('Newbie', 'How do I eat?', 'FOREST')
        sam.ctx.prompt = AsyncMock(side_effect=['a', ''])
        with patch('text_editor.run_editor', AsyncMock(return_value=['Type eat.'])):
            result = await HelpstaffCommand().execute(sam.ctx, '#queue')

        self.assertTrue(result.success)
        self.assertIsNone(help_queue.find('Newbie'))
        [msg] = self.mailbox('Newbie')
        self.assertEqual(msg['from'], 'Sam, Helpstaff member')
        self.assertEqual(msg['reply_to'], 'Sam')
        self.assertIn('  "How do I eat?"', msg['body'])
        self.assertIn('Type eat.', msg['body'])
        self.assertIn('answered your help request', _sent_text(newbie.ctx))

    async def test_answer_with_faq_and_note(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        help_queue.add('Gone', 'I keep starving')
        sam.ctx.prompt = AsyncMock(side_effect=['f', '2', 'Good question!'])
        await HelpstaffCommand().execute(sam.ctx, '#queue')
        [msg] = self.mailbox('Gone')
        body = msg['body']
        self.assertIn('Good question!', body)
        self.assertEqual(body[body.index('Good question!') + 2], faq.get(2)['body'][0])
        self.assertIsNone(help_queue.find('Gone'))

    async def test_skip_close_and_stop(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        help_queue.add('One', 'q1')
        help_queue.add('Two', 'q2')
        help_queue.add('Three', 'q3')
        sam.ctx.prompt = AsyncMock(side_effect=['s', 'c', ''])
        await HelpstaffCommand().execute(sam.ctx, '#queue')
        self.assertEqual([e['name'] for e in help_queue.load()], ['One', 'Three'])
        self.assertEqual(self.mailbox('Two'), [])     # closed without a reply
        self.assertIn('2 question(s) still waiting', _sent_text(sam.ctx))

    async def test_cannot_answer_own_question(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        help_queue.add('Sam', 'mine')
        sam.ctx.prompt = AsyncMock(side_effect=['a', ''])
        await HelpstaffCommand().execute(sam.ctx, '#queue')
        self.assertIsNotNone(help_queue.find('Sam'))
        self.assertIn("can't answer your own", _sent_text(sam.ctx))

    async def test_editor_abort_keeps_question(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        help_queue.add('Newbie', 'q')
        sam.ctx.prompt = AsyncMock(side_effect=['a', ''])
        with patch('text_editor.run_editor', AsyncMock(return_value=None)):
            await HelpstaffCommand().execute(sam.ctx, '#queue')
        self.assertIsNotNone(help_queue.find('Newbie'))

    async def test_empty_queue(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        await HelpstaffCommand().execute(sam.ctx, '#queue')
        self.assertIn('No questions are waiting', _sent_text(sam.ctx))

    async def test_plain_player_cannot_review(self):
        player = make_client(make_player('Newbie'))
        make_server(player)
        result = await HelpstaffCommand().execute(player.ctx, '#queue')
        self.assertFalse(result.success)


class TestMailReplyTo(_IsolatedStore):

    def test_add_message_records_reply_to(self):
        import mail
        mail.add_message('Newbie', 'Sam, Helpstaff member', 'hi', reply_to='Sam')
        mail.add_message('Newbie', 'Bob', 'plain')
        first, second = self.mailbox('Newbie')
        self.assertEqual(first['reply_to'], 'Sam')
        self.assertNotIn('reply_to', second)

    async def test_mail_reply_goes_to_reply_to(self):
        import mail
        from commands.mail import MailCommand
        mail.add_message('Newbie', 'Sam, Helpstaff member', 'answer', reply_to='Sam')
        newbie = make_client(make_player('Newbie'))
        make_server(newbie)
        with patch('commands.page.PageCommand.execute',
                   AsyncMock(return_value=CommandResult.ok())) as page:
            await MailCommand().execute(newbie.ctx, '#reply', '1=Thanks!')
        self.assertEqual(page.await_args.args[1], 'Sam=Thanks!')


# ---------------------------------------------------------------------------
# Login check-in
# ---------------------------------------------------------------------------

class TestLoginCheckin(_IsolatedStore):

    async def _checkin(self, client):
        from logon_events.helpstaff import helpstaff_checkin
        await helpstaff_checkin(client.ctx, client.ctx.player)

    async def test_non_member_is_not_asked(self):
        admin = make_client(make_player('Boss', admin=True))
        make_server(admin)
        await self._checkin(admin)
        admin.ctx.prompt.assert_not_awaited()

    async def test_member_says_yes(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        sam.ctx.prompt = AsyncMock(return_value='y')
        await self._checkin(sam)
        self.assertTrue(duty.on_duty(sam))
        sam.ctx.prompt.assert_awaited_once()      # nothing saved: no review offer

    async def test_member_return_stays_off(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        sam.ctx.prompt = AsyncMock(return_value='')
        await self._checkin(sam)
        self.assertFalse(duty.on_duty(sam))

    async def test_offers_review_when_questions_saved(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        help_queue.add('Newbie', 'q')
        sam.ctx.prompt = AsyncMock(side_effect=['n', 'y'])
        with patch('helpstaff.review.review_queue', AsyncMock(return_value=0)) as review:
            await self._checkin(sam)
        review.assert_awaited_once()
        preamble = ' '.join(sam.ctx.prompt.await_args_list[0].kwargs['preamble_lines'])
        self.assertIn('1 saved question waiting', preamble)

    async def test_declining_review_leaves_queue(self):
        sam = make_client(make_player('Sam', member=True))
        make_server(sam)
        help_queue.add('Newbie', 'q')
        sam.ctx.prompt = AsyncMock(side_effect=['y', ''])
        with patch('helpstaff.review.review_queue', AsyncMock(return_value=0)) as review:
            await self._checkin(sam)
        review.assert_not_awaited()
        self.assertIsNotNone(help_queue.find('Newbie'))


# ---------------------------------------------------------------------------
# Command metadata
# ---------------------------------------------------------------------------

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
