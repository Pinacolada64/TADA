"""tests/test_quote.py

Unit tests for SPUR.MISC2.S:488-503's QUOTE command:

  - tada_utilities.format_quote() -- "$" substitution for the *reading*
    player's name, not the author's.
  - Player.quote field (default None, round-trips through save/load).
  - commands/quote.py's View/Write/Quit flow.
  - simple_server.py's _describe_room() showing each bystander's quote
    (substituted with the *viewer's* name), and that showing bystanders
    no longer clobbers the viewer's own player reference (a real bug:
    the room-listing loop used to reassign the outer `player` variable
    to each bystander in turn, so anything read from it afterwards --
    e.g. the debug-mode flag check -- used a random *other* occupant's
    data instead of the viewer's own).

Run with:
    python -m pytest tests/test_quote.py -v
"""
from __future__ import annotations

import unittest

from simple_server import Server
from tada_utilities import format_quote
from commands.quote import QuoteCommand


class TestFormatQuote(unittest.TestCase):

    def test_no_quote_set_returns_none(self):
        self.assertIsNone(format_quote(None, 'Rulan'))
        self.assertIsNone(format_quote('', 'Rulan'))

    def test_dollar_substituted_with_reader_name(self):
        self.assertEqual(format_quote('Hello $, welcome!', 'Rulan'),
                          "'Hello Rulan, welcome!'")

    def test_no_dollar_returned_unchanged_but_quoted(self):
        self.assertEqual(format_quote('Trespassers will be shot.', 'Rulan'),
                          "'Trespassers will be shot.'")

    def test_only_first_dollar_replaced(self):
        self.assertEqual(format_quote('$ meets $ again', 'Rulan'),
                          "'Rulan meets $ again'")

    def test_dollar_at_start(self):
        self.assertEqual(format_quote('$, go away.', 'Rulan'), "'Rulan, go away.'")

    def test_dollar_at_end(self):
        self.assertEqual(format_quote('Welcome, $', 'Rulan'), "'Welcome, Rulan'")


