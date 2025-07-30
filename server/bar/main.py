import logging
from dataclasses import dataclass
from pprint import pprint

# TADA imports:
from player import Player
from flags import PlayerFlags
from tada_utilities import input_yes_no


def bouncer(character: "Player"):
    """
    Mundo the bouncer gets personal with the player.
    Also called when the Blue Djinn is insulted.
    """
    # if player's HP < 5, don't attack with baseball bat:
    action = ''
    if character.hit_points > 5:
        action = "knocks you over the head with a baseball bat, and "
        # TODO: write 'character.adjust_hp' and put check for >=0 HP there...
        character.hit_points -= 5
    character.output(f"At a signal, Mundo {action}throws you out into the street...")
    bar.pos_y, bar.pos_x = 0, 6
    bar.valid_move = True  # to redisplay bar map


def skip(player: Player):
    import bar.skip
    bar.skip.main(player)


def vinny(character: Player):
    """Loan shark"""
    character.output("Vinny")


def fat_olaf(character: Player):
    import bar.fat_olaf
    bar.fat_olaf.main(character)


def zelda(character: Player):
    """
    * Spy on player's stats
    * Raise other players' dead monsters
    """
    import bar.zelda
    bar.zelda.main(character)


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


def horizontal_ruler(player: Player):
    """Display a horizontal ruler for x-position debugging"""
    #           1         2         3         4
    # 01234567890123456789012345678901234567890 etc.
    # TODO: This will come in handy for text editor .Column display
    bar_map = Bar.bar_map[player.client_settings.translation]
    ruler_length = len(bar_map[0])
    digits = "0123456789"
    print("   ", end='')
    print(" ", end='')  # extra space for first '0'
    highest_tens_digit = int(str(ruler_length)[0])
    for tens in range(1, highest_tens_digit + 1):
        print(f'{tens:> 10}', end='')
    print()
    print("   ", end='')
    print((digits * 10)[:ruler_length])


def prompt(character: Player, prompt_string: str):
    """
    Prompt user for something, accept input

    :param character: Player to prompt, also for client_settings.return_key string
    :param prompt_string: string to prompt for, minus space at end
    :return: tuple(previous_command, command) command: leftmost char of input, lowercase
    """
    temp = input(f"{character.output(prompt_string)}: ")
    character.output("")
    if temp != '':
        command = temp[0].lower()
        character.previous_command = command
    if temp == '' and character.previous_command:
        command = character.previous_command
        if not character.query_flag(PlayerFlags.EXPERT_MODE):
            character.output(f"(Repeating '{command}'.)")
    return character.previous_command, character.command


def bar_help(character: Player):
    character.output(["This is the Wall Bar & Grill, a place where you (and your party, if you "
                      "have others with you) can find food, drink, and various services to help "
                      "yourself--or harm others, if you wish--in the Land.",
                      "",
                      "In the map of the bar:",
                      "",
                      # all text in a bulleted list item [handled by format_bulleted_text()] should be
                      # a single string to correctly indent text on subsequent_indent lines:
                      "* 'o' represents each person you can interact with, by moving in front "
                      "(or to the side) of them, then typing [G]o here.",
                      "* [] represents a desk sitting in front of the person.",
                      "* 'M' represents Mundo, the bar bouncer.",
                      "* Lastly, 'X' represents you (plus your party, if applicable)."])


def bar_none(character: Player):
    logging.info("Calling bar_none module")
    import bar.bar_none
    bar.bar_none.main(character)


def blue_djinn(character: Player):
    logging.info("Calling blue_djinn module")
    import bar.blue_djinn
    bar.blue_djinn.main(character)


def show_menu(character: Player):
    go_here = ", [G]o here" if bar.can_go_here else ''
    character.output([f"[N]orth, [E]ast, [S]outh, [W]est{go_here}, [H]elp, [Q]uit",
                      "Toggles: [D]ebug, e[X]pert Mode"])


