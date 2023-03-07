import shutil  # for get_terminal_width()
import textwrap
import re
import colorama  # for foreground color changes
import logging

import bar_zelda
from tada_utilities import output, input_prompt
from globals import set_client, get_client, set_flag, get_flag
from server import Player

# client = get_client()
# flag = get_flag()


def bouncer(conn: Player):
    """
    Mundo the bouncer gets personal with the player.
    Also called from Blue Djinn being insulted.
    """
    global hp, pos_y, pos_x, valid_move
    text = ["At a signal, Mundo "]
    # if player's HP < 5, don't attack with baseball bat:
    if conn.hit_points > 5:
        text.append("knocks you over the head with a baseball bat, and ")
        conn.hit_points -= 5
    text.append("throws you out into the street...")
    output([" ".join(text)], conn)
    pos_y, pos_x = 0, 6
    valid_move = True  # to re-display bar map


def blue_djinn(conn: Player):
    """Hire thugs to attack other players"""
    character = "The Blue Djinn"
    if conn.flag['expert_mode'] is False:
        output([f"For a price, {character} can attack other players."], conn)
        print()
        blue_djinn_menu()
    output(f'{character} sits behind the table.')
    while True:
        command, last_command = input_prompt('He hisses, "What do you want?":', help=True)
        if command == 'h':
            output(['"Who do you want me to mess up?"', "TODO"], conn)
            continue
        if command == 'i':
            bouncer(conn)
            continue
        if command == 'l':
            output(["He looks relieved."], conn)
            break  # out of loop
        if command == '?':
            blue_djinn_menu(conn)
            continue
        else:
            output([f"{character} looks amused."], conn)
            continue


def blue_djinn_menu(conn: Player):
    output(["[H]ire [I]nsult [L]eave"], conn)


def skip(conn: Player):
    """Order hash or coffee"""
    # global player_name
    if conn.flag['expert_mode'] is False:
        output(["You can come here once per day to drink coffee (which resets "
                "your 'tired' and 'thirsty' health flags), or eat hash (which "
                "restores some of your energy)."], conn)
        print()
    output(["Skip sweats over a hot grill, muttering under his breath..."], conn)

    if conn.flag["debug"]:
        while True:
            command, _ = input_prompt("Add 'Skip' to once-per-day activities?", help=True)
            if command == 'y':
                if "Skip" not in conn.once_per_day:
                    conn.once_per_day.append("Skip")
                    output(["Appended."], conn)
                    break  # out of loop
            elif command == 'n':
                break
            elif command == '?':
                output(["Trip the 'once per day' limit of visiting Skip's eatery."], conn)
    if "Skip" in conn.once_per_day:
        output(['Skip suddenly looks annoyed. "Hey, you\'ve already [been] here once today!"'], conn)
        return

    if conn.flag["expert_mode"] is False:
        skip_show_menu(conn)

    while True:
        command, last_command = input_prompt(f'"What\'ll ya have, {conn.name}?" ', help=True)
        if command == 'h':
            # TODO: check/subtract silver
            output(["The hash is greasy, but hot and nourishing."], conn)
            continue

        if command == 'c':
            # TODO: check/subtract silver
            output(["The steaming mug of coffee is strangely satisfying."], conn)
            continue

        if command == '?':
            skip_show_menu()
            continue

        if command == 'l':
            output(['"Yeah, well... take \'er easy..." Skip mumbles.'], conn)
            return
        else:
            output(['"Eh? What?" Skip mutters.'], conn)


def skip_show_menu(conn: Player):
    output(["[H]ash (1 silver), [C]offee (5 silver), or [L]eave"], conn)


def vinny(conn: Player):
    """Loan shark"""
    output(["Vinny"], conn)


def zelda(conn: Player):
    """Madame Zelda, the fortune-teller"""
    bar_zelda.main()
    return


def fat_olaf(conn: Player):
    output(["The slave trader Fat Olaf sits behind a table, gnawing a chicken leg."], conn)
    if conn.flag["expert_mode"] is False:
        print()
        output(['"I buy und sell servants yu can add tu your party! '
                'They need tu be fed und paid on a veekly basis '
                'tu remain loyal tu yu, though! I kin alzo strengthen '
                'your allies, for a fee."'], conn)
        print()
        fat_olaf_menu(conn)
    while True:
        print()
        command, last_command = input_prompt("Vot kin I du ver ya?", help=True)
        if command == '' or command == 'l':
            output(['"Hokey dokey." Fat Olaf watches you leave.'], conn)
            return

        if command == "?":
            fat_olaf_menu(conn)
            continue
        if command in ["b", "s", "m"]:
            output(["[FIXME]: That hasn't been written yet."], conn)
            continue
        else:
            output(['Fat Olaf looks puzzled. "Vot?"'], conn)


def fat_olaf_menu(conn: Player):
    output(["[B]uy, [S]ell, [M]aintain, [L]eave"], conn)
    return


def bar_none(conn: Player):
    output(["Exception raised: NO_FLAVOR_TEXT"], conn)


def horizontal_ruler(conn: Player, bar):
    # TODO: This will come in handy for text editor .Column display

    #           1         2         3         4
    # 01234567890123456789012345678901234567890 etc.
    ruler_length = len(bar[0])
    digits = "0123456789"
    text = ["    "]
    highest_tens_digit = int(str(ruler_length)[0])
    for tens in range(1, highest_tens_digit + 1):
        text.append(f'{tens:> 10}')
    output(["".join(text)], conn)
    output([f"   {(digits * 10)[:ruler_length]}"], conn)


