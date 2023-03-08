import logging
import glob
import json

from server import Player
from tada_utilities import output, input_prompt


def get_player_info(stats: list, conn: Player, id_pattern="*") -> dict:
    """
    Put stats[] from file 'player-<id_pattern>.json' into returned_stats{}

    :param conn: Player object
    :param id_pattern: wildcard pattern of 'player-{id_pattern}.json' ids to return, default '*'
    :param stats: list of stats to return from file(s)
    :return: returned_stats: dict of data{'stat': 'value', 'stat': 'value'}, etc.
    Always prepends {'id': <game_id>} for keeping track of files to open later
    """

    # TODO: scan through connected players first to save unnecessary disk access
    #  and pulling outdated stats from that disk file vs. live stats of connected
    #  player
    logging.info(f'get_player_info: Info requested: {stats}')
    # FIXME: get path from server.Player?
    # use relative path:
    path = "./run/server"
    # absolute path: "D:/Documents/C64/TADA/server/run/server"
    filename_list = glob.glob(f'{path}/player-{id_pattern}.json')
    # print(filename_list)
    returned_stats = None
    for index, player_filename in enumerate(filename_list):
        logging.info(f"get_player_info: Reading {player_filename}")
        with open(player_filename) as json_file:
            try:
                # returns dict object
                player_data = json.load(json_file)
                logging.info(f'{player_data=}')
                """
                # Print the type of data variable
                print("Type:", type(player_data))

                # Print the data of dictionary
                print(f"  id: {player_data['id']}")
                print(f"name: {player_data['name']}")
                """
                returned_stats = {'id': player_data['id']}
                # https://datagy.io/python-attributeerror-dict-object-has-no-attribute-append/
                for stat in stats:
                    try:
                        returned_stats[stat] = player_data[stat]
                    except KeyError:
                        logging.warning(f'get_player_info: {stat=} not found')
            except FileNotFoundError:
                logging.info(f'File "{path}" not found.')
                continue
    if filename_list is None:
        output([f"There are no players matching the pattern '{id_pattern}'."], conn)
        returned_stats = None
    logging.info(f'{returned_stats=}')
    return returned_stats


def zelda_menu(conn: Player):
    output(["[S]tudy a player (1,000 silver), [R]esurrect monsters (6,000 silver), or [L]eave"],
           conn)


def main(conn: Player):
    """
    Spy on player's stats
    Raise other players' dead monsters

    conn: Player to output text to
    """
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')

    logging.info(f'zelda.main(): {conn.client=}')
    logging.info(f'zelda.main(): {conn.flag=}')
    logging.info(f'zelda.main(): {conn.name=}')

    character = "Madame Zelda"
    output([f'{character} and her cat sit in front of a crystal ball.'], conn)
    if conn.flag['expert_mode'] is False:
        output(["She can either show other players' statistics (which costs 1,000 silver), or resurrect "
               "their dead monsters so they must be fought again (which costs 6,000 silver)."],
               conn)
        print()
        zelda_menu(conn)
    while True:
        print()
        command, last_command = input_prompt('"What dooooo you wiiiiiish?":', conn)
        if command == "s":
            if conn.flag['expert_mode'] is False:
                output(["[?] lists players."], conn)
            # TODO: trap against null input, digits; can't use prompt() if it just returns 1st character
            look_up = input_prompt('"Study which player?": ', conn)
            if look_up.lower() == conn.name.lower():
                output(['She looks you up and down. "I suggesssst youuuuuu uuuuuuuse a mirror!"'], conn)
                continue  # out of the loop
            if look_up == '?':
                output(["[TODO]: List players"], conn)
                # list_players()
                continue
            else:
                pay = 'y'  # FIXME: temporarily short-circuit answering
                while pay not in ["y", "n"]:
                    pay, _ = input_prompt('"It willlll cossssst 1,000 silver. '
                                          'Is thaaaaaat okayyyyy?" [y/n]:', conn)
                if pay == 'y':
                    logging.info("TODO: check silver")
                    output([f'{character} hunkers down over the ball.. "I seeeee..."'], conn)
                    try:
                        stats = ['name', 'gender', 'map_level', 'hit_points', 'experience',
                                 'shield', 'armor', 'stat']
                        temp = get_player_info(stats, conn, id_pattern=look_up)
                        if temp is None:
                            logging.info(f"Can't find player {look_up}.")
                            break
                        pronoun = "She" if temp['gender'] == 'female' else "He"
                        output([f"{temp['name']} is on dungeon level {temp['map_level']}. "
                                f"{pronoun} has {temp['hit_points']} hit points.",
                                " ",
                                f"{pronoun} has "
                                f"charisma of {temp['stat']['chr']}, "
                                f"constitution of {temp['stat']['con']}, "
                                f"dexterity of {temp['stat']['dex']}, "
                                f"energy of {temp['stat']['egy']}, "
                                f"intelligence of {temp['stat']['int']}, "
                                f"strength of {temp['stat']['str']}, "
                                f"and wisdom of {temp['stat']['wis']}.",
                                " ",
                                f"{temp['name']} has achieved {temp['experience']} experience in the land."], conn)
                        print()
                        sh = temp['shield']
                        if str(sh).isnumeric():
                            shield = f'{sh}%'
                        elif sh == 'none':
                            shield = 'no'
                        ar = temp['armor']
                        if str(ar).isnumeric():
                            armor = f'{ar}%'
                        elif ar == 'none':
                            armor = 'no'
                        output([f"{pronoun} has {shield} shield, and {armor} armor."], conn)
                        logging.info(f"TODO: Instruments of death")
                        continue  # back to Zelda menu
                    except FileNotFoundError:
                        logging.info(f"Can't find player '{look_up}'.")
                        break
                # pay 1000 silver?
                if pay == 'n':
                    output(['"Hmph..."'], conn)
                    break

        if command == 'r':
            target = input_prompt('"Whooose monsters shall I briiiiing back to liiiiife?" ', conn)
            # TODO: be kind, if target doesn't have any dead monsters, say so and skip this
            anonymous = ""
            while anonymous not in ["y", "n"]:
                anonymous, last_command = input_prompt(['"Dooo you wiiiiish to be unknowwwwwn?" [Y/N]:'], conn)
            benefactor = f'{"somebody" if anonymous == "y" else f"{conn.name}"}'
            message = f"Zelda casts 'Monster Life' on {target}! Spell paid for by {benefactor}!"
            output([message], conn)
            # TODO: battle_log(message)
            output([f"{character} and her cat get [really] weird...",
                    "[TODO]: Resurrect player's monsters",
                    '"It iiiisss doooooone!"'], conn)
            continue  # back to menu

        if command == '?':
            zelda_menu(conn)
            continue
        if command == 'l':
            output([f'{character} crosses her arms. "Gooo away, you bother my caaaat..."'], conn)
            break  # return to bar
        else:
            output([f'{character} stares at you. Her cat stares too.'], conn)

    # TODO: could be a player editor skeleton
    """
    data = ['name', 'hit_points']
    # returns dict:
    stats = get_player_info(data, id_pattern='a')

    if stats is not None:
        # https://stackoverflow.com/questions/36244380/enumerate-for-dictionary-in-python#53865188
        for i, (key, value) in enumerate(stats.items(), start=1):
            temp = str(key).replace("_", " ").title()
            print(f"{i:2}. {str(temp).ljust(30, '.')}: {value}")
            # preferred output: " 1. Name................: Alice"
    """
