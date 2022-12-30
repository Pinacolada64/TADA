import shutil  # for get_terminal_width()
import textwrap
import re
import colorama  # for foreground color changes

# import server.server


def bouncer():
    """
    Mundo the bouncer gets personal with the player.
    Also called from Blue Djinn being insulted.
    """
    global hp, pos_y, pos_x, valid_move
    text = ["At a signal, Mundo "]
    # if player's HP < 5, don't attack with baseball bat:
    if hp > 5:
        text.append("knocks you over the head with a baseball bat, and ")
        hp -= 5
    text.append("throws you out into the street...")
    output(" ".join(text))
    pos_y, pos_x = 0, 6
    valid_move = True  # to re-display bar map


def blue_djinn():
    """Hire thugs to attack other players"""
    character = "The Blue Djinn"
    if flag['expert_mode'] is False:
        output(f"For a price, {character} can attack other players.")
        blue_djinn_menu()
    output(f'{character} sits behind the table.')
    while True:
        command, last_command = prompt('He hisses, "What do you want?":', help=True)
        if command == 'h':
            output('"Who do you want me to mess up?"')
            output("TODO")
            continue
        if command == 'i':
            bouncer()
            continue
        if command == 'l':
            output("He looks relieved.")
            break  # out of loop
        if command == '?':
            blue_djinn_menu()
            continue
        else:
            output(f"{character} looks amused.")
            continue


def blue_djinn_menu():
    output("\n[H]ire [I]nsult [L]eave\n")


def skip():
    """Order hash or coffee"""
    global player_name
    if flag['expert_mode'] is False:
        output("You can come here once per day to drink coffee (which resets"
               "your 'tired' and 'thirsty' health flags), or eat hash (which"
               "restores some of your energy).")
        print()
    output("Skip sweats over a hot grill, muttering under his breath...")

    if flag["debug"]:
        while True:
            command, last_command = prompt("Add 'Skip' to once-per-day activities?", help=True)
            if command == 'y':
                if "Skip" not in once_per_day:
                    once_per_day.append("Skip")
                    output("Appended.")
                    break  # out of loop
            if command == '?':
                output("Trip the 'once per day' limit of visiting Skip's eatery.")
    if "Skip" in once_per_day:
        output('Skip suddenly looks annoyed. "Hey, you\'ve already [been] here once today!"')
        return

    if flag["expert_mode"] is False:
        skip_show_menu()

    while True:
        command, last_command = prompt(f'"What\'ll ya have, {player_name}?" ', help=True)
        if command == 'h':
            # TODO: check/subtract silver
            output("The hash is greasy, but hot and nourishing.")
            continue

        if command == 'c':
            # TODO: check/subtract silver
            output("The steaming mug of coffee is strangely satisfying.")
            continue

        if command == '?':
            skip_show_menu()
            continue

        if command == 'l':
            output('"Yeah, well... take \'er easy..." Skip mumbles.')
            return
        else:
            output('"Eh? What?" Skip mutters.')


def skip_show_menu():
    output("[H]ash (1 silver), [C]offee (5 silver), or [L]eave")


def vinny():
    """Loan shark"""
    output("Vinny")


def zelda():
    """Madame Zelda, the fortune-teller"""
    logging.debug("zelda(): importing bar_zelda.py")
    global player_name
    global client
    print("zelda(): function call")
    import bar_zelda
    bar_zelda.main()
    return


def fat_olaf():
    output("The slave trader Fat Olaf sits behind a table, gnawing a chicken leg.")
    if flag["expert_mode"] is False:
        output("I buy und sell servants yu can add tu your party! "
               "They need tu be fed und paid on a veekly basis "
               "tu remain loyal tu yu, though!")
        print()
        fat_olaf_menu()
        print()
    while True:
        command, last_command = prompt("Vot kin I du ver ya?", help=True)
        if command == '' or command == 'l':
            output('"Hokey dokey." Fat Olaf watches you leave.')
            return

        if command == "?":
            fat_olaf_menu()
            continue
        if command in ["b", "s", "m"]:
            output("FIXME: That hasn't been written yet.")
            continue
        else:
            output('Fat Olaf looks puzzled. "Vot?"')


def fat_olaf_menu():
    output(f"[B]uy, [S]ell, [M]aintain, [L, {client['return_key']}] Leave")
    return


def bar_none():
    output("Exception raised: NO_FLAVOR_TEXT")


def horizontal_ruler():
    # TODO: This will come in handy for text editor .Column display

    #           1         2         3         4
    # 01234567890123456789012345678901234567890 etc.
    ruler_length = len(bar[0])
    digits = "0123456789"
    text = ["    "]
    highest_tens_digit = int(str(ruler_length)[0])
    for tens in range(1, highest_tens_digit + 1):
        text.append(f'{tens:> 10}')
    output("".join(text))
    output(f"   {(digits * 10)[:ruler_length]}")


