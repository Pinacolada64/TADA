from server.server import Player
from tada_utilities import header, output, input_number_range, input_yes_no

# from characters import Character

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


def choose_gender(p: Player):
    """step 1: choose character gender"""
    output('Verus squints myopically. "Are you a male or female?"', p)
    while True:
        temp = input("Enter [M]ale or [F]emale: ").lower()
        if temp == 'm':
            p.gender = 'male'
            break
        if temp == 'f':
            p.gender = 'female'
            break


def edit_gender(p: Player):
    """toggle existing character gender"""
    """
    :param p: Character to toggle gender of
    """

    while True:
        # FIXME: this is probably a dirty hack
        if p.gender == 'female':
            p.gender = 'male'
            break
        if p.gender == 'male':
            p.gender = 'female'
            break
    output(f"{p.name} is now {p.gender}.", p)


def choose_name(char: Character):
    """step 2: choose character name"""
    if char.name:
        # enter_name is called from multiple places, so it is a function:
        char.name = enter_name(char, edit_mode=True)

    elif char.name is None:
        # no existing name, prompt for new character name
        char.name = enter_name(char, edit_mode=False)


def edit_name(char: Character):
    """update character name"""
    # 'char' param shadows 'character' from outer scope
    char.name = enter_name(char, edit_mode=True)


def enter_name(char: Character, edit_mode: bool):
    """
    change character name. this can also be called during final player edit menu

    :param: _char: Character object (trying to make _private to eliminate shadowing)
    :param: edit_mode: True: editing existing name
                      False: no name assigned, entering new name
    :return: name: str
    """
    if edit_mode is True:
        print(f"([{return_key}] keeps '{char.name}.')")
    # TODO: this should be written as a generic edit prompt
    temp = input("What is your name: ")
    if edit_mode:
        # Return hit, or new string = old string:
        if temp == "" or temp == char.name:
            output(f"(Keeping the name of '{char.name}'.)", char)
    output(f'Verus checks to see if anyone else has heard of "{temp}" around '
           'here...', char)
    # TODO: check for existing name
    _ = f'"Seems to be okay." He '
    if edit_mode and char.name != temp:
        _ += "scratches out your old name and re-writes it"
    else:
        _ += "scribbles your name"
    _ += " in a dusty book."
    output(_, char)
    return temp


def choose_client(p: Player):
    """step 0: choose (or update existing) client name and parameters"""
    logging.info(f"{p.client['name']}")

    num_options = 3
    # FIXME: this unintentionally wraps text (as it's supposed to) but loses newlines
    # output('* ' * 80, c)

    # output() discards newlines, so can't use it here - even literal \n's don't work:

    # the width of this string is >40 characters
    output('"Which kind of client are you using?" Verus asks.',
           c)
    print()  # must be used in place of 'output('\n', c)'?
    output("## Client type     Screen size", c)
    output("-- --------------- -----------", c)
    output("1. Commodore 64    (40 x 25)", c)
    output("2. Commodore 128   (80 x 25)", c)
    output("3. TADA client", c)
    print()
    temp = input_number_range(prompt="Which client", lo=1, hi=num_options)

    if temp == 1:
        p.client['name'] = 'Commodore 64'
        p.client['columns'] = 40
        p.client['rows'] = 25
        p.client['translation'] = 'PETSCII'
    elif temp == 2:
        p.client['name'] = 'Commodore 128'
        p.client['columns'] = 80
        p.client['rows'] = 25
        p.client['translation'] = 'PETSCII'
    elif temp == 3:
        p.client['name'] = 'TADA Client'
        p.client['columns'] = 80
        p.client['rows'] = 25
        p.client['translation'] = "ASCII"

    # FIXME: until below code gets fixed, {return_key} will be "Enter"
    if p.client['translation'] == "PETSCII":
        p.return_key = "Return"
    else:
        p.return_key = "Enter"
    output(f"Client set to: {p.client['name']}", c)


