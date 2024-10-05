# this also imports the current Player class framework:
import flags

def bouncer():
    """
    Mundo the bouncer gets personal with the player.
    Also called when the Blue Djinn is insulted.
    """
    global hp, pos_y, pos_x, valid_move
    print("At a signal, Mundo ", end='')
    # if player's HP < 5, don't attack with baseball bat:
    if hp > 5:
        print("knocks you over the head with a baseball bat, and ", end='')
        hp -= 5
    print("throws you out into the street...")
    pos_y, pos_x = 0, 6
    valid_move = True  # to re-display bar map


def blue_djinn(character: Player):
    """Hire thugs to attack other players"""
    npc = "The Blue Djinn"
    if flag['expert_mode'] is False:
        print(f"For a price, {npc} can attack other players.")
        blue_djinn_menu()
    print(f'{npc} sits behind the table.')
    while True:
        command, last_command = prompt('He hisses, "What do you want?":')
        if command == 'h':
            print('"Who do you want me to mess up?"')
            print("TODO")
            continue
        if command == 'i':
            bouncer()
            continue
        if command == 'l':
            print("He looks relieved.")
            break  # out of loop
        if command == '?':
            blue_djinn_menu()
            continue
        else:
            print(f"{npc} looks amused.")
            continue

def blue_djinn_menu():
    print("\n[H]ire [I]nsult [L]eave\n")

def vinny():
    """Loan shark"""
    print("Vinny")


def skip(character: Player):
    """Order hash or coffee"""
    global player_name
    print("Skip sweats over a hot grill, muttering under his breath...")

    if flag["debug"]:
        command, last_command = prompt("Add 'Skip' to once-per-day activities?")
        if command == 'y':
            if "Skip" not in once_per_day:
                once_per_day.append("Skip")
                print("Appended.")
    if "Skip" in once_per_day:
        print('Skip suddenly looks annoyed. "Hey, you\'ve already [been] here once today!"')
        return

    if flag["expert_mode"] is False:
        skip_show_menu()

    while True:
        command, last_command = prompt(f'"What\'ll ya have, {character.name}?" ')
        if command == 'h':
            # TODO: check/subtract silver
            print("The hash is greasy, but hot and nourishing.")
            continue

        if command == 'c':
            # TODO: check/subtract silver
            print("The steaming mug of coffee is strangely satisfying.")
            character.
            continue

        if command == '?':
            skip_show_menu()
            continue

        if command == 'l':
            print('"Yeah, well... take \'er easy..." Skip mumbles.')
            return
        else:
            print('"Eh? What?" Skip mutters.')


def skip_show_menu():
    print("[H]ash (1 silver), [C]offee (5 silver), or [L]eave")


def fat_olaf(character: Player):
    print("The slave trader Fat Olaf sits behind a table, gnawing a chicken leg.")
    if flag["expert_mode"] is False:
        print('''
"I buy und sell servants yu can add tu your party!
They need tu be fed und paid on a veekly basis tu remain loyal tu yu, though!"
''')
        fat_olaf_menu()
        print()
    while True:
        command, last_command = prompt("Vot kin I du ver ya?")
        if command == '' or command == 'l':
            print('"Hokey dokey." Fat Olaf watches you leave.')
            return

        if command == "?":
            fat_olaf_menu()
            continue
        if command in ["b", "s", "m"]:
            print("FIXME: That hasn't been written yet.")
            continue
        else:
            print('Fat Olaf looks puzzled. "Vot?"')


def fat_olaf_menu():
    print(f"[B]uy, [S]ell, [M]aintain, [L, {client['return_key']}] Leave")
    return


def bar_none():
    print("Exception raised: NO_FLAVOR_TEXT")


