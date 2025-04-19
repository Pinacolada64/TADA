import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

# TADA-specific imports:
from flags import PlayerFlags
from characters import Player


class IDNumber:
    """Save from having to manually specify an ID#"""
    def __init__(self, value: int):
        self.value = value
        logging.debug(" init: id=%i", self.value)

    def increment(self):
        logging.debug("enter: id=%i", self.value)
        self.value += 1
        logging.debug(" exit: id=%i", self.value)
        return self.value

@dataclass
class BoobyTrap:
    room: int
    level: int
    combination: str  # letter A-I
    buried_by: str  # Player  # so we can determine if they're DIGging up their own or someone else's stuff


class Item:
    def __init__(self, item_id: int, name: str, description: str, owner: Optional[str], prefix: str = "I"):
        self.prefix = prefix
        self.item_id = item_id
        self.owner = owner  # TODO: can be a Player, but moving this after Player breaks inheritance
        self.name = name
        self.description = description

    """
    def __str__(self, player: Player):
        print(f"From {player.name}'s perspective:")
        print(f"\t{player.query_flag(PlayerFlags.DEBUG_MODE)=}, {player.query_flag(PlayerFlags.DUNGEON_MASTER)=}, {self.owner=}")
        if player and (player.has_item(self) or player.query_flag(PlayerFlags.DEBUG_MODE) or player.query_flag(PlayerFlags.DEBUG_MODE) or player == self.owner):
            return f"{self.name} [{self.prefix}#{self.item_id}]"
        else:
            return f"{self.name}"
    """

class Weapon:
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
        try:
            with open(filename) as jsonF:
                weapons = json.load(jsonF)
                logging.debug("read_weapons: JSON data read")
                return weapons
        except FileNotFoundError:
            logging.error(">>> read_weapons: File not found: %s" % filename)
            return None

class OldWeapon(Item):
    def __init__(self, item_id: int, name: str, description: str, owner: str):
        super().__init__(item_id, name, description, owner, prefix="W")



if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() - %(message)s')

    # Example usage
    id_number = IDNumber(1)

    ylana = Player()

    rulan = Player()
    rulan.set_flag(PlayerFlags.DEBUG_MODE)

    sword = Weapon(101, "Sword", "A sharp, steel sword.", None)
    hammer = Weapon(102, "Hammer", "A metal claw on a stick.", None)

    print(sword.__str__(rulan))  # Output: "Sword [#1]" (because Rulan owns the item AND Debug Mode is on)
    print(hammer.__str__(rulan))  # Output: "Other Item" (because Rulan does not own the item)
