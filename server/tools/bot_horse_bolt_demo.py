#!/usr/bin/env python3
"""bot_horse_bolt_demo.py — Scripted transcript of the horse-bolt mechanic,
run against the real command engine (not a live server).

Same lightweight approach as bot_ration_demo.py: this drives the actual
production code (ally_events.horse_bolt.maybe_bolt_mount/bolt_thrown_mount,
commands.mount.MountCommand, combat.engine.CombatSession._charge_unseat_check,
and the real commands.editplayer.EditPlayerCommand menu) directly, in-process,
against a small fake Map/Player/ctx -- no socket, no running server required.
Every line of "send" output below is genuine engine output, including the
game's own |color|text|reset| tags; only the *scenario* (dice rolls, which
exit a bolt takes, what gets typed into a prompt) is scripted, via patching
random.randint/random.choice inside ally_events.horse_bolt and combat.engine
for just long enough to force a deterministic path.

Why this exists
----------------
Built to demonstrate, end to end, the horse-bolt mechanic added after a real
bug report: a medusa scared a player's horse SHADOW into the tactical-ambush
desert branch, permanently removing it from the party ("runs away
screaming!"). Mounts are now excluded from that mechanic (commands/order.py,
combat/engine.py, encounters/monster.py); this script instead walks through
the gentler replacement in ally_events/horse_bolt.py:

  1. Ambushed while mounted -- SHADOW bolts a couple of rooms away (dry).
  2. DUMMYBOT walks there and MOUNT catches it.
  3. Ambushed again -- SHADOW bolts toward water, stops at the edge
     instead of ever landing in the water room itself (bolt_at_water).
  4. DUMMYBOT finds it there; MOUNT's catch line reads "at the water's
     edge" instead of the generic "nearby".
  5. A CHARGE throws DUMMYBOT from the saddle -- already-spooked SHADOW
     bolts a third time, farther away this time.
  6. Rather than search, an admin runs the real EditPlayerCommand menu
     (Character Names -> Horse -> [C] Recall Horse) to get it back.

Usage
-----
    python tools/bot_horse_bolt_demo.py                # prints the transcript
    python tools/bot_horse_bolt_demo.py --json out.json  # also writes JSON

The JSON form (a flat list of {"speaker": ..., "text": ...} records,
speaker in {NARRATOR, SERVER, DUMMYBOT-INPUT}) is what fed the "Horse Bolt
Session" artifact built from this same run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ally_events.horse_bolt import _BOLT_HOPS, maybe_bolt_mount
from bar.ally_data import Ally, AllyFlags, AllyStatus
from base_classes import Map, PlayerStat, Room
from combat.engine import CombatSession
from commands.editplayer import EditPlayerCommand
from commands.mount import MountCommand
from flags import PlayerFlags
from player import Player

TRANSCRIPT: list[dict] = []


def _stamp(speaker: str, text: str) -> None:
    TRANSCRIPT.append({'speaker': speaker, 'text': text})


def narrate(text: str) -> None:
    _stamp('NARRATOR', text)


class ScriptedChoice:
    """Feeds ally_events.horse_bolt.random.choice() a fixed hop count then
    a fixed direction sequence, so a bolt's path is fully deterministic."""

    def __init__(self, hops: int, directions: list[str]):
        self._hops = hops
        self._dirs = list(directions)
        self._gave_hops = False

    def __call__(self, seq):
        seq = list(seq)
        if not self._gave_hops and seq == list(_BOLT_HOPS):
            self._gave_hops = True
            return self._hops
        return self._dirs.pop(0)


class DemoClient:
    def __init__(self, room: int):
        self.room = room


class DemoServer:
    def __init__(self, game_map: Map):
        self.game_map = game_map
        self.clients = {}


