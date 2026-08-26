"""tests/social/test_board_edit.py

Unit tests for commands/board/edit.py -- the admin-only 'board #edit'
SIG/board structural editor (Phase 2 of the sig-editor project).
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import board as board_store
from commands.board.edit import edit_board_settings
from flags import PlayerFlags


def run(coro):
    return asyncio.run(coro)


class _FakePlayer:
    def __init__(self, name='tester', admin=True):
        self.name = name
        self._admin = admin
        self.return_key = 'Enter'

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        return False


def make_ctx(player=None, prompts=None):
    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompts or [])
    return ctx


class BoardEditTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sigs_path = Path(self._tmp.name) / 'board_sigs.json'
        self.meta_path = Path(self._tmp.name) / 'board_meta.json'
        self.threads_path = Path(self._tmp.name) / 'board_threads.json'
        for attr, path in (('SIGS_FILE', self.sigs_path),):
            patcher = patch.object(board_store.sigs, attr, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        meta_patcher = patch.object(board_store.meta, 'META_FILE', self.meta_path)
        meta_patcher.start()
        self.addCleanup(meta_patcher.stop)
        threads_patcher = patch.object(board_store.threads, 'BOARD_FILE', self.threads_path)
        threads_patcher.start()
        self.addCleanup(threads_patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _seed_sig_and_board(self, sig_name='General', board_name='General Discussion',
                             sig_id=1, board_id=1, **board_overrides):
        board_store.sigs.save_sigs(
            {'sigs': [{'id': sig_id, 'name': sig_name, 'board_ids': [board_id]}]}, self.sigs_path)
        board = {'id': board_id, 'name': board_name, 'anonymous_mode': 'ask',
                 'access': {'type': 'any'}, 'admins': []}
        board.update(board_overrides)
        board_store.meta.save_meta({'boards': {str(board_id): board}}, self.meta_path)


class TestPermission(BoardEditTestCase):
    def test_non_admin_denied(self):
        ctx = make_ctx(player=_FakePlayer(admin=False))
        result = run(edit_board_settings(ctx))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'permission_denied')
        ctx.prompt.assert_not_awaited()


class TestTopLevel(BoardEditTestCase):
    def test_bare_enter_saves_and_exits_with_nothing_seeded(self):
        ctx = make_ctx(prompts=[''])
        result = run(edit_board_settings(ctx))
        self.assertTrue(result.success)
        self.assertIn('saved', str(ctx.send.call_args_list).lower())

    def test_unrecognized_top_level_choice_reports_error_and_stays_in_menu(self):
        ctx = make_ctx(prompts=['zzz', ''])
        run(edit_board_settings(ctx))
        self.assertIn("Unrecognized choice 'zzz'", str(ctx.send.call_args_list))

    def test_nothing_saved_until_exit(self):
        # A SIG added mid-session shouldn't hit disk until the final Enter.
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['s', 'a', 'New SIG', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual([s['name'] for s in saved['sigs']], ['General', 'New SIG'])


class TestSigManagement(BoardEditTestCase):
    def test_add_sig(self):
        ctx = make_ctx(prompts=['s', 'a', 'Chit-Chat', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual([s['name'] for s in saved['sigs']], ['Chit-Chat'])

    def test_add_sig_blank_name_cancelled(self):
        ctx = make_ctx(prompts=['s', 'a', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved['sigs'], [])

    def test_rename_sig(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['s', '1', 'r', 'Renamed', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved['sigs'][0]['name'], 'Renamed')

    def test_delete_sig_with_boards_refused(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['s', '1', 'x', '', '', ''])
        run(edit_board_settings(ctx))
        self.assertIn('still has boards', str(ctx.send.call_args_list))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(len(saved['sigs']), 1)

    def test_delete_empty_sig(self):
        board_store.sigs.save_sigs({'sigs': [{'id': 1, 'name': 'Empty', 'board_ids': []}]}, self.sigs_path)
        ctx = make_ctx(prompts=['s', '1', 'x', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved['sigs'], [])

    def test_reorder_sigs(self):
        board_store.sigs.save_sigs({'sigs': [
            {'id': 1, 'name': 'First', 'board_ids': []},
            {'id': 2, 'name': 'Second', 'board_ids': []},
        ]}, self.sigs_path)
        # ImageBBS-style "Move <name> before which?" prompt, not an
        # up/down nudge -- move Second to position 1.
        ctx = make_ctx(prompts=['s', '2', 'o', '1', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual([s['name'] for s in saved['sigs']], ['Second', 'First'])

    def test_reorder_sig_out_of_range_position_rejected(self):
        board_store.sigs.save_sigs({'sigs': [
            {'id': 1, 'name': 'First', 'board_ids': []},
            {'id': 2, 'name': 'Second', 'board_ids': []},
        ]}, self.sigs_path)
        ctx = make_ctx(prompts=['s', '1', 'o', '99', '', '', ''])
        run(edit_board_settings(ctx))
        self.assertIn('Not a valid position', str(ctx.send.call_args_list))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual([s['name'] for s in saved['sigs']], ['First', 'Second'])

    def _seed_sig_with_two_boards(self):
        board_store.sigs.save_sigs({'sigs': [{'id': 1, 'name': 'General', 'board_ids': [1, 2]}]},
                                    self.sigs_path)
        board_store.meta.save_meta({'boards': {
            '1': {'id': 1, 'name': 'Alpha', 'anonymous_mode': 'ask', 'access': {'type': 'any'}, 'admins': []},
            '2': {'id': 2, 'name': 'Beta', 'anonymous_mode': 'ask', 'access': {'type': 'any'}, 'admins': []},
        }}, self.meta_path)

    def test_sig_detail_lists_its_boards(self):
        self._seed_sig_with_two_boards()
        ctx = make_ctx(prompts=['s', '1', '', '', ''])
        run(edit_board_settings(ctx))
        preambles = str(ctx.prompt.call_args_list)
        self.assertIn('Alpha', preambles)
        self.assertIn('Beta', preambles)

    def test_list_range_shows_only_that_range(self):
        # 'L1-1' -- text_editor.py's own '.l' dot-command convention,
        # a blank range instead lists everything (see the next test).
        self._seed_sig_with_two_boards()
        ctx = make_ctx(prompts=['s', '1', 'L1-1', '', '', ''])
        run(edit_board_settings(ctx))
        listed = str(ctx.send.call_args_list)
        self.assertIn('Alpha', listed)
        self.assertNotIn('Beta', listed)

    def test_bare_list_shows_every_board(self):
        self._seed_sig_with_two_boards()
        ctx = make_ctx(prompts=['s', '1', 'L', '', '', ''])
        run(edit_board_settings(ctx))
        listed = str(ctx.send.call_args_list)
        self.assertIn('Alpha', listed)
        self.assertIn('Beta', listed)

    def test_edit_range_opens_each_board_detail_one_at_a_time(self):
        self._seed_sig_with_two_boards()
        ctx = make_ctx(prompts=['s', '1', 'E1-2', '', '', '', '', ''])
        run(edit_board_settings(ctx))
        preambles = str(ctx.prompt.call_args_list)
        self.assertIn('Board: Alpha', preambles)
        self.assertIn('Board: Beta', preambles)

    def test_bare_edit_defaults_to_last_board(self):
        # Mirrors text_editor.py's own '.e' with no range: edits just
        # the last item, not everything.
        self._seed_sig_with_two_boards()
        ctx = make_ctx(prompts=['s', '1', 'E', '', '', '', ''])
        run(edit_board_settings(ctx))
        preambles = str(ctx.prompt.call_args_list)
        self.assertNotIn('Board: Alpha', preambles)
        self.assertIn('Board: Beta', preambles)


class TestBoardManagement(BoardEditTestCase):
    def test_rename_board(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['b', '1', 'r', 'New Name', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['name'], 'New Name')

    def test_rename_board_rejects_duplicate_name(self):
        board_store.sigs.save_sigs({'sigs': [{'id': 1, 'name': 'General', 'board_ids': [1, 2]}]}, self.sigs_path)
        board_store.meta.save_meta({'boards': {
            '1': {'id': 1, 'name': 'Alpha', 'anonymous_mode': 'ask', 'access': {'type': 'any'}, 'admins': []},
            '2': {'id': 2, 'name': 'Beta', 'anonymous_mode': 'ask', 'access': {'type': 'any'}, 'admins': []},
        }}, self.meta_path)
        ctx = make_ctx(prompts=['b', '1', 'r', 'Beta', '', '', ''])
        run(edit_board_settings(ctx))
        self.assertIn('already exists', str(ctx.send.call_args_list))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['name'], 'Alpha')

    def test_set_anonymous_mode(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['b', '1', 'a', 'y', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['anonymous_mode'], 'yes')

    def test_set_access_gate_guild(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['b', '1', 'g', 'g', '2', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['access'], {'type': 'guild', 'value': 'The Iron Fist'})

    def test_set_access_gate_flag(self):
        self._seed_sig_and_board()
        # 1 = ADMIN in _GATE_FLAG_CHOICES's curated, numbered order.
        ctx = make_ctx(prompts=['b', '1', 'g', 'f', '1', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['access'], {'type': 'flag', 'value': 'ADMIN'})

    def test_flag_gate_shows_a_numbered_list(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['b', '1', 'g', 'f', '1', '', '', ''])
        run(edit_board_settings(ctx))
        preambles = str(ctx.prompt.call_args_list)
        self.assertIn('Dungeon Master', preambles)
        self.assertIn('Guild Member', preambles)

    def test_set_access_gate_any_of(self):
        self._seed_sig_and_board()
        # 2 = FIST in the Guild enum's order; 2 = DUNGEON_MASTER in
        # _GATE_FLAG_CHOICES's order.
        ctx = make_ctx(prompts=['b', '1', 'g', 'o', '2', '2', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['access'], {
            'type': 'any_of',
            'values': [{'type': 'guild', 'value': 'The Iron Fist'},
                       {'type': 'flag', 'value': 'DUNGEON_MASTER'}],
        })

    def test_out_of_range_flag_number_rejected(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['b', '1', 'g', 'f', '99', '', '', ''])
        run(edit_board_settings(ctx))
        self.assertIn('Not a valid flag number', str(ctx.send.call_args_list))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['access'], {'type': 'any'})

    def test_add_and_remove_admins(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['b', '1', 'p', 'a', 'alice, bob', 'r1', '', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(saved['boards']['1']['admins'], ['bob'])

    def test_move_board_between_sigs(self):
        board_store.sigs.save_sigs({'sigs': [
            {'id': 1, 'name': 'General', 'board_ids': [1]},
            {'id': 2, 'name': 'Other', 'board_ids': []},
        ]}, self.sigs_path)
        board_store.meta.save_meta({'boards': {
            '1': {'id': 1, 'name': 'General Discussion', 'anonymous_mode': 'ask',
                  'access': {'type': 'any'}, 'admins': []},
        }}, self.meta_path)
        ctx = make_ctx(prompts=['b', '1', 'm', '1', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved['sigs'][0]['board_ids'], [])
        self.assertEqual(saved['sigs'][1]['board_ids'], [1])

    def test_share_board_into_another_sig_keeps_original(self):
        board_store.sigs.save_sigs({'sigs': [
            {'id': 1, 'name': 'General', 'board_ids': [1]},
            {'id': 2, 'name': 'Other', 'board_ids': []},
        ]}, self.sigs_path)
        board_store.meta.save_meta({'boards': {
            '1': {'id': 1, 'name': 'General Discussion', 'anonymous_mode': 'ask',
                  'access': {'type': 'any'}, 'admins': []},
        }}, self.meta_path)
        ctx = make_ctx(prompts=['b', '1', 'h', '1', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved['sigs'][0]['board_ids'], [1])
        self.assertEqual(saved['sigs'][1]['board_ids'], [1])

    def test_reorder_board_within_sig(self):
        board_store.sigs.save_sigs({'sigs': [
            {'id': 1, 'name': 'General', 'board_ids': [1, 2]},
        ]}, self.sigs_path)
        board_store.meta.save_meta({'boards': {
            '1': {'id': 1, 'name': 'Alpha', 'anonymous_mode': 'ask', 'access': {'type': 'any'}, 'admins': []},
            '2': {'id': 2, 'name': 'Beta', 'anonymous_mode': 'ask', 'access': {'type': 'any'}, 'admins': []},
        }}, self.meta_path)
        ctx = make_ctx(prompts=['b', '2', 'o', '1', '', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved['sigs'][0]['board_ids'], [2, 1])

    def test_delete_board_refused_with_threads(self):
        self._seed_sig_and_board()
        board_store.save_board([{'id': 1, 'board_id': 1, 'title': 'Hi', 'author': 'bob',
                                  'anonymous': False, 'posted_at': '2026-01-01T00:00:00',
                                  'body': [], 'replies': []}], self.threads_path)
        ctx = make_ctx(prompts=['b', '1', 'x', '', '', ''])
        run(edit_board_settings(ctx))
        self.assertIn('still has 1 thread', str(ctx.send.call_args_list))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertIn('1', saved['boards'])

    def test_delete_board_with_no_threads(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['b', '1', 'x', '', ''])
        run(edit_board_settings(ctx))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertNotIn('1', saved['boards'])
        saved_sigs = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved_sigs['sigs'][0]['board_ids'], [])


class TestNewBoard(BoardEditTestCase):
    def test_new_board_requires_a_sig_first(self):
        ctx = make_ctx(prompts=['n', ''])
        run(edit_board_settings(ctx))
        self.assertIn('Create a SIG first', str(ctx.send.call_args_list))

    def test_new_board(self):
        board_store.sigs.save_sigs({'sigs': [{'id': 1, 'name': 'General', 'board_ids': []}]}, self.sigs_path)
        ctx = make_ctx(prompts=['n', 'Off Topic', '1', ''])
        run(edit_board_settings(ctx))
        saved_meta = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(len(saved_meta['boards']), 1)
        new_id = next(iter(saved_meta['boards']))
        self.assertEqual(saved_meta['boards'][new_id]['name'], 'Off Topic')
        saved_sigs = board_store.sigs.load_sigs(self.sigs_path)
        self.assertEqual(saved_sigs['sigs'][0]['board_ids'], [int(new_id)])

    def test_new_board_rejects_duplicate_name(self):
        self._seed_sig_and_board()
        ctx = make_ctx(prompts=['n', 'General Discussion', ''])
        run(edit_board_settings(ctx))
        self.assertIn('already exists', str(ctx.send.call_args_list))
        saved = board_store.meta.load_meta(self.meta_path)
        self.assertEqual(len(saved['boards']), 1)


if __name__ == '__main__':
    unittest.main()
