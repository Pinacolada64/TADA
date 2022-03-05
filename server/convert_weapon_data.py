#!/bin/env python3

import json
from dataclasses import dataclass
import logging


@dataclass
class Weapons(object):
    number: int
    location: int  # on player, in shoppe, in room
    name: str
    kind: str  # magical, standard, cursed
    sound_effect: list  # hit/miss strings
    stability: int  # aka "ease of use"
    to_hit: int  # 3-9 (*10% in game) aka "damage"
    price: int
    weapon_class: str
    flags: list

    def __str__(self):
        return f'#{self.number} {self.name}'


def read_stanza(filename):
    """
    Read block of data [6 lines] from file
    skipping '#'-style comments; `^` is stanza delimiter

    :return: data[], the info from the file
    """
    count = 0
    line = []
    while count < 6:
        # 'diskin()' discards '#'-style comments
        temp = diskin(filename)
        if temp != "^":
            line.append(temp)
            count += 1
    logging.info("Stanza:")
    count = 0
    for n in line:
        logging.info(f'{count=} {n=}')
        count += 1
    return line


def diskin(filename):
    # get a line of data from disk file, discarding '#'-style comments
    while True:
        data = filename.readline().strip('\n')
        if data.startswith("#") is False:
            logging.info(f'keep {data=}')
            return data
        else:
            logging.info(f'toss {data=}')