@dataclass
class Bar(object):
    from terminal import Translation
    # initial x-coordinate of player:
    pos_x: int = 6
    # initial y-coordinate of player:
    pos_y: int = 0
    # True: a person to interact with is in an adjacent square
    # and '[G]o Here' will be shown in the hotkey options
    can_go_here: bool = False

    valid_move: bool = True

    # 'M' is the marker for Mundo, the bar's bouncer
    # 'o' is the marker for various NPCs sitting behind tables
    bar_map = {Translation.ASCII: ["+----| |----+",
                                   "|o[]     []o|",
                                   "|          M|",
                                   "|  +--+  []o|",
                                   "|  |oo|  []o|",
                                   "+-----------+"
                                   ],
               # https://en.wikipedia.org/wiki/Box-drawing_characters
               Translation.ANSI: ["┌────┤ ├────┐",
                                  "│o[]     []o│",
                                  "│          M│",
                                  "│  ┌──┐  []o│",
                                  "│  │oo│  []o│",
                                  "└──┴──┴─────┘"
                                  ]}

    # tuple is: y-coordinate, x-coordinate, name, routine to call:
    # TODO: if Expert Mode off, display a letter instead of 'o'
    locations = [(0, 6, "Exit", None),
                 (1, 4, "The Blue Djinn", blue_djinn),
                 (1, 8, "Vinny the Loan Shark", vinny),
                 (2, 4, "Skip's Eats", skip),
                 (2, 5, "Bar None", bar_none),
                 (3, 8, "Fat Olaf's Slave Trade", fat_olaf),
                 (4, 8, "Madame Zelda's", zelda)]


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Logging is running")

    # instantiate Player
    rulan_settings = {'name': 'Rulan'}
    rulan = Player(**rulan_settings)
    rulan.client_settings.screen_columns = 80

    rulan.clear_flag(PlayerFlags.EXPERT_MODE)  # set to False
    rulan.set_flag(PlayerFlags.DEBUG_MODE)  # set to True

    # once-per-day activities:
    rulan.once_per_day = []

    # must be assigned for 'global' in prompt() to work:
    rulan.command = None
    rulan.previous_command = None

    rulan.hit_points = 20

    # instantiate Bar, place player at (x=6, y=0)
    bar = Bar()

    apostrophe = "'"

    rulan.output(['You stand in the doorway of a smoky bar. A faded sign hanging on the wall above you reads: '
                  '"WALL BAR AND GRILL."', ""])

    if not rulan.query_flag(PlayerFlags.EXPERT_MODE):
        bar_help(rulan)

    bar_map = Bar.bar_map[rulan.client_settings.translation]
    obstacles = {char for line in bar_map for char in line if char != ' '}

    while True:
        rulan.output("")
        if rulan.query_flag(PlayerFlags.DEBUG_MODE):
            horizontal_ruler(rulan)
        for count, line in enumerate(bar_map):
            if rulan.query_flag(PlayerFlags.DEBUG_MODE):
                print(f'{count: 2} ', end='')
            if count == bar.pos_y:
                print(f'{line[:bar.pos_x]}X{line[bar.pos_x + 1:]}')
            else:
                print(line)

        # look through 'locations' tuple to see if the player is in an
        # interactive spot
        bar.can_go_here = False
        _ = []
        for place in bar.locations:
            # sorted by rows
            if bar.pos_y == place[0] and bar.pos_x == place[1]:
                _.append(f'{place[2]}')  # name
                if rulan.query_flag(PlayerFlags.DEBUG_MODE):
                    _.append(f"  function: {place[3]}")  # function
                rulan.output(" ".join(_))
                bar.can_go_here = True
                bar.go_routine = place[3]

        if rulan.query_flag(PlayerFlags.DEBUG_MODE):
            rulan.output(f'(x: {bar.pos_x}, y: {bar.pos_y})')

        bump = False
        opponent = None
        text = None
        if bar.pos_y == 2 and bar.pos_x == 1:
            bump = True
            opponent = "The Blue Djinn"
            text = 'eyes you, hissing. "Are'
        if bar.pos_y == 2 and bar.pos_x == 10:
            # getting too close to Vinny the loan shark:
            bump = True
            opponent = "Mundo the bouncer"
            text = 'looks up from the floor. "Hey,'
        if bump:
            response = input_yes_no(f'{opponent} {text} you looking for a fight?"')
            if response:
                if opponent.startswith("Mundo"):
                    bouncer(rulan)  # also called from blue djinn
                    continue
                else:
                    # TODO: Blue Djinn: finish this
                    rulan.output(f"{opponent} something something...")
            else:
                rulan.output(f'"Well then, [watch] it!" {opponent} glares at you.')

        if not rulan.query_flag(PlayerFlags.EXPERT_MODE):
            show_menu(character=rulan)
            if rulan.previous_command:
                repeat_command = f"'{rulan.previous_command}'" if rulan.previous_command is not None else 'Invalid command'
                rulan.output(f"[{rulan.client_settings.return_key.value}] = '{repeat_command}'")

        print(f"[HP: {rulan.hit_points}] ", end='')
        # parser:
        rulan.command, rulan.previous_command = prompt(rulan, "What now?")
        rulan.output("")

        move_into_obstacle = False

        if rulan.command == '?':
            show_menu(rulan)

        if rulan.command == 'h':
            bar_help(rulan)

        if bar.can_go_here and rulan.command == "g":
            # exit doesn't have a function
            if callable(bar.go_routine):
                # FIXME:  mutable parameter list
                bar.go_routine(rulan)  # call routine with Character object
                print()

        if rulan.command == 'd':
            rulan.toggle_flag(PlayerFlags.DEBUG_MODE, verbose=True)
            rulan.output("")

        if rulan.command == 'x':
            rulan.toggle_flag(PlayerFlags.EXPERT_MODE, verbose=True)
            rulan.output("")

        if rulan.command == 'n':
            # look up for an obstacle:
            obstacle = bar_map[bar.pos_y - 1][bar.pos_x]
            if obstacle not in obstacles:
                bar.pos_y -= 1
                bar.valid_move = True
            else:
                bar.move_into_obstacle = True

        if rulan.command == 's':
            # look down for an obstacle:
            obstacle = bar_map[bar.pos_y + 1][bar.pos_x]
            if obstacle not in obstacles:
                bar.pos_y += 1
            else:
                move_into_obstacle = True

        if rulan.command == 'e':
            # look right for an obstacle:
            obstacle = bar_map[bar.pos_y][bar.pos_x + 1]
            if obstacle not in obstacles:
                bar.pos_x += 1
            else:
                move_into_obstacle = True

        if rulan.command == 'w':
            # look left for an obstacle:
            obstacle = bar_map[bar.pos_y][bar.pos_x - 1]
            if obstacle not in obstacles:
                bar.pos_x -= 1
            else:
                move_into_obstacle = True

        if rulan.command == "q":
            break

        if move_into_obstacle:
            rulan.output("Laughter fills the bar as you attempt to move through solid objects.")
            rulan.hit_points -= 1
            if rulan.hit_points <= 0:
                rulan.output("You have died.")
                # TODO: room_notify(f"{player.name} dies from bumping into something.")
                break  # out of loop
            continue  # suppress the following message

        if bar.valid_move:
            rulan.previous_command = rulan.previous_command
        else:
            # valid_move has been set to False above
            rulan.output("The bar patrons look at you strangely as you do something incomprehensible.")
            rulan.previous_command = None
            # TODO: room_notify(f"{player.name} is confused.")
