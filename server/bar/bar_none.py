"""bar/bar_none.py — Bar None: drinks and food at the Wall Bar & Grill.

Two bartenders work different shifts:
  Mae  (day):   06:00–19:59  — food and drink menu
  Guss (night): 20:00–05:59  — talk, coin flip, blackjack

Guss ported from SPUR.BAR2.S (blackjack section ver. 1.4 by K. Echstenkamper).

SPUR notes (Guss):
  - Entry: "HAAY... DUDE! Like wats happenin?"  Leave: "Later... dude!"
  - T)alk: free-form chat with word-level keyword detection (SPUR: chat.chk).
  - F)lip: coin flip, max 1,000s bet (SPUR: flip section).
  - B)lackjack: full game, 500s table limit, H)it / D)ouble / S)tand.
    Dealer (Guss) stands on 17+; Aces count 11 or 1.
  - Guss's slang: "Most henious", "Most bogus", "Tubuler!", "Radical!",
    "Most excellent!", "Bogus!" (mirroring SPUR dialog verbatim).
"""
import datetime
import logging
import random
from typing import Optional

from bar.ally_data import Ally
from bar.main import food_menu
from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from items import Rations
from network_context import GameContext
from presence import broadcast_area
from tada_utilities import get_pronoun, PronounType, get_article_and_quantity, tip

log = logging.getLogger(__name__)

_NPC = "Mae"
_AP  = "'"


# ---------------------------------------------------------------------------
# Bartender class
# ---------------------------------------------------------------------------

class Bartender(Ally):
    def __init__(self, name, gender, strength, to_hit, flags):
        super().__init__(name, gender, strength, to_hit, flags)
        self.greetings = [
            "Can't just stand there. What'll it be?",
            "Fresh off the road? You look it. Name your poison.",
            f"The name's {self.name}. The bottles are dusty, but the ale is cold. What do you want?",
            "Find a seat, or don't. Just tell me what you're drinkin'.",
            "Another soul wanders in. Let's get you something to forget why.",
            "I've got everything from 'cheap and nasty' to 'top shelf and dusty'. Your call.",
        ]

    def random_greeting(self):
        return f'The bartender says, "{random.choice(self.greetings)}"'


# ---------------------------------------------------------------------------
# Shift selection
# ---------------------------------------------------------------------------

def _is_guss_shift() -> bool:
    """Guss works evenings and nights (20:00 – 05:59); Mae works days (06:00 – 19:59)."""
    hour = datetime.datetime.now().hour
    return hour >= 20 or hour < 6


# ---------------------------------------------------------------------------
# Mae — food/drink menu
# ---------------------------------------------------------------------------

async def _bar_none_menu(ctx: GameContext, displayed_items: list) -> None:
    lines = ["Menu:", ""]
    for i, item in enumerate(displayed_items, 1):
        lines.append(f"  {i:>2}. {item.name.title():<20} {item.price:>3} silver")
    lines.append("")
    lines.append(f"[L]ist, [X]pert mode, or select 1-{len(displayed_items)}")
    await ctx.send(lines)


