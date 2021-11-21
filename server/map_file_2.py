#!/bin/env python3

# + encode map data as JSON.  why:
#   + don't need to write own parser,
#   + flexible for adding/changing fields (including optional fields)
# + use 'dataclass' for Room.  why:
#   + convenient for class with many fields mostly stored as data
# + use 'textwrap' for formatting multiline text.  why:
#   + can store text without all the format

import json
import textwrap
from dataclasses import dataclass, field

@dataclass
class Room(object):
    number: int
    name: str
    desc: str
    exits: list = field(default_factory=lambda: []) # {n e s w rc rt}
    monster: int = 0
    item: int = 0
    weapon: int = 0
    food: int = 0
    alignment: str = "neutral"

    def __str__(self):
        return f'#{self.number} {self.name}\n' \
               f'{self.desc}\n{self.exits}'

class Map(object):
    def __init__(self):
        """dict Room{name: str, alignment: str, items: list, desc: str}"""
        self.rooms = {}

    def read_map(self, filename: str):
        """
        Data format on C64:
        * Room number        (rm)
        * Location name      (lo$)
        * items: monster, item, weapon, food
        * exits: north, east, south, west,
          RC (room command: 1=move up,
                            2=move down),
          RT (Room exit transports you to:
                 room #, or 0=Shoppe)
        https://github.com/Pinacolada64/TADA-old/blob/master/text/s_t_level-1-data.txt
        """

        with open(filename) as jsonF:
            map_data = json.load(jsonF)
        for room_data in map_data['rooms']:
            room = Room(**room_data)
            self.rooms[room.number] = room

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    # load map
    game_map = Map()
    game_map.read_map("map_data.json")
    # print rooms
    wrapper = textwrap.TextWrapper(width=40)
    for number, room in game_map.rooms.items():
        print(f"#{number} - {room.name}")
        print(wrapper.fill(text=room.desc))
        print(room.exits)

