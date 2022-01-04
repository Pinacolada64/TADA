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
import logging
from players import Player


@dataclass
class Room(object):
    number: int
    name: str
    desc: str
    exits: dict = field(default_factory=lambda: {})  # {n e s w rc rt}
    monster: int = 0
    item: int = 0
    weapon: int = 0
    food: int = 0
    alignment: str = "neutral"

    def __str__(self):
        return f'#{self.number} {self.name}\n' \
               f'{self.desc}\n{self.exits}'

    def exitsTxt(self):
        # connection/transport names, index by (connection, transport)
        extra_txts = {(1, 0): 'Up to Shoppe', (1, 1): 'Up',
                      (2, 0): 'Down to Shoppe', (2, 1): 'Down'}
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:
                exit_txts.append(compass_txts[k])
        room_connection = self.exits.get('rc', 0)
        room_transport = self.exits.get('rt', 0)
        exit_extra = extra_txts.get((room_connection, room_transport))
        if exit_extra:  # is not None:
            exit_txts.append(exit_extra)
        return ", ".join(exit_txts)


class Map(object):
    def __init__(self):
        """
        dict Room{name: str, alignment: str, monster: int, item: int, weapon: int, food: int, desc: str}
        """
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
                 <>0: room #, or 0=Shoppe)
        https://github.com/Pinacolada64/TADA/blob/master/text/s_t_level-1-data.txt
        """

        with open(filename) as jsonF:
            map_data = json.load(jsonF)
        for room_data in map_data['rooms']:
            room = Room(**room_data)
            self.rooms[room.number] = room
            logging.info(f'{room.number=}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    # compass direction text names, used in Room.exitsTxt and main parser
    compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West'}

    # create new Player
    # Rulan = Player()
    # Rulan = dict(flag['debug']: True)
    # print(Rulan)

    # load map
    game_map = Map()
    game_map.read_map("level_1.json")

    # print rooms - this works fine
    wrapper = textwrap.TextWrapper(width=80)
    for number, room in game_map.rooms.items():
        print(f"#{number} {room.name}")
        print(wrapper.fill(text=room.desc))
        exits_txt = room.exitsTxt()
        if exits_txt is not None:
            print(f"exits: {exits_txt}")
        print()

    # start of ryan's code
    player_room = 1
    logging.info("Made it past dumping JSON info")

    debug = True
    room_id = 1
    while True:
        # get room # that player is in
        try:
            room = game_map.rooms[room_id]
        except KeyError:
            print("exception: No such room yet (37, Bar?).")

        # FIXME: could all this be put in a room.header() __str__ method?
        if debug is True:  # Rulan.flag["debug"]:
            print(f'#{room.number} ', end='')
        print(f'{room.name} {room.alignment}\n')
        print(wrapper.fill(text=room.desc))
        exits_txt = room.exitsTxt()
        if exits_txt is not None:
            print(f"Ye may travel: {exits_txt}")
            # ryan: list exit dirs and room #s
            if debug:
                for k in room.exits:
                    logging.info(f'{k=}')

        # import json
        #
        # with open('./testJSON.json') as json_file:
        #     data = json.load(json_file)
        #     dataList = {item['id']: item['name'] for item in data}

        # item_here = room.items
        # if item_here:
        #    # TODO: add grammatical list item (SOME MELONS, AN ORANGE)
        #    print(f"Ye see {item_here}.")

        cmd = input("What now? ").lower()
        direction = cmd[0:1]
        if direction in ['n', 'e', 's', 'w']:
            # check room.exits for 'direction'
            logging.info("dir: n/e/s/w")
            if direction in room.exits:
                try:
                    print(f"You move {compass_txts[direction]}.")
                    try:
                        room_id = room.exits[direction]
                    except KeyError:
                        print("exception: No such room yet (37, Bar?).")
                    logging.info(f'{room_id=}')
                except ValueError:
                    print("exception: Ye cannot travel that way.")
            else:
                print("Ye cannot travel that way.")
        if cmd == "q":
            print("Quitting.")
            break
