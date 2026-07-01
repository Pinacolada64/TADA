"""bar/zelda.py — Madame Zelda's: spy on stats / resurrect monsters / fortune.

Ported from SPUR.BAR.S (zelda/zelda.3/zelda.4/pr.weapons section).

SPUR notes:
  - Study a player: 1,000 silver; shows all stats + weapons carried.
  - Resurrect monsters: 6,000 silver; clears target's monsters_killed list
    (SPUR: writes 0 to position 44 of spur.monsters file for that player).
    Can be done anonymously ("SOMEBODY").
  - Fortune: free; Zelda reads the tea leaves.
"""
import datetime
import glob
import json
import logging
import os
from pathlib import Path
from random import choice

from base_classes import Gender, PlayerStat, PlayerMoneyTypes, PronounType
from commands.messaging import player_exists, prompt_player_choice
from flags import PlayerFlags
from items import ItemCategory
from network_context import GameContext
from presence import broadcast_area
from tada_utilities import get_pronoun

log = logging.getLogger(__name__)

_NPC        = "Madame Zelda"
_AP         = "'"
_STUDY_COST = 1_000
_RESS_COST  = 6_000

# Player save files live here relative to the server working directory.
_PLAYER_DIR = Path("run") / "server"


# ---------------------------------------------------------------------------
# Battle log  (SPUR.BAR.S: "battle.log" file, appended on resurrection)
# ---------------------------------------------------------------------------

def _append_battle_log(entry: str) -> None:
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    path = os.path.join(str(base or './run/server'), 'battle.log')
    try:
        with open(path, 'a') as fh:
            stamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            fh.write(f'[{stamp}] {entry}\n')
    except Exception:
        log.exception('Failed to write battle.log')


# ---------------------------------------------------------------------------
# Player-file helpers
# ---------------------------------------------------------------------------

def _player_json_path(name: str) -> Path | None:
    """Return the JSON save-file path for a player name, or None if not found."""
    pattern = str(_PLAYER_DIR / f'player-{name}.json')
    matches = glob.glob(pattern)
    if matches:
        return Path(matches[0])
    # Case-insensitive fallback
    for p in _PLAYER_DIR.glob('player-*.json'):
        stem = p.stem[len('player-'):]
        if stem.lower() == name.lower():
            return p
    return None


def get_player_info(stats: list[str], id_pattern: str = '*') -> dict | None:
    """Read *stats* from every player-<id_pattern>.json on disk.

    Returns a dict {'id': ..., stat: value, ...} for the first matching file,
    or None if no files match.
    """
    log.info('Info requested: %s for pattern %r', stats, id_pattern)
    filename_list = glob.glob(str(_PLAYER_DIR / f'player-{id_pattern}.json'))
    log.debug('filename list: %s', filename_list)
    if not filename_list:
        return None
    for player_filename in filename_list:
        log.info('get_player_info: reading %s', player_filename)
        try:
            with open(player_filename) as f:
                data = json.load(f)
            stem        = Path(player_filename).stem
            fallback_id = stem[len('player-'):] if stem.startswith('player-') else stem
            result      = {'id': data.get('id', fallback_id)}
            for stat in stats:
                try:
                    result[stat] = data[stat]
                except KeyError:
                    log.warning('stat %r not found in %s', stat, player_filename)
            return result
        except (FileNotFoundError, json.JSONDecodeError):
            log.exception('Could not read %s', player_filename)
            continue
    return None


def _find_online_player(ctx, name: str):
    """Return the live Player object if *name* is online, else None."""
    for client in getattr(ctx.server, 'clients', []):
        p = getattr(client, 'player', None)
        if p and p.name.lower() == name.lower():
            return p
    return None


def _clear_monsters_killed_offline(name: str) -> bool:
    """Clear monsters_killed in a player's JSON save file directly.

    Returns True on success.
    """
    path = _player_json_path(name)
    if path is None:
        log.warning('_clear_monsters_killed_offline: no save file for %r', name)
        return False
    try:
        with open(path) as fh:
            data = json.load(fh)
        data['monsters_killed'] = []
        with open(path, 'w') as fh:
            json.dump(data, fh, indent=4)
        return True
    except Exception:
        log.exception('Failed to clear monsters_killed for %r', name)
        return False


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

