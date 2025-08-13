import doctest
from typing import TYPE_CHECKING

import tada_utilities
from menu_system import MenuItem, Menu, navigate_menu

if TYPE_CHECKING:
    from player import Player
    from base_classes import Gender, PlayerClass, PlayerRace, PlayerStat, PlayerMoneyTypes, Guild, PlayerClassText, \
        PlayerRaceText
    from terminal import Translation
    from tada_utilities import header, input_number_range, input_yes_no, a_or_an
    from flags import PlayerFlags

from random import randrange  # for age and generating random stats

from datetime import date, datetime  # for birthday displays/calculations

import calendar  # monthrange for validating # of days in month

import logging

# import cbmcodecs2
# FIXME: package does not recognize color codes. Is it an XY problem that adding them to the decode table will solve?
#   Should p.output() handle e.g., "{orange}" as a special case in strings by itself?
# $90 is {black}
"""
Traceback (most recent call last):
    File "<string>", line 1, in <module>
    UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 2537: character maps to <undefined>
"""


# resources:
# https://docs.python.org/3/library/collections.html
# https://docs.python.org/3/library/datetime.html
# https://www.dataquest.io/blog/python-datetime-tutorial/


def choose_gender(character: "Player"):
    """step 1: choose character gender"""
    from base_classes import Gender
    character.output('Verus squints myopically. "Are you a male or female?"')
    while True:
        temp = input("Enter [M]ale or [F]emale: ").lower()
        if temp == 'm':
            character.gender = Gender.MALE
            break
        if temp == 'f':
            character.gender = Gender.FEMALE
            break


def edit_gender(char: "Player"):
    """toggle existing character gender"""
    """
    :param char: Player to toggle gender of
    """
    from base_classes import Gender
    while True:
        # FIXME: this is probably a dirty hack
        if char.gender == Gender.FEMALE:
            char.gender = Gender.MALE
            logging.debug("edit_gender: changed from Female to Male")
            break
        if char.gender == Gender.MALE:
            char.gender = Gender.FEMALE
            logging.debug("edit_gender: changed from Male to Female")
            break
    char.output(f"{char.name} is now {char.gender}.")


def choose_name(char: "Player"):
    """step 2: choose character name"""
    if char.name:
        # this is repeated, so function:
        char.name = enter_name(char, edit_mode=True)

    elif char.name is None:
        # no existing name, prompt for new character name
        char.name = enter_name(char, edit_mode=False)


def edit_name(char: "Player"):
    """update character name"""
    # 'character' param shadows 'character' from outer scope
    char.name = enter_name(char, edit_mode=True)


def enter_name(p: "Player", edit_mode: bool):
    """
    Change character name. This can also be called during final player edit menu.

    :param p: Player object
    :param edit_mode: True: editing existing name
                      False: no name assigned, entering new name
    :return: current_name: str
    """
    if edit_mode:
        print(f"({p.client_settings.return_key} keeps '{p.name}.')")
    # TODO: this should be written as a generic edit prompt
    logging.info("Edit mode: %s" % edit_mode)
    current_name = input("What is your name: ").strip()
    if edit_mode:
        # Return hit, or new string = old string:
        if current_name == "" or current_name == p.name:
            current_name = p.name
            p.output(f"(Keeping the name of '{current_name}'.)")

    p.output(f'Verus checks to see if anyone else has heard of "{current_name}" around '
             'here...')
    # TODO: check for existing name
    _ = ['"Seems to be okay." He']
    if edit_mode and p.name != current_name:
        _.append("scratches out your old name and re-writes it")
    else:
        _.append("scribbles your name")
    _.append("in a dusty book.")
    p.output(" ".join(_))
    return current_name


def choose_client(p: "Player"):
    """step 0: choose (or update existing) client name and parameters"""
    from tada_utilities import input_number_range
    from terminal import Translation
    logging.info("init: Client name: %s" % p.client_settings.name)

    options = 3
    # FIXME: this unintentionally wraps text (as it's supposed to) but loses newlines
    # output('* ' * 80, p)

    # output() discards newlines, so can't use it here - even literal \n's don't work:

    # the width of this string is >40 characters
    """
    p.output('"Which kind of client are you using?" Verus asks.')
    print()  # must be used in place of \n
    p.output("   Client type     Screen size")
    p.output("   --------------- --------------------")
    p.output("1. Commodore 64    40 columns x 25 rows")
    p.output("2. Commodore 128   80 columns x 25 rows")
    p.output("3. TADA client     80 columns x 25 rows")
    print()
    """
    p.output(['"Which kind of client are you using?" Verus asks.',
              "",  # "" must be used in place of \n
              "   Client type     Screen size",
              "   --------------- --------------------",
              "1. Commodore 64    40 columns x 25 rows",
              "2. Commodore 128   80 columns x 25 rows",
              "3. TADA client     80 columns x 25 rows",
              "",
              ])

    temp = input_number_range(prompt="Which client", p=p, lo=1, hi=options)

    if temp == 1:
        p.client_settings.name = 'Commodore 64'
        p.client_settings.screen_columns = 40
        p.client_settings.screen_rows = 25
        p.client_settings.translation = Translation.PETSCII
    elif temp == 2:
        p.client_settings.name = 'Commodore 128 (80 columns)'
        p.client_settings.screen_columns = 80
        p.client_settings.screen_rows = 25
        p.client_settings.translation = Translation.PETSCII
    elif temp == 3:
        p.client_settings.name = 'TADA Client'
        p.client_settings.screen_columns = 80
        p.client_settings.screen_rows = 25
        p.client_settings.translation = Translation.ASCII

    if p.client_settings.translation == Translation.PETSCII:
        p.client_settings.return_key = "Return"
    else:
        p.client_settings.return_key = "Enter"
    client_name = p.client_settings.name
    columns = p.client_settings.screen_columns
    rows = p.client_settings.screen_rows
    p.output(f"Client set to: {client_name} ({columns}x{rows})")
    return p


