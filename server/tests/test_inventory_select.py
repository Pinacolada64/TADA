"""tests/test_inventory_select.py

Unit tests for inventory_select.py -- the shared "pick an item of type X"
helper that READY / UNREADY (and, later, USE / DROP) build their numbered
lists and selection prompts on.

Run with:
    python -m pytest tests/test_inventory_select.py -v
"""
from __future__ import annotations

import unittest

from inventory import Inventory
from inventory_select import (
    ItemChoice,
    gather_items,
    owner_has_readied,
    resolve_or_prompt,
    same_item,
)
from items import Item, ItemCategory


def _weapon(name, item_id=1):
    return Item(id_number=item_id, name=name, category=ItemCategory.WEAPON)


def _thing(name, item_id=1):
    return Item(id_number=item_id, name=name, category=ItemCategory.ITEM)


class _FakeAlly:
    def __init__(self, name, items=None, readied_weapon=None):
        self.name = name
        self.items = list(items or [])
        self.readied_weapon = readied_weapon
        self.status = None


class _FakeParty:
    def __init__(self, members):
        self.members = members


class _FakePlayer:
    def __init__(self, items=None, readied_weapon=None, party=None):
        self.inventory = Inventory()
        for it in (items or []):
            self.inventory.add(it)
        self.readied_weapon = readied_weapon
        self.party = party
        self.return_key = 'RETURN'


class _FakeCtx:
    def __init__(self, player, answers=()):
        self.player = player
        self._sent: list[str] = []
        self._answers = iter(answers)

    async def send(self, msg, **kw):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def prompt(self, *a, **kw):
        return next(self._answers, None)

    def sent(self):
        return '\n'.join(self._sent)


# ---------------------------------------------------------------------------
# same_item / owner_has_readied
# ---------------------------------------------------------------------------

class TestSameItem(unittest.TestCase):
    def test_identity(self):
        w = _weapon('SWORD')
        self.assertTrue(same_item(w, w))

    def test_same_id_same_category(self):
        self.assertTrue(same_item(_weapon('SWORD', 5), _weapon('SWORD', 5)))

    def test_same_id_different_category_is_not_a_match(self):
        # id_number is only unique within a category (weapons/items/rations
        # each count from 1) -- weapon #5 must not equal item #5.
        self.assertFalse(same_item(_weapon('SWORD', 5), _thing('POTION', 5)))

    def test_none(self):
        self.assertFalse(same_item(None, _weapon('SWORD')))

    def test_owner_has_readied(self):
        w = _weapon('AXE', 9)
        ally = _FakeAlly('Alan', readied_weapon=_weapon('AXE', 9))
        self.assertTrue(owner_has_readied(ally, w))
        self.assertFalse(owner_has_readied(_FakeAlly('Bo'), w))


# ---------------------------------------------------------------------------
# gather_items
# ---------------------------------------------------------------------------

