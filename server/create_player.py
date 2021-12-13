import textwrap

from players import Player

from random import randrange  # for age and generating random stats

# import cbmcodecs2
# FIXME: broken package
"""
Traceback (most recent call last):
    File "<string>", line 1, in <module>
    UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 2537: character maps to <undefined>
"""


# https://docs.python.org/3/library/collections.html


def choose_gender(player: Player):
    """step 1: choose character gender"""
    print('Verus squints myopically. "Are you a male or female?"')
    while True:
        temp = input("Enter [M]ale or [F]emale: ").lower()
        if temp == 'm':
            player.gender = 'male'
            break
        if temp == 'f':
            player.gender = 'female'
            break


def edit_gender(character: Player):
    """toggle existing character gender"""
    while True:
        # FIXME: this is probably a dirty hack
        if character.gender == 'female':
            character.gender = 'male'
            break
        if character.gender == 'male':
            character.gender = 'female'
            break
    print(f"{character.name} is now {character.gender}.")


def choose_name(player: Player):
    """step 2: choose character name"""
    if player.name:
        # this is repeated, so function:
        enter_name(player=player, edit_mode=True)

    elif player.name is None:
        # no existing name, prompt for new character name
        player.name = enter_name(player=player, edit_mode=False)

        print(f'{player.name}')


def edit_name(player: Player):
    """update character name"""
    player.name = enter_name(player, edit_mode=True)


def enter_name(player: Player, edit_mode: bool):
    """
    change player name. this can also be called during final player edit menu

    :param player: player object
    :param edit_mode: True: editing existing name
                        False: no name assigned, entering new name
    :return: name (str)
    """
    if edit_mode is True:
        print(f"Editing existing name '{player.name}'.")
    print("([Q] quits", end='')
    if edit_mode is True:
        print(f", Return/Enter keeps existing name", end='')
    print(")")
    # TODO: this should be written as a generic edit prompt
    temp = input("What is your name: ")
    if edit_mode:
        # Return hit, or new string = old string:
        if temp == "" or temp == player.name:
            temp = player.name
            print(f"(Keeping the name of '{temp}'.)")
    if temp.lower() == 'q':
        print("'Quit' selected.")
    print(f'Verus checks to see if anyone else has heard of "{temp}" around here...')
    # TODO: check for existing name
    print(f"Seems to be okay. He ", end='')
    if edit_mode and player.name != temp:
        print("scratches out your old name and re-writes it", end='')
    else:
        print("scribbles your name", end='')
    print(" in a dusty book.")
    return temp


def choose_client(player: Player):
    global return_key
    """step 0: choose (or update existing) client name and parameters"""
    logging.info(f"{player.client['name']}")
    if player.client['name']:
        options = 3
        # FIXME: this unintentionally wraps text (as it's supposed to) but loses newlines
        """
        output(text=f'''Using output():\n\n
        "Which kind of client are you using, {player.name}?" Verus asks.\n\n
        \n\n
        ## Client type     Screen size
        -- --------------- -----------
        1. Commodore 64    (40 x 25)\n
        2. Commodore 128   (80 x 25)\n
        3. TADA client\n
        ''', player=character)
        """
        print(f'''"Which kind of client are you using, {player.name}?" Verus asks.

        ## Client type     Screen size
        -- --------------- -----------
        1. Commodore 64    (40 x 25)
        2. Commodore 128   (80 x 25)
        3. TADA client
        ''')

        temp = input(f"Which client (1-{options}, [Q]uit): ").lower()

        if temp == "q":
            # FIXME
            pass

        elif temp == "1":
            player.client['name']: 'Commodore 64'
            player.client['columns']: 40
            player.client['rows']: 25
            player.client['translation']: 'PETSCII'
            bla = player.client['name']
            return_key = 'Return'
            logging.info(f'1: Client set to {bla}.')
        elif temp == "2":
            player.client['name']: 'Commodore 128'
            player.client['columns']: 80
            player.client['rows']: 25
            player.client['translation']: 'PETSCII'
            return_key = 'Return'
        elif temp == "3":
            player.client['name']: 'TADA Client'
            player.client['columns']: 80
            player.client['rows']: 25
            player.client['translation']: "ASCII"
            return_key = 'Enter'

        # FIXME: until below code gets fixed, {return_key} will be "Enter"
        if player.client['translation'] == "PETSCII":
            return_key = "Return"
        else:
            return_key = "Enter"
        print(f"Client: {player.client['name']}")


def edit_client(player: Player):
    pass


def choose_class(player: Player):
    """step 3a: choose player class"""
    # NOTE: Player object 'class' attribute conflicts with built-in keyword
    # I am naming it char_class instead
    display_classes()
    player.char_class = "fixme"
    print("TODO: choose class")


def display_classes():
    print('''"Choose a class," Verus instructs.

    (1) Wizard   (4) Paladin  (7) Archer
    (2) Druid    (5) Ranger   (8) Assassin
    (3) Fighter  (6) Thief    (9) Knight

    FINISH ME''')
    # TODO: Should be a help function to get help about individual classes.
    # Whether it's called up with "H1" or "1?" is undetermined.


def edit_class(player: Player):
    while True:
        display_classes()
        print(f'Current class: {player.char_class}. [{return_key}] keeps this.')
        print(f'TODO: edit and validate.')
        break


