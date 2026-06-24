"""shoppe/elevator.py — Elevator to the seven levels of the Land."""
import logging
from typing import Optional

from network_context import GameContext
from player import Player, set_up_combinations
from base_classes import CombinationTypes, Combination

log = logging.getLogger(__name__)

_AP = "'"

_LEVEL_NAMES = [
    "The Land of the Enchanted",   # 1
    "Dark Side",                   # 2
    "The Shadowed Land",           # 3
    "Maze of Alleyways",           # 4
    "Land of the Wraiths",         # 5
    "A Brave New World",           # 6
    "The House",                   # 7
]


# ---------------------------------------------------------------------------
# Combination check
# ---------------------------------------------------------------------------

def _wrong_combination_msg() -> str:
    return f'The guard frowns. "That{_AP}s not the right combination."'


async def get_combination(ctx: GameContext, *,
                          is_interactive: bool = False,
                          provided_ans: Optional[str] = None) -> bool:
    """Ask the player for the elevator combination.

    Returns True if correct, False otherwise.
    """
    player = ctx.player
    if not hasattr(player, 'combinations'):
        player.combinations = set_up_combinations()

    scrap = player.combinations.get(CombinationTypes.ELEVATOR)
    if not scrap:
        await ctx.send(
            f'The burly guard crosses his arms. '
            f'"Sorry, I can{_AP}t let you use the elevator without a combination."'
        )
        return False

    if not is_interactive:
        try:
            entered = Combination.from_string(provided_ans)
        except Exception:
            entered = None
        if entered and entered.combination == scrap.combination:
            return True
        await ctx.send(_wrong_combination_msg())
        return False

    max_tries = 5
    for attempt in range(1, max_tries + 1):
        raw = await ctx.prompt(f'Combination [attempt {attempt}/{max_tries}]')
        if raw is None:
            break
        ans = raw.strip()
        if not ans:
            await ctx.send(f'The guard frowns. "You{_AP}re telling me you don{_AP}t have a combination?"')
            continue
        try:
            entered = Combination.from_string(ans)
            if entered.combination == scrap.combination:
                return True
        except Exception:
            pass
        await ctx.send(_wrong_combination_msg())

    await ctx.send('Out of attempts.')
    return False


# ---------------------------------------------------------------------------
# Elevator motion
# ---------------------------------------------------------------------------

def _out_of_range(obstacle: str) -> str:
    return (
        f'The guard looks alarmed. "Not on your life, we{_AP}d go straight through the {obstacle}!" '
        f'He pauses, scratching his chin. "That would be kind of fun, but I don{_AP}t '
        f'think my boss would be very happy with me."'
    )


async def _travel_to(ctx: GameContext, target: int) -> None:
    """Move the player to target level and narrate the journey."""
    player = ctx.player
    if target < 1 or target > len(_LEVEL_NAMES):
        obstacle = 'basement' if target < 1 else 'roof'
        await ctx.send(_out_of_range(obstacle))
        return

    current = getattr(player, 'map_level', 1) or 1
    direction = ('upwards' if target > current
                 else 'downwards' if target < current
                 else 'nowhere in particular')
    level_name = _LEVEL_NAMES[target - 1]

    await ctx.send(
        f'The guard closes the doors, throws a lever, and the elevator creaks '
        f'{direction} towards {level_name}. Once there, he opens the doors again.'
    )
    player.map_level = target
    try:
        ctx.client.map_level = target
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main entry point — called from shoppe/main.py _elevator()
# ---------------------------------------------------------------------------

async def main(ctx: GameContext) -> None:
    """Run the elevator interaction loop."""
    player = ctx.player

    # Elevator serves levels 1–5 only (matches SPUR.SHOP.S elevator section)
    current_level = getattr(player, 'map_level', 1) or 1
    if current_level > 5:
        await ctx.send(
            f'The guard shakes his head. "Elevator doesn{_AP}t run up here, friend."'
        )
        return

    await ctx.send(
        'A burly guard stands here, his arms crossed. He looks you up and down.',
    )

    ok = await get_combination(ctx, is_interactive=True)
    if not ok:
        return

    # Only levels 1–5 are reachable by elevator
    available = _LEVEL_NAMES[:5]

    while True:
        lines = ['', 'Elevator — choose a level:', '']
        for i, name in enumerate(available, 1):
            marker = ' <--' if i == current_level else ''
            lines.append(f'  {i}. {name}{marker}')
        lines += ['', '  [X] Cancel', '']
        await ctx.send(lines)

        raw = await ctx.prompt('Level')
        if raw is None:
            break
        cmd = raw.strip().lower()

        if not cmd or cmd == 'x':
            await ctx.send('The guard steps aside as you leave.')
            break

        try:
            target = int(cmd)
            if 1 <= target <= len(available):
                await _travel_to(ctx, target)
                break
            else:
                await ctx.send(f'Please choose a level between 1 and {len(available)}.')
        except ValueError:
            await ctx.send(f'Please enter a level number (1–{len(available)}) or X to cancel.')


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
    ctx.player.combinations = {}   # no combo → guard refuses
    ctx.client = MagicMock()
    ctx.send = AsyncMock()

    answers = iter([])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, None))

    asyncio.run(main(ctx))
    print('Standalone elevator test complete.')