def choose_class(p: "Player"):
    """step 3a: choose player class"""
    # NOTE: Player object 'class' attribute conflicts with built-in keyword
    # I am naming it 'PlayerClass' instead
    from flags import PlayerFlags
    from base_classes import PlayerClass, PlayerClassText
    from tada_utilities import input_yes_no

    # Provide initial class explanation unless in expert mode
    # so we don't have to go through every character creation step...
    # FIXME: this text is not wrapping properly; check columns
    logging.debug("Column width: %i" % p.client_settings.screen_columns)
    if not p.query_flag(PlayerFlags.EXPERT_MODE):
        p.output("Your class defines your character's primary skills, abilities, and role within a group. It's their "
                 "profession or path in life, granting them unique ways to interact with the world and combat.")

    # Debug mode shortcut for class selection
    if p.query_flag(PlayerFlags.DEBUG_MODE):
        shortcut = PlayerClass.FIGHTER
        answer = input_yes_no(f"Debug mode: Shortcut setting Player Class to '{shortcut}'")
        if answer:
            logging.info("Shortcut taken: set character_class: %s" % shortcut)
            p.char_class = shortcut
            return

    while True:  # Loop until a valid choice is made
        display_classes(p)
        choice = input("Class [1-9, I1-I9]: ").lower().strip()

        # TODO: make this into a subroutine
        if choice.isdigit():  # Check if the input is purely a number
            number_choice = int(choice)
            if 1 <= number_choice <= 9:  # Correct range check for 1 to 9 inclusive
                p.char_class = [c for c in PlayerClass][number_choice - 1]
                logging.debug("Class: %s" % p.char_class)
                return  # Exit the loop and function as a valid choice was made
            else:
                p.output('"Choose a class between 1 and 9," suggests Verus.')
        elif choice.startswith("i") and len(choice) == 2 and choice[1].isdigit():  # Check for "I#" format
            class_number_str = choice[1]
            try:
                class_info_index = int(class_number_str)
                if 1 <= class_info_index <= 9:  # Ensure the number after 'I' is in range
                    # Access the enum member by its index number:
                    class_text = [ct for ct in PlayerClassText][class_info_index - 1]
                    # FIXME: get rid of \n
                    # dedented = textwrap.dedent(class_text).strip('\n')
                    try:
                        p.output(class_text)
                    except KeyError:
                        p.output(f'Verus frowns, "I don{apostrophe}t have information on {choice}."')
                else:
                    p.output('"To get class info, enter I followed by a number between 1 and 9," Verus explains.')
            except ValueError:  # This would catch if choice[1] wasn't a digit, though the outer check handles most of it
                p.output("That's not a valid info request. Try I1, I2, etc.")
        else:
            p.output(
                "Verus shakes his head. 'That's not a choice I understand. Try a number or I followed by a number.'")

        # The loop continues if no valid return or specific error handled


def choose_settings(p: "Player"):
    p.output(["-- Settings Menu Mockup --",
              "",
              "[1. / R] Regional Settings",
              "       locale (date format, time format: 12/24 hour), time zone, etc.",
              "[2. / C] Colors: Screen / Text Highlight Colors",
              "       bracketed text highlight & normal colors, etc.",
              "[3. / O] Choose Other Settings",
              "       character translation, line endings, etc.",
              "",
              "[D]    Debug Mode: Off",
              "[E]   Expert Mode: Off",
              "[L] Logging Level: Debug"
              "",
              "[PREFS] command (not implemented yet) will change most of these.",
              ])


