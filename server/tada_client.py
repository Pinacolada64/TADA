#!/usr/bin/env python3
"""tada_client.py — prompt_toolkit-based async client for the TADA server (Totally Awesome Dungeon Adventure).

Layout
------
┌─────────────────────────────────────────┐
│  output area  (scrollable, PgUp/PgDn)  │
├─────────────────────────────────────────┤
│  status bar   (connection / mode)       │
├─────────────────────────────────────────┤
│  input line   (dedicated prompt area)   │
└─────────────────────────────────────────┘

The asyncio receive loop appends incoming lines to the output buffer while
the player types freely in the input line — no blocking on input().
"""

import argparse
import asyncio
import getpass
import json
import logging
import re
import sys
from datetime import datetime

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import is_done
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window, ConditionalContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.processors import Processor, Transformation
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

# commands/connect.py sends "Welcome, <name>!" (or "Welcome, <name>,
# Wraith Master of Spur!" for that title) on successful login, and
# "Welcome, <guest name>!" for guests -- stop at the first ',' or '!' so
# both forms yield just the name.
_WELCOME_RE = re.compile(r'^Welcome, ([^,!]+)')

_STYLE = Style.from_dict({
    'output-field': 'bg:#1a1a2e #e0e0e0',
    'status-bar':   'bg:#16213e #a0c4ff bold',
    'input-field':  'bg:#0f3460 #e0e0e0',
    'prompt-mark':  '#f0a500 bold',
})

# ---------------------------------------------------------------------------
# ANSI lexer for the output buffer
# ---------------------------------------------------------------------------

class _AnsiLexer(Lexer):
    """Interpret ANSI escape sequences stored in the output Buffer per line."""
    def lex_document(self, document):
        lines = document.lines
        def get_line(lineno):
            if 0 <= lineno < len(lines):
                try:
                    return list(to_formatted_text(ANSI(lines[lineno])))
                except Exception:
                    return [('', lines[lineno])]   # fall back to plain text
            return []
        return get_line

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

class ClientState:
    def __init__(self, debug: bool = False):
        self.mode            = 'init'
        self.user_id         = None
        self.character_name  = None   # set once login succeeds -- see _receive_loop()
        self.connected       = False
        self.host            = ''
        self.port            = 0
        self.debug           = debug
        self.prompt_text     = '> '   # updated from each Message's 'prompt' field

    @property
    def status_text(self) -> str:
        # Before login succeeds (character_name unknown yet), show the
        # original connection/mode status.
        if not self.character_name:
            conn = f'{self.host}:{self.port}' if self.connected else 'disconnected'
            user = self.user_id or '(not logged in)'
            return f' TADA  {conn}  |  {user}  |  {self.mode} '

        # Logged in: simple "TADA | host:port | character" line. Mode is
        # only shown with --debug, since it's not something a player needs
        # to see day to day.
        text = f' TADA | {self.host}:{self.port} | {self.character_name} '
        if self.debug:
            text = text.rstrip() + f' | {self.mode} '
        return text


# ---------------------------------------------------------------------------
# Clean shutdown helper
# ---------------------------------------------------------------------------

def _force_quit(app: 'Application', writer: asyncio.StreamWriter | None = None) -> None:
    """Cancel all blocking waits and exit the app in one shot.

    Cancels the pending input future  → _input_loop wakes and breaks.
    Closes the writer (transport)     → reader.readline() returns b'' → _receive_loop breaks.
    Calls app.exit()                  → app.run_async() returns.
    """
    fut = getattr(app, '_input_future', None)
    if fut and not fut.done():
        try:
            fut.get_loop().call_soon_threadsafe(fut.cancel)
        except Exception:
            pass
    w = writer or getattr(app, '_writer', None)
    if w:
        try:
            w.close()
        except Exception:
            pass
    try:
        app.exit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Output buffer helpers
# ---------------------------------------------------------------------------

_SCROLLBACK = 2000   # maximum lines kept in the output buffer

def _append_output(output_buffer: Buffer, lines: list[str]) -> None:
    """Append lines to the output buffer, trimming old content if needed."""
    text = output_buffer.text
    existing = text.split('\n') if text else []
    existing.extend(lines)
    if len(existing) > _SCROLLBACK:
        existing = existing[-_SCROLLBACK:]
    new_text = '\n'.join(existing)
    # Cursor at end: BufferControl auto-scrolls to keep cursor in view,
    # which pins the output to the bottom — exactly like a terminal.
    output_buffer.set_document(Document(new_text, len(new_text)), bypass_readonly=True)


# ---------------------------------------------------------------------------
# Wire protocol  (newline-delimited JSON, matching simple_server.py)
# ---------------------------------------------------------------------------

