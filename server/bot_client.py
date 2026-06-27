#!/usr/bin/env python3
"""bot_client.py — Scripted bot that connects to the TADA server and plays a session.

Usage:
    python bot_client.py [--host HOST] [--port PORT] [--user USER] [--password PW]

Runs a sequence of commands and pretty-prints the server's responses.
"""

import asyncio
import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

HOST     = '127.0.0.1'
PORT     = 34083
DELAY    = 0.4   # seconds between commands (let server respond fully)
WIDTH    = 72
# strftime format: %Y=4-digit year, %m=month, %d=day, %H=hour(24h), %M=minute, %S=second
# e.g. bot_session_2026-06-27_143022.log
LOG_FILE = Path(f'bot_session_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log')

_logfile = None  # opened in run_bot(); shared by all print helpers


def _log(text: str = '') -> None:
    """Print to stdout and mirror to the session log file."""
    print(text)
    if _logfile is not None:
        _logfile.write(text + '\n')


# ---------------------------------------------------------------------------
# Wire helpers (mirrors simple_client.py without the interactive bits)
# ---------------------------------------------------------------------------

async def _send(writer, obj: dict) -> None:
    data = json.dumps(obj).encode() + b'\n'
    writer.write(data)
    try:
        await writer.drain()
    except ConnectionResetError:
        pass


async def _recv(reader, timeout: float = 3.0) -> dict | None:
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not raw:
            return None
        return json.loads(raw.strip())
    except asyncio.TimeoutError:
        return None
    except Exception as e:
        _log(f'  [recv error: {e}]')
        return None


async def _recv_all(reader, timeout: float = 1.5) -> list[dict]:
    """Drain messages until the server goes quiet or a prompt is seen."""
    msgs = []
    while True:
        msg = await _recv(reader, timeout=timeout)
        if msg is None:
            break
        msgs.append(msg)
        # Stop collecting once we see a prompt — server is waiting for us
        if msg.get('prompt'):
            break
    return msgs


async def _drain_until(reader, target_prompt: str, timeout: float = 3.0) -> list[dict]:
    """Drain ALL messages until a specific prompt value is seen.

    Used after multi-step sequences (login, quit) where the server sends
    several messages before it's ready for the next command.
    """
    all_msgs: list[dict] = []
    while True:
        msgs = await _recv_all(reader, timeout=timeout)
        if not msgs:
            break
        all_msgs.extend(msgs)
        last = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        if last == target_prompt:
            break
    return all_msgs


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def _print_msg(msg: dict) -> None:
    lines = msg.get('lines', [])
    if isinstance(lines, str):
        lines = [lines]
    for line in lines:
        if line:
            for wrapped in textwrap.wrap(line, WIDTH) or [line]:
                _log(f'  {wrapped}')
        else:
            _log()
    prompt = msg.get('prompt', '')
    if prompt:
        _log(f'  [{prompt}]')


def _print_exchange(label: str, msgs: list[dict]) -> None:
    _log(f'\n{"─" * WIDTH}')
    _log(f'  ← {label}')
    _log(f'{"─" * WIDTH}')
    for msg in msgs:
        _print_msg(msg)


def _print_send(cmd: str) -> None:
    _log(f'\n  → {cmd!r}')


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------