def choose_class(c: Character):
    """step 3a: choose player class"""
    # NOTE: Character object 'class' attribute conflicts with built-in keyword
    # I am naming it char_class instead
    display_classes(c)
    temp = input_number_range("Class", lo=1, hi=9,
                              reminder='"Choose a class between 1 and 9," suggests Verus.')
    # was previously using 'temp = int(input(...))' but you can't cast a str -> int
    logging.info(f"{temp=}")
    # first time answering this prompt, there is no race to validate against:
    p.char_class = ['wizard' if p.gender == 'male' else 'witch',
                    'druid', 'fighter', 'paladin', 'ranger',
                    'thief', 'archer', 'assassin', 'knight'][temp - 1]


def display_classes(c: Character):
    # TODO: make this a subroutine:
    wizard = 'Wizard' if p.gender == 'male' else 'Witch '
    output('"Choose a class," Verus instructs.', c)
    print()
    output(f"(1) {wizard}   (4) Paladin  (7) Archer", c)
    output("(2) Druid    (5) Ranger   (8) Assassin", c)
    output("(3) Fighter  (6) Thief    (9) Knight", c)
    print()


def edit_class(p: Player):
    """
    this is called during final_edit() to change the class,
    then validate the resulting class/race combination
    """
    while True:
        display_classes(p)
        # TODO: Should be a help function to get help about individual classes.
        # Whether it's called up with "H1" or "1?" is undetermined.
        pc = input_number_range("Class", default=p.char_class.title(),
                                lo=1, hi=9,
                                reminder='"Choose a class between 1 and 9,"'
                                         ' suggests Verus.')
        # output(f'{return_key} keeps {p.char_class.title()}.', c)
        """
        if the character creation process has only asked for the class so far,
        race will be None, and we shouldn't validate the combination
        """
        # temp = input("Class [1-9]: ")
        # if temp.isalpha():
        #     output('"Numbers only, please."', c)
        # temp = int(temp)
        # valid = 0 < temp < 10  # accept 1-9
        # if valid:
        valid = validate_class_race_combo(p)
        if valid:
            # class/race combo is good, set class:
            p.char_class = ['wizard' if p.gender == 'male' else 'witch',
                            'druid', 'fighter', 'paladin', 'ranger',
                            'thief', 'archer', 'assassin', 'knight'][pc - 1]
            # end loop
            break


def validate_class_race_combo(p: Player):
    """
    make sure selected class/race combination is allowed

    :param: p: Player object to validate class and race of
    :returns: True if an acceptable combination, False if not
    """
    ok_combination = True
    logging.info("validate_class_race_combo reached")

    # list of bad combinations:
    if p.char_class == 'wizard' or p.char_class == 'witch':
        if p.race in ['ogre', 'dwarf', 'orc']:
            ok_combination = False

    elif p.char_class == 'druid':
        if p.race in ['ogre', 'orc']:
            ok_combination = False

    elif p.char_class == 'thief':
        if p.race == 'elf':
            ok_combination = False

    elif p.char_class == 'archer':
        if p.race in ['ogre', 'gnome', 'hobbit']:
            ok_combination = False

    elif p.char_class == 'assassin':
        if p.race in ['gnome', 'elf', 'hobbit']:
            ok_combination = False

    elif p.char_class == 'knight':
        if p.race in ['ogre', 'orc']:
            ok_combination = False

    if ok_combination is False:
        temp = f'''"{'An ' if p.race.startswith(('a', 'e', 'i', 'o', 'u')) else 'A '}'''
        temp += f'{p.race} {p.char_class} does not a good adventurer make. Try again."'
        output(temp, c)
    else:
        output('"Okay, fine with me," agrees Verus.', c)
    return ok_combination


def choose_race(c: Character):
    """step 3b: choose character race"""
    while True:
        display_races(c)
        temp = input_number_range(prompt="Race", lo=1, hi=9,
                                  reminder='"Enter a race from 1-9," Verus says.')
        # TODO: help option here ("H1", "1?" or similar, want to avoid reading 9 races as in original
        p.race = ['human', 'ogre', 'gnome', 'elf', 'hobbit', 'halfling',
                  'dwarf', 'orc', 'half-elf'][temp - 1]
        valid = validate_class_race_combo(c)
        if valid:
            break


