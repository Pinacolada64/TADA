import textwrap

from players import Player

from random import randrange  # for age and generating random stats

from datetime import date  # for birthday displays/calculations

import calendar  # monthrange for validating # of days in month

# import cbmcodecs2
# FIXME: broken package
"""
Traceback (most recent call last):
    File "<string>", line 1, in <module>
    UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 2537: character maps to <undefined>
"""

# resources:
# https://docs.python.org/3/library/collections.html
# https://docs.python.org/3/library/datetime.html
# https://www.dataquest.io/blog/python-datetime-tutorial/


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
    print("([Q]uit", end='')
    if edit_mode is True:
        print(f", [{return_key}] keeps existing name", end='')
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
            print("quit selected")

        if temp == "1":
            print("Option 1")
            player.client['name'] = 'Commodore 64'
            player.client['columns'] = 40
            player.client['rows'] = 25
            player.client['translation'] = 'PETSCII'
        elif temp == "2":
            player.client['name'] = 'Commodore 128'
            player.client['columns'] = 80
            player.client['rows'] = 25
            player.client['translation'] = 'PETSCII'
        elif temp == "3":
            player.client['name'] = 'TADA Client'
            player.client['columns'] = 80
            player.client['rows'] = 25
            player.client['translation'] = "ASCII"

        # FIXME: until below code gets fixed, {return_key} will be "Enter"
        if player.client['translation'] == "PETSCII":
            return_key = "[Return]"
        else:
            return_key = "[Enter]"
        print(f"Client set to: {player.client['name']}")


def edit_client(player: Player):
    pass


def choose_class(player: Player):
    """step 3a: choose player class"""
    # NOTE: Player object 'class' attribute conflicts with built-in keyword
    # I am naming it char_class instead
    class_valid = False
    while class_valid is False:
        display_classes()
        temp = int(input("Class [1-9]: "))
        valid = 0 < temp < 10  # accept 1-9
        if valid:
            # first time answering this prompt, there is no race to validate against:
            player.char_class = ['wizard', 'druid', 'fighter', 'paladin', 'ranger',
                                 'thief', 'archer', 'assassin', 'knight'][temp-1]
            class_valid = True
        else:
            print('"Choose a class between 1 and 9," suggests Verus.')


def display_classes():
    print('''"Choose a class," Verus instructs.

    (1) Wizard   (4) Paladin  (7) Archer
    (2) Druid    (5) Ranger   (8) Assassin
    (3) Fighter  (6) Thief    (9) Knight
    ''')


def edit_class(character: Player):
    """
    this is called during final_edit() to change the class,
    then validate the resulting class/race combination
    """
    # TODO: combine common code in another method
    valid_class = False
    while valid_class is False:
        display_classes()
        # TODO: Should be a help function to get help about individual classes.
        # Whether it's called up with "H1" or "1?" is undetermined.
        print(f'{return_key} keeps {character.char_class.title()}.')
        """if the character creation process has only asked for the class so far,
        race will be None, and we shouldn't validate the combination"""
        temp = int(input("Class [1-9]: "))
        valid = 0 < temp < 10  # accept 1-9
        if valid:
            valid_class = validate_class_race_combo(player=character)
            if valid_class:
                # class/race combo is good, set class:
                character.char_class = ['wizard', 'druid', 'fighter', 'paladin',
                                        'ranger', 'thief', 'archer', 'assassin',
                                        'knight'][temp-1]
                # end outer loop
                break
        else:
            print('"Choose a class between 1 and 9," suggests Verus.')


def validate_class_race_combo(player: Player):
    """make sure selected class/race combination is allowed
    :param player: Player object to validate class and race of
    :returns: True if an acceptable combination, False if not"""
    ok_combination = True
    logging.info("validate_class_race_combo reached")

    # list of bad combinations:
    if player.char_class == 'wizard':
        if player.race in ['ogre', 'dwarf', 'orc']:
            ok_combination = False

    elif player.char_class == 'druid':
        if player.race in ['ogre', 'orc']:
            ok_combination = False

    elif player.char_class == 'thief':
        if player.race == 'elf':
            ok_combination = False

    elif player.char_class == 'archer':
        if player.race in ['ogre', 'gnome', 'hobbit']:
            ok_combination = False

    elif player.char_class == 'assassin':
        if player.race in ['gnome', 'elf', 'hobbit']:
            ok_combination = False

    elif player.char_class == 'knight':
        if player.race in ['ogre', 'orc']:
            ok_combination = False

    if ok_combination is False:
        print(f"\"{'An ' if player.race.startswith(('a', 'e', 'i', 'o', 'u')) else 'A '}", end='')
        print(f"{player.race} {player.char_class} does not a good adventurer make. Try again.\"")
    else:
        print('"Okay, fine with me," agrees Verus.')
    return ok_combination


def choose_race(player: Player):
    """step 3b: choose player race"""
    valid = False
    while valid is False:
        display_races()
        print("Race [1-9]", end='')
        temp = input(": ")
        # TODO: help option here ("H1", "1?" or similar, want to avoid reading 9 races as in original
        temp = int(temp)
        valid = 0 < temp < 10  # accept 1-9
        if valid:
            player.race = ['human', 'ogre', 'gnome', 'elf', 'hobbit', 'halfling',
                           'dwarf', 'orc', 'half-elf'][temp-1]
            valid = validate_class_race_combo(player=player)
            if valid:
                break


def display_races():
    print('''"Choose a race," Verus instructs.
    
    (1) Human    (4) Elf      (7) Dwarf
    (2) Ogre     (5) Hobbit   (8) Orc
    (3) Gnome    (6) Halfling (9) Half-Elf
    ''')
    # TODO: Should be a help function to get help about individual races.
    # Whether it's called up with "H1" or "1?" is undetermined.


