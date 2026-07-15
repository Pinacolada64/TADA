"""tests/test_shoppe_locker.py

Covers shoppe/locker.py — the Private Locker (SPUR.MISC6.S "locker"
subroutine, reached from the Merchant Shoppe), with a homebrew
combination-lock layer on top (matching the Elevator's guard-and-combination
pattern):

  - First visit: no LOCKER combination yet -> an attendant assigns one,
    hands over a "brass claim tag" keepsake, and opens the locker directly
    (no combination re-entry needed on the very first visit).
  - Later visits: must enter the previously-issued combination, with a
    limited number of attempts, same shape as shoppe/elevator.py's guard.
  - P)ut / T)ake / L)ook move items between player.inventory and
    player.locker (both Inventory instances), respecting capacity limits
    on both sides.

Run with:
    python -m pytest tests/test_shoppe_locker.py -v
"""
from __future__ import annotations

import unittest

from shoppe.locker import main as locker_main
from base_classes import CombinationTypes
from inventory import Inventory, LOCKER_CAPACITY
from items import Item, ItemCategory
from player import Player


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _combo_digits(player) -> str:
    combo = player.combinations[CombinationTypes.LOCKER]
    return '-'.join(f'{n:02}' for n in combo.combination)


class TestFirstVisit(unittest.IsolatedAsyncioTestCase):

    async def test_new_player_has_no_locker_combination(self):
        player = Player(name='Rulan')
        self.assertNotIn(CombinationTypes.LOCKER, player.combinations)

    async def test_first_visit_assigns_combination_and_tag(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx(['q'], player)
        await locker_main(ctx)

        self.assertIn(CombinationTypes.LOCKER, player.combinations)
        flat = ctx._flat()
        self.assertIn('locker attendant', flat)
        self.assertIn(_combo_digits(player), flat)
        self.assertIn('brass claim tag', flat)
        tag_entries = player.inventory.find(name='brass claim tag')
        self.assertEqual(len(tag_entries), 1)

    async def test_first_visit_skips_combination_reprompt(self):
        """The attendant hands you in directly -- no combination prompt yet."""
        player = Player(name='Rulan')
        ctx = _FakeCtx(['q'], player)
        await locker_main(ctx)
        self.assertIn('PRIVATE LOCKER', ctx._flat())

    async def test_full_pack_skips_tag_but_still_grants_combination(self):
        player = Player(name='Rulan')
        player.inventory = Inventory(capacity=0)  # no room for the tag
        ctx = _FakeCtx(['q'], player)
        await locker_main(ctx)
        self.assertIn(CombinationTypes.LOCKER, player.combinations)
        self.assertIn("can't give you the tag", ctx._flat().replace(chr(8217), "'"))


class TestReturnVisit(unittest.IsolatedAsyncioTestCase):

    def _player_with_combo(self):
        player = Player(name='Rulan')
        from base_classes import Combination
        combo = Combination(CombinationTypes.LOCKER)
        combo.combination = (11, 22, 33)
        player.combinations[CombinationTypes.LOCKER] = combo
        return player

    async def test_correct_combination_opens_locker(self):
        player = self._player_with_combo()
        ctx = _FakeCtx(['11-22-33', 'q'], player)
        await locker_main(ctx)
        self.assertIn('PRIVATE LOCKER', ctx._flat())

    async def test_wrong_combination_locks_out_after_max_tries(self):
        player = self._player_with_combo()
        ctx = _FakeCtx(['1-1-1', '2-2-2', '3-3-3', '4-4-4', '5-5-5'], player)
        await locker_main(ctx)
        self.assertIn('Out of attempts.', ctx._flat())
        self.assertNotIn('PRIVATE LOCKER', ctx._flat())

    async def test_blank_combination_reprompts(self):
        player = self._player_with_combo()
        ctx = _FakeCtx(['', '11-22-33', 'q'], player)
        await locker_main(ctx)
        self.assertIn('PRIVATE LOCKER', ctx._flat())

    async def test_disconnect_during_combination_prompt(self):
        player = self._player_with_combo()
        ctx = _FakeCtx([], player)
        await locker_main(ctx)
        self.assertNotIn('PRIVATE LOCKER', ctx._flat())


class TestPutTakeLook(unittest.IsolatedAsyncioTestCase):

    def _ready_player(self):
        player = Player(name='Rulan')
        from base_classes import Combination
        combo = Combination(CombinationTypes.LOCKER)
        combo.combination = (1, 2, 3)
        player.combinations[CombinationTypes.LOCKER] = combo
        player.locker = Inventory(capacity=LOCKER_CAPACITY)
        player.inventory.add(Item(id_number=201, name='sword', category=ItemCategory.ITEM))
        return player

    async def test_put_moves_item_to_locker(self):
        player = self._ready_player()
        ctx = _FakeCtx(['1-2-3', 'p', '1', 'q'], player)
        await locker_main(ctx)
        self.assertEqual(len(player.inventory.find(name='sword')), 0)
        self.assertEqual(len(player.locker.find(name='sword')), 1)
        self.assertIn('Ok, it is in the locker.', ctx._flat())

    async def test_take_moves_item_back(self):
        player = self._ready_player()
        # Put it away first, then take it back out in the same session.
        ctx = _FakeCtx(['1-2-3', 'p', '1', 't', '1', 'q'], player)
        await locker_main(ctx)
        self.assertEqual(len(player.inventory.find(name='sword')), 1)
        self.assertEqual(len(player.locker.find(name='sword')), 0)
        self.assertIn('Got it!', ctx._flat())

    async def test_look_lists_both_sides(self):
        player = self._ready_player()
        ctx = _FakeCtx(['1-2-3', 'l', 'q'], player)
        await locker_main(ctx)
        flat = ctx._flat()
        self.assertIn('The locker contains', flat)
        self.assertIn('And you are carrying', flat)
        self.assertIn('sword', flat)

    async def test_put_when_locker_full(self):
        player = self._ready_player()
        player.locker = Inventory(capacity=0)
        ctx = _FakeCtx(['1-2-3', 'p', 'q'], player)
        await locker_main(ctx)
        self.assertIn('The locker is full!', ctx._flat())

    async def test_take_when_pack_full(self):
        player = self._ready_player()
        player.inventory.capacity = len(player.inventory)  # already at capacity
        player.locker.add(Item(id_number=202, name='shield', category=ItemCategory.ITEM))
        ctx = _FakeCtx(['1-2-3', 't', 'q'], player)
        await locker_main(ctx)
        self.assertIn('You can carry no more Items.', ctx._flat())

    async def test_put_invalid_number_rejected(self):
        player = self._ready_player()
        ctx = _FakeCtx(['1-2-3', 'p', '99', 'q'], player)
        await locker_main(ctx)
        self.assertIn("You're NOT carrying that!!", ctx._flat())

    async def test_take_invalid_number_rejected(self):
        player = self._ready_player()
        player.locker.add(Item(id_number=202, name='shield', category=ItemCategory.ITEM))
        ctx = _FakeCtx(['1-2-3', 't', '99', 'q'], player)
        await locker_main(ctx)
        self.assertIn("That's not in the locker!", ctx._flat())


class TestLockerPersistence(unittest.TestCase):
    """player.locker (an Inventory) must survive a save/load roundtrip,
    same as player.inventory and player.quote."""

    def test_defaults_to_none(self):
        self.assertIsNone(Player().locker)

    def test_survives_save_and_load_roundtrip(self):
        import tempfile
        from unittest.mock import patch
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            with patch('player.Player._json_path',
                       staticmethod(lambda user_id: str(Path(tmp) / f'player-{user_id}.json'))):
                p = Player(name='Rulan', id='rulan')
                p.locker = Inventory(capacity=LOCKER_CAPACITY)
                p.locker.add(Item(id_number=201, name='sword', category=ItemCategory.ITEM))
                p.unsaved_changes = True
                assert p.save(force=True)

                reloaded = Player(name='Rulan', id='rulan')
                self.assertIsInstance(reloaded.locker, Inventory)
                self.assertEqual(len(reloaded.locker.find(name='sword')), 1)


class TestShoppeDispatch(unittest.IsolatedAsyncioTestCase):
    """shoppe/main.py recognizes the free-text 'locker' command word
    (SPUR.MISC6.S's `if i$="LOCKER" goto locker` style dispatch) ahead of
    its normal single-letter menu-key truncation, so typing LOCKER doesn't
    collide with the 'L' (Player List) menu key."""

    async def test_locker_command_enters_locker(self):
        from shoppe.main import _shoppe_session

        from flags import PlayerFlags

        player = Player(name='Rulan')
        player.set_flag(PlayerFlags.EXPERT_MODE)
        ctx = _FakeCtx(['locker', 'q', 'x'], player)
        await _shoppe_session(ctx, player)
        self.assertIn('PRIVATE LOCKER', ctx._flat())

    async def test_l_alone_still_reaches_player_list(self):
        """Single-letter 'l' must still dispatch to the Player List menu key,
        not get swallowed by the 'locker'/'lock' free-text check."""
        from shoppe.main import _shoppe_session
        from flags import PlayerFlags

        from unittest.mock import AsyncMock, patch

        player = Player(name='Rulan')
        player.set_flag(PlayerFlags.EXPERT_MODE)
        ctx = _FakeCtx(['l', ''], player)
        with patch('commands.messaging.prompt_player_choice', new=AsyncMock(return_value=None)) as mocked:
            await _shoppe_session(ctx, player)
        mocked.assert_awaited_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
