"""shoppe/main.py — Merchant Shoppe entry point."""
import logging

from network_context import GameContext

log = logging.getLogger(__name__)

_AP = "'"


# ---------------------------------------------------------------------------
# Sub-section stubs
# ---------------------------------------------------------------------------

async def _bank(ctx: GameContext) -> None:
    await ctx.send(
        'You approach the Bank of SPUR.',
        '',
        '(Banking not yet available.)',
    )


async def _wizard(ctx: GameContext) -> None:
    await ctx.send(
        'The wizened wizard studies you carefully.',
        '',
        '(Wizard not yet available.)',
    )


async def _locker(ctx: GameContext) -> None:
    await ctx.send(
        'You open your locker and find it empty.',
        '',
        '(Locker not yet available.)',
    )


async def _elevator(ctx: GameContext) -> None:
    from shoppe.elevator import execute as elevator_execute
    context = {'player': ctx.player, 'client': ctx.client}
    await elevator_execute(None, ctx.reader, ctx.writer, context=context, args=[])


# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------

_MENU = (
    ('B', 'Bank of SPUR',      _bank),
    ('E', 'Elevator',          _elevator),
    ('L', 'Locker',            _locker),
    ('W', 'Visit the Wizard',  _wizard),
)


async def _show_menu(ctx: GameContext) -> None:
    lines = ['', 'Merchant Shoppe:', '']
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

    await ctx.send(
        'You follow the sloping passageway downward into the merchant{_AP}s annex.'.format(_AP=_AP),
        '',
        'Torchlight flickers across rows of stalls lining the walls.  The smell '
        'of old parchment and coin mingles in the cool underground air.',
    )

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
            await ctx.send('You climb back up the passageway into the daylight.')
            break

        matched = next((fn for key, _, fn in _MENU if key.lower() == cmd), None)
        if matched:
            await matched(ctx)
        else:
            await ctx.send(f'"{raw.strip()}"? (B/E/L/W to choose, X to leave)')


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
    ctx.send = AsyncMock()

    answers = iter(['b', 'l', 'w', 'x'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, None))

    asyncio.run(main(ctx))
    print('Standalone shoppe test complete.')
