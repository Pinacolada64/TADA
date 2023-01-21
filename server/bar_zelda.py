import logging
import glob
import json

from bar import output, input_prompt
from globals import get_client, get_flag

client = get_client()
flag = get_flag()


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
        output(f"There are no players matching the pattern '{id_pattern}'.")
        returned_stats = None
    logging.info(f'{returned_stats=}')
    return returned_stats


def zelda_menu():
    output("[S]tudy a player (1,000 silver), [R]esurrect monsters (6,000 silver), or [L]eave")


def main(client: dict, flag: dict, player_name: str):
    """
    Spy on player's stats
    Raise other players' dead monsters
    """
    import logging

    # set up logging to file - see previous section for more details
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    # Now, we can log to the root logger, or any other logger. First the root...
    logging.info('Jackdaws love my big sphinx of quartz.')

    # Now, define a couple of other loggers which might represent areas in your
    # application:

    logger1 = logging.getLogger(__name__)
    # logger2 = logging.getLogger('myapp.area2')

    logger1.debug('Quick zephyrs blow, vexing daft Jim.')
    logger1.info('How quickly daft jumping zebras vex.')
    logger1.warning('Jail zesty vixen who grabbed pay from quack.')
    logger1.error('The five boxing wizards jump quickly.')

    logger1.info("Test")
    logger1.info(f'{client=}')
    logger1.info(f'{flag=}')
    logger1.info(f'{player_name=}')

    # TODO: import server.server.Player dataclass

    character = "Madame Zelda"
    output(f'{character} and her cat sit in front of a crystal ball.')
    if flag['expert_mode'] is False:
        output("She can either show other players' statistics (which costs 1,000 silver), or resurrect "
               "their dead monsters so they must be fought again (which costs 6,000 silver).")
        print()
        zelda_menu()
    while True:
        print()
        command, last_command = input_prompt('"What dooooo you wiiiiiish?":')
        if command == "s":
            if flag['expert_mode'] is False:
                output("[?] lists players.")
            # TODO: trap against null input, digits; can't use prompt() if it just returns 1st character
            look_up = input('"Study which player?": ')
            if look_up.lower() == player_name.lower():
                output('She looks you up and down. "I suggesssst youuuuuu uuuuuuuse a mirror!"')
                continue  # out of the loop
            if look_up == '?':
                output("[TODO]: List players")
                # list_players()
                continue
            else:
                pay = 'y'  # FIXME: temporarily short-circuit answering
                while pay not in ["y", "n"]:
                    pay, _ = input_prompt('"It willlll cossssst 1,000 silver. '
                                          'Is thaaaaaat okayyyyy?" [y/n]:')
                if pay == 'y':
                    logging.info("TODO: check silver")
                    output(f'{character} hunkers down over the ball.. "I seeeee..."')
                    try:
                        stats = ['name', 'gender', 'map_level', 'hit_points', 'experience',
                                 'shield', 'armor', 'stat']
                        temp = get_player_info(stats, id_pattern=look_up)
                        if temp is None:
                            logging.info(f"Can't find player {look_up}.")
                            break
                        pronoun = "She" if temp['gender'] == 'female' else "He"
                        output(f"{temp['name']} is on dungeon level {temp['map_level']}. "
                               f"{pronoun} has {temp['hit_points']} hit points.")
                        print()
                        # order: chr con dex egy int str wis
                        output(f"{pronoun} has "
                               f"charisma of {temp['stat']['chr']}, "
                               f"constitution of {temp['stat']['con']}, "
                               f"dexterity of {temp['stat']['dex']}, "
                               f"energy of {temp['stat']['egy']}, "
                               f"intelligence of {temp['stat']['int']}, "
                               f"strength of {temp['stat']['str']}, "
                               f"and wisdom of {temp['stat']['wis']}.")
                        print()
                        output(f"{temp['name']} has achieved {temp['experience']} experience in the land.")
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
                        output(f"{pronoun} has {shield} shield, and {armor} armor.")
                        logging.info(f"TODO: Instruments of death")
                        continue  # back to Zelda menu
                    except FileNotFoundError:
                        logging.info(f"Can't find player '{look_up}'.")
                        break
                # pay 1000 silver?
                if pay == 'n':
                    output('"Hmph..."')
                    break

        if command == 'r':
            target = input('"Whooose monsters shall I briiiiing back to liiiiife?" ')
            # TODO: be kind, if target doesn't have any dead monsters, say so and skip this
            anonymous = ""
            while anonymous not in ["y", "n"]:
                anonymous, last_command = input_prompt('"Dooo you wiiiiish to be unknowwwwwn?" [Y/N]:')
            benefactor = f'{"somebody" if anonymous == "y" else f"{player_name}"}'
            message = f"""Zelda casts 'Monster Life' on {target}! Spell paid for by {benefactor}!"""
            output(message)
            # TODO: battle_log(message)
            output(f"{character} and her cat get [really] weird...")
            output("[TODO]: Resurrect player's monsters")
            output('"It iiiisss doooooone!"')
            continue  # back to menu

        if command == '?':
            zelda_menu()
            continue
        if command == 'l':
            output(f'{character} crosses her arms. "Gooo away, you bother my caaaat..."')
            break  # return to bar
        else:
            output(f'{character} stares at you. Her cat stares too.')

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