def convert(txt_filename, weapon_json_filename):
    write = False

    weapon_kind = {"M.": "magic",
                   "S.": "standard",
                   "C.": "cursed"}

    weapon_classes = {1: "energy",
                      2: "bash/slash",
                      3: "poke/jab",
                      4: "n/a",  # there isn't a class 4 category
                      5: "pole/range",
                      6: "n/a",  # there isn't a class 6 category
                      7: "n/a",  # there isn't a class 7 category
                      8: "projectile",  # (+10% surprise, ammo bonus)
                      9: "proximity"}

    weapon_flags = {"x": "future expansion"}

    """
    I think only Skip's branch uses this weapon class "sound effect":
    (variable is 'vr=val(zz$)*6+1' because each SFX is 6 chars).

    Weapon class doesn't always match the expected SFX class.
    
    weapon         vr          zw$       zx$
    class        class   #   miss sfx  hit sfx   notes
    ----------   -----   --  --------  -------   ---------------
    n/a           0      1    CRACK!    CRACK!
    Energy        1      7    SWISH!    SLASH!
    Bash/Slash    2      13   SWISH!    BASH!
    Poke/Jab      3      19   SWISH!    THUNK!
    n/a           4      25   SWISH!    STAB!
    Pole/Range    5      31   KA-PWING! BLAM! 
    n/a           6      37   FIZZLE!   BOOOM!
    n/a           7      43   SIZZLE!   SIZZLE!  heat damage: FLAME THROWER, etc.
    Projectile    8      49   SWISH!    CRASH!
    Proximity     9      55   BRRRT!    BRRRT!

    https://github.com/Pinacolada64/TADA/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.WEAPON.S#L43
    This is the weapon class hit/miss "sound effect":
    https://github.com/Pinacolada64/TADA/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.COMBAT.S#L119
    then it's used here:
    https://github.com/Pinacolada64/TADA/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.COMBAT.S#L171
    """
    # TODO: update programming-notes.txt

    weapon_sounds = [
        # miss     # hit
        ["CRACK!", "CRACK!"],
        ["SWISH!", "SLASH!"],
        ["SWISH!", "BASH!"],
        ["SWISH!", "THUNK!"],
        ["SWISH!", "STAB!"],
        ["KA-PWING!", "BLAM!"],  # bullet ricocheting off target
        ["FIZZLE!", "BOOOM!"],
        ["SIZZLE!", "SIZZLE!"],
        ["SWISH!", "CRASH!"],
        ["BRRRT!", "BRRRT!"]
    ]

    with open(txt_filename) as file:
        debug = True
        weapon_list = []
        # get weapon count:
        # enter a state where it's only looking for an integer value [weapon count]
        num_weapons = 999  # some unrealistic number to serve as a flag
        while num_weapons == 999:
            # discard '#'-style comments:
            data = diskin(file)
            print(f'{data=}')
            break
        # hoping for an integer here:
        num_weapons = int(data)
        print(f'{num_weapons=}')
        # I eliminated "^" record separators in this file
        # _ = diskin(file)
        count = 0
        """
        sample data:
        2 .................. Location: 0: On player
                                       1: In room
                                       2: In shoppe [first 10 weapons are always
                                                     in the Shoppe]
        
        S. 1  LONG SWORD   (spaces for clarity,
        ^^ ^  |________|    no spaces in actual string)
        |  |      |
        |  |	  `-------- weapon name
        |  |
        |  `--------------- hit/miss "sound effect" class (0-9)
        |                   7 = Secondary heat damage (phaser, fireball, etc.)
        |                   Nothing to do with weapon class though
        |
        `------------------ M. = Magical
                            S. = Standard
                            C. = Cursed [first 10 weapons cannot be cursed
                                         since they are always in the Shoppe]

        5<cr> ............. "ease of use" % (5-9) *10 [AKA "stability"?]
        6<cr> ............. "to hit" % (3-9) *10 [chance of causing damage]
        250<cr> ........... price (1-9999)
        2<cr> ............. weapon class [wa]
                            1: Energy (gets changed to 10)
                            2: Bash/Slash
                            3: Poke/Jab
                            4: [does not exist]
                            5: Pole/Range
                            6: [does not exist]
                            7: [does not exist]
                            8: Projectile (+10% surprise, ammo bonus)
                            9: Proximity

        There don't seem to be flags associated with weapons, but I'm leaving
        the logic for them in, and the JSON data field, if we ever want to add
        them in the future.
        
        NOTE: All the null bytes padding each fixed-length "record" in weapons.txt
        wreak havoc with Windows' copy-and-paste functionality in Andy Fadden's
        "CiderPress" disk archive manager. I had to copy each record manually,
        being sure not to select any null bytes so that copy-and-paste would work.
        
        Ammunition carrier:
        1 ..................... (availability flag?)
        T..357 BANDOLIER|064	(TLOS differs ammo from carriers by putting "*"
                                 in ITEMS file [indicates an inactive item],
                                 and hard-coding items 147-150 to be carriers)
                                 [see: spur.misc5.s:ammo]

        (breakdown also found in /programming-notes/file-formats.txt)
        """
        # capture weapon names, then convert to lowercase with .lower():
        while count < num_weapons:
            count += 1
            data = read_stanza(file)
            # 0=on player, 1=in room, 2=in shoppe:
            location = int(data[0])
            # info: weapon kind, sfx, name
            info = data[1]
            # kind = "M."agic / "S."tandard / "C."ursed
            kind = weapon_kind[info[:2]]

            # capture weapon sfx number:
            temp = info[2:3]  # digit 0-9
            if temp.isdigit():
                # list within a list
                weapon_sound = weapon_sounds[int(temp)]  # [0]
                start_name = 3  # starting position of name
            else:
                weapon_sound = None
                start_name = 2  # starting position of name

            flag = info.rfind("|")
            if flag == -1:  # not found
                flag_list = None
                name = info[start_name:]
                logging.info("(No flags)")
            else:
                # '|' in weapon name. it has weapon flags:
                # trim name to before '|':
                # can also do: weapon[start_name:weapon.find('|')].rstrip()
                name = info[start_name:flag].rstrip()
                # clear per-weapon flag list:
                flag_list = []
                # parse all the flags after the | symbol,
                # add their English keywords to flag_list
                logging.info(f'Flags: {info[flag + 1:]}')
                for k, v in weapon_flags.items():
                    if k in info[flag + 1:]:
                        logging.info(f'with flag: {k=} {v=}')
                        flag_list.append(v)
            stability = int(data[2]) * 10
            to_hit = int(data[3]) * 10
            price = int(data[4])
            weapon_class = weapon_classes[int(data[5])]
            # toss "^" data block separator:
            # _ = diskin(file)
            print(f"""Parsed input:\n
{count=}
{location=}
{name=}
{kind=}
{weapon_sound=}
{stability=}%
{to_hit=}%
{price=}
{weapon_class=}
{flag_list=}
""")

            # TODO: maybe descriptions later
            """
            descLines = []
            moreLines = True
            while moreLines:
                line = diskin(file)
                if line != "^":
                    descLines.append(line)
                else:
                    moreLines = False
            weapon_data['desc'] = " ".join(descLines)
            """

            weapon_data = {"number": count,
                           'location': location,
                           'name': name,
                           'kind': kind,  # magical / standard / cursed
                           'sound_effect': weapon_sound,
                           "stability": stability,
                           'to_hit': to_hit,
                           "price": price,
                           "weapon_class": weapon_class,
                           'flags': flag_list
                           }

            if debug:
                name = weapon_data['name']
                location = weapon_data['location']
                try:
                    flags = weapon_data['flags']
                except ValueError:
                    flags = '(None)'
                logging.info(f'{count=} {location=} {name=} {flags=}')
            # add based on dataclass:
            weapon = Weapons(**weapon_data)
            logging.info(f"*** processed weapon '{weapon_data['name']}'")
            weapon_list.append(weapon)
            if debug:
                # if count % 20 == 0:
                _ = input("Hit Return: ")

        if write is True:
            with open(weapon_json_filename, 'w') as weapon_json:
                json.dump(weapon_list, weapon_json,
                          default=lambda o: {k: v for k, v in o.__dict__.items() if v}, indent=4)
            logging.info(f"wrote '{weapon_json_filename}'")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    logging.info("Logging is running")

    convert('weapons.txt', 'weapons.json')
