"""
test_help.py  –  runs without a server, net_common, or command_processor.

Run with:
    python test_help.py          # all tests
    python test_help.py -v       # verbose
"""

import asyncio
import sys
import unittest
from dataclasses import dataclass, field
from typing import List

# ── Minimal stubs so help.py can be imported standalone ──────────────────────

# Stub out CommandResult and BaseCommand so help.py's late imports resolve.
import types

_base_cmd_mod = types.ModuleType("commands.base_command")

@dataclass
class CommandResult:
    success: bool
    message: str = ""
    error: str   = ""
    data: dict   = field(default_factory=dict)

    def to_dict(self):
        return {"success": self.success, "message": self.message,
                "error": self.error, "data": self.data}

class BaseCommand:
    name    = ""
    aliases: List[str] = []
    help    = None          # will be a CommandHelp once attached

    async def execute(self, ctx, *args):
        raise NotImplementedError

    def help_text(self) -> str:
        ch = getattr(self, 'help', None)
        return ch.summary if ch else "No help."

    def help_detail(self, width: int = 80) -> str:
        from help import format_help
        ch = getattr(self, 'help', None)
        return format_help(ch, command_name=self.name, max_width=width) or self.help_text()

_base_cmd_mod.CommandResult = CommandResult
_base_cmd_mod.BaseCommand   = BaseCommand
sys.modules["commands"]              = types.ModuleType("commands")
sys.modules["commands.base_command"] = _base_cmd_mod

# Stub command_processor so the late-import inside _resolve_command_manager
# doesn't blow up (it only runs if context has no manager, which our tests avoid).
_cp_mod = types.ModuleType("commands.command_processor")
sys.modules["commands.command_processor"] = _cp_mod

# ── Now we can import our module under test ───────────────────────────────────
from server.commands.help import (
    CommandHelp,
    HelpCategory,
    HelpCommand,
    _find_command,
    _resolve_command_manager,
    format_help,
)

# ── Tiny fake command manager ─────────────────────────────────────────────────

class FakeCommand(BaseCommand):
    def __init__(self, name, aliases=None, category=HelpCategory.GENERAL,
                 summary="", description=""):
        self.name    = name
        self.aliases = aliases or []
        self.help    = CommandHelp(
            summary=summary or f"The {name} command.",
            description=description or f"Does {name}-y things.",
            category=category,
            usage=[(f"{name} <target>", f"Use {name} on something")],
            examples=[(f"{name} goblin", "Classic usage")],
            notes=[f"Remember: {name} is case-insensitive."],
        )


class FakeCommandManager:
    def __init__(self, commands: list):
        self._cmds = {c.name: c for c in commands}
        # also register aliases
        for c in commands:
            for a in c.aliases:
                self._cmds[a] = c

    def get_all_commands(self):
        # return unique instances only (names and aliases both point to the same obj)
        seen = {}
        for c in self._cmds.values():
            seen[id(c)] = c
        return {c.name: c for c in seen.values()}

    def get_command(self, name):
        return self._cmds.get(name)


