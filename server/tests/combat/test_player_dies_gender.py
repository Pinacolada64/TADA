"""tests/combat/test_player_dies_gender.py

CombatSession._player_dies()'s closing line uses gendered "son"/"daughter"
phrasing (TADA addition, not SPUR-sourced -- see server/GENDER_AUDIT.md's
death-message-variant suggestion). The "You have been slain by..." line
itself stays gender-neutral and unchanged.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import Gender
from combat.engine import CombatSession


class _FakePlayer:
    def __init__(self, gender):
        self.name = 'Rulan'
        self.hit_points = 30
        self.gender = gender


class _FakeCtx:
    def __init__(self, gender):
        self.player = _FakePlayer(gender)
        self.client = MagicMock(room=1)
        self.server = MagicMock()
        self.send = AsyncMock()
        self.send_room = AsyncMock()

    def sent(self) -> str:
        return '\n'.join(str(c.args[0]) for c in self.send.await_args_list)


class TestPlayerDiesGenderedSendoff(unittest.IsolatedAsyncioTestCase):

    async def test_male_gets_son(self):
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        ctx = _FakeCtx(Gender.MALE)
        await session._player_dies(ctx)
        self.assertIn('son of these lands', ctx.sent())

    async def test_female_gets_daughter(self):
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        ctx = _FakeCtx(Gender.FEMALE)
        await session._player_dies(ctx)
        self.assertIn('daughter of these lands', ctx.sent())

    async def test_slain_by_line_unchanged_regardless_of_gender(self):
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        ctx = _FakeCtx(Gender.FEMALE)
        await session._player_dies(ctx)
        self.assertIn('You have been slain by the TROLL!', ctx.sent())


if __name__ == '__main__':
    unittest.main()