async def _handshake(reader, writer) -> bool:
    # Receive server Init
    server_init = await _recv(reader, timeout=5.0)
    if not server_init:
        _log('No Init from server.')
        return False
    _log(f'  Server: {server_init.get("server_id", "?")}  '
         f'key={server_init.get("server_key", "?")}')

    # Echo the server's own id/key back — server validates they match.
    await _send(writer, {
        'server_id':  server_init.get('server_id',  'test_server'),
        'server_key': server_init.get('server_key', 'test_key'),
    })

    # Drain setup messages until we reach the login prompt.
    # Server sequence: Handshake OK → terminal menu (prompt "> ") →
    #   terminal-type prompt → [we send 'A'] → ANSI confirm → TADA
    #   banner → login prompt ("login> ").
    # We keep draining and answering until we see "login> ".
    phase = 0
    while True:
        msgs = await _recv_all(reader, timeout=3.0)
        if not msgs:
            break
        _print_exchange(f'Setup {phase}', msgs)
        phase += 1

        last_prompt = next(
            (m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')),
            '',
        )
        if last_prompt == 'login> ':
            break  # at the login prompt — ready for the script
        if 'terminal type' in last_prompt.lower():
            # Server is explicitly waiting for terminal-type choice; answer ANSI.
            # Generic "> " prompts during setup are just ctx.send() artifacts —
            # the server is not blocked on those, so we don't respond to them.
            await _send(writer, {'lines': ['A'], 'mode': 'login'})

    return True


# ---------------------------------------------------------------------------
# Bot script
# ---------------------------------------------------------------------------

async def run_bot(host: str, port: int, user: str, password: str) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_client session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}  user={user}')

    _log(f'Connecting to {host}:{port} ...')
    try:
        reader, writer = await asyncio.open_connection(host, port)
    except ConnectionRefusedError:
        _log(f'Connection refused — is the server running on port {port}?')
        _logfile.close()
        sys.exit(1)

    _log('Connected.')

    if not await _handshake(reader, writer):
        writer.close()
        _logfile.close()
        return

    # Script: list of (command_string, mode_string, description)
    script = [
        (f'connect {user} {password}', 'login', 'Log in'),
        ('look',                        'game',  'Look around'),
        ('help',                        'game',  'Help menu'),
        ('inv',                         'game',  'Check inventory'),
        ('stats',                        'game',  'Check stats'),
        ('quit',                         'game',  'Quit'),
    ]

    for cmd, mode, description in script:
        await asyncio.sleep(DELAY)
        display_cmd = cmd if 'password' not in description.lower() else f'connect {user} ****'
        _print_send(f'{display_cmd}  ({description})')

        await _send(writer, {'lines': [cmd], 'mode': mode})

        if cmd.startswith('connect ') or mode == 'game':
            # The game loop sends "main> " BEFORE reading each command, so the
            # prompt for the current iteration arrives in the NEXT recv window.
            # Drain until we see "main> " to consume both the response and the
            # next game prompt as one logical exchange.
            # For paginated output (More prompt) send Q to skip to the end.
            msgs = []
            while True:
                batch = await _recv_all(reader, timeout=3.0)
                if not batch:
                    break
                msgs.extend(batch)
                last_p = next((m.get('prompt', '') for m in reversed(batch) if m.get('prompt')), '')
                if last_p == 'main> ':
                    break
                if 'more' in last_p.lower():
                    # Dismiss the More prompt so output continues to the game prompt
                    await _send(writer, {'lines': ['Q'], 'mode': 'game'})
        else:
            msgs = await _recv_all(reader, timeout=3.0)
        _print_exchange(description, msgs)

        # Quit triggers a Y/N confirmation; answer Y and drain the farewell sequence
        if cmd == 'quit' and any('leave spur' in ' '.join(m.get('lines', [])).lower() or
                                  'leave' in m.get('prompt', '').lower()
                                  for m in msgs):
            await asyncio.sleep(DELAY)
            _print_send('Y  (confirm quit)')
            await _send(writer, {'lines': ['Y'], 'mode': 'game'})
            msgs = await _recv_all(reader, timeout=4.0)
            _print_exchange('Quit sequence', msgs)

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    _log(f'\n{"═" * WIDTH}')
    _log('  Bot session complete.')
    _log(f'{"═" * WIDTH}')
    _log(f'# log written to {LOG_FILE}')

    _logfile.close()
    print(f'Log saved to {LOG_FILE}')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA bot client')
    parser.add_argument('--host',     default=HOST)
    parser.add_argument('--port',     type=int, default=PORT)
    parser.add_argument('--user',     default='test')
    parser.add_argument('--password', default='test')
    args = parser.parse_args()

    asyncio.run(run_bot(args.host, args.port, args.user, args.password))
