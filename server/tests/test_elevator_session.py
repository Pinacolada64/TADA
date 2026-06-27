"""tests/test_elevator_session.py

Tests for the elevator session loop, look description, fall-through dispatch,
travel, and out-of-range guards introduced in the recent elevator overhaul.

The old test_elevator.py targets a now-obsolete API; these tests use the
current ctx-based interface.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from shoppe.elevator import (
    _out_of_range,
    _travel_to,
    _elevator_session,
    _ELEVATOR_DESCRIPTION,
    _LEVEL_NAMES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(level: int = 1) -> MagicMock:
    p = MagicMock()
    p.name       = 'TestPlayer'
    p.map_level  = level
    p.is_debug   = False
    p.client_settings.screen_columns = 78
    return p


def make_ctx(player, prompts: list, *, processor=None) -> MagicMock:
    """Build a ctx whose prompt() feeds from *prompts*, then returns None."""
    ctx              = MagicMock()
    ctx.player       = player
    ctx.send         = AsyncMock()
    ctx.server.clients = {}           # no other occupants → no presence broadcasts

    ctx.client.map_level = player.map_level
    ctx.client.command_processor = processor

    it = iter(prompts)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    return ctx


def _sent(ctx) -> str:
    """Flatten all ctx.send() call args into one searchable string."""
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


# Patch both get_combination (always True) and underline (trivial output)
_PATCH_COMBO   = patch('shoppe.elevator.get_combination', new=AsyncMock(return_value=True))
_PATCH_ULINE   = patch('shoppe.elevator.underline', return_value=['Elevator', '--------'])


# ---------------------------------------------------------------------------
# _out_of_range()  — pure function
# ---------------------------------------------------------------------------

class TestOutOfRange(unittest.TestCase):

    def test_contains_obstacle(self):
        self.assertIn('ceiling', _out_of_range('ceiling'))

    def test_contains_floor(self):
        self.assertIn('floor', _out_of_range('floor'))

    def test_contains_roof(self):
        self.assertIn('roof', _out_of_range('roof'))

    def test_returns_string(self):
        self.assertIsInstance(_out_of_range('basement'), str)


# ---------------------------------------------------------------------------
# _travel_to()
# ---------------------------------------------------------------------------

class TestTravelTo(unittest.IsolatedAsyncioTestCase):

    async def test_sets_player_map_level(self):
        player = make_player(level=1)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 3)
        self.assertEqual(player.map_level, 3)

    async def test_sends_travel_narrative(self):
        player = make_player(level=1)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 2)
        self.assertIn('Dark Side', _sent(ctx))

    async def test_direction_upwards(self):
        player = make_player(level=1)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 3)
        self.assertIn('upwards', _sent(ctx))

    async def test_direction_downwards(self):
        player = make_player(level=4)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 2)
        self.assertIn('downwards', _sent(ctx))

    async def test_same_level_sends_nowhere(self):
        player = make_player(level=2)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 2)
        self.assertIn('nowhere in particular', _sent(ctx))

    async def test_target_below_range_sends_out_of_range(self):
        player = make_player(level=1)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 0)
        self.assertIn('basement', _sent(ctx))
        self.assertEqual(player.map_level, 1)   # unchanged

    async def test_target_above_range_sends_out_of_range(self):
        player = make_player(level=5)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 8)
        self.assertIn('roof', _sent(ctx))
        self.assertEqual(player.map_level, 5)   # unchanged

    async def test_sets_client_map_level(self):
        player = make_player(level=1)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 4)
        self.assertEqual(ctx.client.map_level, 4)

    async def test_level_name_in_output(self):
        player = make_player(level=1)
        ctx    = make_ctx(player, [])
        await _travel_to(ctx, 5)
        self.assertIn(_LEVEL_NAMES[4], _sent(ctx))   # "Land of the Wraiths"


# ---------------------------------------------------------------------------
# _elevator_session() — look / description
# ---------------------------------------------------------------------------

class TestElevatorLook(unittest.IsolatedAsyncioTestCase):

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_look_sends_description(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['look', 'l'])   # look then leave
        await _elevator_session(ctx, player)
        self.assertIn('iron cage', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_lo_abbreviation(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['lo', 'l'])
        await _elevator_session(ctx, player)
        self.assertIn('iron cage', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_loo_abbreviation(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['loo', 'l'])
        await _elevator_session(ctx, player)
        self.assertIn('iron cage', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_look_does_not_exit(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['look', 'l'])
        await _elevator_session(ctx, player)
        # 'leave' message only from the explicit 'l' — not from 'look'
        self.assertIn('steps aside', _sent(ctx))


# ---------------------------------------------------------------------------
# _elevator_session() — leave variants
# ---------------------------------------------------------------------------

class TestElevatorLeave(unittest.IsolatedAsyncioTestCase):

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_l_exits(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await _elevator_session(ctx, player)
        self.assertIn('steps aside', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_x_exits(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['x'])
        await _elevator_session(ctx, player)
        self.assertIn('steps aside', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_leave_word_exits(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['leave'])
        await _elevator_session(ctx, player)
        self.assertIn('steps aside', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_empty_input_exits(self, *_):
        player = make_player()
        ctx    = make_ctx(player, [''])
        await _elevator_session(ctx, player)
        self.assertIn('steps aside', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_none_prompt_exits(self, *_):
        player = make_player()
        ctx    = make_ctx(player, [None])
        await _elevator_session(ctx, player)
        # No crash; guard message not shown on EOF
        self.assertTrue(ctx.send.called)


# ---------------------------------------------------------------------------
# _elevator_session() — U / D navigation
# ---------------------------------------------------------------------------

class TestElevatorUpDown(unittest.IsolatedAsyncioTestCase):

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_u_moves_up(self, *_):
        player = make_player(level=2)
        ctx    = make_ctx(player, ['u', 'l'])
        await _elevator_session(ctx, player)
        self.assertEqual(player.map_level, 3)

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_d_moves_down(self, *_):
        player = make_player(level=3)
        ctx    = make_ctx(player, ['d', 'l'])
        await _elevator_session(ctx, player)
        self.assertEqual(player.map_level, 2)

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_u_at_top_sends_out_of_range(self, *_):
        player = make_player(level=5)   # top of elevator range
        ctx    = make_ctx(player, ['u', 'l'])
        await _elevator_session(ctx, player)
        self.assertIn('ceiling', _sent(ctx))
        self.assertEqual(player.map_level, 5)

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_d_at_bottom_sends_out_of_range(self, *_):
        player = make_player(level=1)
        ctx    = make_ctx(player, ['d', 'l'])
        await _elevator_session(ctx, player)
        self.assertIn('floor', _sent(ctx))
        self.assertEqual(player.map_level, 1)


# ---------------------------------------------------------------------------
# _elevator_session() — numeric level selection
# ---------------------------------------------------------------------------

class TestElevatorNumeric(unittest.IsolatedAsyncioTestCase):

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_number_travels_to_level(self, *_):
        player = make_player(level=1)
        ctx    = make_ctx(player, ['4', 'l'])
        await _elevator_session(ctx, player)
        self.assertEqual(player.map_level, 4)

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_out_of_range_number_sends_error(self, *_):
        player = make_player(level=1)
        ctx    = make_ctx(player, ['9', 'l'])
        await _elevator_session(ctx, player)
        out = _sent(ctx)
        self.assertIn('between 1 and', out)
        self.assertEqual(player.map_level, 1)


# ---------------------------------------------------------------------------
# _elevator_session() — fall-through to command processor
# ---------------------------------------------------------------------------

class TestElevatorFallThrough(unittest.IsolatedAsyncioTestCase):

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_unknown_input_dispatches_to_processor(self, *_):
        processor = MagicMock()
        processor.process_input = AsyncMock(return_value=MagicMock())
        player = make_player()
        ctx    = make_ctx(player, ['say hello', 'l'], processor=processor)
        await _elevator_session(ctx, player)
        processor.process_input.assert_awaited_once_with('say hello', ctx=ctx)

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_stat_dispatched_to_processor(self, *_):
        processor = MagicMock()
        processor.process_input = AsyncMock(return_value=MagicMock())
        player = make_player()
        ctx    = make_ctx(player, ['stat', 'l'], processor=processor)
        await _elevator_session(ctx, player)
        processor.process_input.assert_awaited_once_with('stat', ctx=ctx)

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_no_processor_sends_fallback(self, *_):
        player = make_player()
        ctx    = make_ctx(player, ['gibberish', 'l'], processor=None)
        await _elevator_session(ctx, player)
        self.assertIn('L to leave', _sent(ctx))

    @_PATCH_COMBO
    @_PATCH_ULINE
    async def test_look_not_dispatched_to_processor(self, *_):
        """'look' is handled locally — must not reach the command processor."""
        processor = MagicMock()
        processor.process_input = AsyncMock(return_value=MagicMock())
        player = make_player()
        ctx    = make_ctx(player, ['look', 'l'], processor=processor)
        await _elevator_session(ctx, player)
        processor.process_input.assert_not_awaited()


# ---------------------------------------------------------------------------
# _ELEVATOR_DESCRIPTION constant
# ---------------------------------------------------------------------------

class TestElevatorDescription(unittest.TestCase):

    def test_description_is_non_empty(self):
        self.assertGreater(len(_ELEVATOR_DESCRIPTION), 0)

    def test_description_mentions_iron_cage(self):
        self.assertIn('iron cage', _ELEVATOR_DESCRIPTION)


if __name__ == '__main__':
    unittest.main()
