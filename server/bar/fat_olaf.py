"""bar/fat_olaf.py — Fat Olaf's Servant Trade.

Buy/sell/maintain allies.  Ported from t_bar_olaf.lbl and SPUR.BAR.S.

SPUR notes:
  - Max 3 allies in party at once.
  - Price = strength × 100 silver; Elite allies cost double (t_bar_olaf.lbl).
  - Selling pays back strength × 50 (half price); Elite doubles payout.
  - Olaf won't buy "free spirits" — allies not purchased here (SPUR.BAR.S).
  - Selling penalty: -50 honour if honour >= 50 (t_bar_olaf.lbl, 2012 version).
  - MAINTAIN in SPUR.BAR.S strengthens allies; honour +5; was a stub in
    t_bar_olaf.lbl ({:999}).  TADA implements the SPUR.BAR.S version.
"""
import logging
import random
from typing import List, Optional

from bar.ally_data import AllyFlags, AllyStatus, Ally, load_allies, save_ally_roster
from bar.allies import pick_ally
from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from network_context import GameContext
from presence import broadcast_area

log = logging.getLogger(__name__)

_NPC        = "Fat Olaf"
_AP         = "'"
_MAX_ALLIES = 3
_STRENGTHEN_BASE_COST = 20   # cost per point of current strength (TADA extension)
_HONOR_SELL_LOSS      = 50   # honour lost when selling (t_bar_olaf.lbl :185)
_HONOR_MAINTAIN_GAIN  = 5    # honour gained when maintaining (SPUR.BAR.S maint)


# ---------------------------------------------------------------------------
# Public filter utility — kept as module-level so other modules can use it
# (e.g. to list who owns whom, or to list all free/available allies)
# ---------------------------------------------------------------------------

def filter_allies(
    ally_list: List[Ally],
    filter_by_status: Optional[AllyStatus] = None,
) -> List[Ally]:
    """Return allies matching an optional status filter.

    Pass filter_by_status=None to get all allies unfiltered.
    Examples:
        filter_allies(all_allies, AllyStatus.FREE)     # available for sale
        filter_allies(all_allies, AllyStatus.SERVANT)  # owned by someone
        filter_allies(all_allies)                       # everyone
    """
    if filter_by_status is None:
        return list(ally_list)
    return [a for a in ally_list if a.status == filter_by_status]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ally_price(ally: Ally) -> int:
    """Buy price: strength × 100; double for Elite (t_bar_olaf.lbl :57-59)."""
    price = ally.strength * 100
    if AllyFlags.ELITE in (ally.flags or []):
        price *= 2
    return price


def _ally_sellback(ally: Ally) -> int:
    """Olaf's buyback offer: strength × 50; double for Elite (SPUR.BAR.S sell)."""
    price = ally.strength * 50
    if AllyFlags.ELITE in (ally.flags or []):
        price *= 2
    return price


def _is_elite(ally: Ally) -> bool:
    return AllyFlags.ELITE in (ally.flags or [])


def _owned_allies(player) -> List[Ally]:
    """Allies currently in this player's party."""
    from bar.ally_data import Ally as AllyType
    return [m for m in player.party if isinstance(m, AllyType)]


def _purchased_allies(player) -> List[Ally]:
    """Allies this player purchased (SERVANT status), excluding free spirits (FREE)."""
    from bar.ally_data import Ally as AllyType
    return [
        m for m in player.party
        if isinstance(m, AllyType)
        and m.status == AllyStatus.SERVANT
    ]


def _sync_to_roster(master_list: List[Ally], name: str,
                    status: AllyStatus, owner: Optional[str],
                    strength: Optional[int] = None) -> None:
    """Update the named ally in master_list and persist the roster."""
    for a in master_list:
        if a.name == name:
            a.status = status
            a.owner  = owner
            if strength is not None:
                a.strength = strength
            break
    save_ally_roster(master_list)


