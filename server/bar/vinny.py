"""bar/vinny.py — Vinny the Loan Shark / banker.

Ported from t_bar_vinney.lbl and SPUR.BAR3.S.

SPUR notes:
  - Max outstanding loan: 5,000 silver.
  - Loans carry a 4/3 repayment ratio (you repay ~133% of what you borrow).
  - Max stored in bar: 5,000 silver (PlayerMoneyTypes.IN_BAR).
  - Minimum payment: 1,000s, or the full loan if less than that.
  - Gender-based address: female → 'honey'/'doll', male → 'weasel'/'mac'.
  - Loan tracked on player: loan_amount (silver owed), loan_days (days left).
"""
import logging
import math
from typing import Tuple

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from network_context import GameContext
from presence import broadcast_area

log = logging.getLogger(__name__)

_NPC      = "Vinny"
_AP       = "'"
_MAX_LOAN = 5_000     # max new + outstanding combined (SPUR.BAR3.S)
_MAX_STORED = 5_000   # max silver Vinny will hold for you (SPUR.BAR3.S)
_LOAN_RATE  = 4 / 3   # repayment is 133% of principal (SPUR.BAR3.S borrow logic)
_MIN_PAYMENT = 1_000  # minimum partial payment (SPUR.BAR3.S)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gender_terms(player) -> Tuple[str, str]:
    """Return (familiar, address) based on player gender.

    t_bar_vinney.lbl: female → 'honey'/'doll'; male → 'weasel'/'mac'.
    """
    try:
        from characters import Gender
        if getattr(player, 'gender', None) == Gender.FEMALE:
            return 'honey', 'doll'
    except Exception:
        pass
    return 'weasel', 'mac'


async def _show_menu(ctx: GameContext) -> None:
    rk = ctx.player.client_settings.return_key
    await ctx.send([
        '',
        f'  [A] Apply for a loan',
        f'  [C] Clown around',
        f'  [G] Get stored money (withdraw)',
        f'  [P] Pay off current loan',
        f'  [R] Review terms of agreement',
        f'  [S] Store money in bar (deposit)',
        f'  [L] / [{rk}]: Leave',
        '',
    ])


async def _review_terms(ctx: GameContext, hn: str) -> None:
    """R — review loan and account balances (SPUR.BAR3.S review)."""
    player  = ctx.player
    in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
    in_bar  = player.get_silver(PlayerMoneyTypes.IN_BAR)
    loan    = player.loan_amount
    days    = player.loan_days

    lines = ['', f'{_NPC}{_AP}s books:', '']
    lines.append(f'  Silver in hand  : {in_hand:>8,}s')
    lines.append(f'  Stored in bar   : {in_bar:>8,}s')
    if loan:
        daily = math.ceil(loan / max(days, 1)) if days else loan
        lines.append(f'  Loan outstanding: {loan:>8,}s')
        if days:
            lines.append(f'  Days to repay   : {days:>8}')
            lines.append(f'  ~Daily payment  : {daily:>8,}s')
        else:
            lines.append(f'  DUE TODAY')
    else:
        lines.append(f'  Loan            :     none')
    lines.append('')
    await ctx.send(lines)


