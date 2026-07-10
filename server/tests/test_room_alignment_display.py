"""tests/test_room_alignment_display.py

Unit tests for base_classes.room_alignment_label(), formatting.guild_sigil_for(),
and their use in simple_server.py's _describe_room():

  - Regression: room.alignment used to be interpolated directly into the
    room-name line (f'[{alignment}]'), showing the raw enum value
    ("free_fire") instead of anything readable.
  - Regression: NEUTRAL (the default for nearly every ordinary room) was
    truthy and got displayed too ("[neutral]" on almost every room in the
    game), even though RoomAlignment's own docstring calls it "no marker".
  - guild_sigil_for() renders a colorized, terminal-appropriate sigil
    ('|token|...|reset|') instead of an English label -- different glyphs
    for ANSI/ASCII vs PETSCII terminals where the C64 charset can't
    represent the ANSI glyph (see formatting.py's module comment for the
    verified-by-direct-encode details: '\\' and ASCII '|' have no PETSCII
    slot in either charset mode; only one diagonal-quadrant block exists
    on the C64 and it has no mirror, so Claw uses '/))' on both terminal
    types instead of the original SPUR '\\|/').
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# See test_wild_horse_placement.py: force a clean reimport regardless of
# what stubbed sys.modules['network_context']/['net_common'] before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room, RoomAlignment, room_alignment_label
from formatting import guild_sigil_for
from terminal import Translation


class TestRoomAlignmentLabel:
    """base_classes.room_alignment_label() -- plain-English label, terminal-agnostic."""

    def test_free_fire_label(self):
        assert room_alignment_label(RoomAlignment.FREE_FIRE) == 'Free-Fire'

    def test_fist_label(self):
        assert room_alignment_label(RoomAlignment.FIST) == 'Fist Territory'

    def test_claw_label(self):
        assert room_alignment_label(RoomAlignment.CLAW) == 'Claw Territory'

    def test_sword_label(self):
        assert room_alignment_label(RoomAlignment.SWORD) == 'Sword Territory'

    def test_hq_label(self):
        assert room_alignment_label(RoomAlignment.HQ) == 'HQ'

    def test_neutral_is_not_shown(self):
        assert room_alignment_label(RoomAlignment.NEUTRAL) is None

    def test_none_is_not_shown(self):
        assert room_alignment_label(None) is None


def _ctx(translation):
    ctx = MagicMock()
    ctx.player.client_settings.translation = translation
    return ctx


class TestGuildSigilFor:
    """formatting.guild_sigil_for() -- colorized, terminal-appropriate sigil."""

    def test_neutral_has_no_sigil(self):
        assert guild_sigil_for(_ctx(Translation.ANSI), RoomAlignment.NEUTRAL) is None

    def test_none_has_no_sigil(self):
        assert guild_sigil_for(_ctx(Translation.ANSI), None) is None

    def test_accepts_raw_string_value(self):
        assert guild_sigil_for(_ctx(Translation.ANSI), 'free_fire') is not None

    def test_ansi_claw_uses_safe_ascii_not_backslash_pipe(self):
        sigil = guild_sigil_for(_ctx(Translation.ANSI), RoomAlignment.CLAW)
        assert '/))' in sigil
        assert '\\' not in sigil

    def test_petscii_claw_matches_ansi_glyph(self):
        """Claw's original SPUR sigil ('\\|/') has no PETSCII encoding at
        all (neither '\\' nor ASCII '|' exist in the C64 charset) -- both
        terminal types fall back to the same safe '/))' glyph."""
        ansi_sigil   = guild_sigil_for(_ctx(Translation.ANSI), RoomAlignment.CLAW)
        petscii_sigil = guild_sigil_for(_ctx(Translation.PETSCII), RoomAlignment.CLAW)
        assert '/))' in ansi_sigil
        assert '/))' in petscii_sigil

    def test_petscii_sword_uses_box_drawing_glyphs(self):
        sigil = guild_sigil_for(_ctx(Translation.PETSCII), RoomAlignment.SWORD)
        assert '├' in sigil
        assert '─' in sigil

    def test_ansi_sword_uses_ascii_glyph(self):
        sigil = guild_sigil_for(_ctx(Translation.ANSI), RoomAlignment.SWORD)
        assert '-}===>' in sigil

    def test_all_non_neutral_sigils_are_petscii_encodable(self):
        """Every sigil must actually encode without error -- this is the
        whole point of the terminal-specific tables."""
        from formatting import _TOKEN_RE, petscii_encode

        for alignment in (RoomAlignment.FREE_FIRE, RoomAlignment.CLAW,
                          RoomAlignment.SWORD, RoomAlignment.FIST, RoomAlignment.HQ):
            sigil = guild_sigil_for(_ctx(Translation.PETSCII), alignment)
            assert sigil is not None
            encoded = petscii_encode(sigil)
            # No unknown-token literal braces should survive encoding.
            assert b'|' not in encoded.replace(b'||', b'')


def _make_map(*, alignment, name='MERCHANT LOBBY +') -> Map:
    m = Map()
    room = Room(number=1, name=name, desc='The store entrance.',
                exits={}, alignment=alignment)
    m.levels[1] = {1: room}
    m.rooms = m.levels[1]
    return m


def _client(translation=Translation.ANSI) -> MagicMock:
    client = MagicMock()
    client.room = 1
    client.ctx.player.map_level = 1
    client.ctx.player.is_debug = False
    client.ctx.player.client_settings.translation = translation
    return client


class TestDescribeRoomAlignmentDisplay:

    @pytest.fixture
    def server(self):
        return Server('127.0.0.1', 0)

    def test_free_fire_room_shows_sigil_only_once(self, server):
        """Regression: level_1.json bakes '+' directly into some room
        names (e.g. 'MERCHANT LOBBY +') -- the dynamic sigil must replace
        that legacy text, not sit alongside it."""
        server.game_map = _make_map(alignment=RoomAlignment.FREE_FIRE)
        lines = server._describe_room(_client())
        assert lines[0] == 'MERCHANT LOBBY  |red|+|reset|'
        assert lines[0].count('+') == 1

    def test_fist_room_shows_sigil_only_once(self, server):
        server.game_map = _make_map(alignment=RoomAlignment.FIST,
                                    name='GAS ROOM ==[]')
        lines = server._describe_room(_client())
        assert lines[0].count('==[]') == 1
        assert lines[0].startswith('GAS ROOM  ')

    def test_neutral_room_still_strips_legacy_text_but_has_no_sigil(self, server):
        """A NEUTRAL-aligned room never happens to carry legacy sigil text
        in the real data, but if it did, stripping is unconditional --
        there's no sigil to replace it with, so it's just gone."""
        server.game_map = _make_map(alignment=RoomAlignment.NEUTRAL)
        lines = server._describe_room(_client())
        assert lines[0] == 'MERCHANT LOBBY'

    def test_petscii_client_gets_petscii_sword_sigil(self, server):
        server.game_map = _make_map(alignment=RoomAlignment.SWORD,
                                    name='CAVERN LEDGE -]----')
        lines = server._describe_room(_client(translation=Translation.PETSCII))
        assert '├' in lines[0]
        assert 'CAVERN LEDGE  ' in lines[0]
        assert '-]----' not in lines[0]

    def test_hq_room_appends_hq_sigil(self, server):
        server.game_map = _make_map(alignment=RoomAlignment.SWORD,
                                    name='CAVERN PEAK -]---- HQ')
        lines = server._describe_room(_client())
        assert lines[0].startswith('CAVERN PEAK  ')
        assert '-}===>' in lines[0]
        assert '|yellow|HQ|reset|' in lines[0]

    def test_non_hq_room_has_no_hq_sigil(self, server):
        server.game_map = _make_map(alignment=RoomAlignment.SWORD,
                                    name='EDGE OF FOREST -]----')
        lines = server._describe_room(_client())
        assert 'HQ' not in lines[0]


class TestStripLegacyAlignmentSuffix:
    """base_classes.strip_legacy_alignment_suffix() -- against every real
    non-neutral room name pattern actually found in level_1.json (the only
    level file with baked-in legacy sigils; levels 2-7 never have them)."""

    def test_free_fire(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('MERCHANT LOBBY +') == ('MERCHANT LOBBY', False)

    def test_sword(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('CAVERN LEDGE -]----') == ('CAVERN LEDGE', False)

    def test_sword_hq(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('CAVERN PEAK -]---- HQ') == ('CAVERN PEAK', True)

    def test_claw(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('RUBY ROOM //>') == ('RUBY ROOM', False)

    def test_claw_hq(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('STORAGE ROOM //> HQ') == ('STORAGE ROOM', True)

    def test_fist(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('GAS ROOM ==[]') == ('GAS ROOM', False)

    def test_fist_hq(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('SECLUDED ROOM ==[] HQ') == ('SECLUDED ROOM', True)

    def test_plain_name_unchanged(self):
        from base_classes import strip_legacy_alignment_suffix
        assert strip_legacy_alignment_suffix('Tiny Town') == ('Tiny Town', False)
        assert strip_legacy_alignment_suffix('The Foyer') == ('The Foyer', False)