async def _recv_message(reader: asyncio.StreamReader) -> dict | None:
    try:
        raw = await reader.readline()
        if not raw:
            return None
        return json.loads(raw.strip().decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning('recv decode error: %s', e)
        return None
    except Exception:
        return None


async def _send_message(writer: asyncio.StreamWriter, obj: dict) -> None:
    data = json.dumps(obj).encode('utf-8') + b'\n'
    writer.write(data)
    await writer.drain()


# ---------------------------------------------------------------------------
# Receive coroutine — runs concurrently with the prompt_toolkit event loop
# ---------------------------------------------------------------------------

async def _receive_loop(
    reader:        asyncio.StreamReader,
    output_buffer: Buffer,
    state:         ClientState,
    app:           Application,
) -> None:
    """Read messages from the server and push them into the output buffer."""
    while True:
        msg = await _recv_message(reader)
        if msg is None:
            _append_output(output_buffer, ['', '[disconnected from server]'])
            state.connected = False
            app.invalidate()
            _force_quit(app)   # unblock _input_loop so the TaskGroup can exit
            break

        try:
            lines = msg.get('lines', [])
            if isinstance(lines, str):
                lines = [lines]

            if lines:
                _append_output(output_buffer, lines)
                for line in lines:
                    match = _WELCOME_RE.match(line)
                    if match:
                        state.character_name = match.group(1)
                        break

            if 'mode' in msg:
                state.mode = msg['mode']

            if 'prompt' in msg and msg['prompt']:
                state.prompt_text = msg['prompt']

            if 'user_id' in msg:
                state.user_id = msg['user_id']

            if msg.get('mode') == 'bye':
                state.connected = False
                _force_quit(app)   # unblock _input_loop so the TaskGroup can exit
        except Exception:
            log.exception('_receive_loop: error processing message: %r', msg)

        app.invalidate()


# ---------------------------------------------------------------------------
# Build the prompt_toolkit Application
# ---------------------------------------------------------------------------

def _build_app(state: ClientState) -> tuple[Application, Buffer, Buffer]:
    """Return (app, output_buffer, input_buffer)."""

    # --- output area (ANSI-aware, scrollable) ---
    # BufferControl auto-scrolls by keeping cursor in view. _AnsiLexer
    # interprets ANSI escape sequences so colours render correctly.
    output_buffer = Buffer(name='output', read_only=True)

    output_window = Window(
        content=BufferControl(
            buffer=output_buffer,
            lexer=_AnsiLexer(),
            focusable=False,
        ),
        wrap_lines=True,
        style='class:output-field',
    )

    # --- status bar ---
    def _status_text():
        return [('class:status-bar', state.status_text)]

    status_window = Window(
        content=FormattedTextControl(_status_text),
        height=1,
        style='class:status-bar',
    )

    # --- input area ---
    input_buffer = Buffer(name='input', multiline=False)

    input_window = Window(
        content=BufferControl(buffer=input_buffer, focusable=True),
        height=1,
        style='class:input-field',
        get_line_prefix=lambda line_no, wrap_count: [('class:prompt-mark', state.prompt_text)],
    )

    layout = Layout(
        HSplit([
            output_window,
            status_window,
            input_window,
        ]),
        focused_element=input_window,
    )

    # --- key bindings ---
    kb = KeyBindings()

    @kb.add('c-c')
    @kb.add('c-q')
    def _exit(event):
        _force_quit(event.app)

    @kb.add('pageup')
    def _page_up(event):
        # Move the cursor up by one page; BufferControl scrolls to follow it.
        #
        # step must be the FULL window_height, not window_height - 2: the
        # cursor starts at the last visible line (bottom of the viewport),
        # so a jump of only window_height - 2 lines still lands inside the
        # *current* viewport -- prompt_toolkit only scrolls when the cursor
        # actually leaves the visible range, so that first press was a
        # silent no-op and the viewport only caught up on the second press.
        # A full-window_height jump always lands at least one line outside
        # the old viewport, so every press scrolls immediately.
        info = output_window.render_info
        step = info.window_height if info else 10
        doc  = output_buffer.document
        # Count back `step` newlines from the current cursor position
        before = doc.text[:doc.cursor_position]
        lines  = before.split('\n')
        target = '\n'.join(lines[:-step]) if len(lines) > step else ''
        output_buffer.set_document(Document(doc.text, len(target)), bypass_readonly=True)

    @kb.add('pagedown')
    def _page_down(event):
        # Move the cursor down by one page; clamp to end of buffer.
        # See _page_up's comment: must be a full window_height, not
        # window_height - 2, or the first press is a silent no-op.
        info = output_window.render_info
        step = info.window_height if info else 10
        doc  = output_buffer.document
        before = doc.text[:doc.cursor_position]
        after  = doc.text[doc.cursor_position:]
        down_lines = after.split('\n')
        if len(down_lines) <= step:
            new_pos = len(doc.text)   # already at or near bottom
        else:
            new_pos = doc.cursor_position + len('\n'.join(down_lines[:step]))
        output_buffer.set_document(Document(doc.text, new_pos), bypass_readonly=True)

    @kb.add('enter')
    def _send(event):
        # Handled in the main loop via input_buffer.on_text_changed / asyncio
        # We just signal the waiting coroutine via a Future stored on the app.
        text = input_buffer.text
        input_buffer.reset()
        if hasattr(event.app, '_input_future') and event.app._input_future and \
                not event.app._input_future.done():
            event.app._input_future.get_loop().call_soon_threadsafe(
                event.app._input_future.set_result, text
            )

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=_STYLE,
        full_screen=True,
        mouse_support=False,
    )
    app._input_future = None
    return app, output_buffer, input_buffer


