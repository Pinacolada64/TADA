bar = ["********************",
       "*                  *",
       "*                  *",
       "*******      *******",
       "*     *      *     *",
       "*                  *",
       "*     *      *     *",
       "********************"
       ]

# pos is zero-based from the top down, left-to-right
pos_y = 3  # row
pos_x = 9  # column


def horizontal_ruler():
    #           1         2         3         4
    # 01234567890123456789012345678901234567890 etc.
    digits = "0123456789"
    ruler_length = len(bar[0])
    numbering = True
    if numbering:
        print("   ", end='')
    print(" ", end='')  # extra space for first '0'
    highest_tens_digit = int(str(ruler_length)[0])
    for tens in range(1, highest_tens_digit + 1):
        print(f'{tens:> 10}', end='')
    print()
    if numbering:
        print("   ", end='')
    print((digits * 10)[:ruler_length])


while True:
    count = 0
    horizontal_ruler()
    for line in bar:
        print(f'{count: 2} ', end='')
        if count == pos_y:
            print(f'{line[:pos_x]}X{line[pos_x + 1:]}')
        else:
            print(line)
        count += 1

    print(f'{pos_x=}, {pos_y=}')
    direction = input("Which way? ").lower()
    print()
    valid_move = False

    if direction == 'n':
        # look up for obstacle:
        obstacle = bar[pos_y - 1][pos_x]
        if obstacle != "*":
            pos_y -= 1
            valid_move = True

    if direction == 's':
        # look down for obstacle:
        obstacle = bar[pos_y + 1][pos_x]
        if obstacle != "*":
            pos_y += 1
            valid_move = True

    if direction == 'e':
        # look right for obstacle:
        obstacle = bar[pos_y][pos_x + 1]
        if obstacle != "*":
            pos_x += 1
            valid_move = True

    if direction == 'w':
        # look left for obstacle:
        obstacle = bar[pos_y][pos_x - 1]
        if obstacle != "*":
            pos_x -= 1
            valid_move = True

    if direction == "q":
        break

    if valid_move is False:
        print("You can't go that way.\n")
