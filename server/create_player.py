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


def choose_gender(char: Player):
    """step 1: choose character gender"""
    output('Verus squints myopically. "Are you a male or female?"', char)
    while True:
        temp = input("Enter [M]ale or [F]emale: ").lower()
        if temp == 'm':
            character.gender = 'male'
            break
        if temp == 'f':
            character.gender = 'female'
            break


def edit_gender(char: Player):
    """toggle existing character gender"""
    """
    :param char: Player to toggle gender of
    """

    while True:
        # FIXME: this is probably a dirty hack
        if char.gender == 'female':
            char.gender = 'male'
            break
        if char.gender == 'male':
            char.gender = 'female'
            break
    output(f"{char.name} is now {char.gender}.", char)


def choose_name(char: Player):
    """step 2: choose character name"""
    if char.name:
        # this is repeated, so function:
        char.name = enter_name(char.name, edit_mode=True)

    elif character.name is None:
        # no existing name, prompt for new character name
        character.name = enter_name(char, edit_mode=False)


def edit_name(char: Player):
    """update character name"""
    # 'character' param shadows 'character' from outer scope
    char.name = enter_name(char, edit_mode=True)


def enter_name(_char: Player, edit_mode: bool):
    """
    change character name. this can also be called during final player edit menu

    :param _char: Player object (trying to make _private to eliminate shadowing)
    :param edit_mode: True: editing existing name
                      False: no name assigned, entering new name
    :return: name: str
    """
    if edit_mode is True:
        output(f"(Editing existing name '{_char.name}'.)", _char)
    print("([Q]uit", end='')
    if edit_mode is True:
        print(f", [{return_key}] keeps existing name", end='')
    print(")")
    # TODO: this should be written as a generic edit prompt
    temp = input("What is your name: ")
    if edit_mode:
        # Return hit, or new string = old string:
        if temp == "" or temp == _char.name:
            output(f"(Keeping the name of '{_char.name}'.)", _char)
    if temp.lower() == 'q':
        output("'Quit' selected.", _char)
    output(f'Verus checks to see if anyone else has heard of "{temp}" around '
           'here...', _char)
    # TODO: check for existing name
    print(f"Seems to be okay. He ", end='')
    if edit_mode and character.name != temp:
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
        output('* '*80, player)

        # output() discards newlines, so can't use it here - even literal \n's don't work:

        # the width of this string is >40 characters
        output(f'"Which kind of client are you using, {player.name}?" Verus asks.',
               player)
        print()  # must be used in place of \n
        output("## Client type     Screen size", player)
        output("-- --------------- -----------", player)
        output("1. Commodore 64    (40 x 25)", player)
        output("2. Commodore 128   (80 x 25)", player)
        output("3. TADA client", player)
        print()
        temp = input(f"Which client (1-{options}, [Q]uit): ").lower()

        if temp == "q":
            # FIXME
            output("quit selected", player)

        if temp == "1":
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
        output(f"Client set to: {player.client['name']}", player)


def choose_class(player: Player):
    """step 3a: choose player class"""
    # NOTE: Player object 'class' attribute conflicts with built-in keyword
    # I am naming it char_class instead
    class_valid = False
    while class_valid is False:
        is_num = False
        while is_num is False:
            display_classes(player)
            temp = input("Class [1-9]: ")
            # was previously using 'temp = int(input(...))' but you can't cast a str -> int
            if temp.isalpha() is False:
                is_num = True
                temp = int(temp)
                class_valid = 0 < temp < 10  # accept 1-9
                logging.info(f"{class_valid=}, {is_num=}, {temp=}")
            output('"Choose a class between 1 and 9," suggests Verus.', player)
    # first time answering this prompt, there is no race to validate against:
    player.char_class = ['wizard' if player.gender == 'male' else 'witch',
                         'druid', 'fighter', 'paladin', 'ranger',
                         'thief', 'archer', 'assassin', 'knight'][temp-1]


def display_classes(player: Player):
    wizard = 'Wizard' if player.gender == 'male' else 'Witch '
    output('"Choose a class," Verus instructs.', player)
    print()
    output(f"(1) {wizard}   (4) Paladin  (7) Archer", player)
    output("(2) Druid    (5) Ranger   (8) Assassin", player)
    output("(3) Fighter  (6) Thief    (9) Knight", player)
    print()


