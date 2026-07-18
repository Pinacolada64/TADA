"""commands/pray.py — PRAY: beg the Spirit of the Dungeons for a boost.

SPUR.MISC2.S's "pray" subroutine. A player who's genuinely low on hit
points, Strength, or Energy can pray for a small top-up -- once per
session (twice for Druids and Paladins). Pray when you're not actually
in need, or push your luck past the once-per-session limit, and you get
a snarky refusal instead -- or, if you keep pestering after being
warned, a fatal lightning bolt.

Variable mapping (programming-notes/spur variables.txt is the authority
here -- an earlier draft of this file guessed ps/pe were food/drink
based on an unrelated hunger-message section in SPUR.MAIN.S that happens
to reuse those same two letters for a different purpose):
    hp = hit_points        pe = PlayerStat.EGY (Energy)
    ps = PlayerStat.STR    pt = PlayerStat.CON (Constitution)

Mechanics ported:
  - A 0-9 roll (SPUR: random(10)-3, so -3..6) adjusted by honor (-1 under
    800, another -1 under 400; +1 over 1200, another +2 over 1600 -- SPUR
    literally reads "if xy>1600 xy=xy+2", but xy never gets anywhere near
    1600 (it's a single-digit roll) -- this is a transcription typo for
    "if vk>1600", corrected here) and class (Druid +2, Paladin +1).
  - If the roll is still below hit_points, Strength, AND Energy (i.e.
    nothing is actually critically low), the prayer is declined with one
    of several random SPUR flavor lines (harsher/nicer variants by
    honor).
  - Otherwise, if the once-per-session allowance isn't used up, the
    Spirit grants a boost: hit_points gets +10, Strength/Energy/
    Constitution each get +1, if a second roll (6-10) beats their
    current value. Logged to battle.log as "PRAY" (or "PIOUS PRAY" for
    a Druid/Paladin's second prayer of the session).
  - If you're in need but carrying unused rations -- any ration item
    other than four specific special-effect potions/pills (RED SERUM
    #44, BLUE PILL #45, POTION OF SKILL #65, CHARM POTION #68, none of
    which are real sustenance) -- the Spirit refuses to help and tells
    you to eat/drink what you're already carrying first
    (SPUR.MISC2.S:207-211's xf/xf$ check: xf is the ration count in
    inventory, xf$ the packed item codes; the four exemptions don't
    count against you, but if you're carrying anything else edible
    you're just being lazy).
  - Pray again after the allowance is exhausted and you get ONE warning
    ("Buggest me oncest more and thou art toast!"); the NEXT prayer
    after that warning is instant death by lightning bolt.

New in TADA simplifications:
  - hit_points is tracked on this codebase's 0-100+ scale, matching
    SPUR's own +10 grant. Strength/Energy/Constitution are 1-18 D&D-
    scale attributes here (PlayerStat), not the larger vitality-gauge
    scale SPUR's hp/ps/pe/pt share -- boosting them by +10 would blow
    past their normal range, so this port scales those three grants down
    to +1 instead (Ryan's call).
  - The once-per-session limit is tracked as transient per-session
    counters (player.prayed_count/player.prayer_punished), not persisted
    -- same pattern as player.last_examined (EXAMINE) and
    player.loot_count (LOOT), mirroring SPUR's own ys$ flag string
    which resets each login too.
"""
import logging
import random

from base_classes import PlayerClass, PlayerStat
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext

log = logging.getLogger(__name__)

_HONOR_LOW         = 800
_HONOR_VERY_LOW    = 400
_HONOR_LOW_REJECT  = 700   # below this, prayer is flatly refused ("Cooties!")
_HONOR_HIGH        = 1200
_HONOR_VERY_HIGH   = 1600

_DOUBLE_PRAYER_CLASSES = (PlayerClass.DRUID, PlayerClass.PALADIN)

_HP_BOOST_AMOUNT       = 10
_STAT_BOOST_AMOUNT     = 1   # Strength/Energy/Constitution -- see module docstring
_NOT_IN_NEED_THRESHOLD = 7   # SPUR.MISC2.S:236: hp>7, ps(STR)>7, pe(EGY)>7

# RED SERUM/BLUE PILL/POTION OF SKILL/CHARM POTION -- special-effect
# potions/pills, not real sustenance, so carrying them doesn't count
# against the "you have unused rations" check (SPUR.MISC2.S:208-211).
_EXEMPT_RATION_IDS = {44, 45, 65, 68}


def _has_unused_rations(player) -> bool:
    """True if the player is carrying a ration item (food or drink, any
    id_number not in _EXEMPT_RATION_IDS) they haven't been eating/
    drinking. SPUR.MISC2.S:207-211's xf/xf$ check."""
    from items import ItemCategory
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return False
    for entry in inv.entries():
        item = entry.item
        if getattr(item, 'category', None) not in (ItemCategory.FOOD, ItemCategory.DRINK):
            continue
        if getattr(item, 'id_number', None) in _EXEMPT_RATION_IDS:
            continue
        return True
    return False


def _need_roll(player) -> int:
    """The "are you actually in need" roll (SPUR.MISC2.S:199-203)."""
    xy = random.randint(0, 9) - 3
    honor = int(getattr(player, 'honor', 0) or 0)
    if honor < _HONOR_LOW:
        xy -= 1
    if honor < _HONOR_VERY_LOW:
        xy -= 2
    if honor > _HONOR_HIGH:
        xy += 1
    if honor > _HONOR_VERY_HIGH:
        xy += 2
    return xy