async def _zelda_menu(ctx: GameContext) -> None:
    rk = getattr(ctx.player.client_settings, 'return_key', 'Enter')
    await ctx.send([
        f'[S]tudy a player ......... {_STUDY_COST:,} silver',
        f'[R]esurrect monsters ..... {_RESS_COST:,} silver',
        f'[T]ell your fortune ............. Free!',
        '',
        f'[{rk}] / [L] Leave',
    ])


# ---------------------------------------------------------------------------
# STUDY  (SPUR.BAR.S zelda.3 + pr.weapons)
# ---------------------------------------------------------------------------

async def _study_player(ctx: GameContext) -> None:
    """Spy on another character's full stats for 1,000 silver."""
    player = ctx.player

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send('[?] lists players.  Wildcards * and ? are supported.')

    raw = await ctx.prompt('"Study which player?" (? to list, wildcards ok)')
    if raw is None:
        return
    look_up = raw.strip()
    if not look_up:
        return

    if look_up.lower() == player.name.lower():
        await ctx.send(f'{_NPC} looks you up and down. "I suggesssst youuuu uuuuse a mirror!"')
        return

    if look_up == '?' or '*' in look_up or '?' in look_up:
        pattern = '*' if look_up == '?' else look_up
        look_up = await prompt_player_choice(ctx, pattern, prompt_text='Study whom')
        if look_up is None:
            return
    elif not player_exists(ctx.server, look_up):
        await ctx.send(f'{_NPC} peers into the ball. "I seeee no oooone by thaaaaat name..."')
        return

    # Confirm and charge
    raw2 = await ctx.prompt('Y/N', preamble_lines=[
        f'{_NPC}: "It willlll cossssst {_STUDY_COST:,} silver.  Is thaaaaaat okayyyyy?"',
    ])
    if not raw2 or raw2.strip().lower() not in ('y', 'yes'):
        await ctx.send(f'{_NPC}: "Hmpppth.."')
        return

    silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
    if silver < _STUDY_COST:
        await ctx.send(f'{_NPC}: "Ye doooo not have enough gold."')
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, _STUDY_COST)
    player.unsaved_changes = True

    await ctx.send(f'{_NPC} hunkers down over the ball.. "I SEEEEEE......."')

    fields = ['name', 'gender', 'char_class', 'char_race', 'guild',
              'natural_alignment', 'current_alignment',
              'map_level', 'map_room', 'hit_points', 'experience', 'honor',
              'shield', 'armor', 'silver', 'monsters_killed', 'times_played',
              'stats', 'inventory']
    info = get_player_info(fields, id_pattern=look_up)
    if info is None:
        await ctx.send(f'{_NPC} frowns. "I cannot seeee thiiiiis person..."')
        return

    pronoun     = 'She' if info.get('gender') == Gender.FEMALE else 'He'
    target_name = info.get('name', look_up)
    level       = info.get('map_level', '?')

    # Identity + level (SPUR.BAR.S: "n2$ on dungeon level yl")
    parts = [target_name]
    if info.get('char_race'):
        parts.append(str(info['char_race']))
    if info.get('char_class'):
        parts.append(str(info['char_class']))
    if info.get('guild'):
        parts.append(f"({info['guild']})")
    await ctx.send(' '.join(parts))
    await ctx.send(f'"{target_name} has achieved level {level} in the land."')

    # Alignment
    nat = info.get('natural_alignment', '?')
    cur = info.get('current_alignment', '?')
    await ctx.send(f'Alignment: {nat} (natural) / {cur} (current)')

    # Location & vitals
    await ctx.send(
        f'{pronoun} is on dungeon level {level}, '
        f'room {info.get("map_room", "?")}, '
        f'with {info.get("hit_points", "?")} hit points.'
    )

    # Ability scores (SPUR: strength, intelligence, dexterity, energy, constitution, wisdom)
    stat_block = info.get('stats', {})
    if stat_block:
        await ctx.send(
            f'With a strength of {stat_block.get(str(PlayerStat.STR), "?")}, '
            f'intelligence of {stat_block.get(str(PlayerStat.INT), "?")}, '
            f'dexterity of {stat_block.get(str(PlayerStat.DEX), "?")}, '
            f'energy of {stat_block.get(str(PlayerStat.EGY), "?")}, '
            f'constitution of {stat_block.get(str(PlayerStat.CON), "?")}, '
            f'wisdom of {stat_block.get(str(PlayerStat.WIS), "?")}.'
        )

    # Progress
    await ctx.send(
        f'{pronoun} has {info.get("experience", "?")} experience '
        f'and {info.get("honor", "?")} honor.'
    )

    # Equipment (SPUR: "has ye% shield, and yf% armor")
    sh     = info.get('shield', None)
    ar     = info.get('armor',  None)
    shield = f'{sh}%' if sh is not None and str(sh).lstrip('-').isnumeric() else 'no'
    armor  = f'{ar}%' if ar is not None and str(ar).lstrip('-').isnumeric() else 'no'
    await ctx.send(f'{pronoun} has {shield} shield and {armor} armor.')

    # Weapons — "Instruments of death..."  (SPUR.BAR.S: gosub pr.weapons)
    inv_data = info.get('inventory', [])
    weapons  = [
        e.get('item_name', '?')
        for e in (inv_data if isinstance(inv_data, list) else [])
        if e.get('item_category') == str(ItemCategory.WEAPON)
    ]
    if weapons:
        await ctx.send('"Instruments of death..."')
        for w in weapons:
            await ctx.send(f'  {w}')
    else:
        await ctx.send('No weapons.')

    # Monsters killed
    mk = info.get('monsters_killed')
    if mk:
        count = len(mk) if isinstance(mk, list) else mk
        await ctx.send(f'{pronoun} has slain {count} monster type(s).')

    # Silver
    silver_data = info.get('silver', {})
    if isinstance(silver_data, dict):
        in_hand = silver_data.get('IN_HAND', 0)
        in_bank = silver_data.get('IN_BANK', 0)
        await ctx.send(f'{pronoun} carries {in_hand:,}s and has {in_bank:,}s in the bank.')

    if info.get('times_played'):
        await ctx.send(f'{pronoun} has played {info["times_played"]} time(s).')

    await ctx.send(f'{_NPC} sits back. "It issss done."')