class TestGatherItems(unittest.TestCase):
    def test_player_only_no_filter(self):
        p = _FakePlayer(items=[_weapon('SWORD', 1), _thing('LANTERN', 2)])
        got = gather_items(p)
        self.assertEqual([c.name for c in got], ['SWORD', 'LANTERN'])
        self.assertTrue(all(c.owner is None for c in got))

    def test_category_filter(self):
        p = _FakePlayer(items=[_weapon('SWORD', 1), _thing('LANTERN', 2)])
        got = gather_items(p, category=ItemCategory.WEAPON)
        self.assertEqual([c.name for c in got], ['SWORD'])

    def test_predicate_anded_with_category(self):
        p = _FakePlayer(items=[_weapon('LONG SWORD', 1), _weapon('SHORT BOW', 2)])
        got = gather_items(p, category=ItemCategory.WEAPON,
                           predicate=lambda it: 'BOW' in it.name)
        self.assertEqual([c.name for c in got], ['SHORT BOW'])

    def test_predicate_alone_no_category(self):
        # How USE selects: no category, a "not a weapon" predicate.
        p = _FakePlayer(items=[_weapon('SWORD', 1), _thing('LANTERN', 2),
                               _thing('COMPASS', 3)])
        not_weapon = lambda it: str(it.category) != str(ItemCategory.WEAPON)
        got = gather_items(p, predicate=not_weapon)
        self.assertEqual([c.name for c in got], ['LANTERN', 'COMPASS'])

    def test_readied_flag_set_for_player(self):
        w = _weapon('SWORD', 1)
        p = _FakePlayer(items=[w], readied_weapon=w)
        got = gather_items(p, category=ItemCategory.WEAPON)
        self.assertTrue(got[0].readied)

    def test_include_allies_appends_after_player_grouped_by_ally(self):
        pw = _weapon('SWORD', 1)
        aw1 = _weapon('AXE', 2)
        aw2 = _weapon('MACE', 3)
        alan = _FakeAlly('Alan', items=[_make_entry(aw1)], readied_weapon=aw1)
        bo = _FakeAlly('Bo', items=[_make_entry(aw2)])
        p = _FakePlayer(items=[pw], party=_FakeParty([alan, bo]))
        got = gather_items(p, category=ItemCategory.WEAPON, include_allies=True,
                           allies=[alan, bo])
        self.assertEqual([c.name for c in got], ['SWORD', 'AXE', 'MACE'])
        self.assertEqual([c.owner_name for c in got], ['You', 'Alan', 'Bo'])
        # the ally's readied weapon carries the flag
        self.assertTrue(got[1].readied)
        self.assertFalse(got[2].readied)

    def test_include_player_false(self):
        aw = _weapon('AXE', 2)
        alan = _FakeAlly('Alan', items=[_make_entry(aw)])
        p = _FakePlayer(items=[_weapon('SWORD', 1)], party=_FakeParty([alan]))
        got = gather_items(p, category=ItemCategory.WEAPON,
                           include_player=False, include_allies=True,
                           allies=[alan])
        self.assertEqual([c.name for c in got], ['AXE'])


class _Entry:
    def __init__(self, item):
        self.item = item


def _make_entry(item):
    return _Entry(item)


# ---------------------------------------------------------------------------
# resolve_or_prompt
# ---------------------------------------------------------------------------