def edit_class(player: Player):
    """
    this is called during final_edit() to change the class,
    then validate the resulting class/race combination
    """
    # TODO: combine common code in another method
    valid_class = False
    while valid_class is False:
        display_classes(player)
        # TODO: Should be a help function to get help about individual classes.
        # Whether it's called up with "H1" or "1?" is undetermined.
        output(f'{return_key} keeps {player.char_class.title()}.', player)
        """if the character creation process has only asked for the class so far,
        race will be None, and we shouldn't validate the combination"""
        temp = input("Class [1-9]: ")
        if temp.isalpha():
            output('"Numbers only, please."', player)
        temp = int(temp)
        valid = 0 < temp < 10  # accept 1-9
        if valid:
            valid_class = validate_class_race_combo(player)
            if valid_class:
                # class/race combo is good, set class:
                character.char_class = ['wizard', 'druid', 'fighter', 'paladin',
                                        'ranger', 'thief', 'archer', 'assassin',
                                        'knight'][temp-1]
                if temp == 1 and character.gender == 'female':
                    character.char_class = 'witch'
                # end outer loop
                break
        else:
            output('"Choose a class between 1 and 9," suggests Verus.', player)


def validate_class_race_combo(player: Player):
    """make sure selected class/race combination is allowed
    :param player: Player object to validate class and race of
    :returns: True if an acceptable combination, False if not"""
    ok_combination = True
    logging.info("validate_class_race_combo reached")

    # list of bad combinations:
    if player.char_class == 'wizard' or 'witch':
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
        temp = f'''"{'An ' if player.race.startswith(('a', 'e', 'i', 'o', 'u')) else 'A '}"'''
        temp += f'{player.race} {player.char_class} does not a good adventurer make. Try again."'
        output(temp, player)
    else:
        output('"Okay, fine with me," agrees Verus.', player)
    return ok_combination


def choose_race(player: Player):
    """step 3b: choose player race"""
    valid = False
    while valid is False:
        display_races(player)
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


def display_races(player: Player):
    output('"Choose a race," Verus instructs.', player)
    print()
    output("(1) Human    (4) Elf      (7) Dwarf", player)
    output("(2) Ogre     (5) Hobbit   (8) Orc", player)
    output("(3) Gnome    (6) Halfling (9) Half-Elf", player)
    print()
    # TODO: Should be a help function to get help about individual races.
    # Whether it's called up with "H1" or "1?" is undetermined.


def edit_race(player: Player):
    race_valid = False
    while race_valid is False:
        display_races(player)
        if player.race:
            output(f"{return_key} keeps '{player.race.title()}'.", player)
            print()
        print("Race [1-9]", end='')
        temp = input(": ")
        if temp == '':
            output(f"Keeping '{player.race.title()}'.", player)
        # TODO: help option here ("H1", "1?" or similar, want to avoid reading 9 races as in original
        temp = int(temp)
        valid = 1 < temp < 9
        if valid:
            player.race = ['human' 'ogre', 'gnome', 'elf', 'hobbit', 'halfling',
                           'dwarf', 'orc', 'half-elf'][temp-1]
        race_valid = validate_class_race_combo(player=player)
        if race_valid is not True:
            output('"Try picking a different race," Verus suggests.', player)


def choose_age(player: Player):
    """
    step 4: allow player to select age and birthday

    if player.age = 0, it is displayed as 'Unknown'
    """
    age_valid = False
    temp_age = 0
    while age_valid is False:
        output('Enter [0] to be of an unknown age.', player)
        output('Enter [R] to select a random age between 15-50.', player)
        print()
        temp_age = input("Enter your age (0, R or 15-50): ")
        if temp_age.lower() == 'r':
            temp_age = randrange(15, 50)
            break
        if temp_age.isalpha():
            output('Verus tsks. "Please enter a number."', player)
        temp_age = int(temp_age)
        if temp_age == 0:
            """
            I think this is mostly for when people LOOK at your character:
            
            Looking at Railbender, you see a man of unknown age.
            
            Not entirely sure, though.
            """
            temp_age = 0
            break

        age_valid = validate_age(temp_age, player)
        if age_valid is False:
            output('"Try again," suggests Verus.', player)

    temp = 'of an unknown' if temp_age == 0 else f'{temp_age} years of'
    output(f'Verus studies you, and comments: "You\'re {temp} age."', player)
    player.age = temp_age

    # year = today.year - player.age FIXME: (if =0, what then?)
    _month = date.today().month
    _day = date.today().day
    _year = date.today().year
    output(f'"Which would you like your birthday to be?" asks Verus.', player)
    print()
    output(f"[T]oday ({_month}/{_day})", player)
    output("[A]nother date (choose month and day)", player)
    print()
    temp = input("Which [T, A]: ").lower()
    if temp == 't':
        # store as tuple:
        player.birthday = (_month, _day, _year)
        output(f'Set to today: {_month}/{_day}.', player)
        print()
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
        output(f"Birthday: {_month}/{_day}/{_year}", player)


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
            output("Numbers only, please.", player)
        temp = int(temp)
        if start-1 < temp < end+1:
            valid = True
            return temp
        output("No, try again.", player)