async def _apply_loan(ctx: GameContext, hn: str, dl: str) -> None:
    """A — apply for a new loan (t_bar_vinney.lbl :apply_loan / SPUR.BAR3.S borrow)."""
    player   = ctx.player
    existing = player.loan_amount

    if existing >= _MAX_LOAN:
        await ctx.send(
            f'{_NPC} growls. {_AP}Heck no! Youse got too much outstanding gold ta '
            f'suit me. Pay some of it back foist, youse dirty {hn}!{_AP}'
        )
        return

    headroom = _MAX_LOAN - existing
    if existing:
        await ctx.send(
            f'{_NPC} looks disgusted. {_AP}Another loan? '
            f'Youse borrowed less den {_MAX_LOAN:,}s an{_AP} '
            f'I{_AP}m such a nice guy, I{_AP}ll let youse have dis extra gold. '
            f'But if youse fail ta pay...{_AP} '
            f'His voice trails off as he raises a ham-like fist menacingly.'
        )
    else:
        await ctx.send(
            f'{_NPC} leans forward. {_AP}Psst, wanna loan, {hn}? '
            f'I can let youse have up to {headroom:,}s wit{_AP} my blessing.{_AP}'
        )

    raw = await ctx.prompt(
        f'How much? (1–{headroom:,}, Enter to cancel)'
    )
    if not raw or not raw.strip():
        await ctx.send(f'{_NPC} looks offended. {_AP}What? Was it sometin{_AP} I said?{_AP}')
        return

    try:
        amount = int(raw.strip().replace(',', ''))
        if not (1 <= amount <= headroom):
            raise ValueError
    except ValueError:
        await ctx.send(f'{_NPC} smirks. {_AP}Nice try, {hn}...{_AP}')
        return

    # Repayment at 133% (SPUR.BAR3.S: g1*4/3)
    total_owed = existing + math.ceil(amount * _LOAN_RATE)
    weeks      = max(1, math.ceil(amount / 1000))
    days       = weeks * 7
    daily      = math.ceil(total_owed / days)

    await ctx.send(
        f'{_NPC}: {_AP}Youse got {days} days ta pay off dis loan '
        f'atta average of {daily:,}s a day, or else!{_AP}'
    )

    raw2 = await ctx.prompt(f'Can youse handle dis, {hn}? (Y/N)')
    if not raw2 or raw2.strip().upper() != 'Y':
        await ctx.send(f'{_NPC} smirks. {_AP}Hah. Thought not.{_AP}')
        return

    player.loan_amount = total_owed
    player.loan_days   = days
    player.subtract_silver(PlayerMoneyTypes.IN_HAND, -amount)   # negative = add
    player.unsaved_changes = True
    in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
    await ctx.send(
        f'{_NPC} forks over the gold. '
        f'(You now have {in_hand:,}s in hand.)'
    )


async def _pay_loan(ctx: GameContext, hn: str, dl: str) -> None:
    """P — pay down the outstanding loan (t_bar_vinney.lbl :200 / SPUR.BAR3.S pay)."""
    player  = ctx.player
    loan    = player.loan_amount
    in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)

    if not loan:
        await ctx.send(f'{_NPC}: {_AP}Youse don{_AP}t owe nuttin{_AP}!{_AP}')
        return

    if not in_hand:
        await ctx.send(f'{_NPC} grins. {_AP}Yer broke, dummy!{_AP}')
        return

    await ctx.send(
        f'{_NPC} breaks into a smile. {_AP}Come ta pay da ol{_AP} man back, '
        f'have youse? As long as youse make yer payments on time, '
        f'we take good care of youse here.{_AP}'
    )

    min_pay = min(_MIN_PAYMENT, loan)
    lines = ['',
             f'  Silver in hand  : {in_hand:>8,}s',
             f'  Loan outstanding: {loan:>8,}s',
             f'  Minimum payment : {min_pay:>8,}s',
             '',
             f'  [Enter] to cancel  |  A = pay all  |  or enter an amount',
             '']
    await ctx.send(lines)

    raw = await ctx.prompt('Pay how much')
    if not raw or not raw.strip():
        await ctx.send(f'{_NPC} shrugs.')
        return

    if raw.strip().lower() == 'a':
        amount = loan
    else:
        try:
            amount = int(raw.strip().replace(',', ''))
        except ValueError:
            await ctx.send(f'{_NPC} scowls. {_AP}Huh?{_AP}')
            return

    if amount > loan:
        # Overpayment — Vinny quietly returns the excess (t_bar_vinney.lbl :230 comment)
        excess  = amount - loan
        amount  = loan
        await ctx.send(
            f'{_NPC} stabs his finger at the paper, then leans in and whispers, '
            f'{_AP}Look, uh... dis is just between youse an{_AP} me, but...{_AP} '
            f'he shoves {excess:,}s back. {_AP}Youse don{_AP} hafta pay me all dis. '
            f'Dis is our secret, ok?{_AP}'
        )

    if amount < min_pay and amount < loan:
        await ctx.send(
            f'{_NPC} shakes his head. {_AP}Minimum payment is {min_pay:,}s!{_AP}'
        )
        return

    if in_hand < amount:
        await ctx.send(f'{_NPC}: {_AP}You don{_AP}t have that much!{_AP}')
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, amount)
    player.loan_amount = max(0, loan - amount)
    if player.loan_amount == 0:
        player.loan_days = 0
        await ctx.send(
            f'[Loan is now paid in full.]\n'
            f'{_NPC} looks startled. {_AP}Pleasure doing business with you, {dl}.{_AP}'
        )
    else:
        await ctx.send(
            f'Paid. [Loan now at {player.loan_amount:,}s.]'
        )
    player.unsaved_changes = True


