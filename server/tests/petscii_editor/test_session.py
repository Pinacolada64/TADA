"""tests/petscii_editor/test_session.py

Coverage for petscii_editor/session.py's stream_canvas_edit(), the
streaming round trip pulled out of commands/banner_edit.py's original
_edit() so commands/board/edit.py's SIG/board intro-screen editor could
reuse it against a different on-disk path.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from petscii_editor import canvas as canvas_wire
from petscii_editor import store as canvas_store
from petscii_editor.canvas import Canvas
from petscii_editor.session import stream_canvas_edit
from network_context import PETSCIINetworkContext


def _fake_ctx(reader):
    # A real (uninitialized) instance rather than MagicMock(spec=...) --
    # PETSCIINetworkContext's 'player' field is a dataclass annotation
    # with no class-level attribute, so spec's dir()-based allowlist
    # doesn't recognize it as settable.
    ctx = PETSCIINetworkContext.__new__(PETSCIINetworkContext)
    ctx.player = MagicMock()
    ctx.player.name = 'Admin'
    ctx.reader = reader
    ctx.send = AsyncMock()
    ctx.send_raw = AsyncMock()
    return ctx


def _upload_bytes(canvas: Canvas) -> bytes:
    return canvas_wire.encode_download(canvas)


class TestStreamCanvasEditSuccess(unittest.IsolatedAsyncioTestCase):

    async def test_uploaded_canvas_is_saved(self):
        cv = Canvas()
        cv.chars[0] = 65
        reader = AsyncMock()
        reader.readexactly.side_effect = [
            _upload_bytes(cv)[:4],
            _upload_bytes(cv)[4:],
        ]
        ctx = _fake_ctx(reader)
        path = canvas_store.CANVASES_DIR / '__test_session_save.canvas'

        result = await stream_canvas_edit(
            ctx, path,
            opening_msg='opening', timeout_msg='timeout',
            cancelled_msg='cancelled', saved_msg='saved',
            log_label='test subject',
        )

        self.assertTrue(result.success)
        saved = canvas_store.load(path)
        self.assertIsInstance(saved, Canvas)
        self.assertEqual(saved.chars[0], 65)
        ctx.send.assert_any_call('saved')
        path.unlink(missing_ok=True)

    async def test_non_petscii_ctx_is_rejected(self):
        ctx = MagicMock()  # not spec'd as PETSCIINetworkContext
        ctx.send = AsyncMock()
        result = await stream_canvas_edit(
            ctx, canvas_store.CANVASES_DIR / '__unused.canvas',
            opening_msg='opening', timeout_msg='timeout',
            cancelled_msg='cancelled', saved_msg='saved',
            log_label='test subject',
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'no_petscii_display')


class TestStreamCanvasEditCancelTimeout(unittest.IsolatedAsyncioTestCase):

    async def test_client_cancel_reports_cancelled_and_does_not_save(self):
        reader = AsyncMock()
        cancel_header = bytes([canvas_wire.STREAM_START, canvas_wire.STREAM_CANCEL, 0, 0])
        reader.readexactly.side_effect = [cancel_header]
        ctx = _fake_ctx(reader)
        path = canvas_store.CANVASES_DIR / '__test_session_cancel.canvas'
        path.unlink(missing_ok=True)

        result = await stream_canvas_edit(
            ctx, path,
            opening_msg='opening', timeout_msg='timeout',
            cancelled_msg='cancelled', saved_msg='saved',
            log_label='test subject',
        )

        self.assertTrue(result.success)
        ctx.send.assert_any_call('cancelled')
        self.assertFalse(path.exists())

    async def test_timeout_reports_timeout_message(self):
        reader = AsyncMock()
        reader.readexactly.side_effect = asyncio.TimeoutError()
        ctx = _fake_ctx(reader)

        result = await stream_canvas_edit(
            ctx, canvas_store.CANVASES_DIR / '__unused2.canvas',
            opening_msg='opening', timeout_msg='timeout',
            cancelled_msg='cancelled', saved_msg='saved',
            log_label='test subject',
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, 'upload_timeout')
        ctx.send.assert_any_call('timeout')


if __name__ == '__main__':
    unittest.main()
