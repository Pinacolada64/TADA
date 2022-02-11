#!/bin/env python3

import json
from dataclasses import dataclass
import logging


@dataclass
class Items(object):
    number: int
    name: str
    # armor | book | cursed | compass | drink | food | shield | treasure | weapon
    type: str
    flags: dict
    price: int

    def __str__(self):
        return f'#{self.number} {self.name}'


def convert(object_txt_filename, object_json_filename):
    # FIXME: items 127 and 129 are duplicates (LAW ROCKET)
    write = False
    object_data = {'objects': []}
    object_types = {'A': 'armor', 'B': 'book', 'C': 'cursed', 'P': 'compass',
                    'S': 'shield', 'T': 'treasure'}
    """
    object_state can be one of several statuses:
     tuple: (level_number, room_number)  # maybe irrelevant, already stored in map data
        buried flag {position: "n | ne | e | se | s | sw | w | nw | center", booby-trap: [A-I]}
     held by player
     held by ally
     in locker
     destroyed
    """
    with open(object_txt_filename) as object_txt:
        count = 0
        debug = True
        object_list = []
        while count < 20:  # was 'while True' which... loops over the same item infinitely?
            object_data = {}
            line = object_txt.readline()
            logging.info(f"Raw input: '{line}'")
            # '#'-style comments can begin the line, and a null is EOF:
            if line.startswith('#') is False and line != '':
                count += 1
                field = line.strip('\n').split(',')
                if debug:
                    for k in field:
                        print(f"'{k}' ", end='')
                    print()
                object_data['number'] = count
                object_data['type'] = object_types[field[0][0:1]]
                # skip past the 'x.' prefix, strip trailing spaces:
                temp = field[0][2:].strip()
                # if '|' in object name, it is 'used with' item
                pos = temp.rfind('|')  # index('|')
                if pos:
                    # object_data['name'] = field[1][:container - 1:].rstrip(' ')
                    # trim name to just before '|':
                    name = temp[pos - 1:]
                    # 2-digit round count
                    rounds = temp[pos + 1:2]
                    # 1-digit damage count
                    damage = temp[pos + 3:1]
                    # can 'blah.rfind('substring') to match with complementary item:
                    used_with = temp[pos + 4:]
                    logging.info(f'{rounds=}, {damage=}, {used_with=}')
                    _ = input("Hit Return: ")
                    temp = {"rounds": rounds,
                            "damage": damage,
                            "used_with": used_with}
                    object_data['flags'] = temp
                else:
                    object_data['name'] = field[1].rstrip(' ')
                    object_data['flags'] = ''
                    logging.info("(Not a container)")

                object_data['price'] = field[2]
                # TODO: maybe descriptions later
                # descLines = []
                # moreLines = True
                # while moreLines:
                #     line = mapTxt.readline().strip()
                #     if line != "^":
                #         descLines.append(line)
                #     else:
                #         moreLines = False
                # roomData['desc'] = " ".join(descLines)

                if debug:
                    name = object_data['name']
                    price = object_data['price']
                    try:
                        flags = object_data['flags']
                    except ValueError:
                        flags = '(None)'
                    print(f'{count=} {name=} {flags=} {price=}')
                item = Items(**object_data)
                logging.info(f"*** processed object '{object_data['name']}'")
                object_list.append(item)
                if debug:
                    logging.info(f'{object_list}')
            else:
                print("breaking")

        if write is True:
            with open(object_json_filename, 'w') as object_json:
                json.dump(object_data, object_json,
                          default=lambda o: {k: v for k, v in o.__dict__.items() if v}, indent=4)
            logging.info(f"wrote '{object_json_filename}'")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    logging.info("Logging is running")

    convert('objects.txt', 'objects.json')