def _free_allies_for_sale(master_list: List[Ally], player) -> List[Ally]:
    """Allies available to buy: FREE status and not already owned by this player."""
    owned_names = {a.name for a in _owned_allies(player)}
    return [
        a for a in filter_allies(master_list, AllyStatus.FREE)
        if a.name not in owned_names
    ]


async def _show_menu(ctx: GameContext) -> None:
    rk = ctx.player.client_settings.return_key
    await ctx.send(
        f'[B]uy, [S]ell, or [M]aintain a servant; '
        f'[?] / [H]: Help; '
        f'[L] / [{rk}]: Leave'
    )


# ---------------------------------------------------------------------------
# BUY  (t_bar_olaf.lbl :30 / SPUR.BAR.S buy)
# ---------------------------------------------------------------------------

async def _buy_servant(ctx: GameContext, master_list: List[Ally]) -> None:
    player = ctx.player
    owned  = _owned_allies(player)

    if len(owned) >= _MAX_ALLIES:
        await ctx.send(f'{_NPC} shakes his head. {_AP}Yu hav 3 allies alriddy!{_AP}')
        return

    available = _free_allies_for_sale(master_list, player)
    if not available:
        await ctx.send(f'{_NPC} mutters, {_AP}Surry, ald solt ut!{_AP}')
        return

    while True:
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        lines  = ['Servants for sale:', '',
                  f'  {"##":>3}  {"Name":<22} {"Str":>3}  {"To-hit":>6}  {"Price":>7}  Notes',
                  '']
        for i, a in enumerate(available, 1):
            price     = _ally_price(a)
            elite_tag = '  [Elite!]' if _is_elite(a) else ''
            lines.append(
                f'  {i:>3}.  {a.name:<22} {a.strength:>3}  {a.to_hit*10:>5}%'
                f'  {price:>6}s{elite_tag}'
            )
        lines += ['',
                  f'  Silver in hand: {silver}s',
                  f'  [?] list again   [{ctx.player.client_settings.return_key}] cancel',
                  '']
        await ctx.send(lines)

        raw = await ctx.prompt(f'{_NPC}: {_AP}Buy vich vun? (1-{len(available)}, ? to list){_AP}')
        if raw is None or raw.strip() == '':
            await ctx.send(f'{_NPC} dismisses you with a wave. {_AP}Hokay, vine. See yu later!{_AP}')
            return
        if raw.strip() == '?':
            continue

        try:
            idx = int(raw.strip()) - 1
            if not (0 <= idx < len(available)):
                raise ValueError
        except ValueError:
            await ctx.send(f'{_NPC}: {_AP}Whoa, dun{_AP}t hav that many!{_AP}')
            continue

        chosen = available[idx]
        price  = _ally_price(chosen)

        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        if silver < price:
            await ctx.send(
                f'{_NPC} shakes his head. {_AP}Yu can{_AP}t afford zat vun, friend.{_AP}'
            )
            continue

        elite_line = f'(An Elite ally!)\n' if _is_elite(chosen) else ''
        raw2 = await ctx.prompt(
            f'{elite_line}{_NPC}: {_AP}Vell, {chosen.name} iz a vine specimen — '
            f'{price}s. Hokay?{_AP} (Y/N)'
        )
        if not raw2 or raw2.strip().upper() != 'Y':
            await ctx.send(f'{_NPC}: {_AP}Vell, too bad!{_AP}')
            continue

        player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        await ctx.send(
            f'{_AP}Yu hav {silver}s left.{_AP}'
        )
        player.unsaved_changes = True
        chosen.status = AllyStatus.SERVANT
        chosen.owner  = player.name
        # Strength +5 on hire (SPUR.BAR.S: a1=x2+5 — ally is emboldened by new contract)
        chosen.strength = chosen.strength + 5
        save_ally_roster(master_list)
        await player.party.add(ctx, player, chosen)
        await ctx.send(f'{_NPC}: {_AP}May {chosen.name} serve yu vell!{_AP}')

        available = _free_allies_for_sale(master_list, player)
        if not available or len(_owned_allies(player)) >= _MAX_ALLIES:
            return


