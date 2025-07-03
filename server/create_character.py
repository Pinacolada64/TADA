from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from player import Player
    from base_classes import Gender, PlayerClass, PlayerRace, PlayerStat, PlayerMoneyTypes
    from terminal import Translation
    from tada_utilities import header, input_number_range, input_yes_no
    from flags import PlayerFlags

from random import randrange  # for age and generating random stats

from datetime import date, datetime  # for birthday displays/calculations

import calendar  # monthrange for validating # of days in month

import logging

# import cbmcodecs2
# FIXME: broken package
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


def enter_name(_char: "Player", edit_mode: bool):
    """
    change character name. this can also be called during final player edit menu

    :param _char: Player object (trying to make _private to eliminate shadowing)
    :param edit_mode: True: editing existing name
                      False: no name assigned, entering new name
    :return: name: str
    """
    if edit_mode:
        print(f"({_char.client_settings.return_key} keeps '{_char.name}.')")
    # TODO: this should be written as a generic edit prompt
    temp = input("What is your name: ")
    if edit_mode:
        # Return hit, or new string = old string:
        if temp is None or temp == _char.name:
            _char.output(f"(Keeping the name of '{_char.name}'.)")
    _char.output(f'Verus checks to see if anyone else has heard of "{temp}" around '
                 'here...')
    # TODO: check for existing name
    _ = ['"Seems to be okay." He ']
    if edit_mode and _char.name != temp:
        _.append("scratches out your old name and re-writes it")
    else:
        _.append("scribbles your name")
    _.append("in a dusty book.")
    _char.output(" ".join(_))
    return temp


def choose_client(p: "Player"):
    """step 0: choose (or update existing) client name and parameters"""
    logging.info(f"{p.client_settings.NAME}")

    options = 3
    # FIXME: this unintentionally wraps text (as it's supposed to) but loses newlines
    # output('* ' * 80, p)

    # output() discards newlines, so can't use it here - even literal \n's don't work:

    # the width of this string is >40 characters
    p.output('"Which kind of client are you using?" Verus asks.')
    print()  # must be used in place of \n
    p.output("## Client type     Screen size")
    p.output("-- --------------- --------------------")
    p.output("1. Commodore 64    40 columns x 25 rows")
    p.output("2. Commodore 128   80 columns x 25 rows")
    p.output("3. TADA client")
    print()
    temp = input_number_range(prompt="Which client", lo=1, hi=options)

    if temp == 1:
        p.client_settings.NAME = 'Commodore 64'
        p.client_settings.COLUMNS = 40
        p.client_settings.ROWS = 25
        p.client_settings.TRANSLATION = Translation.PETSCII
    elif temp == 2:
        p.client_settings.NAME = 'Commodore 128 (80 columns)'
        p.client_settings.COLUMNS = 80
        p.client_settings.ROWS = 25
        p.client_settings.TRANSLATION = Translation.PETSCII
    elif temp == 3:
        p.client_settings.NAME = 'TADA Client'
        p.client_settings.COLUMNS = 80
        p.client_settings.ROWS = 25
        p.client_settings.TRANSLATION = Translation.ASCII

    # FIXME: until below code gets fixed, {return_key} will be "Enter"
    if p.client_settings.TRANSLATION == Translation.PETSCII:
        p.client_settings.RETURN_KEY = "Return"
    else:
        p.client_settings.RETURN_KEY = "Enter"
    p.output(f"Client set to: {p.client_settings.NAME}")


def choose_class(p: "Player"):
    """step 3a: choose player class"""
    # NOTE: Player object 'class' attribute conflicts with built-in keyword
    # I am naming it 'PlayerClass' instead
    pc = p.char_class
    # just so we don't have to go through every char creation step...
    if p.query_flag(PlayerFlags.DEBUG_MODE):
        shortcut = PlayerClass.FIGHTER
        answer = input_yes_no(f"Debug mode: Shortcut setting PC to {shortcut}?")
        if answer:
            pc = shortcut
            logging.debug("choose_class: Shortcut taken: set character_class: %s" % shortcut)
            return
    display_classes(p)
    temp = input_number_range("Class", lo=1, hi=9,
                              reminder='"Choose a class between 1 and 9," suggests Verus.')
    # was previously using 'temp = int(input(...))' but you can't cast a str -> int
    logging.info(f"{temp=}")
    # first time answering this prompt, there is no race to validate against:
    p.char_class = ['wizard' if p.gender == 'male' else 'witch',
                    'druid', 'fighter', 'paladin', 'ranger',
                    'thief', 'archer', 'assassin', 'knight'][temp - 1]


