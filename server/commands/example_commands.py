"""commands/example_commands.py

Example commands: test, table.
Auto-discovered by CommandProcessor.discover().
"""

import logging
from typing import List

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext

log = logging.getLogger(__name__)


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
            ("test #colors",            "List every color rendered in its own color."),
            ("test #table",             "Test table zebra striping and border styles."),
        ],
        notes = ["'#colors' has no effect in plain-text mode."],
    )

    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        positional, switches = self.parse_args(*args)

        await ctx.send(
            "Test command executed.",
            f"  Args:     {positional or 'none'}",
            f"  Switches: {switches or 'none'}",
            ""
        )
        if "#colors" in switches:
            # Folded in from the former standalone 'colors' command (Ryan):
            # its name/aliases ('colors'/'color'/'colour'/'colours')
            # clashed with the 'help colors' concept topic added alongside
            # the |token| mini-language docs -- _TOPICS is checked before
            # commands in HelpCommand.execute(), so 'help colors' silently
            # shadowed this command's own help entirely. Folding the
            # behavior under 'test #colors' frees those names for the help
            # topic instead of fighting over them.
            from formatting import COLOR_NAME_TO_TOKEN

            lines = ['Available colors:', '']
            for color_name, token in COLOR_NAME_TO_TOKEN.items():
                lines.append(f'  |{token}|{color_name.value}|reset|')

            if len(lines) == 2:
                lines.append('  (no colors available — plain text mode)')

            await ctx.send(lines)

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

        if "#table" in switches:
            from table import Table, Column, Align
            from formatting import codec_for_settings, PETSCIICodec

            headers = [
                Column("Name", min_width=8),
                Column("Class", align=Align.LEFT),
                Column("HP", align=Align.RIGHT),
            ]
            rows = [
                ["Aldric", "Fighter", "45"],
                ["Rhiannon", "Mage", "72"],
                ["Bram", "Rogue", "38"],
                ["Selene", "Cleric", "60"],
            ]
            width = ctx.player.client_settings.screen_columns

            await ctx.send("", "Zebra striping (green/yellow rows, 'single' border):")
            zebra = Table(headers, border_style="single",
                          text_color=["green", "yellow"])
            for row in rows:
                zebra.add_row(row)
            await ctx.send(*zebra.render(width=width))

            border_names = ["ascii", "single", "double"]
            # PETSCII line-drawing bytes only round-trip on a client whose
            # codec is actually PETSCII (cbmcodecs2-mapped) -- on any other
            # client they'd render as garbage, so only demo it there.
            is_petscii = isinstance(codec_for_settings(ctx.player.client_settings),
                                     PETSCIICodec)
            if is_petscii:
                border_names.append("petscii")

            for name in border_names:
                await ctx.send("", f"Border style: {name}")
                t = Table(headers, border_style=name)
                for row in rows:
                    t.add_row(row)
                await ctx.send(*t.render(width=width))

            if not is_petscii:
                await ctx.send("", "(Skipping 'petscii' border style — client isn't PETSCII-capable.)")

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
