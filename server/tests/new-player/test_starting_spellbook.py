"""tests/new-player/test_starting_spellbook.py

Covers commands/new_player.py's _assign_equipment() granting a starting
Spell Book to Wizards/Druids (spellbook.py) -- same beginner-gear step
that already issues a shield/armor/starter weapon.
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import spellbook
from base_classes import PlayerClass
from commands.new_player import _assign_equipment
from inventory import Inventory
from player import Player


def run(coro):
    return asyncio.run(coro)


def _ctx(char_class):
    player = Player(name='Rulan', char_class=char_class)
    player.inventory = Inventory(capacity=14)
    ctx = SimpleNamespace(
        player=player,
        server=SimpleNamespace(items=[], weapons=[]),
        send=AsyncMock(),
    )
    return ctx


class TestStartingSpellbookGrant(unittest.TestCase):
    def test_wizard_starts_with_a_spell_book(self):
        ctx = _ctx(PlayerClass.WIZARD)
        run(_assign_equipment(ctx))
        self.assertIsNotNone(spellbook.find_spellbook(ctx.player))

    def test_druid_starts_with_a_spell_book(self):
        ctx = _ctx(PlayerClass.DRUID)
        run(_assign_equipment(ctx))
        self.assertIsNotNone(spellbook.find_spellbook(ctx.player))

    def test_fighter_does_not_get_a_spell_book(self):
        ctx = _ctx(PlayerClass.FIGHTER)
        run(_assign_equipment(ctx))
        self.assertIsNone(spellbook.find_spellbook(ctx.player))

    def test_grant_is_mentioned_in_the_issued_equipment_lines(self):
        ctx = _ctx(PlayerClass.WIZARD)
        run(_assign_equipment(ctx))
        sent = '\n'.join(
            '\n'.join(a) if isinstance(a, list) else str(a)
            for call in ctx.send.await_args_list
            for a in call.args
        )
        self.assertIn('Spell Book', sent)


if __name__ == '__main__':
    unittest.main()