async def _store_money(ctx: GameContext, dl: str) -> None:
    """S — deposit silver with Vinny (t_bar_vinney.lbl :400 / SPUR.BAR3.S save)."""
    player  = ctx.player
    in_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
    in_bar  = player.get_silver(PlayerMoneyTypes.IN_BAR)
    room    = _MAX_STORED - in_bar

    if not in_hand:
        await ctx.send(f'{_NPC}: {_AP}Yer broke, dummy!{_AP}')
        return

    if room <= 0:
        await ctx.send(
            f'{_NPC} shakes his head. {_AP}5,000s max, {dl}!{_AP}'
        )
        return

    await ctx.send(
        f'{_NPC}: {_AP}Wanna store some of yer gold here, {dl}?{_AP}'
    )

    can_store = min(in_hand, room)
    lines = ['',
             f'  Silver in hand  : {in_hand:>8,}s',
             f'  Already stored  : {in_bar:>8,}s',
             f'  Can deposit max : {can_store:>8,}s',
             '',
             f'  [Enter] to cancel  |  A = all  |  or enter an amount',
             '']
    await ctx.send(lines)

    raw = await ctx.prompt('Deposit how much')
    if not raw or not raw.strip():
        await ctx.send(f'Okay, fine wit{_AP} me...{_AP} he shrugs.')
        return

    if raw.strip().lower() == 'a':
        amount = can_store
    else:
        try:
            amount = int(raw.strip().replace(',', ''))
        except ValueError:
            await ctx.send(f'{_NPC} glares. {_AP}Hey!{_AP}')
            return

    if amount < 1 or amount > can_store:
        await ctx.send(f'{_NPC} glares. {_AP}Hey!{_AP}')
        return

    player.subtract_silver(PlayerMoneyTypes.IN_HAND, amount)
    player.subtract_silver(PlayerMoneyTypes.IN_BAR, -amount)
    player.unsaved_changes = True
    new_total = player.get_silver(PlayerMoneyTypes.IN_BAR)
    await ctx.send(f'Deposited. [Total stored is now {new_total:,}s.]')


async def _get_money(ctx: GameContext, dl: str) -> None:
    """G — withdraw stored silver (t_bar_vinney.lbl :get_gold / SPUR.BAR3.S withdraw)."""
    player = ctx.player
    in_bar = player.get_silver(PlayerMoneyTypes.IN_BAR)

    if not in_bar:
        await ctx.send(f'{_NPC} frowns. {_AP}Youse don{_AP}t have nuttin stored here, {dl}.{_AP}')
        return

    lines = ['',
             f'  Stored in bar   : {in_bar:>8,}s',
             '',
             f'  [Enter] to cancel  |  A = all  |  or enter an amount',
             '']
    await ctx.send(lines)

    raw = await ctx.prompt('Withdraw how much')
    if not raw or not raw.strip():
        await ctx.send(f'{_NPC} shrugs.')
        return

    if raw.strip().lower() == 'a':
        amount = in_bar
    else:
        try:
            amount = int(raw.strip().replace(',', ''))
        except ValueError:
            await ctx.send(f'{_NPC} inspects his bat menacingly.')
            return

    if amount < 1 or amount > in_bar:
        await ctx.send(f'{_NPC} inspects his bat menacingly.')
        return

    player.subtract_silver(PlayerMoneyTypes.IN_BAR, amount)
    player.subtract_silver(PlayerMoneyTypes.IN_HAND, -amount)
    player.unsaved_changes = True
    remaining = player.get_silver(PlayerMoneyTypes.IN_BAR)
    in_hand   = player.get_silver(PlayerMoneyTypes.IN_HAND)
    await ctx.send(
        f'Withdrawn. [Stored: {remaining:,}s  |  In hand: {in_hand:,}s]'
    )


