import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from base_classes import WeaponClass
# TADA-specific imports:
from flags import PlayerFlags
from new_player_2 import Player


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


@dataclass
class BaseItem:
    """Base class for all items"""
    id_prefix: str = "I"
    id_number: int = 0
    name: str = None
    description: str = None
    location: int = 0
    owner = None  # could be a Player instance if a monster joins the party
    flags: list = field(default_factory=list)


class Item(BaseItem):
    def __init__(self, **kwargs):
        # item_id: int, name: str, description: str, owner: Optional[str],  id_prefix: str = "I"):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.id_prefix = "I"

        """
        class Item(object):
            def __init__(self, number, name, kind, price, **flags):
                logging.debug("Item.__init__: Instantiate item '%s'" % name)
                self.number = number
                self.name = name
                self.kind = kind
                self.price = price
                # this field is optional:
                if flags:
                    logging.debug("item.__init__ Flags:")
                    self.flags = flags
                    for key, value in flags.items():
                        logging.debug("item.__init__: %s %s" % (key, value))
            """

    @staticmethod
    def read_items(filename: str) -> dict | None:
        try:
            with open(filename) as json_file:
                items: dict = json.load(json_file)
                logging.debug("JSON data read")
                return items
        except FileNotFoundError:
            logging.error(">>> %s not found" % filename)
            return None

    """
    def __str__(self, player: Player):
        print(f"From {player.name}'s perspective:")
        print(f"\t{player.query_flag(PlayerFlags.DEBUG_MODE)=}, {player.query_flag(PlayerFlags.DUNGEON_MASTER)=}, {self.owner=}")
        if player and (player.has_item(self) or player.query_flag(PlayerFlags.DEBUG_MODE) or player.query_flag(PlayerFlags.DEBUG_MODE) or player == self.owner):
            return f"{self.name} [{self.prefix}#{self.item_id}]"
        else:
            return f"{self.name}"
    """


class Weapon(BaseItem):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        id_number: int
        id_prefix: str = "W"
        location: int
        name: str
        kind: Optional[str]
        sound_effect: tuple[str, str]
        stability: int
        to_hit: int
        price: int
        weapon_class: WeaponClass

    @staticmethod
    def read_weapons(filename: str) -> dict | None:
        try:
            with open(filename) as json_file:
                weapons = json.load(json_file)
                logging.debug("JSON data read")
                return weapons
        except FileNotFoundError:
            logging.error(">>> File not found: %s" % filename)
            return None


class Rations(BaseItem):
    def __init__(self, number, name, kind, price, **flags):
        self.number = number
        self.name = name
        self.kind = kind  # food, drink, cursed
        self.price = price
        # this field is optional:
        if flags is not None:
            self.flags = flags

    def __str__(self):
        # TODO: only display '[<kind> #<number>]' if Player's DEBUG or ADMIN flags are True
        if self.kind == "food":
            return f"{self.name} [Food #{self.number}]"
        elif self.kind == "drink":
            return f"{self.name} [Drink #{self.number}]"
        elif self.kind == "cursed":
            return f"{self.name} [Cursed #{self.number}]"
        else:
            # unknown kind:
            return f"{self.name} [Ration #{self.number}]"

    @staticmethod
    def read_rations(filename: str) -> dict | None:
        try:
            with open(filename) as json_file:
                rations = json.load(json_file)
                logging.debug("read_rations: JSON data read")
                return rations
        except FileNotFoundError:
            logging.error(">>> read_rations: File not found: %s" % filename)
            return None



if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    # Example usage
    ylana = Player()

    rulan = Player()
    rulan.set_flag(PlayerFlags.DEBUG_MODE)

    sword = Weapon(id_number=101, name="Sword", description="A sharp, steel sword.")
    hammer = Weapon(id_number=102, name="Hammer", description="A metal claw on a stick.")

    rulan.add_inventory_item(sword)
    ylana.add_inventory_item(hammer)

    print(rulan.look_at(sword))  # Output: "Sword [W#1]" (because Rulan owns the item AND Debug Mode is on)
    print(rulan.look_at(hammer))  # Output: "Hammer" (because Rulan does not own the item)
