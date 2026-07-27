#!/usr/bin/env python3
"""tools/bot_cast_check.py — Live check of the spell book + cast command
against a real running TADA server.

Connects as botdruid (already a Druid, so this exercises the "DRUID
POWER!" caster bonus for free): confirms `cast` says "no spells" before
any are learned, navigates to the Wizard's shop and buys ESP, confirms
the purchase landed in the Spell Book (not the main inventory) via
`cast`'s own listing, casts it, and reports the real (unscripted) roll
outcome. Real INT/silver changes are left in place -- rerun against a
throwaway account or expect the target character's stats to drift.

Usage:
    .venv/bin/python tools/bot_cast_check.py [--host HOST] [--port PORT] [--user USER]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot_credentials import load_password


async def recv_until_prompt(reader, label, max_msgs=60, quiet_timeout=3.0):
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


async def main(host: str, port: int, user: str) -> None:
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

    print('\n=== cast with no known spells ===')
    await send_line(writer, 'cast')
    await recv_until_prompt(reader, user, max_msgs=10)

    print('\n=== navigate to the Wizard shop ===')
    await send_line(writer, 'down')
    await recv_until_prompt(reader, user, max_msgs=20)
    await send_line(writer, 'W')
    await recv_until_prompt(reader, user, max_msgs=20)

    print('\n=== buy ESP (spell #1) ===')
    await send_line(writer, 'Y')  # "Are you here to learn a spell?"
    prompt = await recv_until_prompt(reader, user, max_msgs=20)
    while '-- More' in prompt or '-- End' in prompt:
        await send_line(writer, '')  # advance paging
        prompt = await recv_until_prompt(reader, user, max_msgs=20)
    await send_line(writer, '1')  # ESP
    await recv_until_prompt(reader, user, max_msgs=20)
    await send_line(writer, 'Y')  # confirm purchase
    await recv_until_prompt(reader, user, max_msgs=20)
    await send_line(writer, 'Q')  # leave the wizard shop, back to Shoppe menu
    await recv_until_prompt(reader, user, max_msgs=20)
    await send_line(writer, 'X')  # leave the Shoppe entirely, back to main game
    await recv_until_prompt(reader, user, max_msgs=20)

    print('\n=== cast (should now list ESP) ===')
    await send_line(writer, 'cast')
    await recv_until_prompt(reader, user, max_msgs=20)
    await send_line(writer, '1')
    await recv_until_prompt(reader, user, max_msgs=20)

    print('\n=== quit ===')
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
    parser.add_argument('--user', default='botdruid')
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.user))
