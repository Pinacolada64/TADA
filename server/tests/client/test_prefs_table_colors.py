"""tests/client/test_prefs_table_colors.py

Regression/coverage for commands/prefs.py's 'A' (Table Colors) picker,
which sets client_settings.table_colors (a table.ZebraColors) -- consumed
by any command that renders a zebra-striped table.Table (e.g. WHEREAT's
#population summary).
"""
from __future__ import annotations

import unittest

from table import DEFAULT_ZEBRA_COLORS, ZEBRA_COLOR_PRESETS, ZebraColors
from player import Player
from commands.prefs import _pick_table_colors

# 'A' menu's option number for 'Custom (pick each stripe)' -- one past the
# last named preset, matching _pick_table_colors()'s own custom_num.
_CUSTOM = str(len(ZEBRA_COLOR_PRESETS) + 1)


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
        if prompt_text:
            self.sent.append(prompt_text)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestPickTableColorsDefault(unittest.IsolatedAsyncioTestCase):

    async def test_default_option_clears_override(self):
        player = Player()
        player.client_settings.table_colors = ZebraColors(stripe_a='green')
        ctx = _FakeCtx(['1', 'y'], player)
        await _pick_table_colors(ctx)
        self.assertIsNone(player.client_settings.table_colors)

    async def test_blank_leaves_existing_override_untouched(self):
        player = Player()
        player.client_settings.table_colors = ZebraColors(stripe_a='green')
        ctx = _FakeCtx([''], player)
        await _pick_table_colors(ctx)
        self.assertEqual(player.client_settings.table_colors.stripe_a, 'green')


class TestPickTableColorsNamedPresets(unittest.IsolatedAsyncioTestCase):

    async def test_picking_a_named_preset_stores_its_colors(self):
        player = Player()
        idx = next(i for i, (name, _) in enumerate(ZEBRA_COLOR_PRESETS, 1)
                   if name == 'Ocean')
        ctx = _FakeCtx([str(idx), 'y'], player)
        await _pick_table_colors(ctx)
        tc = player.client_settings.table_colors
        self.assertEqual((tc.stripe_a, tc.stripe_b), ('blue', 'light_blue'))

    async def test_picking_a_named_preset_stores_a_copy_not_the_shared_instance(self):
        player = Player()
        idx = next(i for i, (name, _) in enumerate(ZEBRA_COLOR_PRESETS, 1)
                   if name == 'Fire')
        ctx = _FakeCtx([str(idx), 'y'], player)
        await _pick_table_colors(ctx)
        tc = player.client_settings.table_colors
        preset_tc = dict(ZEBRA_COLOR_PRESETS)['Fire']
        self.assertIsNot(tc, preset_tc)
        tc.stripe_a = 'mutated'
        self.assertEqual(preset_tc.stripe_a, 'red')  # preset itself untouched

    async def test_out_of_range_number_leaves_scheme_unchanged(self):
        player = Player()
        player.client_settings.table_colors = ZebraColors(stripe_a='green')
        ctx = _FakeCtx([str(len(ZEBRA_COLOR_PRESETS) + 50)], player)
        await _pick_table_colors(ctx)
        self.assertEqual(player.client_settings.table_colors.stripe_a, 'green')


class TestPickTableColorsCustom(unittest.IsolatedAsyncioTestCase):

    async def test_custom_walks_both_stripes_in_order(self):
        player = Player()
        ctx = _FakeCtx([_CUSTOM, '1', '2', 'y'], player)
        await _pick_table_colors(ctx)
        tc = player.client_settings.table_colors
        self.assertIsInstance(tc, ZebraColors)
        self.assertNotEqual(
            (tc.stripe_a, tc.stripe_b),
            (DEFAULT_ZEBRA_COLORS.stripe_a, DEFAULT_ZEBRA_COLORS.stripe_b),
        )

    async def test_custom_blank_field_keeps_its_current_value(self):
        player = Player()
        player.client_settings.table_colors = ZebraColors(stripe_a='purple')
        ctx = _FakeCtx([_CUSTOM, '', '', 'y'], player)
        await _pick_table_colors(ctx)
        tc = player.client_settings.table_colors
        self.assertEqual(tc.stripe_a, 'purple')
        self.assertEqual(tc.stripe_b, DEFAULT_ZEBRA_COLORS.stripe_b)

    async def test_custom_out_of_range_number_leaves_field_unchanged(self):
        player = Player()
        ctx = _FakeCtx([_CUSTOM, '999', '', 'y'], player)
        await _pick_table_colors(ctx)
        tc = player.client_settings.table_colors
        self.assertEqual(tc.stripe_a, DEFAULT_ZEBRA_COLORS.stripe_a)

    async def test_custom_starts_from_a_copy_not_the_shared_default(self):
        """Editing one stripe via Custom must never mutate the shared
        module-level DEFAULT_ZEBRA_COLORS instance itself."""
        player = Player()
        ctx = _FakeCtx([_CUSTOM, '1', '', 'y'], player)
        await _pick_table_colors(ctx)
        self.assertEqual(DEFAULT_ZEBRA_COLORS.stripe_a, 'white')

    async def test_cancel_mid_walk_returns_without_saving(self):
        player = Player()
        ctx = _FakeCtx([_CUSTOM], player)
        await _pick_table_colors(ctx)
        self.assertIsNone(player.client_settings.table_colors)


class TestPickTableColorsConfirmLoop(unittest.IsolatedAsyncioTestCase):

    async def test_n_does_not_save_and_reprompts_the_picker(self):
        player = Player()
        idx_ocean = next(i for i, (name, _) in enumerate(ZEBRA_COLOR_PRESETS, 1)
                          if name == 'Ocean')
        idx_forest = next(i for i, (name, _) in enumerate(ZEBRA_COLOR_PRESETS, 1)
                           if name == 'Forest')
        ctx = _FakeCtx([str(idx_ocean), 'n', str(idx_forest), 'y'], player)
        await _pick_table_colors(ctx)
        tc = player.client_settings.table_colors
        self.assertEqual(tc.stripe_a, 'green')

    async def test_asks_satisfactory_question_before_saving(self):
        player = Player()
        ctx = _FakeCtx(['1', 'y'], player)
        await _pick_table_colors(ctx)
        self.assertIn('Are these colors satisfactory?', ctx._flat())

    async def test_blank_on_confirm_does_not_save(self):
        player = Player()
        player.client_settings.table_colors = ZebraColors(stripe_a='purple')
        idx_ocean = next(i for i, (name, _) in enumerate(ZEBRA_COLOR_PRESETS, 1)
                          if name == 'Ocean')
        ctx = _FakeCtx([str(idx_ocean)], player)
        await _pick_table_colors(ctx)
        self.assertEqual(player.client_settings.table_colors.stripe_a, 'purple')


class TestPickTableColorsPreview(unittest.IsolatedAsyncioTestCase):

    async def test_shows_live_mock_table_using_current_scheme(self):
        # Regression: mirrors _pick_menu_colors()'s live-preview
        # convention -- the preview renders a real table.Table with the
        # candidate scheme's colors, not a hand-built approximation.
        player = Player()
        player.client_settings.table_colors = ZebraColors(stripe_a='green')
        ctx = _FakeCtx([''], player)
        await _pick_table_colors(ctx)
        text = ctx._flat()
        self.assertIn('|green|', text)
        self.assertIn('Town Square', text)
        self.assertIn('Players', text)


if __name__ == '__main__':
    unittest.main()
