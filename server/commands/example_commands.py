"""commands/example_commands.py

Example commands: colors, test, table.
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
            ""
        )
        if "#feep" in switches:
            await ctx.send(['"Feeping creatures" is a Spoonerism of "creeping features."',
                            '',
                            'Feature creep is the excessive ongoing expansion or addition '
                            'of new features in a product, especially in computer software, '
                            'video games, and consumer or business electronics. ([Wikipedia])',
                            '',
                            'Feeps forever!'])

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
        from formatting import border_style_for_ctx

        border = border_style_for_ctx(ctx)

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

    print("All self-tests passed.")
