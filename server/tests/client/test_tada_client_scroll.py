"""tests/test_tada_client_scroll.py

Regression test for a real bug reported live: tada_client.py's PgUp/PgDn
key bindings needed to be pressed twice before the output viewport
actually scrolled.

Root cause: _page_up()/_page_down() moved the cursor by
`window_height - 2` lines per press (a deliberate 2-line overlap between
pages). Since the cursor normally rests at the very last visible line
(the output pane auto-tracks new text), a jump of window_height - 2
still landed *inside* the currently-rendered viewport -- prompt_toolkit
only rescrolls when the cursor actually leaves the visible range, so
the first press was a silent no-op and the viewport only caught up on
the second press. Fixed by jumping a full window_height instead.

Run with:
    python -m pytest tests/test_tada_client_scroll.py -v
"""
from __future__ import annotations

import asyncio
import unittest

from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import tada_client as tc

_PAGE_UP   = '\x1b[5~'
_PAGE_DOWN = '\x1b[6~'


async def _drive_pgup_pgdn(num_lines: int, presses: list[str]) -> list[int]:
    """Build the real app, seed it with num_lines of output, send each key
    in *presses* in order, and return the vertical_scroll reading after
    each one."""
    state = tc.ClientState()
    app, output_buffer, input_buffer = tc._build_app(state)

    text = "\n".join(f"line {i}" for i in range(num_lines))
    output_buffer.set_document(Document(text, len(text)), bypass_readonly=True)

    readings: list[int] = []
    with create_pipe_input() as pipe_input:
        app.output = DummyOutput()
        app.input = pipe_input
        run_task = asyncio.ensure_future(app.run_async())
        await asyncio.sleep(0.2)

        out_win = next(
            w for w in app.layout.find_all_windows()
            if getattr(w.content, 'buffer', None) is output_buffer
        )

        for key in presses:
            pipe_input.send_text(key)
            await asyncio.sleep(0.2)
            readings.append(out_win.render_info.vertical_scroll)

        app.exit()
        try:
            await run_task
        except Exception:
            pass

    return readings


class TestPageUpPageDownScrollsImmediately(unittest.IsolatedAsyncioTestCase):

    async def test_every_consecutive_pageup_press_moves_the_viewport(self):
        readings = await _drive_pgup_pgdn(200, [_PAGE_UP, _PAGE_UP, _PAGE_UP, _PAGE_UP])
        self.assertEqual(len(readings), 4)
        for prev, cur in zip(readings, readings[1:]):
            self.assertLess(cur, prev, f"scroll did not move: {readings}")

    async def test_every_consecutive_pagedown_press_moves_the_viewport(self):
        # Scroll to the top first, then page back down.
        presses = [_PAGE_UP] * 6 + [_PAGE_DOWN] * 4
        readings = await _drive_pgup_pgdn(200, presses)
        down_readings = readings[6:]
        self.assertEqual(len(down_readings), 4)
        for prev, cur in zip(down_readings, down_readings[1:]):
            self.assertGreater(cur, prev, f"scroll did not move: {down_readings}")

    async def test_pageup_no_op_regression_guard(self):
        """Directly guards the reported symptom: vscroll after the FIRST
        PageUp must differ from vscroll after a run with zero PageUps."""
        with_press    = await _drive_pgup_pgdn(200, [_PAGE_UP])
        without_press = await _drive_pgup_pgdn(200, [])
        # without_press has no readings (nothing was pressed) -- instead
        # capture the resting vscroll by reading render_info directly
        # after only the initial render, mirroring _drive_pgup_pgdn's setup.
        state = tc.ClientState()
        app, output_buffer, _ = tc._build_app(state)
        text = "\n".join(f"line {i}" for i in range(200))
        output_buffer.set_document(Document(text, len(text)), bypass_readonly=True)
        with create_pipe_input() as pipe_input:
            app.output = DummyOutput()
            app.input = pipe_input
            run_task = asyncio.ensure_future(app.run_async())
            await asyncio.sleep(0.2)
            out_win = next(
                w for w in app.layout.find_all_windows()
                if getattr(w.content, 'buffer', None) is output_buffer
            )
            resting_vscroll = out_win.render_info.vertical_scroll
            app.exit()
            try:
                await run_task
            except Exception:
                pass

        self.assertNotEqual(with_press[0], resting_vscroll)


if __name__ == '__main__':
    unittest.main()