def display_races(c: Character):
    output('"Choose a race," Verus instructs.', c)
    output('\n', c)
    output("(1) Human    (4) Elf      (7) Dwarf", c)
    output("(2) Ogre     (5) Hobbit   (8) Orc", c)
    output("(3) Gnome    (6) Halfling (9) Half-Elf", c)
    output('\n', c)
    # TODO: Should be a help function to get help about individual races.
    # Whether it's called up with "H1" or "1?" is undetermined.


def edit_race(p: Player) -> Player.race:
    race_valid = False
    while race_valid is False:
        display_races(c)
        if p.race:
            temp = input_number_range("Race", p, lo=1, hi=9,
                                      reminder='"Enter a race from 1-9," Verus suggests.')
            # output(f"{return_key} keeps '{p.race.title()}'.", c)
            print()
        # print("Race [1-9]", end='')
        # temp = input(": ")
        # TODO: make subroutine that validates isalpha() and allowable range:
        # if temp.isalpha():
        #     output(f'"Numbers only, please."', c)
        # if temp == '':
        #     output(f"Keeping '{p.race.title()}'.", c)
        # TODO: help option here ("H1", "1?" or similar, want to avoid reading 9 races as in original
        # temp = int(temp)
        # valid = 1 < temp < 9
        # if valid:
        p.race = ['human' 'ogre', 'gnome', 'elf', 'hobbit', 'halfling',
                  'dwarf', 'orc', 'half-elf'][temp - 1]
        race_valid = validate_class_race_combo(p.char_class, p.race)
        if race_valid is False:
            output('"Try picking a different race," Verus suggests.', c)
    # TODO: assign natural_alignment
    return p.race


def choose_age(c: Character):
    """
    step 4: allow player to select age and birthday

    if character.age = 0, it is displayed as 'Unknown'
    """
    age_valid = False
    temp_age = 0
    while age_valid is False:
        output('Enter [0] to be of an unknown age.', c)
        output('Enter [R] to select a random age between 15-50.', c)
        print()
        temp_age = input(output("Enter your age ([0], [R] or [15-50]): ", c))
        if temp_age.lower() == 'r':
            temp_age = randrange(15, 50)
            break
        if temp_age.isalpha():
            output('Verus tsks. "Please enter a number."', c)
        temp_age = int(temp_age)
        if temp_age == 0:
            """
            I think this is mostly for when people LOOK at your character:
            
            Looking at Railbender, you see a man of unknown age.
            
            Not entirely sure, though.
            """
            temp_age = 0
            break

        age_valid = validate_age(temp_age, c)
        if age_valid is False:
            output('"Try again," suggests Verus.', c)

    temp = 'of an unknown' if temp_age == 0 else f'{temp_age} years of'
    output(f'Verus studies you, and comments: "You\'re {temp} age."', c)
    p.age = temp_age

    # year = today.year - p.age FIXME: (if =0, what then?)
    _month = date.today().month
    _day = date.today().day
    _year = date.today().year
    output(f'"Which would you like your birthday to be?" asks Verus.', c)
    print()
    output(f"[T]oday ({_month}/{_day})", c)
    output("[A]nother date (choose month and day)", c)
    print()
    temp = input("Which [T, A]: ").lower()
    if temp == 't':
        # store as tuple:
        p.birthday = (_month, _day, _year)
        output(f'Set to today: {_month}/{_day}.', c)
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
        p.birthday = (_month, _day, _year)
        output(f"Birthday: {_month}/{_day}/{_year}", c)


# def validate_range(word, start, end, c=None):
#     """
#     :param word: Edit <word>
#     :param start: lowest number to allow
#     :param end: highest number to allow
#     :param c: Character object to output to
#     :return: temp, the value input
#     """
#     while True:
#         temp = input(f"{word} ({start}-{end}): ")
#         if temp.isalpha():
#             output("Numbers only, please.", c)
#         temp = int(temp)
#         if start - 1 < temp < end + 1:
#             return temp
#         output("No, try again.", c)


