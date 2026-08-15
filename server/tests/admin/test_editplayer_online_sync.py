#!/usr/bin/env python3
"""tests/admin/test_editplayer_online_sync.py

Regression test for a live-sync bug in EditPlayerCommand: editing an
*online* player used to build its edit buffer from that player's on-disk
save file, which only reflects their state as of their last save (e.g.
login) -- not anything picked up/changed during the current live session.
Saving the edit buffer back over that stale file, then reloading the live
session from it, silently reverted the connected player's actual live
progress (inventory, in this scenario) to the stale snapshot.

Found live: an admin ran `ep` on a player who was online and had picked
up an item that session; the item vanished from her live inventory
afterward even though the admin never touched inventory at all.

Fix: commands/editplayer.py now force-saves the live player's *current*
in-memory state to disk before building the edit buffer, so there's no
stale snapshot to overwrite or reload from.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import net_common
from commands.editplayer import EditPlayerCommand
from flags import PlayerFlags
from items import Item, ItemCategory
from player import Player


class _FakeCtx:
    def __init__(self, responses=None, player=None, server=None):
        self._q = list(responses or [])
        self.sent: list[str] = []
        self.player = player
        self.server = server or SimpleNamespace(weapons=[], clients={})

    async def send(self, *args) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                self.sent.extend(str(x) for x in a)
            else:
                self.sent.append(str(a))

    async def prompt(self, prompt_text: str = '', preamble_lines=None) -> str:
        if preamble_lines:
            await self.send(preamble_lines)
        return self._q.pop(0) if self._q else ''


class TestEditPlayerOnlineLiveSync(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_run_dir = net_common.run_server_dir
        net_common.run_server_dir = self._tmp.name
        self.addCleanup(lambda: setattr(net_common, 'run_server_dir', self._orig_run_dir))

    async def test_online_edit_does_not_revert_unsaved_live_inventory(self):
        # Gadget logs in and her initial state gets saved (e.g. at login).
        live_player = Player(name='Gadget', id='Gadget')
        live_player.save(force=True)

        # She plays and picks up an item -- held only in memory, same as a
        # real session between autosaves/quit.
        live_player.inventory.add(Item(id_number=99, name='MAGIC RING', category=ItemCategory.ITEM))
        self.assertTrue(live_player.inventory.find(name='MAGIC RING'))

        # An admin runs `ep gadget` while she's online and toggles an
        # unrelated flag (Expert Mode, main menu item 7 -> flag 1), then
        # confirms the save prompt.
        admin = Player(name='Railbender', id='Railbender')
        live_ctx = _FakeCtx(player=live_player)
        other_client = SimpleNamespace(ctx=live_ctx)
        ctx = _FakeCtx(
            player=admin,
            server=SimpleNamespace(weapons=[], clients={'addr1': other_client}),
            responses=['7', '1', '', '', 'y'],
        )

        result = await EditPlayerCommand().execute(ctx, 'gadget')
        self.assertTrue(result.success)

        # The admin's edit landed...
        self.assertTrue(live_player.query_flag(PlayerFlags.EXPERT_MODE))
        # ...and her live-picked-up item survived the round trip instead of
        # being reverted to the stale pre-session snapshot.
        self.assertTrue(live_player.inventory.find(name='MAGIC RING'))


if __name__ == '__main__':
    unittest.main()
