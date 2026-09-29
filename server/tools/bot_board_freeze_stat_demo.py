#!/usr/bin/env python3
"""tools/bot_board_freeze_stat_demo.py — Live smoke test for the
sig-editor project's Stat column ('*NEW*'/'*NRB*'/'*FZN*') and
freeze/unfreeze feature (commands/board/reply.py's end-of-bulletin
'F'/'O' options): posts a thread, freezes it via the interactive
reader, confirms the listing shows '*FZN*' and a direct reply is
refused, then unfreezes it again.

Run against a server (point --port at whichever instance you're testing,
e.g. the sig-editor sandbox rather than the live default 34083):
    python tools/bot_board_freeze_stat_demo.py --port 34090
"""
import argparse
import asyncio
import json
import re

from bot_credentials import load_password

HOST = '127.0.0.1'
PORT = 34083


async def _send(writer, obj):
    writer.write(json.dumps(obj).encode() + b'\n')
    await writer.drain()


async def _recv(reader, timeout=3.0):
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not raw:
            return None
        return json.loads(raw.strip())
    except asyncio.TimeoutError:
        return None


async def _recv_all(reader, timeout=1.5):
    msgs = []
    while True:
        msg = await _recv(reader, timeout=timeout)
        if msg is None:
            break
        msgs.append(msg)
        lines = msg.get('lines') or []
        if not lines and msg.get('prompt'):
            break
    return msgs


def _text(msgs):
    parts = []
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        parts.extend(str(l) for l in lines)
    return '\n'.join(parts)


def _print(msgs):
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        for l in lines:
            print(l)
        if m.get('prompt'):
            print(f'  [{m["prompt"]}]')


async def _say(writer, reader, cmd, mode='game', timeout=4.0):
    print(f"\n=== -> {cmd!r} ===")
    await _send(writer, {'lines': [cmd], 'mode': mode})
    msgs = await _recv_all(reader, timeout=timeout)
    _print(msgs)
    while msgs and 'more' in (msgs[-1].get('prompt') or '').lower():
        await _send(writer, {'lines': ['Q'], 'mode': mode})
        more = await _recv_all(reader, timeout=timeout)
        _print(more)
        msgs += more
    return msgs