def display_classes(p: "Player"):
    wizard = 'Wizard' if p.gender == Gender.MALE else 'Witch '
    p.output('"Choose a class," Verus instructs.')
    print()
    p.output(f"(1) {wizard}   (4) Paladin  (7) Archer")
    p.output("(2) Druid    (5) Ranger   (8) Assassin")
    p.output("(3) Fighter  (6) Thief    (9) Knight")
    print()


def edit_class(p: "Player"):
    """
    this is called during final_edit() to change the class,
    then validate the resulting class/race combination
    """
    while True:
        display_classes(p)
        # TODO: Should be a help function to get help about individual classes.
        # Whether it's called up with "H1" or "1?" is undetermined.
        pc = input_number_range("Character class: ", default=p.char_class.title(),
                                lo=1, hi=9,
                                reminder='"Choose a class between 1 and 9,"'
                                         ' suggests Verus.')
        # output(f'{return_key} keeps {p.player_class.title()}.', p)
        """
        if the character creation process has only asked for the class so far,
        race will be None, and we shouldn't validate the combination
        """
        # temp = input("Class [1-9]: ")
        # if temp.isalpha():
        #     output('"Numbers only, please."', p)
        # temp = int(temp)
        # valid = 0 < temp < 10  # accept 1-9
        # if valid:
        valid = validate_class_race_combo(p)
        if valid:
            # class/race combo is good, set class:
            p.player_class = ['wizard' if p.gender == Gender.MALE else 'witch',
                              'druid', 'fighter', 'paladin', 'ranger',
                              'thief', 'archer', 'assassin', 'knight'][pc - 1]
            # end loop
            break


def validate_class_race_combo(p: "Player") -> bool:
    """
    make sure the selected class & race combination is allowed

    :param p: Player object to validate class and race of
    :return: True if an acceptable combination, False if not
    """
    bad_combination = False
    logging.debug("validate_class_race_combo reached")

    # list of bad class & race combinations:
    if p.char_class == PlayerClass.WIZARD:
        if p.char_race in [PlayerRace.OGRE, PlayerRace.DWARF, PlayerRace.ORC]:
            bad_combination = True

    elif p.char_class == PlayerClass.DRUID:
        if p.char_race in [PlayerRace.OGRE, PlayerRace.ORC]:
            bad_combination = True

    elif p.char_class == PlayerClass.THIEF:
        if p.char_race == PlayerRace.ELF:
            bad_combination = True

    elif p.char_class == PlayerClass.ARCHER:
        if p.char_race in [PlayerRace.OGRE, PlayerRace.GNOME, PlayerRace.HOBBIT]:
            bad_combination = True

    elif p.char_class == PlayerClass.ASSASSIN:
        if p.char_race in [PlayerRace.GNOME, PlayerRace.ELF, PlayerRace.HOBBIT]:
            bad_combination = True

    elif p.char_class == PlayerClass.KNIGHT:
        if p.char_race in [PlayerRace.OGRE, PlayerRace.ORC]:
            bad_combination = True

    if bad_combination:
        temp = f'''"{'An ' if p.char_race.startswith(('a', 'e', 'i', 'o', 'u')) else 'A '}'''
        temp += f'{p.char_race} {p.char_race} does not a good adventurer make. Try again."'
        p.output(temp)
    else:
        p.output('"Okay, fine with me," agrees Verus.')
    return bad_combination