def zelda():
    """
    Spy on player's stats
    Raise other players' dead monsters
    """
    character = "Madame Zelda"
    if flag['expert_mode'] is False:
        print("She can show other players' statistics, or resurrect their dead monsters so they have to be fought again.")
        zelda_menu()
    print(f'{character} and her cat sit in front of a crystal ball.')
    while True:
        command, last_command = prompt('"What dooooo you wiiiiiish?":')
        if command == "s":
            if flag['expert_mode'] is False:
                print("'?' lists players.")
            command, last_command = prompt('"Study which player?":')
            if command.lower() == player_name.lower():
                print('"I suggesssst you uuuuuuuse a mirror!"')
            if command == '?':
                list_players()
                continue
            else:
                while True:
                    command, last_command = prompt('"It willlll cossssst 1,000 silver. Is thaaaaaat okayyyyy?":')
                    if command == 'y':
                        print("TODO: check silver, find player, read stats")
                        print('She hunkers down over the ball.. "I seeeee..."')
                        """
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
            print("TODO: Resurrect player's monsters")
            target = input('"Whooose monsters shall I briiiiing back to liiiiife?" ')
            while True:
                command, last_command = prompt('"Dooo you wiiiiish to be unknowwwwwn?" [Y/N]:')
                print(f"{character} and her cat get REALLY weird...")
                benefactor = f'{"somebody" if command == "y" else f"{player_name}"}'
                message = f"""Zelda casts 'Monster Life' on {target}! Spell paid for by {benefactor}!"""
                print(message)
                # TODO: battle_log(message)
                print('"It iiiisss doooooone!"')
                break
            continue  # back to menu
        if command == '?':
            zelda_menu()
            continue
        if command == 'l':
            print('"Gooo away, you bother my caaaat..."')
            break  # out of loop
        else:
            print(f'{character} stares at you. Her cat stares too.')

def zelda_menu():
    print("[S]tudy a player, [R]esurrect monsters, or [L]eave")


def list_players():
    """List players in game"""
    import os
    import glob
    import server.server
    player_list = glob.glob('./server/run/server/player-*.json')
    # FIXME: get names from JSON files
    if player_list is None:
        print("There are no players.")
        return
    else:
        for player_name, index in enum(player_list):
            print(f'{index: 2}. {player_name}')


def horizontal_ruler():
    # TODO: This will come in handy for text editor .Column display

    #           1         2         3         4
    # 01234567890123456789012345678901234567890 etc.
    ruler_length = len(bar[0])
    digits = "0123456789"
    print("   ", end='')
    print(" ", end='')  # extra space for first '0'
    highest_tens_digit = int(str(ruler_length)[0])
    for tens in range(1, highest_tens_digit + 1):
        print(f'{tens:> 10}', end='')
    print()
    print("   ", end='')
    print((digits * 10)[:ruler_length])


def prompt(prompt: str):
    """
    Prompt user for something
    :param prompt: string to prompt for, minus space at end
    :return: tuple(last_command, command)
    """
    global command, last_command
    temp = input(f"{prompt} ")
    print()
    if temp != '':
        command = temp[0].lower()
        last_command = command
    if temp == '':
        command = last_command
        if flag["expert_mode"] is False:
            print(f"(Repeating '{command}'.)\n")
    return last_command, command


def show_menu():
    extra = ", [G]o here" if go_here else ''
    print(f"[N]orth, [E]ast, [S]outh, [W]est, [Q]uit{extra}")
    print("Toggles: [D]ebug, e[X]pert Mode")


if __name__ == '__main__':
    bar = ["+----| |----+",
           "|o[]     []o|",
           "|           |",
           "|  +--+  []o|",
           "|  |oo|  []o|",
           "+-----------+"
           ]

    # y, x, name, routine to call:
    locations = [(0, 6, "Exit", None),
                 (1, 4, "The Blue Djinn", blue_djinn),
                 (1, 8, "Vinny the Loan Shark", vinny),
                 (2, 4, "Skip's Eats", skip),
                 (2, 5, "Bar None", bar_none),
                 (3, 8, "Fat Olaf's Slave Trade", fat_olaf),
                 (4, 8, "Madame Zelda's", zelda)]

    obstacles = ["+", "-", "|", '[', ']']

    print("You stand in the doorway of a smoky bar. A faded sign reads:")
    print('"WALL BAR AND GRILL."')

    # pos is zero-based from the top down, left-to-right
    pos_y = 0  # row
    pos_x = 6  # column

    client = {"type": "Commodore 64",
              "return_key": "Return"}

    rulan = Player()

    rulan.
    flag = {"expert_mode": False,
            "debug": True}

    # once-per-day activities:
    once_per_day = []

    # must be assigned for 'global' in prompt() to work:
    command = "?"
    last_command = "?"

    player_name = "Railbender"

    # TODO: get from Player.hit_points:
    hp = 20

    while True:
        if flag["debug"]:
            horizontal_ruler()
        for count, line in enumerate(bar):
            if flag["debug"]:
                print(f'{count: 2} ', end='')
            if count == pos_y:
                print(f'{line[:pos_x]}X{line[pos_x + 1:]}')
            else:
                print(line)

        go_here = False
        valid_move = False

        for place in locations:
            # sorted by rows
            if pos_y == place[0] and pos_x == place[1]:
                print(f'{place[2]}', end='')
                if flag["debug"]:
                    print(f"  function {place[3]}", end='')
                print()
                go_here = True
                go_routine = place[3]

        if flag["debug"]:
            print(f'{pos_x=}, {pos_y=}')

        bump = False
        if pos_y == 2 and pos_x == 1:
            bump = True
            opponent = "The Blue Djinn"
            text = 'eyes you, hissing. "Are'
        if pos_y == 2 and pos_x == 11:
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
                    bouncer()  # also called from blue djinn
                    continue
                else:
                    # TODO: Blue Djinn: finish this
                    print(f"{opponent} something something...")
            else:
                print('"Well then, WATCH it!"')

        if flag['expert_mode'] is False:
            show_menu()

        print(f"[{client['return_key']}] = '{last_command}'")
        print(f"[HP: {hp}] ", end='')
        # parser:
        command, last_command = prompt("Which way?")
        move_into_obstacle = False

        if command == '?':
            show_menu()
            valid_move = True

        if go_here and command == "g":
            valid_move = True
            # exit doesn't have a function
            if go_routine:
                go_routine()  # call routine
                print()
            # if callable(go_routine):
            #   go_routine  # does not work

            # except:
            #     print("Can't hack it, man.")

        if command == 'd':
            flag['debug'] = not flag['debug']
            print(f"Debug info is now {'On' if flag['debug'] else 'Off'}.")
            valid_move = True

        if command == 'x':
            flag['expert_mode'] = not flag['expert_mode']
            print(f"Expert Mode is now {'On' if flag['expert_mode'] else 'Off'}.")
            valid_move = True

        if command == 'n':
            # look up for obstacle:
            obstacle = bar[pos_y - 1][pos_x]
            if obstacle not in obstacles:
                pos_y -= 1
                valid_move = True
            else:
                move_into_obstacle = True

        if command == 's':
            # look down for obstacle:
            obstacle = bar[pos_y + 1][pos_x]
            if obstacle not in obstacles:
                pos_y += 1
                valid_move = True
            else:
                move_into_obstacle = True

        if command == 'e':
            # look right for obstacle:
            obstacle = bar[pos_y][pos_x + 1]
            if obstacle not in obstacles:
                pos_x += 1
                valid_move = True
            else:
                move_into_obstacle = True

        if command == 'w':
            # look left for obstacle:
            obstacle = bar[pos_y][pos_x - 1]
            if obstacle not in obstacles:
                pos_x -= 1
                valid_move = True
            else:
                move_into_obstacle = True

        if command == "q":
            break

        if move_into_obstacle:
            print("Laughter fills the bar as you attempt to move through solid objects.\n")
            hp -= 1
            if hp <= 0:
                print("You have died.")
                # TODO: room_notify(f"{player.name} dies from bumping into something.")
                break  # out of loop
            continue  # suppress the following message

        if valid_move:
            last_command = command
        else:
            print("The bar patrons look at you strangely as you do something incomprehensible.")
            last_command = "?"
            # TODO: room_notify(f"{player.name} is confused.")
