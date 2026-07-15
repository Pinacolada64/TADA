#!/usr/bin/env python3
"""tests/test_editplayer.py

Unit and integration tests for commands/editplayer.py.

Layers:
  1. TestFlagStatus       — _flag_status() pure function, no ctx required
  2. TestPromptInt        — _prompt_int() loop logic with scripted ctx
  3. TestMenuStructure    — menu builders return correct shape
  4. TestFlagToggleAction — toggle closures change player flag state
  5. TestAttributesAction — stat-edit closures read/write player.stats
  6. TestNamesAction      — name-edit closure and dot_leader value
  7. TestAlignmentAction  — alignment picker and dot_leader value
  8. TestStatisticsAction — age/class/guild/race edit closures
  9. TestIntegration      — full run_menu navigation with scripted responses

Run with:
    python -m pytest tests/test_editplayer.py -v
    python tests/test_editplayer.py
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

# Allow running directly: python tests/test_editplayer.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from base_classes import Alignment, Guild, PlayerClass, PlayerRace, PlayerStat
from flags import FlagDisplayTypes, PlayerFlags, new_player_default_flags
from commands.editplayer import (
    EditPlayerCommand,
    _alignment_menu,
    _attributes_menu,
    _build_main_menu,
    _flag_status,
    _flags_menu,
    _names_menu,
    _prompt_int,
    _statistics_menu,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

@dataclass
class _Settings:
    screen_columns: int = 80
    return_key: str = 'Enter'


class _MockPlayer:
    """Minimal Player-compatible stub — no net_common dependency."""

    def __init__(self, name: str = 'TestPlayer'):
        self.name              = name
        self.client_settings   = _Settings()
        self._flags: set       = set()
        self.stats             = {s: 10 for s in PlayerStat}
        self.age               = 25
        self.char_class        = PlayerClass.FIGHTER
        self.guild             = Guild.CIVILIAN
        self.char_race         = list(PlayerRace)[0]
        self.natural_alignment = Alignment.NEUTRAL
        self.current_alignment = Alignment.NEUTRAL
        self.combinations: dict = {}

    def query_flag(self, flag) -> bool:
        return flag in self._flags

    def set_flag(self, flag) -> None:
        self._flags.add(flag)

    def clear_flag(self, flag) -> None:
        self._flags.discard(flag)

    def toggle_flag(self, flag) -> None:
        if flag in self._flags:
            self._flags.discard(flag)
        else:
            self._flags.add(flag)


class _MockCtx:
    """Async context stub with a scripted prompt-response queue."""

    def __init__(self, responses: list | None = None, player=None):
        self._q: list        = list(responses or [])
        self.sent: list[str] = []
        self.player          = player or _MockPlayer()

    async def send(self, *args) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                self.sent.extend(str(x) for x in a)
            else:
                self.sent.append(str(a))

    async def prompt(self, prompt_text: str = '',
                     preamble_lines: list | None = None) -> str:
        if preamble_lines:
            await self.send(preamble_lines)
        return self._q.pop(0) if self._q else ''


# ---------------------------------------------------------------------------
# 1. _flag_status
# ---------------------------------------------------------------------------

class TestFlagStatus(unittest.TestCase):

    def setUp(self):
        self.player = _MockPlayer()

    def test_unset_flag_returns_off(self):
        self.assertEqual(_flag_status(self.player, PlayerFlags.EXPERT_MODE), 'Off')

    def test_set_flag_returns_on(self):
        self.player.set_flag(PlayerFlags.EXPERT_MODE)
        self.assertEqual(_flag_status(self.player, PlayerFlags.EXPERT_MODE), 'On')

    def test_every_flag_returns_valid_string(self):
        valid = {'On', 'Off', 'Yes', 'No'}
        for flag in PlayerFlags:
            result = _flag_status(self.player, flag)
            self.assertIn(result, valid,
                          f'{flag.name} returned unexpected {result!r}')

    def test_yesno_flags_use_yes_no(self):
        yesno = [f for f, dt, _ in new_player_default_flags
                 if dt == FlagDisplayTypes.YESNO]
        for flag in yesno:
            self.assertEqual(_flag_status(self.player, flag), 'No')
            self.player.set_flag(flag)
            self.assertEqual(_flag_status(self.player, flag), 'Yes')
            self.player.clear_flag(flag)

    def test_onoff_flags_use_on_off(self):
        onoff = [f for f, dt, _ in new_player_default_flags
                 if dt == FlagDisplayTypes.ONOFF]
        self.assertTrue(onoff, 'No ONOFF flags found in new_player_default_flags')
        for flag in onoff:
            self.assertIn(_flag_status(self.player, flag), {'On', 'Off'})


# ---------------------------------------------------------------------------
# 2. _prompt_int
# ---------------------------------------------------------------------------

class TestPromptInt(unittest.IsolatedAsyncioTestCase):

    async def test_valid_input_in_range(self):
        ctx = _MockCtx(responses=['30'])
        self.assertEqual(await _prompt_int(ctx, 'Age', 25, 15, 50), 30)

    async def test_empty_input_returns_none(self):
        ctx = _MockCtx(responses=[''])
        self.assertIsNone(await _prompt_int(ctx, 'Age', 25, 15, 50))

    async def test_boundary_low_accepted(self):
        ctx = _MockCtx(responses=['15'])
        self.assertEqual(await _prompt_int(ctx, 'Age', 25, 15, 50), 15)

    async def test_boundary_high_accepted(self):
        ctx = _MockCtx(responses=['50'])
        self.assertEqual(await _prompt_int(ctx, 'Age', 25, 15, 50), 50)

    async def test_below_range_loops_then_cancel(self):
        ctx = _MockCtx(responses=['5', ''])
        self.assertIsNone(await _prompt_int(ctx, 'Age', 25, 15, 50))

    async def test_above_range_loops_then_cancel(self):
        ctx = _MockCtx(responses=['99', ''])
        self.assertIsNone(await _prompt_int(ctx, 'Age', 25, 15, 50))

    async def test_non_numeric_loops_then_cancel(self):
        ctx = _MockCtx(responses=['banana', ''])
        self.assertIsNone(await _prompt_int(ctx, 'Age', 25, 15, 50))

    async def test_invalid_then_valid_returns_value(self):
        ctx = _MockCtx(responses=['0', '30'])
        self.assertEqual(await _prompt_int(ctx, 'Age', 25, 15, 50), 30)

    async def test_error_message_sent_on_bad_value(self):
        ctx = _MockCtx(responses=['abc', ''])
        await _prompt_int(ctx, 'Age', 25, 15, 50)
        self.assertIn('number', ' '.join(ctx.sent).lower())


# ---------------------------------------------------------------------------
# 3. Menu structure
# ---------------------------------------------------------------------------

class TestMenuStructure(unittest.TestCase):

    def setUp(self):
        self.ctx = _MockCtx()

    # -- main menu --

    def test_main_menu_has_twelve_selectable_items(self):
        self.assertEqual(len(_build_main_menu(self.ctx).selectable), 12)

    def test_main_menu_contains_expected_labels(self):
        labels = {i.text for i in _build_main_menu(self.ctx).selectable}
        for name in ('Alignment', 'Attributes', 'Flags/Counters',
                     'Statistics', 'Character Names', 'Combinations',
                     'Hit Points', 'Money', 'Weapons'):
            self.assertIn(name, labels, f'{name!r} missing from main menu')

    def test_all_main_menu_items_have_action_or_submenu(self):
        for item in _build_main_menu(self.ctx).selectable:
            self.assertTrue(item.action is not None or item.submenu is not None,
                            f'{item.text!r} has neither action nor submenu')

    def test_main_menu_shortcuts_unique(self):
        seen: list = []
        for item in _build_main_menu(self.ctx).selectable:
            for sc in item.shortcuts:
                self.assertNotIn(sc, seen, f'Duplicate shortcut {sc!r} in main menu')
                seen.append(sc)

    # -- attributes menu --

    def test_attributes_menu_covers_every_stat(self):
        labels = {i.text for i in _attributes_menu(self.ctx).selectable}
        for stat in PlayerStat:
            self.assertIn(stat.value, labels,
                          f'PlayerStat.{stat.name} ({stat.value!r}) missing')

    def test_attributes_menu_every_item_has_dot_leader(self):
        for item in _attributes_menu(self.ctx).selectable:
            self.assertIsNotNone(item.dot_leader_handler,
                                 f'{item.text!r} missing dot_leader_handler')

    # -- flags menu --

    def test_flags_menu_section_headers_present(self):
        headers = {i.text for i in _flags_menu(self.ctx).menu_items if i.is_header}
        self.assertIn('— Option Toggles —',  headers)
        self.assertIn('— Player Status —',   headers)
        self.assertIn('— Game Objectives —', headers)

    def test_flags_menu_contains_key_flags(self):
        labels = {i.text for i in _flags_menu(self.ctx).selectable}
        for flag in (PlayerFlags.EXPERT_MODE, PlayerFlags.HOURGLASS,
                     PlayerFlags.MORE_PROMPT, PlayerFlags.ADMIN,
                     PlayerFlags.HAS_HORSE, PlayerFlags.WRAITH_KING_ALIVE,
                     PlayerFlags.SPUR_ALIVE):
            self.assertIn(flag.value, labels, f'{flag.name} missing from flags menu')

    def test_flags_menu_shortcuts_unique(self):
        seen: list = []
        for item in _flags_menu(self.ctx).selectable:
            for sc in item.shortcuts:
                self.assertNotIn(sc, seen,
                                 f'Duplicate shortcut {sc!r} in flags menu')
                seen.append(sc)

    def test_flags_menu_every_item_has_dot_leader(self):
        for item in _flags_menu(self.ctx).selectable:
            self.assertIsNotNone(item.dot_leader_handler,
                                 f'{item.text!r} missing dot_leader_handler')

    # -- names menu --

    def test_names_menu_has_expected_items(self):
        labels = {i.text for i in _names_menu(self.ctx).selectable}
        for name in ('Player Name', 'Ally 1', 'Ally 2', 'Ally 3', 'Horse'):
            self.assertIn(name, labels)

    # -- statistics menu --

    def test_statistics_editable_fields_have_dot_leaders(self):
        sel = {i.text: i for i in _statistics_menu(self.ctx).selectable}
        for field_name in ('Age', 'Class', 'Guild', 'Race'):
            self.assertIn(field_name, sel)
            self.assertIsNotNone(sel[field_name].dot_leader_handler,
                                 f'{field_name!r} missing dot_leader_handler')


# ---------------------------------------------------------------------------
# 4. Flag toggle action
# ---------------------------------------------------------------------------

class TestFlagToggleAction(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.ctx = _MockCtx()

    async def _toggle(self, flag: PlayerFlags) -> None:
        menu = _flags_menu(self.ctx)
        item = next(i for i in menu.selectable if i.text == flag.value)
        result = item.action(self.ctx)
        if asyncio.iscoroutine(result):
            await result

    async def test_toggle_off_to_on(self):
        self.assertFalse(self.ctx.player.query_flag(PlayerFlags.EXPERT_MODE))
        await self._toggle(PlayerFlags.EXPERT_MODE)
        self.assertTrue(self.ctx.player.query_flag(PlayerFlags.EXPERT_MODE))

    async def test_toggle_on_to_off(self):
        self.ctx.player.set_flag(PlayerFlags.EXPERT_MODE)
        await self._toggle(PlayerFlags.EXPERT_MODE)
        self.assertFalse(self.ctx.player.query_flag(PlayerFlags.EXPERT_MODE))

    async def test_toggle_sends_flag_name_and_status(self):
        await self._toggle(PlayerFlags.EXPERT_MODE)
        combined = ' '.join(self.ctx.sent)
        self.assertIn('Expert Mode', combined)
        self.assertIn('On', combined)

    async def test_double_toggle_restores_state(self):
        before = self.ctx.player.query_flag(PlayerFlags.HOURGLASS)
        await self._toggle(PlayerFlags.HOURGLASS)
        await self._toggle(PlayerFlags.HOURGLASS)
        self.assertEqual(self.ctx.player.query_flag(PlayerFlags.HOURGLASS), before)

    async def test_every_flag_item_toggles_without_error(self):
        for item in _flags_menu(self.ctx).selectable:
            result = item.action(self.ctx)
            if asyncio.iscoroutine(result):
                await result


# ---------------------------------------------------------------------------
# 5. Attributes action
# ---------------------------------------------------------------------------

class TestAttributesAction(unittest.IsolatedAsyncioTestCase):

    async def _invoke(self, ctx, stat: PlayerStat):
        menu = _attributes_menu(ctx)
        item = next(i for i in menu.selectable if i.text == stat.value)
        result = item.action(ctx)
        if asyncio.iscoroutine(result):
            await result

    async def test_valid_input_updates_stat(self):
        stat = list(PlayerStat)[0]
        ctx = _MockCtx(responses=['15'])
        await self._invoke(ctx, stat)
        self.assertEqual(ctx.player.stats[stat], 15)

    async def test_blank_input_leaves_stat_unchanged(self):
        stat = list(PlayerStat)[0]
        ctx = _MockCtx(responses=[''])
        original = ctx.player.stats[stat]
        await self._invoke(ctx, stat)
        self.assertEqual(ctx.player.stats[stat], original)

    async def test_energy_accepts_25(self):
        ctx = _MockCtx(responses=['25'])
        await self._invoke(ctx, PlayerStat.EGY)
        self.assertEqual(ctx.player.stats[PlayerStat.EGY], 25)

    async def test_energy_rejects_above_25(self):
        ctx = _MockCtx(responses=['26', ''])
        original = ctx.player.stats[PlayerStat.EGY]
        await self._invoke(ctx, PlayerStat.EGY)
        self.assertEqual(ctx.player.stats[PlayerStat.EGY], original)

    async def test_dot_leader_shows_current_value(self):
        ctx = _MockCtx()
        ctx.player.stats[PlayerStat.CON] = 14
        menu = _attributes_menu(ctx)
        item = next(i for i in menu.selectable if i.text == PlayerStat.CON.value)
        self.assertEqual(item.dot_leader_handler(ctx), '14')


# ---------------------------------------------------------------------------
# 6. Names action
# ---------------------------------------------------------------------------

class TestNamesAction(unittest.IsolatedAsyncioTestCase):

    async def _invoke_name(self, ctx):
        menu = _names_menu(ctx)
        item = next(i for i in menu.selectable if i.text == 'Player Name')
        result = item.action(ctx)
        if asyncio.iscoroutine(result):
            await result

    async def test_new_name_applied(self):
        ctx = _MockCtx(responses=['Railbender'])
        await self._invoke_name(ctx)
        self.assertEqual(ctx.player.name, 'Railbender')

    async def test_blank_input_preserves_name(self):
        ctx = _MockCtx(responses=[''])
        ctx.player.name = 'OldName'
        await self._invoke_name(ctx)
        self.assertEqual(ctx.player.name, 'OldName')

    async def test_dot_leader_shows_current_name(self):
        ctx = _MockCtx()
        ctx.player.name = 'Pinacolada'
        menu = _names_menu(ctx)
        item = next(i for i in menu.selectable if i.text == 'Player Name')
        self.assertEqual(item.dot_leader_handler(ctx), 'Pinacolada')


# ---------------------------------------------------------------------------
# 7. Alignment action
# ---------------------------------------------------------------------------

class TestAlignmentAction(unittest.IsolatedAsyncioTestCase):

    async def _invoke(self, ctx, label: str):
        menu = _alignment_menu(ctx)
        item = next(i for i in menu.selectable if i.text == label)
        result = item.action(ctx)
        if asyncio.iscoroutine(result):
            await result

    async def test_pick_natural_alignment(self):
        ctx = _MockCtx(responses=['1'])
        await self._invoke(ctx, 'Natural Alignment')
        self.assertEqual(ctx.player.natural_alignment, list(Alignment)[0])

    async def test_pick_current_alignment_second_option(self):
        options = list(Alignment)
        ctx = _MockCtx(responses=['2'])
        await self._invoke(ctx, 'Current Alignment')
        self.assertEqual(ctx.player.current_alignment, options[1])

    async def test_blank_input_leaves_unchanged(self):
        ctx = _MockCtx(responses=[''])
        ctx.player.natural_alignment = Alignment.NEUTRAL
        await self._invoke(ctx, 'Natural Alignment')
        self.assertEqual(ctx.player.natural_alignment, Alignment.NEUTRAL)

    async def test_dot_leader_reflects_current(self):
        ctx = _MockCtx()
        ctx.player.current_alignment = Alignment.EVIL
        menu = _alignment_menu(ctx)
        item = next(i for i in menu.selectable if i.text == 'Current Alignment')
        self.assertIn('Evil', item.dot_leader_handler(ctx))


# ---------------------------------------------------------------------------
# 8. Statistics action
# ---------------------------------------------------------------------------

class TestStatisticsAction(unittest.IsolatedAsyncioTestCase):

    async def _invoke(self, ctx, label: str):
        menu = _statistics_menu(ctx)
        item = next(i for i in menu.selectable if i.text == label)
        result = item.action(ctx)
        if asyncio.iscoroutine(result):
            await result

    async def test_edit_age_valid(self):
        ctx = _MockCtx(responses=['30'])
        await self._invoke(ctx, 'Age')
        self.assertEqual(ctx.player.age, 30)

    async def test_edit_age_cancel_unchanged(self):
        ctx = _MockCtx(responses=[''])
        ctx.player.age = 25
        await self._invoke(ctx, 'Age')
        self.assertEqual(ctx.player.age, 25)

    async def test_edit_class(self):
        ctx = _MockCtx(responses=['1'])
        await self._invoke(ctx, 'Class')
        self.assertEqual(ctx.player.char_class, list(PlayerClass)[0])

    async def test_edit_class_non_numeric_unchanged(self):
        ctx = _MockCtx(responses=['abc'])
        original = ctx.player.char_class
        await self._invoke(ctx, 'Class')
        self.assertEqual(ctx.player.char_class, original)

    async def test_edit_guild(self):
        ctx = _MockCtx(responses=['1'])
        await self._invoke(ctx, 'Guild')
        self.assertEqual(ctx.player.guild, list(Guild)[0])

    async def test_edit_race(self):
        ctx = _MockCtx(responses=['1'])
        await self._invoke(ctx, 'Race')
        self.assertEqual(ctx.player.char_race, list(PlayerRace)[0])

    async def test_age_dot_leader(self):
        ctx = _MockCtx()
        ctx.player.age = 33
        menu = _statistics_menu(ctx)
        item = next(i for i in menu.selectable if i.text == 'Age')
        self.assertEqual(item.dot_leader_handler(ctx), '33')

    async def test_edit_birthday_numeric_month(self):
        ctx = _MockCtx(responses=['09-16'])
        await self._invoke(ctx, 'Birthday')
        self.assertEqual((ctx.player.birthday.month, ctx.player.birthday.day), (9, 16))

    async def test_edit_birthday_month_name_prefix(self):
        """Ryan: EditPlayer's birthday editor should accept the same
        month-name-prefix input as character creation's."""
        ctx = _MockCtx(responses=['Sep-16'])
        await self._invoke(ctx, 'Birthday')
        self.assertEqual((ctx.player.birthday.month, ctx.player.birthday.day), (9, 16))

    async def test_edit_birthday_full_month_name(self):
        ctx = _MockCtx(responses=['September-16'])
        await self._invoke(ctx, 'Birthday')
        self.assertEqual((ctx.player.birthday.month, ctx.player.birthday.day), (9, 16))

    async def test_edit_birthday_invalid_month_name_rejected(self):
        ctx = _MockCtx(responses=['xyz-16'])
        original = getattr(ctx.player, 'birthday', None)
        await self._invoke(ctx, 'Birthday')
        self.assertEqual(getattr(ctx.player, 'birthday', None), original)
        self.assertIn('Invalid date', ' '.join(ctx.sent))

    async def test_edit_birthday_blank_cancels(self):
        ctx = _MockCtx(responses=[''])
        original = getattr(ctx.player, 'birthday', None)
        await self._invoke(ctx, 'Birthday')
        self.assertEqual(getattr(ctx.player, 'birthday', None), original)