def display_classes(p: "Player"):
    from base_classes import Gender, PlayerClass
    logging.info("Entering")

    wizard = 'Wizard' if p.gender == Gender.MALE else 'Witch'
    p.output('"Choose a class," Verus instructs.')
    print()

    # Column headers with specific widths
    # "Choose" takes 6 characters. "Info" takes 4. "Name" takes 4.
    # We'll set column widths to ensure alignment.
    # Let's aim for these column start positions:
    # Choose (starts at 0)
    # Info (starts at column 9)
    # Name (starts at column 19)

    p.output(f"{'Choose':<7} {'Info':<5} {'Name':<20}")  # Adjust widths as needed
    # Example: "Choose" is left-aligned in 8 chars, "Info" in 9, "Name" in 20.

    # Data rows
    # The actual column for "Choose" is just the index
    # The "Info" column is like "I1", "I2", etc.
    # The "Name" column is the class name

    class_names = [
        wizard,  # Wizard/Witch is special
        PlayerClass.DRUID.name.capitalize(),
        PlayerClass.FIGHTER.name.capitalize(),
        PlayerClass.PALADIN.name.capitalize(),
        PlayerClass.RANGER.name.capitalize(),
        PlayerClass.THIEF.name.capitalize(),
        PlayerClass.ARCHER.name.capitalize(),
        PlayerClass.ASSASSIN.name.capitalize(),
        PlayerClass.KNIGHT.name.capitalize()
    ]

    for i, class_name in enumerate(class_names, start=1):
        # Calculate the fixed width for each component
        # {i:<8} : Left-align the number 'i' in a field of 8 characters.
        # {f'I{i}':<9} : Left-align "I[i]" in a field of 9 characters.
        # {class_name:<20} : Left-align the class name in a field of 20 characters.
        p.output(f"[  {i:<6} {f'I{i}':<4}] {class_name:<20}")
    p.output("")


def edit_class(p: "Player"):
    """
    this is called during final_edit() to change the class,
    then validate the resulting class/race combination
    """
    from base_classes import PlayerClass
    while True:
        display_classes(p)
        default = p.char_class if p.char_class is not None else None
        choice = input("Character class [1-9, I1-I9]: ").lower().strip()

        # out_of_bounds='"Choose a class between 1 and 9," suggests Verus.',
        # default=default)
        """
        if the character creation process has only asked for the class so far,
        race will be None, and we shouldn't validate the combination
        """
        char_class = int(choice)
        p.char_class = [c for c in PlayerClass][char_class - 1]
        logging.debug("player_class: %s" % p.char_class)

        # validate_class_race_combo(p) prints a message about invalid class/race combinations
        if validate_class_race_combo(p):
            # class/race combo is good, keep class:
            print(f'"That{apostrophe}s fine," smiles Verus.')
            break  # end loop


def validate_class_race_combo(p: "Player") -> bool:
    """
    Make sure the selected class & race combination is allowed. Set p.char_class beforehand.
    If p.char_race is None, this is the initial run of choose_class() and validation will be
    skipped.

    If called from choose_race() or final_edit(), both p.char_class and p.char_race should be
    set, and validation will proceed. Returns state of bad_combination: False if not

    :param p: Player object to validate class and race of
    :return: True if a class and race combination is acceptable. False if it isn't an acceptable combination.
    """
    from base_classes import PlayerClass, PlayerRace
    from tada_utilities import a_or_an

    logging.debug("Validating: Race=%s, Class=%s" % (p.char_race, p.char_class))
    good_combination = True
    if p.char_class is not None and p.char_race is None:
        logging.info("char_race unset, skipping validation. Returning True to allow continuing.")
        return True
    # list of bad class & race combinations:
    if p.char_class == PlayerClass.WIZARD:
        logging.info("-=> Wizard")
        if p.char_race in [PlayerRace.OGRE, PlayerRace.DWARF, PlayerRace.ORC]:
            logging.info("-=> %s: bad" % p.char_race)
            good_combination = False

    elif p.char_class == PlayerClass.DRUID:
        if p.char_race in [PlayerRace.OGRE, PlayerRace.ORC]:
            good_combination = False

    elif p.char_class == PlayerClass.THIEF:
        if p.char_race == PlayerRace.ELF:
            good_combination = False

    elif p.char_class == PlayerClass.ARCHER:
        if p.char_race in [PlayerRace.OGRE, PlayerRace.GNOME, PlayerRace.HOBBIT]:
            good_combination = False

    elif p.char_class == PlayerClass.ASSASSIN:
        if p.char_race in [PlayerRace.GNOME, PlayerRace.ELF, PlayerRace.HOBBIT]:
            good_combination = False

    elif p.char_class == PlayerClass.KNIGHT:
        if p.char_race in [PlayerRace.OGRE, PlayerRace.ORC]:
            good_combination = False

    if not good_combination:
        logging.info("%s %s is bad combination" % (p.char_race, p.char_class))
        temp = f'Verus remarks, "{a_or_an(p.char_race, capitalize=True)} ' \
               f'{p.char_class} doth not a good adventurer make. Try again."'
        p.output(temp)
    else:
        p.output('"Okay, fine with me," agrees Verus.')
    return good_combination


