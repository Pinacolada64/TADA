# Thanks to Tanabi for all the help :)

class Room(object):
    def __init__(self, number: int, name: str,
                 monster: int, item: int, weapon: int, food: int,
                 exits: list,
                 desc: str):
        """Adds alignment of 'neutral' without having to specify for each room"""
        self.number = number
        self.name = name
        self.monster = monster
        self.alignment = "neutral"
        self.item = item
        self.weapon = weapon
        self.food = food
        self.exits = exits
        self.desc = desc

    def __str__(self):
        return f'#{self.number=} {self.name=}\n' \
               f'{self.desc}\n\n{self.exits}\n'

    """
    https://www.reddit.com/r/learnpython/comments/qo4y4b/beginner_introduction_to_classes_no_links_in_post/
    Note that a method definition that is preceded by the command, @staticmethod
    (a decorator) is really just a function that does not include the "self"
    reference to the calling instance. It is included in a class definition
    for convenience and can be called by reference to the class or the instance.    
    """

    @staticmethod
    def create_room(number: int, name: str, monster: int, item: int, weapon: int, food: int, exits: list, desc: str):
        Room.number = self.number
        Room.name = self.name
        Room.monster = self.monster
        # self.db[new_room.alignment] = "neutral"
        Room.alignment = "neutral"
        return Room(number, name, alignment, monster, item, weapon, food, exits, desc)


class Map(object):
    def __init__(self):
        """dict Room{name: str, alignment: str, items: list, desc: str}"""
        self.db = {}  # dict
        logging.info("You just created a new Map object!")
        # new_room = 0

    def add_room(self, number: int, name: str, monster: int, item: int, weapon: int,
                 food: int, exits: list, desc: str):
        new_room = Room.create_room(number, name, monster, item, weapon, food, exits, desc)
        self.db[new_room.number] = new_room
        logging.info(f'# {number=} {name=}')
        logging.info(f'{monster=} {item=} {weapon=} {food=}')
        logging.info(f'{exits=}')
        logging.info(f'{desc=}')
        # TODO: until actual room alignment can be changed, this saves entering a data point:
        # exits: n e s w rc rt
        # FIXME: work on rc/rt later
        return new_room.number

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
        with open(filename, "r") as f:  # read-only
            try:
                # line 1:
                data = f.readline()
                room_number = data.rstrip('\n')
                logging.info(f'{room_number=}')

                # line 2:
                data = f.readline()
                room_name = data.strip('\n')
                logging.info(f'{room_name=}')

                # line 3:
                data = f.readline().split(",")  # creates a list
                monster = data[0]
                logging.info(f'{monster=}')
                item = data[1]
                logging.info(f'{item=}')
                weapon = data[2]
                logging.info(f'{weapon=}')
                food = data[3].rstrip('\n')
                logging.info(f'{food=}')

                # line 4:
                exits = f.readline().split(",")  # creates a list
                # exits = rstrip('\n').data
                logging.info(f'{exits=}')
                room_list = []

                # lines 5-n:
                temp = ""
                while temp != "^":  # end of description text block
                    temp = f.readline().rstrip('\n')
                    logging.info(f'{temp=}')
                    room_list.append(temp)  # append to list
                room_desc = " ".join(room_list)
                logging.info(f'{room_desc=}')

                Map.add_room(room_number, room_name, monster, item, weapon, food, exits=exits, desc=room_desc)
                _ = input("Pause: ")
            except EOFError:
                logging.info("EOF reached")
                f.close()


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    debug = True
    descriptions = True

    game_map = Map()  # instantiate new Map object

    game_map.read_map("map_data.txt")