# ---------------------------------------------------------------------------
# Input helper — waits for the user to press Enter
# ---------------------------------------------------------------------------

async def _get_input(app: Application) -> str | None:
    """Suspend until the user presses Enter; returns the typed text."""
    loop = asyncio.get_event_loop()
    fut  = loop.create_future()
    app._input_future = fut
    try:
        return await fut
    except asyncio.CancelledError:
        return None
    finally:
        app._input_future = None


# ---------------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------------

async def _login(
    writer:        asyncio.StreamWriter,
    output_buffer: Buffer,
    state:         ClientState,
    app:           Application,
    user_id:       str,
    password:      str,
) -> bool:
    """Send handshake + credentials; return True on success."""
    # Handshake
    await _send_message(writer, {
        'mode':             'init',
        'server_id':        'test_server',
        'server_key':       'test_key',
        'protocol_version': 1,
        'translation':      'UTF-8',
    })
    _append_output(output_buffer, [f'Connecting to {state.host}:{state.port}...'])
    app.invalidate()

    # Credentials — server's _login() prompts "connect <user> <pass>" as a text command
    if user_id == 'guest':
        await _send_message(writer, {'mode': 'login', 'type': 'command', 'text': 'connect guest'})
    else:
        await _send_message(writer, {'mode': 'login', 'type': 'command', 'text': f'connect {user_id} {password}'})

    state.user_id = user_id
    state.mode    = 'login'
    return True


# ---------------------------------------------------------------------------
# Main input loop — runs inside app.run_async()
# ---------------------------------------------------------------------------

async def _input_loop(
    writer:        asyncio.StreamWriter,
    output_buffer: Buffer,
    state:         ClientState,
    app:           Application,
) -> None:
    """Read lines from the input area and send them to the server."""
    while state.connected:
        text = await _get_input(app)
        if text is None:
            break
        text = text.strip()

        # Echo what the user typed into the output pane
        if text:
            _append_output(output_buffer, [f'> {text}'])
            app.invalidate()

        if text.lower() in ('quit', 'exit', '/quit'):
            await _send_message(writer, {'mode': state.mode, 'type': 'command', 'text': 'quit'})
            break

        await _send_message(writer, {'mode': state.mode, 'type': 'command', 'text': text})

    app.exit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run(host: str, port: int, user_id: str, password: str, debug: bool = False) -> None:
    state = ClientState(debug=debug)
    state.host = host
    state.port = port

    try:
        reader, writer = await asyncio.open_connection(host, port)
        state.connected = True
    except OSError as e:
        print(f'Connection failed: {e}', file=sys.stderr)
        return

    app, output_buffer, input_buffer = _build_app(state)
    app._writer = writer   # lets _force_quit close the transport from key bindings

    _append_output(output_buffer, [
        ' ╔══════════════════════════════════════════════════╗',
        ' ║  TADA — Totally Awesome Dungeon Adventure        ║',
        ' ║  prompt_toolkit client                           ║',
        ' ║                                                  ║',
        ' ║  PgUp / PgDn  scroll output                      ║',
        ' ║  Ctrl-C / Ctrl-Q  quit   •   or type: quit       ║',
        ' ╚══════════════════════════════════════════════════╝',
        '',
    ])

    await _login(writer, output_buffer, state, app, user_id, password)

    async def _run_app_safe():
        try:
            await app.run_async()
        except Exception:
            log.exception('app.run_async() raised')

    async with asyncio.TaskGroup() as tg:
        tg.create_task(_receive_loop(reader, output_buffer, state, app))
        tg.create_task(_input_loop(writer, output_buffer, state, app))
        tg.create_task(_run_app_safe())

    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description='TADA prompt_toolkit client')
    parser.add_argument('host',     nargs='?', default='localhost')
    parser.add_argument('port',     nargs='?', type=int, default=34083)
    parser.add_argument('--user',   default='')
    parser.add_argument('--guest',  action='store_true')
    parser.add_argument('--debug',  action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        filename='tada_client.log',
    )

    if args.guest:
        user_id  = 'guest'
        password = 'guest'
    else:
        user_id  = args.user or input('Username: ').strip() or 'guest'
        password = getpass.getpass('Password: ') if user_id != 'guest' else 'guest'

    try:
        asyncio.run(run(args.host, args.port, user_id, password, debug=args.debug))
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == '__main__':
    sys.exit(main())