async def _mae_session(ctx: GameContext, mae: Bartender) -> None:
    """Mae's interaction loop: food and drink menu."""
    player = ctx.player

    foodstuffs     = Rations.read_rations("../rations.json") or []
    displayed_items = food_menu(player, foodstuffs)
    log.debug("Displayed items: %i", len(displayed_items))
    await _bar_none_menu(ctx, displayed_items)
    await broadcast_area(ctx, 'bar', f'{player.name} pulls up a stool at {mae.name}{_AP}s bar.')

    while True:
        raw = await ctx.prompt(f"1-{len(displayed_items)}, [L]ist, [X]pert")
        if raw is None:
            await ctx.send(f'{mae.name} nods as you head for the door. "See you around."')
            break

        menu_item = raw.strip()
        if not menu_item:
            await ctx.send(f'{mae.name} nods as you head for the door. "See you around."')
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from the bar.')
            break

        if menu_item.lower() in ('?', 'l', 'list'):
            displayed_items = food_menu(player, foodstuffs)
            await _bar_none_menu(ctx, displayed_items)
            continue

        if menu_item.lower() == 'x':
            player.toggle_flag(PlayerFlags.EXPERT_MODE, True)
            continue

        try:
            item_num = int(menu_item)
            if 1 <= item_num <= len(displayed_items):
                selected_item = displayed_items[item_num - 1]
                if player.subtract_silver(PlayerMoneyTypes.IN_HAND, selected_item.price):
                    await ctx.send(
                        f"You slide a few coins across the bar for "
                        f"{get_article_and_quantity(selected_item.name.title())}."
                    )
                else:
                    await ctx.send(
                        f'{mae.name} shakes {get_pronoun(mae, PronounType.SUBJECTIVE)} '
                        f'head. "Looks as if that{_AP}s too rich for your blood..."'
                    )
            else:
                responses = [
                    'Please read carefully, since our menu items have recently changed in order to better serve you.',
                    'Please continue to peruse the menu, as your order is very important to us.',
                    f"Sorry, hon, I don{_AP}t have anything for number {item_num} on my list.",
                ]
                await ctx.send(f'Mae says, "{random.choice(responses)}"')

        except ValueError:
            await ctx.send(f'{mae.name} says, "Well, that{_AP}s an odd menu selection..."')


# ---------------------------------------------------------------------------
# Guss — talk
# ---------------------------------------------------------------------------

# SPUR.BAR2.S chat.chk keyword groups (word-level scan)
_PROFANITY   = {"SHIT", "FUCK", "ASS", "HOLE", "CUNT"}
_QUESTION_WH = {"HOW", "WHY", "WHERE", "WHAT", "WHEN", "WHO"}
_INSULTS     = {"SHUTUP", "JERK", "KISS", "KICK", "KILL", "HIT", "BEAT", "GEEK", "UGLY"}
_LORE        = {"DURA", "SPUR", "LAND", "MONSTER", "AMULET"}
_MYSTERY     = {"RING", "EXCALIBUR", "GUILD", "EVIL", "GOOD", "GOLD"}

# SPUR.BAR2.S chk.2 — random idle responses Guss gives when no keyword hits
_IDLE_RESPONSES = [
    "Guss looks at you, 'You don't say!'",
    "Guss looks thoughtful..",
    "Guss refills your glass, listening..",
    "'Um-hmmm...'",
    "'Say! How do ya suppose they get frosting in those twinkies?'",
    "Guss stares off into space..",
    "'yep..'",
]


def _scan_chat(text: str) -> Optional[str]:
    """Return a Guss chat response string, or None to fall through to idle.

    SPUR.BAR2.S chat.chk scans the input one word at a time against keyword
    lists.  We replicate that word-level scan here rather than substring match
    so "GOLD" doesn't trigger on "MARIGOLD", etc.
    """
    stripped = text.strip()

    # Bare "?" → request for clarification (SPUR: if i$="?")
    if stripped == "?":
        return "'Could you be a bit more clear?'"

    words = stripped.upper().split()

    for word in words:
        if word in _PROFANITY:
            return "Guss is shocked by your foul mouth.."
        if word in _QUESTION_WH:
            return "'An interesting question..'"
        if word in _INSULTS:
            # SPUR: gosub fight then i$="'Hmpth..'" — here we just warn
            return "Guss clenches his jaw. 'Watch yourself, dude.'"
        if word in _LORE:
            return "Guss looks nervous, 'Watch what you say..'"
        if word in _MYSTERY:
            return "'Stay healthy, keep your nose clean and you will find out!'"

    # Question mark anywhere in text (SPUR: if instr("?",i$))
    if "?" in stripped:
        return random.choice([
            "'Why do you ask?'",
            "'What kind of question is that?'",
            "'I waz wondering that myself..'",
            "'Beats me..'",
        ])

    if "HELP" in {w.upper() for w in words}:
        return "'One must help one's self..'"

    return None  # chk.2 idle path