def choose_race(p: "Player"):
    """step 3b: choose player race"""
    pr = p.char_race
    # just so we don't have to go through every char creation step...
    if p.query_flag(PlayerFlags.DEBUG_MODE):
        shortcut = PlayerRace.ORC
        answer = input_yes_no(f"Shortcut setting Player Race to {shortcut}?")
        if answer:
            p.char_race = shortcut
            logging.debug("choose_race: Shortcut taken: set character_race: %s" % shortcut)
    while True:
        display_races(p)
        temp = input_number_range(prompt="Race", lo=1, hi=9,
                                  reminder='"Enter a race from 1-9," Verus says.')
        # TODO: help option here ("H1", "1?" or similar, want to avoid reading 9 races as in original
        p.char_race = [PlayerRace.HUMAN,
                       PlayerRace.OGRE,
                       PlayerRace.GNOME,
                       PlayerRace.ELF,
                       PlayerRace.HOBBIT,
                       PlayerRace.HALF_ELF,  # FIXME: Wrong race
                       PlayerRace.DWARF,
                       PlayerRace.ORC,
                       PlayerRace.HALF_ELF]
        # 'human', 'ogre', 'gnome', 'elf', 'hobbit', 'halfling',
        #          'dwarf', 'orc', 'half-elf'][temp - 1]
        valid = validate_class_race_combo(p)
        if valid:
            break


def display_races(p: "Player"):
    p.output('"Choose a race," Verus instructs.')
    print()
    p.output("(1) Human    (4) Elf      (7) Dwarf")
    p.output("(2) Ogre     (5) Hobbit   (8) Orc")
    p.output("(3) Gnome    (6) Halfling (9) Half-Elf")
    print()
    # TODO: Should be a help function to get help about individual races.
    #  Whether it's called up with "H1" or "1?" is undetermined.


def edit_race(p: "Player") -> None:
    race_valid = False
    while not race_valid:
        display_races(p)
        if p.race:
            temp = input_number_range("Race", 1, 9, p,
                                      reminder='"Enter a race from 1-9," Verus suggests.')
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
        p.race = ['human', 'ogre', 'gnome', 'elf', 'hobbit', 'halfling',
                  'dwarf', 'orc', 'half-elf'][temp - 1]
        race_valid = validate_class_race_combo(p)
        if not race_valid:
            p.output('"Try picking a different race," Verus suggests.')
    return None


def choose_age(p: "Player"):
    """
    step 4: allow player to select age and birthday

    if player.age = 0, it is displayed as 'Unknown'
    """
    age_valid = False
    temp_age = 0
    while age_valid is False:
        p.output('Enter [0] to be of an unknown age.')
        p.output('Enter [R] to select a random age between 15-50.')
        print()
        temp_age = input("Enter your age (0, R or 15-50): ")
        if temp_age.lower() == 'r':
            temp_age = randrange(15, 50)
            break
        if temp_age.isalpha():
            p.output('Verus tsks. "Please enter a number."')
        temp_age = int(temp_age)
        if temp_age == 0:
            """
            I think this is mostly for when people LOOK at your character:
            
            Looking at Railbender, you see a man of unknown age.
            
            Not entirely sure, though.
            """
            temp_age = 0
            break

        age_valid = validate_age(temp_age, p)
        if age_valid is False:
            p.output('"Try again," suggests Verus.')

    temp = 'of an unknown' if temp_age == 0 else f'{temp_age} years of'
    p.output(f'Verus studies you, and comments: "You\'re {temp} age."')
    p.age = temp_age

    # year = today.year - p.age FIXME: (if =0, what then?)
    _month = date.today().month
    _day = date.today().day
    _year = date.today().year
    p.output(f'"Which would you like your birthday to be?" asks Verus.')
    print()
    p.output(f"[T]oday ({_month}/{_day})")
    p.output("[A]nother date (choose month and day)")
    print()
    temp = input("Which [T, A]: ").lower()
    if temp == 't':
        # store as datetime:
        p.birthday = datetime(_month, _day, _year)
        p.output(f'Set to today: {_month}/{_day}.')
        print()
    if temp == 'a':
        # year is calculated for leap year in monthrange() below, and displaying later
        # FIXME: what to do about age = 0
        _year = date.today().year - p.age
        _month = input_number_range(prompt="Month", lo=1, hi=12)
        # monthrange(year, day) returns tuple: (month, days_in_month)
        # we just need days_in_month, which is monthrange()[1]
        _day = input_number_range(prompt="Day", lo=1,
                                  hi=calendar.monthrange(year=_year, month=_month)[1])

        # store birthday as tuple: birthday[0] = month, [1] = day, [2] = year
        # store year anyway in case age = 0
        p.birthday = datetime(_month, _day, _year)
        p.output(f"Birthday: {_month}/{_day}/{_year}")