def prompt(prompt: str, help=False):
    """
    Prompt user for something
    :param prompt: string to prompt for, minus space at end
    :param help: if True and Expert Mode is off, tell that '?' gets help
    :return: tuple(last_command, command)
    """
    global command, last_command
    if flag['expert_mode'] is False and help is True:
        prompt = f"['?' for menu] {prompt}"
    temp = input(f"{prompt} ")
    print()
    if temp != '':
        command = temp[0].lower()
        last_command = command
    if temp == '':
        command = last_command
        if flag["expert_mode"] is False:
            output(f"(Repeating '{command}'.)\n")
    return last_command, command


def show_main_menu():
    # TODO: grab these options from the functions themselves
    extra = ", [G]o here" if go_here else ''
    output(f"[N]orth, [E]ast, [S]outh, [W]est, [Q]uit{extra}")
    output("Toggles: [D]ebug, [T]ranslation, e[X]pert Mode, [M]ore Prompt")
    output("  Tests: [O]utput word-wrap, [X] More Prompt")


def output(string: str, bracket_coloring=True) -> None:
    """
    Word-wrap string to client['cols'] width.
    If a line break in the string is needed, make two separate calls to output(), one per line.
    Ending a string with a CR or specifying CR in the join() call won't do what you want.

    :param string: string[] to output
    :param bracket_coloring: if False, do not recolor text within brackets
     (e.g., used in drawing bar because of '[]' table graphics)
    """

    """
    we want to wrap the un-substituted text first. substituting ANSI
    escape codes adds 5-6 characters per substitution, and that wraps
    text in the wrong places.
    """
    # returns wrapped_text[]:
    wrapped_text = textwrap.wrap(string, width=client['cols'])

    # color text inside brackets using re and colorama:
    # '.+?' is a non-greedy match (finds multiple matches, not just '[World...a]')
    # >>> re.sub(r'\[(.+?)\]', r'!\1!', string="Hello [World] this [is a] test.")
    # 'Hello !World! this !is a! test.'
    if bracket_coloring and client['translation'] != "ASCII":
        foreground = colorama.Fore
        colored_lines = []
        for i, temp in enumerate(wrapped_text):
            colored_lines.append(re.sub(pattern=r'\[(.+?)]',
                                        repl=f'{foreground.RED}' + r'\1' + f'{foreground.RESET}',
                                        string=temp))
        new_lines = colored_lines
    else:
        new_lines = string

    if type(new_lines) == str:
        print(f'{new_lines}')
        return
    elif type(new_lines) == list:
        for i, line in enumerate(new_lines, start=1):
            print(line)
            if i % client['rows'] == 0 and flag['more_prompt'] is True:
                # print(f'{i=} {client["rows"]=} {i % client["rows"]=}')
                temp, _ = prompt(f"[A]bort or {client['return_key']} to continue: ", help=False)
                if temp == 'a':
                    print('[Aborted.]')
                    break  # out of the loop

        """
        rows = 25
        for i in range(1,58):
            print(f'{i=}', end='')
            if i % rows == 0:
                print(f' [pause]', end='')
            print()
        """


