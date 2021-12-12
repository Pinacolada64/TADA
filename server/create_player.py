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


def choose_name(player: Player):
    """choose (or update existing) player name"""
    if player.name:
        # this is repeated, so function:
        enter_name(player=player, edit_mode=True)

    elif player.name is None:
        # no existing name, prompt for new character name
        player.name = enter_name(player=player, edit_mode=False)

        print(f'{player.name}')


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
            print(f'(Keeping the name of {temp}.)')
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
    """choose (or update existing) client type"""
    if player.client['type']:
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
            player.client['type']: 'Commodore 64'
            player.client['columns']: 40
            player.client['rows']: 25
            player.client['translation']: 'PETSCII'
        elif temp == "2":
            player.client['type']: 'Commodore 128'
            player.client['columns']: 80
            player.client['rows']: 25
            player.client['translation']: 'PETSCII'
        elif temp == "3":
            player.client['type']: 'TADA Client'
            player.client['columns']: 80
            player.client['rows']: 25
            player.client['translation']: "ASCII"

        print(f"Terminal: {player.client['type']}")


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

    player = Player(name=None, connection_id=1,
                    client={'type': 'Commodore 128', 'columns': 80, 'translation': 'PETSCII'},
                    # these are enabled for debugging info:
                    flags={'dungeon_master': True, 'debug': True, 'expert_mode': False}
                    )

    choose_name(player=player)

    choose_client(player=player)  # TODO: net_server

    output(text="Done!", player=player)
