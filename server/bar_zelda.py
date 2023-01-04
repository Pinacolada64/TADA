import logging
import glob
import json

from bar import output, prompt


def get_player_info(stats: list, id_pattern="*") -> dict:
    """
    Put stats[] from file 'player-<id_pattern>.json' into returned_stats{}

    :param id_pattern: wildcard pattern of 'player-{id_pattern}.json' ids to return, default '*'
    :param stats: list of stats to return from file(s)
    :return: returned_stats: dict of data{'stat': 'value', 'stat': 'value'}, etc.
    Always prepends {'id': <game_id>} for keeping track of files to open later
    """

    # TODO: scan through connected players first to save unnecessary disk access
    #  and pulling outdated stats from that disk file vs. live stats of connected
    #  player
    print(f'get_player_info: Info requested: {stats}')
    # FIXME: get path from server.Player
    path = "D:/Documents/C64/TADA/server/run/server"
    filename_list = glob.glob(f'{path}/player-{id_pattern}.json')
    # print(filename_list)
    for index, player_filename in enumerate(filename_list):
        logging.info(f"get_player_info: Reading {player_filename}")
        with open(player_filename) as json_file:
            # returns dict object
            player_data = json.load(json_file)
            """
            # Print the type of data variable
            print("Type:", type(player_data))
            
            # Print the data of dictionary
            print(f"  id: {player_data['id']}")
            print(f"name: {player_data['name']}")
            """
            returned_stats = {'id': player_data['id']}
            # https://datagy.io/python-attributeerror-dict-object-has-no-attribute-append/
            logging.info(f'get_player_info: {returned_stats=}')
            for stat in stats:
                try:
                    returned_stats[stat] = player_data[stat]
                    # name = data['name']
                    # append dict item to list: [{'name': 'Alice'}, {'name': 'Mr. X'}]
                    # stats_requested.append(dict([v, data[v]]))
                    logging.info(f'{returned_stats=}')
                except KeyError:
                    print(f'get_player_info: {stat=} not found')
    if filename_list is None:
        print(f"There are no players matching the pattern '{id_pattern}'.")
        returned_stats = None
    return returned_stats


def zelda_menu():
    output("[S]tudy a player, [R]esurrect monsters, or [L]eave")


def main(client: dict, flag: dict, player_name: str):
    """
    Spy on player's stats
    Raise other players' dead monsters
    """
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    print(f'zelda.main(): {client=}')
    print(f'zelda.main(): {flag=}')
    print(f'zelda.main(): {player_name=}')

    # TODO: import server.server.Player dataclass

    character = "Madame Zelda"
    output(f'{character} and her cat sit in front of a crystal ball.')
    if flag['expert_mode'] is False:
        output("She can either show other players' statistics, or resurrect "
               "their dead monsters so they must be fought again.")
        print()
        zelda_menu()
        print()
    while True:
        command, last_command = prompt('"What dooooo you wiiiiiish?":')
        if command == "s":
            if flag['expert_mode'] is False:
                output("'?' lists players.")
            # TODO: trap against null input, digits; can't use prompt() if it just returns 1st character
            look_up = input('"Study which player?": ')
            if look_up.lower() == player_name.lower():
                output('"I suggesssst you uuuuuuuse a mirror!"')
            if look_up == '?':
                # list_players_in_dir()
                continue
            else:
                while True:
                    command, last_command = prompt('"It willlll cossssst 1,000 silver. "'
                                                   '"Is thaaaaaat okayyyyy?":')
                    if command == 'y':
                        output("[TODO:] check silver")
                        output('She hunkers down over the ball.. "I seeeee..."')
                        try:
                            # TODO: store gender
                            stats = ['name', 'map_level', 'hit_points', 'experience_level',
                                     'shield', 'armor']
                            temp = get_player_info(stats, id_pattern=look_up)
                            _ = input("Pause: ")
                            output(f"{temp['name']} is on dungeon level {temp['map_level']}. "
                                   f"They have {temp['hit_points']} hit points, a strength of <str>, "
                                   f"an intelligence of <int>, dexterity of <dex>, energy of <egy>, "
                                   f"constitution of <con>, wisdom of <wis>."
                                   f" "
                                   f"{temp['name']} has achieved {temp['experience_level']} in the land. ",
                                   f" "
                                   f"They have {temp['shield']}% shield, and {temp['armor']}% armor."
                                   f" "
                                   f"[TODO:] Instruments of death")

                        except FileNotFoundError:
                            logging.info(f"Can't find player '{look_up}'.")

                    else:
                        output('"Hmph..."')
                        break
                    continue
        if command == 'r':
            output("[TODO]: Resurrect player's monsters")
            target = input('"Whooose monsters shall I briiiiing back to liiiiife?" ')
            while True:
                command, last_command = prompt('"Dooo you wiiiiish to be unknowwwwwn?" [Y/N]:')
                output(f"{character} and her cat get [really] weird...")
                benefactor = f'{"somebody" if command == "y" else f"{player_name}"}'
                message = f"""Zelda casts 'Monster Life' on {target}! Spell paid for by {benefactor}!"""
                output(message)
                # TODO: battle_log(message)
                output('"It iiiisss doooooone!"')
                break
            continue  # back to menu
        if command == '?':
            zelda_menu()
            continue
        if command == 'l':
            output('"Gooo away, you bother my caaaat..."')
            break  # out of loop
        else:
            output(f'{character} stares at you. Her cat stares too.')

    data = ['name', 'hit_points']
    # returns dict:
    stats = get_player_info(data, id_pattern='a')

# https://stackoverflow.com/questions/36244380/enumerate-for-dictionary-in-python#53865188
    for i, (key, value) in enumerate(stats.items(), start=1):
        temp = str(key).replace("_", " ").title()
        print(f"{i:2}. {str(temp).ljust(30, '.')}: {value}")
        # preferred output: " 1. Name................: Alice"


if __name__ == '__main__':
    def __init__(self, client, flag, player_name):
        """
        FIXME: Again, just trying to figure out a method of passing
         client['cols'] from bar.py, and failing
        """
        # imported from bar.py:
        self.client = client
        self.flag = flag
        self.player_name = player_name
        main(client=client, flag=flag, player_name=player_name)