async def _clown_around(ctx: GameContext, hn: str, dl: str) -> None:
    """C — clown around with Vinny (t_bar_vinney.lbl :clown_around).

    If female, Vinny flirts; if male, he's business-first.
    TODO: add balloon animal to inventory (t_bar_vinney.lbl :78-79).
    """
    if dl == 'doll':
        await ctx.send(
            f'{_NPC} comes out from behind his table, wiggling his eyebrows. '
            f'{_AP}I wouldn{_AP}t mind clownin{_AP} around wit{_AP} youse, {dl}, but...{_AP} '
            f'He sighs and sits again. {_AP}Business before pleasure, as they say.{_AP}'
        )
    else:
        await ctx.send(
            f'{_NPC} looks up from his ledger, unamused. '
            f'{_AP}Youse come here ta clown around, {dl}? I{_AP}m a busy man.{_AP}'
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    """Vinny the Loan Shark interaction loop."""
    player = ctx.player
    hn, dl = _gender_terms(player)

    await broadcast_area(ctx, 'bar', f'{player.name} walks up to Vinny{_AP}s table.')

    # Vinny's entrance (t_bar_vinney.lbl :start)
    await ctx.send([
        f'Your vision is filled with a very large man, with broad shoulders '
        f'the size of a good-sized draft horse. He{_AP}s got the biggest hands '
        f'and bushiest eyebrows you{_AP}ve ever seen. A plastic name tag '
        f'mentions his name is Vinney, and that he{_AP}s... available for '
        f'children{_AP}s parties?',
        '',
    ])

    if dl == 'doll':
        await ctx.send(f'{_NPC} leers. {_AP}Heya, sweet thing.{_AP}')
    await ctx.send(
        f'He looks at you suspiciously through a cloud of cigar smoke...'
    )

    # Greet based on loan status (t_bar_vinney.lbl :check_loan)
    loan = player.loan_amount
    days = player.loan_days
    if loan:
        if days == 0:
            await ctx.send(
                f'{_NPC} rasps, {_AP}Got my money, {hn}? '
                f'You owe me {loan:,}s, payable today. '
                f'Cough up da dough, {dl}!{_AP}'
            )
        else:
            await ctx.send(
                f'{_NPC} rasps, {_AP}Got my money, {hn}? '
                f'You owe me {loan:,}s, payable in {days} day{"s" if days != 1 else ""}. '
                f'Cough up da dough, {dl}!{_AP}'
            )

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await _show_menu(ctx)

    while True:
        await ctx.send('')
        raw = await ctx.prompt(f'{_NPC}: {_AP}Whaddya need, {hn}?{_AP}')
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
            if dl == 'doll':
                await ctx.send(f'{_NPC} looks a bit sad to see you go.')
            else:
                await ctx.send(f'{_NPC} nods. {_AP}Later, {dl}.{_AP}')
            await broadcast_area(ctx, 'bar', f'{player.name} leaves Vinny{_AP}s table.')
            break
        elif cmd in ('?', 'h'):
            await _show_menu(ctx)
        elif cmd == 'r':
            await _review_terms(ctx, hn)
        elif cmd == 'a':
            await _apply_loan(ctx, hn, dl)
        elif cmd == 'p':
            await _pay_loan(ctx, hn, dl)
        elif cmd == 's':
            await _store_money(ctx, dl)
        elif cmd == 'g':
            await _get_money(ctx, dl)
        elif cmd == 'c':
            await _clown_around(ctx, hn, dl)
        else:
            await ctx.send(
                f'{_NPC} glares. {_AP}Look, {hn}, knock it off. '
                f'Just stick wit{_AP} da choices. '
                f'We{_AP}ll both be so much happier that way, '
                f'youse know what I mean...?{_AP}'
            )


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
    ctx.player.name          = 'Rulan'
    ctx.player.loan_amount   = 0
    ctx.player.loan_days     = 0
    ctx.player.unsaved_changes = False
    ctx.player.client_settings = MagicMock(return_key='Return')
    ctx.player.query_flag    = lambda _: False
    ctx.player.previous_command = None

    _wallet = {PlayerMoneyTypes.IN_HAND: 3000,
               PlayerMoneyTypes.IN_BAR:  0}
    ctx.player.get_silver    = lambda k: _wallet.get(k, 0)
    ctx.player.subtract_silver = lambda k, amt: _wallet.update({k: _wallet.get(k, 0) - amt})
    ctx.send  = AsyncMock()

    answers = iter(['r', 'a', '500', 'y', 'r', 's', '200', 'g', 'a', 'p', 'a', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print('Standalone Vinny test complete.')
