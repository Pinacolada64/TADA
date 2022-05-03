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
# from characters import Character


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
    alignment: str = "neutral"  # default unless set to another guild

    def __str__(self):
        return f'#{self.number} {self.name}\n' \
               f'{self.desc}\n{self.exits}'

    def exitsTxt(self):
        # connection/transport names, index by (connection, transport)
        # rc = 1: Up     rt != 0: Room #
        # rc = 2: Down   rt == 0: Shoppe
        extra_txts = {(1, 0): 'Up to Shoppe',
                      (2, 0): 'Down to Shoppe'}
        exit_txts = []
        for k in self.exits.keys():
            if k in compass_txts:
                exit_txts.append(compass_txts[k])
        room_connection = self.exits.get('rc', 0)
        room_transport = self.exits.get('rt', 0)
        exit_extra = extra_txts.get((room_connection, room_transport))
        if exit_extra:  # is not None:
            exit_txts.append(exit_extra)
        # example: level 1, room 20:
        if room_connection == 1 and room_transport != 0:
            exit_txts.append(f"Up to #{room_transport}" if debug else "Up")
        if room_connection == 2 and room_transport != 0:
            exit_txts.append(f"Down to #{room_transport}" if debug else "Down")
        return ", ".join(exit_txts)


class Item(object):
    def __init__(self, number, name, type, price, **flags):
        if flags:
            for key, value in flags.items():
                logging.info(f'{key=} {value=}')
        self.number = number
        self.name = name
        self.type = type
        self.price = price
        # this field may or may not be present:
        if flags is not None:
            self.flags = flags

    @staticmethod
    def read_items(filename: str):
        with open(filename) as jsonF:
            temp = json.load(jsonF)
            items = temp["items"]  # remove the dict "items"
        logging.info("*** Read item JSON data")

        # count = 0
        # 'item' becomes a copy of each dict element on each iteration of the loop:
        # for item in items:
        #     print(f'{count:3} {item["name"]}')  # this works
        #     count += 1
        # _ = input("Pause: ")
        print(f'{items[61]["name"]}')  # Adventurer's Guide

        """
        count = 0
        for item in item_list:
            count += 1
            logging.info(f'{count} {item}')

            number = item['number']
            name = item['name']
            type = item['type']
            price = item['price']
            try:
                flags = item['flags']
            except KeyError:
                flags = None
            logging.info(f'{count=} {name=} {type=} {price=} {flags=}')
            temp = Item(number, name, type, price, **flags)
            logging.info(f'After Item instantiated: {temp=}')
            item_list.append(temp)
        """
        return items


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
            # logging.info(f'{room.number=} {room.name=}')


class Monster(object):
    def __init__(self, number, status, name, size, strength, special_weapon, to_hit, **flags):
        self.number = number
        self.status = status
        self.name = name
        # this field is optional:
        if size is not None:
            self.size = size
        self.strength = strength
        # this field is optional:
        if special_weapon is not None:
            self.special_weapon = special_weapon
        self.to_hit = to_hit
        # this field is optional:
        if flags is not None:
            self.flags = flags

    @staticmethod
    def read_monsters(filename: str):
        with open(filename) as jsonF:
            monsters = json.load(jsonF)
            # items = temp["items"]  # remove the dict "items"
        logging.info("*** Read monster JSON data")

        # count = 0
        # 'item' becomes a copy of each dict element on each iteration of the loop:
        # for item in items:
        #     print(f'{count:3} {item["name"]}')  # this works
        #     count += 1
        # _ = input("Pause: ")
        # print(f'{items[61]["name"]}')  # Adventurer's Guide

        return monsters


class Weapons(object):
    def __init__(self, number, location, name, kind, sound_effect, stability, to_hit, price, weapon_class, **flags):
        self.number = number
        self.location = location
        self.name = name
        # this field is optional:
        self.kind = kind
        self.sound_effect = sound_effect
        self.stability = stability
        self.to_hit = to_hit
        self.price = price
        self.weapon_class = weapon_class
        # this field is optional:
        if flags is not None:
            self.flags = flags

    @staticmethod
    def read_weapons(filename: str):
        with open(filename) as jsonF:
            weapons = json.load(jsonF)
        logging.info("*** Read weapon JSON data")

        # count = 0
        # 'weapon' becomes a copy of each dict element on each iteration of the loop:
        # for weapon in weapons:
        #     print(f'{count:3} {weapon["name"]}')  # this works
        #     count += 1
        # _ = input("Pause: ")
        # print(f'{weapon[10]["name"]}')  # STONE KNIFE

        return weapons