def validate_age(age: int, c: Character):
    """
    validate that the age == 0, or 15 < age < 50
    :param c: Character to output message to
    :param age: age entered
    :return: True if age == 0, or 15 < age 50, False if not
    """
    if age == 0:
        output("You're of an unknown age.", c)
        return True
    if age < 15:
        output('"Oh, come off it! You\'re not even old enough to handle a '
               'Staff yet."', c)
        return False
    if age > 50:
        output('"Hmm, we seem to be out of Senior Adventurer life '
               'insurance policies right now. Come back tomorrow!"', c)
        return False


def final_edit(c: Character):
    """allow player another chance to view/edit characteristics before saving"""
    output(f"Summary of character '{p.name}':", c)
    options = 5
    while True:
        output('\n', c)
        output(f'1.    Name: {p.name}', c)
        output(f'2.  Gender: {p.gender.title()}', c)
        output(f'3.   Class: {p.char_class.title()}', c)
        output(f'4.    Race: {p.race.title()}', c)
        if p.age == 0:
            temp = "Unknown"
        else:
            temp = p.age
        output(f'5.     Age: {temp}', c)
        # print(f'5.     Age: {p.age()}')
        # Birthday: tuple(month, day, year)
        output(f'  Birthday: {p.birthday[0]}/{(p.birthday[1])}/'
               f'{(p.birthday[2])}', c)
        output('\n', c)

        temp = input(f"Option [1-{options}, {return_key}=Done]: ")
        output('\n', c)
        if temp == '1':
            edit_name(c)
        if temp == '2':
            edit_gender(c)
        if temp == '3':
            edit_class(c)
        if temp == '4':
            edit_race(c)
        if temp == '5':
            choose_age(c)
        if temp == '':
            break


def choose_guild(c: Character):
    valid_guild = False
    while valid_guild is False:
        output('"Would you like to join a Guild?" asks Verus.', c)
        output('\n', c)
        output("    No, stay a [C]ivilian", c)
        output("    No, turn into an [O]utlaw", c)
        output("   Yes, join a [G]uild", c)
        output('\n', c)
        temp = input("Which option [C, O, G]: ").lower()
        output('\n', c)
        if temp in ['c', 'o']:
            guilds = {'c': 'civilian', 'o': 'outlaw'}
            p.guild = guilds[temp]
            _ = guilds[temp].title()
            output(f'"You have chosen to be a {_}."', c)
            valid_guild = True
            break
        if temp == 'g':
            while True:
                output('"Which guild would you like to join?" asks Verus expectantly.', c)
                output('\n', c)
                output("[F]ist", c)
                output("[S]word", c)
                output("[C]law", c)
                output("[N]one - changed my mind", c)
                output('\n', c)
                temp = input("Which option [F, S, C, N]: ").lower()[0:1]
                output('\n', c)
                if temp in ['f', 's', 'c']:
                    guilds = {'f': 'fist', 's': 'sword', 'c': 'claw'}
                    p.guild = guilds[temp]
                    _ = guilds[temp].title()
                    output(f'"You have chosen the {_} guild."', c)
                    valid_guild = True
                    break
                # N goes back to choose_guild()
                if temp == 'n':
                    output("Withdrawing guild choice.", c)
                    valid_guild = False


def roll_stats(p: Player):
    roll_number = 0
    chances = 5
    output(f"You will have {chances} chances to roll for {p.name}'s attributes.", c)
    while roll_number < chances:
        roll_number += 1
        print(f"Throw {roll_number} of {chances} - Rolling...", end='')
        # considering that running both these routines make unbelievably good 1st level stats,
        # i don't think they both need to be called.
        # TODO: each routine needs to be tested/compared to see what a more realistic set of stats is
        # for k in p.stats:
        # p.stats[k] = getnum()
        # logging.info(f'{k=} {p.stats[k]=}')
        class_race_bonuses(p)
        output('\n', p)
        p.hit_points = 0
        # hp=((ps+pd+pt+pi+pw+pe)/6)+random(10)
        p.hit_points = p.stats['chr'] + p.stats['con'] + p.stats['dex'] + p.stats['int'] \
            + p.stats['str'] + p.stats['wis'] + p.stats['egy'] // 7 + randrange(10)
        p.experience = 0

        if randrange(10) > 5:
            p.shield = 0
            p.armor = 0
        else:
            p.shield = randrange(30)
            p.armor = randrange(30)

        print(f"Charisma......: {p.stats['chr']}")
        print(f"Constitution..: {p.stats['con']}")
        print(f"Dexterity.....: {p.stats['dex']}")
        print(f"Intelligence..: {p.stats['int']}")
        print(f"Strength......: {p.stats['str']}")
        print(f"Wisdom........: {p.stats['wis']}\n")
        print(f"Hit Points....: {p.hit_points}")
        print(f"Energy Level..: {p.stats['egy']}")
        temp = p.shield
        print(f"Shield........: {f'{temp}%' if temp else 'None'}")
        temp = p.armor
        print(f"Armor.........: {f'{temp}%' if temp else 'None'}")
        output('\n', p)
        temp = input_yes_no("Do you accept")  # returns True if 'yes'
        if temp is True:
            break
    for k in p.stats:
        logging.info(f'{k=} {p.stats[k]}')
    if roll_number == chances:
        output('"Sorry, you\'re stuck with these scores," Verus says.', p)


