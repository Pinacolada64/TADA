"""bar/zelda.py — Madame Zelda's: spy on stats / resurrect monsters."""
import glob
import json
import logging
from pathlib import Path

from flags import PlayerFlags
from base_classes import Gender, PlayerStat, PlayerMoneyTypes
from commands.messaging import find_players, player_exists
from network_context import GameContext
from presence import broadcast_area

log = logging.getLogger(__name__)

_NPC = "Madame Zelda"

# Player save files live here relative to the server working directory.
_PLAYER_DIR = Path("run") / "server"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def get_player_info(stats: list[str], id_pattern: str = "*") -> dict | None:
    """Read *stats* from every player-<id_pattern>.json on disk.

    Returns a dict {'id': ..., stat: value, ...} for the first matching file,
    or None if no files match.
    """
    log.info("Info requested: %s for pattern %r", stats, id_pattern)
    # TODO: check connected players first to avoid stale disk data
    filename_list = glob.glob(str(_PLAYER_DIR / f"player-{id_pattern}.json"))
    log.debug("filename list: %s", filename_list)

    if not filename_list:
        return None

    for player_filename in filename_list:
        log.info("get_player_info: reading %s", player_filename)
        try:
            with open(player_filename) as f:
                data = json.load(f)
            result = {'id': data['id']}
            for stat in stats:
                try:
                    result[stat] = data[stat]
                except KeyError:
                    log.warning("stat %r not found in %s", stat, player_filename)
            return result
        except (FileNotFoundError, json.JSONDecodeError):
            log.exception("Could not read %s", player_filename)
            continue

    return None


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

async def _zelda_menu(ctx: GameContext) -> None:
    return_key = getattr(ctx.player.client_settings, 'return_key', 'Enter')
    await ctx.send([
        "[S]tudy a player (1,000 silver)",
        "[R]esurrect monsters (6,000 silver), or",
        f"[{return_key}] / [L] Leave",
    ])


def _player_list_lines(ctx: GameContext, pattern: str = '*') -> list[str]:
    """Return formatted player list lines, optionally filtered by pattern.

    Supports * and ? wildcards.  Online players are marked with *.
    """
    from commands.messaging import find_players, online_player_names
    matches = find_players(ctx.server, pattern)
    if not matches:
        return [f'(No players matching "{pattern}".)']
    online = {n.lower() for n in online_player_names(ctx.server)}
    lines  = [f'Players matching "{pattern}" (* = online):', '']
    for name in matches:
        marker = '*' if name.lower() in online else ' '
        lines.append(f'  {marker} {name}')
    return lines


async def _study_player(ctx: GameContext) -> None:
    """Let the player spy on another character's stats for 1,000 silver."""
    player = ctx.player
    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send('[?] lists players.  Wildcards * and ? are supported.')

    raw = await ctx.prompt('"Study which player?" (? to list, wildcards * and ? ok)')
    if raw is None:
        return
    look_up = raw.strip()
    if not look_up:
        return

    if look_up.lower() == player.name.lower():
        await ctx.send('She looks you up and down. "I suggesssst youuuuuu uuuuuuuse a mirror!"')
        return

    if look_up == '?':
        await ctx.send(_player_list_lines(ctx))
        return

    # Wildcard: show matches and let them pick instead of charging
    if '*' in look_up or '?' in look_up:
        await ctx.send(_player_list_lines(ctx, look_up))
        return

    # Validate name before asking for payment
    if not player_exists(ctx.server, look_up):
        await ctx.send(f'{_NPC} peers into the ball. "I seeee no oooone by thaaaaat name..."')
        return

    # Confirm payment (skip in debug mode)
    if player.query_flag(PlayerFlags.DEBUG_MODE):
        pay = True
        log.info("Debug: bypassing payment confirmation")
    else:
        raw2 = await ctx.prompt('Y/N', preamble_lines=[
            '"It willlll cossssst 1,000 silver.  Is thaaaaaat okayyyyy?"',
        ])
        pay = raw2 is not None and raw2.strip().lower() in ('y', 'yes')

    if not pay:
        await ctx.send('"Hmph..."')
        return

    # TODO: verify player.subtract_silver sign convention (positive = deduct)
    if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, 1_000):
        await ctx.send('"You don\'t have enough silver!"')
        return

    await ctx.send(f'{_NPC} hunkers down over the ball.. "I seeeee..."')

    stats = ['name', 'gender', 'map_level', 'hit_points', 'experience',
             'shield', 'armor', 'stat']
    info = get_player_info(stats, id_pattern=look_up)
    if info is None:
        await ctx.send(f'{_NPC} frowns. "I cannot seeee thiiiiis person..."')
        return

    pronoun = "She" if info.get('gender') == Gender.FEMALE else "He"
    await ctx.send([
        f"{info['name']} is on dungeon level {info.get('map_level', '?')}. "
        f"{pronoun} has {info.get('hit_points', '?')} hit points.",
        "",
    ])

    # TODO: stat keys from JSON are strings, not PlayerStat enums — needs mapping
    stat_block = info.get('stat', {})
    if stat_block:
        await ctx.send(
            f"{pronoun} has "
            f"charisma of {stat_block.get(str(PlayerStat.CHR), '?')}, "
            f"constitution of {stat_block.get(str(PlayerStat.CON), '?')}, "
            f"dexterity of {stat_block.get(str(PlayerStat.DEX), '?')}, "
            f"energy of {stat_block.get(str(PlayerStat.EGY), '?')}, "
            f"intelligence of {stat_block.get(str(PlayerStat.INT), '?')}, "
            f"strength of {stat_block.get(str(PlayerStat.STR), '?')}, "
            f"and wisdom of {stat_block.get(str(PlayerStat.WIS), '?')}."
        )

    await ctx.send(
        f"{info['name']} has achieved {info.get('experience', '?')} experience in the land."
    )

    sh = info.get('shield', 'none')
    ar = info.get('armor',  'none')
    shield = f'{sh}%' if str(sh).isnumeric() else 'no'
    armor  = f'{ar}%' if str(ar).isnumeric() else 'no'
    await ctx.send(f"{pronoun} has {shield} shield, and {armor} armor.")


