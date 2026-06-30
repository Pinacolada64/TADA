import json
import logging
from dataclasses import dataclass, field
from enum import auto
from typing import Optional, TYPE_CHECKING, Any, Dict, Tuple

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

# TADA-specific imports:
if TYPE_CHECKING:
    from base_classes import WeaponClass
    from player import Player

from flags import PlayerFlags


class ItemCategory(StrEnum):
    ITEM      = "Item"
    FOOD      = "Food"
    DRINK     = "Drink"
    WEAPON    = "Weapon"
    SPELL     = "Spell"
    ARMOR     = "Armor"
    CONTAINER = "Container"


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
    # Accept either list or dict for flags (some data files use a dict)
    flags: Any = field(default_factory=list)
    category: Optional[ItemCategory] = None


class Item(BaseItem):
    def __init__(self, **kwargs):
        # item_id: int, name: str, description: str, owner: Optional[str],  id_prefix: str = "I"):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.id_prefix = "I"
        if not hasattr(self, 'category'):
            self.category = ItemCategory.ITEM
        # capacity > 0 makes this a container (bag of holding, etc.)
        if not hasattr(self, 'capacity'):
            self.capacity: int = 0
        # BaseItem dataclass __repr__ always reads self.flags; guarantee it exists.
        if not hasattr(self, 'flags'):
            self.flags = []

    @staticmethod
    def read(filename: str) -> dict | None:
        try:
            with open(filename) as json_file:
                data = json.load(json_file)
                logging.info("Read JSON data '%s'" % filename)
                # objects.json historically has a top-level dict with key 'items': [...]
                if isinstance(data, dict) and 'items' in data:
                    return data['items']
                # otherwise return the top-level structure (could already be a list)
                return data
        except FileNotFoundError:
            logging.error(">>> %s not found" % filename)
            return None

    """
    # TODO: re-implement this method in a way that works with the current Player class
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
        # Lazy import to avoid circular dependency
        from base_classes import WeaponClass
        # BaseItem is a dataclass — pass only the fields it declares.
        _base_fields = {'id_prefix', 'id_number', 'name', 'description', 'location', 'flags', 'category'}
        super().__init__(**{k: v for k, v in kwargs.items() if k in _base_fields})
        self.id_number: int = kwargs.get('id_number', 0)
        self.id_prefix: str = "W"
        self.location: int = kwargs.get('location', 0)
        self.name: str = kwargs.get('name', '')
        self.category = kwargs.get('category', ItemCategory.WEAPON)
        self.kind: Optional[str] = kwargs.get('kind')
        self.sound_effect: Tuple[str, str] = kwargs.get('sound_effect', ('', ''))
        self.stability: int = kwargs.get('stability', 0)
        self.to_hit: int = kwargs.get('to_hit', 0)
        self.price: int = kwargs.get('price', 0)
        self.weapon_class: WeaponClass = kwargs.get('weapon_class')

    @staticmethod
    def read_weapons(filename: str) -> Optional[Dict[str, Any]]:
        try:
            with open(filename) as json_file:
                weapons = json.load(json_file)
                logging.info("Read JSON data '%s'" % filename)
                return weapons
        except FileNotFoundError:
            logging.error(">>> File not found: '%s'" % filename)
            return None


class Rations(BaseItem):
    def __init__(self, number, name, kind, price, **flags):
        self.number = number
        self.id_number = number  # alias so inventory.remove() can match by id
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
            return f"{self.name} [Unknown #{self.number}]"

    @staticmethod
    def read_rations(filename: str) -> Optional[Dict[str, Any]]:
        try:
            with open(filename) as json_file:
                rations = json.load(json_file)
                logging.info("Read JSON data '%s'" % filename)
                return rations
        except FileNotFoundError:
            logging.error(">>> File not found: %s" % filename)
            return None


@dataclass
class Spell(BaseItem):
    """A spell that can be cast, with a finite number of charges.

    Fields ported from SPUR.MISC3.S spell records (q$, q2$, q3, q4):
      cast_chance     — probability of success, 0-100 (q3 * 10 in SPUR display)
      effect_type     — single letter: S=Str W=Wis D=Dex C=Con E=Egy I=Int
                        T=Transfer P=Player-HP M=Monster L=LevelDown U=LevelUp
                        R=Shop(teleport) G=SPUR(teleport) A=Aura
      effect_magnitude — numeric modifier applied on success (q2$ second char)
      aux_param        — extra parameter used by aura/time spells (q4)
    """
    charges: int = 0
    max_charges: int = 0
    cast_chance: int = 0       # 0-100 percent
    effect_type: str = ''
    effect_magnitude: int = 0
    aux_param: int = 0

    def __post_init__(self):
        self.id_prefix = "S"
        self.category  = ItemCategory.SPELL

    def use(self) -> bool:
        """Consume one charge. Returns False if already depleted."""
        if self.charges <= 0:
            return False
        self.charges -= 1
        return True

    @property
    def is_depleted(self) -> bool:
        return self.charges <= 0

    def __str__(self):
        charge_pct = int(self.charges / self.max_charges * 100) if self.max_charges else 0
        return (
            f"{self.name} "
            f"[{self.charges}/{self.max_charges} charges, {charge_pct}%"
            f" | cast: {self.cast_chance}%]"
        )


if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)15s() | %(message)s')

    # from inventory import Inventory, InventoryEntry
    from player import Player

    # Example usage
    ylana = Player()

    rulan = Player()
    rulan.set_flag(PlayerFlags.DEBUG_MODE)

    sword = Weapon(id_number=101, name="Sword", description="A sharp, steel sword.")
    hammer = Weapon(id_number=102, name="Hammer", description="A metal claw on a stick.")

    rulan.inventory.add(sword)
    ylana.inventory.add(hammer)

    print(rulan.look_at(sword))  # Output: "Sword [W#1]" (because Rulan owns the item AND Debug Mode is on)
    print(rulan.look_at(hammer))  # Output: "Hammer" (because Rulan does not own the item)