def edit_race(player: Player):
    race_valid = False
    while race_valid is False:
        display_races()
        if player.race:
            print(f"{return_key} keeps '{player.race.title()}'.\n")
        print("Race [1-9]", end='')
        temp = input(": ")
        if temp == '':
            print(f"Keeping '{player.race.title()}'.")
        # TODO: help option here ("H1", "1?" or similar, want to avoid reading 9 races as in original
        temp = int(temp)
        valid = 1 < temp < 9
        if valid:
            player.race = ['human' 'ogre', 'gnome', 'elf', 'hobbit', 'halfling',
                           'dwarf', 'orc', 'half-elf'][temp-1]
        race_valid = validate_class_race_combo(player=player)
        if race_valid is not True:
            print('"Try picking a different race," Verus suggests.')


def choose_age(player: Player):
    """
    step 4: allow player to select age and birthday

    if player.age = 0, it is displayed as 'Unknown'
    """
    age_valid = False
    temp_age = 0
    while age_valid is False:
        print('"Enter [0] to be of an unknown age."')
        print('"Enter [R] to select a random age between 15-50."\n')
        temp_age = input("Enter your age (0, R or 15-50): ")
        if temp_age.lower() == 'r':
            temp_age = randrange(15, 50)
            break
        if temp_age.isalpha():
            print('Verus tsks. "Please enter a number."')
        temp_age = int(temp_age)
        if temp_age == 0:
            """
            I think this is mostly for when people LOOK at your character:
            
            Looking at Railbender, you see a man of unknown age.
            
            Not entirely sure, though.
            """
            temp_age = 0
            break

        age_valid = validate_age(temp_age)
        if age_valid is False:
            print('"Try again," suggests Verus.')

    temp = 'of an unknown' if temp_age == 0 else f'{temp_age} years of'
    print(f'Verus studies you, and comments: "You\'re {temp} age."')
    player.age = temp_age

    # year = today.year - player.age FIXME: (if =0, what then?)
    _month = date.today().month
    _day = date.today().day
    _year = date.today().year
    print(f"""Would you like your birthday to be:
    
    [T]oday ({_month}/{_day})
    [A]nother date (choose month and day)
""")
    temp = input("Which [T, A]: ").lower()
    if temp == 't':
        # store as tuple:
        player.birthday = (_month, _day, _year)
        print(f'Set to today: {_month}/{_day}.\n')
    if temp == 'a':
        # year is calculated for leap year in monthrange() below, and displaying later
        # FIXME: what to do about age = 0
        _year = date.today().year-player.age
        _month = int(validate_range(word="Month", start=1, end=12))
        # monthrange(year, day) returns tuple: (month, days_in_month)
        # we just need days_in_month, which is monthrange()[1]
        _day = int(validate_range(word="Day", start=1,
                                  end=calendar.monthrange(year=_year, month=_month)[1]))

        # store birthday as tuple: birthday[0] = month, [1] = day, [2] = year
        # store year anyway in case age = 0
        player.birthday = (_month, _day, _year)
        print(f"Birthday: {_month}/{_day}/{_year}")


def validate_range(word, start, end):
    """
    :param word: Edit <word>
    :param start: lowest number to allow
    :param end: highest number to allow
    :return: temp, the value input
    """
    valid = False
    while valid is False:
        temp = input(f"{word} ({start}-{end}): ")
        if temp.isalpha():
            print("Numbers only, please.")
        temp = int(temp)
        if start-1 < temp < end+1:
            valid = True
            return temp
        print("No, try again.")


def validate_age(age: int):
    """
    validate that the age == 0, or 15 < age < 50
    :param age: age entered
    :return: True if age == 0, or 15 < age 50, False if not
    """
    if age == 0:
        print("You're of an unknown age.")
        return True
    if age < 15:
        print("\"Oh, come off it! You're not even old enough to handle a "
              'Staff yet. Get real!"')
        return False
    if age > 50:
        print('"Hmm, we seem to be out of Senior Adventurer life '
              'insurance policies right now. Come back tomorrow!"')
        return False


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
        # print(f'5.     Age: {player.age()}')
        # Birthday: tuple(month, day, year)
        print(f'  Birthday: {player.birthday[0]}/{(player.birthday[1])}/'
              f'{(player.birthday[2])}')
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


def choose_guild(player: Player):
    valid_guild = False
    while valid_guild is False:
        print('''"Would you like to join a Guild?" asks Verus.

            No, stay a [C]ivilian
            No, turn into an [O]utlaw
            Yes, join a [G]uild
        ''')
        temp = input("Which option [C, O, G]: ").lower()
        print()
        if temp in ['c', 'o']:
            guilds = {'c': 'civilian', 'o': 'outlaw'}
            player.guild = guilds[temp]
            _ = guilds[temp].title()
            print(f'"You have chosen to be a {_}."')
            valid_guild = True
            break
        if temp == 'g':
            while True:
                print('''"Which guild would you like to join?" asks Verus expectantly.
    
    [F]ist
    [S]word
    [C]law
    [N]one - changed my mind
''')
                temp = input("Which option [F, S, C, N]: ")
                print()
                if temp in ['f', 's', 'c']:
                    guilds = {'f': 'fist', 's': 'sword', 'c': 'claw'}
                    player.guild = guilds[temp]
                    _ = guilds[temp].title()
                    print(f'"You have chosen the {_} guild."')
                    valid_guild = True
                    break
                # N goes back to choose_guild()
                if temp == 'n':
                    print("Withdrawing guild choice.")
                    valid_guild = False


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
                       # char_class=None, race=None,
                       silver={'in_hand': 0, 'in_bank': 0, 'in_bar': 0}
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

    header("Choose Guild")
    choose_guild(player=character)

    output(text="Done!", player=character)