class DemoCtx:
    """Minimal GameContext stand-in: records everything sent, and answers
    ctx.prompt() from a scripted queue while logging what was "typed"."""

    def __init__(self, player: Player, game_map: Map, room: int):
        self.player = player
        self.client = DemoClient(room)
        self.server = DemoServer(game_map)
        self._responses: list[str] = []

    def script(self, responses: list[str]) -> None:
        self._responses = list(responses)

    async def send(self, *args, **kwargs) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                for line in a:
                    _stamp('SERVER', str(line))
            else:
                _stamp('SERVER', str(a))

    async def send_room(self, *args, **kwargs) -> None:
        pass  # other players in the room -- not shown in this transcript

    async def prompt(self, prompt_text: str = '', preamble_lines: list | None = None) -> str:
        if preamble_lines:
            for line in preamble_lines:
                _stamp('SERVER', str(line))
        response = self._responses.pop(0) if self._responses else ''
        _stamp('DUMMYBOT-INPUT', response if response else '(Enter)')
        return response


ROOM_NAMES = {1: 'Stable Yard', 2: 'Dusty Trail', 3: 'Cave Mouth', 5: 'Grotto Path',
              6: 'Sunken Chamber', 7: 'Windmill Rise', 8: 'Far Meadow'}


def make_map() -> Map:
    rooms = {
        1: Room(number=1, name='Stable Yard', desc='Hitching posts and the smell of hay.',
                exits={'east': 2, 'north': 7}),
        2: Room(number=2, name='Dusty Trail', desc='A well-worn path east of the stables.',
                exits={'west': 1, 'east': 3}),
        3: Room(number=3, name='Cave Mouth', desc='Cool air drifts up from a passage below.',
                exits={'west': 2, 'south': 5}),
        5: Room(number=5, name='Grotto Path', desc='Damp stone, the sound of dripping water ahead.',
                exits={'north': 3, 'south': 6}),
        6: Room(number=6, name='Sunken Chamber', desc='A flooded chamber, black water lapping the walls.',
                exits={'north': 5}, flags=['water']),
        7: Room(number=7, name='Windmill Rise', desc='A creaking windmill turns slowly overhead.',
                exits={'south': 1, 'east': 8}),
        8: Room(number=8, name='Far Meadow', desc='Tall grass stretches to the horizon.',
                exits={'west': 7}),
    }
    m = Map()
    m.levels[1] = rooms
    m.rooms = rooms
    return m


def walk(ctx: DemoCtx, dest_room: int, steps: list[str]) -> None:
    # Real game text has no ride/walk distinction for ordinary movement
    # (checked commands/movement.py -- the only travel-flavor lines are
    # the dismount ones, e.g. "Your horse balks at the water"), so this
    # verb choice is narrator flavor only. Still picked off the player's
    # actual PlayerFlags.MOUNTED state rather than hardcoded, so it can't
    # drift out of sync with the scene.
    verb = 'rides' if ctx.player.query_flag(PlayerFlags.MOUNTED) else 'walks'
    for step in steps:
        narrate(f'DUMMYBOT {verb} {step}...')
    ctx.client.room = dest_room
    narrate(f'DUMMYBOT arrives at {ROOM_NAMES[dest_room]} (room {dest_room}).')


async def act1_ambush_bolts_dry(ctx: DemoCtx, shadow: Ally) -> None:
    narrate('=== Scene 1: ambushed on the trail, SHADOW bolts ===')
    ctx.player.set_flag(PlayerFlags.MOUNTED)
    _stamp('SERVER', 'You climb onto SHADOW.')
    narrate('DUMMYBOT rides out of the Stable Yard, SHADOW beneath them.')
    narrate('An ambush falls on the party -- SHADOW panics!')
    with patch('ally_events.horse_bolt.random.randint', return_value=5), \
         patch('ally_events.horse_bolt.random.choice', new=ScriptedChoice(2, ['east', 'east'])):
        await maybe_bolt_mount(ctx)
    narrate(f'(SHADOW is now AllyStatus.{shadow.status.name}, bolt_room_no={shadow.bolt_room_no}, '
            f'bolt_at_water={shadow.bolt_at_water})')


async def act2_track_and_catch(ctx: DemoCtx, shadow: Ally) -> None:
    narrate('')
    narrate('=== Scene 2: DUMMYBOT tracks SHADOW down ===')
    walk(ctx, shadow.bolt_room_no, ['east', 'east'])
    await MountCommand().execute(ctx)