def show_main_menu(conn: Player, go_here: bool):
    # TODO: grab these options from the functions themselves
    extra = ", [G]o here" if go_here else ''
    output([f"   Dirs: [N]orth, [E]ast, [S]outh, [W]est, [Q]uit{extra}",
            "Toggles: [D]ebug, [T]ranslation, e[X]pert Mode, [M]ore [P]rompt",
            "  Tests: [O]utput word-wrap, [M]ore Prompt"], conn)


def main(conn: Player):
    locations = [(0, 6, "Exit", None),
                 (1, 4, "The Blue Djinn", blue_djinn),
                 (1, 8, "Vinny the Loan Shark", vinny),
                 (2, 4, "Skip's Eats", skip),
                 (2, 5, "Bar None", bar_none),
                 (3, 8, "Fat Olaf's Slave Trade", fat_olaf),
                 (4, 8, "Madame Zelda's", zelda)]

    if conn.client['translation'] == 'PetSCII':
        # code page 437 / Commodore PetSCII graphics
        bar = ["┌────┤ ├────┐",
               "│o[]     []o│",
               "│           │",
               "│  ┌──┐  []o│",
               "│  │oo│  []o│",
               "└──┴──┴─────┘"]
        obstacles = ["─", "┤", "├", "│", "[", "]", "┌", "─", "┐"]
    else:
        # ASCII
        bar = ["+----| |----+",
               "|o[]     []o|",
               "|           |",
               "|  +--+  []o|",
               "|  |oo|  []o|",
               "+-----------+"]
        obstacles = ["+", "-", "|", '[', ']']

    # pos is zero-based from the top down, left-to-right
    pos_y = 0  # row
    pos_x = 6  # column

    window_size = shutil.get_terminal_size()

    output(['You stand in the doorway of a smoky bar. A faded sign reads: "WALL BAR AND GRILL."'],
           conn)

    while True:
        print()
        if conn.flag["debug"]:
            horizontal_ruler(conn, bar)
        for count, line in enumerate(bar):
            text = []
            if conn.flag["debug"]:
                text.append(f'{count: 2} ')
            if count == pos_y:
                text.append(f'{line[:pos_x]}X{line[pos_x + 1:]}')
            else:
                text.append(line)
            output(text, conn)
            # print("".join(text))
        go_here = False
        valid_move = False

        for place in locations:
            # sorted by rows
            if pos_y == place[0] and pos_x == place[1]:
                text = [f'{place[2]}']
                if conn.flag["debug"]:
                    text.append(f"  {place[3]}")
                output(["".join(text)], conn, bracket_coloring=False)
                go_here = True
                go_routine = place[3]

        if conn.flag["debug"]:
            output([f'{pos_x=}, {pos_y=}'], conn)

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
                    output([f"{opponent} something something..."], conn)
            else:
                output(['"Well then, [WATCH] it!"'], conn)

        if conn.flag['expert_mode'] is False:
            show_main_menu(conn, go_here)
            output([f"[{conn.client['return_key']}] = '{conn.last_command}'"], conn)

        output([f"[HP: {conn.hit_points}]"], conn)
        # parser:
        command, last_command = input_prompt("Which way?")
        move_into_obstacle = False

        if command == '?':
            show_main_menu(conn, go_here)
            valid_move = True

        if command == "g":
            if go_here:
                valid_move = True
                # NOTE: exit doesn't have a function
                if callable(go_routine):
                    go_routine()
                    print()
                    continue

                else:
                    output(f"Can't hack it, man. {go_routine} isn't callable.")
            if conn.flag['debug']:
                valid_move = False
                while valid_move is False:
                    num_places = len(locations)
                    for i, k in enumerate(locations):
                        print(f'{i} {k[2]}')
                    option, _ = input_prompt("Quick move:", help=False)
                    place = int(option)
                    if 1 > place > num_places:
                        output("Aborting.")
                        break  # out of the loop
                    where = locations[place]
                    pos_y, pos_x = where[0], where[1]
                    print(f"Quick moving to {where[2]}.")
                    valid_move = True

        # toggles:
        if command == 'd':
            conn.flag['debug'] = not conn.flag['debug']
            output(f"Debug info is now {'On' if conn.flag['debug'] else 'Off'}.")
            valid_move = True

        if command == 'x':
            conn.flag['expert_mode'] = not conn.flag['expert_mode']
            output([f"Expert Mode is now {'On' if conn.flag['expert_mode'] else 'Off'}."], conn)
            valid_move = True

        if command == "mp":
            conn.flag['more_prompt'] = not conn.flag['more_prompt']
            output([f"More Prompt is now {'On' if conn.flag['more_prompt'] else 'Off'}."], conn)
            valid_move = True

        if command == 't':
            kind = ''
            temp = conn.client['translation']
            if temp == 'PetSCII':
                kind = "ASCII"
                conn.client['translation'] = kind
            elif temp == 'ASCII':
                kind = "PetSCII"
                conn.flag['expert_mode'] = not conn.flag['expert_mode']
                conn.client['translation'] = kind
            output([f"(Translation type changed to '{kind}'.)"], conn)
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

            _ = input("Okay? ")
            # valid_move = True  # because Latin is incomprehensible :)

        # regular commands:
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
            Player.hit_points -= 1
            if Player.hit_points <= 0:
                output(["You have died."], conn=Player)
                # TODO: room_notify(f"{player.name} dies from bumping into something.")
                break  # out of loop
            continue  # suppress the following message

        if valid_move:
            last_command = command
        else:
            output("The bar patrons look at you strangely as you do something incomprehensible.")
            last_command = "?"
            # TODO: room_notify(f"{player.name} is confused.")


if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    main()
