import logging
import random  # for random.choices
from dataclasses import dataclass

# this also imports the current Player class framework:
# TODO: break Player stuff out of flags
from flags import Player, PlayerFlags, PlayerMoneyTypes

def bouncer(character: Player):
    """
    Mundo the bouncer gets personal with the player.
    Also called when the Blue Djinn is insulted.
    """
    print("At a signal, Mundo ", end='')
    # if player's HP < 5, don't attack with baseball bat:
    if character.hit_points > 5:
        print("knocks you over the head with a baseball bat, and ", end='')
        # TODO: write 'character.adjust_hp' and put check for >=0 HP there...
        character.hit_points -= 5
    print("throws you out into the street...")
    bar.pos_y, bar.pos_x = 0, 6
    bar.valid_move = True  # to re-display bar map


def blue_djinn(character: Player):
    """Hire thugs to attack other players"""
    npc = "The Blue Djinn"
    if character.query_flag(PlayerFlags.EXPERT_MODE) is False:
        print(f"For a price, {npc} can attack other players.")
        blue_djinn_menu()
    print(f'{npc} sits behind the table.')
    while True:
        command, last_command = prompt(character, 'He hisses, "What do you want?":')
        if command == 'h':
            print('"Who do you want me to mess up?"')
            # TODO: finish Blue Djinn
            continue
        if command == 'i':
            # choice insults:
            # convert list element random.choices returns to a string:
            random_insult = random.choices(["lineage", "dog's appearance", "parenting skills"])[0]
            print(f"You say something deeply insulting about {npc_name}'s {random_insult}.")
            print(f"{npc_name}'s eyes narrow...\n")
            bouncer(character)
            break
        if command == 'l':
            print("He looks relieved.")
            break  # out of loop
        if command == '?':
            blue_djinn_menu(character)
            continue
        else:
            print(f"{npc} looks amused.")
            continue

def blue_djinn_menu(character: Player):
    print("\nOptions: [H]ire [I]nsult [L]eave\n")

def vinny(character: Player):
    """Loan shark"""
    print("Vinny")

def skip(character: Player):
    """Order hash or coffee from Skip"""
    print("Skip sweats over a hot grill, muttering under his breath...")

    add_item = "Skip"
    # TODO: make this a general function
    if character.query_flag(PlayerFlags.DEBUG_MODE):
        command, last_command = prompt(character, f"Add '{add_item}' to once-per-day activities? ")
        if command == 'y':
            if add_item not in character.once_per_day:
                character.once_per_day.append(add_item)
                print("Appended.")
    if add_item in character.once_per_day:
        print('Skip suddenly looks annoyed. "Hey, you\'ve already [been] here once today!"')
        print("He points angrily towards the exit, and you decide to heed his advice.")
        print("(Never argue with a man who has hot grease at his disposal.)")
        return

    if character.query_flag(PlayerFlags.EXPERT_MODE) is False:
        skip_show_menu()

    while True:
        command, last_command = prompt(character, f'"What\'ll ya have, {character.name}?" ')
        if command == 'h':
            # TODO: check/subtract silver
            print("The hash is greasy, but hot and nourishing.")
            continue

        if command == 'c':
            # TODO: check/subtract silver
            character.gold[PlayerMoneyTypes.IN_HAND] = character.gold[PlayerMoneyTypes.IN_HAND] - 2
            print("The steaming mug of coffee is strangely satisfying.")
            character.clear_flag(PlayerFlags.TIRED)
            print("(You feel more awake.)")
            continue

        if command == '?':
            skip_show_menu(character)
            continue

        if command == 'l':
            print('"Yeah, well... take \'er easy..." Skip mumbles.')
            return
        else:
            print('"Eh? What?" Skip mutters.')


def skip_show_menu(character: Player):
    print("[H]ash (1 silver), [C]offee (5 silver), or [L]eave")


def fat_olaf(character: Player):
    npc_name = "Fat Olaf"
    print(f"The slave trader {npc_name} sits behind a table, gnawing a chicken leg.")
    if character.query_flag(PlayerFlags.EXPERT_MODE) is False:
        print('''
"I buy und sell servants yu can add tu your party!
They need tu be fed und paid on a veekly basis tu remain loyal tu yu, though!"
''')
        fat_olaf_menu(character)
        print()
    while True:
        command, last_command = prompt(character, "Vot kin I du ver ya?")
        if command == '' or command == 'l':
            print(f'"Hokey dokey." {npc_name} watches you leave.')
            return

        if command == "?":
            fat_olaf_menu(character)
            continue
        if command in ["b", "s", "m"]:
            print("FIXME: That hasn't been written yet.")
            continue
        else:
            print(f'{npc_name} looks puzzled. "Vot?"')


