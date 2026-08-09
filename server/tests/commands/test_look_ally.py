"""tests/commands/test_look_ally.py

Covers commands/look.py's ally-lookup branch (Ryan, 8/1/26): LOOK <ally
name> gives simple flavor text for a party member, with a MOUNT ally
(AllyFlags.MOUNT) additionally naming its gender/breed/colour --
base_classes.HorseBreed/HorseColor, assigned on capture by
ally_events/capture_horse.py.
"""
from __future__ import annotations

import unittest

from bar.ally_data import Ally, AllyFlags
from base_classes import Gender, HorseBreed, HorseColor
from commands.look import LookCommand
from inventory import Inventory
from player import Player


class _FakeClient:
    room = None


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.client = _FakeClient()
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        pass


def _player_with_ally(ally: Ally) -> Player:
    p = Player(name='Rulan')
    p.inventory = Inventory(capacity=10)
    p.party.add_member(p, ally)
    return p


class TestLookAtMount(unittest.IsolatedAsyncioTestCase):

    async def test_shows_gender_breed_and_colour(self):
        mount = Ally(name='SILVER', gender='f', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT])
        mount.breed = HorseBreed.ARABIAN
        mount.color = HorseColor.PALOMINO
        ctx = _FakeCtx(_player_with_ally(mount))

        result = await LookCommand().execute(ctx, 'SILVER')

        self.assertTrue(result.success)
        self.assertIn('SILVER is a female Palomino Arabian.', ctx.sent)

    async def test_male_mount(self):
        mount = Ally(name='THUNDER', gender='m', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT])
        mount.breed = HorseBreed.MUSTANG
        mount.color = HorseColor.BLACK
        ctx = _FakeCtx(_player_with_ally(mount))

        await LookCommand().execute(ctx, 'THUNDER')

        self.assertIn('THUNDER is a male Black Mustang.', ctx.sent)

    async def test_matches_by_case_insensitive_substring(self):
        mount = Ally(name='SILVER', gender='f', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT])
        mount.breed = HorseBreed.ARABIAN
        mount.color = HorseColor.PALOMINO
        ctx = _FakeCtx(_player_with_ally(mount))

        await LookCommand().execute(ctx, 'silver')

        self.assertIn('SILVER is a female Palomino Arabian.', ctx.sent)

    async def test_legacy_mount_without_breed_or_colour(self):
        # A mount saved before breed/color existed -- fields default to None.
        mount = Ally(name='OLDNAG', gender='m', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT])
        ctx = _FakeCtx(_player_with_ally(mount))

        await LookCommand().execute(ctx, 'OLDNAG')

        self.assertIn('OLDNAG is a male horse.', ctx.sent)

    async def test_no_saddlebags(self):
        mount = Ally(name='SILVER', gender='f', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT])
        ctx = _FakeCtx(_player_with_ally(mount))

        await LookCommand().execute(ctx, 'SILVER')

        self.assertIn('SILVER has no saddlebags.', ctx.sent)

    async def test_empty_saddlebags_look_thin(self):
        mount = Ally(name='SILVER', gender='f', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT, AllyFlags.SADDLEBAGS])
        mount.items = []
        ctx = _FakeCtx(_player_with_ally(mount))

        await LookCommand().execute(ctx, 'SILVER')

        self.assertIn('SILVER has saddlebags strapped on, looking a bit thin.', ctx.sent)

    async def test_partly_full_saddlebags(self):
        from bar.ally_data import add_ally_item
        from items import Item, ItemCategory

        mount = Ally(name='SILVER', gender='f', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT, AllyFlags.SADDLEBAGS])
        add_ally_item(mount, Item(id_number=1, name='Rope', category=ItemCategory.ITEM))
        ctx = _FakeCtx(_player_with_ally(mount))

        await LookCommand().execute(ctx, 'SILVER')

        self.assertIn('SILVER has saddlebags strapped on, looking comfortably full.', ctx.sent)

    async def test_full_saddlebags_look_fat(self):
        from bar.ally_data import add_ally_item
        from commands.give import _MOUNT_CAPACITY_WITH_SADDLEBAGS
        from items import Item, ItemCategory

        mount = Ally(name='SILVER', gender='f', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT, AllyFlags.SADDLEBAGS])
        for i in range(_MOUNT_CAPACITY_WITH_SADDLEBAGS):
            add_ally_item(mount, Item(id_number=i, name=f'Item{i}', category=ItemCategory.ITEM))
        ctx = _FakeCtx(_player_with_ally(mount))

        await LookCommand().execute(ctx, 'SILVER')

        self.assertIn('SILVER has saddlebags strapped on, looking fat and well-packed.', ctx.sent)


class TestLookAtNonMountAlly(unittest.IsolatedAsyncioTestCase):

    async def test_generic_ally_description(self):
        ally = Ally(name='BARDA', gender='f', strength=10, to_hit=5, flags=[])
        ctx = _FakeCtx(_player_with_ally(ally))

        result = await LookCommand().execute(ctx, 'BARDA')

        self.assertTrue(result.success)
        self.assertIn('BARDA is here with you, ready to help.', ctx.sent)


if __name__ == '__main__':
    unittest.main()