def choose_race(p: "Player"):
    """step 3b: choose player race"""
    from base_classes import PlayerRace, PlayerRaceText
    from flags import PlayerFlags
    from tada_utilities import input_yes_no
    # just so we don't have to go through every char creation step...
    if p.query_flag(PlayerFlags.DEBUG_MODE):
        shortcut = PlayerRace.ORC
        answer = input_yes_no(f"Shortcut setting Player Race to '{shortcut}'?")
        if answer:
            p.char_race = shortcut
            logging.debug("Shortcut taken: set PlayerRace to '%s'" % shortcut)
            return
    while True:
        display_races(p)
        # TODO: make this into a subroutine
        choice = input("Race [1-9, I1-I9]: ").lower().strip()

        if choice.isdigit():  # Check if the input is purely a number
            number_choice = int(choice)
            if 1 <= number_choice <= 9:  # Correct range check for 1 to 9 inclusive
                p.char_race = [c for c in PlayerRace][number_choice - 1]
                logging.debug("Race: %s" % p.char_class)
                return  # Exit the loop and function as a valid choice was made
            else:
                p.output('"Choose a race between 1 and 9," suggests Verus.')
        elif choice.startswith("i") and len(choice) == 2 and choice[1].isdigit():  # Check for "I#" format
            race_number_str = choice[1]
            try:
                race_info_index = int(race_number_str)
                if 1 <= race_info_index <= 9:  # Ensure the number after 'I' is in range
                    # Access the enum member by its index number:
                    race_text = [rt for rt in PlayerRaceText][race_info_index - 1]
                    # FIXME: get rid of \n
                    # dedented = textwrap.dedent(race_text).strip('\n')
                    try:
                        p.output(race_text)
                    except KeyError:
                        p.output(f'Verus frowns, "I don{apostrophe}t have information on {choice}."')
                else:
                    p.output('"To get race info, enter I followed by a number between 1 and 9," Verus explains.')
            except ValueError:  # This would catch if choice[1] wasn't a digit, though the outer check handles most of it
                p.output("That's not a valid info request. Try I1, I2, etc.")
        else:
            p.output(
                "Verus shakes his head. 'That's not a choice I understand. Try a number or I followed by a number.'")

        # The loop continues if no valid return or specific error handled
        p.char_race = [r for r in PlayerRace][race_info_index - 1]
        logging.debug("char_race: '%s'" % p.char_race)
        # False means the class/race combination is bad:
        combination_okay = validate_class_race_combo(p)
        logging.info("Exit: combination ok: %s" % combination_okay)
        if combination_okay:
            logging.info("FIXME: finish validation")
            break
        else:
            logging.info("Bad class/race combination, continuing loop")


def display_races(p: "Player"):
    from base_classes import Gender, PlayerRace
    logging.info("Entering")

    p.output('"Choose a race," Verus instructs.')
    print()

    # Column headers with specific widths
    # "Choose" takes 6 characters. "Info" takes 4. "Name" takes 4.
    # We'll set column widths to ensure alignment.
    # Let's aim for these column start positions:
    # Choose (starts at 0)
    # Info (starts at column 9)
    # Name (starts at column 19)

    p.output(f"{'Choose':<7} {'Info':<5} {'Name':<20}")  # Adjust widths as needed
    # Example: "Choose" is left-aligned in 8 chars, "Info" in 9, "Name" in 20.

    # Data rows
    # The actual column for "Choose" is just the index
    # The "Info" column is like "I1", "I2", etc.
    # The "Name" column is the class name

    race_names = [
        PlayerRace.HUMAN.capitalize(),
        PlayerRace.OGRE.capitalize(),
        PlayerRace.PIXIE.capitalize(),
        PlayerRace.ELF.capitalize(),
        PlayerRace.HOBBIT.capitalize(),
        PlayerRace.GNOME.capitalize(),
        PlayerRace.DWARF.capitalize(),
        PlayerRace.ORC.capitalize(),
        PlayerRace.HALF_ELF.capitalize()
    ]

    # enumerating through race names so choosing a menu option displays correct race info:
    for i, race_name in enumerate(race_names, start=1):
        # Calculate the fixed width for each component
        # {i:<8} : Left-align the number 'i' in a field of 8 characters.
        # {f'I{i}':<9} : Left-align "I[i]" in a field of 9 characters.
        # {class_name:<20} : Left-align the class name in a field of 20 characters.
        p.output(f"[  {i:<6} {f'I{i}':<4}] {race_name:<20}")
    p.output("")


def edit_race(p: "Player") -> None:
    from tada_utilities import input_number_range
    race_valid = False
    while not race_valid:
        display_races(p)
        if p.char_race:
            temp = input_number_range("Race", 1, 9, p,
                                      out_of_bounds='"Enter a race from 1-9," Verus suggests.')
            logging.info("'%s' race set to %s" % (p.name, PlayerRace[temp - 1]))
            p.char_race = PlayerRace[temp - 1]
            # output(f"{return_key} keeps '{p.race.title()}'.", p)
            print()
        # print("Race [1-9]", end='')
        # temp = input(": ")
        # TODO: make subroutine that validates isalpha() and allowable range:
        # if temp.isalpha():
        #     output(f'"Numbers only, please."', p)
        # if temp == '':
        #     output(f"Keeping '{p.race.title()}'.", p)
        # TODO: help option here ("H1", "1?" or similar, want to avoid reading 9 races as in original
        # temp = int(temp)
        # valid = 1 < temp < 9
        # if valid:
        if not validate_class_race_combo(p):
            p.output('"Try picking a different race," Verus suggests.')


