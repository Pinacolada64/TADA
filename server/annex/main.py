"""annex/main.py — The Annex: bulletin board and social hub (SPUR.ANNEX.S port).

The Annex is a separate area from the Merchant Shoppe — it's an information
and social hub with guild standings, news, player lists, and duel records.
In the original, it had 17 menu options.
"""
import logging

from network_context import GameContext

log = logging.getLogger(__name__)

_AP = "'"


# ---------------------------------------------------------------------------
# Sub-section stubs
# ---------------------------------------------------------------------------

async def _school_info(ctx: GameContext) -> None:
    """Display school/introductory text."""
    await ctx.send('(School info not yet available.)')


async def _system_message(ctx: GameContext) -> None:
    """Display the current system message."""
    await ctx.send('(System message not yet available.)')


async def _tips(ctx: GameContext) -> None:
    """Display gameplay tips."""
    await ctx.send('(Tips not yet available.)')


async def _school_spells(ctx: GameContext) -> None:
    """Spell tutorial for new players."""
    await ctx.send('(School spells not yet available.)')


async def _news_new(ctx: GameContext) -> None:
    """Display recent news from the battle log."""
    await ctx.send('(Recent news not yet available.)')


async def _news_old(ctx: GameContext) -> None:
    """Display older news."""
    await ctx.send('(Older news not yet available.)')


async def _guild_standings(ctx: GameContext) -> None:
    """Show duel win/loss records per guild with Latin motto rankings.

    Guilds: Mark of the Claw (\\|/), Mark of the Sword (-}----), Iron Fist (==[])
    Points = (wins*3)/2 - losses
    Rankings: IMPARI MARTE / FVIMVS TROES / FILIVS TERRAE
    """
    await ctx.send('(Guild standings not yet available.)')


async def _personal_records(ctx: GameContext) -> None:
    """Show the player's personal duel record (wins, losses, Vinny gold ledger)."""
    await ctx.send('(Personal records not yet available.)')


async def _view_system_data(ctx: GameContext) -> None:
    """Admin-only: view and edit detailed game state (weapons, monsters, flags, etc.)."""
    player = ctx.player
    if not getattr(player, 'is_sysop', False):
        await ctx.send('You are not authorized to view system data.')
        return
    await ctx.send('(System data view not yet available.)')


async def _message_board_1(ctx: GameContext) -> None:
    """Read message board 1."""
    await ctx.send('(Message board not yet available.)')


async def _message_board_2(ctx: GameContext) -> None:
    """Read message board 2."""
    await ctx.send('(Message board not yet available.)')


async def _message_board_3(ctx: GameContext) -> None:
    """Read message board 3."""
    await ctx.send('(Message board not yet available.)')


async def _list_civilians(ctx: GameContext) -> None:
    """List all players with Civilian status."""
    await ctx.send('(Civilian list not yet available.)')


async def _list_claw(ctx: GameContext) -> None:
    """List members of the Mark of the Claw guild."""
    await ctx.send('(Mark of the Claw roster not yet available.)')


async def _list_sword(ctx: GameContext) -> None:
    """List members of the Mark of the Sword guild."""
    await ctx.send('(Mark of the Sword roster not yet available.)')


async def _list_fist(ctx: GameContext) -> None:
    """List members of the Iron Fist guild."""
    await ctx.send('(Iron Fist roster not yet available.)')


async def _list_outlaws(ctx: GameContext) -> None:
    """List players with Outlaw status."""
    await ctx.send('(Outlaw list not yet available.)')


# ---------------------------------------------------------------------------
# Menu (mirrors the 17-option SPUR.ANNEX.S main menu)
# ---------------------------------------------------------------------------

_MENU = (
    ('1',  'School Info',        _school_info),
    ('2',  'System Message',     _system_message),
    ('3',  'Tips',               _tips),
    ('4',  'School Spells',      _school_spells),
    ('5',  'News (Recent)',      _news_new),
    ('6',  'News (Old)',         _news_old),
    ('7',  'Guild Standings',    _guild_standings),
    ('8',  'Personal Records',   _personal_records),
    ('9',  'System Data',        _view_system_data),
    ('10', 'Message Board 1',    _message_board_1),
    ('11', 'Message Board 2',    _message_board_2),
    ('12', 'Message Board 3',    _message_board_3),
    ('13', 'Civilians',          _list_civilians),
    ('14', 'Mark of the Claw',   _list_claw),
    ('15', 'Mark of the Sword',  _list_sword),
    ('16', 'Iron Fist',          _list_fist),
    ('17', 'Outlaws',            _list_outlaws),
)


async def _show_menu(ctx: GameContext) -> None:
    lines = ['', 'The Annex:', '']
    for key, label, _ in _MENU:
        lines.append(f'  [{key:>2}] {label}')
    lines += ['  [ X] Leave the Annex', '']
    await ctx.send(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Run the Annex interaction loop."""
    player = ctx.player

    await ctx.send(
        'You enter the Annex — a vaulted stone chamber lined with notice boards '
        'and guild banners.  The hum of conversation fills the air.',
    )

    while True:
        if not player.is_expert:
            await _show_menu(ctx)

        raw = await ctx.prompt('Annex')
        if raw is None:
            break
        cmd = raw.strip().lower()

        if not cmd or cmd == 'x':
            await ctx.send('You step back out into the corridor.')
            break

        matched = next((fn for key, _, fn in _MENU if key == cmd), None)
        if matched:
            await matched(ctx)
        else:
            await ctx.send(f'"{raw.strip()}"? (Enter a number 1–17, or X to leave)')


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.name = 'Rulan'
    ctx.player.is_expert = True
    ctx.player.is_sysop = False
    ctx.send = AsyncMock()

    answers = iter(['7', '8', 'x'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, None))

    asyncio.run(main(ctx))
    print('Standalone annex test complete.')
