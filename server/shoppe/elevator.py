"""shoppe/elevator.py — Elevator to the seven levels of the Land."""
import logging
from typing import Optional

from flags import PlayerFlags
from formatting import hrule_char, underline
from network_context import GameContext
from player import Player
from base_classes import CombinationTypes, Combination
from presence import enter_area, leave_area, broadcast_area, broadcast_open_room, others_present

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


def level_name(level: int) -> Optional[str]:
    """Return the display name for a dungeon level, or None if out of range."""
    if 1 <= level <= len(_LEVEL_NAMES):
        return _LEVEL_NAMES[level - 1]
    return None


# ---------------------------------------------------------------------------
# Combination check
# ---------------------------------------------------------------------------

def _wrong_combination_msg() -> str:
    return f'The guard frowns. "That{_AP}s not the right combination."'


def _find_combination(player, kind: CombinationTypes):
    """Return the Combination of the given type from the player's list, or None."""
    combos = getattr(player, 'combinations', None)
    if not combos:
        return None
    if isinstance(combos, dict):
        return combos.get(kind)
    # list of Combination objects (standard initialisation via set_up_combinations)
    return next((c for c in combos if c.name == kind), None)


async def get_combination(ctx: GameContext, *,
                          is_interactive: bool = False,
                          provided_ans: Optional[str] = None) -> bool:
    """Ask the player for the elevator combination.

    Returns True if correct, False otherwise.
    """
    player = ctx.player

    # No auto-generation here: the ELEVATOR combination only exists once the player
    # has READ the scrap of paper (item #69, commands/read.py). Without that, the
    # guard simply refuses -- matching SPUR.MISC2.S, where the elevator's combination
    # check has no fallback.
    scrap = _find_combination(player, CombinationTypes.ELEVATOR)
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
# Elevator description
# ---------------------------------------------------------------------------

_ELEVATOR_DESCRIPTION = (
    'You are inside a cramped iron cage, barely large enough for a few people '
    'and their gear. Thick cables vanish into the darkness above and below. '
    'A lever mounted on the wall rattles with each subtle sway of the car. '
    'Through the gaps in the ironwork you can glimpse rough stone walls '
    'sliding past — or standing still, depending on your perspective.'
)


# ---------------------------------------------------------------------------
# Elevator motion
# ---------------------------------------------------------------------------

def _out_of_range(obstacle: str) -> str:
    return (
        f'The guard looks alarmed. "Not on your life, we{_AP}d go straight through the {obstacle}!" '
        f'He pauses, scratching his chin. "That [would] be kind of fun, but I don{_AP}t '
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
    await broadcast_area(ctx, 'elevator',
                         f'{player.name} travels {direction} to {level_name}.')
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

    if player.query_flag(PlayerFlags.ROOM_DESCRIPTIONS):
        await ctx.send(_ELEVATOR_DESCRIPTION)
    await ctx.send(
        'A burly guard stands here, his arms crossed. He looks you up and down.',
    )
    await broadcast_open_room(ctx, f'{player.name} steps up to the elevator.')

    await enter_area(ctx, 'Elevator')
    try:
        await _elevator_session(ctx, player)
    finally:
        await leave_area(ctx, 'Elevator')


async def _elevator_session(ctx: GameContext, player) -> None:
    """Inner elevator loop, called after presence is established."""
    if ctx.player.is_debug:
        elevator_combo = _find_combination(ctx.player, CombinationTypes.ELEVATOR) or "None"
        await ctx.send(f"[Debug] Combination for {elevator_combo}")
    ok = await get_combination(ctx, is_interactive=True)
    if not ok:
        return

    # Only levels 1–5 are reachable by elevator
    available = _LEVEL_NAMES[:5]

    while True:
        current_level = getattr(player, 'map_level', 1) or 1
        lines = ['', *underline('Elevator', ctx), '',
                 f"* [U]p a level, [D]own a level, or choose a level (1-{len(available)}):"]
        for i, name in reversed(list(enumerate(available, 1))):
            marker = '->' if i == current_level else '  '
            lines.append(f'{marker} {i}. {name}')
        lines += ['', '  [L]eave elevator', '']
        await ctx.send(lines)

        raw = await ctx.prompt('Level (or L to leave)')
        if raw is None:
            break
        cmd = raw.strip().lower()

        if not cmd or cmd in ('x', 'l', 'leave'):
            await ctx.send('The guard steps aside as you leave.')
            break

        if cmd == 'u':
            if current_level >= len(available):
                await ctx.send(_out_of_range('ceiling'))
            else:
                await _travel_to(ctx, current_level + 1)
            continue

        if cmd == 'd':
            if current_level <= 1:
                await ctx.send(_out_of_range('floor'))
            else:
                await _travel_to(ctx, current_level - 1)
            continue

        if cmd in ('look', 'lo', 'loo'):
            others = others_present(ctx, 'elevator')
            msg = [_ELEVATOR_DESCRIPTION]
            if others:
                msg.append(f'Also here: {", ".join(others)}.')
            await ctx.send(msg)
            continue

        try:
            target = int(cmd)
            if 1 <= target <= len(available):
                await _travel_to(ctx, target)
            else:
                await ctx.send(f'Please choose a level between 1 and {len(available)}.')
        except ValueError:
            processor = getattr(ctx.client, 'command_processor', None)
            if processor:
                await processor.process_input(raw.strip(), ctx=ctx)
            else:
                await ctx.send(f'Please enter a level number (1–{len(available)}) or L to leave.')


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