async def _guss_talk(ctx: GameContext) -> None:
    """Free-form chat with Guss. SPUR.BAR2.S: bar.b → chat.chk loop."""
    player = ctx.player

    await ctx.send(f'Guss says, "So, what{_AP}s on yer mind, {player.name}?"')

    while True:
        raw = await ctx.prompt('->')
        if raw is None:
            break

        text = raw.strip()
        if not text or text.upper() in ('Q', 'L', 'LEAVE', 'BYE'):
            break

        response = _scan_chat(text)
        if response is None:
            response = random.choice(_IDLE_RESPONSES)

        await ctx.send(f'Guss says, "{response}"')
        # SPUR: after chk.3 print, prompts again (goto chat.chk)


# ---------------------------------------------------------------------------
# Guss — coin flip
# ---------------------------------------------------------------------------

_FLIP_MAX_BET = 1_000   # SPUR: zz>1000 → "1000 max, my friend.."
_FLIP_RICH    = 10_000  # SPUR: gh>1 (more than one 10,000-gp page) → "Yer too rich for me!"


async def _guss_flip(ctx: GameContext) -> None:
    """Coin-flip gambling. SPUR.BAR2.S: flip section."""
    player = ctx.player

    await ctx.send(
        f'Guss says, "AWWRIGHT {_AP}M Man!" Guss thumps a bag of gold on the bar!'
    )

    while True:
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        await ctx.send(f'(You have {silver:,}s in hand.)')

        if silver >= _FLIP_RICH:
            await ctx.send("Guss says, 'Yer too rich for me!'")
            return

        raw = await ctx.prompt("'How much ya wanna bet?' (Enter to leave)")
        if raw is None or not raw.strip() or raw.strip().upper() == 'Q':
            return

        try:
            bet = int(raw.strip())
        except ValueError:
            await ctx.send("Guss squints. 'That ain't a number, dude.'")
            continue

        if bet <= 0:
            return
        if bet > _FLIP_MAX_BET:
            await ctx.send("Guss says, '1000 max, my friend..'")
            continue
        if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, bet):
            await ctx.send("Guss says, 'Hey dude, you don't have that much!'")
            continue

        # Call the toss
        while True:
            raw2 = await ctx.prompt("Call it! [H]eads or [T]ails?")
            if raw2 is None:
                # Carrier drop — refund and exit
                player.subtract_silver(PlayerMoneyTypes.IN_HAND, -bet)
                return
            call = raw2.strip().upper()
            if call in ('H', 'T'):
                break
            await ctx.send("Guss says, 'Huh?'")

        await ctx.send("Guss flips a coin..")
        result = random.choice(('H', 'T'))
        await ctx.send(f'Guss says, "{"HEADS" if result == "H" else "TAILS"}!"')

        if result == call:
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -bet)   # refund + winnings
            player.unsaved_changes = True
            await ctx.send(f"Guss says, 'You win!'  (+{bet:,}s)")
        else:
            player.unsaved_changes = True
            await ctx.send(f"Guss says, 'Too bad..'  (-{bet:,}s)")


# ---------------------------------------------------------------------------
# Guss — blackjack
# ---------------------------------------------------------------------------

_BJ_TABLE_LIMIT  = 500   # SPUR: b>500 → "500 gold. Table limit, my friend.."
_BJ_MIN_BET      = 25    # SPUR: b<25  → "Last of the big spenders!" (non-blocking)
_BJ_RICH         = 10_000 # SPUR: gh>1 → "Yer too rich for me!"
_BJ_DEALER_STAND = 17    # Dealer (Guss) stands on 17+; hits on 16 or less

# Ranks: (display_label, card_value)  — Aces start at 11; bust-reduction handled by _hand_total
_RANKS = [
    ('2',2), ('3',3), ('4',4), ('5',5), ('6',6), ('7',7),
    ('8',8), ('9',9), ('10',10), ('J',10), ('Q',10), ('K',10), ('A',11),
]
_SUITS = ['♠', '♥', '♦', '♣']