async def act3_ambush_bolts_to_water(ctx: DemoCtx, shadow: Ally) -> None:
    narrate('')
    narrate('=== Scene 3: ambushed again, SHADOW bolts toward the water ===')
    narrate('An ambush falls on the party again -- SHADOW panics!')
    with patch('ally_events.horse_bolt.random.randint', return_value=5), \
         patch('ally_events.horse_bolt.random.choice', new=ScriptedChoice(2, ['south', 'south'])):
        await maybe_bolt_mount(ctx)
    narrate(f'(SHADOW is now AllyStatus.{shadow.status.name}, bolt_room_no={shadow.bolt_room_no}, '
            f'bolt_at_water={shadow.bolt_at_water} -- stopped short of the Sunken Chamber)')


async def act4_find_at_waters_edge(ctx: DemoCtx, shadow: Ally) -> None:
    narrate('')
    narrate("=== Scene 4: DUMMYBOT finds SHADOW at the water's edge ===")
    walk(ctx, shadow.bolt_room_no, ['south'])
    await MountCommand().execute(ctx)


async def act5_charge_throws_and_bolts(ctx: DemoCtx, shadow: Ally) -> None:
    narrate('')
    narrate('=== Scene 5: a CHARGE throws DUMMYBOT, SHADOW bolts a third time ===')
    walk(ctx, 1, ['back toward the stable'])
    narrate('DUMMYBOT CHARGEs a monster -- and takes the jar badly.')
    session = CombatSession({'name': 'CAVE TROLL', 'strength': 10}, room_no=1)
    with patch('combat.engine.random.randint', return_value=1), \
         patch('ally_events.horse_bolt.random.randint', return_value=1), \
         patch('ally_events.horse_bolt.random.choice', new=ScriptedChoice(2, ['north', 'east'])):
        await session._charge_unseat_check(ctx)
    narrate(f'(SHADOW is now AllyStatus.{shadow.status.name}, bolt_room_no={shadow.bolt_room_no}, '
            f'far away in {ROOM_NAMES[shadow.bolt_room_no]} -- too far to chase down right now)')


async def act6_admin_recalls(ctx: DemoCtx, shadow: Ally) -> None:
    narrate('')
    narrate('=== Scene 6: an admin recalls SHADOW via EditPlayerCommand ===')
    narrate('SUPPORT logs in as an admin and runs EDITPLAYER on DUMMYBOT.')
    ctx.script(['cn', 'h', 'c', '', ''])
    await EditPlayerCommand().execute(ctx)
    narrate(f'(SHADOW is now AllyStatus.{shadow.status.name}, bolt_room_no={shadow.bolt_room_no})')


def _print_transcript() -> None:
    for entry in TRANSCRIPT:
        speaker, text = entry['speaker'], entry['text']
        if speaker == 'DUMMYBOT-INPUT':
            print(f'> {text}')
        else:
            print(text)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', metavar='FILE',
                        help='Also write the transcript as JSON to FILE.')
    args = parser.parse_args()

    game_map = make_map()
    player = Player(name='Dummybot')
    player.stats = {PlayerStat.STR: 1, PlayerStat.CON: 1, PlayerStat.INT: 1,
                     PlayerStat.EGY: 1, PlayerStat.DEX: 1}
    player.hit_points = 50
    player.xp_level = 1

    shadow = Ally(name='SHADOW', gender='m', strength=20, to_hit=0, flags=[AllyFlags.MOUNT])
    shadow.status = AllyStatus.SERVANT
    player.party.members.append(shadow)

    ctx = DemoCtx(player, game_map, room=1)

    await act1_ambush_bolts_dry(ctx, shadow)
    await act2_track_and_catch(ctx, shadow)
    await act3_ambush_bolts_to_water(ctx, shadow)
    await act4_find_at_waters_edge(ctx, shadow)
    await act5_charge_throws_and_bolts(ctx, shadow)
    await act6_admin_recalls(ctx, shadow)

    _print_transcript()

    if args.json:
        out = Path(args.json)
        out.write_text(json.dumps(TRANSCRIPT, indent=2))
        print(f'\nWrote {len(TRANSCRIPT)} transcript lines to {out}')


if __name__ == '__main__':
    asyncio.run(main())