def getnum():
    """ACOS code:
getnum
 zz$=rnd$:a=0   # rnd$ = random character
getnum1
 print ".";
 b=asc(rnd$)-64:if b>17 then b=b-7
 if b=>11 return
 a=a+1:if a<10 then zz$=rnd$:goto getnum1
 b=b+9:if b<11 goto getnum1
 return"""
    a = 0  # loop counter
    b = 0  # value returned
    while a < 10:
        print(".", end='')
        b = randrange(1, 26)  # assuming 1-26 is rnd$'s limit
        logging.info(f'{b=} init')
        if b > 17:
            b -= 7
            logging.info(f'{b=} -7')
        if b >= 11:
            logging.info(f'{b=} >= 11 return')
            return b
        a += 1
        logging.info(f'loop {a=}')
        b += 9
        logging.info(f'stat {b=} +9')
        if b > 11:
            logging.info(f'stat {b=} >11 break')
            break
    logging.info(f'stat {b=} return')
    return b


def class_race_bonuses(c: Character):
    """adjust stats of character 'c', based on class and race"""
    cc = p.char_class
    # if cp.flags['debug']:
    # just so we don't have to go through every char creation step...
    # TODO: prompt using display_classes()
    # cc = 'fighter'
    # logging.info(f'Shortcut: set {cc=}')

    # Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  Assassin Knight
    if p.is_magic_user(c):  # class 1, 'witch' or 'wizard'
        # these lists are all the same length because they loop through all
        # player attributes and add or subtract the number in that position.
        # if 0, the attribute is not modified.
        # NOTE: compared to t.np, stat 4 (Ego) has been removed from these lists
        #     chr con dex int str wis egy
        adj = [0, -1, 0, +2, 0, 0, 0]
    if cc == 'druid':  # class 2
        adj = [0, 0, 0, +2, -1, +2, 0]
    if cc == 'fighter':  # class 3
        adj = [0, +2, -1, -1, +2, 0, +2]
    if cc == 'paladin':  # class 4
        adj = [0, 0, +1, +1, +1, +1, 0]
    if cc == 'ranger':  # class 5
        adj = [0, 0, 0, -1, +1, -1, 0]
    if cc == 'thief':  # class 6
        adj = [0, 0, +1, 0, 0, 0, +2]
    if cc == 'archer':  # class 7
        adj = [0, 0, +2, 0, 0, 0, -1]
    if cc == 'assassin':  # class 8
        adj = [0, 0, -1, 0, +2, 0, 0]
    if cc == 'knight':  # class 9
        adj = [0, +1, 0, +1, 0, 0, -1]
    logging.info(f'Apply class bonuses: {adj=}')
    apply_bonuses(adj, c)

    cr = p.race
    # if p.flags['debug']:
    # just so we don't have to go through every char creation step...
    # TODO: prompt using display_classes()
    # cr = 'human'
    # logging.info(f'Shortcut: set {cr=}')

    # Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc     Half-Elf
    # these lists are all the same length because they loop through all
    # player attributes and add or subtract the number in that position.
    # if 0, the attribute is not modified.
    # NOTE: compared to t.np, stat 4 (Ego) has been removed from these lists
    #     chr con dex int str wis egy
    if cr == 'human':  # race 1
        adj = [0, +1, +2, +2, -1, 0, 0]
    if cr == 'ogre':  # race 2
        adj = [0, +2, -1, -2, +3, -1, 0]
    if cr == 'pixie':  # race 3
        adj = [0, 0, -1, 0, +1, +1, 0]
    if cr == 'elf':  # race 4
        adj = [0, -1, +2, +1, 0, +2, 0]
    if cr == 'hobbit':  # race 5
        adj = [0, 0, +1, +2, -1, 0, +1]
    if cr == 'gnome':  # race 6
        adj = [0, +1, +2, +2, -1, 0, 0]
    if cr == 'dwarf':  # race 7
        adj = [0, +1, -1, 0, +2, 0, 0]
    if cr == 'orc':  # race 8
        adj = [0, 0, +1, -1, +2, -1, +2]
    if cr == 'half-elf':  # race 9
        adj = [0, 0, +1, 0, 0, +1, 0]
    logging.info(f'Apply race bonuses: {adj=}')
    apply_bonuses(adj, c)


