"""tests/combat/test_galadriel.py — encounters/galadriel.py: the "Test
of Galadriel" random encounter (SPUR.MISC6.S:504-534, quest #8).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Map, Room
from items import ItemCategory


def _make_map(room_flags=None, level=1):
    m = Map()
    rooms = {
        1: Room(number=1, name='Room One', desc='', exits={}, monster=0,
                flags=room_flags or []),
        2: Room(number=2, name='Room Two', desc='', exits={}, monster=5),
    }
    m.levels[level] = rooms
    if level == 1:
        m.rooms = rooms
    return m


class _FakeInventoryEntry:
    def __init__(self, item):
        self.item = item


class _FakeItem:
    def __init__(self, id_number, name):
        self.id_number = id_number
        self.name = name


class _FakeInventory:
    def __init__(self, items=()):
        self._entries = [_FakeInventoryEntry(i) for i in items]
        self.added = []

    def entries(self, category=None):
        return self._entries

    def add(self, item, quantity=1):
        self._entries.append(_FakeInventoryEntry(item))
        self.added.append(item)


def _make_player(seen=False, items=()):
    player = MagicMock()
    player.name = 'Testerson'
    player.once_per_day = ['galadriel_seen'] if seen else []
    player.inventory = _FakeInventory(items)
    player.unsaved_changes = False
    return player


_MESSAGES = {
    24: ['A soft vision floats before your eyes!'],
    25: ['Who lies in the tomb of Moria?', '1) Khazad-dum 2) Gimli 3) Balin 4) EntWood'],
    26: ['In what great battle was Sting first used?', '1) A 2) B 3) C 4) D'],
    27: ['What is a Treebeard?', '1) A 2) B 3) C 4) D'],
    28: ['What is a Gollum?', '1) A 2) B 3) C 4) D'],
    29: ['Who is Sharkey?', '1) A 2) B 3) C 4) D'],
}


def _make_ctx(room_no=1, player=None, game_map=None, prompt_returns=None, map_level=1):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player = player or _make_player()
    ctx.player.map_level = map_level
    ctx.server.game_map = game_map or _make_map()
    ctx.server.messages = dict(_MESSAGES)
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompt_returns or [])
    return ctx


class TestTryEncounterGating(unittest.IsolatedAsyncioTestCase):
    async def test_no_op_if_already_seen(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(player=_make_player(seen=True))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_no_op_if_already_carrying_empty_vial(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(player=_make_player(items=[_FakeItem(142, "Galadriel's vial (empty)")]))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_no_op_if_already_carrying_full_vial(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(player=_make_player(items=[_FakeItem(143, "Galadriel's vial (full)")]))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_no_op_if_room_has_monster(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(room_no=2)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_no_op_when_roll_fails(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=99.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_marks_seen_on_trigger(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['1'])
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=25):
            await try_encounter(ctx)
        self.assertIn('galadriel_seen', ctx.player.once_per_day)


class TestRiddleOutcome(unittest.IsolatedAsyncioTestCase):
    async def test_correct_answer_awards_vial(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['3'])  # riddle #25's correct answer
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=25):
            await try_encounter(ctx)
        added = ctx.player.inventory.added
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].id_number, 143)
        self.assertEqual(added[0].category, ItemCategory.DRINK)
        self.assertTrue(ctx.player.unsaved_changes)

    async def test_wrong_answer_awards_nothing(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['1'])  # wrong for riddle #25 (correct is 3)
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=25):
            await try_encounter(ctx)
        self.assertEqual(ctx.player.inventory.added, [])

    async def test_non_numeric_answer_treated_as_wrong(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['banana'])
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=25):
            await try_encounter(ctx)
        self.assertEqual(ctx.player.inventory.added, [])

    async def test_correct_answer_sends_congratulations(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['2'])  # riddle #26's correct answer
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=26):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('Well done', sent)

    async def test_wrong_answer_sends_dismissal(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['1'])  # wrong for riddle #26 (correct is 2)
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=26):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('Return when Ye are worthy', sent)


class TestBattleLog(unittest.IsolatedAsyncioTestCase):
    async def test_pass_logs_to_battle_log(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['1'])  # riddle #28's correct answer
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=28), \
             patch('net_common.append_battle_log') as mock_log:
            await try_encounter(ctx)
        mock_log.assert_called_once()
        self.assertIn('PASSed', mock_log.call_args.args[0])

    async def test_fail_logs_to_battle_log(self):
        from encounters.galadriel import try_encounter
        ctx = _make_ctx(prompt_returns=['4'])  # wrong for riddle #28 (correct is 1)
        with patch('random.uniform', return_value=0.0), \
             patch('random.choice', return_value=28), \
             patch('net_common.append_battle_log') as mock_log:
            await try_encounter(ctx)
        mock_log.assert_called_once()
        self.assertIn('FAILed', mock_log.call_args.args[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
