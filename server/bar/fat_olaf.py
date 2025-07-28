import json
import logging
import pathlib
from enum import Enum, auto
from pathlib import Path

from bar.ally_data import AllyFlags, assign_random_statuses
from player import Player
from flags import PlayerFlags
from bar.main import prompt


def sell_servant(player):
    pass


def main(character: Player):
    npc_name = "Fat Olaf"
    character.output(f"The slave trader {npc_name} sits behind a table, gnawing a chicken leg.")
    if not character.query_flag(PlayerFlags.EXPERT_MODE):
        character.output(['"I buy und sell servants yu can add tu your party! ',
                          'They need tu be fed und paid on a veekly basis tu remain loyal tu yu, though!"'])
        print()
        fat_olaf_menu(character)
        print()
    while True:
        command, last_command = prompt(character, "Vot kin I du ver ya?")
        if command in ['', 'l']:
            print(f'"Hokey dokey." {npc_name} watches you leave.')
            return

        if command in ["?", "h"]:
            fat_olaf_menu(character)
            continue
        if command in ["b"]:
            buy_servant(player)
            continue
        if command in ["s"]:
            sell_servant(player)
            continue
        if command in ["m"]:
            character.output("[FIXME]: That hasn't been written yet.")
            continue
        else:
            print(f'{npc_name} looks puzzled. "Vot?"')

def buy_servant(player: Player):
    print("Buy servant")
    servants = filter_servants()
    logging.debug("Servants: %i" % len(servants))
    if servants:
        print("Servants:")
        print(f"## {'Name'.ljust(20)} {'Strength'.rjust(8)} {'Price'.rjust(5)} Elite?")
        for i, servant in enumerate(servants, 1):
            name = servant.name
            strength = servant.strength
            price = servant.strength * 100
            flags = servant.flags
            elite_str = ''
            if flags:
                if AllyFlags.ELITE in flags:
                    price = price * 2
                    elite_str = '[Elite!]'
            if i % 20 == 0:
                _ = input("Hit Return: ")
            print(f"{i:>2} {name:.<20} {strength:>8} {price:>5,} {elite_str}")
    else:
        print("No servants are for sale today.")


def filter_servants() -> list | None:
    from ally_data import AllyStatus, load_allies, assign_random_statuses
    raw_servants = load_allies()
    servants = assign_random_statuses(raw_servants)
    logging.debug("    Raw servants list: %i" % len(servants))
    servants_only = [servant for servant in servants if servant.status == AllyStatus.SERVANT]
    if servants_only:
        logging.debug("Filtered Servant list: %i" % len(servants_only))
        return servants_only
    else:
        print("No servants")
        return None

def fat_olaf_menu(character: Player) -> None:
    return_key = character.client_settings.return_key.name
    character.output([f"[B]uy, [S]ell, or [M]aintain a servant; "
                      f"[?] or [H]: Help; "
                      f"[L] or [{return_key}]: Leave"])

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')
    logging.info("Logging is running")

    player = Player()
    main(player)
