"""tests/test_new_player_quit_resume.py

Regression tests for a real gap found interactively: "You may type 'quit'
at any time to abandon character creation" (NewPlayerCommand's own help
text) was only true for about half the steps -- Gender, Preferences,
Client Type, Class, Race, Attributes, Quote, Review, and the Age step's
birthday sub-prompt didn't recognize 'quit'/'q' at all (Preferences
treated it as "exit this menu and continue", Quote would have literally
set your quote to "quit").

Fixed centrally: _prompt_or_quit() (wraps ctx.prompt()) is now used by
every step. On 'quit'/'q' it asks _confirm_quit_or_continue() --
(A)bandon, (R)esume later, or (C)ontinue (a typo/change of mind: re-asks
the original question and keeps going) -- right at the point of typing
it, rather than assuming. (A)/(R) raise _CreationAbandoned, caught once
in main_flow(). Resuming persists player.id, creation_done=False, and
creation_step, plus a login credential file, so commands/connect.py's
_authenticate() can route back into main_flow() at the saved step.

Run with:
    python -m pytest tests/test_new_player_quit_resume.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from commands.new_player import (
    _CreationAbandoned, _choose_gender, _choose_quote, main_flow,
)


class _Ctx:
    def __init__(self, responses):
        self._q = list(responses)
        self.sent: list = []
        from player import Player
        self.player = Player()

    async def send(self, *args):
        self.sent.extend(args)

    async def prompt(self, prompt_text='', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestIndividualStepsRecognizeQuit(unittest.IsolatedAsyncioTestCase):
    """Spot-check a couple of the previously-unhandled steps directly."""

    async def test_gender_raises_on_quit(self):
        ctx = _Ctx(['quit'])
        with self.assertRaises(_CreationAbandoned):
            await _choose_gender(ctx)

    async def test_gender_raises_on_q(self):
        ctx = _Ctx(['q'])
        with self.assertRaises(_CreationAbandoned):
            await _choose_gender(ctx)

    async def test_gender_raises_on_disconnect(self):
        ctx = _Ctx([])   # prompt() returns None immediately
        with self.assertRaises(_CreationAbandoned):
            await _choose_gender(ctx)

    async def test_quote_step_no_longer_accepts_literal_quit_as_the_quote(self):
        """Previously the biggest surprise: any text was accepted as the
        quote, including the word 'quit' itself."""
        ctx = _Ctx(['quit'])
        with self.assertRaises(_CreationAbandoned):
            await _choose_quote(ctx)

    async def test_continue_after_quit_does_not_raise(self):
        """Typing 'quit' by mistake, then choosing (C)ontinue, must not
        abandon -- it re-asks the original question and proceeds normally."""
        ctx = _Ctx(['quit', 'C', 'f'])   # quit, continue, then answer for real
        result = await _choose_gender(ctx)
        self.assertTrue(result)
        self.assertIn('Gender set to Female.', ctx._flat())

    async def test_continue_re_asks_the_confirmation_on_a_second_quit(self):
        """quit -> continue -> quit again -> abandon: each 'quit' gets its
        own fresh confirmation, not a one-shot check."""
        ctx = _Ctx(['quit', 'C', 'quit', 'A'])
        with self.assertRaises(_CreationAbandoned) as cm:
            await _choose_gender(ctx)
        self.assertFalse(cm.exception.resume)


class TestMainFlowAbandonOrResumePrompt(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        import tempfile
        import net_common
        from pathlib import Path
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_run_dir = net_common.run_server_dir
        net_common.run_server_dir = self._tmpdir.name

        fake_user_dir = Path(self._tmpdir.name) / 'net'
        fake_user_dir.mkdir(parents=True, exist_ok=True)
        self._user_dir_patcher = patch(
            'commands.new_player.user_dir', return_value=fake_user_dir,
        )
        self._user_dir_patcher.start()

    def tearDown(self):
        import net_common
        self._user_dir_patcher.stop()
        net_common.run_server_dir = self._old_run_dir
        self._tmpdir.cleanup()

    async def test_quit_before_username_only_offers_abandon(self):
        """Quitting during Name (before player.id exists) can't offer to
        resume -- there's no identity to save a credential file under."""
        from player import Player
        player = Player()
        ctx = _Ctx(['quit', 'A'])   # typed at the Name prompt, then confirm Abandon
        result = await main_flow(ctx, player=player)
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'abandoned')
        text = ctx._flat()
        self.assertIn("Resuming later isn't possible yet", text)
        self.assertNotIn('(R)esume', text)

    async def test_quit_after_username_offers_abandon_or_resume_prompt(self):
        from player import Player
        player = Player()
        ctx = _Ctx(['Thorgar', '', 'quit'])  # name, username(blank->default), quit at prefs
        result = await main_flow(ctx, player=player)
        self.assertFalse(result.success)
        self.assertIn('(A)bandon', ctx._flat())
        self.assertIn('(R)esume later', ctx._flat())

    async def test_choosing_abandon_discards_everything(self):
        from player import Player
        player = Player()
        ctx = _Ctx(['Thorgar', '', 'quit', 'A'])
        result = await main_flow(ctx, player=player)
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'abandoned')
        self.assertIn("Feel free to try again", ctx._flat())

    async def test_choosing_continue_keeps_the_session_going(self):
        """A typo'd 'quit' at Preferences, walked back with (C)ontinue,
        must not abandon or pause -- creation proceeds to completion."""
        from player import Player
        player = Player()
        ctx = _Ctx([
            'Thorgar', '',        # name, username
            'quit', 'C', '',      # prefs: quit (mistake), continue, then accept defaults
            'm', '25', 't',       # gender, age, birthday
            '4',                  # client
            '1', '1', 'c', 'y',   # class, race, guild, accept stats
            '',                   # quote: silent
            'y',                  # accept review
            'hunter2', 'hunter2', # password
        ])
        result = await main_flow(ctx, player=player)
        self.assertTrue(result.success, msg=result.message)
        self.assertTrue(player.creation_done)

    async def test_choosing_resume_persists_paused_state(self):
        from player import Player
        player = Player()
        ctx = _Ctx([
            'Thorgar', '',       # name, username (blank -> 'thorgar')
            'quit',              # quit at Preferences (step 3)
            'R',                 # resume later
            'hunter2', 'hunter2',  # password, confirm
        ])
        result = await main_flow(ctx, player=player)
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'paused')
        self.assertFalse(player.creation_done)
        self.assertEqual(player.creation_step, 3)   # Preferences
        self.assertEqual(player.id, 'thorgar')
        self.assertIn("Log back in as 'thorgar'", ctx._flat())

        # A login credential file now exists for this username.
        from net_common import user_dir
        self.assertTrue((user_dir() / 'login-thorgar.json').exists())

    async def test_resume_step_skips_prologue_and_earlier_steps(self):
        from player import Player
        player = Player(name='Thorgar', id='thorgar')
        player.gender = None
        ctx = _Ctx(['m'])   # only Gender should be asked (resuming at step 4)
        # Not a full run-through -- just confirm the right step starts and
        # the prologue's welcome text is skipped in favor of "Welcome back".
        ctx._q = ['m', '25', 't', '', '4', '1', '1', 'c', 'y', '', 'y',
                   'hunter2', 'hunter2']
        await main_flow(ctx, player=player, resume_step=4)
        text = ctx._flat()
        self.assertIn('Welcome back, Thorgar!', text)
        self.assertNotIn("Before you begin your adventure", text)
        self.assertIn('Step 4 of 12: Gender', text)
        self.assertNotIn('Step 1 of 12: Name', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