def validate_class_race_combo(self, player: Player):
    """make sure class/race combination are allowed"""
    bad_combination = False

    # list of bad combinations:
    if player.char_class == 'wizard':
        if player.race in ['ogre', 'dwarf', 'orc']:
            bad_combination = True

    elif player.char_class == 'druid':
        if player.race in ['ogre', 'orc']:
            bad_combination = True

    elif player.char_class == 'thief':
        if player.race == 'elf':
            bad_combination = True

    elif player.char_class == 'archer':
        if player.race in ['ogre', 'gnome', 'hobbit']:
            bad_combination = True

    elif player.char_class == 'assassin':
        if player.race in ['gnome', 'elf', 'hobbit']:
            bad_combination = True

    elif player.char_class == 'knight':
        if player.race in ['ogre', 'orc']:
            bad_combination = True

    if bad_combination:
        print("Bad combination.")
    else:
        print('"Okay, fine with me," agrees Verus.')


def choose_race(player: Player):
    """step 3b: choose player race"""
    display_races()
    player.race = "temp"


def display_races():
    print('''"Choose a race," Verus instructs.
    
    (1) Human    (4) Elf      (7) Dwarf
    (2) Ogre     (5) Hobbit   (8) Orc
    (3) Gnome    (6) Halfling (9) Half-Elf

    FINISH ME''')
    # TODO: Should be a help function to get help about individual races.
    # Whether it's called up with "H1" or "1?" is undetermined.


def edit_race(player: Player):
    while True:
        display_races()
        print(f'Current race: {player.race}. [{return_key}] keeps this.')
        print(f'TODO: edit and validate.')
        break


def choose_age(player: Player):
    """
    step 4: allow player to select age and birthday

    if player.age = 0, it is displayed as 'Unknown'
    """
    while True:
        print('"Enter [0] to be of an unknown age."')
        print('"Enter [R] to select a random age between 15-50."\n')
        temp = input("Enter your age (0, R or 15-50): ")
        if temp.lower() == 'r':
            player.age = randrange(15, 50)
            break
        if temp.isalpha():
            print('Verus tsks. "Please enter a number."')
        temp = int(temp)
        if temp == 0:
            """
            I think this is mostly for when people LOOK at your character:
            
            Looking at Railbender, you see a man of unknown age.
            
            Not entirely sure, though.
            """
            player.age = 0
            print('Verus studies you, and comments: "You\'re of an unknown age."')
            break

        valid = validate_age(temp)
        if valid:
            player.age = temp
            print(f'Verus remarks, "You\'re {player.age} years of age."')
            break
        print('"Try again," suggests Verus.')
    print("TODO: Choose birthday")


def edit_age(player: Player):
    pass


def validate_age(age: int):
    if age < 15:
        print("\"Oh, come off it! You're not even old enough to handle a "
              'Staff yet! Get real!"')
        return False
    if age > 50:
        print('"Hmmm, we seem to be out of Senior Adventurer life '
              'insurance policies right now. Come back tomorrow!"')
        return False
    return True


def final_edit(player: Player):
    """allow player another chance to view/edit characteristics before saving"""
    print(f"Summary of character '{player.name}':")
    options = 5
    while True:
        print()
        print(f'1.    Name: {player.name}')
        print(f'2.  Gender: {player.gender.title()}')
        print(f'3.   Class: {player.char_class.title()}')
        print(f'4.    Race: {player.race.title()}')
        if player.age == 0:
            temp = "Unknown"
        else:
            temp = player.age
        print(f'5.     Age: {temp}')
        print(f"  Birthday: player.birthday")
        print()

        temp = input(f"Option [1-{options}, {return_key}=Done]: ")
        print()
        if temp == '1':
            edit_name(player)
        if temp == '2':
            edit_gender(player)
        if temp == '3':
            edit_class(player)
        if temp == '4':
            edit_race(player)
        if temp == '5':
            choose_age(player)
        if temp == '':
            break


def header(text: str):
    print()
    print(text)
    print("-" * len(text))
    print()


def output(player: Player, text: str):
    """
    Print 'text' word-wrapped to <columns> characters to Player:

    :param player: Player to output text to
    :param text: string to output
    :return: none

    TODO: implement cbmcodec2 ASCII -> PETSCII translation
    """
    if player.client['translation'] == 'PETSCII':
        pass  # until cbmcodecs2 is fixed
    print('\n'.join(textwrap.wrap(text, width=player.client['columns'])))


if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    logging.info("Logging is running")

    connection_id = 1
    # FIXME: initially, we wouldn't know which Player object to output it to (hasn't been created yet)
    #  so use IP address?  will use standard print() here until Player object is established

    character = Player(name=None, connection_id=1,
                       client={'name': 'Commodore 128', 'columns': 80, 'translation': 'PETSCII'},
                       # these are enabled for debugging info:
                       flags={'dungeon_master': True, 'debug': True, 'expert_mode': False},
                       silver={'in_hand': 1000}
                       )

    header("Introduction")
    print("Your faithful servant Verus appears at your side, as if by magic.")
    print('Verus mentions, "Do not worry if ye answer wrong, ye can change thy answer later."')

    header("0. Choose Client")
    choose_client(player=character)  # TODO: net_server handles this

    header("I. Choose Gender")
    choose_gender(player=character)

    header("II. Choose Name")
    choose_name(player=character)

    header("III. Choose Class")
    choose_class(player=character)

    header("IV. Choose Race")
    choose_race(player=character)

    header("V. Choose Age")
    choose_age(player=character)

    header("VI. Final Edit")
    final_edit(player=character)

    output(text="Done!", player=character)
