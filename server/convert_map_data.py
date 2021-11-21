#!/bin/env python3

import json
from dataclasses import dataclass

@dataclass
class Room(object):
    number: int
    name: str
    exits: list     # {n e s w rc rt}
    desc: str
    monster: int = 0
    item: int = 0
    weapon: int = 0
    food: int = 0
    #alignment: str = "neutral"

    def __str__(self):
        return f'#{self.number} {self.name}\n' \
               f'{self.desc}\n{self.exits}'

def convert(mapTxtFilename, mapJsonFilename):
    mapData = {'rooms': []}
    with open(mapTxtFilename) as mapTxt:
        moreRooms = True
        while moreRooms:
            roomData = {}
            line = mapTxt.readline().strip()
            if line == '':  # end of file
                moreRooms = False
                break
            roomData['number'] = int(line)
            roomData['name'] = mapTxt.readline().strip()
            for k, v in zip(['monster', 'item', 'weapon', 'food'],
                    mapTxt.readline().strip().split(',')):
                if v != "0":  roomData[k] = int(v)
            roomData['exits'] = {k: int(v) for k, v in 
                    zip(['n', 'e', 's', 'w', 'rc', 'rt'],
                            mapTxt.readline().strip().split(','))
                    if v != "0"}
            descLines = []
            moreLines = True
            while moreLines:
                line = mapTxt.readline().strip()
                if line != "^":  descLines.append(line)
                else:  moreLines = False
            roomData['desc'] = " ".join(descLines)
            room = Room(**roomData)
            print(f"processed room '{room.name}'")
            mapData['rooms'].append(room)
    with open(mapJsonFilename, 'w') as mapJson:
        json.dump(mapData, mapJson,
                default=lambda o: {k: v for k, v in o.__dict__.items() if v}, indent=4)
    print(f"wrote '{mapJsonFilename}'")

if __name__ == '__main__':
    convert('map_data.txt', 'map_data.json')