def validate_age(age: int, player):
    """
    validate that the age == 0, or 15 < age < 50
    :param player: Player to output message to
    :param age: age entered
    :return: True if age == 0, or 15 < age 50, False if not
    """
    if age == 0:
        output("You're of an unknown age.", player)
        return True
    if age < 15:
        output('"Oh, come off it! You\'re not even old enough to handle a '
               'Staff yet."', player)
        return False
    if age > 50:
        output('"Hmm, we seem to be out of Senior Adventurer life '
               'insurance policies right now. Come back tomorrow!"', player)
        return False


def final_edit(player: Player):
    """allow player another chance to view/edit characteristics before saving"""
    output(f"Summary of character '{player.name}':", player)
    options = 5
    while True:
        print()
        output(f'1.    Name: {player.name}', player)
        output(f'2.  Gender: {player.gender.title()}', player)
        output(f'3.   Class: {player.char_class.title()}', player)
        output(f'4.    Race: {player.race.title()}', player)
        if player.age == 0:
            temp = "Unknown"
        else:
            temp = player.age
        output(f'5.     Age: {temp}', player)
        # print(f'5.     Age: {player.age()}')
        # Birthday: tuple(month, day, year)
        output(f'  Birthday: {player.birthday[0]}/{(player.birthday[1])}/'
               f'{(player.birthday[2])}', player)
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
        output('"Would you like to join a Guild?" asks Verus.', player)
        print()
        output("    No, stay a [C]ivilian", player)
        output("    No, turn into an [O]utlaw", player)
        output("   Yes, join a [G]uild", player)
        print()
        temp = input("Which option [C, O, G]: ").lower()
        print()
        if temp in ['c', 'o']:
            guilds = {'c': 'civilian', 'o': 'outlaw'}
            player.guild = guilds[temp]
            _ = guilds[temp].title()
            output(f'"You have chosen to be a {_}."', player)
            valid_guild = True
            break
        if temp == 'g':
            while True:
                output('"Which guild would you like to join?" asks Verus expectantly.', player)
                print()
                output("[F]ist", player)
                output("[S]word", player)
                output("[C]law", player)
                output("[N]one - changed my mind", player)
                print()
                temp = input("Which option [F, S, C, N]: ")
                print()
                if temp in ['f', 's', 'c']:
                    guilds = {'f': 'fist', 's': 'sword', 'c': 'claw'}
                    player.guild = guilds[temp]
                    _ = guilds[temp].title()
                    output(f'"You have chosen the {_} guild."', player)
                    valid_guild = True
                    break
                # N goes back to choose_guild()
                if temp == 'n':
                    output("Withdrawing guild choice.", player)
                    valid_guild = False


def header(text: str):
    print()
    print(text)
    print("-" * len(text))
    print()


def output(string: str, player: Player):
    """
    Print <string> word-wrapped to <columns> characters to Player:

    :param string: string to output
    :param player: Player to output text to
    :return: none

    TODO: implement cbmcodec2 ASCII -> PETSCII translation
    """
    if player.client['translation'] == 'PETSCII':
        pass  # until cbmcodecs2 is fixed
    print(textwrap.fill(text=string, width=player.client['columns']))


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
    output("Your faithful servant Verus appears at your side, as if by magic.",
           character)
    output('Verus mentions, "Do not worry if ye answer wrong, ye can change thy answer later."',
           character)

    header("0. Choose Client")
    choose_client(character)  # TODO: net_server handles this

    header("I. Choose Gender")
    choose_gender(character)

    header("II. Choose Name")
    choose_name(character)

    header("III. Choose Class")
    choose_class(character)

    header("IV. Choose Race")
    choose_race(character)

    header("V. Choose Age")
    choose_age(character)

    header("VI. Final Edit")
    final_edit(character)

    header("Choose Guild")
    choose_guild(character)

    output("Done!", character)
