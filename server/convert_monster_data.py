#!/bin/env python3

import json
from dataclasses import dataclass
import logging
import re


@dataclass
class Items(object):
    number: int
    name: str
    # armor | book | cursed | compass | drink | food | shield | treasure | weapon
    type: str
    flags: list
    price: int

    def __str__(self):
        return f'#{self.number} {self.name}'


def read_stanza(filename):
    """
    Read block of data [usually 5 lines] from file
    skipping '#'-style comments; `^` is stanza delimiter

    :return: data[], the info from the file
    """
    line = []
    for count in range(1, 5):
        while True:
            data = filename.readline().strip('\n')
            while data.startswith("#") is False:
                logging.info(f'{data=}')
                line[count] = data
                break
            # while filename.readline().strip('\n')


"""
    def get_line(filename):
    # get a line of data from disk file, skipping '#'-style comments
    # '^' marks end of stanza
        with open(filename) as monster_txt:
            while True:
                ...?
"""

def convert(monster_txt_filename, monster_json_filename):
    write = False
    monster_data = {'monsters': []}
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

    monster_classes = {1: "huge",
                       2: "large",
                       3: "big",
                       4: "man-sized",
                       5: "short",
                       6: "small",
                       7: "swift"
                       }

    with open(monster_txt_filename) as monster_txt:
        # TODO: not sure how to code this yet
        debug = True
        monster_list = []
        # get monster count:
        # enter a state where it's only looking for an integer value [monster count]
        # not sure if this could be farmed out to a function
        num_monsters = 999  # some unrealistic number to serve as a flag
        while num_monsters == 999:
            # discard '#'-style comments:
            while True:
                data = monster_txt.readline().strip('\n')
                while data.startswith("#") is False:
                    print(f'{data=}')
                break
            # hoping for an integer here:
            data = int(monster_txt.readline().strip('\n'))
            print(f'found {data=}')
            if data != 0:
                num_monsters = data
                break
            # toss "^" separator:
            _ = monster_txt.readline().strip('\n')
        count = 0
"""
        sample data:
        M.7RATTLESNAKE |*
        capture monster names (from 'M\.(?:\d)' through an optional '|' indicating flags)
        then convert to lowercase with .lower():
"""
        monster_name = re.compile('^M\.?:\d(.+(?:\|))')
        while count < num_monsters:  # was 'while True' which... loops over the same item infinitely?
            monster_data = {}
            status = monster_txt.readline().strip('\n')
            info = monster_txt.readline().strip('\n')
            # TODO: capture optional monster class number after 'M.':
            monster_class = re.compile('^M\.(?:\d)', info)
            name = info.monster_name.lower()
            strength = monster_txt.readline().strip('\n')
            special_weapon = monster_txt.readline().strip('\n')
            to_hit = monster_txt.readline().strip('\n')
            # toss "^" data block separator:
            _ = monster_txt.readline().strip('\n')
            print(f"""Raw input:\n
{status=}
{info=}
{strength=}
{special_weapon=}
{to_hit=}
""")
            # '#'-style comments can begin the line, and a null is EOF:
            if status.startswith('#') is False and status != '':
                count += 1
                field = info.split(',')
                if debug:
                    for k in field:
                        print(f"'{k}' ", end='')
                    print()
                monster_data['number'] = count
                monster_data['type'] = monster_flags[field[0]]
                # monster name, strip trailing spaces:
                temp = field[1].strip()
                logging.info(f'{temp=}')
                # if '|' in monster name, it has monster flags:
                pos = temp.rfind('|')  # returns -1 if not found
                if pos != -1:
                    # trim name to before '|':
                    name = temp[:pos]
                    monster_data['name'] = name
                    # clear flag_list:
                    flag_list = []
                    # FIXME: not sure if 'enumerate' will work; I want to parse all the flags
                    #  after the | symbol and add their English keywords to flag_list, maybe 'yield'?
                    for flag in enumerate(monster_flags):
                        logging.info(f'with flag: {flag=}')
                        flag_list.append(flag)
                        monster_data['flags'] = flag_list
                else:
                    monster_data['name'] = field[1].rstrip(' ')
                    monster_data['flags'] = None
                    logging.info("(No flags)")

                monster_data['price'] = int(field[2])
                # TODO: maybe descriptions later
                """
                descLines = []
                moreLines = True
                while moreLines:
                    line = objTxt.readline().strip()
                    if line != "^":
                        descLines.append(line)
                    else:
                        moreLines = False
                itemData['desc'] = " ".join(descLines)
                """

                if debug:
                    type = monster_data['type']
                    name = monster_data['name']
                    try:
                        flags = monster_data['flags']
                    except ValueError:
                        flags = '(None)'
                    print(f'{count=} {type=} {name=} {flags=}')
                item = Items(**monster_data)
                logging.info(f"*** processed monster '{monster_data['name']}'")
                monster_list.append(item)
                if debug:
                    if count % 20 == 0:
                        _ = input("Hit Return: ")
                        # logging.info(f'{count=} {len(monster_list)=}')

        if write is True:
            with open(monster_json_filename, 'w') as monster_json:
                json.dump(monster_list, monster_json,
                          default=lambda o: {k: v for k, v in o.__dict__.items() if v}, indent=4)
            logging.info(f"wrote '{monster_json_filename}'")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    logging.info("Logging is running")

    convert('monsters.txt', 'monsters.json')
