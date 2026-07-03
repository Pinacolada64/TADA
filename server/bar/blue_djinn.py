"""bar/blue_djinn.py — The Blue Djinn: hire a thug to attack another player.

Ported from SPUR.BAR.S (thug/hire/bouncer section).

SPUR notes:
  - Price = target's level × 500 gold.
  - Hirer may remain anonymous; stored as "SOMEBODY" in the contract.
  - Contracts are stored in a shared 'thug' file keyed by target (SPUR.BAR.S).
    TADA uses data/hit_contracts.json instead.
  - Insult → Mundo the bouncer throws you out (−5 HP, teleport to door).
  - Resolution (carrying out the hit when the target logs in) is a TODO.
"""
import datetime
import json
import logging
import os
import random

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from network_context import GameContext
from presence import broadcast_area

log = logging.getLogger(__name__)

_NPC      = "The Blue Djinn"
_AP       = "'"
_PRICE_PER_LEVEL = 500   # silver per target level (SPUR.BAR.S: yn*500)


# ---------------------------------------------------------------------------
# Hit-contract storage  (analogous to SPUR's 'thug' file)
# ---------------------------------------------------------------------------

def _contracts_path() -> str:
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    if base is None:
        base = './run/server'
    return os.path.join(str(base), 'hit_contracts.json')


def _load_contracts() -> dict:
    path = _contracts_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as fh:
            return json.load(fh)
    except Exception:
        log.exception('Failed to load hit_contracts.json')
        return {}


def _save_contracts(data: dict) -> None:
    path = _contracts_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, 'w') as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        log.exception('Failed to save hit_contracts.json')


def add_contract(target_name: str, attacker_display: str,
                 attacker_real: str, gold_paid: int) -> None:
    """Record a hit contract against target_name."""
    data = _load_contracts()
    key  = target_name.lower()
    data.setdefault(key, [])
    data[key].append({
        'attacker_display': attacker_display,
        'attacker_real':    attacker_real,
        'gold_paid':        gold_paid,
        'timestamp':        datetime.datetime.utcnow().isoformat(),
        'resolved':         False,
    })
    _save_contracts(data)


def pending_contracts(target_name: str) -> list:
    """Return unresolved hit contracts against target_name."""
    data = _load_contracts()
    return [c for c in data.get(target_name.lower(), []) if not c.get('resolved')]


