# File: `bar/main.py`
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from network_context import GameContext
from player import Player
from flags import PlayerFlags
from items import Rations
from presence import enter_area, leave_area, broadcast_area

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bar state
# ---------------------------------------------------------------------------

@dataclass
class Bar:
    pos_x: int = 6
    pos_y: int = 0
    can_go_here: bool = False
    valid_move: bool = True
    go_routine: Optional[Callable] = field(default=None, repr=False)

    # 'M' = Mundo the bouncer, 'o' = NPC, 'X' = player (injected at render time)
    bar_map = {
        'ascii': [
            "+----| |----+",
            "|o()     ()o|",
            "|          M|",
            "|  +--+  ()o|",
            "|  |oo|  ()o|",
            "+-----------+",
        ],
        'ansi': [
            "┌────┤ ├────┐",
            "│o()     ()o│",
            "│          M│",
            "│  ┌──┐  ()o│",
            "│  │oo│  ()o│",
            "└──┴──┴─────┘",
        ],
        # cbmcodecs2 maps Unicode box chars to PETSCII graphics bytes, but
        # '[' and ']' are not in petscii_c64en_lc — use '(' and ')' instead.
        'petscii': [
            "┌────┤ ├────┐",
            "│o()     ()o│",
            "│          M│",
            "│  ┌──┐  ()o│",
            "│  │oo│  ()o│",
            "└──┴──┴─────┘",
        ],
    }

    # (row, col, display_name, async_routine | None)
    # None routine = Exit (no interaction)
    locations = [
        (0, 6,  "Exit",                   None),
        (1, 4,  "The Blue Djinn",         '_blue_djinn'),
        (1, 8,  "Vinny the Loan Shark",   '_vinny'),
        (2, 4,  "Skip's Eats",            '_skip'),
        (2, 5,  "Bar None",               '_bar_none'),
        (3, 8,  "Fat Olaf's Slave Trade", '_fat_olaf'),
        (4, 8,  "Madame Zelda's",         '_zelda'),
    ]


# ---------------------------------------------------------------------------
# NPC stubs  (each becomes a full async sub-module later)
# ---------------------------------------------------------------------------

async def _bouncer(ctx: GameContext, bar: Bar) -> None:
    """Mundo ejects the player."""
    player = ctx.player
    action = ''
    if player.hit_points > 5:
        action = "knocks you over the head with a baseball bat, and "
        player.hit_points -= 5
    await ctx.send(f"At a signal, Mundo {action}throws you out into the street...")
    bar.pos_y, bar.pos_x = 0, 6
    bar.valid_move = True


async def _blue_djinn(ctx: GameContext, bar: Bar) -> None:
    from bar.blue_djinn import main as blue_djinn_main
    await blue_djinn_main(ctx, bar)


async def _vinny(ctx: GameContext, bar: Bar) -> None:
    from bar.vinny import main as vinny_main
    await vinny_main(ctx, bar)


async def _skip(ctx: GameContext, bar: Bar) -> None:
    from bar.skip import main as skip_main
    await skip_main(ctx, bar)


async def _bar_none(ctx: GameContext, bar: Bar) -> None:
    from bar.bar_none import main as bar_none_main
    await bar_none_main(ctx, bar)


async def _fat_olaf(ctx: GameContext, bar: Bar) -> None:
    from bar.fat_olaf import main as fat_olaf_main
    await fat_olaf_main(ctx, bar)


async def _zelda(ctx: GameContext, bar: Bar) -> None:
    from bar.zelda import main as zelda_main
    await zelda_main(ctx, bar)


# Map from location name strings to async routines
_ROUTINES = {
    '_blue_djinn': _blue_djinn,
    '_vinny':      _vinny,
    '_skip':       _skip,
    '_bar_none':   _bar_none,
    '_fat_olaf':   _fat_olaf,
    '_zelda':      _zelda,
}


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

async def _bar_help(ctx: GameContext) -> None:
    await ctx.send([
        "This is the Wall Bar & Grill, a place where you (and your party, if you "
        "have others with you) can find food, drink, and various services to help "
        "yourself--or harm others, if you wish--in the Land.",
        "",
        "In the map of the bar:",
        "",
        "* 'o' represents each person you can interact with, by moving in front "
        "(or to the side) of them, then typing [G]o here.",
        "* '()' represents a table sitting in front of the person.",
        "* 'M' represents Mundo, the bar bouncer.",
        "* Lastly, 'X' represents you (plus your party, if applicable).",
    ])


