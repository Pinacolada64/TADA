"""logon_events/birthday.py — Birthday greeting login event.

Referenced but left unwritten by TODO.md's "Modular logon/logoff event
system" entry, which explicitly called this out as missing alongside
news/tip-of-the-day/once-per-day-reset (those three already live inline
in commands/connect.py). Picked as the first concrete logon_events/
module for exactly that reason -- it was already scoped, just never
built. Not part of a generalized auto-discovered package yet (see
TODO.md's open questions on that); commands/connect.py wires this one
module in directly, gated by config.birthday_greeting_enabled.

Both Verus's own wish and Vinny's cameo also broadcast to the room
(ctx.send_room(..., exclude_self=True), Ryan's request), so other
players nearby see something happen, not just the birthday player
themselves -- Verus's line is disembodied (he's a narrator, not a
physical NPC), Vinny's names him because he's actually standing there.

Vinny's cameo (Ryan's idea): bar/vinny.py's own entrance flavor text
already claims his name tag advertises him as "available for children's
parties" -- so on a birthday, he actually shows up. Brings a cake
(regardless of loan status) and, only if the player has an outstanding
loan, begrudgingly knocks 10% off it -- reuses bar/vinny.py's own
_gender_terms()/_NPC dialect helpers so his voice matches the bar scene,
rather than a second hand-rolled version of "youse"/"dis".
"""
from __future__ import annotations

import datetime
import math

_CAKE_ID = 9001  # deliberately outside objects.json's real range (max 165)
                 # -- not a catalog item, just a birthday keepsake; see
                 # _make_cake().
_LOAN_DISCOUNT_RATE = 0.10  # "some amount" (Ryan's own wording) -- modest,
                            # not a real bailout, matching "begrudgingly".


def is_birthday_today(player, today: datetime.date | None = None) -> bool:
    """Whether *today* (default: the real today) matches player.birthday's
    month/day -- year ignored, since a birthday recurs every year
    regardless of what year the character sheet says they were born.
    False if no birthday is on file at all.

    Single source of truth for "is it their birthday" -- shared by
    main() below and combat/resolution.py's monster_attacks() (birthday
    combat immunity, Ryan's request), so both stay in agreement instead
    of each hand-rolling the same month/day comparison."""
    birthday = getattr(player, 'birthday', None)
    if birthday is None:
        return False
    today = today or datetime.date.today()
    return (birthday.month, birthday.day) == (today.month, today.day)


async def main(ctx, player, today: datetime.date | None = None) -> list[str]:
    """Return birthday greeting lines if *today* (default: the real
    today) is player's birthday (see is_birthday_today()). Returns []
    otherwise.

    Async (unlike commands/connect.py's other sync _login_*_lines(ctx,
    player) helpers) because Vinny's cameo also broadcasts to the room
    via ctx.send_room() -- see _vinny_birthday_visit().
    """
    if not is_birthday_today(player, today):
        return []
    lines = [
        f"|yellow|*** Happy Birthday, {player.name}! ***|reset|",
        f"Verus says, \"Another year older, {player.name}? "
        "May your coffers stay full and your dice stay kind.\"",
        "",
    ]
    if ctx is not None:
        try:
            await ctx.send_room(
                f"Verus's voice echoes through the air: "
                f"\"Happy birthday, {player.name}!\"",
                exclude_self=True,
            )
        except AttributeError:
            pass  # ctx without send_room (e.g. a bare test double) -- skip quietly
    lines += await _vinny_birthday_visit(ctx, player)
    return lines


def _make_cake():
    from items import Item, ItemCategory
    return Item(
        id_number=_CAKE_ID,
        name='birthday cake',
        category=ItemCategory.ITEM,
        price=0,  # a keepsake, not merchandise -- Ye Olde Pawn Shoppe
                  # would (correctly) offer nothing for it.
    )


async def _vinny_birthday_visit(ctx, player) -> list[str]:
    """Vinny's cameo: hands over a birthday cake, and -- only if the
    player has an outstanding loan -- begrudgingly knocks
    _LOAN_DISCOUNT_RATE off it. Silver, not silence: he still grumbles
    either way. Also lets everyone else in the room see him show up
    (ctx.send_room()), same as any other in-room event -- this only
    works because commands/connect.py sets ctx.client.room *before*
    calling here; normally that doesn't happen until simple_server.py's
    _game_loop(), well after the login-lines block this runs in."""
    from bar.vinny import _NPC, _gender_terms

    hn, dl = _gender_terms(player)
    lines = [
        f"{_NPC} shoulders his way in, awkwardly holding a lopsided cake "
        f"with too many candles. 'Heard it was ya birthday, {hn}. "
        "Don't get used ta dis kinda thing.'",
    ]

    inv = getattr(player, 'inventory', None)
    if inv is not None and inv.add(_make_cake()):
        player.unsaved_changes = True
        lines.append("[You receive a birthday cake.]")
    else:
        lines.append(
            f"{_NPC} looks around at your full pockets and shrugs. "
            "'...guess I'll eat it myself, den.'"
        )

    loan = getattr(player, 'loan_amount', 0) or 0
    if loan > 0:
        discount = min(loan, max(1, math.floor(loan * _LOAN_DISCOUNT_RATE)))
        player.loan_amount = loan - discount
        if player.loan_amount == 0:
            player.loan_days = 0
        player.unsaved_changes = True
        lines.append(
            f"{_NPC} grumbles, '...an' since it's ya birthday, "
            f"I'm knockin' {discount:,}s off what youse owes me. "
            f"Don't say I never did nuttin' for youse, {dl}.' "
            f"[Loan now at {player.loan_amount:,}s.]"
        )

    lines.append("")

    if ctx is not None:
        try:
            await ctx.send_room(
                f"{_NPC} shoulders his way in, wishing {player.name} a happy "
                "birthday with a lopsided, too-many-candled cake.",
                exclude_self=True,
            )
        except AttributeError:
            pass  # ctx without send_room (e.g. a bare test double) -- skip quietly

    return lines
