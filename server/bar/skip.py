"""bar/skip.py — Skip's Eats: hash and coffee at the Wall Bar & Grill.

Ported from t_bar_skip.lbl (Nov 2014).

SPUR notes:
  - Hash costs 5 silver; coffee costs 1 silver.  (Reversed in earlier TADA stub.)
  - Hash: STR += rnd(5) capped at 25; clears hungry (player.food = max).
  - Coffee: EGY += rnd(5) capped at 25; clears thirsty (player.drink = max);
    clears tired; +4 HP if HP ≤ 21; CON += rnd(3) capped at 25.
  - Once per day (ys$/"*SK" flag in SPUR, player.once_per_day in TADA).
  - Each item (hash, coffee) can only be ordered once per visit (SPUR: zv$ accumulator).
  - Gender address: female → "miss", male → "mac" (SPUR: z$).
  - Stat cap at 25 (SPUR: if peek(m)+ar<25 then poke m,...).
  - Feeding party members is a TADA extension; SPUR feeds only the current player.
"""
import logging
import random

from bar.ally_data import Ally
from base_classes import PlayerMoneyTypes, PlayerStat, PronounType
from flags import PlayerFlags
from network_context import GameContext
from presence import broadcast_area
from tada_utilities import get_pronoun

log = logging.getLogger(__name__)

_NPC       = "Skip"
_HASH_COST = 5    # silver  (SPUR: 5g for hash)
_COFF_COST = 1    # silver  (SPUR: 1g for coffee)
_STAT_CAP  = 25   # SPUR: if peek(m)+ar < 25 then poke m, peek(m)+ar
_HP_COFFEE_THRESHOLD = 21   # +4 HP only when HP <= this (SPUR: if x>21 then {:con})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gender_address(player) -> str:
    """Return 'miss' for female players, 'mac' for all others (SPUR: z$)."""
    try:
        from characters import Gender
        if getattr(player, 'gender', None) == Gender.FEMALE:
            return 'miss'
    except Exception:
        pass
    return 'mac'


def _improve_stat(player, stat: PlayerStat, rng: int) -> int:
    """Increase *stat* by randint(1, rng), capped at _STAT_CAP.

    Returns the actual amount gained (0 if already capped).
    SPUR: ar=fn r(ar):m=v1+85+s:if peek(m)+ar<25 then poke m,peek(m)+ar
    """
    gain    = random.randint(1, rng)
    current = player.stats.get(stat, 0)
    if current >= _STAT_CAP:
        return 0
    new_val = min(current + gain, _STAT_CAP)
    actual  = new_val - current
    player.stats[stat] = new_val
    player.unsaved_changes = True
    return actual