# ---------------------------------------------------------------------------
# RESURRECT  (SPUR.BAR.S zelda.4)
# ---------------------------------------------------------------------------

async def _resurrect_monsters(ctx: GameContext) -> None:
    """Clear a player's monsters_killed list for 6,000 silver."""
    player = ctx.player

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send('[?] lists players.  Wildcards * and ? are supported.')

    raw = await ctx.prompt(f'{_NPC}: "Whooose monsters shall I briiiiing back to liiiiife?" (? to list)')
    if raw is None:
        return
    target = raw.strip()
    if not target:
        return

    if target == '?' or '*' in target or '?' in target:
        pattern = '*' if target == '?' else target
        target  = await prompt_player_choice(ctx, pattern,
                                             prompt_text='Resurrect whose monsters')
        if target is None:
            return
    elif not player_exists(ctx.server, target):
        await ctx.send(f'{_NPC} shakes her head. "Theeeeere are no monsters to raissse for thaaaaat one..."')
        return

    if target.lower() == player.name.lower():
        await ctx.send(f'{_NPC}: "I suggest you NOT do that!"')
        return

    # Check target actually has killed monsters
    mk_info = get_player_info(['monsters_killed'], id_pattern=target)
    mk      = mk_info.get('monsters_killed') if mk_info else None
    if not mk:
        await ctx.send(f'{_NPC} peers into the ball. "Thiiiiis one has no dead monstersss to raissse..."')
        return

    count = len(mk) if isinstance(mk, list) else mk

    # Confirm target and show count
    raw2 = await ctx.prompt('Y/N', preamble_lines=[
        f'You want me to bring {target}{_AP}s {count} slain monster type(s) back alive?'
    ])
    if not raw2 or raw2.strip().upper() != 'Y':
        await ctx.send(f'{_NPC}: "Wellll, make up your mind!"')
        return

    # Confirm cost
    raw3 = await ctx.prompt('Y/N', preamble_lines=[
        f'{_NPC}: "It will cost you {_RESS_COST:,} silver.  Ok?"'
    ])
    if not raw3 or raw3.strip().upper() != 'Y':
        await ctx.send(f'{_NPC}: "Hmpppth.."')
        return

    silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
    if silver < _RESS_COST:
        await ctx.send(f'{_NPC}: "Ye doooo not have enough gold."')
        return

    # Anonymous option (SPUR.BAR.S: "Dooo you wish to be unknown?")
    raw4 = await ctx.prompt(f'{_NPC}: "Dooo you wish to be unknown?" (Y/N)')
    anonymous  = raw4 is not None and raw4.strip().upper() == 'Y'
    benefactor = 'SOMEBODY' if anonymous else player.name

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, _RESS_COST)
    player.unsaved_changes = True

    await ctx.send(f'{_NPC} and her cat get really weird...')

    # Clear monsters_killed — online player first, then fall back to disk
    online_target = _find_online_player(ctx, target)
    if online_target is not None:
        online_target.monsters_killed = []
        online_target.unsaved_changes = True
        cleared = True
    else:
        cleared = _clear_monsters_killed_offline(target)

    if not cleared:
        await ctx.send(f'{_NPC} frowns. "Something went wrong... the ritual failed."')
        # refund
        player.subtract_silver(PlayerMoneyTypes.IN_HAND, -_RESS_COST)
        player.unsaved_changes = True
        return

    # Battle log (SPUR.BAR.S: appends to battle.log)
    stamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    log_entry = (
        f'** MONSTER REVIVAL ** — {target}{_AP}s monsters raised'
        f' | Spell paid for by {benefactor}'
    )
    _append_battle_log(log_entry)

    if not anonymous:
        await broadcast_area(
            ctx, 'bar',
            f'{player.name} pays Zelda to raise {target}{_AP}s slain monsters back to life!'
        )

    await ctx.send([
        f'{_NPC}: "It issssss done!"',
        f'(All of {target}{_AP}s {count} slain monster type(s) may walk the dungeon again.)',
        f'[Spell paid for by {benefactor}]',
    ])