# def validate_range(word, start, end, p=None):
#     """
#     :param word: Edit <word>
#     :param start: lowest number to allow
#     :param end: highest number to allow
#     :param p: Player object to output to
#     :return: temp, the value input
#     """
#     while True:
#         temp = input(f"{word} ({start}-{end}): ")
#         if temp.isalpha():
#             output("Numbers only, please.", p)
#         temp = int(temp)
#         if start - 1 < temp < end + 1:
#             return temp
#         output("No, try again.", p)


def validate_age(age: int, p: "Player"):
    """
    validate that the age == 0, or 15 < age < 50
    :param p: Player to output message to
    :param age: age entered
    :return: True if age == 0, or 15 < age 50, False if not
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
    return None


def final_edit(p: "Player"):
    """allow player another chance to view/edit characteristics before saving"""
    p.output(f"Your Summary:")
    options = 5
    while True:
        print()
        p.output(f'1.    Name: {p.name}')
        p.output(f'2.  Gender: {p.gender}')
        p.output(f'3.   Class: {p.char_class}')
        p.output(f'4.    Race: {p.char_race}')
        # FIXME: this needs work
        age = p.birthday.year - datetime.year
        if age == 0:
            temp = "Unknown"
        else:
            temp = f"{age} years old"
        p.output(f'5.     Age: {temp}')
        # TODO: date format setting in player profile (YYYY-MM-DD or DD-MM-YYYY, mainly)
        p.output(f'  Birthday: {p.birthday.month}/{p.birthday.day}/'
                 f'{p.birthday.year}')
        print()

        temp = input(f"Option [1-{options}, {p.client_settings.RETURN_KEY}=Done]: ")
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
            break


def choose_guild(p: "Player"):
    valid_guild = False
    while not valid_guild:
        p.output('"Would you like to join a Guild?" asks Verus.')
        print()
        p.output("    No, stay a [C]ivilian.")
        print()
        p.output("""
        
    * You are safe from dueling by all but Outlaws.
    * You may only duel Outlaws.
    * You may remain in the Shoppe while you sleep.
""")
        p.output("    No, become an [O]utlaw")
        p.output("   Yes, join a [G]uild")
        p.output("""
    * You may seek refuge in your Guild headquarters,
      donating or taking items which other members have
      made available to you in your time of need.""")
        print()
        temp = input("Which option [C, O, G]: ").lower()
        print()
        if temp in ['c', 'o']:
            guilds = {'c': 'civilian', 'o': 'outlaw'}
            p.guild = guilds[temp]
            _ = guilds[temp].title()
            p.output(f'"You have chosen to be a {_}."')
            valid_guild = True
            break
        if temp == 'g':
            while True:
                """Indicate if you wish to join a Clan:

        1) Join Mark of the Claw    \|/
        2) Join Mark of the Sword   -}----
        3) Join The Iron Fist       ==[]
        4) Become a Civilian. You are safe
           from dueling from all but Out-
           laws. You may only duel Outlaws.
           You may remain in the Shoppe while you sleep.
        5) Become an Outlaw."""

                p.output('"Which guild would you like to join?" asks Verus expectantly.')
                print()
                p.output("Join the Iron [F]ist ==[]")
                p.output("Join Mark of the [S]word =}----")
                p.output("Join Mark of the [C]law \|/")
                print()
                p.output("[N]one - changed my mind")
                print()
                temp = input("Which option [F, S, C, N]: ").lower()[0:1]
                print()
                if temp in ['f', 's', 'c']:
                    guilds = {'f': 'fist', 's': 'sword', 'c': 'claw'}
                    p.guild = guilds[temp]
                    _ = guilds[temp].title()
                    p.output(f'"You have chosen the {_} guild."')
                    valid_guild = True
                    break
                # N goes back to choose_guild()
                if temp == 'n':
                    p.output("Withdrawing guild choice.")
                    valid_guild = False


def roll_stats(p: "Player"):
    roll_number = 0
    chances = 5
    p.output(f"You will have {chances} chances to roll for {p.name}'s attributes.")
    while roll_number < chances:
        roll_number += 1
        print(f"Throw {roll_number} of {chances} - Rolling...", end='')
        # considering that running both these routines make unbelievably good 1st level stats,
        # i don't think they both need to be called.
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

    if roll_number == chances:
        p.output('"Sorry, you\'re stuck with these scores," Verus says.')


def getnum():
    """ACOS code:
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
        print(".", end='')
        b = randrange(1, 26)  # assuming 1-26 is rnd$'s limit
        logging.debug("getnum: init: stat b = %i" % b)
        if b > 17:
            b -= 7
            logging.debug("getnum: stat b -= 7 (now %i)" % b)
        if b >= 11:
            logging.debug("getnum: stat b >= 11 (now %i): return b" % b)
            return b
        a += 1
        logging.info(f'loop {a=}')
        b += 9
        logging.debug("getnum: loop: a += 1 (now %i), stat: b += 9 (now %i)" % (a, b))
        if b > 11:
            logging.debug("getnum: stat b > 9 (now %i), break" % b)
            break
    logging.debug("getnum: stat b = %i, return" % b)
    return b


