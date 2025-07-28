import bar.main
from bar.main import prompt
import random
from flags import PlayerFlags
from player import Player

def main(character: Player):
    """Hire thugs to attack other players"""
    npc_name = "The Blue Djinn"
    if not character.query_flag(PlayerFlags.EXPERT_MODE):
        character.output(f"For a price, {npc_name} can attack other players.")
        blue_djinn_menu(character)
    character.output(f'{npc_name} sits behind the table.')
    while True:
        command, last_command = prompt(character, 'He hisses, "What do you want?":')
        if command == 'h':
            character.output('"Who do you want me to mess up?"')
            # TODO: finish Blue Djinn
            continue
        if command == 'i':
            # choice insults:
            # convert list element random.choices returns to a string:
            random_insult = random.choices(["lineage", "dog's appearance", "parenting skills"])[0]
            character.output(f"You say something deeply insulting about {npc_name}'s {random_insult}. "
                             f"{npc_name}'s eyes narrow...")
            bar.main.bouncer(character)
            continue
        if command in ['l', '']:
            print(f"{npc_name} looks relieved.")
            break  # out of loop
        if command in ['h', '?']:
            blue_djinn_menu(character)
            continue
        else:
            print(f"{npc_name} looks amused.")
            continue

def blue_djinn_menu(character: Player):
    character.output("Options: [H]ire [I]nsult [L]eave")

if __name__ == '__main__':
    player = Player()
    main(character=player)