# ---------------------------------------------------------------------------
# SELL  (t_bar_olaf.lbl :150 + SPUR.BAR.S sell)
#
# SPUR.BAR.S adds: Olaf pays you back at strength×50 (silver); won't buy
# "free spirits" (allies not purchased from him).  The honour penalty and
# "You wound me!" come from t_bar_olaf.lbl (2012 version).
# ---------------------------------------------------------------------------

async def _sell_servant(ctx: GameContext, master_list: List[Ally]) -> None:
    player   = ctx.player
    for_sale = _purchased_allies(player)

    if not for_sale:
        all_owned = _owned_allies(player)
        if all_owned:
            # Has allies but none are purchasable — free spirits only
            await ctx.send(
                f'{_NPC} eyes your companions and shakes his head. '
                f'{_AP}Olaf duz nut buy free spirits!{_AP}'
            )
        else:
            await ctx.send(
                f'{_NPC} looks around, puzzled. '
                f'{_AP}I dun{_AP}t see any teu sell!{_AP}'
            )
        return

    await ctx.send('Your current servants:')
    chosen = await pick_ally(
        ctx, for_sale, 'Sell which servant?',
        extra_fn=lambda a: f'(offer: {_ally_sellback(a)}s)',
        # invalid_msg=f'{_NPC}: {_AP}I tink yu must be drinking teu moch!{_AP}',
    )
    if chosen is None:
        await ctx.send(f'{_NPC} shrugs.')
        return
    others  = [a for a in _owned_allies(player) if a is not chosen]
    offer   = _ally_sellback(chosen)

    if others:
        other_names = ', '.join(a.name for a in others)
        await ctx.send(
            f'{other_names} look{"s" if len(others) == 1 else ""} relieved, while'
        )
    await ctx.send(f'{chosen.name} looks shocked. {_AP}Sir! You wound me!{_AP}')

    # Olaf makes his offer and asks for confirmation (SPUR.BAR.S)
    raw2 = await ctx.prompt(
        f'{_NPC}: {_AP}He dun{_AP}t look teu gud, but I gus I cun give yu {offer}s. '
        f'Hokay?{_AP} (Y/N)'
    )
    if not raw2 or raw2.strip().upper() != 'Y':
        await ctx.send(f'{_NPC}: {_AP}Hoh vell.{_AP}')
        return

    # Honour penalty (t_bar_olaf.lbl :141-142 — 2012 version: lose 50 if >= 50)
    if getattr(player, 'honor', 0) >= _HONOR_SELL_LOSS:
        player.honor -= _HONOR_SELL_LOSS
        await ctx.send(f'(You lose {_HONOR_SELL_LOSS} honour points.)')

    player.party.remove(chosen)
    chosen.status = AllyStatus.FREE
    chosen.owner  = None
    _sync_to_roster(master_list, chosen.name, AllyStatus.FREE, None, chosen.strength)
    player.subtract_silver(PlayerMoneyTypes.IN_HAND, -offer)   # negative = add silver
    player.unsaved_changes = True
    silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
    await ctx.send(
        f'{_NPC} nods. {_AP}Hokay vine! Dunkah.{_AP}  '
        f'(You now have {silver}s.)'
    )


# ---------------------------------------------------------------------------
# MAINTAIN  (SPUR.BAR.S maint — strengthens ally; honour +5)
#
# t_bar_olaf.lbl routes this to {:999} (end label) — never implemented there.
# SPUR.BAR.S has partial logic: reads new strength (x2), stores it back,
# gives +5 honour, prints "Olaf does something mysterious... DER!! NAOW IZ BEDDER!!"
# TADA fills in the cost and stat increase details.
# ---------------------------------------------------------------------------

