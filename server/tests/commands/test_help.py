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
# 1. Fix sys.path FIRST so 'commands/' is findable from tests/commands/
#    __file__ is  .../server/tests/commands/test_help.py
#    ROOT  is  .../server/
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
# Color helpers -- |token| markup for headings/rules/commands/aliases
# ---------------------------------------------------------------------------

class TestColorHelpers(unittest.TestCase):

    def test_heading_is_yellow(self):
        self.assertEqual(help_mod._heading("Usage:"), "|yellow|Usage:|reset|")

    def test_rule_is_dark_gray(self):
        self.assertEqual(help_mod._rule("---"), "|dark_gray|---|reset|")

    def test_cmd_is_cyan(self):
        self.assertEqual(help_mod._cmd("quote"), "|cyan|quote|reset|")

    def test_alias_is_darker_than_command(self):
        """The user's one explicit ask: aliases render in a slightly
        darker color than the command name itself."""
        cmd_color   = help_mod._cmd("quote")
        alias_color = help_mod._alias("(q)")
        self.assertIn("|cyan|", cmd_color)
        self.assertIn("|dark_gray|", alias_color)
        self.assertNotEqual(cmd_color.split("|")[1], alias_color.split("|")[1])

    def test_all_color_tokens_render_on_ansi_and_petscii(self):
        """Every token used here must exist in both ANSI_COLOR_CODES and
        PETSCII_CONTROL_CODES -- otherwise it'd silently break (or worse,
        show a literal '|token|' string) on one terminal type."""
        from formatting import ANSI_COLOR_CODES, PETSCII_CONTROL_CODES
        for token in ("yellow", "dark_gray", "cyan"):
            self.assertIn(token, ANSI_COLOR_CODES)
            self.assertIn(token, PETSCII_CONTROL_CODES)

    def test_vis_ljust_ignores_token_markup(self):
        colored = help_mod._cmd("go")  # 2 visible chars, much longer raw string
        padded  = help_mod._vis_ljust(colored, 10)
        from formatting import _visible_len
        self.assertEqual(_visible_len(padded), 10)

    def test_vis_ljust_no_padding_needed(self):
        text = "already-long-enough"
        self.assertEqual(help_mod._vis_ljust(text, 5), text)


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

    def test_admin_notes_hidden_by_default(self):
        h = Help(notes=["Regular note."], admin_notes=["Admin-only note."])
        out = self._fmt(h)
        self.assertIn("Regular note.", out)
        self.assertNotIn("Admin-only note.", out)

    def test_admin_notes_shown_when_privileged(self):
        h = Help(notes=["Regular note."], admin_notes=["Admin-only note."])
        out = self._fmt(h, is_privileged=True)
        self.assertIn("Regular note.", out)
        self.assertIn("Admin-only note.", out)

    def test_admin_notes_alone_still_shows_notes_heading_when_privileged(self):
        h = Help(admin_notes=["Admin-only note."])
        out = self._fmt(h, is_privileged=True)
        self.assertIn("Notes:", out)
        self.assertIn("Admin-only note.", out)

    def test_admin_notes_alone_produces_no_notes_section_when_not_privileged(self):
        h = Help(admin_notes=["Admin-only note."])
        out = self._fmt(h, is_privileged=False)
        self.assertNotIn("Notes:", out)
        self.assertNotIn("Admin-only note.", out)

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
        # Lines may carry |token| color markup now (headings/rules/command
        # names) -- assert on visible width, not raw string length.
        from formatting import _visible_len
        h = Help(summary="x", usage=[("editplayer", "Edit your character interactively.")])
        lines = format_help(h, width=80)
        for line in (lines if isinstance(lines, list) else []):
            self.assertLessEqual(_visible_len(line), 80, f"Line too long: {line!r}")

    def test_width_40_no_line_exceeds(self):
        from formatting import _visible_len
        h = Help(summary="x", usage=[("editplayer", "Edit your character.")])
        lines = format_help(h, width=40)
        for line in (lines if isinstance(lines, list) else []):
            self.assertLessEqual(_visible_len(line), 40, f"Line too long: {line!r}")


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

    async def test_category_substring_matches_unambiguously(self):
        ctx, _ = _ctx_with_processor(_make_cmd("ban", category=HelpCategory.ADMINISTRATIVE))
        result = await HelpCommand().execute(ctx, "#cat", "admin")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("ban", output)

    async def test_category_substring_can_match_anywhere_in_name(self):
        ctx, _ = _ctx_with_processor(_make_cmd("go", category=HelpCategory.MOVEMENT))
        result = await HelpCommand().execute(ctx, "#cat", "move")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("go", output)

    async def test_category_substring_ambiguous_reports_all_matches(self):
        ctx, _ = _ctx_with_processor()
        # 'c' matches Combat, Communication, and Concept -- all start with 'c'.
        result = await HelpCommand().execute(ctx, "#cat", "c")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "ambiguous_category")
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("Combat", output)
        self.assertIn("Communication", output)
        self.assertIn("Concept", output)

    async def test_category_matches_across_reloaded_enum_identity(self):
        """Regression: 'reload commands.help' creates a brand-new
        HelpCategory class. Any command module that wasn't reloaded in
        the same breath still holds a reference to the *old*
        HelpCategory.ADMINISTRATIVE object -- enums compare by identity,
        so a naive `cat == matched` silently drops that command from its
        own category listing. Simulate that here with a separate Enum
        class sharing the same member name, standing in for the stale
        reference."""
        import enum

        class _StaleHelpCategory(enum.Enum):
            ADMINISTRATIVE = "Administrative"

        self.assertIsNot(_StaleHelpCategory.ADMINISTRATIVE, HelpCategory.ADMINISTRATIVE)

        stale_cmd = _make_cmd("ban", category=_StaleHelpCategory.ADMINISTRATIVE)
        ctx, _ = _ctx_with_processor(stale_cmd)
        result = await HelpCommand().execute(ctx, "administrative")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("ban", output)

    async def test_category_exact_match_still_wins_over_substring(self):
        """'general' is itself a full category name -- exact match must
        take priority even though it's also technically a substring of
        nothing else here; this guards the exact-match-first ordering."""
        ctx, _ = _ctx_with_processor(_make_cmd("look", category=HelpCategory.GENERAL))
        result = await HelpCommand().execute(ctx, "general")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("look", output)

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
# Standalone concept topics (e.g. "help about") -- not tied to any Command,
# so they work at the LOGIN prompt too (help itself is Mode.ANY).
# ---------------------------------------------------------------------------

