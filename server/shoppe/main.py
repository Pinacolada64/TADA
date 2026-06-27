"""shoppe/main.py — Merchant Shoppe entry point (SPUR.SHOP.S port)."""
import logging

from network_context import GameContext
from presence import enter_area, leave_area, others_present

log = logging.getLogger(__name__)

_AP = "'"

# Shoppe is closed on level 7 (matches SPUR.SHOP.S main1 level-gate)
_CLOSED_LEVELS = {7}


# ---------------------------------------------------------------------------
# Sub-section stubs
# ---------------------------------------------------------------------------

async def _armory(ctx: GameContext) -> None:
    """Buy and sell weapons. Max 6 weapons per player."""
    await ctx.send(
        'The weaponsmith looks up from his grindstone.',
        '',
        '(Armory not yet available.)',
    )


async def _protection(ctx: GameContext) -> None:
    """Buy armor and shields. Max 5 items per player."""
    await ctx.send(
        'Racks of armor line the walls.',
        '',
        '(Protection shop not yet available.)',
    )


async def _general_store(ctx: GameContext) -> None:
    """Buy general goods. Max 10 unique items per player."""
    await ctx.send(
        'Shelves of supplies stretch from floor to ceiling.',
        '',
        '(General store not yet available.)',
    )


async def _bank(ctx: GameContext) -> None:
    """Deposit, withdraw, or transfer gold between players (level 2+ for transfers)."""
    await ctx.send(
        'You approach the Bank of SPUR.  A teller looks up with a practiced smile.',
        '',
        '(Banking not yet available.)',
    )


async def _wizard(ctx: GameContext) -> None:
    """Learn spells. Wizards pay half price, Druids two-thirds. Max 10 spells."""
    await ctx.send(
        'The wizened wizard studies you carefully.',
        '',
        '(Wizard not yet available.)',
    )


async def _clan(ctx: GameContext) -> None:
    """Change guild affiliation (Claw, Sword, Fist, Civilian, Outlaw). Costs gold and honor."""
    await ctx.send(
        'A stern-faced registrar eyes you from behind a heavy desk.',
        '',
        '(Clan/Guild office not yet available.)',
    )


async def _elevator(ctx: GameContext) -> None:
    """Ride the elevator to levels 1–5."""
    from shoppe.elevator import main as elevator_main
    await elevator_main(ctx)


async def _pawn_shop(ctx: GameContext) -> None:
    """Sell (not buy) items to the pawn merchant."""
    await ctx.send(
        'A wiry merchant peers at you over a pile of odds and ends.',
        '',
        '(Pawn shop not yet available.)',
    )


async def _player_list(ctx: GameContext) -> None:
    """Browse online and offline players, filtered by name."""
    await ctx.send(
        '(Player list not yet available.)',
    )


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

_MENU = (
    ('A', 'Armory',          _armory),
    ('P', 'Protection',      _protection),
    ('G', 'General Store',   _general_store),
    ('B', 'Bank of SPUR',    _bank),
    ('W', 'Wizard',          _wizard),
    ('C', 'Clan / Guild',    _clan),
    ('E', 'Elevator',        _elevator),
    ('V', 'Pawn Shop',       _pawn_shop),
    ('L', 'Player List',     _player_list),
)


async def _show_menu(ctx: GameContext) -> None:
    lines = ['', 'Merchant Shoppe:', '']
    other_names = others_present(ctx, 'shoppe')
    if other_names:
        lines.append(f'  Also here: {", ".join(other_names)}')
        lines.append('')
    for key, label, _ in _MENU:
        lines.append(f'  [{key}] {label}')
    lines += ['  [X] Leave the Shoppe', '']
    await ctx.send(lines)


# ---------------------------------------------------------------------------
# Main entry point — called from commands/movement.py _enter_shoppe()
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Run the Merchant Shoppe interaction loop."""
    player = ctx.player

    level = getattr(player, 'map_level', 1) or 1
    if level in _CLOSED_LEVELS:
        await ctx.send(
            'Shoppe closed due to lack of interest on this level. '
            'Look for our stores in levels 1-5!!!'
        )
        return

    await ctx.send(
        f'You follow the sloping passageway downward into the merchant{_AP}s annex.',
        '',
        'Torchlight flickers across rows of stalls lining the walls.  The smell '
        'of old parchment and coin mingles in the cool underground air.',
    )

    await enter_area(ctx, 'shoppe')
    try:
        await _shoppe_session(ctx, player)
    finally:
        await leave_area(ctx, 'shoppe')


async def _shoppe_session(ctx: GameContext, player) -> None:
    """Inner shoppe loop, called after presence is established."""
    while True:
        if not player.is_expert:
            await _show_menu(ctx)

        raw = await ctx.prompt('Shoppe')
        if raw is None:
            break
        cmd = raw.strip().lower()[:1]

        if not cmd:
            continue

        if cmd == 'x':
            await ctx.send(f'You climb back up the passageway into the daylight.')
            break

        matched = next((fn for key, _, fn in _MENU if key.lower() == cmd), None)
        if matched:
            await matched(ctx)
        else:
            keys = '/'.join(k for k, _, _ in _MENU)
            await ctx.send(f'"{raw.strip()}"? ({keys}/X to choose)')


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
    ctx.player.map_level = 1
    ctx.player.is_expert = True
    ctx.send = AsyncMock()

    answers = iter(['a', 'p', 'g', 'b', 'w', 'c', 'v', 'l', 'x'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, None))

    asyncio.run(main(ctx))
    print('Standalone shoppe test complete.')
