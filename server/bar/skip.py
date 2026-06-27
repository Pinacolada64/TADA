"""bar/skip.py — Skip's Eats: hash and coffee at the Wall Bar & Grill."""
import logging

from bar.ally_data import Ally
from base_classes import PlayerMoneyTypes, PronounType
from flags import PlayerFlags
from network_context import GameContext
from presence import broadcast_area
from tada_utilities import get_pronoun

log = logging.getLogger(__name__)

_NPC = "Skip"
_AP = "'"   # apostrophe shorthand used in Skip's dialogue


async def _skip_menu(ctx: GameContext) -> None:
    await ctx.send([
        f"[H]ash   (1 silver),",
        "[C]offee (5 silver),",
        "[L]eave",
    ])


async def main(ctx: GameContext, bar=None) -> None:
    """Skip's Eats interaction loop."""
    player = ctx.player

    await ctx.send(f"{_NPC} sweats over a hot grill, muttering under his breath...")

    # TODO: make handling once-daily events a general function
    add_item = _NPC
    if player.query_flag(PlayerFlags.DEBUG_MODE):
        raw = await ctx.prompt('Y/N', preamble_lines=[f"Add '{add_item}' to once-per-day activities?"])
        if raw is not None and raw.strip().lower() in ('y', 'yes'):
            if add_item not in player.once_per_day:
                player.once_per_day.append(add_item)
                await ctx.send("Appended.")

    if add_item in player.once_per_day:
        await ctx.send(
            f'Skip suddenly looks annoyed. "Hey, you{_AP}ve already [been] here once today!" '
            "He points angrily towards the exit, and you decide to heed his advice. "
            "(Never argue with a man who has hot grease at his disposal.)"
        )
        return

    await broadcast_area(ctx, 'bar', f'{player.name} sits down at {_NPC}\'s counter.')

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        await _skip_menu(ctx)

    pay_9_grand = False
    if player.query_flag(PlayerFlags.DEBUG_MODE):
        raw = await ctx.prompt('Y/N', preamble_lines=["Pay 9,000 to trigger failure cases?"])
        pay_9_grand = raw is not None and raw.strip().lower() in ('y', 'yes')

    while True:
        await ctx.send("")
        raw = await ctx.prompt(f'"What{_AP}ll ya have, {player.name}?"')
        if raw is None:
            break

        # No repeat-last-command here (keep_msg=False in original)
        menu_item = raw.strip().lower()
        if not menu_item:
            continue

        await ctx.send("")

        if menu_item == 'h':
            # Debug only: seed test allies so the party-selection path can be exercised
            if player.query_flag(PlayerFlags.DEBUG_MODE):
                await player.party.add(ctx, player, Ally("Michelle", "f", 4, 5))
                await player.party.add(ctx, player, Ally("King Brian", "m", 5, 6))

            # Default: feed the player themselves
            patron = player
            first_or_third_person = "you"
            pronoun = get_pronoun(player, PronounType.SUBJECTIVE)
            plural = ""

            if player.party:
                patrons = [player] + list(player.party)
                lines = [f"{i}. {p.name}" for i, p in enumerate(patrons, 1)]
                await ctx.send(["Who to feed:"] + lines)

                total = len(patrons)
                selection = None
                while True:
                    raw_sel = await ctx.prompt(f"Choose who to feed (1-{total})")
                    if raw_sel is None:
                        break
                    try:
                        sel = int(raw_sel.strip())
                        if 1 <= sel <= total:
                            selection = sel
                            break
                    except ValueError:
                        pass
                    await ctx.send("Try again.")
                if selection is None:
                    break

                patron = patrons[selection - 1]
                if isinstance(patron, Ally):
                    first_or_third_person = get_pronoun(patron, PronounType.SUBJECTIVE)
                    pronoun = first_or_third_person.capitalize()
                    plural = "s"
                else:
                    # Another Player in the party
                    first_or_third_person = (
                        "you" if selection == 1
                        else get_pronoun(patron, PronounType.SUBJECTIVE)
                    )
                    pronoun = get_pronoun(patron, PronounType.SUBJECTIVE).capitalize()
                    plural = ""

            cost = 9_000 if pay_9_grand else 1
            if player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost):
                await ctx.send(
                    f"Skip pushes a chipped plate with some hash sitting on it towards {patron.name}. "
                    f"Hesitantly, {first_or_third_person} decide{plural} to sample {_NPC}{_AP}s wares. "
                    f"The hash is greasy, but hot and nourishing."
                )
                current_hp = patron.hit_points
                adjusted_hp = current_hp + 5
                patron.hit_points = adjusted_hp
                if not player.query_flag(PlayerFlags.EXPERT_MODE):
                    poss = (
                        "Your" if patron is player
                        else get_pronoun(patron, PronounType.POSSESSIVE_ADJECTIVE).capitalize()
                    )
                    await ctx.send(
                        f"({poss} hit points have gone up by 5, from {current_hp} to {adjusted_hp}.)"
                    )
            else:
                await ctx.send(f'"Sorry, pal," {_NPC} mutters, "I{_AP}m not running a charity here."')

        elif menu_item == 'c':
            cost = 9_000 if pay_9_grand else 5
            if player.subtract_silver(PlayerMoneyTypes.IN_HAND, cost):
                await ctx.send(
                    "Skip sets a chipped mug filled with viscous black... something... "
                    "on the counter in front of you. "
                    "Oddly enough, the steaming mug of coffee is strangely satisfying."
                )
                if player.query_flag(PlayerFlags.TIRED):
                    player.clear_flag(PlayerFlags.TIRED)
                    if not player.query_flag(PlayerFlags.EXPERT_MODE):
                        await ctx.send("(You feel more awake.)")
            else:
                await ctx.send(
                    f'{_NPC} wipes a nonexistent spot on the luncheon counter with a rag. '
                    f'"I know, times are tough."'
                )

        elif menu_item == '?':
            await _skip_menu(ctx)

        elif menu_item in ('l', 'q'):
            await ctx.send(f'"Yeah, well... take {_AP}er easy..." {_NPC} mumbles.')
            await broadcast_area(ctx, 'bar', f'{player.name} gets up from {_NPC}\'s counter.')
            break

        else:
            await ctx.send(f'"That ain{_AP}t on the menu," {_NPC} mutters.')


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
    ctx.player.once_per_day = []
    from party import Party
    ctx.player.party = Party()
    ctx.player.query_flag = lambda _: False
    ctx.player.subtract_silver = lambda *_: True
    ctx.send = AsyncMock()

    answers = iter(['h', 'c', 'l'])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, 'l'))

    asyncio.run(main(ctx))
    print("Standalone skip test complete.")
