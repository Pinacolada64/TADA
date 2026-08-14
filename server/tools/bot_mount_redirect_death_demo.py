#!/usr/bin/env python3
"""bot_mount_redirect_death_demo.py — Scripted transcript of a Saddled
mount dying to redirect a killing blow meant for its rider, run against
the real command engine (not a live server).

Same lightweight approach as bot_horse_bolt_demo.py: this drives the
actual production code (combat.engine.CombatSession._try_redirect_to_mount/
_resolve_monster_hit) directly, in-process, against a small fake
Map/Player/ctx -- no socket, no running server required. Every line of
"send" output below is genuine engine output, including the game's own
|color|text|reset| tags; only the *scenario* (dice rolls) is scripted,
via patching random.randint inside combat.engine for just long enough
to force a deterministic path.

Why this exists
----------------
Follow-up to the "mount takes the hit" mechanic added to
_try_redirect_to_mount() (see MECHANICS.md "Horses", combat/engine.py):
a Saddled mount that dies redirecting a hit now takes the player down
with it, out of the fight entirely. Built to answer, concretely rather
than by inspection, three questions raised while reviewing that change:

  - Does the player actually change rooms when this happens? (No --
    checked below by comparing ctx.client.room before/after.)
  - Does the player's party come running? (No such mechanic exists in
    this port at all -- each connected client is independent, and even
    a bolting mount only ever relocates the Ally object's own
    bolt_room_no, never the player's. See ally_events/horse_bolt.py.)
  - Does the player get cleared out of combat properly? (Yes --
    _try_redirect_to_mount() now calls self._remove_attacker(ctx) and
    sets self._done if no one else is still fighting, and
    _resolve_monster_hit() propagates that up so the round loop stops
    swinging at a player who just went down. There's no
    player.in_combat field in this codebase; CombatSession.attackers
    list-membership *is* the "in combat" state -- see
    commands/messaging.py's is_in_combat().)

Scenario
--------
  1. DUMMYBOT mounts SHADOW, already Saddled, and rides out to fight a
     CAVE TROLL.
  2. The troll's swing redirects onto SHADOW (agility check succeeds).
  3. SHADOW's hit_points are rigged low enough that the redirect damage
     kills it outright.
  4. Because SHADOW is Saddled, DUMMYBOT goes down too -- "...SHADOW
     stumbles, taking you with him, and falls, not moving." -- and is
     pulled out of the fight (removed from session.attackers; the
     session ends outright here since DUMMYBOT was the only attacker).
  5. The room number is printed before and after: unchanged.

Usage
-----
    python tools/bot_mount_redirect_death_demo.py                # prints the transcript
    python tools/bot_mount_redirect_death_demo.py --json out.json  # also writes JSON
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bar.ally_data import Ally, AllyFlags, AllyStatus
from base_classes import Map, PlayerStat, Room
from combat.engine import CombatSession
from combat.resolution import MonsterAttackResult
from flags import PlayerFlags
from player import Player

TRANSCRIPT: list[dict] = []


def _stamp(speaker: str, text: str) -> None:
    TRANSCRIPT.append({'speaker': speaker, 'text': text})


def narrate(text: str) -> None:
    _stamp('NARRATOR', text)


class DemoClient:
    def __init__(self, room: int):
        self.room = room


class DemoServer:
    def __init__(self, game_map: Map):
        self.game_map = game_map
        self.clients = {}


class DemoCtx:
    """Minimal GameContext stand-in: records everything sent."""

    def __init__(self, player: Player, game_map: Map, room: int):
        self.player = player
        self.client = DemoClient(room)
        self.server = DemoServer(game_map)

    async def send(self, *args, **kwargs) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                for line in a:
                    _stamp('SERVER', str(line))
            else:
                _stamp('SERVER', str(a))

    async def send_room(self, *args, **kwargs) -> None:
        pass  # other players in the room -- not shown in this transcript


ROOM_NAMES = {1: 'Stable Yard', 2: 'Dusty Trail'}


def make_map() -> Map:
    rooms = {
        1: Room(number=1, name='Stable Yard', desc='Hitching posts and the smell of hay.',
                exits={'east': 2}),
        2: Room(number=2, name='Dusty Trail', desc='A well-worn path east of the stables.',
                exits={'west': 1}),
    }
    m = Map()
    m.levels[1] = rooms
    m.rooms = rooms
    return m


async def act1_mount_up_and_charge(ctx: DemoCtx, shadow: Ally) -> CombatSession:
    narrate('=== Scene 1: DUMMYBOT mounts saddled SHADOW and rides out to fight ===')
    ctx.player.set_flag(PlayerFlags.MOUNTED)
    _stamp('SERVER', 'You climb onto SHADOW.')
    narrate(f'SHADOW is Saddled ({AllyFlags.SADDLED in shadow.flags}), '
            f'hit_points={shadow.hit_points} (rigged low for this demo -- a real capture '
            f'seeds strength x _HP_PER_STRENGTH, see ally_events/capture_horse.py).')
    narrate('DUMMYBOT CHARGEs a CAVE TROLL blocking the trail.')
    session = CombatSession({'name': 'CAVE TROLL', 'to_hit': 9, 'strength': 10}, room_no=1)
    session.attackers.append(ctx)
    return session


async def act2_troll_swing_redirects_and_kills_mount(ctx: DemoCtx, session: CombatSession,
                                                       shadow: Ally) -> bool:
    narrate('')
    narrate('=== Scene 2: the troll counter-swings -- redirected onto SHADOW, kills it ===')
    room_before = ctx.client.room
    result = MonsterAttackResult(hit=True, damage=1)
    # random.randint call order inside _try_redirect_to_mount: the d10
    # agility check (1, succeeds against to_hit=9), then r1/r2/r3 for the
    # damage roll (10 each -> dmg = (10+10+10)/3 + (8-9) = 9, more than
    # enough to finish off a mount rigged to 5 HP).
    with patch('combat.engine.random.randint', side_effect=[1, 10, 10, 10]):
        stop_the_loop = await session._resolve_monster_hit(ctx, result)
    room_after = ctx.client.room

    narrate(f'(SHADOW hit_points now {shadow.hit_points}, status=AllyStatus.{shadow.status.name})')
    narrate(f'(DUMMYBOT PlayerFlags.MOUNTED still set? {ctx.player.query_flag(PlayerFlags.MOUNTED)})')
    narrate(f'(room before={room_before}, after={room_after} -- '
            f'{"unchanged" if room_before == room_after else "MOVED"}, '
            f'nothing in this port relocates the player as a combat consequence)')
    narrate(f'(ctx still in session.attackers? {ctx in session.attackers})')
    narrate(f'(session._done set (fight over)? {session._done.is_set()})')
    narrate(f'(_resolve_monster_hit told the caller to stop the round loop? {stop_the_loop})')
    return stop_the_loop


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

    shadow = Ally(name='SHADOW', gender='m', strength=20, to_hit=0,
                  flags=[AllyFlags.MOUNT, AllyFlags.SADDLED])
    shadow.status = AllyStatus.SERVANT
    shadow.hit_points = 5  # rigged low -- see act1's narration
    player.party.members.append(shadow)

    ctx = DemoCtx(player, game_map, room=1)

    session = await act1_mount_up_and_charge(ctx, shadow)
    await act2_troll_swing_redirects_and_kills_mount(ctx, session, shadow)

    _print_transcript()

    if args.json:
        out = Path(args.json)
        out.write_text(json.dumps(TRANSCRIPT, indent=2))
        print(f'\nWrote {len(TRANSCRIPT)} transcript lines to {out}')


if __name__ == '__main__':
    asyncio.run(main())
