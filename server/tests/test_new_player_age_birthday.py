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
from commands.new_player import _choose_age, _parse_month


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

    async def test_month_name_prefix_accepted(self):
        """Ryan: the month prompt should accept at least the first three
        letters of the month name, not just a number."""
        ctx = _FakeCtx(responses=['40', 'a', 'sep', '16'])
        ok = await _choose_age(ctx)
        self.assertTrue(ok)
        self.assertEqual(ctx.player.birthday.month, 9)

    async def test_month_intro_text_mentions_both_options(self):
        ctx = _FakeCtx(responses=['40', 'a', '6', '16'])
        await _choose_age(ctx)
        text = '\n'.join(ctx.sent)
        self.assertIn('first three letters', text)


class TestParseMonth(unittest.TestCase):

    def test_numeric_in_range(self):
        self.assertEqual(_parse_month('6'), 6)
        self.assertEqual(_parse_month('12'), 12)

    def test_numeric_out_of_range_returns_none(self):
        self.assertIsNone(_parse_month('0'))
        self.assertIsNone(_parse_month('13'))

    def test_three_letter_prefix_case_insensitive(self):
        self.assertEqual(_parse_month('Jan'), 1)
        self.assertEqual(_parse_month('DEC'), 12)
        self.assertEqual(_parse_month('sep'), 9)

    def test_full_month_name(self):
        self.assertEqual(_parse_month('September'), 9)

    def test_too_short_returns_none(self):
        self.assertIsNone(_parse_month('ja'))

    def test_blank_or_garbage_returns_none(self):
        self.assertIsNone(_parse_month(''))
        self.assertIsNone(_parse_month('xyz'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
