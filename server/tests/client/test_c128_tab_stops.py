"""tests/client/test_c128_tab_stops.py

Covers the Commodore 128 hardware tab-stop sync: a real 128's screen
editor has exactly two tab-related escape codes (ESC-Y "Define tab as
eight spaces", ESC-Z "Clear tab") -- no per-column set/clear like a
VT100's HTS/TBC, just one global on/off hardcoded to an 8-column grid
(see assembly-language/client/128_CLIENT_MECHANICS.md for the citation).

terminal.c128_tab_sync_bytes() returns the ESC-Y bytes and forces
tab_settings to match (has_tab_key=True, tab_width=8) whenever a player
is on the "Commodore 128" Client Type preset. commands/prefs.py's
_pick_client_type() sends that live when switching onto the preset, and
ESC-Z when switching away from it -- gated on the preset label
specifically, not just ClientSettings.has_tab (also true for TADA
Client/ANSI/Custom, none of which understand these escape codes).

Run with:
    python -m pytest tests/client/test_c128_tab_stops.py -v
"""
from __future__ import annotations

import unittest

from player import Player
from network_context import PETSCIINetworkContext
from terminal import C128_ESC_CLEAR_TAB, C128_ESC_DEFINE_TAB, c128_tab_sync_bytes
from commands.prefs import _pick_client_type


class TestC128TabSyncBytes(unittest.TestCase):

    def test_returns_esc_y_bytes(self):
        player = Player()
        self.assertEqual(c128_tab_sync_bytes(player.client_settings), bytes([27, ord('Y')]))

    def test_forces_has_tab_key_and_width_8(self):
        player = Player()
        player.client_settings.tab_settings.has_tab_key = False
        player.client_settings.tab_settings.tab_width = 4
        c128_tab_sync_bytes(player.client_settings)
        self.assertTrue(player.client_settings.tab_settings.has_tab_key)
        self.assertEqual(player.client_settings.tab_settings.tab_width, 8)

    def test_creates_tab_settings_if_missing(self):
        player = Player()
        player.client_settings.tab_settings = None
        c128_tab_sync_bytes(player.client_settings)
        self.assertIsNotNone(player.client_settings.tab_settings)
        self.assertTrue(player.client_settings.tab_settings.has_tab_key)


class _FakePetsciiCtx(PETSCIINetworkContext):
    """Real PETSCIINetworkContext (isinstance is what _pick_client_type()
    actually checks) with fake send()/prompt()/send_raw() for testing --
    same pattern as test_prefs_client_type.py's own fake, plus a
    send_raw() capture that one doesn't need."""

    def __init__(self, responses, player):
        super().__init__(player=player, reader=None, writer=None, server=None, client=None)
        self._q = list(responses)
        self.sent: list = []
        self.raw_sent: list[bytes] = []

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def send_raw(self, data: bytes) -> None:
        self.raw_sent.append(data)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None


class TestPickClientTypeLiveSync(unittest.IsolatedAsyncioTestCase):

    async def test_switching_to_c128_sends_esc_y_and_forces_tab_settings(self):
        player = Player()
        player.client_settings.tab_settings.has_tab_key = False
        player.client_settings.tab_settings.tab_width = 4
        ctx = _FakePetsciiCtx(['2'], player)  # preset '2' = Commodore 128, 40x25
        await _pick_client_type(ctx)
        self.assertIn(C128_ESC_DEFINE_TAB, ctx.raw_sent)
        self.assertTrue(player.client_settings.tab_settings.has_tab_key)
        self.assertEqual(player.client_settings.tab_settings.tab_width, 8)

    async def test_switching_away_from_c128_sends_esc_z(self):
        player = Player()
        player.client_settings.has_tab = True  # simulate already on a C128 preset
        ctx = _FakePetsciiCtx(['1'], player)  # preset '1' = Commodore 64 (PETSCII)
        await _pick_client_type(ctx)
        self.assertIn(C128_ESC_CLEAR_TAB, ctx.raw_sent)

    async def test_switching_between_c64_presets_sends_no_escape_bytes(self):
        player = Player()
        player.client_settings.has_tab = False  # already C64, not C128
        ctx = _FakePetsciiCtx(['1'], player)  # preset '1' = Commodore 64 (PETSCII)
        await _pick_client_type(ctx)
        self.assertEqual(ctx.raw_sent, [])

    async def test_re_picking_c128_while_already_on_it_resends_esc_y(self):
        player = Player()
        player.client_settings.has_tab = True  # already on a C128 preset
        ctx = _FakePetsciiCtx(['2'], player)  # preset '2' = Commodore 128, 40x25 again
        await _pick_client_type(ctx)
        # Idempotent re-send is fine (matches connect.py's login-time
        # unconditional send) -- no special-casing "already there".
        self.assertIn(C128_ESC_DEFINE_TAB, ctx.raw_sent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