@dataclass
class Rations(object):
    number: int
    name: str
    kind: str  # magical, standard, cursed
    price: int
    flags: list

    def __init__(self, number, name, kind, price, **flags):
        self.number = number
        self.name = name
        self.kind = kind
        self.price = price
        # this field is optional:
        if flags is not None:
            self.flags = flags

    @staticmethod
    def read_rations(filename: str):
        with open(filename) as jsonF:
            rations = json.load(jsonF)
        logging.info("*** Read ration JSON data")
        return rations


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    wrapper = textwrap.TextWrapper(width=80)

    # compass direction text names, used in Room.exitsTxt and main parser
    compass_txts = {'n': 'North', 'e': 'East', 's': 'South', 'w': 'West'}

    debug = True
    room_number = 1

    # load map
    game_map = Map()
    game_map.read_map("level_1.json")

    # load items
    items = Item.read_items("objects.json")

    # load monsters
    monsters = Monster.read_monsters("monsters.json")

    # load weapons
    weapons = Weapons.read_weapons("weapons.json")

    # load rations
    rations = Rations.read_rations("rations.json")

    # print rooms - this works fine
    """
    if debug:
        for number, room in game_map.rooms.items():
            print(f"#{number} {room.name}")
            print(wrapper.fill(text=room.desc))
            exits_txt = room.exitsTxt()
            if exits_txt:
                print(f"exits: {exits_txt}")
            print()
    """
    # start of ryan's code
    while True:
        # get room # that player is in
        try:
            room = game_map.rooms[room_number]
        except KeyError:
            print("exception: No such room yet (37, Bar?).")

        # FIXME: could all this be put in a room.header() __str__ method?
        # if debug is True:  # player.flag['debug'] is True:
        #     print(f'#{room_number} ', end='')

        # check for/trim room flags (currently only '->'):
        temp = room.name.rfind("|")
        room_name = room.name
        room_flags = ''
        if temp != -1:
            room_name = room.name[:temp]
            room_flags = room.name[temp + 1:]

        temp = str(room.alignment).title()
        print(f"{f'#{room_number} ' if debug else ''}{room_name} [{temp}]\n")
        print(wrapper.fill(text=room.desc))
        exits_txt = room.exitsTxt()
        if exits_txt is not None:
            print(f"Ye may travel: {exits_txt}")
            # ryan: list exit dirs and room #s
            if debug:
                for k, v in room.exits.items():
                    logging.info(f"Exit '{k}' to {v}")

        # show item in room:
        # num = 62  # zero-based numbering, so subtract one to get actual object
        # logging.info(f'item #{num} name: {items[num - 1]["name"]}')

        # is an item in current room?
        # logging.info(f'{room=}')  # raw info
        obj_list = []  # for grammatical list and .join(",") later
        item = room.item
        if item:
            obj_name = items[item - 1]["name"]
            obj_list.append(obj_name)
            print(f'You see item #{item} {obj_name}')

        food = room.food
        if food:
            food_name = rations[room.food - 1]["name"]
            # TODO: obj_list.append(food_name)
            print(f'You see food #{food} {food_name}')

        monster = room.monster
        if monster:
            m = monsters[monster - 1]
            mon_name = m["name"]
            # optional info:
            try:
                mon_size = m["size"]
            except KeyError:
                mon_size = None
            # TODO: obj_list.append(mon_name)
            print(f"You see monster #{monster}: "
                  f"{f'{mon_size} ' if mon_size is not None else ''}"
                  f"{mon_name}")

        weapon = room.weapon  # weapon number
        if weapon:
            w = weapons[weapon - 1]
            weapon_name = w["name"]
            # TODO: obj_list.append(weapon_name)
            print(f'You see weapon #{weapon} {weapon_name}')

        # TODO: add grammatical list item (SOME MELONS, AN ORANGE)

        cmd = input("What now? ").lower()

        if cmd == "db":
            debug = not debug
            if debug:
                state = "on"
            else:
                state = "off"
            print(f"Debug is now {state}.")
            continue

        direction = cmd[0:1]
        if direction in ['n', 'e', 's', 'w']:
            # check room.exits for 'direction'
            if debug:
                logging.info(f"dir: {direction}")
            if direction in room.exits:
                try:
                    print(f"You move {compass_txts[direction]}.")
                    room_number = room.exits[direction]
                    continue
                except KeyError:
                    if debug:
                        logging.warning(f'No such room yet (#{room_number}).")')
                except ValueError:
                    print("exception: Ye cannot travel that way.")
            # case for moving east from room #89 (TELEPORT ROOM):
            if room_flags == "->" and direction == "e":
                # TODO: flag should probably have room number with it; e.g., "->90"
                # TODO: special routines needed?
                print("You walk up to the wall and touch it... and...")
                room_number = 90
                continue
            else:
                print("Ye cannot travel that way.")
                continue
        rc = room.exits.get('rc')
        rt = room.exits.get('rt')
        if direction == "u":
            if rc == 1:
                print(f"You move Up{f' to #{rt}' if debug else ''}.")
                room_number = rt
            else:
                print("Ye cannot go that way.")
        if direction == "d":
            if rc == 2:
                print(f"You move Down{f' to #{rt}' if debug else ''}.")
                room_number = rt
            else:
                print("Ye cannot go that way.")

        if cmd == "q":
            print("Quitting.")
            break

        if cmd[:1] == "#":
            temp = cmd[1:]
            if temp.isdigit() is False:
                print("(Room number required after '#'.)")
                continue
            val = int(temp)
            try:
                room = game_map.rooms[val]
                print(f"You teleport to room #{val}, {room.name}.\n")
                room_number = val
            except KeyError:
                logging.warning(f'No such room yet (#{val}, '
                                f'max of {max(game_map.rooms)}).')
                continue
