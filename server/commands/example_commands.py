"""commands/example_commands.py

Example commands: colors, look, say, test.
Auto-discovered by CommandProcessor.discover().
"""

import logging
from typing import List

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# colors
# ---------------------------------------------------------------------------

class ColorsCommand(Command):
    """Display all available color names rendered in their own color."""

    name    = "colors"
    aliases = ["colour", "colours", "color"]
    modes   = {Mode.LOGIN, Mode.GAME}

    help = Help(
        summary  = "Show all available color names.",
        category = HelpCategory.MISCELLANEOUS,
        usage    = [("colors", "List every color rendered in its own color.")],
        notes    = ["Has no effect in plain-text mode."],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        from formatting import ANSI_COLOR_CODES, COLOR_NAME_TO_TOKEN

        reset = ANSI_COLOR_CODES.get('reset', '')
        lines = ['Available colors:', '']
        for color_name, token in COLOR_NAME_TO_TOKEN.items():
            code = ANSI_COLOR_CODES.get(token, '')
            lines.append(f'  {code}{color_name.value}{reset}')

        if len(lines) == 2:
            lines.append('  (no colors available — plain text mode)')

        await ctx.send(lines)
        return CommandResult.ok()


# ---------------------------------------------------------------------------
# look
# ---------------------------------------------------------------------------

class LookCommand(Command):
    """Describe the current room, or inspect an object or player."""

    name    = "look"
    aliases = ["l"]
    modes   = {Mode.GAME}

    help = Help(
        summary     = "Examine the current room or an object.",
        description = (
            "Without arguments, describes your current location. "
            "With a target, inspects that object or player."
        ),
        category = HelpCategory.MOVEMENT,
        usage    = [
            ("look",           "Describe the current room."),
            ("look <target>",  "Inspect an object or player."),
        ],
        examples = [
            ("look",        "See where you are."),
            ("look sword",  "Examine the sword."),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        if not positional:
            # TODO: pull room description from ctx.client.room
            await ctx.send("You look around.  (room description not yet wired up)")
            return CommandResult.ok()

        target = " ".join(positional)
        # TODO: search room inventory and players for target
        await ctx.send(f"You look at {target}.  (object inspection not yet wired up)")
        return CommandResult.ok()


# ---------------------------------------------------------------------------
# say
# ---------------------------------------------------------------------------

class SayCommand(Command):
    """Say something to everyone in your room."""

    name    = "say"
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Say something to everyone in your room.",
        category = HelpCategory.COMMUNICATION,
        usage    = [("say <message>", "Speak aloud to everyone here.")],
        examples = [("say Hello!", "Greet everyone in the room.")],
    )

    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        positional, _ = self.parse_args(*args)
        text = " ".join(positional).strip()

        if not text:
            await ctx.send("Say what?")
            return CommandResult.fail("No message.", error="missing_args")

        await ctx.send(f'You say: "{text}"')
        await ctx.send_room(
            f'{ctx.player.name} says, "{text}"',
            exclude_self=True,
        )
        return CommandResult.ok()


# ---------------------------------------------------------------------------
# quit
# ---------------------------------------------------------------------------

class QuitCommand(Command):
    """Disconnect from the server."""

    name    = "quit"
    aliases = ["q", "bye", "exit"]
    modes   = {Mode.ANY}

    help = Help(
        summary  = "Disconnect from the server.",
        category = HelpCategory.GENERAL,
        usage    = [("quit", "Close your connection.")],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        await ctx.send("Goodbye!")
        return CommandResult(
            success=True,
            message="Disconnected.",
            data={"quit": True},
        )


# ---------------------------------------------------------------------------
# test  (developer utility — remove before release)
# ---------------------------------------------------------------------------

class TestCommand(Command):
    """Smoke-test the command pipeline."""

    name    = "test"
    aliases: List[str] = []
    modes   = {Mode.ANY}

    help = Help(
        summary  = "Developer smoke-test for the command pipeline.",
        category = HelpCategory.MISCELLANEOUS,
        usage    = [
            ("test [args] [#switches]", "Echo args and switches back."),
            ("test 42",                 "Trigger the Easter egg."),
            ("test #feep",              "Feep forever."),
        ],
    )

    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        positional, switches = self.parse_args(*args)

        await ctx.send(
            "Test command executed.",
            f"  Args:     {positional or 'none'}",
            f"  Switches: {switches or 'none'}",
        )
        if "#feep" in switches:
            await ctx.send("  Feeps forever!")
        if "42" in positional:
            await ctx.send("  The answer to Life, the Universe, and Everything.")

        return CommandResult.ok("Test command executed.")


# ---------------------------------------------------------------------------
# Quick self-test (python -m commands.example_commands)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    ctx = MagicMock()
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.player    = MagicMock(name="Tester")

    cmd    = TestCommand()
    result = asyncio.run(cmd.execute(ctx, "hello", "42", "#feep"))
    assert result.success
    assert result.message == "Test command executed."
    print("✅ TestCommand passed")

    cmd    = SayCommand()
    result = asyncio.run(cmd.execute(ctx, "hello", "world"))
    assert result.success
    print("✅ SayCommand passed")

    cmd    = SayCommand()
    result = asyncio.run(cmd.execute(ctx))
    assert not result.success
    print("✅ SayCommand (no args) passed")

    print("All self-tests passed.")
