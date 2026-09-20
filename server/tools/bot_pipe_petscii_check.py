#!/usr/bin/env python3
"""Live check: what does a real Commodore/PETSCII client actually receive
on the wire when another player says something containing literal '|'
characters?

A PETSCII client can't type '|' itself (no keyboard byte decodes to it --
see network_context.py's _petscii_input_to_ascii), so this drives TWO
bots: botlasso connects over the JSON/ANSI port and types `say "|||"`,
while botdummy connects directly to the raw PETSCII port (both start in
level 1 room 1, see setup_bot_accounts.py) and we dump the exact raw
bytes botdummy's connection receives for that broadcast.

Run with: .venv/bin/python3 tools/bot_pipe_petscii_check.py
"""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot_credentials import load_password

HOST = '127.0.0.1'
JSON_PORT = 45001
PETSCII_PORT = 45002


def to_petscii_input(text: str) -> bytes:
    """Encode *text* as the raw keyboard bytes a real C64 would send so
    that server/network_context.py's _petscii_input_to_ascii() decodes it
    back to *text*. Covers only what this script needs: lowercase
    letters, digits, space, and '"'."""
    out = bytearray()
    for ch in text:
        o = ord(ch)
        if 0x20 <= o <= 0x40:              # space, digits, punctuation
            out.append(o)
        elif 'a' <= ch <= 'z':              # unshifted key -> +0x20 lowercase
            out.append(o - 0x20)
        elif 'A' <= ch <= 'Z':              # shifted key in lowercase charset
            out.append(o + 0x80)
        else:
            raise ValueError(f'to_petscii_input: unsupported char {ch!r}')
    return bytes(out)


# ---------------------------------------------------------------------------
# JSON/ANSI bot (botlasso) -- says the pipe text
# ---------------------------------------------------------------------------

async def _json_send(writer, obj):
    writer.write(json.dumps(obj).encode() + b'\n')
    await writer.drain()


async def _json_recv(reader, timeout=3.0):
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not raw:
            return None
        return json.loads(raw.strip())
    except asyncio.TimeoutError:
        return None


async def _json_recv_all(reader, timeout=1.5):
    msgs = []
    while True:
        msg = await _json_recv(reader, timeout=timeout)
        if msg is None:
            break
        msgs.append(msg)
        lines = msg.get('lines') or []
        if not lines and msg.get('prompt'):
            break
    return msgs


async def _json_send_and_page(writer, reader, obj, timeout=4.0):
    """Send obj, then keep pressing Enter through any '-- End [n/m] --'
    pagination prompts (login banner etc.) until a real blocking prompt
    is reached. Returns the combined list of messages."""
    await _json_send(writer, obj)
    all_msgs = await _json_recv_all(reader, timeout=timeout)
    while all_msgs:
        last_prompt = next((m.get('prompt', '') for m in reversed(all_msgs) if m.get('prompt')), '')
        if '[?=help]' not in last_prompt and 'End [' not in last_prompt:
            break
        await _json_send(writer, {'lines': [''], 'mode': obj.get('mode', 'login')})
        all_msgs = await _json_recv_all(reader, timeout=timeout)
    return all_msgs


