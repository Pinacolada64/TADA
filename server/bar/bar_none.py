import logging
import random
from player import Player
from flags import PlayerFlags
from bar.main import food_menu
from tada_utilities import input_string, get_pronoun, PronounType, get_article_and_quantity
from ally_data import Ally


class Bartender(Ally):
    """
    :param name: name
    :param gender: gender
    :param strength: strength
    :param to_hit: to-hit probability (x10, so 4 x10 = 40)
    :param flags: AllyFlags class [optional]
    """
    def __init__(self, name, gender, strength, to_hit, flags):
        super().__init__(name, gender, strength, to_hit, flags)
        self.greetings = [
            f"Can't just stand there. What'll it be?",
            f"Fresh off the road? You look it. Name your poison.",
            f"The name's {self.name}. The bottles are dusty, but the ale is cold. What do you want?",
            f"Find a seat, or don't. Just tell me what you're drinkin'.",
            f"Another soul wanders in. Let's get you something to forget why.",
            f"I've got everything from 'cheap and nasty' to 'top shelf and dusty'. Your call.",
        ]

    def random_greeting(self):
        return f'The bartender says, "{random.choice(self.greetings)}"'


def main(character: Player):
    from base_classes import PlayerMoneyTypes
    from tada_utilities import tip

    mae = Bartender("Mae", strength=4, to_hit=4, gender="f", flags=[])
    # TODO: bar brawls? attack other patrons/bartender?
    apostrophe = "'"

    if not character.query_flag(PlayerFlags.EXPERT_MODE):
        # Step 1: Call tip() to get the list of strings for the box.
        # This will be an empty list if the user is in expert mode.
        tip_lines = tip(character, "Mae the Bartender",
                        "Mae is the owner and bartender of 'Bar None.' "
                        "You can (L)ist the menu at any time, or enter a number to buy something.")

        # Step 2: Create the list of other description lines.
        description_lines = []
        # Add a conditional blank line if there is a tip box.
        if tip_lines:
            description_lines.append("")
        description_lines.append(
            'The air in "Bar None" is thick enough to chew, a permanent fog of old smoke, spilled ale, '
            'and faint, sweet perfume clinging to the dark wood paneling. Light struggles through the '
            'grimy windows, illuminating lazy, swirling motes of dust in golden shafts that barely reach '
            'the sticky floor. Every sound is muffled here--the low murmur of hushed conversations, the '
            'clink of heavy glass mugs, the soft scrape of a chair against worn floorboards.')
        description_lines.append("")
        description_lines.append("Behind the bar, a formidable oak counter scarred with the rings of a thousand drinks, rows "
            "of dusty bottles stand like silent soldiers at attention. Their labels are faded and peeling, "
            "their contents a mystery of dark ambers, deep crimsons, and liquids the color of old poison. "
            "Flickering light from a crackling fire glints off the grime on their glass shoulders, "
            "promising either a forgotten treasure or a quick death.")
        description_lines.append("")
        description_lines.append(mae.random_greeting())

        # Step 3: Combine the two lists into a single, flat list.
        output_to_page = tip_lines + description_lines

        # Step 4: Pass the final list to your output handler.
        character.output(output_to_page)

    # TODO: multiple, random bartenders?

    # Load the initial data once
    try:
        foodstuffs = Rations.read_rations("../rations.json")
    except FileNotFoundError:
        foodstuffs = []  # Start with an empty list if the file doesn't exist
        logging.debug("Foodstuffs not found")

    # Get the canonical list of items IN THE ORDER THEY ARE DISPLAYED
    # This is the single source of truth for our menu.
    displayed_items = food_menu(character, foodstuffs)
    logging.debug("Displayed items: %i" % len(displayed_items))
    # Main input loop
    while True:
        prompt = f"L)ist, X)pert mode, or select 1-{len(displayed_items)}"
        menu_item = input_string(character, prompt, "", True, False)

        if menu_item == '':
            character.output(f'{mae.name} nods as you head for the door. "See you around."')
            break
        elif menu_item.lower() in ["?", "l", "list"]:
            # Just re-display the menu. We don't need to re-generate the list.
            displayed_items = food_menu(character, foodstuffs)
            continue
        elif menu_item.lower() == "x":
            character.toggle_flag(PlayerFlags.EXPERT_MODE, True)
            continue

        try:
            item_num = int(menu_item)

            # Check if the number is in the valid range of the menu
            if 1 <= item_num <= len(displayed_items):
                # Convert the user's 1-based number to a 0-based list index
                selected_item = displayed_items[item_num - 1]

                # Now you have the correct Rations object!
                if character.subtract_silver(PlayerMoneyTypes.IN_HAND, selected_item.price):
                    character.output(f"You slide a few coins across the bar for {get_article_and_quantity(selected_item.name.title())}.")
                else:
                    character.output(f'{mae.name} shakes {get_pronoun(mae, PronounType.SUBJECTIVE)} '
                                     f'head. "Looks as if that{apostrophe}s too rich for your blood..."')
            else:
                # The number was valid, but not on the menu (e.g., 99)
                responses = [f'Please read carefully, since our menu items have recently changed in order to better serve you.',
                             f'Please continue to peruse the menu, as your order is very important to us.',
                             f"Sorry, hon, I don{apostrophe}t have anything for number {item_num} on my list."]
                character.output(f'Mae says, "{random.choice(responses)}"')

        except ValueError:
            # The input wasn't a number
            character.output(f'{mae.name} says, "Well, that{apostrophe}s an odd menu selection..."')

        except IndexError as e:
            # This is a failsafe, but the check above should prevent it
            logging.error(f"Menu selection caused an IndexError: {e}")


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Logging is running")

    # 1. Read the file.
    from server import Rations

    player = Player()
    player.clear_flag(PlayerFlags.EXPERT_MODE)
    player.set_flag(PlayerFlags.TIRED)

    foodstuffs = Rations.read_rations("../rations.json")
    drinks = [ration for ration in foodstuffs if ration['kind'] == 'drink']

    main(player)