async def _resurrect_monsters(ctx: GameContext) -> None:
    """Resurrect a player's dead monsters for 6,000 silver."""
    player = ctx.player

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send('[?] lists players.  Wildcards * and ? are supported.')

    raw = await ctx.prompt('"Whooose monsters shall I briiiiing back to liiiiife?" (? to list)')
    if raw is None:
        return
    target = raw.strip()
    if not target:
        return

    if target == '?':
        await ctx.send(_player_list_lines(ctx))
        return

    if '*' in target or '?' in target:
        await ctx.send(_player_list_lines(ctx, target))
        return

    if not player_exists(ctx.server, target):
        await ctx.send(f'{_NPC} shakes her head. "Theeeeere are no monsters to raissse for thaaaaat one..."')
        return

    raw2 = await ctx.prompt('Y/N', preamble_lines=['"Dooo you wiiiiish to be unknowwwwwn?"'])
    anonymous = raw2 is not None and raw2.strip().lower() in ('y', 'yes')
    benefactor = "somebody" if anonymous else player.name

    message = f'Zelda casts "Monster Life" on {target}!  Spell paid for by {benefactor}!'
    await ctx.send(message)
    # TODO: write to battle log

    # TODO: verify player.subtract_silver sign convention
    player.subtract_silver(PlayerMoneyTypes.IN_HAND, 6_000)

    await ctx.send([
        f"{_NPC} and her cat get [really] weird...",
        "[TODO]: Resurrect player's monsters",
        '"It iiiisss doooooone!"',
    ])


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    """Madame Zelda interaction loop."""
    player = ctx.player

    await ctx.send(f'{_NPC} and her cat sit in front of a crystal ball.')
    await broadcast_area(ctx, 'bar', f'{player.name} sits down in front of {_NPC}.')
    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send([
            "",
            "She can either show other players' statistics (which costs 1,000 silver), "
            "or resurrect their dead monsters so they must be fought again "
            "(which costs 6,000 silver).",
            "",
        ])
    await _zelda_menu(ctx)

    while True:
        await ctx.send("")
        raw = await ctx.prompt('"What dooooo you wiiiiiish?"')
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

        if command == 's':
            await _study_player(ctx)
        elif command == 'r':
            await _resurrect_monsters(ctx)
        elif command == '?':
            await _zelda_menu(ctx)
        elif command in ('l', 'q'):
            await ctx.send(f'{_NPC} crosses her arms. "Gooo away, you bother my caaaat..."')
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from {_NPC}\'s table.')
            break
        else:
            await ctx.send(f'{_NPC} stares at you. Her cat stares too.')


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
    ctx.player.previous_command = None
    ctx.player.client_settings = MagicMock(return_key='Return')
    ctx.player.query_flag = lambda _: False
    ctx.player.subtract_silver = lambda *_: True
    ctx.send = AsyncMock()

    answers = iter(['s', '*', 'y', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print("Standalone zelda test complete.")