def choose_age(p: "Player"):
    """
    step 4: allow player to select age and birthday

    if player.age = 0, it is displayed as 'Unknown'
    """
    from tada_utilities import input_number_range
    age_valid = False
    age_input = 0
    while not age_valid:
        p.output('Enter [0] to be of an unknown age.')
        p.output('Enter [R] to select a random age between 15-50.')
        print()
        age_input = input("Enter your age (0, R or 15-50): ")
        if age_input.lower()[0:1] == 'r':
            age_input = randrange(15, 50)
            break
        if age_input.isalpha():
            p.output('Verus tsks. "Please enter a number."')
        age_value = int(age_input)
        if age_value == 0:
            """
            I think this is mostly for when people LOOK at your character:
            
            Looking at Railbender, you see a man of unknown age.
            
            Not entirely sure, though.
            """
            age_input = 0
            break

    age_valid = validate_age(age_input, p)
    if not age_valid:
        p.output('"Try again," suggests Verus.')
    else:
        print("Edge case")
    temp = 'of an unknown' if age_input == 0 else f'{age_input} years of'
    p.output(f'Verus studies you, and comments: "You{apostrophe}re {temp} age."')
    p.age = age_input

    # year = today.year - p.age FIXME: (if =0, what then?)
    birthday_month = date.today().month
    birthday_day = date.today().day
    birthday_year = date.today().year
    p.output(f'Verus asks, "Would you like your birthday to be:"')
    print()
    p.output(f"[T]oday ({birthday_month}/{birthday_day})")
    p.output("[A]nother date (choose month and day)")
    print()
    temp = input("Which [T, A]: ").lower()[0:1]
    if temp == 't':
        # store as datetime:
        p.birthday = datetime(birthday_year, birthday_month, birthday_day)
        p.output(f'Set to today: {birthday_month}/{birthday_day}.')
        print()
    if temp == 'a':
        # year is calculated for leap year in monthrange() below, and displaying later
        # FIXME: what to do about age = 0
        birthday_year = date.today().year - p.age
        # show menu items for months:
        for month in range(1, 13):
            print(f"{month:>2}. {calendar.month_name[month]}")
        birthday_month = input_number_range(prompt="Month", lo=1, hi=12, p=p)
        # monthrange(year, day) returns tuple: (month, days_in_month)
        # we just need days_in_month, which is monthrange()[1]
        days_in_month = calendar.monthrange(year=birthday_year, month=birthday_month)[1]
        birthday_day = input_number_range(prompt="Day", lo=1, hi=days_in_month, p=p,
                                          out_of_bounds="Select a day of the month within range.")
        # store birthday as datetime: birthday.month = month, .day = day, .year = year
        # store year anyway in case age = 0
        p.birthday = datetime(birthday_year, birthday_month, birthday_day)
        p.output(f"Birthday: {birthday_month}/{birthday_day}/{birthday_year}")
    else:
        p.output("That's not a choice.")


def validate_age(age: int, p: "Player"):
    """
    validate that the age == 0, or 15 < age < 50

    :param p: Player to output message to
    :param age: age entered
    :return: True if age == 0, or 15 < age < 50, False if not
    """
    if age == 0:
        p.output("You're of an unknown age.")
        return True
    elif age < 15:
        p.output('"Oh, come off it! You\'re not even old enough to handle a '
                 'Staff yet."')
        return False
    elif age > 50:
        p.output('"Hmm, we seem to be out of Senior Adventurer life '
                 'insurance policies right now. Come back tomorrow!"')
        return False
    return True


def final_edit(p: "Player"):
    """allow player another chance to view/edit characteristics before saving"""
    p.output(f"Your Summary:")
    option_count = 6
    while True:
        print()
        p.output(f'1.     Name: {p.name}')
        p.output(f'2.   Gender: {p.gender}')
        p.output(f'3.    Class: {p.char_class}')
        p.output(f'4.     Race: {p.char_race}')
        # FIXME: this needs work
        age = datetime.now().year - p.birthday.year

        if age == 0:
            temp = "Unknown"
            birthday = f"{p.birthday.month}/{p.birthday.day}"
        else:
            temp = f"{age} years old"
            birthday = f"{p.birthday.month}/{p.birthday.day}/{p.birthday.year}"
        p.output(f'5.      Age: {temp}')
        # TODO: date format setting in player profile (YYYY-MM-DD or DD-MM-YYYY, mainly)
        p.output(f'6. Birthday: {birthday}')
        print()

        temp = input(f"Option [1-{option_count}, {p.client_settings.return_key}=Done]: ")
        print()
        if temp == '1':
            edit_name(p)
        if temp == '2':
            edit_gender(p)
        if temp == '3':
            edit_class(p)
        if temp == '4':
            edit_race(p)
        if temp == '5':
            choose_age(p)
        if temp == '':
            print("Done.")
            break