def fat_olaf_menu(character: Player):
    print(f"[B]uy, [S]ell, [M]aintain an ally, [L] or [Return]: Leave")
    return


def bar_none(character: Player):
    print("Exception raised: NO_FLAVOR_TEXT")


def zelda(character: Player):
    """
    * Spy on player's stats
    * Raise other players' dead monsters
    """
    npc_name = "Madame Zelda"
    if character.query_flag(PlayerFlags.EXPERT_MODE) is False:
        print(f"""
{npc_name} can show other players' statistics, or resurrect their dead
monsters (for a hefty fee!) so they have to be fought again.
""")
        zelda_menu(character)
    print(f'{npc_name} and her cat sit in front of a crystal ball.')
    while True:
        command, last_command = prompt(character, '"What dooooo you wiiiiiish?":')
        if command == "s":
            if character.query_flag(PlayerFlags.EXPERT_MODE) is False:
                print("'?' lists players.")
            command, last_command = prompt(character, '"Study which player?":')
            if command.lower() == character.name.lower():
                # studying themselves :)
                print('"I suggesssst you uuuuuuuse a mirror!"')
            if command == '?':
                list_players()
                continue
            else:
                while True:
                    command, last_command = prompt(character, '"It willlll cossssst 1,000 silver. Is thaaaaaat okayyyyy?":')
                    if command == 'y':
                        # TODO: check silver, find player, read stats
                        print('She hunkers down over the ball.. "I seeeee..."')
                        """
                        TLoS code:
                        print n2$" on dungeon level "yl"."
                        print "With "yh" hit points, a strength"
                        print "of "cs", intelligence of "ci","
                        print "dexterity of "cd", energy of "ce","
                        print "constitution of "ct", wisdom of "cw"."
                        print n2$" has achieved level "yn
                        print "in the land, has "ye"% shield, and"
                        print yf"% armor. Instruments of death:'"
                        gosub pr.weapons
                        """
                    else:
                        print('"Hmph..."')
                        break
                    continue
        if command == 'r':
            # TODO: Resurrect player's monsters
            # TODO: adjust Honor score if natural alignment is Good
            target = input('"Whooose monsters shall I briiiiing back to liiiiife?" ')
            if target == '':
                break
            if target == character.name:
                # raise your own monsters?
                print('"I dooooon\'t adviiiiise thaaaaaat."')
                break
            while True:
                command, last_command = prompt(character, '"Dooo you wiiiiish to be unknowwwwwn?" [Y/N]:')
                print(f"{npc_name} and her cat get REALLY weird...")
                benefactor = f'{"somebody" if command == "y" else f"{character.name}"}'
                message = f"Zelda casts 'Monster Life' on {target}! Spell paid for by {benefactor}!"
                print(message)
                # TODO: add this message to daily event log
                print('"It iiiisss doooooone!"')
                break
            continue  # back to menu
        if command == '?':
            zelda_menu(character)
            continue
        if command == 'l' or command == '':
            print('"Gooo awayyyyy, you bother my caaaat..."')
            break  # out of loop
        else:
            print(f'{npc_name} stares at you. Her cat stares too.')

def zelda_menu(character: Player):
    print(f"Options: [S]tudy a player, [R]esurrect monsters, or [L]/[Return]: Leave")
    # TODO: f"{character.client_settings.RETURN_KEY}" or something

def list_players(character: Player):
    """List players in game"""
    import glob
    player_list = glob.glob('./server/run/server/player-*.json')
    # TODO: get names from JSON files
    if player_list is None:
        print("There are no players.")
        return
    else:
        for player_name, index in enumerate(player_list):
            print(f'{index: 2}. {player_name}')


