#!/bin/env python3

import json
from dataclasses import dataclass
import logging


@dataclass
class Weapons(object):
    number: int
    status: int  # on player, in shoppe, in room
    name: str
    sound_effect: list  # hit/miss strings
    type: str  # magical, standard, cursed
    ease_of_use: int
    hits: int
    stability: int

    def __str__(self):
        return f'#{self.number} {self.name}'


def read_stanza(filename):
    """
    Read block of data [5 lines] from file
    skipping '#'-style comments; `^` is stanza delimiter

    :return: data[], the info from the file
    """
    count = 0
    line = []
    while count < 5:
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
    weapon_class = {1: "Energy",
                    2: "Bash/Slash",
                    3: "Poke/Jab",
                    4: "n/a",  # there isn't a class 4 category
                    5: "Pole/Range",
                    6: "n/a",  # there isn't a class 6 category
                    7: "n/a",  # there isn't a class 7 category
                    8: "Projectile",  # (+10% surprise, ammo bonus)
                    9: "Proximity"}

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
    Pole/Range    5      31   BLAM!!    BLAM! 
    n/a           6      37   FIZZLE    BOOOM!
    n/a           7      43   SIZZLE    SIZZLE   heat damage: FLAME THROWER, etc.
    Projectile    8      49   SWISH!    CRASH!
    Proximity     9      55   BRRRT!    BRRRT!

    https://github.com/Pinacolada64/TADA/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.WEAPON.S#L43
    This is the weapon class hit/miss "sound effect":
    https://github.com/Pinacolada64/TADA/blob/4c24c069139a495f97b2964d54c374b957c9eeab/SPUR-code/SPUR.COMBAT.S#L119
    """
    # TODO: update programming-notes.txt

    weapon_sounds = [
        # miss     # hit
        ["CRACK!", "CRACK!"],
        ["SWISH!", "SLASH!"],
        ["SWISH!", "BASH!"],
        ["SWISH!", "THUNK!"],
        ["SWISH!", "STAB!"],
        ["BLAM!!", "BLAM!"],
        ["FIZZLE", "BOOOM!"],
        ["SIZZLE", "SIZZLE"],
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
        # toss "^" separator:
        _ = diskin(file)
        count = 0
        """
        sample data:
        2 .................. Status: 0: On player
                                     1: In room
                                     2: In shoppe
        
        S. 1  LONG SWORD   (spaces for clarity,
        ^^ ^  |________|    no spaces in actual string)
        |  |      |
        |  |	  `-------- weapon name
        |  |
        |  `--------------- TY$	(Type? not 100% sure what this is for)
        |                   0 = ?
        |                   7 = Secondary heat damage (phaser, fireball, etc)
        |                   Nothing to do with weapon class though
        |
        `------------------ M. = Magical
                            S. = Standard
                            C. = Cursed

        5<cr> ............. stability (5-9) % x10 [AKA ease of use?]
        6<cr> ............. hits AKA base damage % (3-9) x10
        250<cr> ........... price (1-9999)
        2<cr> ............. weapon class
                            1: Energy (gets changed to 10)
                            2: Bash/Slash
                            3: Poke/Jab
                            4: [does not exist]
                            5: Pole/Range
                            6: [does not exist]
                            7: [does not exist]
                            8: Projectile (+10% surprise, ammo bonus)
                            9: Proximity
        [I don't see this in all weapons]:
        ??<cr> ............ Stability: 5-9 (aka damage?)

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
            status = int(data[0])  # 0=on player, 1=in room, 2=in shoppe
            info = data[1]  # "M."agical / "S."tandard / "C."ursed
            kind = info[2]  # digit
            # capture optional weapon type number:
            temp = info[2]
            if temp.isdigit():
                weapon_type = weapon_types[int(temp)]
                start_name = 3  # starting position of name
            else:
                weapon_type = None
                start_name = 2  # starting position of name
            logging.info(f'{weapon_type=}')

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
                # FIXME: parse all the flags after the | symbol and add
                #  their English keywords to flag_list
                logging.info(f'Flags: {info[flag + 1:]}')
                for k, v in weapon_flags.items():
                    if k in info[flag + 1:]:
                        logging.info(f'with flag: {k=} {v=}')
                        flag_list.append(v)
            stability = int(data[2])
            hits = int(data[3])
            price = int(data[4])
            weapon_class = int(data[5])
            # toss "^" data block separator:
            _ = diskin(file)
            print(f"""Parsed input:\n
{count=}
{status=}
{name=}
{weapon_size=}
{strength=}
{special_weapon=}
{to_hit=}
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

            weapon_data = {'number': count,
                           'status': status,
                           'name': name,
                           'size': weapon_size,
                           'strength': strength,
                           'special_weapon': special_weapon,
                           'to_hit': to_hit,
                           'flags': flag_list}

            if debug:
                name = weapon_data['name']
                status = weapon_data['status']
                try:
                    flags = weapon_data['flags']
                except ValueError:
                    flags = '(None)'
                logging.info(f'{count=} {status=} {name=} {flags=}')
            # add based on dataclass:
            weapon = weapons(**weapon_data)
            logging.info(f"*** processed weapon '{weapon_data['name']}'")
            weapon_list.append(weapon)
            if debug:
                if count % 20 == 0:
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
