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
    modes   = {Mode.ANY}

    help = Help(
        summary  = "Show all available color names.",
        category = HelpCategory.MISCELLANEOUS,
        usage    = [("colors", "List every color rendered in its own color.")],
        notes    = ["Has no effect in plain-text mode."],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        from formatting import COLOR_NAME_TO_TOKEN

        lines = ['Available colors:', '']
        for color_name, token in COLOR_NAME_TO_TOKEN.items():
            lines.append(f'  |{token}|{color_name.value}|reset|')

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
        return CommandResult.ok(
            message="Disconnected.",
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
            ("test #feep",              "Feeps forever."),
            ("test #box",               "Test box-drawing functions."),
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
            await ctx.send(['  "Feeping creatures" is a Spoonerism of "creeping features.",'
                            '  Feature creep is the excessive ongoing expansion or addition '
                            'of new features in a product, especially in computer software, '
                            'video games and consumer and business electronics. ([Wikipedia])',
                            '  Feeps forever!'])

        if "#box" in switches:
            from formatting import make_box_for_settings
            settings = ctx.player.client_settings
            box = make_box_for_settings(settings,
                                        lines=["You find a sword!", "Take it?"],
                                        frame_color="blue",
                                        title_color="white",
                                        text_color="yellow",
                                        title="Item")
            await ctx.send(*box)
            another_box = make_box_for_settings(
                settings,
                lines=['Choose your destiny.'],
                title='Welcome',
                frame_color='cyan',
                title_color='yellow',
                text_color='white',
            )
            await ctx.send(*another_box)

        if "42" in positional:
            await ctx.send("  The answer to Life, the Universe, and Everything.")

        return CommandResult.ok("Test command executed.")

class TableCommand(Command):
    name = "table"
    aliases = ['']
    modes = {Mode.ANY}

    help = Help(summary="Display a table of all available commands.",
                description="The 'table' command shows a list of commands.",
                examples=[("table", "Show the table.")],
                category=HelpCategory.MISCELLANEOUS
                )
    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        from table import Table, Column, Align
        from formatting import codec_for_settings, PETSCIICodec

        cs = ctx.player.client_settings
        border = 'petscii' if isinstance(codec_for_settings(cs), PETSCIICodec) else getattr(cs, 'border_style', 'single')

        t = Table(
            [
                Column("Command", min_width=8),
                Column("Description", align=Align.LEFT),
            ],
            title="Available Commands",
            border_style=border,
        )
        processor = getattr(getattr(ctx, "client", None), "command_processor", None)
        for name, cmd in (processor.get_all_commands().items() if processor else []):
            summary = getattr(getattr(cmd, "help", None), "summary", "")
            t.add_row([name, summary])

        await ctx.send(*t.render(width=ctx.player.client_settings.screen_columns))
        return CommandResult.ok("Seems fine to me, maybe.")

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
    result = asyncio.run(cmd.execute(ctx, ["hello", "42", "#feep"]))
    assert result.success
    assert result.message == "Test command executed."
    print("✅ TestCommand passed")

    cmd    = SayCommand()
    result = asyncio.run(cmd.execute(ctx, ["hello", "world"]))
    assert result.success
    print("✅ SayCommand passed")

    cmd    = SayCommand()
    result = asyncio.run(cmd.execute(ctx))
    assert not result.success
    print("✅ SayCommand (no args) passed")

    print("All self-tests passed.")