class TestHelpTopics(unittest.IsolatedAsyncioTestCase):

    async def test_about_topic_shows_up(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "about")
        self.assertTrue(result.success)
        self.assertIn("MUD", result.message)
        self.assertIn("Land of Spur", result.message)

    async def test_topic_aliases_all_resolve(self):
        for alias in ("about", "tada", "mud", "whatisthis"):
            ctx, _ = _ctx_with_processor()
            result = await HelpCommand().execute(ctx, alias)
            self.assertTrue(result.success, f"'{alias}' should resolve to the about topic")

    async def test_topic_works_with_no_processor_state(self):
        # No real commands registered at all -- the LOGIN-mode scenario
        # this topic exists for still needs to work.
        ctx  = _make_ctx()
        proc = MagicMock()
        proc.find_command.return_value     = (None, False)
        proc.get_all_commands.return_value = {}
        proc.search_commands.return_value  = []
        ctx.client.command_processor = proc
        ctx.command_processor        = proc

        result = await HelpCommand().execute(ctx, "about")
        self.assertTrue(result.success)

    async def test_concept_category_lists_topics(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "concept")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("about", output)


    def test_multi_paragraph_description_preserves_blank_line(self):
        help_obj = Help(
            summary="Multi-paragraph test.",
            description="First paragraph here.\n\nSecond paragraph here.",
        )
        formatted = format_help(help_obj)
        self.assertIn("", formatted)  # blank line between paragraphs
        joined = "\n".join(formatted)
        self.assertIn("First paragraph here.", joined)
        self.assertIn("Second paragraph here.", joined)

    async def test_rooms_topic_explains_outdoor_rooms(self):
        for alias in ("rooms", "room"):
            ctx, _ = _ctx_with_processor()
            result = await HelpCommand().execute(ctx, alias)
            self.assertTrue(result.success)
            self.assertIn("outdoors", result.message)

    async def test_categories_list_includes_descriptions(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "categories")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        normalized = " ".join(output.split())
        # Every category's one-line description should be present (normalize
        # whitespace since long descriptions wrap across lines).
        self.assertIn("Attacking, fleeing", normalized)      # Combat
        self.assertIn("not tied to one command", normalized)  # Concept