async def run_json_bot(say_ready: asyncio.Event, say_done: asyncio.Event,
                        room_found: asyncio.Event, room_box: dict):
    user = 'botlasso'
    password = load_password(user)
    reader, writer = await asyncio.open_connection(HOST, JSON_PORT)
    init = await _json_recv(reader, timeout=5.0)
    await _json_send(writer, {'server_id': init.get('server_id', 'test_server'),
                               'server_key': init.get('server_key', 'test_key')})

    # Step 1: drain up to and including the terminal-negotiation prompt.
    msgs = await _json_recv_all(reader, timeout=5.0)
    last = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
    print('[botlasso] after handshake, prompt:', repr(last))

    # Step 2: if asked for terminal type, answer 'A' and drain that
    # response fully (this is what lands us at the login prompt).
    if 'terminal type' in last.lower():
        msgs = await _json_send_and_page(writer, reader, {'lines': ['A'], 'mode': 'login'})
        last = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        print('[botlasso] after terminal type, prompt:', repr(last))

    # Step 3: now actually send connect.
    login_msgs = await _json_send_and_page(
        writer, reader, {'lines': [f'connect {user} {password}'], 'mode': 'login'})
    print('[botlasso] full login response:')
    for m in login_msgs:
        print('   ', m)

    # botlasso's current room has a "tough" monster (GUARDIAN) that blocks
    # teleporting *away* (commands/teleport.py's _teleport() -- "casts a
    # Freeze Adventurer spell" and refuses the move), so don't try to move
    # botlasso. Instead look up its (level, room) via 'teleport #find' and
    # have botdummy come to it.
    find_msgs = await _json_send_and_page(writer, reader, {'lines': ['teleport #find rocky ravine'], 'mode': 'game'})
    find_text = ' '.join(l for m in find_msgs for l in (m.get('lines') or []))
    print('[botlasso] find response text:', find_text)
    m = re.search(r'Level (\d+), room (\d+)', find_text)
    level, room = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    print(f'[botlasso] resolved location: level={level} room={room}')
    room_box['level'], room_box['room'] = level, room
    room_found.set()

    await say_ready.wait()   # wait until botdummy has joined the room
    await asyncio.sleep(1.0)  # let botdummy's arrival trickle fully settle

    say_msgs = await _json_send_and_page(writer, reader, {'lines': ['say "|||"'], 'mode': 'game'})
    print('[botlasso] say response:', say_msgs)

    await _json_send(writer, {'lines': ['quit'], 'mode': 'game'})
    await _json_recv_all(reader, timeout=2.0)
    await _json_send(writer, {'lines': ['Y'], 'mode': 'game'})
    await _json_recv_all(reader, timeout=2.0)

    say_done.set()
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Raw PETSCII bot (botdummy) -- receives the broadcast, dumps raw bytes
# ---------------------------------------------------------------------------

async def run_petscii_bot(say_ready: asyncio.Event, say_done: asyncio.Event,
                           room_found: asyncio.Event, room_box: dict):
    user = 'botdummy'
    password = load_password(user)
    reader, writer = await asyncio.open_connection(HOST, PETSCII_PORT)

    # Drain the greeting / terminal-width prompt, then pick 40-column.
    await reader.readuntil(b'\r')  # up through "Screen width [4/8] > "
    writer.write(to_petscii_input('4') + b'\r')
    await writer.drain()

    # Drain "40 column mode set." + login banner, up through "login > ".
    await reader.readuntil(b'\r')
    writer.write(to_petscii_input(f'connect {user} {password}') + b'\r')
    await writer.drain()

    # Drain post-login welcome/room text up to the game prompt. Login sends
    # several separate ctx.send() bursts (welcome, guild greeting, mail
    # check, board-thread check, tip box, equip messages, room text) with
    # small gaps between them, so use a longer idle timeout than a single
    # read's gap to know we've actually reached the prompt.
    try:
        while True:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=1.5)
            if not chunk:
                break
    except asyncio.TimeoutError:
        pass

    # Join botlasso's room (see run_json_bot -- botlasso itself can't
    # leave, so botdummy comes to it instead).
    await room_found.wait()
    level, room = room_box.get('level'), room_box.get('room')
    if level is not None and room is not None:
        writer.write(to_petscii_input(f'#{level} {room}') + b'\r')
        await writer.drain()
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=1.5)
                if not chunk:
                    break
        except asyncio.TimeoutError:
            pass
    else:
        print('[botdummy] WARNING: could not resolve botlasso room, staying put')

    say_ready.set()
    await say_done.wait()

    # Collect whatever arrives after botlasso's say -- the broadcast line.
    collected = bytearray()
    try:
        while True:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=3.0)
            if not chunk:
                break
            collected.extend(chunk)
    except asyncio.TimeoutError:
        pass

    print('=== raw bytes received by botdummy (PETSCII) after the say ===')
    print(repr(bytes(collected)))
    print()
    print('=== hex ===')
    print(collected.hex(' '))

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def main():
    say_ready = asyncio.Event()
    say_done = asyncio.Event()
    room_found = asyncio.Event()
    room_box = {}
    await asyncio.gather(
        run_petscii_bot(say_ready, say_done, room_found, room_box),
        run_json_bot(say_ready, say_done, room_found, room_box),
    )


if __name__ == '__main__':
    asyncio.run(main())