def choose_guild(p: "Player"):
    # older revision of character_editor.py:
    # https://github.com/Pinacolada64/TADA/blob/923fba2ec24cdfe1f94dc81ed20c53e3198ebde1/server/character_editor.py
    # TODO: call this from guild.py or something (Can change guild in Shoppe or Merchant's Annex, I don't remember which)
    from base_classes import Guild
    from tada_utilities import a_or_an
    text = [
        '"Would you like to be a civilian, join a Guild, or be an outlaw?" asks Verus expectantly, leaning towards you.',
        '',
        "[C]ivilian -- This option is generally recommended for new players who want to get a feel for the game without the added complexities of guild politics and dueling. It provides a safer environment to learn the ropes.",
        '',
        "* You are safe from dueling by all but Outlaws. This is a very important rule for civilians to remember.",
        "* You may only duel Outlaws. Your interactions with other civilians will not involve duels.",
        "* You may remain in the Shoppe while you sleep. This provides a safe haven for rest.",
        '',
        "Join a [G]uild -- This introduces several new facets to your life in the Land:",
        "",
        "* You may battle opposing Guild members with the [DUEL] command. If you are victorious against the opposing guild, the room you are in changes to your guild's alignment. Future duels there award a guild combat bonus against opposing guilds. This is a major advantage for controlling strategic locations.",
        "",
        "* The [AUTODUEL] command automatically [DUEL]s opposing guild members, even while you are asleep ([fact check this]). This feature offers continuous engagement for dedicated guild members.",
        "",
        f"* You gain access to your Guild headquarters. This serves as a vital refuge, a place where you can both contribute to and benefit from your fellow members. Whether you{apostrophe}re donating items or silver to aid others, or taking what you need from shared resources, it{apostrophe}s a hub of mutual support. You can also leave messages or reply to others on a public bulletin board.",
        '',
        "[O]utlaw -- Not recommended for first-time players:",
        "",
        "For an Outlaw, the very notion of a Guild is an insult. These are characters who thrive on defiance, going against the grain and making enemies of most others in the Land rather than bending to any collective will or enjoying the camaraderie of a group to be part of.",
        '',
        f"Becoming an Outlaw drastically changes your gameplay experience, making you a target for many players but also opening up unique opportunities for defiance and solo play.",
        '',
    ]

    civilian_info = ['Civilian: The Path of Peace',
                     '',
                     'Do you prefer a quieter existence, free from the entanglements of guild wars? As a Civilian, you walk a path of peace and prosperity.',
                     '',
                     "* You are safe from dueling by all but Outlaws and may only duel Outlaws.",
                     "* You may remain in the Shoppe while you sleep, offering a secure refuge. This choice is ideal for those who wish to focus on trade, crafting, or simply exploring the Land's lore without the constant call to arms."
                     ]

    claw_info = ["Mark of the Claw: Embrace the Wild Within",
                 "",
                 "For the soul intertwined with nature, for the mystic who commands the untamed forces of the world, the Mark of the Claw calls.",
                 "",
                 "If you feel the whisper of the ancient forests, the roar of the wild beasts, and the surge of primal magic, then the Claw is your destiny. This guild is a sanctuary for those who draw power from the earth itself – Druids, Rangers, and mystical scholars. We are guardians of the natural balance, fiercely protective of the wildlands, and masters of forms both fey and fearsome. Join us, and let the untamed power of nature flow through you as you defend the Land with claw and spell!",
                 ]

    fist_info = ["The Iron Fist: Dominate and Conquer",
                 ""
                 "For those who seek undeniable power, for leaders who forge destiny through sheer will, the Iron Fist extends its grip.",
                 "",
                 "If your ambition knows no bounds, if you yearn to command and to dominate, then the Iron Fist offers the path to true supremacy. We are the architects of empire, a guild for tacticians, warlords, and those who bend others to their will. We believe in strength, strategy, and the right of the powerful to rule. Join the Iron Fist, and together, we shall reshape the Land under our unyielding command!"]

    sword_info = ["Mark of the Sword: Forge Your Legend in Steel",
                  ""
                  "For the unyielding spirit, for the warrior whose heart beats with the rhythm of battle, the Mark of the Sword awaits.",
                  ""
                  "If the clash of steel is music to your ears, if disciplined combat and unwavering bravery are your hallmarks, then the Sword is your true home. This guild is the bastion of strength and honor, a brotherhood of Fighters, Knights, and disciplined combatants who stand as the Land's shield. We train relentlessly, fight with courage, and our collective might is an unbreakable force against all who threaten peace. Draw your blade with us, and carve your saga into the annals of history!"
                  ]

    outlaw_info = ['Outlaw: The Path of Defiance',
                   '',
                   'For the lone wolf, for the rebel who bows to no one, the Outlaw life beckons – but be warned, it is not for the faint of heart!',
                   '',
                   'As an Outlaw, the very notion of a Guild is an insult. You thrive on defiance, going against the grain and making enemies of most others in the Land rather than bending to any collective will or enjoying the camaraderie of a group. This path drastically changes your gameplay, making you a target but opening unique opportunities for defiance and solo glory.']

    tada_utilities.text_pager(text, p)

    p.output(["", "--- Guild Selection ---"])
    while True:
        p.output(['',
                  'Join   Info',
                  " [C      IC]  Civilians",
                  " [O      IO]  Outlaws",
                  " [F      IF]  Iron Fist guild",
                  " [M      IM]  Mark of the Claw guild",
                  " [S      IS]  Mark of the Sword guild",
                  ''])
        # tada_utilities.text_pager(menu, p)
        guild_choice = input("Which option [C/IC, O/IO, F/IF, M/IM, S/IS]: ").lower()
        print()
        if guild_choice in ['ic']:
            p.output(civilian_info)
            continue
        if guild_choice in ['io']:
            p.output(outlaw_info)
            continue
        if guild_choice in ['if']:
            p.output(fist_info)
            continue
        if guild_choice in ['im']:
            p.output(claw_info)
            continue
        if guild_choice in ['is']:
            p.output(sword_info)
            continue
        if guild_choice == 'm':
            p.guild = Guild.CLAW
            break
        elif guild_choice == 's':
            p.guild = Guild.SWORD
            break
        elif guild_choice == 'f':
            p.guild = Guild.FIST
            break
        elif guild_choice == 'c':
            p.guild = Guild.CIVILIAN
            break
        elif guild_choice == 'o':
            p.guild = Guild.OUTLAW
            break
        else:
            print("Invalid choice.")

    if guild_choice in ['m', 's', 'f']:
        p.output(f"You have chosen to join the {p.guild} guild.")
    elif guild_choice in ['o', 'c']:
        p.output(f"You have chosen to be {a_or_an(p.guild)}.")


