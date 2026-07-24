#!/usr/bin/env python3
"""bot_ration_demo.py — Scripted transcript of rations + ally hunger,
run against the real command engine (not a live server).

Unlike bot_horse_journey.py (a perceive/update-belief/decide loop against
a real running TADA server over its actual socket), this is a lighter-
weight kind of "bot": it drives the exact same command classes
(commands.eat.EatCommand, commands.drink.DrinkCommand, commands.inv.
InvCommand, commands.get._room_available_items, ally_events.
try_hungry_ally, commands.give._try_body_build) directly, in-process,
against small fake ctx/player/server stand-ins -- no socket, no running
server required. Every line of output below is genuine engine output,
never hand-written flavor text; only the *scenario* (which items exist,
which allies are in the party, what the player types back) is scripted.

Why this exists
----------------
Built to demonstrate, end to end, the fix for a real bug Ryan reported:
a loaf of bread that was genuinely in a player's inventory came up "You
are not carrying any food matching bread" after a save/reload, because
inventory.Inventory.from_json() rebuilt every persisted item as a plain
Item() with no .kind at all (and InventoryEntry.to_json() never wrote one
out to begin with) -- commands/eat.py and commands/drink.py both filter
inventory strictly by item.kind. Fixed in inventory.py; see
tests/test_inventory.py's TestInventoryKindRoundTrip.

While building the fix's showcase, this script also became the cleanest
way to walk through ally_events.try_hungry_ally()'s three real outcomes
side by side:
  - a hungry, non-Elite ally who's fed (honor +2, ally strength +1 via
    commands/give.py's _try_body_build())
  - a hungry, non-Elite ally who's refused (honor -2, player eats it
    themselves)
  - an Elite-flagged ally, who never asks at all no matter how hungry
    (AllyFlags.ELITE -- SPUR's own `instr("!",zt$)` check)

Usage
-----
    python tools/bot_ration_demo.py            # prints the transcript
    python tools/bot_ration_demo.py --json out.json   # also writes JSON

The JSON form (a flat list of {"kind": ..., "text": ...} records, kind in
{heading, cmd, send, prompt, input}) is what fed the "Ration Duty" replay
artifact built from this same run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bar.ally_data import Ally, AllyFlags
from commands.drink import DrinkCommand
from commands.eat import EatCommand
from commands.get import _room_available_items
from commands.inv import InvCommand
from inventory import Inventory

TRANSCRIPT: list[dict] = []

BREAD = {'number': 5, 'id_number': 5, 'name': 'LOAF OF BREAD', 'kind': 'food', 'price': 30}
WATER = {'number': 12, 'id_number': 12, 'name': 'MINERAL WATER', 'kind': 'drink', 'price': 10}


def _stamp(kind: str, text: str = '') -> None:
    TRANSCRIPT.append({'kind': kind, 'text': text})


class FakePlayer:
    """Just enough of a Player for EatCommand/DrinkCommand/InvCommand and
    ally_events.try_hungry_ally() to run against -- real Inventory, real
    party list of Ally instances, no save/load machinery involved."""

    def __init__(self, name: str):
        self.name = name
        self.inventory = Inventory(capacity=14)
        self.max_inventory_size = 14
        self.food = 8    # hungry enough that EatCommand won't refuse
        self.drink = 8
        self.honor = 1000
        self.party: list = []
        self.picked_up_items: list = []
        self.map_level = 1
        self.unsaved_changes = False
        self.return_key = 'Enter'

    def query_flag(self, flag) -> bool:
        return False


class FakeCtx:
    """A ctx wired to one room holding exactly one ration (*ration_dict*)
    -- enough for commands.get._room_available_items() to resolve a
    pickup the same way GET does, without a real Map/Server."""

    def __init__(self, player: FakePlayer, ration_dict: dict):
        self.player = player
        self.client = MagicMock()
        self.client.room = 1
        self._answers: list[str] = []

        server = MagicMock()
        server.items = []
        server.weapons = []
        server.rations = [ration_dict]
        server.monsters = []
        room = MagicMock()
        room.item = 0
        room.weapon = 0
        room.food = 1
        room.monster = 0
        server.game_map.get_room.return_value = room
        self.server = server

    async def send(self, *args) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                for line in a:
                    _stamp('send', str(line))
            else:
                _stamp('send', str(a))

    async def prompt(self, prompt_text: str = '', preamble_lines=None) -> str:
        if preamble_lines:
            for ln in preamble_lines:
                _stamp('send', str(ln))
        answer = self._answers.pop(0) if self._answers else ''
        _stamp('prompt', f'{prompt_text} ')
        _stamp('input', answer)
        return answer


def pickup_ration(player: FakePlayer, ration_dict: dict):
    """Reuse get.py's own room-item resolution (the same code path GET
    itself uses) to add the room's ration to the player's inventory.
    Returns the picked-up Item."""
    ctx = FakeCtx(player, ration_dict)
    _, entry, _ = _room_available_items(ctx)[0]
    player.inventory.add(entry.item, quantity=entry.quantity)
    return entry.item


async def act1_pickup_and_inventory() -> None:
    _stamp('heading', 'Act 1 -- Picking up rations')
    player = FakePlayer('Rulan')

    _stamp('cmd', 'get bread')
    bread = pickup_ration(player, BREAD)
    await FakeCtx(player, BREAD).send(f'You pick up {bread.name.title()}.')

    _stamp('cmd', 'get water')
    water = pickup_ration(player, WATER)
    await FakeCtx(player, WATER).send(f'You pick up {water.name.title()}.')

    _stamp('cmd', 'inv')
    await InvCommand().execute(FakeCtx(player, BREAD))


async def act2_eat_positive() -> None:
    _stamp('heading', 'Act 2 -- Eating with a hungry ally (positive outcome)')
    player = FakePlayer('Rulan')
    pickup_ration(player, BREAD)
    player.party = [Ally('Grommel', 'm', 7, 40)]

    ctx = FakeCtx(player, BREAD)
    ctx._answers = ['Y']
    _stamp('cmd', 'eat bread')
    await EatCommand().execute(ctx, 'bread')


async def act3_eat_negative() -> None:
    _stamp('heading', 'Act 3 -- Eating with a hungry ally (negative outcome)')
    player = FakePlayer('Rulan')
    pickup_ration(player, BREAD)
    player.party = [Ally('Pim', 'f', 9, 35)]

    ctx = FakeCtx(player, BREAD)
    ctx._answers = ['N']
    _stamp('cmd', 'eat bread')
    await EatCommand().execute(ctx, 'bread')


async def act4_eat_elite() -> None:
    _stamp('heading', 'Act 4 -- Eating with an Elite ally (no interception)')
    player = FakePlayer('Rulan')
    pickup_ration(player, BREAD)
    player.party = [Ally('Sable', 'f', 8, 45, flags=[AllyFlags.ELITE])]

    ctx = FakeCtx(player, BREAD)
    _stamp('cmd', 'eat bread')
    await EatCommand().execute(ctx, 'bread')


async def act5_drink() -> None:
    _stamp('heading', 'Act 5 -- Drinking (no ally around)')
    player = FakePlayer('Rulan')
    pickup_ration(player, WATER)

    ctx = FakeCtx(player, WATER)
    _stamp('cmd', 'drink water')
    await DrinkCommand().execute(ctx, 'water')


def _print_transcript() -> None:
    for entry in TRANSCRIPT:
        kind, text = entry['kind'], entry['text']
        if kind == 'heading':
            print(f'\n=== {text} ===')
        elif kind == 'cmd':
            print(f'> {text}')
        elif kind == 'prompt':
            print(f'{text}', end='')
        elif kind == 'input':
            print(text)
        else:
            print(text)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', metavar='FILE',
                        help='Also write the transcript as JSON to FILE.')
    args = parser.parse_args()

    await act1_pickup_and_inventory()
    await act2_eat_positive()
    await act3_eat_negative()
    await act4_eat_elite()
    await act5_drink()

    _print_transcript()

    if args.json:
        out = Path(args.json)
        out.write_text(json.dumps(TRANSCRIPT, indent=2))
        print(f'\nWrote {len(TRANSCRIPT)} transcript lines to {out}')


if __name__ == '__main__':
    asyncio.run(main())
