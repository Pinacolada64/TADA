#!/bin/env python3

import json
from dataclasses import dataclass


@dataclass
class Items(object):
    number: int
    type: str  #
    name: str
    price: str
    # flags: list  # later

    def __str__(self):
        return f'#{self.number} {self.name}'


def convert(object_txt_filename, objectJsonFilename):
    # FIXME: items 127 and 129 are duplicates (LAW ROCKET)
    write = False
    object_data = {'objects': []}
    object_types = {'A': 'armor', 'B': 'book', 'C': 'cursed', 'P': 'compass',
                    'S': 'shield', 'T': 'treasure'}
    with open(object_txt_filename) as object_txt:
        count = 0
        while True:
            object_data = {}
            line = object_txt.readline()
            print(line)
            # '#'-style comments can begin the line, and a null is EOF:
            while line.startswith('#') is False and line != '':
                count += 1
                field = line.split(',')
                # for k in field:
                #     print(f'{k}')
                # break
                object_data['number'] = count
                object_data['type'] = object_types[field[0][0:1]]
                # skip past the 'x.' prefix, strip trailing spaces:
                object_data['name'] = field[0][2:].strip()
                object_data['price'] = field[2]
                # TODO: maybe descriptions later
                print(f'{count=}')
                # descLines = []
                # moreLines = True
                # while moreLines:
                #     line = mapTxt.readline().strip()
                #     if line != "^":
                #         descLines.append(line)
                #     else:
                #         moreLines = False
                # roomData['desc'] = " ".join(descLines)
                item = Items(**object_data)
                print(f"processed object '{object_data['name']}'")
                object_data.append(object_txt)

    print(object_data)

    if write is True:
        with open(objectJsonFilename, 'w') as mapJson:
            json.dump(mapData, mapJson,
                      default=lambda o: {k: v for k, v in o.__dict__.items() if v}, indent=4)
        print(f"wrote '{mapJsonFilename}'")


if __name__ == '__main__':
    convert('objects.txt', 'objects.json')