async def _show_menu(ctx: GameContext, bar: Bar) -> None:
    go_here = ", [G]o here" if bar.can_go_here else ''
    await ctx.send(f"[N]orth, [E]ast, [S]outh, [W]est{go_here}, [H]elp, [Q]uit")


def _render_map(bar: Bar, bar_map: list[str], debug: bool) -> list[str]:
    """Return the bar map with the player marker ('X') inserted."""
    lines = []
    if debug:
        width  = len(bar_map[0])
        prefix = '   '   # matches the f'{row:2} ' row prefix
        tens = ''.join(str(i // 10) if i % 10 == 0 and i > 0 else ' ' for i in range(width))
        ones = ''.join(str(i % 10) for i in range(width))
        lines += [prefix + tens, prefix + ones]
    for row, line in enumerate(bar_map):
        prefix = f'{row:2} ' if debug else ''
        if row == bar.pos_y:
            rendered = f'{line[:bar.pos_x]}X{line[bar.pos_x + 1:]}'
        else:
            rendered = line
        lines.append(f'{prefix}{rendered}')
    return lines


def _pick_map(ctx) -> list[str]:
    """Choose ASCII/ANSI bar map based on the client's translation setting."""
    try:
        from terminal import Translation
        t = ctx.player.client_settings.translation
        # PETSCII uses the same Unicode box chars as ANSI — cbmcodecs2 maps
        # them to the correct PETSCII graphics bytes.  Plain ASCII '|' is not
        # in the PETSCII charset and renders as '?' on a C64.
        if t == Translation.ANSI:
            return Bar.bar_map['ansi']
        if t == Translation.PETSCII:
            return Bar.bar_map['petscii']
    except Exception:
        pass
    return Bar.bar_map['ascii']


# ---------------------------------------------------------------------------
# Food menu (kept sync — only called from __main__ standalone test)
# ---------------------------------------------------------------------------

def food_menu(p: 'Player', foodstuffs: list[dict]) -> list[Rations]:
    all_items = [Rations(1, d['name'], d['kind'], d['price']) for d in foodstuffs]
    all_items.append(Rations(1, "COFFEE", "drink", 5))
    all_items.append(Rations(1, "HASH",   "food",  1))
    drinks = sorted([i for i in all_items if i.kind == 'drink'], key=lambda i: i.name)
    foods  = sorted([i for i in all_items if i.kind == 'food'],  key=lambda i: i.name)
    return drinks + foods


# ---------------------------------------------------------------------------
# Main async entry point — called from commands/movement.py _enter_bar()
# ---------------------------------------------------------------------------

_DIRECTION_NAMES = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west'}


async def enter_bar(ctx: GameContext) -> None:
    """Run the Wall Bar & Grill interaction loop for the given ctx."""
    player  = ctx.player
    bar     = Bar()
    bar_map = _pick_map(ctx)
    obstacles = {ch for line in bar_map for ch in line if ch not in (' ', 'X')}

    await ctx.send([
        'You stand in the doorway of a smoky bar.  A faded sign hanging on '
        'the wall above you reads: "WALL BAR AND GRILL."',
        "",
    ])
    await ctx.send_room(
        f'{player.name} wanders into the Wall Bar & Grill.',
        exclude_self=True,
    )

    if not player.is_expert:
        await _bar_help(ctx)

    await enter_area(ctx, 'Bar')
    try:
        while True:
            debug = player.is_debug
            await ctx.send([''] + _render_map(bar, bar_map, debug))

            # Check for an interactive location at the player's position
            bar.can_go_here = False
            bar.go_routine  = None
            for row, col, name, routine_key in Bar.locations:
                if bar.pos_y == row and bar.pos_x == col:
                    await ctx.send(name)
                    if routine_key:
                        bar.can_go_here = True
                        bar.go_routine  = _ROUTINES.get(routine_key)
                    if debug:
                        await ctx.send(f"  (routine: {routine_key})")

            if debug:
                await ctx.send(f'(x: {bar.pos_x}, y: {bar.pos_y})')

            # Proximity bump checks
            # TODO: add other players here
            bump, opponent, bump_text = False, '', ''
            if bar.pos_y == 2 and bar.pos_x == 1:
                bump, opponent, bump_text = True, "The Blue Djinn", 'eyes you, hissing. "Are'
            elif bar.pos_y == 2 and bar.pos_x == 10:
                bump, opponent, bump_text = True, "Mundo the bouncer", 'looks up from the floor. "Hey,'
            if bump:
                raw = await ctx.prompt('Y/N', preamble_lines=[
                    f'{opponent} {bump_text} you looking for a fight?"',
                ])
                if raw and raw.strip().lower() in ('y', 'yes'):
                    if opponent.startswith("Mundo"):
                        await _bouncer(ctx, bar)
                        continue
                    else:
                        await ctx.send(f"{opponent} draws back, ready to fight... (combat not yet available)")
                else:
                    await ctx.send(f'"Well then, [watch] it!" {opponent} glares at you.')

            # Menu and prompt
            if not player.is_expert:
                await _show_menu(ctx, bar)
                if player.previous_command:
                    await ctx.send(f"[{player.client_settings.return_key}] = '{player.previous_command}'")

            raw = await ctx.prompt('bar', preamble_lines=[f'[HP: {player.hit_points}]'])
            if raw is None:
                break
            inp = raw.strip().lower()

            # Repeat last command on empty input
            if not inp:
                if player.previous_command:
                    inp = player.previous_command
                    if not player.is_expert:
                        await ctx.send(f"(Repeating '{inp}'.)")
                else:
                    continue

            command = inp[0]
            player.previous_command = command

            move_into_obstacle = False
            moved_direction    = None

            if command in ('?', 'h'):
                await _bar_help(ctx)
            elif command == 'g' and bar.can_go_here and callable(bar.go_routine):
                await bar.go_routine(ctx, bar)
            elif command == 'd':
                player.toggle_flag(PlayerFlags.DEBUG_MODE, True)
            elif command == 'x':
                player.toggle_flag(PlayerFlags.EXPERT_MODE, True)
            elif command == 'q':
                await ctx.send("You head back out to the street.")
                await ctx.send_room(
                    f'{player.name} heads back out into the street.',
                    exclude_self=True,
                )
                break
            elif command == 'n':
                if bar.pos_y > 0 and bar_map[bar.pos_y - 1][bar.pos_x] not in obstacles:
                    bar.pos_y -= 1
                    moved_direction = 'north'
                else:
                    move_into_obstacle = True
            elif command == 's':
                if bar.pos_y < len(bar_map) - 1 and bar_map[bar.pos_y + 1][bar.pos_x] not in obstacles:
                    bar.pos_y += 1
                    moved_direction = 'south'
                else:
                    move_into_obstacle = True
            elif command == 'e':
                if bar.pos_x < len(bar_map[0]) - 1 and bar_map[bar.pos_y][bar.pos_x + 1] not in obstacles:
                    bar.pos_x += 1
                    moved_direction = 'east'
                else:
                    move_into_obstacle = True
            elif command == 'w':
                if bar.pos_x > 0 and bar_map[bar.pos_y][bar.pos_x - 1] not in obstacles:
                    bar.pos_x -= 1
                    moved_direction = 'west'
                else:
                    move_into_obstacle = True
            else:
                await ctx.send('Hm? (N/S/E/W to move, H for help, Q to leave)')

            if moved_direction:
                await broadcast_area(ctx, 'bar',
                                     f'{player.name} moves {moved_direction}.')

            if move_into_obstacle:
                await ctx.send("Laughter fills the bar as you attempt to move through solid objects.")
                player.hit_points -= 1
                if player.hit_points <= 0:
                    await broadcast_area(ctx, 'bar',
                                         f'{player.name} has died walking into solid objects.')
                    await ctx.send("You have died.")
                    break
    finally:
        await leave_area(ctx, 'Bar')


# ---------------------------------------------------------------------------
# Standalone smoke-test  (python -m bar.main)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    ctx               = MagicMock()
    ctx.player        = MagicMock()
    ctx.player.name   = 'Rulan'
    ctx.player.hit_points = 20
    ctx.player.previous_command = None
    ctx.player.client_settings  = MagicMock(
        screen_columns=80, translation=None, return_key='Return'
    )
    ctx.player.query_flag = lambda _flag: False
    ctx.player.toggle_flag = lambda _flag, _v: None
    ctx.send  = AsyncMock()

    answers = iter(['n', 'e', 'g', 'q'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'q'))

    asyncio.run(enter_bar(ctx))
    print("Standalone bar test complete.")
