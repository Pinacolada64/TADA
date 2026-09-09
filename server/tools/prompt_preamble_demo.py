#!/usr/bin/env python3
"""tools/prompt_preamble_demo.py — renders, through the real send()/
prompt() formatting pipeline, the ctx.prompt() call sites that were
reworked so long inline option text moves into `preamble_lines` (which
word-wraps to the player's actual screen width, see tada_utilities.py /
network_context.py) instead of being baked unwrapped into `prompt_text`
(sent raw, never wrapped -- the alpha-tester complaint this fixes).

This drives the real production functions (not reimplemented copies) with
a genuine Player and a fake reader/writer/server standing in for the
socket, so what's printed is exactly what a client receives on the wire:
every `ctx.send()` becomes one JSON Message with wrapped `lines`, and
every `ctx.prompt()` becomes one Message with wrapped `lines` (the
preamble) followed by a short raw `prompt`.

Each scenario is answered just enough to reach its target prompt and then
immediately cancel out (Q/Enter/blank), so this only exercises the fixed
prompt itself, not the rest of each command's flow.

Run from server/:
    .venv/bin/python3 tools/prompt_preamble_demo.py [columns]

Default column width is 40 (C64 default). Pass e.g. 80 to compare against
a wider client.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.WARNING)

import net_common as nc
from network_context import GameContext
from player import Player


# ---------------------------------------------------------------------------
# Fake transport — same pattern as tests/social/test_messaging.py's
# test_prompt_prepends_and_clears_pending_pages
# ---------------------------------------------------------------------------

class _FakeWriter:
    async def drain(self) -> None:
        pass

    def write(self, data: bytes) -> None:
        pass


class _FakeReader:
    """Hands back one canned response per readline(), JSON-encoded exactly
    like a real client reply."""

    def __init__(self, responses: list[str]):
        self._q = list(responses)

    async def readline(self) -> bytes:
        text = self._q.pop(0) if self._q else ''
        return nc.to_jsonb({'text': text}) + b'\n'


class _RecordingServer:
    """Captures every Message that would have gone out over the wire."""

    def __init__(self):
        self.clients: dict = {}
        self.sent_messages: list[nc.Message] = []

    async def send_message(self, writer, obj) -> None:
        self.sent_messages.append(obj)


def _make_ctx(columns: int, responses: list[str]) -> tuple[GameContext, _RecordingServer]:
    from terminal import Translation

    player = Player(name='Rulan')
    player.client_settings.screen_columns = columns
    player.client_settings.translation = Translation.ASCII  # plain text for this demo

    from flags import PlayerFlags
    player.clear_flag(PlayerFlags.HOURGLASS)  # no clock-prefix noise in this demo
    server = _RecordingServer()
    ctx = GameContext(
        player = player,
        reader = _FakeReader(responses),
        writer = _FakeWriter(),
        server = server,
        client = SimpleNamespace(room=1),
    )
    return ctx, server


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render(title: str, source: str, columns: int, server: _RecordingServer) -> None:
    bar = '+' + '-' * (columns + 2) + '+'
    print(f'\n=== {title}  ({source}) ===')
    print(f'[{columns}-column client]')
    print(bar)
    for msg in server.sent_messages:
        for line in msg.lines:
            print(f'| {line:<{columns}} |')
        # ctx.send() stamps every message with the ambient status prompt
        # ('> ') too -- only a genuine ctx.prompt() call (empty lines,
        # its own prompt text) is what we're here to look at.
        if msg.prompt and not msg.lines:
            label = f'>>> {msg.prompt}'
            print(f'| {label:<{columns}} |')
    print(bar)


# ---------------------------------------------------------------------------
# Scenarios — one per fixed call site
# ---------------------------------------------------------------------------

async def demo_ready_weapon(columns: int) -> None:
    from items import Weapon
    ctx, server = _make_ctx(columns, [''])  # blank = cancel
    weapons = [
        Weapon(id_number=1, name='Rusty Dagger', location=0,
               stability=80, to_hit=60, price=15),
        Weapon(id_number=2, name='Broadsword of Whacking', location=0,
               stability=95, to_hit=75, price=250),
    ]
    from items import ready_weapon
    await ready_weapon(ctx, ctx.player, weapons)
    _render('READY weapon', 'items.py:ready_weapon()', columns, server)


async def demo_armory_buy(columns: int) -> None:
    from shoppe.armory import _buy
    ctx, server = _make_ctx(columns, ['Q'])
    all_weapons = []  # empty catalog is fine -- we only reach the choice prompt
    await _buy(ctx, ctx.player, ctx.player.inventory, all_weapons)
    _render('Armory — buy a weapon', 'shoppe/armory.py:_buy()', columns, server)


async def demo_guild_food_locker(columns: int) -> None:
    from guild_hq.main import _food_locker
    ctx, server = _make_ctx(columns, ['Q'])
    state = {'food_locker': [], 'log': []}
    await _food_locker(ctx, ctx.player, state, {})
    _render('Guild HQ — food locker', 'guild_hq/main.py:_food_locker()', columns, server)


async def demo_little_girl(columns: int) -> None:
    from encounters.little_girl import try_encounter
    from base_classes import Map, Room

    ctx, server = _make_ctx(columns, ['I'])  # Ignore -- fewest follow-on prompts
    game_map = Map()
    rooms = {1: Room(number=1, name='Room One', desc='', exits={}, monster=0, flags=[])}
    game_map.levels[1] = rooms
    game_map.rooms = rooms
    ctx.server.game_map = game_map

    import random
    orig_uniform, orig_randint = random.uniform, random.randint
    random.uniform = lambda a, b: 0.0    # force the encounter to trigger
    random.randint = lambda a, b: 1      # force the "runs away" branch (no further prompts)
    try:
        await try_encounter(ctx)
    finally:
        random.uniform, random.randint = orig_uniform, orig_randint
    _render('Little girl encounter', 'encounters/little_girl.py:try_encounter()', columns, server)


async def demo_general_store(columns: int) -> None:
    from shoppe.main import _general_store
    ctx, server = _make_ctx(columns, [''])  # blank = leave
    await _general_store(ctx)
    _render('General Store — buy', 'shoppe/main.py:_general_store()', columns, server)


SCENARIOS = [
    demo_ready_weapon,
    demo_armory_buy,
    demo_guild_food_locker,
    demo_little_girl,
    demo_general_store,
]


async def main() -> None:
    columns = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    for scenario in SCENARIOS:
        await scenario(columns)


if __name__ == '__main__':
    asyncio.run(main())