async def main(host: str, port: int, user: str, password: str) -> None:
    reader, writer = await asyncio.open_connection(host, port)
    init = await _recv(reader, timeout=5.0)
    await _send(writer, {'server_id': init.get('server_id', 'test_server'),
                          'server_key': init.get('server_key', 'test_key')})
    while True:
        msgs = await _recv_all(reader, timeout=3.0)
        if not msgs:
            break
        last = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        if last == 'login> ':
            break
        if 'terminal type' in last.lower():
            await _send(writer, {'lines': ['A'], 'mode': 'login'})
        elif '-- ' in last and ('more' in last.lower() or 'end' in last.lower()):
            # Paginated pre-login banner (network_context.py's _paginate())
            # -- blank/Enter advances a page, including the last one, which
            # is what actually reaches the real login prompt. Without
            # answering this, _recv_all() just times out mid-banner and the
            # outer loop above wrongly treats that as "handshake done."
            await _send(writer, {'lines': [''], 'mode': 'login'})

    await _say(writer, reader, f'connect {user} {password}', 'login')

    title = 'Freeze/Stat demo thread'

    print('\n\n########## POSTING A FRESH THREAD ##########')
    await _say(writer, reader, 'board post')
    await _say(writer, reader, title)
    await _say(writer, reader, 'n')  # anonymous? no
    await _say(writer, reader, 'Kicking the tires on freeze/unfreeze and the Stat column.')
    msgs = await _say(writer, reader, '.s')  # save
    posted_text = _text(msgs)
    match = re.search(r'Thread #(\d+) posted', posted_text)
    assert match, f'Post did not confirm with an id: {posted_text!r}'
    thread_id = match.group(1)
    print(f'--- posted thread id: {thread_id} ---')

    row_pattern = re.compile(rf'^\s*{re.escape(thread_id)}\s')

    def _row_for_my_thread(listing_text: str) -> str:
        """The board may already hold other threads that also show
        '*NEW*' independently of anything this script does (including,
        it turns out, an identically-titled leftover from an earlier
        aborted run of this very script) -- every assertion below has
        to check *this thread's own row*, matched by its own id at the
        start of the row, not by title text."""
        row = next((l for l in listing_text.splitlines() if row_pattern.match(l)), None)
        assert row, f'Could not find a listing row for id {thread_id}:\n{listing_text}'
        return row

    print('\n\n########## LISTING BEFORE FREEZE (expect *NEW*, no *FZN*) ##########')
    msgs = await _say(writer, reader, 'board')
    row = _row_for_my_thread(_text(msgs))
    assert '*NEW*' in row, f'Expected *NEW* on my thread row: {row!r}'
    assert '*FZN*' not in row, f'Should not be frozen yet: {row!r}'
    await _say(writer, reader, '')  # leave listing

    print('\n\n########## ENSURING PROMPT MODE IS ON ##########')
    # botdummy is a shared, reused test account -- Prompt Mode may already
    # be on from an earlier session, in which case toggling it blindly
    # would turn it OFF. Check the confirmation text and toggle again if
    # this flipped it the wrong way.
    msgs = await _say(writer, reader, 'pm')
    if 'Prompt Mode: Off.' in _text(msgs):
        await _say(writer, reader, 'pm')

    print('\n\n########## READING THE THREAD AND FREEZING IT (poster permission) ##########')
    await _say(writer, reader, f'board {thread_id}')  # jumps straight to it -- ids are globally unique
    msgs2 = await _say(writer, reader, 'f')  # freeze
    freeze_text = _text(msgs2)
    assert 'Bulletin frozen.' in freeze_text, f'Freeze did not confirm: {freeze_text!r}'
    await _say(writer, reader, 'q')  # back to listing

    print('\n\n########## LISTING AFTER FREEZE (expect *FZN*, not *NEW*) ##########')
    msgs = await _say(writer, reader, 'board')
    row = _row_for_my_thread(_text(msgs))
    assert '*FZN*' in row, f'Expected *FZN* after freezing: {row!r}'
    assert '*NEW*' not in row, f'*FZN* should take priority over *NEW*: {row!r}'
    await _say(writer, reader, '')  # leave listing

    print('\n\n########## CONFIRMING A DIRECT REPLY IS REFUSED WHILE FROZEN ##########')
    msgs = await _say(writer, reader, f'board reply {thread_id}')
    reply_refused_text = _text(msgs)
    assert 'frozen' in reply_refused_text.lower(), f'Expected frozen refusal: {reply_refused_text!r}'

    print('\n\n########## UNFREEZING VIA "O" (redisplay) THEN "F" AGAIN ##########')
    await _say(writer, reader, f'board {thread_id}')
    await _say(writer, reader, 'o')  # redisplay, doesn't advance
    msgs = await _say(writer, reader, 'f')  # toggle back to unfrozen
    unfreeze_text = _text(msgs)
    assert 'Bulletin unfrozen.' in unfreeze_text, f'Unfreeze did not confirm: {unfreeze_text!r}'
    await _say(writer, reader, 'q')

    print('\n\n########## FINAL LISTING (expect *NEW* again, not *FZN*) ##########')
    msgs = await _say(writer, reader, 'board')
    row = _row_for_my_thread(_text(msgs))
    assert '*NEW*' in row, f'Expected *NEW* again after unfreezing: {row!r}'
    assert '*FZN*' not in row, f'Should be unfrozen now: {row!r}'
    await _say(writer, reader, '')

    print('\n\n########## ALL ASSERTIONS PASSED ##########')

    await _say(writer, reader, 'quit')
    await _say(writer, reader, 'Y')

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--user', default='botdummy')
    parser.add_argument('--password', default=None)
    args = parser.parse_args()
    password = args.password or load_password(args.user)
    asyncio.run(main(args.host, args.port, args.user, password))