class TestResolveOrPrompt(unittest.IsolatedAsyncioTestCase):
    def _choices(self):
        return [
            ItemChoice(item=_weapon('LONG SWORD', 1)),
            ItemChoice(item=_weapon('SHORT SWORD', 2)),
            ItemChoice(item=_weapon('BATTLE AXE', 3)),
        ]

    async def test_name_unique_match_returns_without_prompt(self):
        ctx = _FakeCtx(_FakePlayer())
        got = await resolve_or_prompt(
            ctx, self._choices(), args=['axe'], prompt_text='Ready which',
            label_fn=lambda c: c.name)
        self.assertEqual(got.name, 'BATTLE AXE')
        self.assertEqual(ctx.sent(), '')  # nothing printed

    async def test_name_no_match_sends_custom_message(self):
        ctx = _FakeCtx(_FakePlayer())
        got = await resolve_or_prompt(
            ctx, self._choices(), args=['mace'], prompt_text='Ready which',
            label_fn=lambda c: c.name,
            no_match_msg=lambda q: f'No weapon or ally matching "{q}".')
        self.assertIsNone(got)
        self.assertIn('No weapon or ally matching "mace".', ctx.sent())

    async def test_name_ambiguous_prompts_and_picks(self):
        ctx = _FakeCtx(_FakePlayer(), answers=['2'])
        got = await resolve_or_prompt(
            ctx, self._choices(), args=['sword'], prompt_text='Ready which',
            label_fn=lambda c: c.name, ambiguous_header='Which weapon?')
        self.assertEqual(got.name, 'SHORT SWORD')
        self.assertIn('Which weapon?', ctx.sent())
        self.assertIn('1. LONG SWORD', ctx.sent())
        self.assertIn('2. SHORT SWORD', ctx.sent())

    async def test_full_list_numbered_pick(self):
        ctx = _FakeCtx(_FakePlayer(), answers=['3'])
        got = await resolve_or_prompt(
            ctx, self._choices(), args=[], prompt_text='Ready which weapon',
            label_fn=lambda c: c.name, list_header='Weapons:')
        self.assertEqual(got.name, 'BATTLE AXE')
        self.assertIn('Weapons:', ctx.sent())

    async def test_blank_reply_is_a_silent_cancel(self):
        ctx = _FakeCtx(_FakePlayer(), answers=[''])
        got = await resolve_or_prompt(
            ctx, self._choices(), args=[], prompt_text='x',
            label_fn=lambda c: c.name)
        self.assertIsNone(got)

    async def test_out_of_range_reply_sends_invalid(self):
        ctx = _FakeCtx(_FakePlayer(), answers=['9'])
        got = await resolve_or_prompt(
            ctx, self._choices(), args=[], prompt_text='x',
            label_fn=lambda c: c.name)
        self.assertIsNone(got)
        self.assertIn('Invalid selection.', ctx.sent())

    async def test_non_numeric_reply_sends_invalid(self):
        ctx = _FakeCtx(_FakePlayer(), answers=['huh'])
        got = await resolve_or_prompt(
            ctx, self._choices(), args=[], prompt_text='x',
            label_fn=lambda c: c.name)
        self.assertIsNone(got)
        self.assertIn('Invalid selection.', ctx.sent())

    async def test_invalid_msg_override(self):
        # USE keeps SPUR's "You don't have that item." for a bad pick.
        ctx = _FakeCtx(_FakePlayer(), answers=['9'])
        got = await resolve_or_prompt(
            ctx, self._choices(), args=[], prompt_text='Use which item',
            label_fn=lambda c: c.name,
            invalid_msg="You don't have that item.")
        self.assertIsNone(got)
        self.assertIn("You don't have that item.", ctx.sent())
        self.assertNotIn('Invalid selection.', ctx.sent())

    async def test_empty_choices_returns_none(self):
        ctx = _FakeCtx(_FakePlayer())
        got = await resolve_or_prompt(
            ctx, [], args=[], prompt_text='x', label_fn=lambda c: c.name)
        self.assertIsNone(got)

    async def test_auto_select_single_skips_menu(self):
        ctx = _FakeCtx(_FakePlayer())
        one = [ItemChoice(item=_weapon('ONLY BLADE', 1))]
        got = await resolve_or_prompt(
            ctx, one, args=[], prompt_text='x', label_fn=lambda c: c.name,
            auto_select_single=True)
        self.assertEqual(got.name, 'ONLY BLADE')
        self.assertEqual(ctx.sent(), '')

    async def test_auto_select_single_off_by_default_shows_menu(self):
        ctx = _FakeCtx(_FakePlayer(), answers=['1'])
        one = [ItemChoice(item=_weapon('ONLY BLADE', 1))]
        got = await resolve_or_prompt(
            ctx, one, args=[], prompt_text='x', label_fn=lambda c: c.name)
        self.assertEqual(got.name, 'ONLY BLADE')
        self.assertIn('1. ONLY BLADE', ctx.sent())

    async def test_group_fn_sections_full_list_with_continuous_numbering(self):
        ctx = _FakeCtx(_FakePlayer(), answers=['3'])
        choices = [
            ItemChoice(item=_weapon('SWORD', 1)),
            ItemChoice(item=_weapon('AXE', 2), owner=_FakeAlly('Alan')),
            ItemChoice(item=_weapon('MACE', 3), owner=_FakeAlly('Bo')),
        ]
        got = await resolve_or_prompt(
            ctx, choices, args=[], prompt_text='Ready which weapon',
            label_fn=lambda c: (f'{c.owner_name}: {c.name}' if c.is_ally else c.name),
            group_fn=lambda c: ("Your allies' weapons:" if c.is_ally
                                else 'Weapons you carry:'))
        out = ctx.sent()
        self.assertIn('Weapons you carry:', out)
        self.assertIn("Your allies' weapons:", out)
        self.assertIn('1. SWORD', out)
        self.assertIn('2. Alan: AXE', out)
        self.assertIn('3. Bo: MACE', out)
        self.assertEqual(got.name, 'MACE')


if __name__ == '__main__':
    unittest.main()