async def _maintain_servant(ctx: GameContext, master_list: List[Ally]) -> None:
    player = ctx.player
    owned  = _purchased_allies(player)

    if not owned:
        if _owned_allies(player):
            await ctx.send(f'{_NPC} shrugs. {_AP}Olaf only strengthens servants he has sold!{_AP}')
        else:
            await ctx.send(f'{_NPC} shrugs. {_AP}Yu hav no servants to maintain!{_AP}')
        return

    await ctx.send('Servant condition:')
    chosen = await pick_ally(
        ctx, owned,
        f'{_NPC}: {_AP}Vich servant du yu vish to strengthen?{_AP}',
        extra_fn=lambda a: (f'HP: {a.hit_points}' if a.hit_points else 'HP: unknown')
                           + f'  (strengthen: {a.strength * _STRENGTHEN_BASE_COST}s)',
        # invalid_msg=f'{_NPC}: {_AP}Com com, 1 teu {{len(owned)}}! (Enter aborts){_AP}',
    )
    if chosen is None:
        await ctx.send(f'{_NPC} shrugs.')
        return
    cost   = chosen.strength * _STRENGTHEN_BASE_COST
    silver = player.get_silver(PlayerMoneyTypes.IN_HAND)

    raw2 = await ctx.prompt(
        f'{_NPC}: {_AP}Dat vill be {cost}s. Yu hav {silver}s. Hokay?{_AP} (Y/N)'
    )
    if not raw2 or raw2.strip().upper() != 'Y':
        await ctx.send(f'{_NPC} shrugs.')
        return

    if silver < cost:
        await ctx.send(
            f'{_NPC} shakes his head. {_AP}Yu can{_AP}t afford zat, friend.{_AP}'
        )
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost)
    # Strengthen (SPUR.BAR.S: updates x2 new-strength back into slot)
    gain = random.randint(1, 3)
    chosen.strength += gain
    _sync_to_roster(master_list, chosen.name, chosen.status, chosen.owner, chosen.strength)
    # Honour bonus for investing in servant (SPUR.BAR.S: vk=vk+5 if vk<2000)
    if getattr(player, 'honor', 0) < 2000:
        player.honor = getattr(player, 'honor', 0) + _HONOR_MAINTAIN_GAIN
    player.unsaved_changes = True

    await ctx.send([
        f'Olaf does something mysterious...',
        f'{_NPC}: {_AP}Der!! Naow iz bedder!!{_AP}',
        f'{chosen.name} gained {gain} strength (now {chosen.strength}).',
    ])


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    """Fat Olaf's Servant Trade interaction loop."""
    player = ctx.player

    master_list = load_allies()

    await ctx.send(f'The slave trader {_NPC} sits behind a table, gnawing a chicken leg.')
    await broadcast_area(ctx, 'bar', f'{player.name} sits down across from {_NPC}.')
    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send([
            f'{_NPC}: {_AP}I buy und sell servants yu can add tu your party!{_AP}',
            f'{_AP}They need tu be fed und paid on a veekly basis tu remain loyal tu yu!{_AP}',
        ])
        await _show_menu(ctx)

    while True:
        await ctx.send('')
        raw = await ctx.prompt(f'{_NPC}: {_AP}Vot kin I du ver ya?{_AP}')
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
            await ctx.send(f'"Hokey dokey." {_NPC} watches you leave.')
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from {_NPC}{_AP}s table.')
            break
        elif cmd in ('?', 'h'):
            await _show_menu(ctx)
        elif cmd == 'b':
            await _buy_servant(ctx, master_list)
        elif cmd == 's':
            await _sell_servant(ctx, master_list)
        elif cmd == 'm':
            await _maintain_servant(ctx, master_list)
        else:
            await ctx.send(f'{_NPC}: {_AP}Kud yu spek up, young{_AP}un?{_AP}')


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
    ctx.player.name = 'Rulan'
    ctx.player.hit_points = 20
    ctx.player.honor = 100
    ctx.player.party = Party()
    ctx.player.client_settings = MagicMock(return_key='Return')
    ctx.player.query_flag = lambda _: False
    ctx.player.get_silver = MagicMock(return_value=9999)
    ctx.player.subtract_silver = MagicMock(return_value=True)
    ctx.player.previous_command = None
    ctx.send = AsyncMock()

    answers = iter(['b', '1', 'y', 'm', '1', 'y', 's', '1', 'y', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print('Standalone fat_olaf test complete.')