if __name__ == '__main__':
    import logging
    # y, x, name, routine to call:
    locations = [(0, 6, "Exit", None),
                 (1, 4, "The Blue Djinn", blue_djinn),
                 (1, 8, "Vinny the Loan Shark", vinny),
                 (2, 4, "Skip's Eats", skip),
                 (2, 5, "Bar None", bar_none),
                 (3, 8, "Fat Olaf's Slave Trade", fat_olaf),
                 (4, 8, "Madame Zelda's", zelda)]

    obstacles = ["+", "-", "|", '[', ']']

    # pos is zero-based from the top down, left-to-right
    pos_y = 0  # row
    pos_x = 6  # column

    window_size = shutil.get_terminal_size()

    client = {"type": "Commodore 64",
              "return_key": "Return",
              "cols": window_size[0],
              "rows": window_size[1],
              "translation": "PetSCII"}

    flag = {"expert_mode": False,
            "debug": True,
            "more_prompt": True}

    # once-per-day activities:
    once_per_day = []

    # must be assigned for 'global' in prompt() to work:
    command = "?"
    last_command = "?"

    player_name = "Railbender"

    # TODO: get from Player.hit_points:
    hp = 20

    output('You stand in the doorway of a smoky bar. A faded sign reads: "WALL BAR AND GRILL."')

    while True:
        if client['translation'] == 'PetSCII':
            # code page 437 / Commodore PetSCII graphics
            bar = ["┌────┤ ├────┐",
                   "│o[]     []o│",
                   "│           │",
                   "│  ┌──┐  []o│",
                   "│  │oo│  []o│",
                   "└──┴──┴─────┘"]
        else:
            # ASCII
            bar = ["+----| |----+",
                   "|o[]     []o|",
                   "|           |",
                   "|  +--+  []o|",
                   "|  |oo|  []o|",
                   "+-----------+"]
        print()
        if flag["debug"]:
            horizontal_ruler()
        for count, line in enumerate(bar):
            text = []
            if flag["debug"]:
                text.append(f'{count: 2} ')
            if count == pos_y:
                text.append(f'{line[:pos_x]}X{line[pos_x + 1:]}')
            else:
                text.append(line)
            # FIXME: bracket_coloring parameter needed?
            # output("".join(text), bracket_coloring=False)
            # output(text, bracket_coloring=False)
            print("".join(text))
        go_here = False
        valid_move = False

        for place in locations:
            # sorted by rows
            if pos_y == place[0] and pos_x == place[1]:
                text = [f'{place[2]}']
                if flag["debug"]:
                    text.append(f"  {place[3]}")
                output("".join(text), bracket_coloring=False)
                go_here = True
                go_routine = place[3]

        if flag["debug"]:
            output(f'{pos_x=}, {pos_y=}')

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
            # FIXME: intercept moving south from here, can walk over Fat Olaf
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
                    output(f"{opponent} something something...")
            else:
                output('"Well then, [WATCH] it!"')

        if flag['expert_mode'] is False:
            show_main_menu()
            output(f"[{client['return_key']}] = '{last_command}'")

        output(f"[HP: {hp}]")
        # parser:
        command, last_command = prompt("Which way?")
        move_into_obstacle = False

        if command == '?':
            show_main_menu()
            valid_move = True

        if command == "g":
            if go_here:
                valid_move = True
                # NOTE: exit doesn't have a function
                if callable(go_routine):
                    go_routine()
                    print()
                else:
                    output(f"Can't hack it, man. {go_routine} isn't callable.")
            if flag['debug']:
                valid_move = False
                while valid_move is False:
                    last_place = len(locations)
                    for i, k in enumerate(locations):
                        print(f'{i} {k[2]}')
                    place, temp = prompt("Quick move:", help=False)
                    place = int(place)
                    if 1 > place > last_place:
                        output("Aborting.")
                        break  # out of the loop
                    where = locations[place]
                    pos_y, pos_x = where[0], where[1]
                    print(f"Quick moving to {where[2]}.")
                    valid_move = True

        # toggles:
        if command == 'd':
            flag['debug'] = not flag['debug']
            output(f"Debug info is now {'On' if flag['debug'] else 'Off'}.")
            valid_move = True

        if command == 'x':
            flag['expert_mode'] = not flag['expert_mode']
            output(f"Expert Mode is now {'On' if flag['expert_mode'] else 'Off'}.")
            valid_move = True

        if command == 't':
            temp = client['translation']
            if temp == 'PetSCII':
                kind = "ASCII"
                client['translation'] = kind
            elif temp == 'ASCII':
                kind = "PetSCII"
                client['translation'] = kind
            output(f"(Translation type changed to '{kind}'.)")
            valid_move = True

        # other:
        if command == 'o':
            output("Using output(): Lorem ipsum dolor sit amet, consectetur "
                   "adipiscing elit, sed do eiusmod tempor incididunt ut labore "
                   "et dolore magna aliqua. Suscipit adipiscing bibendum est "
                   "ultricies integer quis auctor elit. Sed viverra ipsum nunc "
                   "aliquet bibendum enim facilisis. Amet nulla facilisi morbi "
                   "tempus iaculis urna id volutpat. Nec tincidunt praesent semper "
                   "feugiat nibh sed. Lacus luctus accumsan tortor posuere. Gravida "
                   "quis blandit turpis cursus in hac habitasse platea. Consequat "
                   "id porta nibh venenatis cras sed. Potenti nullam ac tortor vitae "
                   "purus faucibus. Habitasse platea dictumst vestibulum rhoncus est "
                   "pellentesque elit ullamcorper dignissim. Nec nam aliquam sem et. "
                   "Dui ut ornare lectus sit amet est placerat. Sagittis orci a "
                   "scelerisque purus. Adipiscing vitae proin sagittis nisl rhoncus "
                   "mattis rhoncus. Ut morbi tincidunt augue interdum velit. Orci eu "
                   "lobortis elementum nibh tellus.")

            x = input("Okay? ")
            # valid_move = True  # because Latin is incomprehensible :)

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
            output("Laughter fills the bar as you attempt to move through solid objects.\n")
            hp -= 1
            if hp <= 0:
                output("You have died.")
                # TODO: room_notify(f"{player.name} dies from bumping into something.")
                break  # out of loop
            continue  # suppress the following message

        if valid_move:
            last_command = command
        else:
            output("The bar patrons look at you strangely as you do something incomprehensible.")
            last_command = "?"
            # TODO: room_notify(f"{player.name} is confused.")
