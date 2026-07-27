#!/usr/bin/env python3
"""tools/bot_monster_cast_check.py — Live check of monster spellcasting
(combat/monster_spells.py) against a real running TADA server.

Connects as an admin account, teleports to a known +/++ flagged
monster's room, attacks repeatedly, and watches for the Endurance/
Destroy/Teleport narration. Default target is the WEREWOLF at level 1
room 78 (cast_one_spell only, so expect Endurance then Destroy, never
Teleport) -- pass --level/--room/--rounds for a ++ monster (e.g. WITCH,
level 2 room 117) to also see a Teleport once both single-use effects
have fired.

Real HP/silver/position changes are left on the target account --
rerun against a throwaway admin or expect its state to drift.

Usage:
    .venv/bin/python tools/bot_monster_cast_check.py [--host HOST] [--port PORT]
        [--user USER] [--level N] [--room N] [--rounds N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot_credentials import load_password


async def recv_until_prompt(reader, label, max_msgs=40, quiet_timeout=3.0):
    prompt = ''
    for _ in range(max_msgs):
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=quiet_timeout)
        except asyncio.TimeoutError:
            break
        if not raw:
            break
        msg = json.loads(raw)
        lines = msg.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        for line in lines:
            print(f'  [{label}] {line}')
        prompt = msg.get('prompt', '')
        if prompt:
            print(f'  [{label}] [{prompt}]')
            if prompt.rstrip().endswith('>'):
                break
    return prompt


async def send_line(writer, text):
    print(f'  --> {text!r}')
    writer.write(json.dumps({'lines': [text]}).encode() + b'\n')
    await writer.drain()


async def main(host: str, port: int, user: str, level: int, room: int, rounds: int) -> None:
    password = load_password(user)

    reader, writer = await asyncio.open_connection(host, port)
    raw = await asyncio.wait_for(reader.readline(), timeout=5.0)
    init = json.loads(raw)
    writer.write(json.dumps({'server_id': init.get('server_id', 'test_server'),
                              'server_key': init.get('server_key', 'test_key')}).encode() + b'\n')
    await writer.drain()

    while True:
        raw = await asyncio.wait_for(reader.readline(), timeout=4.0)
        msg = json.loads(raw)
        prompt = msg.get('prompt', '')
        if prompt == 'login> ':
            break
        if 'terminal type' in prompt.lower():
            writer.write(json.dumps({'lines': ['A'], 'mode': 'login'}).encode() + b'\n')
            await writer.drain()

    await send_line(writer, f'connect {user} {password}')
    await recv_until_prompt(reader, user, max_msgs=60)

    print(f'\n=== teleport to level {level}, room {room} ===')
    await send_line(writer, f'teleport {level} {room}')
    await recv_until_prompt(reader, user, max_msgs=20)

    print(f'\n=== attack up to {rounds} times, watching for spellcasting ===')
    for _ in range(rounds):
        await send_line(writer, 'attack')
        prompt = await recv_until_prompt(reader, user, max_msgs=15)
        if prompt is None:
            break

    print('\n=== flee and quit ===')
    await send_line(writer, 'flee')
    await recv_until_prompt(reader, user, max_msgs=15)
    await send_line(writer, 'quit')
    prompt = await recv_until_prompt(reader, user, max_msgs=10)
    if 'Y/N' in prompt:
        await send_line(writer, 'Y')
        await recv_until_prompt(reader, user, max_msgs=10)
    writer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=34083)
    parser.add_argument('--user', default='botdummy')
    parser.add_argument('--level', type=int, default=1)
    parser.add_argument('--room', type=int, default=78)  # WEREWOLF
    parser.add_argument('--rounds', type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.user, args.level, args.room, args.rounds))
