"""bar/blue_djinn.py — The Blue Djinn: hire thugs to attack other players."""
import logging
import random

from flags import PlayerFlags
from network_context import GameContext
from presence import broadcast_area

log = logging.getLogger(__name__)

_NPC = "The Blue Djinn"


async def _blue_djinn_menu(ctx: GameContext) -> None:
    await ctx.send("Options: [H]ire, [I]nsult, [L]eave")


async def main(ctx: GameContext, bar=None) -> None:
    """The Blue Djinn interaction loop."""
    player = ctx.player

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send(f"For a price, {_NPC} can attack other players.")
        await _blue_djinn_menu(ctx)

    await ctx.send(f"{_NPC} sits behind the table.")
    await broadcast_area(ctx, 'bar', f'{player.name} sits down with {_NPC}.')

    while True:
        await ctx.send("")
        raw = await ctx.prompt(f'{_NPC} hisses, "What do you want?"')
        if raw is None:
            break

        inp = raw.strip().lower()
        if not inp:
            if player.previous_command:
                inp = player.previous_command
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    await ctx.send(f"(Repeating '{inp}'.)")
            else:
                continue

        command = inp[0]
        player.previous_command = command

        if command == 'h':
            await ctx.send('"Who do you want me to mess up?"')
            # TODO: finish Blue Djinn hire logic
        elif command == 'i':
            insult_target = random.choice(["lineage", "dog's appearance", "parenting skills"])
            await ctx.send(
                f"You say something deeply insulting about {_NPC}'s {insult_target}. "
                f"{_NPC}'s eyes narrow..."
            )
            from bar.main import _bouncer
            if bar is not None:
                await _bouncer(ctx, bar)
            else:
                if player.hit_points > 5:
                    player.hit_points -= 5
                await ctx.send("Mundo throws you out into the street...")
            await broadcast_area(ctx, 'bar', f'Mundo throws {player.name} out of the bar.')
            break
        elif command == '?':
            await _blue_djinn_menu(ctx)
        elif command in ('l', 'q'):
            await ctx.send(f"{_NPC} looks relieved.")
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from {_NPC}.')
            break
        else:
            await ctx.send(f"{_NPC} looks amused.")


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
    ctx.player.hit_points = 20
    ctx.player.previous_command = None
    ctx.player.query_flag = lambda _: False
    ctx.send = AsyncMock()

    answers = iter(['i', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print("Standalone blue_djinn test complete.")