def _make_manager():
    hc         = HelpCommand()
    hc.name    = "help"
    hc.aliases = ["h", "?"]
    return FakeCommandManager([
        hc,
        FakeCommand("say",    ["'"],         HelpCategory.COMMUNICATION,
                    "Say something to the room.",
                    "Speaks aloud so every player in the room can hear you."),
        FakeCommand("shout",  ["yell"],      HelpCategory.COMMUNICATION,
                    "Shout to the entire MUD."),
        FakeCommand("go",     ["move"],      HelpCategory.MOVEMENT,
                    "Move in a direction.",
                    "Move your character in a direction: north, south, east, west, up, or down."),
        FakeCommand("look",   ["l"],         HelpCategory.GENERAL,
                    "Describe the current room."),
        FakeCommand("attack", ["kill", "k"], HelpCategory.COMBAT,
                    "Attack a monster or player."),
        FakeCommand("login",  [],            HelpCategory.AUTHENTICATION,
                    "Log in to the game."),
    ])


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(coro):
    """Run a coroutine synchronously (works on Python 3.7+)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFormatHelp(unittest.TestCase):
    """format_help() is a pure function – no async needed."""

    def _sample(self):
        return CommandHelp(
            summary="A sample command.",
            description="Does sample-y things with great enthusiasm.",
            category=HelpCategory.GENERAL,
            usage=[
                ("sample <target>", "Apply sample to something"),
                ("sample all",      "Apply to everything in the room"),
            ],
            examples=[
                ("sample goblin", "Samples the goblin"),
            ],
            notes=["This is a note.", "Notes can be multiple."],
        )

    def test_returns_string(self):
        out = format_help(self._sample(), command_name="sample")
        self.assertIsInstance(out, str)

    def test_contains_summary(self):
        out = format_help(self._sample(), command_name="sample")
        self.assertIn("A sample command", out)

    def test_contains_usage_section(self):
        out = format_help(self._sample(), command_name="sample")
        self.assertIn("Usage:", out)
        self.assertIn("sample <target>", out)

    def test_contains_examples(self):
        out = format_help(self._sample(), command_name="sample")
        self.assertIn("Examples:", out)
        self.assertIn("sample goblin", out)

    def test_contains_notes(self):
        out = format_help(self._sample(), command_name="sample")
        self.assertIn("Notes:", out)
        self.assertIn("This is a note.", out)

    def test_plain_string_input(self):
        out = format_help("Just a plain string.")
        self.assertIn("Just a plain string", out)

    def test_none_returns_none(self):
        self.assertIsNone(format_help(None))

    def test_width_respected(self):
        long_desc = "word " * 30
        ch = CommandHelp(summary="X", description=long_desc)
        out = format_help(ch, width=40)
        for line in out.splitlines():
            self.assertLessEqual(len(line), 45,   # allow small slack for indented lines
                                 f"Line too long: {line!r}")


class TestResolveCmdManager(unittest.TestCase):

    def test_finds_in_dict_by_key(self):
        mgr = _make_manager()
        ctx = {"command_processor": mgr}
        self.assertIs(_resolve_command_manager(ctx), mgr)

    def test_finds_command_manager_key(self):
        mgr = _make_manager()
        ctx = {"command_manager": mgr}
        self.assertIs(_resolve_command_manager(ctx), mgr)

    def test_returns_none_for_empty_dict(self):
        # Should not raise, just return None (no global fallback registered)
        result = _resolve_command_manager({})
        self.assertIsNone(result)


class TestFindCommand(unittest.TestCase):

    def setUp(self):
        self.mgr = _make_manager()

    def test_find_by_name(self):
        cmd = _find_command("say", self.mgr)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "say")

    def test_find_by_alias(self):
        cmd = _find_command("yell", self.mgr)
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "shout")

    def test_unknown_returns_none(self):
        self.assertIsNone(_find_command("zzznope", self.mgr))


class TestHelpCommandGeneral(unittest.TestCase):

    def setUp(self):
        self.hc  = HelpCommand()
        self.mgr = _make_manager()
        self.ctx = {"command_processor": self.mgr}

    def test_general_help_succeeds(self):
        result = run(self.hc.execute(self.ctx))
        self.assertTrue(result["success"])

    def test_general_help_contains_categories(self):
        result = run(self.hc.execute(self.ctx))
        msg = result["message"]
        self.assertIn("COMMUNICATION", msg)
        self.assertIn("MOVEMENT", msg)

    def test_general_help_lists_commands(self):
        result = run(self.hc.execute(self.ctx))
        msg = result["message"]
        self.assertIn("say", msg)
        self.assertIn("go",  msg)

    def test_no_command_manager_returns_failure(self):
        result = run(self.hc.execute({}))
        self.assertFalse(result["success"])
        self.assertIn("command manager", result["message"].lower())


class TestHelpCommandSpecific(unittest.TestCase):

    def setUp(self):
        self.hc  = HelpCommand()
        self.mgr = _make_manager()
        self.ctx = {"command_processor": self.mgr}

    def test_help_for_known_command(self):
        result = run(self.hc.execute(self.ctx, "say"))
        self.assertTrue(result["success"])
        self.assertIn("say", result["message"].lower())

    def test_help_shows_usage(self):
        result = run(self.hc.execute(self.ctx, "go"))
        self.assertIn("Usage:", result["message"])

    def test_help_by_alias(self):
        result = run(self.hc.execute(self.ctx, "yell"))   # alias for shout
        self.assertTrue(result["success"])
        self.assertIn("shout", result["message"].lower())

    def test_unknown_command_fails(self):
        result = run(self.hc.execute(self.ctx, "zzznope"))
        self.assertFalse(result["success"])

    def test_help_help(self):
        # "help help" should return the HelpCommand's own metadata
        result = run(self.hc.execute(self.ctx, "help"))
        self.assertTrue(result["success"])
        self.assertIn("help", result["message"].lower())


class TestHelpCommandCategory(unittest.TestCase):

    def setUp(self):
        self.hc  = HelpCommand()
        self.mgr = _make_manager()
        self.ctx = {"command_processor": self.mgr}

    def test_list_categories(self):
        result = run(self.hc.execute(self.ctx, "#cat"))
        self.assertTrue(result["success"])
        self.assertIn("Communication", result["message"])

    def test_show_category_by_name(self):
        result = run(self.hc.execute(self.ctx, "communication"))
        self.assertTrue(result["success"])
        self.assertIn("say", result["message"])
        self.assertIn("shout", result["message"])

    def test_category_shorthand(self):
        result = run(self.hc.execute(self.ctx, "#cat", "movement"))
        self.assertTrue(result["success"])
        self.assertIn("go", result["message"])

    def test_unknown_category(self):
        result = run(self.hc.execute(self.ctx, "zzzcategory"))
        # Should fall through to command lookup and fail gracefully
        self.assertFalse(result["success"])


class TestHelpCommandSearch(unittest.TestCase):

    def setUp(self):
        self.hc  = HelpCommand()
        self.mgr = _make_manager()
        self.ctx = {"command_processor": self.mgr}

    def test_search_by_name_fragment(self):
        result = run(self.hc.execute(self.ctx, "search", "sh"))
        self.assertTrue(result["success"])
        self.assertIn("shout", result["message"])

    def test_search_by_description_word(self):
        result = run(self.hc.execute(self.ctx, "search", "direction"))
        self.assertTrue(result["success"])
        self.assertIn("go", result["message"])

    def test_search_no_match(self):
        result = run(self.hc.execute(self.ctx, "search", "xyzzy_impossible"))
        self.assertFalse(result["success"])


class TestHelpCommandMeta(unittest.TestCase):
    """HelpCommand's own help metadata should be accessible."""

    def test_help_text_returns_summary(self):
        hc = HelpCommand()
        self.assertIn("help", hc.help_text().lower())

    def test_help_detail_returns_formatted_string(self):
        hc = HelpCommand()
        out = hc.help_detail()
        self.assertIn("Usage:", out)
        self.assertIn("help <command>", out)


