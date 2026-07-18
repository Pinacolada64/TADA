"""tests/commands/test_order.py — unit tests for commands/order.py (ORDER).

Coverage:
  - no servants -> "You don't have any servants!"
  - show deployment, decline to change (N) -> no positions altered
  - full re-deploy (3 servants into 3 slots) -> positions set, persisted
    (unsaved_changes flips, party.to_json/from_json round-trips position)
  - leaving a slot NONE with fewer servants than slots is allowed
  - typing 0/blank for a slot while servants remain unplaced forces a retry
    ("You didn't deploy ALL your servants!"), matching SPUR.MISC2.S
  - a DEAD/UNCONSCIOUS or FREE ally is not offered as deployable
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from bar.ally_data import Ally, AllyPosition, AllyStatus
from commands.order import OrderCommand
from party import Party


def _make_ally(name: str, strength: int = 10, to_hit: int = 5,
               status: AllyStatus = AllyStatus.SERVANT) -> Ally:
    ally = Ally(name, 'm', strength, to_hit)
    ally.status = status
    ally.hit_points = 20
    return ally


def _make_player(allies=None):
    player = MagicMock()
    player.name = 'Rulan'
    player.party = Party(allies or [])
    player.unsaved_changes = False
    return player


class _FakeCtx:
    """Fake GameContext whose prompt() answers come from a queue, one per call."""

    def __init__(self, player, answers=None):
        self.player = player
        self._sent: list[str] = []
        self._answers = list(answers or [])

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass

    async def prompt(self, *args, **kwargs) -> str:
        return self._answers.pop(0) if self._answers else ''

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _run(coro):
    return asyncio.run(coro)


class TestOrderCommand(unittest.TestCase):

    def test_no_servants(self):
        player = _make_player([])
        ctx = _FakeCtx(player)
        result = _run(OrderCommand().execute(ctx))
        self.assertTrue(result.success)
        self.assertIn("You don't have any servants!", ctx.sent())

    def test_decline_change_leaves_positions_untouched(self):
        ally = _make_ally('BATMAN')
        ally.position = AllyPosition.POINT
        player = _make_player([ally])
        ctx = _FakeCtx(player, answers=['N'])

        _run(OrderCommand().execute(ctx))

        self.assertEqual(ally.position, AllyPosition.POINT)
        self.assertFalse(player.unsaved_changes)
        self.assertIn('POINT MAN', ctx.sent())
        self.assertIn('BATMAN', ctx.sent())

    def test_full_redeploy_three_servants(self):
        a1, a2, a3 = (_make_ally('ALFRED'), _make_ally('ROBIN'), _make_ally('BATGIRL'))
        player = _make_player([a1, a2, a3])
        # Y, then pick ROBIN(2) for Point, ALFRED(1) for Flank, BATGIRL(1, last one left) for Rear
        ctx = _FakeCtx(player, answers=['Y', '2', '1', '1'])

        result = _run(OrderCommand().execute(ctx))

        self.assertTrue(result.success)
        self.assertEqual(a2.position, AllyPosition.POINT)
        self.assertEqual(a1.position, AllyPosition.FLANK)
        self.assertEqual(a3.position, AllyPosition.REAR)
        self.assertTrue(player.unsaved_changes)

    def test_partial_deploy_leaves_a_slot_none(self):
        a1 = _make_ally('ALFRED')
        player = _make_player([a1])
        # Y, then place ALFRED at Flank (slot 2), NONE for Point (slot 1) and Rear (slot 3)
        ctx = _FakeCtx(player, answers=['Y', '0', '1', '0'])

        _run(OrderCommand().execute(ctx))

        self.assertEqual(a1.position, AllyPosition.FLANK)

    def test_leaving_someone_undeployed_forces_retry(self):
        a1, a2 = _make_ally('ALFRED'), _make_ally('ROBIN')
        player = _make_player([a1, a2])
        # First pass: only deploy ALFRED (Point), decline the other two slots
        # -> ROBIN never placed -> "didn't deploy ALL" -> retry -> this time
        # place ALFRED at Point, ROBIN at Flank, none at Rear.
        ctx = _FakeCtx(player, answers=['Y', '1', '0', '0', '1', '1', '0'])

        _run(OrderCommand().execute(ctx))

        self.assertIn("You didn't deploy ALL your servants!", ctx.sent())
        self.assertEqual(a1.position, AllyPosition.POINT)
        self.assertEqual(a2.position, AllyPosition.FLANK)

    def test_deployment_display_shows_only_positioned_servants(self):
        alive = _make_ally('ALFRED')
        alive.position = AllyPosition.POINT
        dead  = _make_ally('DEAD GUY', status=AllyStatus.DEAD)
        free  = _make_ally('FREE SPIRIT', status=AllyStatus.FREE)
        player = _make_player([alive, dead, free])
        ctx = _FakeCtx(player, answers=['N'])

        _run(OrderCommand().execute(ctx))

        sent = ctx.sent()
        self.assertIn('ALFRED', sent)
        self.assertNotIn('DEAD GUY', sent)
        self.assertNotIn('FREE SPIRIT', sent)

    def test_dead_and_free_allies_not_offered_when_redeploying(self):
        alive = _make_ally('ALFRED')
        dead  = _make_ally('DEAD GUY', status=AllyStatus.DEAD)
        free  = _make_ally('FREE SPIRIT', status=AllyStatus.FREE)
        player = _make_player([alive, dead, free])
        # Only one servant (ALFRED) is actually eligible: 'Y' to change, then
        # place him at Point (1) and decline the other two slots (0, 0).
        # If DEAD GUY/FREE SPIRIT were wrongly offered, this exact answer
        # sequence would leave someone undeployed and trigger a retry, which
        # would exhaust the canned answers and return '' (an invalid pick).
        ctx = _FakeCtx(player, answers=['Y', '1', '0', '0'])

        result = _run(OrderCommand().execute(ctx))

        self.assertTrue(result.success)
        self.assertEqual(alive.position, AllyPosition.POINT)
        self.assertNotIn("You didn't deploy ALL your servants!", ctx.sent())

    def test_position_round_trips_through_party_json(self):
        ally = _make_ally('BATMAN')
        ally.position = AllyPosition.REAR
        party = Party([ally])

        restored = Party.from_json(party.to_json())

        self.assertEqual(restored.members[0].position, AllyPosition.REAR)


if __name__ == '__main__':
    unittest.main()
