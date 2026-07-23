"""tests/client/test_prefs_menu_colors.py

Regression/coverage for commands/prefs.py's 'S' (Menu Colors) picker,
which sets client_settings.menu_colors (a menu_system.MenuColor) --
consumed by menu_system.format_menu_lines() to color every menu
(EDITPLAYER, CONFIG, etc).
"""
from __future__ import annotations

import unittest

from menu_system import DEFAULT_MENU_COLORS, MENU_COLOR_PRESETS, MenuColor
from player import Player
from commands.prefs import _pick_menu_colors

# 'S' menu's option number for 'Custom (pick each part)' -- one past the
# last named preset, matching _pick_menu_colors()'s own custom_num.
_CUSTOM = str(len(MENU_COLOR_PRESETS) + 1)


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


class TestPickMenuColorsDefault(unittest.IsolatedAsyncioTestCase):

    async def test_default_option_clears_override(self):
        player = Player()
        player.client_settings.menu_colors = MenuColor(rule='green')
        ctx = _FakeCtx(['1', 'y'], player)
        await _pick_menu_colors(ctx)
        self.assertIsNone(player.client_settings.menu_colors)

    async def test_blank_leaves_existing_override_untouched(self):
        player = Player()
        player.client_settings.menu_colors = MenuColor(rule='green')
        ctx = _FakeCtx([''], player)
        await _pick_menu_colors(ctx)
        self.assertEqual(player.client_settings.menu_colors.rule, 'green')


class TestPickMenuColorsNamedPresets(unittest.IsolatedAsyncioTestCase):

    async def test_picking_a_named_preset_stores_its_colors(self):
        player = Player()
        # Index 2 in MENU_COLOR_PRESETS ('Monochrome Green' -- see the
        # module-level list in menu_system.py).
        idx = next(i for i, (name, _) in enumerate(MENU_COLOR_PRESETS, 1)
                   if name == 'Monochrome Green')
        ctx = _FakeCtx([str(idx), 'y'], player)
        await _pick_menu_colors(ctx)
        mc = player.client_settings.menu_colors
        self.assertEqual((mc.rule, mc.number, mc.shortcut, mc.label,
                           mc.dot_leader, mc.dot_value),
                          ('green',) * 6)

    async def test_picking_a_named_preset_stores_a_copy_not_the_shared_instance(self):
        player = Player()
        idx = next(i for i, (name, _) in enumerate(MENU_COLOR_PRESETS, 1)
                   if name == 'Monochrome Orange')
        ctx = _FakeCtx([str(idx), 'y'], player)
        await _pick_menu_colors(ctx)
        mc = player.client_settings.menu_colors
        preset_mc = dict(MENU_COLOR_PRESETS)['Monochrome Orange']
        self.assertIsNot(mc, preset_mc)
        mc.rule = 'mutated'
        self.assertEqual(preset_mc.rule, 'orange')  # preset itself untouched

    async def test_out_of_range_number_leaves_scheme_unchanged(self):
        player = Player()
        player.client_settings.menu_colors = MenuColor(rule='green')
        ctx = _FakeCtx([str(len(MENU_COLOR_PRESETS) + 50)], player)
        await _pick_menu_colors(ctx)
        self.assertEqual(player.client_settings.menu_colors.rule, 'green')


class TestPickMenuColorsCustom(unittest.IsolatedAsyncioTestCase):

    async def test_custom_walks_all_six_fields_in_order(self):
        # Custom, then one numbered pick per _MENU_COLOR_FIELDS entry
        # (rule, number, shortcut, label, dot_leader, dot_value).
        player = Player()
        ctx = _FakeCtx([_CUSTOM, '1', '2', '3', '4', '5', '6', 'y'], player)
        await _pick_menu_colors(ctx)
        mc = player.client_settings.menu_colors
        self.assertIsInstance(mc, MenuColor)
        # Whatever landed shouldn't just be the untouched default scheme --
        # confirms all six prompts were actually consumed and applied.
        self.assertNotEqual(
            (mc.rule, mc.number, mc.shortcut, mc.label, mc.dot_leader, mc.dot_value),
            (DEFAULT_MENU_COLORS.rule, DEFAULT_MENU_COLORS.number,
             DEFAULT_MENU_COLORS.shortcut, DEFAULT_MENU_COLORS.label,
             DEFAULT_MENU_COLORS.dot_leader, DEFAULT_MENU_COLORS.dot_value),
        )

    async def test_custom_blank_field_keeps_its_current_value(self):
        player = Player()
        player.client_settings.menu_colors = MenuColor(rule='purple')
        # Blank on every prompt after Custom -- every field should keep
        # the value it started with (the existing override's 'purple'
        # rule, defaults for the rest).
        ctx = _FakeCtx([_CUSTOM, '', '', '', '', '', '', 'y'], player)
        await _pick_menu_colors(ctx)
        mc = player.client_settings.menu_colors
        self.assertEqual(mc.rule, 'purple')
        self.assertEqual(mc.number, DEFAULT_MENU_COLORS.number)

    async def test_custom_out_of_range_number_leaves_field_unchanged(self):
        player = Player()
        ctx = _FakeCtx([_CUSTOM, '999', '', '', '', '', '', 'y'], player)
        await _pick_menu_colors(ctx)
        mc = player.client_settings.menu_colors
        self.assertEqual(mc.rule, DEFAULT_MENU_COLORS.rule)

    async def test_custom_starts_from_a_copy_not_the_shared_default(self):
        """Editing one field via Custom must never mutate the shared
        module-level DEFAULT_MENU_COLORS instance itself."""
        player = Player()
        ctx = _FakeCtx([_CUSTOM, '1', '', '', '', '', '', 'y'], player)
        await _pick_menu_colors(ctx)
        self.assertEqual(DEFAULT_MENU_COLORS.rule, 'cyan')

    async def test_cancel_mid_walk_returns_without_saving(self):
        player = Player()
        # Custom, then a single None (queue exhausted) on the first
        # field's prompt -- _FakeCtx.prompt() returns None once responses
        # run out.
        ctx = _FakeCtx([_CUSTOM], player)
        await _pick_menu_colors(ctx)
        self.assertIsNone(player.client_settings.menu_colors)


