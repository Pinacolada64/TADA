"""ship/transporter.py — the ship's transporter room (SPUR.SHIP.S `elevator`/`elev.1`/`malfunction`).

Beams the player down from the ship (level 6) directly into another
level's Merchant Shoppe (SPUR: `dy$=dz$+"spur.shop":link dy$` on success --
a real one-way trip, not a round-trip visit). Gated by the same access
code as the dungeon elevator (SPUR reads the same per-player "elevator"
file/`xu$` value for both -- see shoppe/elevator.py's own combination
check, reused here rather than duplicated).

Malfunction risk: base ~9% (SPUR: `xz=random(100):if xz<10 goto
malfunction`), which gets *worse*, not better, after the first successful
trip this session (SPUR: `xz=xz-20` once the `TR+` token is set -- TODO.md
previously described this as "20 points better malfunction odds," which
the arithmetic contradicts; ported literally here regardless of that
stale paraphrase). On malfunction, the player is teleported to a random
level/room instead -- same `_teleport_to()` pattype as commands/use.py's
`_communicator_malfunction()`, whose own docstring is why this module
also skips SPUR's "[] MALFUNCTION []" typewriter/erase animation (a
C64-terminal-timing effect with no gameplay meaning to preserve).
"""
import logging
import random

from network_context import GameContext

log = logging.getLogger(__name__)

_ONCE_TOKEN = 'ship_transporter_used'  # SPUR's ys$ "TR+" token
_MIN_LEVEL, _MAX_LEVEL = 1, 5          # SPUR: "LEVEL: [1] [2] [3] [4] [5]"
_MALFUNCTION_LEVELS = 6                # SPUR malfunction: cl=random(6)+1


async def main(ctx: GameContext) -> bool:
    """Run the transporter room. Returns True if the player left the ship
    (successful beam-down or malfunction relocation), False if they backed
    out (should stay in the ship's menu loop)."""
    from shoppe.elevator import _find_combination
    from base_classes import CombinationTypes, Combination

    player = ctx.player
    scrap = _find_combination(player, CombinationTypes.ELEVATOR)
    if not scrap:
        await ctx.send('The transporter panel is dark -- you have no access code.')
        return False

    while True:
        raw = await ctx.prompt('TRANSPORTER ROOM: Coordinates ->')
        if raw is None or not raw.strip() or raw.strip().upper() == 'Q':
            return False
        try:
            entered = Combination.from_string(raw.strip())
        except Exception:
            entered = None
        if entered and entered.combination == scrap.combination:
            break
        await ctx.send('Wrong!')

    raw = await ctx.prompt('LEVEL: [1] [2] [3] [4] [5]->')
    if raw is None:
        return False
    try:
        target = int(raw.strip())
    except ValueError:
        target = -1
    if not (_MIN_LEVEL <= target <= _MAX_LEVEL):
        await ctx.send("It don't go there!")
        return False

    await ctx.send('Standby to beam down!')

    once = getattr(player, 'once_per_day', None)
    if once is None:
        once = []
        player.once_per_day = once
    roll = random.randint(1, 100)
    if _ONCE_TOKEN in once:
        roll -= 20
    if roll < 10:
        await _malfunction(ctx, player)
        return True

    if _ONCE_TOKEN not in once:
        once.append(_ONCE_TOKEN)
        player.unsaved_changes = True

    await ctx.send('...........')
    ctx.player.map_level = target
    try:
        ctx.client.map_level = target
    except Exception:
        pass
    ctx.client.room = 1
    ctx.player.map_room = 1
    player.unsaved_changes = True

    from shoppe.elevator import level_name
    name = level_name(target)
    if name:
        await ctx.send(f'You have entered {name}!')

    from shoppe.main import main as shoppe_main
    await shoppe_main(ctx)
    await ctx.server._show_room(ctx)
    return True


async def _malfunction(ctx: GameContext, player) -> None:
    """SPUR.SHIP.S `malfunction`: alarm flavor, battle-log entry, then
    teleport to a random level/room instead of the intended destination."""
    import net_common

    await ctx.send([
        'A strange buzzing comes from the transporter!!',
        'A red light starts flashing urgently!',
        '*** MALFUNCTION ***',
    ])
    net_common.append_battle_log(
        f'THE TRANSPORTER MALFUNCTIONED! {player.name} WAS SENT.. SOMEWHERE..'
    )

    game_map = getattr(ctx.server, 'game_map', None)
    target_level = random.randint(1, _MALFUNCTION_LEVELS)
    rooms = (game_map.levels.get(target_level, {}) if game_map else {}) or {}
    target_room = (random.choice(list(rooms.keys())) if rooms
                   else getattr(player, 'map_room', 1))
    await ctx.server._teleport_to(ctx, target_level, target_room)
