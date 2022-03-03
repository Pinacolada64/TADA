#!/bin/env python3

import json
from dataclasses import dataclass
import logging


@dataclass
class Monsters(object):
    number: int
    status: int
    name: str
    size: int
    strength: int
    special_weapon: int
    to_hit: int
    flags: list

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


def convert(txt_filename, monster_json_filename):
    write = True
    # TODO: before write to disk: monster_data = {'monsters': []}
    # flags with '[?]' I am unsure about
    monster_flags = {']': 'double attacks',
                     ':': 'mechanical being',
                     '.': 'increase strength [?]',
                     'E': 'evil',
                     'G': 'good',
                     ';;': 'heavy armor',
                     ';': 'light armor',
                     '<': 're-animates',
                     '>>': '2x chance find gold',
                     '>': 'chance find gold',
                     '++': 'cast multiple spells [?]',
                     '+': 'cast one spell [?]',
                     '#': 'cast turn to stone',
                     '*': 'poisonous attack',
                     '@': 'diseased attack',
                     '&': 'experience drain',
                     '%': 'magic-resistant',
                     '~': 'appears unaffected [?]',
                     '-': 'fire attack',
                     'X': 'no gold on body',
                     '$': 'multiple monsters',
                     '?': 'do not display "THE"',
                     # AC = Able to be Charmed:
                     'AC': 'charmable',
                     # regex: !(\d{2}), 2-digit quote number follows
                     '!': 'quote flag'}

    monster_sizes = {1: "huge",
                     2: "large",
                     3: "big",
                     4: "man-sized",
                     5: "short",
                     6: "small",
                     7: "swift"
                     }

    with open(txt_filename) as file:
        debug = True
        monster_list = []
        # get monster count:
        # enter a state where it's only looking for an integer value [monster count]
        num_monsters = 999  # some unrealistic number to serve as a flag
        while num_monsters == 999:
            # discard '#'-style comments:
            data = diskin(file)
            print(f'{data=}')
            break
        # hoping for an integer here:
        num_monsters = int(data)
        print(f'{num_monsters=}')
        # toss "^" separator:
        _ = diskin(file)
        count = 0
        """
        sample data:
        1) 1
        2) M.7RATTLESNAKE |*
        3) 2
        4) 0
        5) 8
        
        1) status
        2) M. Monster flag
           7  [optional] monster class
           RATTLESNAKE name
           |  [optional] monster flags follow
        3) strength
        4) special weapon to kill?
        5) to-hit
        
        (breakdown also found in /programming-notes/file-formats.txt)
        
        capture monster names (from 'M\.(?:\d)' through an optional '|' indicating flags)
        then convert to lowercase with .lower():
        
        """
        # monster_name = re.compile("^M\.?:\d(.+(?:\|))")
        while count < num_monsters:
            count += 1
            data = read_stanza(file)
            status = int(data[0])  # usually '1' for 'active'
            info = data[1]
            # capture optional monster class number after 'M.':
            temp = info[2]
            if temp.isdigit():  # re.compile('^M\.(?:\d)', info)
                monster_size = monster_sizes[int(temp)]
                start_name = 3  # starting position of name
            else:
                monster_size = None
                start_name = 2  # starting position of name
            logging.info(f'{monster_size=}')

            flag = info.rfind("|")
            if flag == -1:  # not found
                flag_list = None
                name = info[start_name:]
                logging.info("(No flags)")
            else:
                # '|' in monster name. it has monster flags:
                # trim name to before '|':
                # can also do: monster[start_name:monster.find('|')].rstrip()
                name = info[start_name:flag].rstrip()  # was flag - 1
                # clear per-monster flag list:
                flag_list = []
                # FIXME: parse all the flags after the | symbol and add
                #  their English keywords to flag_list
                logging.info(f'Flags: {info[flag + 1:]}')
                for k, v in monster_flags.items():
                    if k in info[flag + 1:]:
                        logging.info(f'with flag: {k=} {v=}')
                        flag_list.append(v)
            logging.info(f'{name=}')
            strength = int(data[2])
            special_weapon = int(data[3])
            to_hit = int(data[4])
            # toss "^" data block separator:
            _ = diskin(file)
            print(f"""Parsed input:\n
{count=}
{status=}
{name=}
{monster_size=}
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
            monster_data['desc'] = " ".join(descLines)
            """

            monster_data = {'number': count,
                            'status': status,
                            'name': name,
                            'size': monster_size,
                            'strength': strength,
                            'special_weapon': special_weapon,
                            'to_hit': to_hit,
                            'flags': flag_list}

            if debug:
                name = monster_data['name']
                status = monster_data['status']
                try:
                    flags = monster_data['flags']
                except ValueError:
                    flags = '(None)'
                logging.info(f'{count=} {status=} {name=} {flags=}')
            # add based on dataclass:
            monster = Monsters(**monster_data)
            logging.info(f"*** processed monster '{monster_data['name']}'")
            monster_list.append(monster)
            if debug:
                if count % 20 == 0:
                    _ = input("Hit Return: ")

        if write is True:
            with open(monster_json_filename, 'w') as monster_json:
                json.dump(monster_list, monster_json,
                          default=lambda o: {k: v for k, v in o.__dict__.items() if v}, indent=4)
            logging.info(f"wrote '{monster_json_filename}'")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    logging.info("Logging is running")

    convert('monsters.txt', 'monsters.json')