def _draw_card() -> tuple[str, int]:
    """Return (display_label, value) for a random card."""
    rank_label, value = random.choice(_RANKS)
    suit              = random.choice(_SUITS)
    return f'{rank_label}{suit}', value


def _hand_total(cards: list) -> int:
    """Best blackjack total: reduce Aces from 11→1 as needed to avoid bust."""
    total = sum(v for _, v in cards)
    aces  = sum(1 for _, v in cards if v == 11)
    while total > 21 and aces:
        total -= 10
        aces  -= 1
    return total


def _fmt_hand(cards: list, hide_hole: bool = False) -> str:
    """Format a hand as '[A♠] [K♥]'.  hide_hole=True shows '[?]' for card index 1."""
    parts = []
    for i, (label, _) in enumerate(cards):
        parts.append('[?]' if hide_hole and i == 1 else f'[{label}]')
    return ' '.join(parts)


async def _guss_blackjack(ctx: GameContext) -> None:
    """Full blackjack game.  SPUR.BAR2.S blackjack section — ver. 1.4.

    Payout model (bet already deducted before each hand):
      win  → subtract_silver(−bet*2)  # return stake + profit
      push → subtract_silver(−bet)    # return stake only
      loss → nothing                  # stake was already deducted
    """
    player = ctx.player

    await ctx.send(
        "Guss says, 'AWWRIGHT!' Guss plops a strange hat on his head, and deals.."
    )

    while True:
        silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        await ctx.send(f'(You have {silver:,}s in hand.)')

        if silver < 1:
            await ctx.send("Guss says, 'Hey dude, broke eh? Maybe later..'")
            return
        if silver >= _BJ_RICH:
            await ctx.send("Guss says, 'Yer too rich for me!'")
            return

        raw = await ctx.prompt("'How much ya wanna bet?' (Enter or Q to leave)")
        if raw is None or raw.strip().upper() in ('', 'Q'):
            return

        try:
            bet = int(raw.strip())
        except ValueError:
            await ctx.send("Guss squints. 'A number, dude..'")
            continue

        if bet <= 0:
            return
        if bet > _BJ_TABLE_LIMIT:
            await ctx.send("Guss says, '500 gold. Table limit, my friend..'")
            continue
        if bet < _BJ_MIN_BET:
            await ctx.send("Guss says, 'Last of the big spenders!'")
            # Non-blocking — SPUR just prints the line
        if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, bet):
            await ctx.send(f"Guss says, 'Hey dude, you don{_AP}t have that much!'")
            continue

        # Deal initial hands; redeal if either starts at 21 before blackjack check
        # (SPUR: if zt>21 goto set.num / if zs>21 goto set.num)
        for _ in range(10):
            p_hand = [_draw_card(), _draw_card()]
            g_hand = [_draw_card(), _draw_card()]
            if _hand_total(p_hand) <= 21 and _hand_total(g_hand) <= 21:
                break

        p_total = _hand_total(p_hand)
        g_total = _hand_total(g_hand)

        # Natural blackjack checks (SPUR: if zs=21 / if zt=21)
        if g_total == 21:
            await ctx.send([
                f'Guss reveals: {_fmt_hand(g_hand)}  = 21',
                "Guss says, 'Blackjack! I win! Most excellent!'",
            ])
            player.unsaved_changes = True
            continue  # next hand; bet already forfeited

        if p_total == 21:
            # SPUR: g2=b*2:gosub add.gold — return stake + profit (blackjack pays 1:1 here)
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -(bet * 2))
            player.unsaved_changes = True
            await ctx.send([
                f'Your hand: {_fmt_hand(p_hand)}  = 21',
                f"Guss says, 'Blackjack! You win! Bogus!'  (+{bet:,}s)",
            ])
            continue  # next hand

        # Player's turn
        busted = False
        while True:
            p_total = _hand_total(p_hand)
            await ctx.send([
                f'Your hand:  {_fmt_hand(p_hand)}  = {p_total}',
                f'Guss shows: {_fmt_hand(g_hand, hide_hole=True)}',
            ])

            raw2 = await ctx.prompt('[H]it, [D]ouble, [S]tand')
            if raw2 is None:
                # Carrier drop — forfeit bet and exit
                player.unsaved_changes = True
                return

            action = raw2.strip().upper()

            if action == 'D':
                # SPUR: g2=b*2:gosub chk.gold; if fail → "Yo! Dude!..."
                if not player.subtract_silver(PlayerMoneyTypes.IN_HAND, bet):
                    await ctx.send(
                        "Guss says, 'Yo! Dude! You don't have the gold to do that!'"
                    )
                    continue
                bet *= 2   # SPUR: b=b*2
                card  = _draw_card()
                p_hand.append(card)
                p_total = _hand_total(p_hand)
                await ctx.send(f'You draw {card[0]}.  You have {p_total}.')
                if p_total > 21:
                    await ctx.send("Guss says, 'You busted! Radical!'")
                    player.unsaved_changes = True
                    busted = True
                break  # double forces stand

            elif action == 'H':
                card = _draw_card()
                p_hand.append(card)
                p_total = _hand_total(p_hand)
                await ctx.send(f'You draw {card[0]}.  You have {p_total}.')
                if p_total > 21:
                    await ctx.send("Guss says, 'You busted! Radical!'")
                    player.unsaved_changes = True
                    busted = True
                    break

            elif action == 'S':
                break  # stand

            else:
                await ctx.send("Guss says, 'I think your shorts must be too tight..'")

        if busted:
            continue  # bet already forfeited; next hand

        # Dealer's turn (SPUR: com.turn / com.cards — hits on ≤ 16)
        await ctx.send(f'Guss reveals: {_fmt_hand(g_hand)}  = {g_total}')
        while g_total < _BJ_DEALER_STAND:
            card    = _draw_card()
            g_hand.append(card)
            g_total = _hand_total(g_hand)
            await ctx.send(f'Guss draws {card[0]}.  Guss has {g_total}.')

        p_total = _hand_total(p_hand)
        await ctx.send([
            f'You had  = {p_total}',
            f'Guss had = {g_total}',
        ])

        # Determine outcome (SPUR: bj.result)
        if p_total == g_total:
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -bet)   # push — return stake
            player.unsaved_changes = True
            await ctx.send("  --- Push ---")
        elif g_total > 21:
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -(bet * 2))
            player.unsaved_changes = True
            await ctx.send(f"Guss says, 'You win! Most henious'  (+{bet:,}s)")
        elif p_total > g_total:
            player.subtract_silver(PlayerMoneyTypes.IN_HAND, -(bet * 2))
            player.unsaved_changes = True
            await ctx.send(f"Guss says, 'You win! Most bogus..'  (+{bet:,}s)")
        else:
            # Guss wins (SPUR: "Tubuler!")
            player.unsaved_changes = True
            await ctx.send("Guss says, 'I win! Tubuler!'")


