"""bar/bar_none.py — Bar None: drinks and food at the Wall Bar & Grill."""
import logging
import random

from bar.ally_data import Ally
from bar.main import food_menu
from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from items import Rations
from network_context import GameContext
from tada_utilities import get_pronoun, PronounType, get_article_and_quantity, tip

log = logging.getLogger(__name__)

_NPC = "Mae"
_AP = "'"


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


async def _bar_none_menu(ctx: GameContext, displayed_items: list) -> None:
    lines = ["Menu:", ""]
    for i, item in enumerate(displayed_items, 1):
        lines.append(f"  {i:>2}. {item.name.title():<20} {item.price:>3} silver")
    lines.append("")
    lines.append(f"[L]ist, [X]pert mode, or select 1-{len(displayed_items)}")
    await ctx.send(lines)


async def main(ctx: GameContext, bar=None) -> None:
    """Bar None interaction loop."""
    player = ctx.player
    mae = Bartender(_NPC, strength=4, to_hit=4, gender="f", flags=[])

    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        tip_lines = tip(player, "Mae the Bartender",
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

    foodstuffs = Rations.read_rations("../rations.json") or []

    displayed_items = food_menu(player, foodstuffs)
    log.debug("Displayed items: %i", len(displayed_items))
    await _bar_none_menu(ctx, displayed_items)

    while True:
        raw = await ctx.prompt(f"1-{len(displayed_items)}, [L]ist, [X]pert")
        if raw is None:
            await ctx.send(f'{mae.name} nods as you head for the door. "See you around."')
            break

        menu_item = raw.strip()
        if not menu_item:
            await ctx.send(f'{mae.name} nods as you head for the door. "See you around."')
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
    ctx.player.query_flag = lambda _: True   # expert mode on; skips tip/description
    ctx.player.toggle_flag = lambda *_: None
    ctx.player.subtract_silver = lambda *_: True
    ctx.send = AsyncMock()

    answers = iter(['l', '1', ''])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(answers, None))

    asyncio.run(main(ctx))
    print("Standalone bar_none test complete.")
