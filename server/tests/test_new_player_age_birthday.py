"""tests/test_new_player_age_birthday.py

Unit tests for commands/new_player.py's _choose_age() and the shared
characters.birthday_for_age() helper it (and commands/editplayer.py) uses.

Age and birthday used to be independent: EditPlayer accepted a freely
entered year, and character creation always used the current year
regardless of age, so the two could openly contradict each other (e.g.
age 30 with a birthday dated this year). birthday_for_age() derives the
birth year as current_year - age so they can't drift apart.

Run with:
    python -m pytest tests/test_new_player_age_birthday.py -v
"""
from __future__ import annotations

import unittest
from datetime import date

from characters import birthday_for_age
from commands.new_player import _choose_age


class _FakePlayer:
    def __init__(self):
        self.age = None
        self.birthday = None


class _FakeCtx:
    def __init__(self, responses=None):
        self._q = list(responses or [])
        self.sent: list[str] = []
        self.player = _FakePlayer()

    async def send(self, *args) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                self.sent.extend(str(x) for x in a)
            else:
                self.sent.append(str(a))

    async def prompt(self, prompt_text: str = '', preamble_lines=None) -> str:
        if preamble_lines:
            await self.send(preamble_lines)
        return self._q.pop(0) if self._q else None


class TestBirthdayForAge(unittest.TestCase):

    def test_derives_year_from_age(self):
        bday = birthday_for_age(30, 6, 16)
        self.assertEqual(bday.year, date.today().year - 30)
        self.assertEqual(bday.month, 6)
        self.assertEqual(bday.day, 16)

    def test_zero_or_missing_age_uses_current_year(self):
        self.assertEqual(birthday_for_age(0, 1, 1).year, date.today().year)
        self.assertEqual(birthday_for_age(None, 1, 1).year, date.today().year)

    def test_feb_29_falls_back_to_feb_28_on_non_leap_derived_year(self):
        # 2001 was not a leap year.
        bday = birthday_for_age(date.today().year - 2001, 2, 29)
        self.assertEqual((bday.year, bday.month, bday.day), (2001, 2, 28))


class TestChooseAgeBirthday(unittest.IsolatedAsyncioTestCase):

    async def test_today_option_derives_birthday_year_from_age(self):
        ctx = _FakeCtx(responses=['30', 't'])
        ok = await _choose_age(ctx)
        self.assertTrue(ok)
        self.assertEqual(ctx.player.age, 30)
        self.assertEqual(ctx.player.birthday.year, date.today().year - 30)
        self.assertEqual(ctx.player.birthday.month, date.today().month)
        self.assertEqual(ctx.player.birthday.day, date.today().day)

    async def test_explicit_date_derives_birthday_year_from_age(self):
        ctx = _FakeCtx(responses=['40', 'a', '6', '16'])
        ok = await _choose_age(ctx)
        self.assertTrue(ok)
        self.assertEqual(ctx.player.age, 40)
        self.assertEqual(ctx.player.birthday.year, date.today().year - 40)
        self.assertEqual(ctx.player.birthday.month, 6)
        self.assertEqual(ctx.player.birthday.day, 16)


if __name__ == '__main__':
    unittest.main(verbosity=2)