def _rejection_line(player, str_stat: int, egy_stat: int) -> str:
    """One of SPUR's random "you're not really in need" refusals
    (SPUR.MISC2.S:233-243), honor-flavored."""
    honor = int(getattr(player, 'honor', 0) or 0)
    hp    = int(getattr(player, 'hit_points', 0) or 0)

    if hp > _NOT_IN_NEED_THRESHOLD and str_stat > _NOT_IN_NEED_THRESHOLD and egy_stat > _NOT_IN_NEED_THRESHOLD:
        if honor > _HONOR_HIGH:
            return "'Thou TRULY dost not need my help now.'"
        return "'Thou art not in need! Dost not buggest me further!'"

    xy = random.randint(0, 10)
    if xy > 8:
        line = ("'God helps those who help themselves...'" if honor > _HONOR_HIGH else
                "A voice whispers in your ear: 'Namby pamby weenie...'")
    elif xy > 5:
        line = ("'Thou really should try to be self-reliant..'" if honor > _HONOR_HIGH else
                "'What ameth I? Thou's mama?!'")
    elif xy > 2:
        line = ("'Perhaps after I finish this task...'" if honor > _HONOR_HIGH else
                "'Notest now, I ameth busy!'")
    else:
        line = ("'Perhaps after I finish lunch...'" if honor > _HONOR_HIGH else
                "'Canst thou not see i am on lunch break?!'")

    if honor < _HONOR_LOW_REJECT:
        return "'Arggh!! Cooties! Get AWAY!'"
    return line


class PrayCommand(Command):
    name    = 'pray'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Beg the Spirit of the Dungeons for a boost.',
        description = (
            'When you are genuinely low on hit points, Strength, or '
            'Energy, PRAY has a chance to grant a small boost -- once '
            'per session (twice for Druids and Paladins). Pray when '
            "you're not in need, or push your luck too far, and the "
            'Spirit is not amused.'
        ),
        category = HelpCategory.GENERAL,
        usage    = [
            ('pray', 'Ask the Spirit of the Dungeons for help.'),
        ],
        examples = [
            ('pray', 'Try your luck when things are looking grim.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        import net_common
        self.parse_args(*args)
        player = ctx.player

        await ctx.send(["", "Thunder rumbles overhead and a vision appears...", ""])

        if getattr(player, 'prayer_punished', False):
            await ctx.send([
                "FOOL!!! Did I not WARN you?!",
                "",
                "You vaguely remember something about",
                '"toast" as you are fried with a huge',
                "lightning bolt, and sizzle to a golden",
                "brown...",
            ])
            player.hit_points = 0
            player.unsaved_changes = True
            net_common.append_battle_log(f'{player.name} was FRIED for pestering the Spirit of the Dungeons.')
            return CommandResult.ok()

        hp         = int(getattr(player, 'hit_points', 0) or 0)
        str_stat   = int(player.stats.get(PlayerStat.STR, 0) or 0)
        egy_stat   = int(player.stats.get(PlayerStat.EGY, 0) or 0)
        char_class = getattr(player, 'char_class', None)

        xy = _need_roll(player)
        if char_class == PlayerClass.DRUID:
            xy += 2
            await ctx.send('(Druid: +20% success)')
        elif char_class == PlayerClass.PALADIN:
            xy += 1
            await ctx.send('(Paladin: +10% success)')

        if xy < hp and xy < str_stat and xy < egy_stat:
            await ctx.send(_rejection_line(player, str_stat, egy_stat))
            return CommandResult.ok()

        if _has_unused_rations(player):
            await ctx.send([
                "'Thou should eateth or drinketh something.",
                "Thou must be a tad slow.'",
            ])
            return CommandResult.ok()

        prayed_count = getattr(player, 'prayed_count', 0)
        allowed      = 2 if char_class in _DOUBLE_PRAYER_CLASSES else 1
        if prayed_count >= allowed:
            await ctx.send([
                "'I have already helped thee today!",
                "Buggest me oncest more and thou art toast!'",
            ])
            player.prayer_punished = True
            return CommandResult.ok()

        await ctx.send("'Oh, very well... here is a little help!'")
        boost_roll = random.randint(6, 10)
        if boost_roll > hp:
            player.hit_points = hp + _HP_BOOST_AMOUNT
            await ctx.send('(Your hit points increase.)')
        if boost_roll > str_stat:
            player.stats[PlayerStat.STR] = str_stat + _STAT_BOOST_AMOUNT
            await ctx.send('(Your hunger lessens.)')
        if boost_roll > egy_stat:
            player.stats[PlayerStat.EGY] = egy_stat + _STAT_BOOST_AMOUNT
            await ctx.send('(Your thirst lessens.)')
        con = int(player.stats.get(PlayerStat.CON, 0) or 0)
        if boost_roll > con:
            player.stats[PlayerStat.CON] = con + _STAT_BOOST_AMOUNT
            await ctx.send('(You feel healthier.)')
        await ctx.send("'Now runnest thee along.'")

        is_pious = prayed_count > 0  # this is a Druid/Paladin's second prayer
        if is_pious:
            await ctx.send('(Your kind may pray twice!)')
        player.prayed_count = prayed_count + 1
        player.unsaved_changes = True

        tag = 'PIOUS PRAY' if is_pious else 'PRAY'
        net_common.append_battle_log(f'{player.name} - {tag}: The Spirit of the Dungeons helped {player.name}.')

        return CommandResult.ok()