# ---------------------------------------------------------------------------
# Guss — main session loop
# ---------------------------------------------------------------------------

async def _guss_session(ctx: GameContext) -> None:
    """Guss the Barkeep interaction loop.  SPUR.BAR2.S: bar.a / bar.b."""
    player = ctx.player
    guss   = Bartender("Guss", gender="m", strength=5, to_hit=5, flags=[])
    guss.greetings = [
        "HAAY... DUDE! Like wats happenin?",
        "Awwright, my man! Pull up a stool!",
        "Hey dude! Long time no see! What'll it be?",
        "DUDE! You made it!",
        "Hey hey hey! The party can start now!",
    ]

    await ctx.send([
        'Guss the Barkeep grins at you.',
        f'Guss says, "{random.choice(guss.greetings)}"',
    ])
    await broadcast_area(ctx, 'bar', f'{player.name} bellies up to the bar with Guss.')

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await ctx.send(
            "Guss is the night-shift barkeep at Bar None.  "
            "He's up for a chat, a coin flip, or a hand of blackjack."
        )

    while True:
        if not player.query_flag(PlayerFlags.EXPERT_MODE):
            await ctx.send('[T]alk, [F]lip coins, [B]lackjack, [L]eave')

        raw = await ctx.prompt('Guss')
        if raw is None:
            await ctx.send("Guss says, 'Later... dude!'")
            break

        inp = raw.strip().upper()
        if not inp or inp in ('L', 'Q', 'LEAVE'):
            await ctx.send("Guss says, 'Later... dude!'")
            await broadcast_area(ctx, 'bar', f'{player.name} tips a hat to Guss and heads out.')
            break
        elif inp == '?':
            await ctx.send('[T]alk, [F]lip coins, [B]lackjack, [L]eave')
        elif inp[0] == 'T':
            await _guss_talk(ctx)
        elif inp[0] == 'F':
            await _guss_flip(ctx)
        elif inp[0] == 'B':
            await _guss_blackjack(ctx)
        else:
            await ctx.send('Guss looks puzzled..')


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(ctx: GameContext, bar=None) -> None:
    """Bar None interaction loop.  Routes to Mae (day) or Guss (night)."""
    player = ctx.player

    if _is_guss_shift():
        await _guss_session(ctx)
        return

    # --- Mae's day shift ---
    mae = Bartender(_NPC, strength=4, to_hit=4, gender="f", flags=[])

    tip_lines = []
    if not player.is_expert:
        tip_lines = tip(ctx, "Mae the Bartender",
                        "Mae is the owner and bartender of 'Bar None.' "
                        "You can (L)ist the menu at any time, or enter a number to buy something.")
        description_lines = []
        if tip_lines:
            description_lines.append("")
        description_lines.append(
            'The air in "Bar None" is thick enough to chew, a permanent fog of old smoke, spilled ale, '
            'and faint, sweet perfume clinging to the dark wood paneling. Light struggles through the '
            'grimy windows, illuminating lazy, swirling motes of dust in golden shafts that barely reach '
            'the sticky floor. Every sound is muffled here--the low murmur of hushed conversations, the '
            'clink of heavy glass mugs, the soft scrape of a chair against worn floorboards.')
        description_lines.append("")
        description_lines.append(
            "Behind the bar, a formidable oak counter scarred with the rings of a thousand drinks, rows "
            "of dusty bottles stand like silent soldiers at attention. Their labels are faded and peeling, "
            "their contents a mystery of dark ambers, deep crimsons, and liquids the color of old poison. "
            "Flickering light from a crackling fire glints off the grime on their glass shoulders, "
            "promising either a forgotten treasure or a quick death.")
        description_lines.append("")
        description_lines.append(mae.random_greeting())
        await ctx.send(tip_lines + description_lines)

    await _mae_session(ctx, mae)


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import asyncio
    import unittest.mock
    from unittest.mock import AsyncMock, MagicMock

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.name             = 'Rulan'
    ctx.player.hit_points       = 20
    ctx.player.unsaved_changes  = False
    ctx.player.query_flag       = lambda _: True   # expert mode on
    ctx.player.toggle_flag      = lambda *_: None
    ctx.player.subtract_silver  = MagicMock(return_value=True)
    ctx.player.get_silver       = MagicMock(return_value=500)
    ctx.send  = AsyncMock()

    # Force Guss shift for smoke-test
    with unittest.mock.patch('bar.bar_none._is_guss_shift', return_value=True):
        # t)alk → say something → leave chat; f)lip → bet → heads; b)lackjack → bet → stand; l)eave
        answers = iter([
            't', 'Hello dude, whats new?', '',      # talk → idle response → exit talk
            'f', '100', 'h',                        # flip → bet 100 → heads
            'b', '50', 's',                         # blackjack → bet 50 → stand (dealer plays out)
            'l',                                    # leave
        ])
        ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))
        asyncio.run(main(ctx))

    print("Standalone bar_none test complete.")
