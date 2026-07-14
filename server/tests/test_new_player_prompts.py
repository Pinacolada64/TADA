"""tests/test_new_player_prompts.py

Regression tests for three bugs found while running through character
creation interactively:

  - _choose_class()'s non-expert overview enumerated starting at 1 (instead
    of the default 0), so the displayed number for a class was off by one
    from its own description -- e.g. "1. Wizard" showed the *next* class's
    (Druid's) description, and typing the displayed number selected the
    wrong class relative to what was shown.
  - _choose_age()/_choose_name()'s 'R' (random) option accepted the first
    generated value outright instead of looping with a y/n confirmation
    like the established random-password pattern (_choose_password(),
    mirroring BASIC line 3172: generate, show, ask, loop until accepted).
  - Both were fixed by delegating to tada_utilities.input_yes_no(), which
    is also covered directly here (default-driven blank-Enter behavior,
    and returning None instead of crashing on disconnect).

Also covers a follow-up change: username is now chosen *after* the
character name (not before), and defaults to it (letters/numbers only)
so blank Enter accepts it -- username is a separate identifier intended
for a planned CommodoreServer.com account link, not the in-world name.

Run with:
    python -m pytest tests/test_new_player_prompts.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from commands.new_player import _choose_age, _choose_class, _choose_name, _choose_username, main_flow
from tada_utilities import input_yes_no


class _FakePlayer:
    is_expert = False
    gender    = 'male'
    age       = None
    birthday  = None
    name      = None


class _FakeCtx:
    def __init__(self, responses):
        self._q = list(responses)
        self.sent: list = []
        self.player = _FakePlayer()

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        out = []
        for item in self.sent:
            if isinstance(item, (list, tuple)):
                out.extend(str(x) for x in item)
            else:
                out.append(str(item))
        return '\n'.join(out)


class TestInputYesNo(unittest.IsolatedAsyncioTestCase):

    async def test_explicit_yes(self):
        ctx = _FakeCtx(['y'])
        self.assertTrue(await input_yes_no(ctx, 'Sure?'))

    async def test_explicit_no(self):
        ctx = _FakeCtx(['n'])
        self.assertFalse(await input_yes_no(ctx, 'Sure?'))

    async def test_blank_without_default_reprompts(self):
        ctx = _FakeCtx(['', 'y'])
        self.assertTrue(await input_yes_no(ctx, 'Sure?'))

    async def test_blank_with_default_true(self):
        ctx = _FakeCtx([''])
        self.assertTrue(await input_yes_no(ctx, 'Sure?', default=True))

    async def test_blank_with_default_false(self):
        ctx = _FakeCtx([''])
        self.assertFalse(await input_yes_no(ctx, 'Sure?', default=False))

    async def test_disconnect_returns_none(self):
        ctx = _FakeCtx([])
        self.assertIsNone(await input_yes_no(ctx, 'Sure?'))


class TestChooseClassMenu(unittest.IsolatedAsyncioTestCase):

    async def test_first_class_description_matches_first_class(self):
        ctx = _FakeCtx(['1'])
        await _choose_class(ctx)
        text = ctx._flat()
        # "1. Wizard" must be followed by Wizard's own description on the
        # same line, not Druid's (the class after it).
        self.assertIn('1. Wizard', text)
        wizard_line = next(l for l in text.splitlines() if l.strip().startswith('1. Wizard'))
        self.assertIn('arcane magic', wizard_line)
        self.assertNotIn('Guardians of nature', wizard_line)

    async def test_selecting_displayed_number_picks_matching_class(self):
        ctx = _FakeCtx(['1'])
        await _choose_class(ctx)
        self.assertEqual(ctx.player.char_class, 'Wizard')

    async def test_second_entry_selects_second_class(self):
        ctx = _FakeCtx(['2'])
        await _choose_class(ctx)
        self.assertEqual(ctx.player.char_class, 'Druid')

    async def test_selection_stores_real_enum_member_not_bare_string(self):
        """Regression test for a real bug found live: char_class used to be
        stored as class_names[sel-1] (a bare .value string), not the real
        PlayerClass member -- StrEnum value-equality masked this for most
        comparisons, but a bare string has no .name attribute, so
        _roll_stats()'s "Applying X / Y attribute bonuses" report silently
        dropped the class name from every message (getattr(char_class,
        'name', None) always came back None). Same bug class already
        fixed for char_race earlier."""
        from base_classes import PlayerClass
        ctx = _FakeCtx(['1'])
        await _choose_class(ctx)
        self.assertIs(ctx.player.char_class, PlayerClass.WIZARD)
        self.assertEqual(ctx.player.char_class.name, 'WIZARD')

    async def test_random_class_example_is_labeled_and_boxed(self):
        """Ryan: the random class shown in the non-expert overview should
        be clearly marked as an example, with its description set apart
        in a tip box rather than blending into the surrounding text."""
        ctx = _FakeCtx(['1'])
        await _choose_class(ctx)
        text = ctx._flat()
        self.assertIn('this is an example', text.lower())
        self.assertIn('Tip', text)


class TestChooseAgeRandomConfirm(unittest.IsolatedAsyncioTestCase):

    async def test_reroll_until_accepted(self):
        # reject, reject, accept, then "today" for birthday
        ctx = _FakeCtx(['r', 'n', 'n', 'y', 't'])
        ok = await _choose_age(ctx)
        self.assertTrue(ok)
        self.assertIsNotNone(ctx.player.age)
        self.assertIn('Accept?', ctx._flat())


class TestChooseNameRandomConfirm(unittest.IsolatedAsyncioTestCase):

    async def test_reroll_until_accepted(self):
        ctx = _FakeCtx(['r', 'n', 'y'])
        ok = await _choose_name(ctx)
        self.assertTrue(ok)
        self.assertIsNotNone(ctx.player.name)


class TestChooseUsernameDefaultsToCharacterName(unittest.IsolatedAsyncioTestCase):
    """Username now comes after the character name and defaults to it --
    a separate account identifier (for a planned CommodoreServer.com link),
    but blank Enter accepts the sanitized character name."""

    def setUp(self):
        # Patches commands.new_player.user_dir directly (not net_common's
        # run_server_dir global) because some test modules elsewhere in the
        # suite pop and re-import net_common at collection time to dodge
        # *other* files' stale sys.modules stubs, leaving this module
        # holding a second, divergent copy -- see the identical note in
        # tests/test_connect.py's TestConnectAuthentication.setUp().
        import tempfile
        from pathlib import Path
        self._tmpdir = tempfile.TemporaryDirectory()
        fake_user_dir = Path(self._tmpdir.name) / 'net'
        fake_user_dir.mkdir(parents=True, exist_ok=True)
        self._user_dir_patcher = patch(
            'commands.new_player.user_dir', return_value=fake_user_dir,
        )
        self._user_dir_patcher.start()

    def tearDown(self):
        self._user_dir_patcher.stop()
        self._tmpdir.cleanup()

    async def test_blank_accepts_sanitized_character_name(self):
        ctx = _FakeCtx([''])
        username = await _choose_username(ctx, default='Dawn Kingsley')
        self.assertEqual(username, 'dawnkingsley')

    async def test_explicit_username_overrides_default(self):
        ctx = _FakeCtx(['someoneelse'])
        username = await _choose_username(ctx, default='Dawn Kingsley')
        self.assertEqual(username, 'someoneelse')

    async def test_short_or_taken_default_falls_back_to_prompting(self):
        # 'Al' sanitizes to 'al' -- too short (<3) to offer as a default,
        # so blank input should keep re-prompting instead of accepting it.
        ctx = _FakeCtx(['', 'validname'])
        username = await _choose_username(ctx, default='Al')
        self.assertEqual(username, 'validname')


class TestMainFlowOrdering(unittest.IsolatedAsyncioTestCase):
    """End-to-end: username comes right after the character name (not at
    the very end), and defaults to it. Password stays at the very end,
    right before persisting."""

    def setUp(self):
        import tempfile
        import net_common
        from pathlib import Path
        self._tmpdir = tempfile.TemporaryDirectory()

        # Player.save()/_json_path() re-import net_common at call time (a
        # local `import net_common` inside the method), so this global is
        # safe to set directly -- it's read fresh on every call, unlike a
        # `from net_common import X` binding captured once at another
        # module's own import time.
        self._old_run_dir = net_common.run_server_dir
        net_common.run_server_dir = self._tmpdir.name

        # commands.new_player's credential-file writes go through a `from
        # net_common import user_dir` binding instead, which *isn't* safe
        # against the module-duplication some other test files cause (see
        # the note in test_connect.py's TestConnectAuthentication.setUp())
        # -- patch it directly so this test can't touch the real project's
        # run/server/net/ directory regardless of full-suite ordering.
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

    async def test_full_flow_username_defaults_to_character_name(self):
        from player import Player

        stub   = Player()   # stands in for the pre-login GuestPlayer
        player = Player()

        class Ctx:
            def __init__(self, responses):
                self._q = list(responses)
                self.player = stub
                self.sent = []

            async def send(self, *args):
                self.sent.extend(args)

            async def prompt(self, prompt_text='', preamble_lines=None):
                return self._q.pop(0) if self._q else None

        ctx = Ctx([
            'Thorgar',     # character name
            '',            # username: blank -> defaults to character name
            '',            # prefs: accept defaults
            'm',           # gender
            '25',          # age
            't',           # birthday: today
            '1',           # class
            '1',           # race
            'c',           # guild: Civilian
            'y',           # accept stats
            '',            # quote: blank -> silent
            'y',           # accept summary
            'pass1234',    # password
            'pass1234',    # confirm password
        ])

        result = await main_flow(ctx, player=player)
        self.assertTrue(result.success, msg=result.message)
        self.assertEqual(player.name, 'Thorgar')
        self.assertEqual(player.id, 'thorgar')
        self.assertEqual(result.data['username'], 'thorgar')

    async def test_step_headings_show_progress(self):
        """Each step sends a 'Step N of TOTAL: <title>' heading so the
        player knows how far along they are."""
        from player import Player

        stub   = Player()
        player = Player()

        class Ctx:
            def __init__(self, responses):
                self._q = list(responses)
                self.player = stub
                self.sent = []

            async def send(self, *args):
                self.sent.extend(args)

            async def prompt(self, prompt_text='', preamble_lines=None):
                return self._q.pop(0) if self._q else None

        ctx = Ctx([
            'Thorgar', '', '', 'm', '25', 't', '1', '1', 'c', 'y',
            '', 'y', 'pass1234', 'pass1234',
        ])
        await main_flow(ctx, player=player)

        flat = '\n'.join(str(x) for x in ctx.sent)
        self.assertIn('Step 1 of 11: Name', flat)
        self.assertIn('Step 2 of 11: Username', flat)
        self.assertIn('Step 3 of 11: Preferences', flat)
        self.assertIn('Step 4 of 11: Gender', flat)
        self.assertIn('Step 5 of 11: Age', flat)
        self.assertIn('Step 11 of 11: Review', flat)
        # Name is asked before Gender/Age/class/race/etc. in the actual
        # send/prompt call order, not just the heading text.
        name_idx   = flat.index('Step 1 of 11: Name')
        gender_idx = flat.index('Step 4 of 11: Gender')
        self.assertLess(name_idx, gender_idx)

    async def test_preferences_shows_orientation_blurb(self):
        """Preferences now runs right after Username, with a one-time
        explanatory blurb reassuring newbies these aren't locked in."""
        from player import Player

        stub   = Player()
        player = Player()

        class Ctx:
            def __init__(self, responses):
                self._q = list(responses)
                self.player = stub
                self.sent = []

            async def send(self, *args):
                self.sent.extend(args)

            async def prompt(self, prompt_text='', preamble_lines=None):
                return self._q.pop(0) if self._q else None

        ctx = Ctx([
            'Thorgar', '', '', 'm', '25', 't', '1', '1', 'c', 'y',
            '', 'y', 'pass1234', 'pass1234',
        ])
        await main_flow(ctx, player=player)

        flat = '\n'.join(str(x) for x in ctx.sent)
        self.assertIn('change any of them later with the PREFS command', flat)


if __name__ == '__main__':
    unittest.main(verbosity=2)