def roll_stats(p: "Player"):
    roll_number = 0
    chances = 5
    p.output(f"You will have {chances} chances to roll for {p.name}'s attributes.")
    while roll_number < chances:
        roll_number += 1
        print(f"Throw {roll_number} of {chances} - Rolling...", end='')
        # considering that running both these routines make unbelievably good 1st level stats,
        # i don't think they both need to be called.
        p.output([f"Throw {roll_number} of {chances} - Rolling...", ""])
        # TODO: each routine needs to be tested/compared to see what a more realistic set of stats is
        # for k in p.stats:
        # p.stats[k] = getnum()
        # logging.info(f'{k=} {p.stats[k]=}')
        class_bonuses(p)
        print()
        p.hit_points = 0
        # hp=((ps+pd+pt+pi+pw+pe)/6)+random(10)
        p.hit_points = (p.get_stat(PlayerStat.CHR) + p.get_stat(PlayerStat.CON) + p.get_stat(PlayerStat.DEX) +
                        p.get_stat(PlayerStat.INT) + p.get_stat(PlayerStat.STR) + p.get_stat(PlayerStat.WIS) +
                        p.get_stat(PlayerStat.EGY) // 7 + randrange(10))
        p.experience = 0

        if randrange(10) > 5:
            p.shield = 0
            p.armor = 0
        else:
            p.shield = randrange(30)
            p.armor = randrange(30)

        print(f"Charisma......: {p.get_stat(PlayerStat.CHR)}")
        print(f"Constitution..: {p.get_stat(PlayerStat.CON)}")
        print(f"Dexterity.....: {p.get_stat(PlayerStat.DEX)}")
        print(f"Intelligence..: {p.get_stat(PlayerStat.INT)}")
        print(f"Strength......: {p.get_stat(PlayerStat.STR)}")
        print(f"Wisdom........: {p.get_stat(PlayerStat.WIS)}\n")
        print(f"Hit Points....: {p.hit_points}")
        print(f"Energy Level..: {p.get_stat(PlayerStat.EGY)}")
        temp = p.shield
        print(f"Shield........: {f'{temp}%' if temp else 'None'}")
        temp = p.armor
        print(f"Armor.........: {f'{temp}%' if temp else 'None'}")
        print()
        temp = input_yes_no("Do you accept")  # returns True if 'yes'
        if temp:
            break
        shield = p.shield
        armor = p.armor

        p.output([f"Charisma......: {p.get_stat(PlayerStat.CHR)}",
                  f"Constitution..: {p.get_stat(PlayerStat.CON)}",
                  f"Dexterity.....: {p.get_stat(PlayerStat.DEX)}",
                  f"Intelligence..: {p.get_stat(PlayerStat.INT)}",
                  f"Strength......: {p.get_stat(PlayerStat.STR)}",
                  f"Wisdom........: {p.get_stat(PlayerStat.WIS)}",
                  f"",
                  f"Hit Points....: {p.hit_points}",
                  f"Energy Level..: {p.get_stat(PlayerStat.EGY)}",
                  f"Shield........: {f'{shield}%' if shield else 'None'}",
                  f"Armor.........: {f'{armor}%' if armor else 'None'}",
                  ""])

    if roll_number == chances:
        p.output('"Sorry, you\'re stuck with these scores," Verus says.')
        p.output(f'"Sorry, you{apostrophe}re stuck with these scores," Verus says.')




def getnum():
    """
    # ACOS code:
    getnum
     zz$=rnd$:a=0  # rnd$ = random character
    getnum1
     print ".";
     b=asc(rnd$)-64:if b>17 then b=b-7
     if b=>11 return
     a=a+1:if a<10 then zz$=rnd$:goto getnum1
     b=b+9:if b<11 goto getnum1
     return
    """
    a = 0  # loop counter
    b = 0  # value returned
    while a < 10:
        logging.info('loop iteration: a=%i' % a)
        # print(".", end='')
        b = randrange(1, 27)  # assuming 1-26 is rnd$'s limit
        logging.debug("stat b = %i" % b)
        if b > 17:
            b -= 7
            logging.debug("stat b > 17: -= 7 (now %i)" % b)
        if b >= 11:
            logging.debug("stat b >= 11 (now %i): return b" % b)
            return b
        a += 1
        b += 9
        logging.debug("loop iteration: %i, stat: b += 9 (now %i)" % (a, b))
        if b > 11:
            logging.debug("stat b > 9 (now %i), break" % b)
            break
    logging.debug("stat b = %i, return" % b)
    return b


def main(player: "Player") -> "Player":
    from flags import PlayerFlags
    from base_classes import PlayerMoneyTypes
    from tada_utilities import header
    # FIXME: initially, we wouldn't know which Player object to output it to (hasn't been created yet)
    #  so use IP address?  will use standard print() here until Player object is established
    logging.debug("In main")

    player.client_settings.screen_columns = 80
    player.connection_id = 1
    # these are enabled for debugging info:
    player.set_flag(PlayerFlags.DUNGEON_MASTER)  # True
    player.set_flag(PlayerFlags.DEBUG_MODE)  # True
    player.clear_flag(PlayerFlags.EXPERT_MODE)  # False

    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 200)
    player.set_silver_absolute(PlayerMoneyTypes.IN_BANK, 0)
    # TODO: preserve this money after character death somehow (save in a different file?)
    player.set_silver_absolute(PlayerMoneyTypes.IN_BAR, 0)

    header("Introduction")
    player.output("Your faithful servant Verus appears at your side, as if by magic.")
    player.output('Verus mentions, "Do not worry if ye answer wrong, ye can change thy answer later."')

    header("0. Choose Client")
    player = choose_client(player)  # TODO: net_server handles this handshaking

    header("00. Choose Settings")
    choose_settings(player)

    header("I. Choose Gender")
    choose_gender(player)

    header("II. Choose Name")
    player.output("Ye may choose your name.")
    choose_name(player)

    header("III. Choose Class")
    choose_class(player)

    header("IV. Choose Race")
    choose_race(player)

    header("V. Choose Age / Birthday")
    choose_age(player)

    header("VI. Final Edit")
    final_edit(player)

    header("VII. Choose Guild")
    choose_guild(player)

    header("VIII. Roll Statistics")
    roll_stats(player)

    header("Done!")

    # FIXME: logging.debug("__main__: client columns: %i" % character.ClientSettingsNames.COLUMNS)
    return player


