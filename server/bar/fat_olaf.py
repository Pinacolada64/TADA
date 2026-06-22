import json
import logging
import pathlib
from enum import Enum, auto
from pathlib import Path
from typing import List

from bar.ally_data import AllyFlags, assign_random_statuses, AllyStatus, Ally, load_allies
from base_classes import PlayerMoneyTypes
from player import Player
from flags import PlayerFlags
from bar.main import prompt


def sell_servant(player):
    pass


def main(player: Player):
    apostrophe = "'"
    npc_name = "Fat Olaf"
    from ally_data import load_allies, assign_random_statuses
    # set up sample data:
    master_ally_list = load_allies()
    # assign some to SERVANT status:
    random_status = assign_random_statuses(master_ally_list)
    master_ally_list = random_status
    player.output(f"The slave trader {npc_name} sits behind a table, gnawing a chicken leg.")
    if not player.query_flag(PlayerFlags.EXPERT_MODE):
        player.output(['"I buy und sell servants yu can add tu your party! ',
                       'They need tu be fed und paid on a veekly basis tu remain loyal tu yu, though!"'])
        print()
        fat_olaf_menu(player)
        print()
    while True:
        command, last_command = prompt(player, "Vot kin I du ver ya?")
        if command in ['', 'l']:
            print(f'"Hokey dokey." {npc_name} watches you leave.')
            return

        if command in ["?", "h"]:
            fat_olaf_menu(player)
            continue
        if command in ["b"]:
            from ally_data import load_allies, assign_random_statuses
            # FIXME: for data population - eventually load from "allies.json" or something
            # master ally list was "loaded" and random statuses assigned above in main()
            master_ally_list = buy_servant(player, master_ally_list)
            continue
        if command in ["s"]:
            sell_servant(player)
            continue
        if command in ["m"]:
            player.output("[FIXME]: That hasn't been written yet.")
            continue
        else:
            print(f'{npc_name} looks puzzled. "Vot?"')


def buy_servant(player: "Player", allies: List["Ally"]) -> List[Ally]:
    from tada_utilities import input_number_range
    player.output("Buy servant")
    while True:
        servants = filter_allies(allies, AllyStatus.SERVANT)
        if not servants:
            player.output('Fat Olaf mutters, "Surry, ald solt ut!"')
            return servants
        logging.debug("Servants: %i" % len(servants))

        player.output(["Servants:", "",
                       f"## {'Name'.ljust(20)} {'Strength'.rjust(8)} {'Price'.rjust(5)} Special"])
        for i, servant in enumerate(servants, 1):
            name = servant.name
            strength = servant.strength
            price = servant.strength * 100
            flags = servant.flags
            elite_str = ""
            # This is the most Pythonic and reliable way to check for flags:
            has_elite_flag = any(flag.value == AllyFlags.ELITE.value for flag in flags)
            if has_elite_flag:
                # double the price:
                price *= 2
                elite_str = "[Elite!]"
            if i % 20 == 0:
                _ = input("Hit Return: ")
            player.output(f"{i:>2} {name.ljust(20, '.')} {strength:>8} {price:>5,} {elite_str}")
        apostrophe = "'"
        if not player.query_flag(PlayerFlags.EXPERT_MODE):
            # TODO: make this a function or @property or something, don't keep repeating yourself:
            return_key = player.client_settings.return_key.name
            player.output(f"[{return_key}] = Done")
        num = input_number_range(player, prompt_msg="Buy vich vun?",
                                 out_of_bounds_msg=f'"Whoa, dun{apostrophe}t hav that many!"', min_value=1,
                                 max_value=len(servants))
        if num == '':
            player.output(f'Fat Olaf dismisses you with a wave. "Hokay, vine. See yu later!"')
            return servants  # callee expects it, even if unchanged
        else:
            chosen_servant = servants[num - 1]
            price = chosen_servant.strength * 100 * (2 if AllyFlags.ELITE in chosen_servant.flags else 1)
            can_afford = player.subtract_silver(PlayerMoneyTypes.IN_HAND, price)
            if can_afford:
                player.output(f"You bought {chosen_servant.name}.")
                logging.debug("servants before: %i" % len(servants))
                # update servant's status:
                chosen_servant.status = AllyStatus.IN_PARTY
                logging.debug("%s servant status: %s" % (chosen_servant.name, chosen_servant.status))
                # update servant in ally list:
                updated_servants = servants
                for i, servant in enumerate(updated_servants):
                    if servant == chosen_servant:
                        updated_servants[i] = chosen_servant
                        logging.debug("servant %i %s status updated" % (i, chosen_servant.name))
                ok, msg = player.party.add_member(player, chosen_servant)
                if msg:
                    player.output(msg)
                if ok:
                    logging.debug("servants after: %i" % len(servants))
            else:
                # can't afford:
                player.output("Some snarky remark")


def filter_allies(ally_list: List[Ally], filter_by_status: AllyStatus) -> List[Ally]:
    """Filters a list of allies by a specific status."""
    filtered_list = [ally for ally in ally_list if ally.status.name == filter_by_status.name]
    logging.debug(f"Found {len(filtered_list)} allies with status '{filter_by_status.name}'.")
    return filtered_list

def fat_olaf_menu(character: Player) -> None:
    return_key = character.client_settings.return_key.name
    character.output([f"[B]uy, [S]ell, or [M]aintain a servant; "
                      f"[?] / [H]: Help; "
                      f"[L] / [{return_key}]: Leave"])


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Logging is running")

    player = Player()
    player.client_settings.screen_columns = 80
    player.add_silver(PlayerMoneyTypes.IN_HAND, 20_000)
    main(player)