def class_bonuses(p: "Player"):
    """
    adjust stats of Player p, based on player class

    these lists are all the same length because they loop through all
    player attributes and add or subtract the number in that position.
    if 0, the attribute is not modified.
    NOTE: compared to t.np, stat 4 (Ego) has been removed from these lists
    """
    # TODO: prompt using display_classes()

    #     chr con dex int str wis egy
    class_bonuses = {
        PlayerClass.WIZARD: [0, -1, 0, +2, 0, 0],  # class 1
        PlayerClass.DRUID: [0, 0, 0, +2, -1, +2],  # class 2
        PlayerClass.FIGHTER: [0, +2, -1, -1, +2, 0, +2],  # class 3
        PlayerClass.PALADIN: [0, 0, +1, +1, +1, +1, 0],  # class 4
        PlayerClass.RANGER: [0, 0, 0, -1, +1, -1, 0],  # class 5
        PlayerClass.THIEF: [0, 0, +1, 0, 0, 0, +2],  # class 6
        PlayerClass.ARCHER: [0, 0, +2, 0, 0, 0, -1],  # class 7
        PlayerClass.ASSASSIN: [0, 0, -1, 0, +2, 0, 0],  # class 8
        PlayerClass.KNIGHT: [0, +1, 0, +1, 0, 0, -1],  # class 9
    }
    logging.debug('class_bonuses: Apply class bonuses: {adj=}')
    # Get bonus list based on player class
    bonus_list = class_bonuses.get(p.char_class)

    if bonus_list:
        logging.debug("class_race_bonuses: Apply class bonuses: %s" % bonus_list)
        apply_bonuses(bonus_list, p)
    else:
        logging.warning(f'class_race_bonuses: Unknown class {p.char_class}')

def calculate_race_bonuses(p: "Player"):
    pr = p.char_race
    if p.query_flag(PlayerFlags.DEBUG_MODE):
        # just so we don't have to go through every char creation step...
        p.output("fixme")
        # TODO: prompt using display_classes()
        pr = PlayerRace.HUMAN
        logging.info(f'Shortcut: set {pr=}')

    # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc     Half-Elf
    # TODO: add Elf bow ability bonus
    # these lists are all the same length because they loop through all
    # player attributes and add or subtract the number in that position.
    # if 0, the attribute is not modified.
    # NOTE: compared to t.np, stat 4 (Ego) has been removed from these lists
    #     order of elements is: chr con dex int str wis egy
    race_bonuses = {PlayerRace.HUMAN: [0, +1, +2, +2, -1, 0, 0],  # race 1
                    PlayerRace.OGRE: [0, +2, -1, -2, +3, -1, 0],  # race 2
                    PlayerRace.PIXIE: [0, 0, -1, 0, +1, +1, 0],  # race 3
                    PlayerRace.ELF: [0, -1, +2, +1, 0, +2, 0],  # race 4
                    PlayerRace.HOBBIT: [0, 0, +1, +2, -1, 0, +1],  # race 5
                    # FIXME: Gnome bonuses same as Human?:
                    PlayerRace.GNOME: [0, +1, +2, +2, -1, 0, 0],  # race 6
                    PlayerRace.DWARF: [0, +1, -1, 0, +2, 0, 0],  # race 7
                    PlayerRace.ORC: [0, 0, +1, -1, +2, -1, +2],  # race 8
                    PlayerRace.HALF_ELF: [0, 0, +1, 0, 0, +1, 0],  # race 9
                    }
    adj = race_bonuses[p.char_race]
    logging.info(f'Apply race bonuses: {adj=}')
    apply_bonuses(adj, p)