def debug_menu(p: "Player"):
    from flags import PlayerFlags
    if p.query_flag(PlayerFlags.DEBUG_MODE):
        debug_menu = Menu(title="*** Debug Menu ***", columns=1)
        # in the case of a shortcut conflict (illustrated below), append an incremental number to the shortcut
        #   (e.g., "JC1", "JC2") to temporarily resolve the conflict
        debug_menu.add_item(MenuItem("Run through main() normally",
                                     "R", action=main))
        debug_menu.add_item(MenuItem(f"{'- or -'.rjust(20)}"))  # header item
        debug_menu.add_item(MenuItem("Jump to Choose Client",
                                     "JC", action=choose_client))
        debug_menu.add_item(MenuItem("Jump to Choose Settings",
                                     "JS", action=choose_settings))
        debug_menu.add_item(MenuItem("Jump to Choose Gender", "JG",
                                     action=choose_gender))
        debug_menu.add_item(MenuItem("Jump to Choose Name", "JN",
                                     action=choose_name))
        debug_menu.add_item(MenuItem("Jump to Choose Class",
                                     "JC", action=choose_class))
        debug_menu.add_item(MenuItem("Jump to Choose Race", "JR",
                                     action=choose_race))
        debug_menu.add_item(MenuItem("Jump to Choose Age / Birthday", "JA",
                                     action=choose_age))
        debug_menu.add_item(MenuItem("Jump to Final Edit", "JF",
                                     action=final_edit))
        debug_menu.add_item(MenuItem("Jump to Choose Guild", "JG",
                                     action=choose_guild))

        menu_stack = [debug_menu]
        navigate_menu(player, menu_stack)


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Logging is running")

    # start doctest
    doctest.testmod(verbose=True)

    """
    Define an apostrophe (') and quotation mark (") character for use in strings with speech in them.
    This avoids:
    * remembering whether to escape with "\'" (or nesting " ' " ' ") in single-quoted strings
    * being unable to use quotes (or apostrophes?) in triple-quoted f-strings
    
    >>> try:
    ...     print(f'Verus says, "I'm not sure."') # will truncate string because of second ' in "I'm"
    ... except SyntaxError as s:
    ...     print(s)
    SyntaxError: unterminated string literal (detected at line 1)
    
    This works, and doesn't use escaped characters which aren't allowed in triple-quoted f-strings:
    >>> quotation, apostrophe = '"', "'"
    >>> try:
    ...     print(f'Verus says, {quotation}I{apostrophe}m not sure.{quotation}') # proper "...I'm..."
    ... except NameError as n:
    ...     print(n)
    [...]
    """
    apostrophe = "'"
    quotation = '"'

    import player

    player_settings = player.set_up_rulan()
    # expects dict:
    player = player.Player(**player_settings)

    debug_menu(player)
    main(player)

    print()
    logging.debug("Final stats: %s" % player)
    # FIXME: print(character).__str__() method
