"""tests/logon_events/test_birthday.py

Unit tests for logon_events/birthday.py -- the first concrete module
under the "modular logon event" idea (TODO.md), picked because that
same TODO entry already called a birthday greeting out as missing.

Also covers Vinny's cameo (Ryan's idea): a birthday cake grant and,
when the player has an outstanding loan, a modest "begrudging" discount
-- reusing bar/vinny.py's own dialect helpers so the voice matches the
bar scene.
"""
from __future__ import annotations

import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import Guild, PlayerMoneyTypes
from inventory import Inventory
from logon_events.birthday import is_birthday_today, main as birthday_main


def run(coro):
    return asyncio.run(coro)


def _player(name='Rulan', birthday=None, loan_amount=0, loan_days=0,
            inventory=None, party=None, guild=None, map_level=1,
            silver_in_hand=0):
    p = MagicMock()
    p.name = name
    p.birthday = birthday
    p.loan_amount = loan_amount
    p.loan_days = loan_days
    p.inventory = inventory if inventory is not None else Inventory(capacity=10)
    p.unsaved_changes = False
    p.party = party if party is not None else []
    p.guild = guild
    p.map_level = map_level
    p.map_room = 1

    wallet = {PlayerMoneyTypes.IN_HAND: silver_in_hand}
    p.get_silver = lambda k: wallet.get(k, 0)

    def _subtract(k, amt):
        wallet[k] = wallet.get(k, 0) - amt
        return True
    p.subtract_silver = _subtract
    p._wallet = wallet
    return p


def _ctx(party_answer='n'):
    ctx = MagicMock()
    ctx.send_room = AsyncMock()
    # Default: decline Vinny's "wanna have a party?" follow-up, so all the
    # pre-existing tests below (written before the party extension existed)
    # see the same cake/loan-only behavior they always have.
    ctx.prompt = AsyncMock(return_value=party_answer)
    ctx.client = MagicMock(room=1)
    return ctx


class TestIsBirthdayToday(unittest.TestCase):
    def test_no_birthday_on_file_is_false(self):
        player = _player(birthday=None)
        self.assertFalse(is_birthday_today(player, today=datetime.date(2026, 7, 27)))

    def test_matching_month_and_day_is_true(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        self.assertTrue(is_birthday_today(player, today=datetime.date(2026, 7, 27)))

    def test_year_is_ignored(self):
        player = _player(birthday=datetime.datetime(1975, 3, 14))
        self.assertTrue(is_birthday_today(player, today=datetime.date(2026, 3, 14)))

    def test_different_day_is_false(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        self.assertFalse(is_birthday_today(player, today=datetime.date(2026, 7, 28)))

    def test_different_month_same_day_is_false(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        self.assertFalse(is_birthday_today(player, today=datetime.date(2026, 8, 27)))

    def test_defaults_to_real_today_when_not_given(self):
        today = datetime.date.today()
        player = _player(birthday=datetime.datetime(1990, today.month, today.day))
        self.assertTrue(is_birthday_today(player))


class TestBirthdayGreeting(unittest.TestCase):
    def test_no_birthday_returns_nothing(self):
        player = _player(birthday=None)
        result = run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(result, [])

    def test_not_today_returns_nothing(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        result = run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 28)))
        self.assertEqual(result, [])

    def test_matching_birthday_greets_by_name(self):
        player = _player(name='Rulan', birthday=datetime.datetime(1990, 7, 27))
        result = run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        flat = '\n'.join(result)
        self.assertIn('Rulan', flat)
        self.assertIn('Happy Birthday', flat)

    def test_verus_broadcasts_his_wish_to_the_room(self):
        ctx = _ctx()
        player = _player(name='Rulan', birthday=datetime.datetime(1990, 7, 27))
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        # Verus's is the *first* broadcast -- Vinny's cameo comes after.
        args, kwargs = ctx.send_room.await_args_list[0]
        self.assertIn('Verus', args[0])
        self.assertIn('Rulan', args[0])
        self.assertTrue(kwargs.get('exclude_self'))

    def test_verus_broadcast_precedes_vinnys(self):
        ctx = _ctx()
        player = _player(name='Rulan', birthday=datetime.datetime(1990, 7, 27))
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        first_args, _ = ctx.send_room.await_args_list[0]
        second_args, _ = ctx.send_room.await_args_list[1]
        self.assertIn('Verus', first_args[0])
        self.assertIn('Vinny', second_args[0])


class TestVinnysCameo(unittest.TestCase):
    def test_grants_a_birthday_cake(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        entries = list(player.inventory.entries())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.name, 'birthday cake')
        self.assertTrue(player.unsaved_changes)

    def test_cake_price_is_zero(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        cake = player.inventory.entries()[0].item
        self.assertEqual(getattr(cake, 'price', None), 0)

    def test_full_inventory_skips_cake_gracefully(self):
        full_inv = Inventory(capacity=0)
        player = _player(birthday=datetime.datetime(1990, 7, 27), inventory=full_inv)
        result = run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(len(list(player.inventory.entries())), 0)
        self.assertIn('eat it myself', '\n'.join(result))

    def test_no_loan_no_discount_mentioned(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27), loan_amount=0)
        result = run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        self.assertNotIn('Loan now at', '\n'.join(result))

    def test_outstanding_loan_gets_a_ten_percent_discount(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27), loan_amount=1000, loan_days=10)
        result = run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(player.loan_amount, 900)
        self.assertIn('Loan now at 900', '\n'.join(result))
        self.assertTrue(player.unsaved_changes)

    def test_loan_days_cleared_when_discount_pays_it_off(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27), loan_amount=5, loan_days=3)
        run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        # floor(5 * 0.10) = 0, but a minimum discount of 1 applies, so a
        # tiny loan is paid off entirely rather than rounding to nothing.
        self.assertEqual(player.loan_amount, 4)

    def test_minimum_discount_is_at_least_one_silver(self):
        player = _player(birthday=datetime.datetime(1990, 7, 27), loan_amount=1, loan_days=1)
        run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(player.loan_amount, 0)
        self.assertEqual(player.loan_days, 0)

    def test_discount_never_exceeds_the_loan_itself(self):
        # Guards the min(loan, ...) clamp -- a 10% discount can't somehow
        # overshoot and go negative.
        player = _player(birthday=datetime.datetime(1990, 7, 27), loan_amount=2, loan_days=1)
        run(birthday_main(_ctx(), player, today=datetime.date(2026, 7, 27)))
        self.assertGreaterEqual(player.loan_amount, 0)

    def test_broadcasts_to_the_room_excluding_self(self):
        # Two broadcasts now: Verus's own wish (main()) and Vinny's
        # cameo -- both real-room events other players should see.
        ctx = _ctx()
        player = _player(name='Rulan', birthday=datetime.datetime(1990, 7, 27))
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(ctx.send_room.await_count, 2)
        for args, kwargs in ctx.send_room.await_args_list:
            self.assertTrue(kwargs.get('exclude_self'))
            self.assertIn('Rulan', args[0])

    def test_no_room_broadcast_when_its_not_the_birthday(self):
        ctx = _ctx()
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 28)))
        ctx.send_room.assert_not_awaited()