def horizontal_ruler():
    # TODO: This will come in handy for text editor .Column display

    #           1         2         3         4
    # 01234567890123456789012345678901234567890 etc.
    ruler_length = len(bar.bar_map[0])
    digits = "0123456789"
    print("   ", end='')
    print(" ", end='')  # extra space for first '0'
    highest_tens_digit = int(str(ruler_length)[0])
    for tens in range(1, highest_tens_digit + 1):
        print(f'{tens:> 10}', end='')
    print()
    print("   ", end='')
    print((digits * 10)[:ruler_length])


def prompt(character: Player, prompt: str):
    """
    Prompt user for something, accept input

    :param character: Player to prompt, also for ClientSettings.RETURN_KEY string
    :param prompt: string to prompt for, minus space at end
    :return: tuple(last_command, command) # command: leftmost char of input, lowercase
    """
    global command, last_command
    temp = input(f"{prompt} ")
    print()
    if temp != '':
        command = temp[0].lower()
        last_command = command
    if temp == '':
        command = last_command
        if character.query_flag(PlayerFlags.EXPERT_MODE) is False:
            print(f"(Repeating '{command}'.)\n")
    return last_command, command


def bar_help(character: Player):
    print("""
This is the Wall Bar & Grill, a place where you (and your party, if you
have others with you) can find food, drink, and various services to help
yourself--or harm others, if you wish--in the Land.

In the map of the bar, 'o' represents each person you can interact with,
by moving in front (or to the side) of them. 'M' represents Mundo, the
bar bouncer. Lastly, 'X' represents you (and your party, if applicable).
""")

def show_menu(character: Player):
    go_here = ", [G]o here" if bar.can_go_here else ''
    print(f"[N]orth, [E]ast, [S]outh, [W]est{go_here}, [H]elp, [Q]uit")
    print("Toggles: [D]ebug, e[X]pert Mode")


@dataclass
class Bar(object):
    # initial x-coordinate of player:
    pos_x: int = 6
    # initial y-coordinate of player:
    pos_y: int = 0
    # True: a person to interact with is in an adjacent square
    # and '[G]o Here' will be shown in the hotkey options
    can_go_here: bool = False

    valid_move: bool = True

    # 'M' is marker for Mundo, the bar's bouncer
    # 'o' is marker for various NPCs sitting behind tables
    bar_map = ["+----| |----+",
               "|o[]     []o|",
               "|          M|",
               "|  +--+  []o|",
               "|  |oo|  []o|",
               "+-----------+"
               ]

    # tuple is: y-coordinate, x-coordinate, name, routine to call:
    # TODO: if Expert Mode off, display a letter instead of 'o'
    locations = [(0, 6, "Exit", None),
                 (1, 4, "The Blue Djinn", blue_djinn),
                 (1, 8, "Vinny the Loan Shark", vinny),
                 (2, 4, "Skip's Eats", skip),
                 (2, 5, "Bar None", bar_none),
                 (3, 8, "Fat Olaf's Slave Trade", fat_olaf),
                 (4, 8, "Madame Zelda's", zelda)]

    obstacles = ["+", "-", "|", '[', ']', 'o', 'M']