class TestPlayerQuoteField(unittest.TestCase):

    def test_defaults_to_none(self):
        from player import Player
        self.assertIsNone(Player().quote)

    def test_survives_save_and_load_roundtrip(self):
        import tempfile
        from unittest.mock import patch
        from pathlib import Path
        from player import Player

        with tempfile.TemporaryDirectory() as tmp:
            with patch('player.Player._json_path',
                       staticmethod(lambda user_id: str(Path(tmp) / f'player-{user_id}.json'))):
                p = Player(name='Rulan', id='rulan')
                p.quote = 'Hello $, welcome!'
                p.unsaved_changes = True
                assert p.save(force=True)

                reloaded = Player(name='Rulan', id='rulan')
                self.assertEqual(reloaded.quote, 'Hello $, welcome!')


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestQuoteCommand(unittest.IsolatedAsyncioTestCase):

    async def test_view_when_unset_shows_silent(self):
        from player import Player
        player = Player(name='Rulan')
        ctx = _FakeCtx(['v', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertIn('Rulan is silent..', ctx._flat())

    async def test_view_substitutes_own_name_as_reader(self):
        from player import Player
        player = Player(name='Rulan')
        player.quote = 'Hello $, welcome!'
        ctx = _FakeCtx(['v', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertIn("'Hello Rulan, welcome!'", ctx._flat())

    async def test_write_sets_quote(self):
        from player import Player
        player = Player(name='Rulan')
        ctx = _FakeCtx(['w', 'Hello $, friend!', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertEqual(player.quote, 'Hello $, friend!')
        self.assertTrue(player.unsaved_changes)

    async def test_write_blank_leaves_unchanged(self):
        from player import Player
        player = Player(name='Rulan')
        player.quote = 'Original quote'
        ctx = _FakeCtx(['w', '', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertEqual(player.quote, 'Original quote')
        self.assertIn('No change..', ctx._flat())

    async def test_write_too_long_rejected(self):
        from player import Player
        player = Player(name='Rulan')
        long_quote = 'x' * 61
        ctx = _FakeCtx(['w', long_quote, 'y' * 10, ''], player)
        await QuoteCommand().execute(ctx)
        self.assertIn('TOO LONG!', ctx._flat())
        self.assertEqual(player.quote, 'y' * 10)

    async def test_dollar_quote_shows_preview_and_accepts(self):
        from player import Player
        player = Player(name='Rulan')
        ctx = _FakeCtx(['w', 'Hello $, welcome!', 'y', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertEqual(player.quote, 'Hello $, welcome!')
        flat = ctx._flat()
        self.assertIn('That will look like:', flat)
        self.assertIn("'Hello Rulan, welcome!'", flat)
        self.assertIn('Accept this?', flat)
        # The label, the rendered preview, and the question are sent as
        # separate lines/items, not concatenated into one string.
        self.assertNotIn("That will look like: 'Hello", flat)

    async def test_dollar_quote_preview_blank_defaults_to_accept(self):
        from player import Player
        player = Player(name='Rulan')
        ctx = _FakeCtx(['w', 'Hello $, welcome!', '', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertEqual(player.quote, 'Hello $, welcome!')

    async def test_dollar_quote_rejected_preview_reprompts(self):
        from player import Player
        player = Player(name='Rulan')
        ctx = _FakeCtx(['w', 'Bad $ placement', 'n', 'Better, $!', 'y', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertEqual(player.quote, 'Better, $!')

    async def test_dollar_quote_disconnect_during_confirm(self):
        from player import Player
        player = Player(name='Rulan')
        ctx = _FakeCtx(['w', 'Hello $, welcome!'], player)  # queue runs out at confirm
        await QuoteCommand().execute(ctx)
        self.assertIsNone(player.quote)

    async def test_no_dollar_quote_skips_preview(self):
        from player import Player
        player = Player(name='Rulan')
        ctx = _FakeCtx(['w', 'No placeholder here', ''], player)
        await QuoteCommand().execute(ctx)
        self.assertEqual(player.quote, 'No placeholder here')
        self.assertNotIn('That will look like:', ctx._flat())

    async def test_blank_at_menu_quits(self):
        from player import Player
        ctx = _FakeCtx([''], Player(name='Rulan'))
        result = await QuoteCommand().execute(ctx)
        self.assertTrue(result.success)

    async def test_disconnect_returns_cleanly(self):
        from player import Player
        ctx = _FakeCtx([], Player(name='Rulan'))
        result = await QuoteCommand().execute(ctx)
        self.assertTrue(result.success)


class _DummyClient:
    ctx = None
    virtual_location = None


class TestDescribeRoomShowsQuotes(unittest.TestCase):

    def _make_client_with_player(self, name, room, quote=None):
        from player import Player
        c = _DummyClient()
        c.room = room
        c.username = name

        class _Ctx:
            pass
        c.ctx = _Ctx()
        c.ctx.player = Player(name=name)
        c.ctx.player.quote = quote
        return c

    def test_bystander_quote_substitutes_viewer_name(self):
        s = Server('127.0.0.1', 0)
        alice = self._make_client_with_player('Alice', room=1, quote='Hello $, welcome!')
        s.clients['alice'] = alice

        viewer = self._make_client_with_player('Rulan', room=1)
        lines = s._describe_room(viewer)
        full = '\n'.join(lines)

        self.assertIn("Alice: 'Hello Rulan, welcome!'", full)

    def test_bystander_without_quote_shows_nothing_extra(self):
        s = Server('127.0.0.1', 0)
        alice = self._make_client_with_player('Alice', room=1)
        s.clients['alice'] = alice

        viewer = self._make_client_with_player('Rulan', room=1)
        lines = s._describe_room(viewer)
        full = '\n'.join(lines)

        self.assertIn('Alice', full)
        self.assertNotIn(':', full.split('Alice', 1)[1].split('\n')[0])

    def test_viewer_own_player_object_not_clobbered_by_bystanders(self):
        """Regression: the bystander-listing loop used to reassign the
        outer `player` variable (the viewer) to each other occupant in
        turn, so is_debug (read after that loop) reflected a random
        *other* player instead of the viewer's own setting."""
        from flags import PlayerFlags

        s = Server('127.0.0.1', 0)
        alice = self._make_client_with_player('Alice', room=1)
        alice.ctx.player.set_flag(PlayerFlags.DEBUG_MODE)
        s.clients['alice'] = alice

        viewer = self._make_client_with_player('Rulan', room=1)
        viewer.ctx.player.clear_flag(PlayerFlags.DEBUG_MODE)

        # Should not raise, and critically should use the viewer's own
        # is_debug (False) rather than Alice's (True) for the [DEBUG] block.
        lines = s._describe_room(viewer)
        full = '\n'.join(lines)
        self.assertNotIn('[DEBUG]', full)


if __name__ == '__main__':
    unittest.main(verbosity=2)
