import logging
import glob
import json

from tada_utilities import input_string, input_yes_no
from flags import PlayerFlags
from player import Player
from base_classes import Gender, PlayerStat, PlayerMoneyTypes


def get_player_info(player: Player, stats: list | str, id_pattern="*") -> dict:
    """
    Put stats[] from file 'player-<id_pattern>.json' into returned_stats{}

    :param player: Player object
    :param id_pattern: wildcard pattern of 'player-{id_pattern}.json' ids to return, default '*'
    :param stats: list of stats to return from file(s)
    :return: returned_stats: dict of data{'stat': 'value', 'stat': 'value'}, etc.
    Always prepends {'id': <game_id>} for keeping track of files to open later
    """
    # TODO: scan through connected players first to save unnecessary disk access
    #  and pulling outdated stats from that disk file vs. live stats of connected
    #  player
    logging.info("Info requested: %s" % stats)
    # FIXME: get path from server.Player?
    # use relative path:
    path = "../run/server"
    filename_list = glob.glob(f'{path}/player-{id_pattern}.json')
    logging.debug("filename list: %s " % filename_list)
    returned_stats = None
    for index, player_filename in enumerate(filename_list):
        logging.info(f"get_player_info: Reading {player_filename}")
        with open(player_filename) as json_file:
            try:
                # returns dict object, I think
                # TODO: use Player.json_load() function instead
                player_data = json.load(json_file)
                logging.info('get_{player_info: %s' % player_data)
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
                        logging.warning('stat %s not found' % stat)
            except FileNotFoundError:
                logging.info("File '%s' not found." % path)
                continue
    if filename_list is None:
        player.output(f"There are no players matching the pattern '{id_pattern}'.")
        returned_stats = None
    logging.info(f'{returned_stats=}')
    return returned_stats


def zelda_menu(player: Player):
    return_key = player.client_settings.return_key.name
    player.output(["[S]tudy a player (1,000 silver)",
                   "[R]esurrect monsters (6,000 silver), or ",
                   f"[{return_key}] / [L] Leave"])


def main(player: Player):
    """
    Spy on player's stats
    Raise other players' dead monsters
    """
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Logging is running")

    npc_name = "Madame Zelda"
    player.output(f'{npc_name} and her cat sit in front of a crystal ball.')
    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        player.output(["","She can either show other players' statistics (which costs 1,000 silver), "
                       "or resurrect their dead monsters so they must be fought again (which costs 6,000 silver).",
                       ""])
        zelda_menu(player)
    while True:
        player.output("")
        command, last_command = input_string('"What dooooo you wiiiiiish?":',  False, player, "reminder")
        if command == "s":
            if not player.query_flag(PlayerFlags.EXPERT_MODE):
                player.output("[?] lists players.")
            # TODO: trap against null input, digits; can't use prompt() if it just returns 1st character
            look_up = input('"Study which player?": ')
            if look_up.lower() == player.name.lower():
                player.output('She looks you up and down. "I suggesssst youuuuuu uuuuuuuse a mirror!"')
                continue  # out of the loop
            if look_up == '?':
                player.output("[TODO]: List players")
                # list_players()
                continue
            else:
                if player.query_flag(PlayerFlags.DEBUG_MODE):
                    pay = True  # FIXME: temporarily short-circuit answering
                    logging.info("Debug: Setting 'pay' to True")
                else:
                    pay, _ = input_yes_no('"It willlll cossssst 1,000 silver. '
                                          'Is thaaaaaat okayyyyy?"')
                if pay:
                    if player.subtract_silver(PlayerMoneyTypes.IN_HAND, -6_000):
                        player.output(f'{npc_name} hunkers down over the ball.. "I seeeee..."')
                    try:
                        stats = ['name', 'gender', 'map_level', 'hit_points', 'experience',
                                 'shield', 'armor', 'stat']
                        temp = get_player_info(player, stats, id_pattern=look_up)
                        if temp is None:
                            logging.info(f"Can't find player {look_up}.")
                            break
                        pronoun = "She" if temp['gender'] == Gender.FEMALE else "He"
                        player.output([f"{temp['name']} is on dungeon level {temp['map_level']}. "
                                      f"{pronoun} has {temp['hit_points']} hit points.", ""])

                        # order: chr con dex egy int str wis
                        player.output(f"{pronoun} has "
                               f"charisma of {temp[PlayerStat.CHR]}, "
                               f"constitution of {temp[PlayerStat.CON]}, "
                               f"dexterity of {temp[PlayerStat.DEX]}, "
                               f"energy of {temp[PlayerStat.EGY]}, "
                               f"intelligence of {temp[PlayerStat.INT]}, "
                               f"strength of {temp[PlayerStat.STR]}, "
                               f"and wisdom of {temp[PlayerStat.WIS]}.")
                        print()
                        player.output(f"{temp['name']} has achieved {temp['experience']} experience in the land.")
                        print()
                        sh = temp['shield']
                        if sh.isnumeric():
                            shield = f'{sh}%'
                        elif sh == 'none':
                            shield = 'no'
                        ar = temp['armor']
                        if ar.isnumeric():
                            armor = f'{ar}%'
                        elif ar == 'none':
                            armor = 'no'
                        player.output(f"{pronoun} has {shield} shield, and {armor} armor.")
                        logging.debug(f"TODO: Instruments of death")
                        continue  # back to Zelda menu
                    except FileNotFoundError:
                        logging.debug(f"Can't find player '{look_up}'.")
                        break
                # pay 1000 silver?
                if pay is False:
                    player.output('"Hmph..."')
                    break

        if command == 'r':
            target = input('"Whooose monsters shall I briiiiing back to liiiiife?" ')
            # TODO: be kind, if target doesn't have any dead monsters, say so and skip this
            anonymous = ""
            while anonymous not in ["y", "n"]:
                anonymous, last_command = input_yes_no('"Dooo you wiiiiish to be unknowwwwwn?"')
            benefactor = "somebody" if anonymous is True else player.name
            message = f'Zelda casts "Monster Life" on {target}! Spell paid for by {benefactor}!'
            player.output(message)
            # TODO: battle_log(message)
            player.output([f"{npc_name} and her cat get [really] weird...",
                            "[TODO]: Resurrect player's monsters",
                            '"It iiiisss doooooone!"'])
            continue  # back to menu

        if command == '?':
            zelda_menu(player)
            continue
        if command == 'l':
            player.output(f'{npc_name} crosses her arms. "Gooo away, you bother my caaaat..."')
            break  # return to bar
        else:
            player.output(f'{npc_name} stares at you. Her cat stares too.')

if __name__ == '__main__':
    player = Player()
    main(player)