def apply_bonuses(adj: list, c: Character):
    """loop through stats, adjusting each based on character class/race bonuses and penalties

    :param: adj: list of adjustments from class_race_bonuses()
    :param: c: Character object to apply adjustments to
    :return: None"""
    num = 0  # index into adj[num]
    for k in p.stats:
        # class_calculate is not in skip's branch
        # https://github.com/Pinacolada64/TADA/blob/skip/SPUR-code/SPUR.NEW.S
        # nor spur.logon.s:
        # https://github.com/Pinacolada64/TADA/blob/master/SPUR-code/SPUR.LOGON.S
        # t.np:
        # y=stat, x=counter, b=max value
        # maximum allowable value for chr, con, dex: 18
        # maximum allowable value for int, str, wis, egy: 25
        # y=v1+86:for x=1 to 8:b=18:if x>3 then b=25
        if num < 3:
            _max = 18
        else:
            _max = 25
        # {:_276}
        # n=fn r(b):if n=1 then {:_276}
        before = randrange(2, _max)
        # n=n+val(mid$(a$,x*2-1,2)):if n<1 then {:_276}
        # poke y,n:y=y+1:print ".";
        # next:y=v1+86
        after = before + adj[num]
        # if n>b then n=b
        if after > _max:
            after = _max
        p.stats[k] = after
        logging.info(f'{k=} {before=} {after=} {_max=}')
        num += 1


def character_setup():
    """create character"""
    from characters import Character

    char = Character
    char.return_key = '[Return]'  # either "Return" or "Enter", depending on terminal type

    # FIXME: initially, we wouldn't know which Character object to output it to (hasn't been created yet)
    #  so use IP address?  will use standard print() here until Character object is established:
    char.connection_id = 1  # TODO: this is for CSIP, eventually
    # these are enabled for debugging info:
    char.flags = {'dungeon_master': True, 'debug': True, 'expert_mode': False},
    char.silver = {'in_hand': 0, 'in_bank': 0, 'in_bar': 0}
    logging.info(f"{char.client['columns']=}")

    header("Introduction")
    output("Your faithful servant Verus appears at your side, as if by magip.",
           char)
    output('Verus mentions, "Do not worry if ye answer wrong, ye can change thy answer later."',
           char)

    header("0. Choose Client")
    choose_client(char)  # TODO: net_server handles this

    header("I. Choose Gender")
    choose_gender(char)

    header("II. Choose Name")
    choose_name(char)

    header("III. Choose Class")
    choose_class(char)

    header("IV. Choose Race")
    choose_race(char)

    header("V. Choose Age")
    choose_age(char)

    # TODO: description
    # TODO: character quote

    header("VI. Final Edit")
    final_edit(char)

    header("Choose Guild")
    choose_guild(char)

    header("Roll Statistics")
    roll_stats(char)

    header("Done!")
    print()
    output("Final stats:", char)
    # can't use output() because of \n's
    # FIXME
    # print(character)
    return char


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    logging.info("Logging is running")

    return_key = '[Return]'

    character_setup()
