"""commands/help_menu.py — native C64 "General Help / Keyboard Shortcuts /
Credits" popup, three pages the player flips between locally (CRSR LEFT/
RIGHT) inside one popup window on the Commodore's own screen, rather than
scrolling text like 'help' does.

Reached via three separate commands -- GUIDE, KEYS (alias SHORTCUTS), and
CREDITS -- each opening the same popup, just starting on a different page.
Mirrors commands/c64_display.py's trigger round trip (send a framed
trigger so tada-client.asm's receive dispatcher knows to load the
help_menu.asm overlay module, same as DISPLAY_STREAM_CONFIRM triggers
load_config_menu), but one-way: unlike Video Settings, there's nothing to
save here, so the client never sends a reply back and this module doesn't
wait for one.

Wire format (must match tada-client.asm/help_menu.asm exactly):

    stream := STREAM_START HELP_STREAM_CONFIRM len_lo len_hi page

STREAM_START (0x01) is shared with every other framed stream on this
connection (petscii_editor/canvas.py, sid_engine/frames.py, c64_display.py)
-- HELP_STREAM_CONFIRM (0x08) is what tells the client's handle_recv_byte
scanner which kind of stream is starting, same role as
DISPLAY_STREAM_CONFIRM (0x06)/APPLY_STREAM_CONFIRM (0x07). Like those, it
must come from the 0x02-0x0f gap rather than a printable letter -- see
sid_engine/frames.py's docstring for why.

page is one byte: PAGE_HELP (0), PAGE_KEYS (1), or PAGE_CREDITS (2) --
must match help_menu.asm's own cur_page values exactly.

Non-Commodore connections (ANSI/plain-text) never get the native popup at
all -- PAGE_TEXT below is the same three pages' content rendered as
ordinary scrolling text instead, so GUIDE/KEYS/CREDITS still work for
every terminal type, just without the on-screen box.
"""
from __future__ import annotations

import logging
from typing import List

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext, PETSCIINetworkContext

log = logging.getLogger(__name__)

STREAM_START         = 0x01
HELP_STREAM_CONFIRM  = 0x08  # unused C64 control code -- opens the native
                               # popup; see this module's docstring for why

PAGE_HELP    = 0
PAGE_KEYS    = 1
PAGE_CREDITS = 2

# Plain-text fallback for non-Commodore connections -- same content as
# help_menu.asm's own row_help_*/row_keys_*/row_credits_* data, just
# rendered as ordinary lines instead of a poked-screen box (a plain-text
# client has no SCREEN_RAM to poke into in the first place).
PAGE_TEXT = {
    PAGE_HELP: [
        "|yellow|General Help|reset|",
        "",
        "TADA is a text adventure -- explore, fight monsters, and level "
        "up your character.",
        "",
        "Common commands: LOOK, N/S/E/W to move, GET, DROP, INV, TALK, "
        "ATTACK.",
        "",
        "Type 'help' for the full command/topic reference, or 'keys' for "
        "a list of line-editing keyboard shortcuts.",
    ],
    PAGE_KEYS: [
        "|yellow|Keyboard Shortcuts|reset|",
        "",
        "Editing the input line (real Commodore keyboard only -- these "
        "are local line-editing keys, not game commands):",
        "",
        "  CRSR keys        Move cursor",
        "  SHIFT+DEL        Insert a space",
        "  DEL              Delete left",
        "  CRSR UP          Jump to start of line",
        "  CRSR DOWN        Jump to end of line",
        "  CTRL+CRSR LEFT   Word left",
        "  CTRL+CRSR DOWN   Word right",
        "  RETURN           Send command",
    ],
    PAGE_CREDITS: [
        "|yellow|Credits|reset|",
        "",
        "TADA -- A Commodore 64/128 MUD",
        "",
        "Created by Ryan Sherwood, with Claude.",
        "Inspired by SPUR.",
        "",
        "Thanks for playing!",
    ],
}


def _encode_trigger(page: int) -> bytes:
    return bytes([STREAM_START, HELP_STREAM_CONFIRM, 1, 0, page])


async def show_help_popup(ctx: GameContext, page: int) -> None:
    """Open the native popup on a real Commodore connection (starting on
    *page*); print the equivalent plain text everywhere else. Fire-and-
    forget on the popup side -- see this module's docstring for why no
    reply is awaited, unlike commands/c64_display.py's Video Settings."""
    if isinstance(ctx, PETSCIINetworkContext):
        await ctx.send_raw(_encode_trigger(page))
        return
    await ctx.send(PAGE_TEXT[page])


class GuideCommand(Command):
    """GUIDE -- open the native General Help page (or its plain-text
    equivalent)."""

    name    = "guide"
    aliases: List[str] = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = "A quick orientation popup -- what TADA is and the basic commands.",
        category = HelpCategory.GENERAL,
        usage    = [("guide", "Open the General Help page.")],
        see_also = ["keys", "credits", "about"],
        petscii_notes = [
            "Opens a native on-screen popup window; flip between this, "
            "'keys', and 'credits' with CRSR LEFT/RIGHT once it's open.",
        ],
    )

    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        await show_help_popup(ctx, PAGE_HELP)
        return CommandResult.ok()


class KeysCommand(Command):
    """KEYS / SHORTCUTS -- open the native Keyboard Shortcuts page (or its
    plain-text equivalent)."""

    name    = "keys"
    aliases: List[str] = ["shortcuts"]
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Keyboard shortcuts for editing the input line.",
        category = HelpCategory.GENERAL,
        usage    = [("keys", "Open the Keyboard Shortcuts page.")],
        see_also = ["guide", "credits"],
        petscii_notes = [
            "Opens a native on-screen popup window; flip between this, "
            "'guide', and 'credits' with CRSR LEFT/RIGHT once it's open.",
        ],
    )

    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        await show_help_popup(ctx, PAGE_KEYS)
        return CommandResult.ok()


class CreditsCommand(Command):
    """CREDITS -- open the native Credits page (or its plain-text
    equivalent)."""

    name    = "credits"
    aliases: List[str] = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = "Who made this thing.",
        category = HelpCategory.GENERAL,
        usage    = [("credits", "Open the Credits page.")],
        see_also = ["guide", "keys"],
        petscii_notes = [
            "Opens a native on-screen popup window; flip between this, "
            "'guide', and 'keys' with CRSR LEFT/RIGHT once it's open.",
        ],
    )

    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        await show_help_popup(ctx, PAGE_CREDITS)
        return CommandResult.ok()