# ---------------------------------------------------------------------------
# FORTUNE  (free; TADA addition)
# ---------------------------------------------------------------------------

_FORTUNES = [
    "Post no bills.",
    "As you slide down the banister of life, make sure the splinters are facing the right way.",
    "Ask me no questions and I'll tell you no lies.",
    "The monster you fear most is already behind you.  No, don't look.",
    "Help!  I am trapped inside a crystal ball!",
    "Today is a good day to not be eaten.",
    "A fool and his silver are soon parted.  You seem quite attached to yours.",
    "Your lucky direction today: not down.",
    "The secret to happiness is low expectations and good armor.",
    "You will meet a tall, dark stranger.  He will attempt to pick your pocket.",
    "The cat sees something you cannot.  The cat is usually right.",
    "Great peril awaits you.  Also, moderate peril.  Actually quite a lot of peril.",
    "What you seek is closer than you think.  And more dangerous.",
]


async def _tell_fortune(ctx: GameContext) -> None:
    player = ctx.player
    while True:
        fortune = choice(_FORTUNES)
        await broadcast_area(
            ctx, 'bar',
            f'{player.name} gets {get_pronoun(player, PronounType.POSSESSIVE_ADJECTIVE)} fortune read.'
        )
        await ctx.send(f'{_NPC} consults the tea leaves, finally announcing: "{fortune}"')
        ans = await ctx.prompt('Another fortune? (Y/N)')
        if not ans or ans.strip().lower() not in ('y', 'yes'):
            break


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    """Madame Zelda interaction loop."""
    player = ctx.player

    await ctx.send(f'{_NPC} and her cat sit in front of a crystal ball.')
    await broadcast_area(ctx, 'bar', f'{player.name} sits down in front of {_NPC}.')

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send([
            '',
            f'{_NPC} can study another player{_AP}s statistics ({_STUDY_COST:,}s), '
            f'resurrect their dead monsters so they must be fought again ({_RESS_COST:,}s), '
            f'or tell your fortune for free.',
            '',
        ])
    await _zelda_menu(ctx)

    while True:
        await ctx.send('')
        raw = await ctx.prompt(f'{_NPC}: "What dooooo you wiiiiiish?"')
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

        cmd = inp[0]
        player.previous_command = cmd

        if cmd == 's':
            await _study_player(ctx)
        elif cmd == 'r':
            await _resurrect_monsters(ctx)
        elif cmd == 't':
            await _tell_fortune(ctx)
        elif cmd == '?':
            await _zelda_menu(ctx)
        elif cmd in ('l', 'q'):
            await ctx.send(f'{_NPC} crosses her arms. "Gooo away, you bother my caaaat..."')
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from {_NPC}{_AP}s table.')
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
    ctx.player.client_settings  = MagicMock(return_key='Return')
    ctx.player.query_flag       = lambda _: False
    ctx.player.get_silver       = MagicMock(return_value=9999)
    ctx.player.subtract_silver  = MagicMock(return_value=True)
    ctx.server = MagicMock()
    ctx.server.clients = []
    ctx.send = AsyncMock()

    answers = iter(['s', '?', '1', 'y', 't', 'n', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print('Standalone zelda test complete.')