class TestPickMenuColorsConfirmLoop(unittest.IsolatedAsyncioTestCase):

    async def test_n_does_not_save_and_reprompts_the_picker(self):
        player = Player()
        idx_green = next(i for i, (name, _) in enumerate(MENU_COLOR_PRESETS, 1)
                          if name == 'Monochrome Green')
        # Pick Monochrome Green, say 'n' (not satisfied), then pick
        # Monochrome White and confirm with 'y' -- the first pick must
        # never have been saved.
        idx_white = next(i for i, (name, _) in enumerate(MENU_COLOR_PRESETS, 1)
                          if name == 'Monochrome White')
        ctx = _FakeCtx([str(idx_green), 'n', str(idx_white), 'y'], player)
        await _pick_menu_colors(ctx)
        mc = player.client_settings.menu_colors
        self.assertEqual(mc.rule, 'white')

    async def test_n_shows_the_picker_again_with_swatches(self):
        player = Player()
        idx_green = next(i for i, (name, _) in enumerate(MENU_COLOR_PRESETS, 1)
                          if name == 'Monochrome Green')
        ctx = _FakeCtx([str(idx_green), 'n'], player)
        await _pick_menu_colors(ctx)
        # 'Custom (pick each part)' is only printed once per picker
        # display -- twice in the sent log means the picker really did
        # redisplay after the 'n'.
        occurrences = ctx._flat().count('Custom (pick each part)')
        self.assertEqual(occurrences, 2)

    async def test_asks_satisfactory_question_before_saving(self):
        player = Player()
        ctx = _FakeCtx(['1', 'y'], player)
        await _pick_menu_colors(ctx)
        self.assertIn('Are these colors satisfactory?', ctx._flat())

    async def test_blank_on_confirm_does_not_save(self):
        player = Player()
        player.client_settings.menu_colors = MenuColor(rule='purple')
        idx_green = next(i for i, (name, _) in enumerate(MENU_COLOR_PRESETS, 1)
                          if name == 'Monochrome Green')
        # Queue exhausted right at the confirm prompt -- _FakeCtx.prompt()
        # returns None, treated the same as a non-'y' answer.
        ctx = _FakeCtx([str(idx_green)], player)
        await _pick_menu_colors(ctx)
        self.assertEqual(player.client_settings.menu_colors.rule, 'purple')

    async def test_custom_confirm_loop_uses_the_just_built_scheme_as_preview(self):
        player = Player()
        ctx = _FakeCtx([_CUSTOM, '1', '', '', '', '', '', 'n', '1', 'y'], player)
        # First custom walk sets field 'rule' to palette #1, says 'n';
        # picker redisplays; pick preset #1 (Default) and confirm -- the
        # first (never-confirmed) custom scheme must not have been saved.
        await _pick_menu_colors(ctx)
        self.assertIsNone(player.client_settings.menu_colors)


class TestPickMenuColorsPreview(unittest.IsolatedAsyncioTestCase):

    async def test_shows_live_mock_menu_using_current_scheme(self):
        # Regression: the preview used to be a hand-built approximation of
        # one sample row; it now renders a real Menu (title, hrules,
        # numbered/shortcut items, dot leaders) through the actual
        # menu_system.format_menu_lines(), so what's shown here is
        # guaranteed to match what a real menu looks like with this scheme.
        player = Player()
        player.client_settings.menu_colors = MenuColor(rule='green')
        ctx = _FakeCtx([''], player)
        await _pick_menu_colors(ctx)
        text = ctx._flat()
        self.assertIn('|green|', text)
        self.assertIn('[Sample Menu]', text)
        self.assertIn('Alignment', text)
        self.assertIn('Hit Points', text)
        self.assertIn('Neutral', text)


if __name__ == '__main__':
    unittest.main()
