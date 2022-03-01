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

    with open(txt_filename) as file:
        # TODO: not sure how to code this yet
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
        M.7RATTLESNAKE |*
        capture monster names (from 'M\.(?:\d)' through an optional '|' indicating flags)
        then convert to lowercase with .lower():
        """
        # monster_name = re.compile("^M\.?:\d(.+(?:\|))")
        while count < num_monsters:  # was 'while True' which... loops over the same item infinitely?
            data = read_stanza(file)
            monster_data = {}
            status = int(data[0])  # usually '1' for 'active'
            info = data[1]
            # TODO: capture optional monster class number after 'M.':
            temp = info[2:1].isdigit()
            start_name = 2  # starting position of name
            if temp:  # re.compile('^M\.(?:\d)', info)
                monster_class = monster_classes.items(temp - 1)
                start_name = 3
            end_name = info.rfind("|")
            if end_name == -1:  # not found
                end_name = len(info)
            name = info[start_name:end_name]
            print(f'{name=}')
            strength = data[3]
            special_weapon = data[4]
            to_hit = data[5]
            # toss "^" data block separator:
            _ = diskin(file)
            print(f"""Raw input:\n
{status=}
{info=}
{strength=}
{special_weapon=}
{to_hit=}
""")
            if status.startswith('#') is False and status != '':
                count += 1
                field = info.split(',')
                if debug:
                    for k in field:
                        print(f"'{k}' ", end='')
                    print()
                monster_data['number'] = count
                monster_data['type'] = monster_flags[field[0]]

                # get monster name, strip trailing spaces:
                temp = field[1].strip()
                logging.info(f'{temp=}')

                # if '|' in monster name, it has monster flags:
                pos = temp.rfind('|')  # returns -1 if not found
                if pos != -1:
                    # trim name to before '|':
                    name = temp[:pos]
                    monster_data['name'] = name
                    flags = temp[pos + 1:]  # flags after '|'
                    # clear monster flag list:
                    flag_list = []
                    # FIXME: parse all the flags after the | symbol and add
                    #  their English keywords to flag_list
                    for k, v in monster_flags.items():
                        if k in flags:
                            logging.info(f'with flag: {k=} {v=}')
                            flag_list.append(v)
                    monster_data['flags'] = flag_list
                    logging.info(f'{monster_data["flags"]=}')
                else:
                    monster_data['name'] = field[1].rstrip(' ')
                    monster_data['flags'] = None
                    logging.info("(No flags)")

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
