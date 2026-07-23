"""tests/social/test_mail_command.py

Unit tests for commands/mail.py -- the in-game MAIL command surface.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import mail as mail_store
from commands.mail import MailCommand
from flags import PlayerFlags


def run(coro):
    return asyncio.run(coro)


class _FakeCommandSettings:
    def __init__(self, groups=None):
        self.groups = groups or {}


class _FakePlayer:
    def __init__(self, name='bob', groups=None, prompt_mode=False, is_expert=False):
        self.name = name
        self.return_key = 'Enter'
        self.command_settings = _FakeCommandSettings(groups)
        self.is_expert = is_expert
        self._prompt_mode = prompt_mode

    def query_flag(self, flag):
        if flag == PlayerFlags.PROMPT_MODE:
            return self._prompt_mode
        return False


def make_ctx(player=None, prompts=None):
    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.client.virtual_location = None
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompts or [])
    return ctx


class MailCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(mail_store, 'MAIL_DIR', Path(self._tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _seed(self, name, messages):
        mail_store.save_mailbox(name, messages)


def _msg(**kw):
    base = {'from': 'Alice', 'timestamp': '2026-07-23T10:00:00', 'body': 'hi', 'read': False}
    base.update(kw)
    return base


class TestList(MailCommandTestCase):

    def test_no_mail_message(self):
        ctx = make_ctx()
        run(MailCommand().execute(ctx))
        sent = str(ctx.send.call_args)
        self.assertIn('no mail', sent.lower())

    def test_lists_sender_and_stays_until_blank(self):
        self._seed('bob', [_msg(**{'from': 'Alice'})])
        ctx = make_ctx(prompts=[''])
        run(MailCommand().execute(ctx))
        preamble = ctx.prompt.call_args.kwargs['preamble_lines']
        self.assertTrue(any('Alice' in ln for ln in preamble))

    def test_new_status_shown_for_unread(self):
        self._seed('bob', [_msg(read=False)])
        ctx = make_ctx(prompts=[''])
        run(MailCommand().execute(ctx))
        preamble = ctx.prompt.call_args.kwargs['preamble_lines']
        row = next(ln for ln in preamble if 'Alice' in ln)
        self.assertIn('New', row)

    def test_sets_and_restores_virtual_location(self):
        self._seed('bob', [_msg()])
        seen = []

        async def _prompt(*a, **kw):
            seen.append(ctx.client.virtual_location)
            return ''
        ctx = make_ctx()
        ctx.prompt = AsyncMock(side_effect=_prompt)
        run(MailCommand().execute(ctx))
        self.assertEqual(seen, ['Reading mail'])
        self.assertIsNone(ctx.client.virtual_location)

    def test_number_inside_listing_reads_message(self):
        self._seed('bob', [_msg(body='secret body')])
        ctx = make_ctx(prompts=['1', ''])
        run(MailCommand().execute(ctx))
        sent = ''.join(str(c) for c in ctx.send.call_args_list)
        self.assertIn('secret body', sent)

    def test_d_prefix_inside_listing_deletes_message(self):
        self._seed('bob', [_msg()])
        ctx = make_ctx(prompts=['d1'])
        run(MailCommand().execute(ctx))
        self.assertEqual(mail_store.load_mailbox('bob'), [])


class TestReadOne(MailCommandTestCase):

    def test_read_marks_message_read(self):
        self._seed('bob', [_msg(read=False)])
        ctx = make_ctx()
        run(MailCommand().execute(ctx, '1'))
        self.assertTrue(mail_store.load_mailbox('bob')[0]['read'])

    def test_read_shows_from_and_body(self):
        self._seed('bob', [_msg(**{'from': 'Carol', 'body': 'meet at dawn'})])
        ctx = make_ctx()
        run(MailCommand().execute(ctx, '1'))
        sent = ''.join(str(c) for c in ctx.send.call_args_list)
        self.assertIn('Carol', sent)
        self.assertIn('meet at dawn', sent)

    def test_out_of_range_number(self):
        self._seed('bob', [_msg()])
        ctx = make_ctx()
        result = run(MailCommand().execute(ctx, '99'))
        self.assertFalse(result.success)


class TestDelete(MailCommandTestCase):

    def test_delete_removes_message(self):
        self._seed('bob', [_msg(), _msg(body='second')])
        ctx = make_ctx()
        run(MailCommand().execute(ctx, '#delete', '1'))
        inbox = mail_store.load_mailbox('bob')
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['body'], 'second')

    def test_delete_out_of_range(self):
        self._seed('bob', [_msg()])
        ctx = make_ctx()
        result = run(MailCommand().execute(ctx, '#delete', '99'))
        self.assertFalse(result.success)


class TestReply(MailCommandTestCase):

    def test_reply_pages_the_original_sender(self):
        self._seed('bob', [_msg(**{'from': 'Alice'})])
        ctx = make_ctx()
        with patch('commands.page.find_online', return_value=([], ['Alice'])), \
             patch('commands.page.player_exists', return_value=True):
            ctx.prompt = AsyncMock(return_value='n')  # decline offline-mail offer
            run(MailCommand().execute(ctx, '#reply', '1=On my way!'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('Alice', sent)

    def test_reply_missing_equals(self):
        self._seed('bob', [_msg()])
        ctx = make_ctx()
        result = run(MailCommand().execute(ctx, '#reply', '1'))
        self.assertFalse(result.success)

    def test_reply_to_out_of_range_message(self):
        self._seed('bob', [_msg()])
        ctx = make_ctx()
        result = run(MailCommand().execute(ctx, '#reply', '99=hello'))
        self.assertFalse(result.success)

    def test_cannot_reply_to_self(self):
        self._seed('bob', [_msg(**{'from': 'bob'})])
        ctx = make_ctx()
        result = run(MailCommand().execute(ctx, '#reply', '1=hello'))
        self.assertFalse(result.success)


class TestComposeShort(MailCommandTestCase):

    def test_short_message_delivered_regardless_of_online_status(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True):
            result = run(MailCommand().execute(ctx, 'Alice=Meet', 'at', 'the', 'inn'))
        self.assertTrue(result.success)
        inbox = mail_store.load_mailbox('Alice')
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['from'], 'bob')
        self.assertEqual(inbox[0]['body'], 'Meet at the inn')

    def test_multiple_comma_targets(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True):
            run(MailCommand().execute(ctx, 'Alice,Carol=Party'))
        self.assertEqual(len(mail_store.load_mailbox('Alice')), 1)
        self.assertEqual(len(mail_store.load_mailbox('Carol')), 1)

    def test_quoted_target_with_space(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True):
            run(MailCommand().execute(ctx, '"Dark Lord"=Surrender'))
        self.assertEqual(len(mail_store.load_mailbox('Dark Lord')), 1)

    def test_group_target_expands(self):
        player = _FakePlayer(groups={'friends': ['Alice', 'Carol']})
        ctx = make_ctx(player=player)
        with patch('commands.mail.player_exists', return_value=True):
            run(MailCommand().execute(ctx, '#friends=hi'))
        self.assertEqual(len(mail_store.load_mailbox('Alice')), 1)
        self.assertEqual(len(mail_store.load_mailbox('Carol')), 1)

    def test_unknown_group_reported(self):
        ctx = make_ctx()
        result = run(MailCommand().execute(ctx, '#nosuchgroup=hi'))
        self.assertIn('no group named', ctx.send.call_args_list[-1].args[0].lower())

    def test_unknown_player_reported(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=False):
            result = run(MailCommand().execute(ctx, 'Ghost=hi'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('No such player', sent)

    def test_cannot_mail_self(self):
        ctx = make_ctx()
        result = run(MailCommand().execute(ctx, 'bob=hi'))
        self.assertFalse(result.success)
        sent = str(ctx.send.call_args_list)
        self.assertIn('cannot mail yourself', sent.lower())

    def test_missing_message_after_equals(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True):
            result = run(MailCommand().execute(ctx, 'Alice='))
        self.assertFalse(result.success)


class TestComposeLong(MailCommandTestCase):

    def test_no_equals_opens_editor_and_delivers_on_save(self):
        ctx = make_ctx()
        serialized = [{'text': 'A longer letter.', 'justification': 'LEFT'}]
        with patch('commands.mail.player_exists', return_value=True), \
             patch('text_editor.run_editor', new=AsyncMock(return_value=serialized)):
            result = run(MailCommand().execute(ctx, 'Alice'))
        self.assertTrue(result.success)
        inbox = mail_store.load_mailbox('Alice')
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['body'], serialized)

    def test_editor_abort_does_not_deliver(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('text_editor.run_editor', new=AsyncMock(return_value=None)):
            run(MailCommand().execute(ctx, 'Alice'))
        self.assertEqual(mail_store.load_mailbox('Alice'), [])

    def test_editor_empty_body_does_not_deliver(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('text_editor.run_editor', new=AsyncMock(return_value=[])):
            run(MailCommand().execute(ctx, 'Alice'))
        self.assertEqual(mail_store.load_mailbox('Alice'), [])

    def test_long_letter_renders_via_read(self):
        self._seed('bob', [])
        serialized = [{'text': 'Structured line.', 'justification': 'LEFT'}]
        mail_store.add_message('bob', 'Alice', serialized)
        ctx = make_ctx()
        run(MailCommand().execute(ctx, '1'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('Structured line.', sent)

    def test_unknown_target_does_not_open_editor(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=False), \
             patch('text_editor.run_editor', new=AsyncMock()) as mock_editor:
            run(MailCommand().execute(ctx, 'Ghost'))
        mock_editor.assert_not_called()


class TestComposeOnlineNotify(MailCommandTestCase):

    def _online_target_ctx(self, name='Alice', is_expert=False):
        target_ctx = MagicMock()
        target_ctx.player.name = name
        target_ctx.player.is_expert = is_expert
        target_ctx.send = AsyncMock()
        return target_ctx

    def test_short_message_notifies_online_target(self):
        target_ctx = self._online_target_ctx()
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('commands.mail.find_online', return_value=([target_ctx], [])):
            run(MailCommand().execute(ctx, 'Alice=hi'))
        target_ctx.send.assert_awaited_once()
        sent = str(target_ctx.send.call_args)
        self.assertIn('new mail', sent.lower())
        self.assertIn('bob', sent.lower())

    def test_notify_includes_hint_for_non_expert(self):
        target_ctx = self._online_target_ctx(is_expert=False)
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('commands.mail.find_online', return_value=([target_ctx], [])):
            run(MailCommand().execute(ctx, 'Alice=hi'))
        sent = str(target_ctx.send.call_args)
        self.assertIn("type 'mail' to read", sent)

    def test_notify_omits_hint_for_expert(self):
        target_ctx = self._online_target_ctx(is_expert=True)
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('commands.mail.find_online', return_value=([target_ctx], [])):
            run(MailCommand().execute(ctx, 'Alice=hi'))
        sent = str(target_ctx.send.call_args)
        self.assertNotIn("type 'mail' to read", sent)
        self.assertIn('You have new mail from bob.', sent)

    def test_short_message_does_not_notify_offline_target(self):
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('commands.mail.find_online', return_value=([], ['Alice'])):
            run(MailCommand().execute(ctx, 'Alice=hi'))
        # Only the sender's own ctx.send should have fired ("Mail sent to Alice.").
        self.assertEqual(len(ctx.send.call_args_list), 1)

    def test_long_letter_notifies_online_target(self):
        target_ctx = self._online_target_ctx()
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('commands.mail.find_online', return_value=([target_ctx], [])), \
             patch('text_editor.run_editor', new=AsyncMock(return_value=[{'text': 'hi', 'justification': 'LEFT'}])):
            run(MailCommand().execute(ctx, 'Alice'))
        target_ctx.send.assert_awaited_once()

    def test_notifies_each_online_target_of_several(self):
        alice_ctx = self._online_target_ctx('Alice')
        carol_ctx = self._online_target_ctx('Carol')
        ctx = make_ctx()
        with patch('commands.mail.player_exists', return_value=True), \
             patch('commands.mail.find_online', return_value=([alice_ctx, carol_ctx], [])):
            run(MailCommand().execute(ctx, 'Alice,Carol=hi'))
        alice_ctx.send.assert_awaited_once()
        carol_ctx.send.assert_awaited_once()


class TestReadInteractive(MailCommandTestCase):

    def test_falls_back_to_list_when_prompt_mode_off(self):
        self._seed('bob', [_msg(), _msg(body='second')])
        player = _FakePlayer(prompt_mode=False)
        ctx = make_ctx(player=player, prompts=[''])
        run(MailCommand().execute(ctx, '#read'))
        # _list()'s own prompt text, not the #read command-bar prompt.
        self.assertIn('Read which', str(ctx.prompt.call_args))

    def test_falls_back_to_list_with_only_one_message(self):
        self._seed('bob', [_msg()])
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player, prompts=[''])
        run(MailCommand().execute(ctx, '#read'))
        self.assertIn('Read which', str(ctx.prompt.call_args))

    def test_no_mail(self):
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player)
        run(MailCommand().execute(ctx, '#read'))
        self.assertIn('no mail', str(ctx.send.call_args).lower())

    def test_walks_each_message_and_marks_read(self):
        self._seed('bob', [_msg(read=False), _msg(body='second', read=False)])
        player = _FakePlayer(prompt_mode=True)
        # Blank ('keep'/next) through both messages, then blank again for
        # "End of mail."
        ctx = make_ctx(player=player, prompts=['', ''])
        run(MailCommand().execute(ctx, '#read'))
        inbox = mail_store.load_mailbox('bob')
        self.assertTrue(all(m['read'] for m in inbox))

    def test_k_keeps_and_advances(self):
        self._seed('bob', [_msg(), _msg(body='second')])
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player, prompts=['k', 'k'])
        run(MailCommand().execute(ctx, '#read'))
        self.assertEqual(len(mail_store.load_mailbox('bob')), 2)

    def test_d_deletes_and_does_not_advance(self):
        self._seed('bob', [_msg(**{'from': 'Alice'}), _msg(**{'from': 'Carol', 'body': 'second'})])
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player, prompts=['d', ''])
        run(MailCommand().execute(ctx, '#read'))
        inbox = mail_store.load_mailbox('bob')
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['from'], 'Carol')

    def test_a_archives_and_excludes_from_future_walks(self):
        self._seed('bob', [_msg(**{'from': 'Alice'}), _msg(**{'from': 'Carol', 'body': 'second'})])
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player, prompts=['a', ''])
        run(MailCommand().execute(ctx, '#read'))
        inbox = mail_store.load_mailbox('bob')
        self.assertTrue(inbox[0]['archived'])
        self.assertFalse(inbox[1].get('archived', False))

    def test_archived_message_excluded_from_numbering(self):
        self._seed('bob', [_msg(**{'from': 'Alice', 'archived': True}),
                            _msg(**{'from': 'Carol', 'body': 'second'})])
        ctx = make_ctx()
        run(MailCommand().execute(ctx, '1'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('Carol', sent)

    def test_o_redisplays_same_message(self):
        self._seed('bob', [_msg(), _msg(body='second')])
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player, prompts=['o', '', ''])
        run(MailCommand().execute(ctx, '#read'))
        # Sent at least twice for message #1 (initial + after 'o'), plus
        # once for message #2 -- 3 "Message N of 2" headers total.
        sent = str(ctx.send.call_args_list)
        self.assertEqual(sent.count('Message 1 of 2'), 2)

    def test_r_replies_and_advances(self):
        self._seed('bob', [_msg(**{'from': 'Alice'}), _msg(body='second')])
        player = _FakePlayer(prompt_mode=True)
        # r -> msg #1 menu; reply text; 'n' declines PAGE's offline-mail
        # offer (Alice isn't online); '' -> msg #2 menu (keep/next).
        ctx = make_ctx(player=player, prompts=['r', 'On my way!', 'n', ''])
        with patch('commands.page.find_online', return_value=([], ['Alice'])), \
             patch('commands.page.player_exists', return_value=True):
            run(MailCommand().execute(ctx, '#read'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('Alice', sent)

    def test_disconnect_mid_walk_exits_cleanly(self):
        self._seed('bob', [_msg(), _msg(body='second')])
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player, prompts=[None])
        result = run(MailCommand().execute(ctx, '#read'))
        self.assertTrue(result.success)

    def test_restores_virtual_location(self):
        self._seed('bob', [_msg(), _msg(body='second')])
        player = _FakePlayer(prompt_mode=True)
        ctx = make_ctx(player=player, prompts=['', ''])
        run(MailCommand().execute(ctx, '#read'))
        self.assertIsNone(ctx.client.virtual_location)


if __name__ == '__main__':
    unittest.main()