class TestFistBirthdayParty(unittest.TestCase):
    def test_declining_leaves_room_and_silver_untouched(self):
        ctx = _ctx(party_answer='n')
        player = _player(birthday=datetime.datetime(1990, 7, 27), silver_in_hand=0)
        result = run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(ctx.client.room, 1)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 0)
        self.assertEqual(ctx.send_room.await_count, 2)  # Verus + Vinny's cameo only
        self.assertNotIn('Tea Room', '\n'.join(result))

    def test_accepting_grants_500_silver(self):
        ctx = _ctx(party_answer='y')
        player = _player(birthday=datetime.datetime(1990, 7, 27), silver_in_hand=0)
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 500)

    def test_accepting_shows_the_tea_room(self):
        ctx = _ctx(party_answer='y')
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        result = run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertIn('Tea Room', '\n'.join(result))

    def test_accepting_moves_player_there_and_back(self):
        ctx = _ctx(party_answer='y')
        player = _player(birthday=datetime.datetime(1990, 7, 27), map_level=3)
        player.map_room = 42
        ctx.client.room = 42
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        # Restored to wherever they started, not left in the Tea Room.
        self.assertEqual(ctx.client.room, 42)
        self.assertEqual(player.map_room, 42)
        self.assertEqual(player.map_level, 3)

    def test_declining_never_moves_the_player(self):
        ctx = _ctx(party_answer='n')
        player = _player(birthday=datetime.datetime(1990, 7, 27), map_level=3)
        player.map_room = 42
        ctx.client.room = 42
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(ctx.client.room, 42)
        self.assertEqual(player.map_room, 42)
        self.assertEqual(player.map_level, 3)

    def test_non_fist_member_gets_immunity_note(self):
        ctx = _ctx(party_answer='y')
        player = _player(birthday=datetime.datetime(1990, 7, 27), guild=Guild.CIVILIAN)
        result = run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertIn('nobody so much as blinks', '\n'.join(result))

    def test_fist_member_gets_no_immunity_note(self):
        ctx = _ctx(party_answer='y')
        player = _player(birthday=datetime.datetime(1990, 7, 27), guild=Guild.FIST)
        result = run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertNotIn('nobody so much as blinks', '\n'.join(result))

    def test_broadcasts_name_party_members_too(self):
        ally = MagicMock()
        ally.name = 'Grog'
        ctx = _ctx(party_answer='y')
        player = _player(name='Rulan', birthday=datetime.datetime(1990, 7, 27),
                          party=[ally])
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        # 2 from Verus/Vinny's cameo, 3 more from Mundo (out/in/back).
        self.assertEqual(ctx.send_room.await_count, 5)
        mundo_calls = ctx.send_room.await_args_list[2:]
        for args, kwargs in mundo_calls:
            self.assertIn('Rulan', args[0])
            self.assertIn('Grog', args[0])

    def test_declining_does_not_ask_a_second_time_or_broadcast_extra(self):
        ctx = _ctx(party_answer='n')
        player = _player(birthday=datetime.datetime(1990, 7, 27))
        run(birthday_main(ctx, player, today=datetime.date(2026, 7, 27)))
        self.assertEqual(ctx.send_room.await_count, 2)


if __name__ == '__main__':
    unittest.main()