def apply_bonuses(adj: list, p: "Player"):
    """
    loop through stats, adjusting each based on p class & race bonuses & penalties

    :param adj: list of adjustments from class_bonuses() & race_bonuses()
    :param p: Player object's stat_name to apply adjustments to
    :return: None
    """
    for i, k in enumerate(PlayerStat, start=1):
        # class_calculate is not in skip's branch
        # https://github.com/Pinacolada64/TADA/blob/skip/SPUR-code/SPUR.NEW.S
        # nor spur.logon.s:
        # https://github.com/Pinacolada64/TADA/blob/master/SPUR-code/SPUR.LOGON.S
        # t.np:
        # y=stat, x=counter, b=max value
        # maximum allowable value for chr, con, dex: 18
        # maximum allowable value for int, str, wis, egy: 25
        # y=v1+86:for x=1 to 8:b=18:if x>3 then b=25
        if i < 3:
            maximum = 18
        else:
            maximum = 25
        # {:_276}
        # n=fn r(b):if n=1 then {:_276}
        before = randrange(2, maximum)
        # n=n+val(mid$(a$,x*2-1,2)):if n<1 then {:_276}
        # poke y,n:y=y+1:print ".";
        # next:y=v1+86
        after = before + adj[i]
        # if n>b then n=b
        if after > maximum:
            after = maximum
        p.set_stat_absolute(k, after)
        logging.info("apply_bonuses: k=%i, before=%i, after=%i, maximum=%i" %
                     (k, before, after, maximum))

def main(player: "Player") -> "Player":
    from flags import PlayerFlags
    from base_classes import PlayerMoneyTypes
    from tada_utilities import header
    # test of using code from create_character from new_player_2.py
    # FIXME: initially, we wouldn't know which Player object to output it to (hasn't been created yet)
    #  so use IP address?  will use standard print() here until Player object is established
    logging.debug("In main")

    player.connection_id = 1
    # these are enabled for debugging info:
    player.set_flag(PlayerFlags.DUNGEON_MASTER)  # True
    player.set_flag(PlayerFlags.DEBUG_MODE)  # True
    player.clear_flag(PlayerFlags.EXPERT_MODE)  # False

    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 200)
    player.set_silver_absolute(PlayerMoneyTypes.IN_BANK, 0)

    # TODO: preserve this money after character death somehow (save in a different file?)
    player.set_silver_absolute(PlayerMoneyTypes.IN_BAR, 0)

    player.client_settings.RETURN_KEY = "Enter"

    header("Introduction")
    player.output("Your faithful servant Verus appears at your side, as if by magic.")
    player.output('Verus mentions, "Do not worry if ye answer wrong, ye can change thy answer later."')

    header("0. Choose Client")
    choose_client(player)  # TODO: net_server handles this

    header("I. Choose Gender")
    choose_gender(player)

    header("II. Choose Name")
    choose_name(player)

    header("III. Choose Class")
    choose_class(player)

    header("IV. Choose Race")
    choose_race(player)

    header("V. Choose Age")
    choose_age(player)

    header("VI. Final Edit")
    final_edit(player)

    header("Choose Guild")
    choose_guild(player)

    header("Roll Statistics")
    roll_stats(player)

    header("Done!")

    # FIXME: logging.debug("__main__: client columns: %i" % character.ClientSettingsNames.COLUMNS)
    return player

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Logging is running")

    import player
    rulan_settings = player.set_up_rulan()
    # expects dict:
    rulan = player.Player(**rulan_settings)
    main(rulan)
    print()
    logging.debug("Final stats: %s" % rulan)
    # can't use output() because of \n's
    # FIXME: print(character).__str__() method
