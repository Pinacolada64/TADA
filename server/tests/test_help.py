#!/usr/bin/env python3
"""tests/test_help.py

Unit tests for commands/help.py.

Run with:
    python -m pytest tests/test_help.py -v
    python -m unittest tests.test_help
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# 1. Fix sys.path FIRST so 'commands/' is findable from tests/
#    __file__ is  .../server/tests/test_help.py
#    ROOT  is  .../server/
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# 2. Stub out heavy server modules before any TADA import touches them
# ---------------------------------------------------------------------------
for _name in ["network_context", "net_common"]:
    sys.modules.setdefault(_name, types.ModuleType(_name))

# ---------------------------------------------------------------------------
# 3. Now import from commands/ — path is correct, stubs are in place
# ---------------------------------------------------------------------------
from commands.help import Help, HelpCategory, HelpCommand, format_help
from commands.base_command import CommandResult
import commands.help as help_mod


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _make_ctx(screen_columns: int = 78):
    ctx = MagicMock()
    ctx.send  = AsyncMock()
    ctx.player.client_settings.screen_columns = screen_columns
    return ctx


def _make_processor(*commands):
    """Return a minimal processor-like stub pre-loaded with commands."""
    proc     = MagicMock()
    cmd_dict = {getattr(c, "name", str(i)): c for i, c in enumerate(commands)}
    proc.get_all_commands.return_value = cmd_dict
    proc.find_command.side_effect      = lambda name: (
        cmd_dict.get(name), name in cmd_dict
    )
    proc.search_commands.side_effect   = lambda term: [
        c for c in cmd_dict.values()
        if term.lower() in getattr(c, "name", "").lower()
        or term.lower() in getattr(getattr(c, "help", None), "summary", "").lower()
    ]
    return proc


def _make_cmd(name: str, aliases=None,
              category=HelpCategory.GENERAL, summary: str = ""):
    """Return a minimal command stub with a Help instance attached."""
    cmd         = MagicMock()
    cmd.name    = name
    cmd.aliases = aliases or []
    cmd.help    = Help(
        summary  = summary or f"Summary for {name}.",
        category = category,
        usage    = [(f"{name} <arg>", "Does something.")],
    )
    return cmd


def _ctx_with_processor(*commands):
    ctx  = _make_ctx()
    proc = _make_processor(*commands)
    ctx.client.command_processor = proc
    ctx.command_processor        = proc
    return ctx, proc


# ---------------------------------------------------------------------------
# format_help() — pure formatter, no I/O
# ---------------------------------------------------------------------------

class TestFormatHelp(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(format_help(None))

    def test_plain_string_is_word_wrapped(self):
        out = format_help("short string")
        self.assertIsInstance(out, str)
        self.assertIn("short string", out)

    def _fmt(self, *args, **kwargs):
        """Return format_help output as a single joined string for assertions."""
        result = format_help(*args, **kwargs)
        return "\n".join(result) if isinstance(result, list) else (result or "")

    def test_summary_appears_in_output(self):
        h = Help(summary="Does the thing.")
        self.assertIn("Does the thing.", self._fmt(h))

    def test_command_name_appears_as_header(self):
        h = Help(summary="Thing.")
        self.assertIn("mytool", self._fmt(h, command_name="mytool"))

    def test_usage_section_present(self):
        h = Help(usage=[("cmd <arg>", "Does something.")])
        self.assertIn("Usage:", self._fmt(h))

    def test_single_example_label(self):
        out = self._fmt(Help(examples=[("cmd foo", "one example")]))
        self.assertIn("Example:", out)
        self.assertNotIn("Examples:", out)

    def test_multiple_examples_label(self):
        self.assertIn("Examples:", self._fmt(Help(examples=[("cmd foo", "first"), ("cmd bar", "second")])))

    def test_notes_section_present(self):
        out = self._fmt(Help(notes=["A useful note."]))
        self.assertIn("Notes:", out)
        self.assertIn("A useful note.", out)

    def test_all_sections_together(self):
        h = Help(
            summary     = "Short summary.",
            description = "Longer description.",
            usage       = [("cmd <arg>", "Does something.")],
            examples    = [("cmd foo", "An example.")],
            notes       = ["A note."],
        )
        out = self._fmt(h, command_name="cmd")
        for expected in ("Usage:", "Example:", "Notes:", "cmd <arg>", "A note."):
            self.assertIn(expected, out)

    def test_width_80_no_line_exceeds(self):
        h = Help(summary="x", usage=[("editplayer", "Edit your character interactively.")])
        lines = format_help(h, width=80)
        for line in (lines if isinstance(lines, list) else []):
            self.assertLessEqual(len(line), 80, f"Line too long: {line!r}")

    def test_width_40_no_line_exceeds(self):
        h = Help(summary="x", usage=[("editplayer", "Edit your character.")])
        lines = format_help(h, width=40)
        for line in (lines if isinstance(lines, list) else []):
            self.assertLessEqual(len(line), 40, f"Line too long: {line!r}")


# ---------------------------------------------------------------------------
# HelpCategory
# ---------------------------------------------------------------------------

class TestHelpCategory(unittest.TestCase):

    def test_expected_categories_present(self):
        names = {c.name for c in HelpCategory}
        for expected in ("GENERAL", "COMMUNICATION", "MOVEMENT",
                         "AUTHENTICATION", "COMBAT", "ADMINISTRATIVE"):
            self.assertIn(expected, names)

    def test_values_are_strings(self):
        for cat in HelpCategory:
            self.assertIsInstance(cat.value, str)


# ---------------------------------------------------------------------------
# HelpCommand.execute() dispatch
# ---------------------------------------------------------------------------

class TestHelpCommandExecute(unittest.IsolatedAsyncioTestCase):

    # --- no args → general help ---

    async def test_no_args_shows_general_help(self):
        ctx, _ = _ctx_with_processor(
            _make_cmd("say",  category=HelpCategory.COMMUNICATION),
            _make_cmd("look", category=HelpCategory.MOVEMENT),
        )
        result = await HelpCommand().execute(ctx)
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("Available Commands by Category", output)

    # --- specific command ---

    async def test_specific_command_shows_help(self):
        ctx, _ = _ctx_with_processor(_make_cmd("say", summary="Say something."))
        result = await HelpCommand().execute(ctx, "say")
        self.assertTrue(result.success)
        self.assertIn("say", result.message)

    async def test_nonexistent_command_fails(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "no_such_command")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "no_help")
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("No help found", output)

    async def test_alias_resolves_to_command(self):
        cmd  = _make_cmd("test", aliases=["t"])
        ctx  = _make_ctx()
        proc = MagicMock()
        proc.find_command.return_value     = (cmd, True)
        proc.get_all_commands.return_value = {"test": cmd}
        proc.search_commands.return_value  = []
        ctx.client.command_processor = proc
        ctx.command_processor        = proc
        result = await HelpCommand().execute(ctx, "t")
        self.assertTrue(result.success)

    # --- categories ---

    async def test_categories_token_lists_all(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "categories")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("General",  output)
        self.assertIn("Movement", output)

    async def test_category_name_shows_its_commands(self):
        ctx, _ = _ctx_with_processor(_make_cmd("go", category=HelpCategory.MOVEMENT))
        result = await HelpCommand().execute(ctx, "movement")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("go", output)

    async def test_unknown_category_fails(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "#cat", "nonexistentcat")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "unknown_category")

    # --- search ---

    async def test_search_finds_matching_command(self):
        ctx, _ = _ctx_with_processor(_make_cmd("test", summary="A test command."))
        result = await HelpCommand().execute(ctx, "search", "tes")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("test", output)

    async def test_search_no_results(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "search", "xyzzy")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("No commands found", output)

    # --- edge cases ---

    async def test_graceful_without_processor(self):
        ctx = _make_ctx()
        ctx.client = MagicMock(spec=[])   # no command_processor attribute
        ctx.command_processor = None
        result = await HelpCommand().execute(ctx)
        self.assertTrue(result.success)

    async def test_falls_back_to_docstring_when_no_help_obj(self):
        cmd             = MagicMock()
        cmd.name        = "nodoc"
        cmd.aliases     = []
        cmd.help        = None
        cmd.execute.__doc__ = "Docstring help text."

        ctx  = _make_ctx()
        proc = MagicMock()
        proc.find_command.return_value     = (cmd, False)
        proc.get_all_commands.return_value = {"nodoc": cmd}
        proc.search_commands.return_value  = []
        ctx.client.command_processor = proc
        ctx.command_processor        = proc

        result = await HelpCommand().execute(ctx, "nodoc")
        self.assertTrue(result.success)
        self.assertIn("Docstring", result.message)

    # --- HelpCategory accessible via the module reference ---

    def test_help_mod_has_helpcategory(self):
        self.assertTrue(hasattr(help_mod, "HelpCategory"))
        self.assertIn(help_mod.HelpCategory.MOVEMENT,
                      list(help_mod.HelpCategory))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s %(name)s: %(message)s")
    unittest.main()