class TestColorsTopic(unittest.IsolatedAsyncioTestCase):
    """'help colors' (aliases 'color'/'markup') documents the |token|
    mini-language (formatting.py's ANSI_COLOR_CODES/PETSCII_CONTROL_CODES/
    |tab| syntax and the new ':count' + '||escape||' additions). Its own
    usage/example text has to survive the *real* rendering pipeline
    (format_lines -> ansi_encode/plain_encode) intact, not just show up
    unprocessed in a mocked ctx.send() -- see the full-pipeline tests
    below, which is what caught the escape mechanism's original bugs."""

    async def test_topic_aliases_all_resolve(self):
        for alias in ("colors", "color", "markup"):
            ctx, _ = _ctx_with_processor()
            result = await HelpCommand().execute(ctx, alias)
            self.assertTrue(result.success, f"'{alias}' should resolve to the colors topic")

    async def test_mentions_tab_and_count_syntax(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "colors")
        self.assertIn("tab", result.message.lower())
        self.assertIn(":5", result.message)

    def test_full_pipeline_ansi_renders_no_stray_warnings(self):
        """Every |token|-shaped example in the topic must be either a
        deliberate live demo or properly ||escaped|| -- an unescaped,
        accidental |word| in the source text logs an 'unknown token'
        warning every time a player views this page."""
        import logging
        from formatting import format_lines, ansi_encode_lines
        from terminal import ClientSettings
        from commands.help import _TOPICS

        help_obj = _TOPICS["colors"]
        formatted = format_help(help_obj, command_name="colors", width=78, rule_char="-")
        lines = format_lines(formatted, ClientSettings())

        with self.assertNoLogs(logging.getLogger(), level="WARNING"):
            ansi_encode_lines(lines)

    def test_full_pipeline_plain_preserves_escaped_examples(self):
        """Escaped ||token|| examples must survive PLAIN clients the same
        way they survive ANSI ones -- regression for the bug where
        _expand_tab_tokens() collapsed the escape too early, leaving a
        bare |tab| for plain_encode() to strip as if it were live markup."""
        from formatting import format_lines, plain_encode_lines
        from terminal import ClientSettings
        from commands.help import _TOPICS

        help_obj = _TOPICS["colors"]
        formatted = format_help(help_obj, command_name="colors", width=78, rule_char="-")
        lines = format_lines(formatted, ClientSettings())
        plain = ' '.join(plain_encode_lines(lines))

        self.assertIn('|tab|', plain)
        self.assertIn('|tab:5|', plain)
        self.assertIn('|color|', plain)
        self.assertIn('|code|', plain)


class TestCommandLineTopicAdminGating(unittest.IsolatedAsyncioTestCase):
    """'help commandline' concept topic -- its admin_notes (mentioning
    #version/#ver) should only show for Admin/Dungeon Master viewers."""

    async def test_regular_player_does_not_see_version_note(self):
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: False
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertTrue(result.success)
        self.assertNotIn("#version", result.message)

    async def test_admin_sees_version_note(self):
        from flags import PlayerFlags
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: flag == PlayerFlags.ADMIN
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertIn("#version", result.message)

    async def test_dungeon_master_sees_version_note(self):
        from flags import PlayerFlags
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: flag == PlayerFlags.DUNGEON_MASTER
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertIn("#version", result.message)

    async def test_general_content_visible_to_everyone(self):
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: False
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertIn("switch", result.message.lower())

    async def test_alias_switches_also_resolves(self):
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: False
        result = await HelpCommand().execute(ctx, "switches")
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s %(name)s: %(message)s")
    unittest.main()