if __name__ == '__main__':
    # instantiate Player
    rulan = Player()
    rulan.client_settings = {"type": "Commodore 64",
                             "return_key": "Return"}

    # TODO: rulan.clear_flag(PlayerFlagTypes.EXPERT_MODE) # set to False
    # TODO: rulan.set_flag(PlayerFlagTypes.DEBUG_MODE) # set to True

    # once-per-day activities:
    rulan.once_per_day = []

    # must be assigned for 'global' in prompt() to work:
    rulan.command = "?"
    rulan.last_command = "?"

    rulan.hit_points = 20

    # instantiate Bar, place player at (x=6, y=0)
    bar = Bar()
    logging.debug("%s" % bar.bar_map)

    print("You stand in the doorway of a smoky bar. A faded sign reads:")
    print('"WALL BAR AND GRILL."')

    while True:
        if rulan.query_flag(PlayerFlags.DEBUG_MODE):
            horizontal_ruler()
        for count, line in enumerate(bar.bar_map):
            if rulan.query_flag(PlayerFlags.DEBUG_MODE):
                print(f'{count: 2} ', end='')
            if count == bar.pos_y:
                print(f'{line[:bar.pos_x]}X{line[bar.pos_x + 1:]}')
            else:
                print(line)

        # look through 'locations' tuple to see if the player is in an
        # interactive spot
        for place in bar.locations:
            # sorted by rows
            if bar.pos_y == place[0] and bar.pos_x == place[1]:
                print(f'{place[2]}', end='')
                if rulan.query_flag(PlayerFlags.DEBUG_MODE):
                    print(f"  function: {place[3]}", end='')
                print()
                bar.can_go_here = True
                bar.go_routine = place[3]

        if rulan.query_flag(PlayerFlags.DEBUG_MODE):
            print(f'(x: {bar.pos_x}, y: {bar.pos_y})')

        bump = False
        opponent = None
        text = None
        if bar.pos_y == 2 and bar.pos_x == 1:
            bump = True
            opponent = "The Blue Djinn"
            text = 'eyes you, hissing. "Are'
        if bar.pos_y == 2 and bar.pos_x == 11:
            # getting too close to Vinny the loan shark:
            bump = True
            opponent = "Mundo the bouncer"
            text = 'looks up from the floor. "Hey,'
        if bump:
            response = ''
            while response not in ["y", "n"]:
                response = input(f'{opponent} {text} you looking for a fight?" (Y/N): ')[0].lower()
            if response == "y":
                if opponent.startswith("Mundo"):
                    bouncer(rulan)  # also called from blue djinn
                    continue
                else:
                    # TODO: Blue Djinn: finish this
                    print(f"{opponent} something something...")
            else:
                print(f'"Well then, WATCH it!" {opponent} glares at you.')

        if rulan.query_flag(PlayerFlags.EXPERT_MODE) is False:
            show_menu()
            print(f"[{rulan.client_settings['return_key']}] = '{rulan.last_command}'")
            show_menu(rulan)

        print(f"[HP: {rulan.hit_points}] ", end='')
        # parser:
        command, last_command = prompt(rulan, "What now?")
        move_into_obstacle = False

        if command == '?':
            show_menu(rulan)

        if command == 'h':
            bar_help(rulan)

        if bar.can_go_here and command == "g":
            # exit doesn't have a function
            if callable(bar.go_routine):
                # FIXME:  mutable parameter list
                bar.go_routine(rulan)  # call routine with Character object
                print()

        if command == 'd':
            rulan.toggle_flag(PlayerFlags.DEBUG_MODE, verbose=True)
            # print(f"Debug info is now {'On' if rulan.query_flag(PlayerFlagName.DEBUG_MODE) else 'Off'}.")

        if command == 'x':
            rulan.toggle_flag(PlayerFlags.EXPERT_MODE, verbose=True)
            # print(f"Expert Mode is now {'On' if rulan.query_flag(PlayerFlagName.EXPERT_MODE) else 'Off'}.")

        if command == 'n':
            # look up for obstacle:
            obstacle = bar.bar_map[bar.pos_y - 1][bar.pos_x]
            if obstacle not in bar.obstacles:
                bar.pos_y -= 1
                bar.valid_move = True
            else:
                bar.move_into_obstacle = True

        if command == 's':
            # look down for obstacle:
            obstacle = bar.bar_map[bar.pos_y + 1][bar.pos_x]
            if obstacle not in bar.obstacles:
                bar.pos_y += 1
            else:
                move_into_obstacle = True

        if command == 'e':
            # look right for obstacle:
            obstacle = bar.bar_map[bar.pos_y][bar.pos_x + 1]
            if obstacle not in bar.obstacles:
                bar.pos_x += 1
            else:
                move_into_obstacle = True

        if command == 'w':
            # look left for obstacle:
            obstacle = bar.bar_map[bar.pos_y][bar.pos_x - 1]
            if obstacle not in bar.obstacles:
                bar.pos_x -= 1
            else:
                move_into_obstacle = True

        if command == "q":
            break

        if move_into_obstacle:
            print("Laughter fills the bar as you attempt to move through solid objects.\n")
            rulan.hit_points -= 1
            if rulan.hit_points <= 0:
                print("You have died.")
                # TODO: room_notify(f"{player.name} dies from bumping into something.")
                break  # out of loop
            continue  # suppress the following message

        if bar.valid_move:
            last_command = command
        else:
            # valid_move has been set to False above
            print("The bar patrons look at you strangely as you do something incomprehensible.")
            last_command = "?"
            # TODO: room_notify(f"{player.name} is confused.")
