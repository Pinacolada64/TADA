import random
from player import Player
from flags import PlayerFlags

def main(character: Player):
    if not character.query_flag(PlayerFlags.EXPERT_MODE):
        character.output(['The air in "Bar None" is thick enough to chew, a permanent fog of old smoke, spilled ale, '
                          'and faint, sweet perfume clinging to the dark wood paneling. Light struggles through the '
                          'grimy windows, illuminating lazy, swirling motes of dust in golden shafts that barely reach '
                          'the sticky floor. Every sound is muffled here--the low murmur of hushed conversations, the '
                          'clink of heavy glass mugs, the soft scrape of a chair against worn floorboards.',
                          "",
                          "Behind the bar, a formidable oak counter scarred with the rings of a thousand drinks, rows "
                          "of dusty bottles stand like silent soldiers at attention. Their labels are faded and peeling, "
                          "their contents a mystery of dark ambers, deep crimsons, and liquids the color of old poison. "
                          "Light from a single, low-hanging bulb glints off the grime on their glass shoulders, "
                          "promising either a forgotten treasure or a quick death."])

    mae = Bartender()
    character.output(["", mae.random_greeting(), "",
                      "The place doesn't look very inviting, so you step back out. Besides, the code isn't done."])


class Bartender:
    def __init__(self):
        self.name = "Mae"
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

if __name__ == '__main__':
    character = Player()
    main(character)