def resolve_contract(target_name: str, index: int) -> None:
    """Mark a contract resolved (called when the hit is carried out)."""
    data = _load_contracts()
    key  = target_name.lower()
    if key in data and index < len(data[key]):
        data[key][index]['resolved'] = True
        _save_contracts(data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _show_menu(ctx: GameContext) -> None:
    rk = ctx.player.client_settings.return_key
    await ctx.send(
        f'[H]ire, [I]nsult, [L] / [{rk}]: Leave  |  [?] Help'
    )


def _player_level(player) -> int:
    """Character level (SPUR's yn)."""
    return max(1, getattr(player, 'xp_level', 1))


# ---------------------------------------------------------------------------
# HIRE  (SPUR.BAR.S hire / thug section)
# ---------------------------------------------------------------------------

async def _hire(ctx: GameContext) -> None:
    player = ctx.player

    await ctx.send(f'{_NPC}: {_AP}Who do you wish me to mess up?{_AP}')

    while True:
        raw = await ctx.prompt('Player name (? to list, Enter to cancel)')
        if not raw or not raw.strip():
            return

        pattern = raw.strip()

        from commands.messaging import prompt_player_choice, find_players, is_online
        if pattern == '?':
            pattern = '*'

        # Use the listing utility to search
        names = find_players(ctx.server, pattern)
        if not names:
            await ctx.send(f'{_NPC} scowls. No players found matching "{pattern}".')
            continue

        # Filter out self
        names = [n for n in names if n.lower() != player.name.lower()]
        if not names:
            await ctx.send(f'{_NPC} scowls. {_AP}You cannot hire me against yourself.{_AP}')
            continue

        if len(names) == 1:
            target_name = names[0]
        else:
            # Multiple matches — show a numbered list
            online_set = {n.lower() for n in (
                [c.player.name for c in getattr(ctx.server, 'clients', [])
                 if getattr(c, 'player', None)]
                if hasattr(ctx, 'server') else []
            )}
            lines = ['', 'Matching players (* = online):', '']
            for i, n in enumerate(names, 1):
                star = '*' if n.lower() in online_set else ' '
                lines.append(f'  {i:>3}.{star} {n}')
            lines.append('')
            await ctx.send(lines)
            raw2 = await ctx.prompt(f'Choose (1–{len(names)}, Enter to cancel)')
            if not raw2 or not raw2.strip():
                return
            try:
                idx = int(raw2.strip()) - 1
                if not (0 <= idx < len(names)):
                    raise ValueError
            except ValueError:
                await ctx.send(f'{_NPC} scowls.')
                continue
            target_name = names[idx]

        # Calculate price from target's level.  We can't load offline players
        # without a full profile fetch, so we use xp_level of the current
        # player as a fallback if the target is offline.
        target_level = 1
        online_clients = getattr(ctx.server, 'clients', [])
        for c in online_clients:
            tp = getattr(c, 'player', None)
            if tp and tp.name.lower() == target_name.lower():
                target_level = _player_level(tp)
                break

        price = target_level * _PRICE_PER_LEVEL

        await ctx.send(
            f'{_NPC}: {_AP}You want me to beat up {target_name}?{_AP}'
        )
        raw3 = await ctx.prompt('Y/N')
        if not raw3 or raw3.strip().upper() != 'Y':
            await ctx.send(f'{_NPC}: {_AP}Well, make up your mind!{_AP}')
            return

        await ctx.send(
            f'{_NPC}: {_AP}For a level {target_level} opponent, '
            f'the price is {price:,}s. Ok?{_AP}'
        )
        raw4 = await ctx.prompt('Y/N')
        if not raw4 or raw4.strip().upper() != 'Y':
            await ctx.send(f'{_NPC} snickers.')
            return

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < price:
            await ctx.send(
                f'{_NPC} shakes his head. {_AP}Ye do not have enough gold.{_AP}'
            )
            return

        # Anonymous option (SPUR.BAR.S: "Do you wish to remain unknown?")
        raw5 = await ctx.prompt('Do you wish to remain unknown? (Y/N)')
        if raw5 and raw5.strip().upper() == 'Y':
            attacker_display = 'SOMEBODY'
        else:
            attacker_display = player.name

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
        player.unsaved_changes = True

        add_contract(
            target_name     = target_name,
            attacker_display= attacker_display,
            attacker_real   = player.name,
            gold_paid       = price,
        )

        await ctx.send(
            f'{_NPC} bows. {_AP}The agreement shall be carried out..{_AP}'
        )
        await broadcast_area(
            ctx, 'bar',
            f'{player.name} makes an arrangement with {_NPC}.',
        )
        return


# ---------------------------------------------------------------------------
# INSULT  (SPUR.BAR.S bouncer section)
# ---------------------------------------------------------------------------

async def _insult(ctx: GameContext, bar) -> None:
    player = ctx.player
    targets = ['lineage', "dog's appearance", 'parenting skills',
               'fashion sense', 'smell', 'intelligence']
    target = random.choice(targets)
    await ctx.send(
        f'You say something deeply insulting about {_NPC}{_AP}s {target}.\n'
        f'{_NPC}{_AP}s eyes narrow...'
    )
    from bar.main import _bouncer
    await _bouncer(ctx, bar)
    await broadcast_area(ctx, 'bar', f'Mundo throws {player.name} out of the bar.')


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    """The Blue Djinn interaction loop."""
    player = ctx.player

    await ctx.send([
        f'{_NPC} sits behind the table, fingers steepled.',
        f'{_AP}What do you want?{_AP} he hisses.',
    ])
    await broadcast_area(ctx, 'bar', f'{player.name} sits down across from {_NPC}.')

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send(
            f'For a price, {_NPC} can arrange for another player '
            f'to be... inconvenienced.'
        )
        await _show_menu(ctx)

    while True:
        await ctx.send('')
        raw = await ctx.prompt(f'{_NPC}')
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

        if cmd in ('l', 'q'):
            await ctx.send(f'{_NPC} looks relieved.')
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from {_NPC}.')
            break
        elif cmd == '?':
            await _show_menu(ctx)
        elif cmd == 'h':
            await _hire(ctx)
        elif cmd == 'i':
            await _insult(ctx, bar)
            break   # bouncer ejects player
        else:
            await ctx.send(f'{_NPC} looks amused.')


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
    ctx.player.xp_level   = 3
    ctx.player.previous_command = None
    ctx.player.client_settings  = MagicMock(return_key='Return')
    ctx.player.query_flag = lambda _: False
    ctx.player.get_silver = MagicMock(return_value=5000)
    ctx.player.subtract_silver = MagicMock(return_value=True)
    ctx.server = MagicMock()
    ctx.server.clients = []
    ctx.send  = AsyncMock()

    answers = iter(['h', 'Bilbo', 'y', 'y', 'n', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print('Standalone blue_djinn test complete.')