# ---------------------------------------------------------------------------
# 9. Integration — full run_menu navigation
# ---------------------------------------------------------------------------

class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Drive EditPlayerCommand.execute() end-to-end with a scripted ctx.

    Each call to ctx.prompt() pops one item from the response queue.
    navigate_menu calls ctx.prompt('Choice', ...) after every menu display.
    Inline action prompts (_prompt_int, list pickers) also consume items.

    Flags/Counters is item 6 in the main menu.
    Expert Mode is item 1 in the flags menu.

    Scripted navigation to toggle Expert Mode and return:
        Main displayed   → '6'  → push Flags submenu
        Flags displayed  → '1'  → run toggle action
        Flags displayed  → ''   → pop Flags submenu
        Main displayed   → ''   → pop main menu, done
    """

    async def test_immediate_exit_returns_success(self):
        result = await EditPlayerCommand().execute(_MockCtx(responses=['']))
        self.assertTrue(result.success)

    async def test_command_produces_output(self):
        ctx = _MockCtx(responses=[''])
        await EditPlayerCommand().execute(ctx)
        self.assertGreater(len(ctx.sent), 0)

    async def test_toggle_expert_mode_via_navigation(self):
        ctx = _MockCtx(responses=['6', '1', '', ''])
        self.assertFalse(ctx.player.query_flag(PlayerFlags.EXPERT_MODE))
        await EditPlayerCommand().execute(ctx)
        self.assertTrue(ctx.player.query_flag(PlayerFlags.EXPERT_MODE))

    async def test_enter_submenu_then_exit(self):
        # Enter Attributes (item 3), exit immediately, exit main
        ctx = _MockCtx(responses=['3', '', ''])
        result = await EditPlayerCommand().execute(ctx)
        self.assertTrue(result.success)

    async def test_edit_age_via_navigation(self):
        # Main → Statistics (11) → Age (1) → 30 → up → up
        ctx = _MockCtx(responses=['11', '1', '30', '', ''])
        await EditPlayerCommand().execute(ctx)
        self.assertEqual(ctx.player.age, 30)

    async def test_toggle_twice_restores_flag(self):
        player = _MockPlayer()
        for _ in range(2):
            ctx = _MockCtx(responses=['6', '1', '', ''], player=player)
            await EditPlayerCommand().execute(ctx)
        self.assertFalse(player.query_flag(PlayerFlags.EXPERT_MODE))

    async def test_unknown_choice_does_not_crash(self):
        # 'zzz' is not a valid shortcut; menu re-prompts, then '' exits
        ctx = _MockCtx(responses=['zzz', ''])
        result = await EditPlayerCommand().execute(ctx)
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.WARNING,
                        format='%(levelname)s %(name)s: %(message)s')
    unittest.main()
