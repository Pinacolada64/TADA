bar = ["+----+ +----+",
       "|o[]     []o|",
       "|           |",
       "|--+     []o|",
       "|oo|     []o|",
       "+-----------+"
       ]


def blue_djinn():
    print("Blue Djinn function")


def vinny():
    print("Vinny")


def skip():
    print("Skip sweats over a hot grill, muttering to himself.")


def fat_olaf():
    print("The slave trader Fat Olaf sits behind a table, gnawing a chicken leg.")
    if flag["expert_mode"] is False:
        print('''
"I buy und sell servants yu can add tu your party!
They need tu be fed und paid on a veekly basis tu remain loyal tu yu, though!"
''')
    while True:
        choice = input("Vot kin I du ver ya?")[0].lower()
        if choice == "?":
            print(f"[B]uy, [S]ell, [M]aintain, [L, {terminal['return_key']}] Leave")
            continue
        if choice == '' or choice == "l":
            print('"Hokey dokey." Fat Olaf watches you leave.')
            return
        else:
            print('Fat Olaf looks puzzled. "Vot?"')


def bar_none():
    print("Exception raised: NO_FLAVOR_TEXT")


def zelda():
    print("Madame Zelda and her cat sit in front of a crystal ball.")
    print('"What dooooo you wish?"')


def horizontal_ruler():
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


# main()

# y, x, name, routine to call:
locations = [(0, 6, "Exit", None),
             (1, 4, "The Blue Djinn", blue_djinn),
             (1, 8, "Vinny the Loan Shark", vinny),
             (2, 1, "Skip's Eats", skip),
             (3, 8, "Fat Olaf's Slave Trade", fat_olaf),
             (4, 4, "Bar None", bar_none),
             (4, 8, "Madame Zelda's", zelda)]

obstacles = ["+", "-", "|", '[', ']']

print("You stand in the doorway of a smoky bar. A faded sign reads:")
print('"WALL BAR AND GRILL."\n')

# pos is zero-based from the top down, left-to-right
pos_y = 0  # row
pos_x = 6  # column

terminal = {"type": "Commodore 64",
            "return_key": "Return"}

flag = {"expert_mode": False,
        "debug": True}

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
        # count += 1

    go_here = False
    for place in locations:
        # sorted by rows
        if pos_y == place[0] and pos_x == place[1]:
            print(f'{place[2]}', end='')
            if flag["debug"]:
                print(f"  function {place[3]}")
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
                print(f"At a signal, {opponent} ", end='')
                # if player's HP < 5, don't attack with baseball bat:
                if hp > 5:
                    print("knocks you over the head with a baseball bat, and ", end='')
                print("throws you out into the street...")
                hp -= 5
                pos_y, pos_x = 0, 6
            else:
                # TODO: Blue Djinn: finish this
                print(f"{opponent} something something...")
        else:
            print('"Well then, WATCH it!"')

    extra = ", [G]o here" if go_here else ''

    print(f"[N]orth, [E]ast, [S]outh, [W]est{extra}")
    print("Toggles: [D]ebug, e[X]pert Mode")
    print(f"HP: {hp}")
    direction = input("Which way? ")[0].lower()
    print()
    valid_move = False
    move_into_obstacle = False

    if go_here and direction == "g":
        valid_move = True
        # exit doesn't have a function
        if go_routine:
            go_routine()  # call routine
            print()
        # if callable(go_routine):
        #   go_routine  # does not work

        # except:
        #     print("Can't hack it, man.")

    if direction == 'd':
        flag['debug'] = not flag['debug']
        print(f"Debug info is now {'On' if flag['debug'] else 'Off'}.")
        valid_move = True

    if direction == 'x':
        flag['expert_mode'] = not flag['expert_mode']
        print(f"Expert Mode is now {'On' if flag['expert_mode'] else 'Off'}.")
        valid_move = True

    if direction == 'n':
        # look up for obstacle:
        obstacle = bar[pos_y - 1][pos_x]
        if obstacle not in obstacles:
            pos_y -= 1
            valid_move = True
        else:
            move_into_obstacle = True

    if direction == 's':
        # look down for obstacle:
        obstacle = bar[pos_y + 1][pos_x]
        if obstacle not in obstacles:
            pos_y += 1
            valid_move = True
        else:
            move_into_obstacle = True

    if direction == 'e':
        # look right for obstacle:
        obstacle = bar[pos_y][pos_x + 1]
        if obstacle not in obstacles:
            pos_x += 1
            valid_move = True
        else:
            move_into_obstacle = True

    if direction == 'w':
        # look left for obstacle:
        obstacle = bar[pos_y][pos_x - 1]
        if obstacle not in obstacles:
            pos_x -= 1
            valid_move = True
        else:
            move_into_obstacle = True

    if direction == "q":
        break

    if move_into_obstacle:
        print("Laughter fills the bar as you attempt to move through solid objects.\n")
        hp -= 1
        if hp <= 0:
            print("You have died.")
            # TODO: room_notify(f"{player.name} dies from bumping into something.")
            break
        valid_move = True  # suppress the following message

    if valid_move is False:
        print("The bar patrons look at you strangely as you do something incomprehensible.")
