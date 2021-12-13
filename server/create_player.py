from players import Player
import textwrap

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
    if character.gender == 'female':
        character.gender = 'male'
        return
    if character.gender == 'male':
        character.gender = 'female'
        return
    raise ValueError


def choose_name(player: Player):
    """step 2: choose (or update existing) player name"""
    if player.name:
        # this is repeated, so function:
        enter_name(player=player, edit_mode=True)

    elif player.name is None:
        # no existing name, prompt for new character name
        player.name = enter_name(player=player, edit_mode=False)

        print(f'{player.name}')


def edit_name(player=Player):
    pass


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
    temp = input("What is your name: ")
    if edit_mode:
        if temp == "":
            temp = player.name
            print(f"(Keeping the name of '{temp}'.)")
    if temp.lower() == 'q':
        print("'Quit' selected.")
    print(f'Verus checks to see if anyone else has heard of "{temp}" around here...')
    # TODO: check for existing name
    print(f"Seems to be okay. He ", end='')
    if edit_mode:
        print("scratches out your old name and re-writes it", end='')
    else:
        print("scribbles", end='')
    print(" your name in a dusty book.")
    return temp


def choose_client(player: Player):
    global return_key
    """step 0: choose (or update existing) client name"""
    logging.info(f"{player.client['name']}")
    if player.client['name']:
        options = 3
        # FIXME: this unintentionally wraps text (as it's supposed to) and loses formatting
        # output(text=f'''
        # "Which kind of client are you using, {player_name}?" Verus asks.
        #
        # 1. Commodore 64    (40x25)
        # 2. Commodore 128   (80x25)
        # 3. TADA client
        # ''', player=player_name)

        print(f'''
        "Which kind of client are you using, {player.name}?" Verus asks.

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
        if player.client == "PETSCII":
            return_key = "Return"
        else:
            return_key = "Enter"
        print(f"Client: {player.client['name']}")


def edit_client(player=Player):
    pass


def choose_class(player: Player):
    """step 3a: choose player class"""
    print('''
"Choose a class," Verus instructs.

    (1) Wizard   (4) Paladin  (7) Archer
    (2) Druid    (5) Ranger   (8) Assassin
    (3) Fighter  (6) Thief    (9) Knight

    FINISH ME
''')


def edit_class(player=Player):
    pass


def choose_race(player: Player):
    """step 3b: choose player race"""
    print('''
"Choose a race," Verus instructs.
    
    (1) Human    (4) Elf      (7) Dwarf
    (2) Ogre     (5) Hobbit   (8) Orc
    (3) Gnome    (6) Halfling (9) Half-Elf

    FINISH ME
''')


def edit_race(player):
    pass


def choose_age(player: Player):
    """
    step 4: allow player to select age and birthday

    if player.age = 0, it is displayed as 'Unknown'
    """
    player.age = 0
    print("TODO: Choose age/birthday")


def edit_age(player):
    pass


def final_edit(player: Player):
    """allow player another chance to view/edit characteristics before saving"""
    print(f"Summary of character '{player.name}':")
    options = 2
    while True:
        print()
        print(f'1.    Name: {player.name}')
        print(f'2.  Gender: {player.gender.title()}')
        print()
        temp = input(f"Option [1-{options}, {return_key}=Done]: ")
        if temp == '1':
            edit_name(player)
        if temp == '2':
            edit_gender(player)
        if temp == '':
            break


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
    print("Your faithful servant Verus appears at your side, as if by magic.")

    character = Player(name=None, connection_id=1,
                       client={'name': 'Commodore 128', 'columns': 80, 'translation': 'PETSCII'},
                       # these are enabled for debugging info:
                       flags={'dungeon_master': True, 'debug': True, 'expert_mode': False},
                       silver={'in_hand': 1000}
                       )

    choose_client(player=character)  # TODO: net_server handles this
    choose_gender(player=character)
    choose_name(player=character)
    choose_class(player=character)
    choose_race(player=character)

    final_edit(player=character)

    output(text="Done!", player=character)
