"""tests/commands/test_get_unconscious.py

Covers commands/get.py's `_try_get_living()` player-target branch
(SPUR.MISC.S get.plyr): GETting a conscious player says "skuttles out
of reach!"; GETting an Unconscious one (PlayerFlags.UNCONSCIOUS -- a
duel loss, see combat/duel.py's DuelSession._end()) says "won't fit in
your sack.." instead (sentence-case per this port's convention, not
SPUR's screaming caps). Previously this branch keyed off hit_points<=0,
which a duel loss never actually produces (loser is left at 15 HP, not
0) -- the real SPUR distinction is unconscious vs. not.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.get import GetCommand
from flags import PlayerFlags
from player import Player


def _room_client(player, room_no=1):
    c = MagicMock()
    c.room = room_no
    c.player = player
    return c


def _make_ctx(viewer, room_no, other_clients):
    ctx = MagicMock()
    ctx.player = viewer
    ctx.client.room = room_no
    ctx.server.clients = {f'c{i}': c for i, c in enumerate(other_clients)}
    ctx.server.monsters = []
    ctx.send = AsyncMock()
    return ctx


class TestGetLivingPlayerTarget(unittest.IsolatedAsyncioTestCase):
    async def test_conscious_player_skuttles_out_of_reach(self):
        viewer = Player(name='Rulan')
        target = Player(name='Belwin')
        other_client = _room_client(target)
        ctx = _make_ctx(viewer, room_no=1, other_clients=[other_client])

        await GetCommand()._try_get_living(ctx, 'belwin')
        sent = '\n'.join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn('skuttles out of reach', sent.lower())
        self.assertNotIn("won't fit", sent.lower())

    async def test_unconscious_player_wont_fit_in_sack(self):
        viewer = Player(name='Rulan')
        target = Player(name='Belwin')
        target.set_flag(PlayerFlags.UNCONSCIOUS)
        other_client = _room_client(target)
        ctx = _make_ctx(viewer, room_no=1, other_clients=[other_client])

        await GetCommand()._try_get_living(ctx, 'belwin')
        sent = '\n'.join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("won't fit in your sack", sent.lower())
        self.assertNotIn('skuttles', sent.lower())


if __name__ == '__main__':
    unittest.main()
