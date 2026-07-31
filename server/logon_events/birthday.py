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

Fist party extension (Ryan's idea): after the cake, Vinny offers to throw
the player an actual party -- if they say yes, he snaps his fingers and
Mundo (bar/main.py's bouncer) appears to carry them bodily to the Fist
Guild's Tea Room (SPUR-data/level-1/level-1.json room 130, level 1,
"fist"-aligned) for a round of congratulations from the guild. This is a
*real* room move (ctx.client.room/player.map_room/player.map_level all
get temporarily repointed at the Tea Room, same fields
commands/teleport.py's own _teleport() sets) rather than just narration,
then moved back to wherever they started once the party's over -- see
_fist_birthday_party(). Doesn't invoke guild_hq/main.py's own interactive
HQ session (chalkboard/bank/lockers) though; this is a party, not a
Guild-services visit. Grants "Fist immunity" -- a narrated exception to
guild_hq/main.py's usual "you're not a member, get out" gate, not a call
into that gate's code -- if the player isn't actually Fist, mirroring
combat/resolution.py's birthday combat immunity (both are one-day
exceptions to a normal rule, not permanent state changes). Ends with a
500 silver birthday present, regardless of guild.

Mundo's three send_room() broadcasts (leaving, arriving, returning --
Ryan's request) all name the birthday player's whole party.py Party too
(allies/mounts), not just the player themselves -- see
_player_and_party_names() -- since Mundo hauling off the player but
leaving their allies standing there mid-conversation would look odd.
Possessive pronoun ("his/her party") comes from tada_utilities.
get_pronoun(), the same helper encounters/dwarf.py and ally_events/
starvation.py already use, rather than a flat "their".
"""
from __future__ import annotations

import datetime
import math
import random

_CAKE_ID = 9001  # deliberately outside objects.json's real range (max 165)
                 # -- not a catalog item, just a birthday keepsake; see
                 # _make_cake().
_LOAN_DISCOUNT_RATE = 0.10  # "some amount" (Ryan's own wording) -- modest,
                            # not a real bailout, matching "begrudgingly".
_PARTY_GIFT_SILVER = 500  # birthday present handed over by Mundo at the party.
_TEA_ROOM_LEVEL  = 1    # SPUR-data/level-1/level-1.json
_TEA_ROOM_NUMBER = 130  # "Tea Room", room_alignment "fist"

# Random flavor for the Fist Guild's congratulations -- sampled without
# replacement so a given party never repeats a line (matching the spirit
# of vinny.py's _ANNOYED_LINES pool, just guild-flavored instead).
_FIST_PARTY_LINES = [
    "A Fist member you don't recognize claps you on the back hard enough to stagger you.",
    "\"Happy birthday!\" someone shouts from across the room, raising a mug in salute.",
    "One of the guild members pulls you into a bone-crushing hug before you can protest.",
    "\"Another year, another target on your back,\" a grizzled Fist veteran laughs, "
    "slapping your shoulder.",
    "Someone starts a ragged chorus of \"Happy Birthday\" that trails off before the "
    "second verse.",
]


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


def _player_and_party_names(player) -> str:
    """"{player.name}" alone, or "{player.name} (and his/her party: X, Y)" if
    player.party (party.py's Party) has members -- Mundo doesn't leave
    anyone's allies/mounts behind when he drags them off (Ryan's request).
    Uses tada_utilities.get_pronoun() for the possessive, same helper
    encounters/dwarf.py and ally_events/starvation.py already use, rather
    than a flat "their" -- matches this codebase's existing gendered-
    pronoun convention instead of introducing a second one."""
    members = [getattr(m, 'name', str(m)) for m in (getattr(player, 'party', None) or [])]
    if not members:
        return player.name
    from tada_utilities import get_pronoun, PronounType
    possessive = get_pronoun(player, PronounType.POSSESSIVE_ADJECTIVE)
    return f"{player.name} (and {possessive} party: {', '.join(members)})"


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

    lines += await _fist_birthday_party(ctx, player, hn, dl)
    return lines


async def _fist_birthday_party(ctx, player, hn: str, dl: str) -> list[str]:
    """Vinny's follow-up offer: a real party at the Fist Guild's Tea Room.
    Requires ctx (there's no way to ask a yes/no question without
    ctx.prompt); returns [] untouched if ctx is None, or if the player
    declines.

    Physically relocates the player there and back (see module docstring)
    rather than just narrating it -- Ryan's explicit request. Broadcasts
    to both the room they're dragged out of and the Tea Room they land in
    (also Ryan's request), same as Vinny's own cameo above."""
    if ctx is None:
        return []

    from bar.vinny import _NPC

    raw = await ctx.prompt(f"{_NPC} eyes you. 'Wanna have a party, {hn}?' (Y/N)")
    if not raw or raw.strip().upper() != 'Y':
        return []

    lines = [
        f"{_NPC} grins and snaps his fingers.",
        "Mundo emerges from the shadows behind him, saying nothing.",
        "Before you can react, Mundo scoops you up like a sack of flour and "
        "carries you out the door.",
    ]

    try:
        await ctx.send_room(
            f"Mundo scoops {_player_and_party_names(player)} up and drags "
            "them off for parts unknown.",
            exclude_self=True,
        )
    except AttributeError:
        pass  # ctx without send_room (e.g. a bare test double) -- skip quietly

    # Actually move them there -- same fields commands/teleport.py's own
    # _teleport() sets, so this is a real (if temporary) relocation, not
    # just narration.
    client    = getattr(ctx, 'client', None)
    old_room  = getattr(client, 'room', None) if client is not None else None
    old_level = int(getattr(player, 'map_level', 1) or 1)

    if client is not None:
        client.room = _TEA_ROOM_NUMBER
    player.map_room  = _TEA_ROOM_NUMBER
    player.map_level = _TEA_ROOM_LEVEL
    if client is not None:
        try:
            client.map_level = _TEA_ROOM_LEVEL
        except Exception:
            pass

    lines += [
        "",
        "|yellow|-- The Tea Room, Fist Guild HQ --|reset|",
        "",
        "Mundo sets you down none too gently beside a small table crowded "
        "with mismatched chairs.",
    ]

    from base_classes import Guild
    if getattr(player, 'guild', None) != Guild.FIST:
        lines.append(
            "Normally a gruff guard would toss you out on your ear for "
            "setting foot on Fist turf uninvited -- tonight, with Mundo "
            "vouching for you, nobody so much as blinks."
        )

    lines += random.sample(_FIST_PARTY_LINES, k=min(2, len(_FIST_PARTY_LINES)))

    from base_classes import PlayerMoneyTypes
    player.subtract_silver(PlayerMoneyTypes.IN_HAND, -_PARTY_GIFT_SILVER)
    player.unsaved_changes = True
    lines.append(
        f"Mundo grunts and presses a small purse into your hands. "
        f"[You receive {_PARTY_GIFT_SILVER:,} silver as a birthday present.]"
    )

    try:
        await ctx.send_room(
            f"Mundo drags {_player_and_party_names(player)} in and drops "
            "them by the table -- another birthday party, apparently.",
            exclude_self=True,
        )
    except AttributeError:
        pass  # ctx without send_room (e.g. a bare test double) -- skip quietly

    lines.append("")
    lines.append(
        "Just as suddenly, Mundo scoops you up again and hauls you back to "
        "where he found you."
    )

    # ...and back again.
    if client is not None:
        client.room = old_room
    player.map_room  = old_room
    player.map_level = old_level
    if client is not None:
        try:
            client.map_level = old_level
        except Exception:
            pass

    try:
        await ctx.send_room(
            f"Mundo drags {_player_and_party_names(player)} back off for "
            "parts unknown, then reappears without them a moment later.",
            exclude_self=True,
        )
    except AttributeError:
        pass  # ctx without send_room (e.g. a bare test double) -- skip quietly

    lines.append("")
    return lines