# ── Pretty-print a sample to stdout when run directly ────────────────────────

def _demo():
    print("\n" + "=" * 60)
    print("  format_help() demo output")
    print("=" * 60)
    ch = CommandHelp(
        summary="Say something to players in your room.",
        description=(
            "Speaks your message aloud so that every player currently "
            "in the same room can read it. Your name is prepended automatically."
        ),
        category=HelpCategory.COMMUNICATION,
        usage=[
            ("say <message>", "Speak to everyone in the room"),
            ("' <message>",   "Shorthand for say"),
        ],
        examples=[
            ("say Hello there!", "Room sees: Aldric says, \"Hello there!\""),
            ("' Greetings",      "Same as: say Greetings"),
        ],
        notes=[
            "You must be in app mode (logged in) to use this command.",
            "Empty messages are silently ignored.",
        ],
    )
    print(format_help(ch, command_name="say"))

    print("\n" + "=" * 60)
    print("  HelpCommand general listing demo")
    print("=" * 60)
    hc  = HelpCommand()
    mgr = _make_manager()
    ctx = {"command_processor": mgr}
    result = asyncio.get_event_loop().run_until_complete(hc.execute(ctx))
    print(result["message"])

    print("\n" + "=" * 60)
    print("  help say  (specific command)")
    print("=" * 60)
    result = asyncio.get_event_loop().run_until_complete(hc.execute(ctx, "say"))
    print(result["message"])


if __name__ == "__main__":
    _demo()
    print("\n" + "=" * 60)
    print("  Running unit tests")
    print("=" * 60 + "\n")
    unittest.main(argv=[sys.argv[0], "-v"])