async def _show_menu(ctx: GameContext) -> None:
    await ctx.send([
        f'[H]ash   ({_HASH_COST} silver)',
        f'[C]offee ({_COFF_COST} silver)',
        '[L]eave',
    ])


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    """Skip's Eats interaction loop."""
    player  = ctx.player
    z       = _gender_address(player)

    await ctx.send(f'{_NPC} sweats over a hot grill, muttering under his breath...')

    # Debug hook: manually toggle the once-per-day flag
    if player.query_flag(PlayerFlags.DEBUG_MODE):
        raw = await ctx.prompt('Y/N', preamble_lines=[f"Add 'Skip' to once-per-day activities?"])
        if raw is not None and raw.strip().lower() in ('y', 'yes'):
            if _NPC not in player.once_per_day:
                player.once_per_day.append(_NPC)
                await ctx.send('Appended.')

    # Once-per-day gate (SPUR: sys is,"*SK",ys$ check)
    if _NPC in player.once_per_day:
        await ctx.send(
            f'Skip suddenly looks annoyed. "Hey, you\'ve already [been] here once today!" '
            'He points angrily towards the exit, and you decide to heed his advice. '
            '(Never argue with a man who has hot grease at his disposal.)'
        )
        return

    await broadcast_area(ctx, 'bar', f'{player.name} sits down at {_NPC}\'s counter.')

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await _show_menu(ctx)

    # Per-visit item lock (SPUR: zv$ accumulator — once ordered, can't order again this visit)
    ordered = set()

    while True:
        await ctx.send('')
        raw = await ctx.prompt(f'"{_NPC}: What\'ll ya have, {z}?"')
        if raw is None:
            break

        menu_item = raw.strip().lower()
        if not menu_item:
            continue

        await ctx.send('')

        if menu_item == 'h':
            if 'h' in ordered:
                await ctx.send(f'{_NPC} protests. "You just had the last of it!"')
                continue

            # Party selection (TADA extension — SPUR feeds only the current player)
            patron             = player
            first_or_third     = 'you'
            pronoun            = get_pronoun(player, PronounType.SUBJECTIVE)
            plural             = ''

            if player.party:
                # Debug: seed test allies
                if player.query_flag(PlayerFlags.DEBUG_MODE):
                    await player.party.add(ctx, player, Ally('Michelle',   'f', 4, 5))
                    await player.party.add(ctx, player, Ally('King Brian', 'm', 5, 6))

                patrons = [player] + list(player.party)
                lines   = [f'  {i}. {p.name}' for i, p in enumerate(patrons, 1)]
                await ctx.send(['Who to feed:', ''] + lines)

                selection = None
                while True:
                    raw_sel = await ctx.prompt(f'Choose (1-{len(patrons)})')
                    if raw_sel is None:
                        break
                    try:
                        sel = int(raw_sel.strip())
                        if 1 <= sel <= len(patrons):
                            selection = sel
                            break
                    except ValueError:
                        pass
                    await ctx.send('Try again.')
                if selection is None:
                    break

                patron = patrons[selection - 1]
                if isinstance(patron, Ally):
                    first_or_third = get_pronoun(patron, PronounType.SUBJECTIVE)
                    pronoun        = first_or_third.capitalize()
                    plural         = 's'
                else:
                    first_or_third = (
                        'you' if selection == 1
                        else get_pronoun(patron, PronounType.SUBJECTIVE)
                    )
                    pronoun = get_pronoun(patron, PronounType.SUBJECTIVE).capitalize()
                    plural  = ''

            if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, _HASH_COST):
                await ctx.send(f'{_NPC} mutters, "Ye don\'t got enough gold."')
                continue

            ordered.add('h')

            await ctx.send(
                f'{_NPC} pushes a chipped plate with some hash sitting on it towards {patron.name}. '
                f'Hesitantly, {first_or_third} decide{plural} to sample {_NPC}\'s wares. '
                '"The hash is greasy, but hot and nourishing."'
            )

            # STR += rnd(5) capped at 25  (SPUR: sub.improve_stats(6,5,"stronger"))
            if hasattr(patron, 'stats'):
                gain = _improve_stat(patron, PlayerStat.STR, 5)
                if gain and not player.query_flag(PlayerFlags.EXPERT_MODE):
                    poss = (
                        'You feel' if patron is player
                        else f'{get_pronoun(patron, PronounType.SUBJECTIVE).capitalize()} feels'
                    )
                    await ctx.send(f'({poss} stronger.)')

            # Clear hungry (SPUR: bit.clear v1+65,6 → player.food restored)
            if hasattr(patron, 'food'):
                patron.food = 20
                patron.unsaved_changes = True

        elif menu_item == 'c':
            if 'c' in ordered:
                await ctx.send(f'{_NPC} protests. "You just had the last of it!"')
                continue

            if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, _COFF_COST):
                await ctx.send(
                    f'{_NPC} wipes a nonexistent spot on the counter with a rag. '
                    '"I know, times are tough."'
                )
                continue

            ordered.add('c')

            await ctx.send(
                f'{_NPC} sets a chipped mug of viscous black something on the counter. '
                '"The steaming mug of coffee is strangely satisfying."'
            )

            # Clear thirsty (SPUR: bit.clear v1+65,3 → player.drink restored)
            player.drink = 20

            # Clear tired (SPUR: bit.clear v1+65,2)
            if player.query_flag(PlayerFlags.TIRED):
                player.clear_flag(PlayerFlags.TIRED)
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    await ctx.send('(You feel more awake.)')

            # EGY += rnd(5) capped at 25  (SPUR: sub.improve_stats(8,5,"more energetic"))
            gain = _improve_stat(player, PlayerStat.EGY, 5)
            if gain and not player.query_flag(PlayerFlags.EXPERT_MODE):
                await ctx.send('(You feel more energetic.)')

            # +4 HP if HP <= threshold  (SPUR: sub.adj_hp(1,4) if x<=21)
            if player.hit_points <= _HP_COFFEE_THRESHOLD:
                before = player.hit_points
                player.hit_points += 4
                player.unsaved_changes = True
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    await ctx.send(f'(HP: {before} → {player.hit_points}.)')

            # CON += rnd(3) capped at 25  (SPUR: sub.improve_stats(2,3,"revitalized"))
            gain = _improve_stat(player, PlayerStat.CON, 3)
            if gain and not player.query_flag(PlayerFlags.EXPERT_MODE):
                await ctx.send('(You feel revitalized.)')

            player.unsaved_changes = True

        elif menu_item == '?':
            await _show_menu(ctx)

        elif menu_item in ('l', 'q'):
            await ctx.send(f'{_NPC} mumbles, "Yeah, well... take \'er easy..."')
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from {_NPC}\'s counter.')
            # Mark once-per-day on leave (SPUR marks when player visits, not when they leave,
            # but we mark here so debug re-entry works cleanly)
            if _NPC not in player.once_per_day:
                player.once_per_day.append(_NPC)
                player.unsaved_changes = True
            break

        else:
            await ctx.send(f'{_NPC} mutters, "That ain\'t on the menu."')


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from party import Party

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.name          = 'Rulan'
    ctx.player.hit_points    = 18
    ctx.player.food          = 5
    ctx.player.drink         = 5
    ctx.player.once_per_day  = []
    ctx.player.party         = Party()
    ctx.player.stats         = {PlayerStat.STR: 10, PlayerStat.EGY: 10, PlayerStat.CON: 10}
    ctx.player.unsaved_changes = False
    ctx.player.query_flag    = lambda _: False
    ctx.player.clear_flag    = lambda _: None
    ctx.player.subtract_silver = MagicMock(return_value=True)
    ctx.send  = AsyncMock()

    answers = iter(['h', 'c', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print('Standalone skip test complete.')
