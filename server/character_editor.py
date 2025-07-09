import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from sys import flags
from typing import List, Optional, Callable, NamedTuple

from base_classes import WeaponClass
from new_player_2 import Player


# Assuming these are defined in other files as per your imports
# from flags import PlayerFlags
# from characters import PlayerStat, Alignment
# from player import Player

# --- Mock Objects for Demonstration ---
class PlayerFlags(Enum):
    FLAG_1 = "Some Flag 1"
    FLAG_2 = "Another Flag"


class PlayerStat(Enum):
    CHA = "Charisma"
    CON = "Constitution"
    DEX = "Dexterity"
    INT = "Intelligence"
    STR = "Strength"
    WIS = "Wisdom"


class Alignment(Enum):
    LAWFUL_GOOD = "Lawful Good"
    GOOD = "Good"
    NEUTRAL = "Neutral"
    EVIL = "Evil"
    CHAOTIC_EVIL = "Chaotic Evil"


class Armor(object):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.defense = kwargs.get('defense')
        self.weight = kwargs.get('weight', 0)
        self.armor_class = kwargs.get('armor_class', 0)
        self.readied = kwargs.get('readied', False)
        logging.info("Armor '%s' created: defense=%i, weight=%i, readied=%s" % (self.name, self.defense, self.weight,
                                                                                self.readied))


class Shield(Armor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging.info("Shield '%s' created." % self.name)


class BaseItem(object):
    pass


class Weapon(BaseItem):
    def __init__(self, **kwargs):
        super().__init__()
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
        owner: Optional[Player]

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


# --- End Mock Objects ---

@dataclass
class Ally:
    """Base class for ally"""
    name: str
    inventory: field(default_factory=list)

    def __post_init__(self):
        logging.info("Ally '%s' created." % self.name)


class Horse(Ally):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __post_init__(self):
        logging.info("Horse '%s' created." % self.name)


"""@dataclass
class Player:
    name: str
    natural_alignment: Alignment = Alignment.NEUTRAL
    current_alignment: Alignment = Alignment.NEUTRAL
    allies: list[Ally | Horse] = field(default_factory=list)
    stats: dict = field(default_factory=lambda: {
        PlayerStat.STRENGTH: 10,
        PlayerStat.DEXTERITY: 12,
        PlayerStat.INTELLIGENCE: 14
    })
    flags: dict = field(default_factory=lambda: {
        PlayerFlags.FLAG_1: True,
        PlayerFlags.FLAG_2: False
    })

    def __post_init__(self):
        logging.info("Player '%s' created." % self.name)

    def add_ally(self, ally: Ally):
        if ally in self.allies:
            logging.error("%s already in allies list!" % ally.name)
        else:
            self.allies.append(ally)
            logging.info("%s added to allies list!" % ally.name)

    def get_stat(self, stat: PlayerStat) -> int:
        return self.stats.get(stat, 0)

    def show_flag_line_item(self, flag: PlayerFlags, leading_num=None):
         return f"{flag.value}: {self.flags.get(flag, False)}"

    def show_flag(self, flag: PlayerFlags) -> str:
        return flag.value
"""


def line_item(item_name: str, item_value: str | int, width: int = 30):
    return f"{item_name:.<{width}}: {item_value}"


@dataclass
class Menu:
    """Base class for menu systems with shared behavior."""
    title: str
    player: Optional[Player] = None
    menu_items: list = field(default_factory=list)
    columns: int = 1

    def display(self) -> None:
        """Displays the menu title and its menu items."""
        print(f"\n{self.title}")
        print("=" * len(self.title))
        """
        Don't tab over if no shortcuts in menu items:
        e.g.,
        1. No shortcut key
        2. No shortcut key
        
        vs.
        1. [i]  Item with shortcut
        2.      Item without shortcut
        """
        # Check if any item in the menu has a shortcut defined.
        has_any_shortcut = any(item.shortcuts for item in self.menu_items)

        for i, item in enumerate(self.menu_items, 1):
            # Join shortcuts for display, e.g., "[1I, I1]"
            shortcut_str = f"[{','.join(item.shortcuts)}]" if item.shortcuts else ""

            # Use the provided line_item for dot leader formatting
            if item.dot_leader_handler and self.player:
                # The handler now returns the value, line_item does the formatting
                value = item.dot_leader_handler(self.player)
                print(f"{i: >2}. {shortcut_str:<8} {line_item(item.text, value)}")
            else:
                print(f"{i: >2}. {shortcut_str:<8} {item.text}")

    def get_choice(self):
        """Gets and validates user input against the numeric input range, plus (possibly multiple) shortcut(s).

        :return: None | MenuItem
        """
        num_items = len(self.menu_items)
        if any(item.shortcuts in item for item in self.menu_items):
            print("You may use shortcuts listed in [square brackets].")
        prompt = f"Enter your choice [1-{num_items}]: "
        while True:
            choice_string = input(prompt).strip().lower()
            if not choice_string:
                return None  # Go back
            # --- FIX FOR NUMERIC CHOICE ---
            if choice_string.isnumeric():
                choice_num = int(choice_string)
                # Check if number is within the valid range of displayed options (1 to N)
                if 1 <= choice_num <= len(self.menu_items):
                    # Return the existing MenuItem from the list using the correct 0-based index
                    return self.menu_items[choice_num - 1]

            for item in self.menu_items:
                # Check if the user's input is in the item's shortcut list
                if choice_string in [sc.lower() for sc in item.shortcuts]:
                    return item
            print("Invalid choice, please try again.")


class MenuItem(NamedTuple):
    text: str
    action: Optional[Callable] = None
    submenu: Optional[Menu] = None
    shortcuts: Optional[List[str]] = None
    dot_leader_handler: Optional[Callable] = None


@dataclass
class AlignmentMenu(Menu):
    title: str = "Alignment Options"

    def __post_init__(self):
        self.menu_items = [
            MenuItem("Natural Alignment", self.edit_natural_alignment, shortcuts=['n'],
                     dot_leader_handler=lambda p: p.natural_alignment.value),
            MenuItem("Current Alignment", self.edit_current_alignment, shortcuts=['c'],
                     dot_leader_handler=lambda p: p.current_alignment.value),
        ]

    def edit_natural_alignment(self, player: Player):
        print(f"\nNatural Alignment is dependent on character class.")
        print(f"{player.name}'s natural alignment (fixed) is {player.natural_alignment.value}.")
        # input("\nPress Enter to continue...")

    def edit_current_alignment(self, player: Player):
        print(f"\nCurrent Alignment is {player.current_alignment.value.title()}.")
        alignments = list(Alignment)
        print("Available alignments:")
        for i, alignment in enumerate(alignments, 1):
            print(f"{i}: {alignment.value.title()}")

        try:
            choice = int(input("Enter your choice: ").strip()) - 1
            if 0 <= choice < len(alignments):
                player.current_alignment = alignments[choice]
                print(f"Current Alignment set to {player.current_alignment.value}.")
            else:
                print("Invalid alignment selected.")
        except (ValueError, IndexError):
            print("Invalid input.")
        # input("\nPress Enter to continue...")


def get_allies(player: Player) -> list:
    """Return a list of 3 tuples("name", "display_name"): the player, the allies, and the horse"""
    characters = [(player.name, "Main Character"),
                  [(ally.name, f"Ally {i}") for i, ally in enumerate(player.allies, 1)],
                  [(player.horse.name, "Horse")]]
    return characters


@dataclass
class ArmorShieldMenu(Menu):
    # Show READYed weapon, weapons in PC / Allies inventory
    # READY a weapon before ye sleep, if ye can...
    # TODO: ensure that multiple players cannot have the same item at once?
    """
    Proposed output:
    * Both menu shortcuts should be usable; confusion (and individual preference)
      between "is it I1 or 1I?" is possible, and frustrating.

       <Main Character: Rulan>
    1. [1I, I1] In Inventory:........: BANDED ARMOR
                                       CLOTH ARMOR
                                       SMALL SHIELD
    2. [1R, R1] READYed..............: BANDED ARMOR
       <Ally 1: SPOCK>
    3. [2I, I2] In Inventory.........: POWER ARMOR
    4. [2R, R2] READYed..............: None
       <Horse: Strawberry>
    5. [3I, I3] In Inventory.........: HORSE ARMOR (BARDING?)

    """
    title: str = "Armor & Shields"

    def __post_init__(self):
        """Builds the menu by iterating through the player, allies, and horse."""
        self.menu_items = []
        if not self.player:
            return None

        # Get a list of allies the player has:
        allies = get_allies(self.player)

        menu_items = []
        item_index = 1

        for owner_name, display_name in allies:
            # 1. Add "In Inventory" menu item for the character
            menu_items.append(MenuItem(
                text=f"<{display_name}: {owner_name}> In Inventory",
                shortcuts=[f"{item_index}I", f"I{item_index}"],
                dot_leader_handler=self._get_inventory_handler(owner_name)
            ))

            # 2. Add "READYed" menu item for the character
            menu_items.append(MenuItem(
                text=f"<{display_name}: {owner_name}> READYed",
                shortcuts=[f"{item_index}R", f"R{item_index}"],
                dot_leader_handler=self._get_readied_handler(owner_name)
            ))
            item_index += 1

        self.menu_items = menu_items

    def _get_inventory_handler(self, owner_name: str) -> Callable:
        """Returns a function that gets all armor for a given owner."""

        def handler(player: Player) -> str:
            items = [armor.name for armor in armory_list if armor.owner == owner_name]
            return "\n".join(items) if items else "None"

        return handler

    def _get_readied_handler(self, owner_name: str) -> Callable:
        """Returns a function that gets only readied armor for a given owner."""

        def handler(player: Player) -> str:
            items = [armor.name for armor in player.armor if armor.owner == owner_name and armor.readied]
            return "\n".join(items) if items else "None"

        return handler


@dataclass
class AttributeMenu(Menu):
    title: str = "Attributes"

    def __post_init__(self):
        self.menu_items = [
            MenuItem(stat.value, dot_leader_handler=lambda p, s=stat: p.get_stat(s)) for stat in PlayerStat
        ]


@dataclass
class FlagsCountersMenu(Menu):
    title: str = "Flags & Counters"

    def __post_init__(self, p: Player):
        self.menu_items = [
            MenuItem(
                text=flag.value,
                dot_leader_handler=lambda p, f=flag: p.query_flag()
            ) for flag in PlayerFlags
        ]


@dataclass
class HitPointsMenu(Menu):
    title: str = "Hit Points"

    def __post_init__(self, player: Player):
        logging.info("In %s" % __class__.__name__)


class CharacterNamesMenu(Menu):
    title: str = "Character Names"

    def __post_init__(self, player: Player):
        menu_items = []


class CombinationMenu(Menu):
    title: str = "Combinations"

    def __post_init__(self, player: Player):
        logging.info("In %s" % __class__.__name__)


class MapInfoMenu(Menu):
    title: str = "Map Information"

    def __post_init__(self, player: Player):
        logging.info("In %s" % __class__.__name__)


class MoneyMenu(Menu):
    title: str = "Money"

    def __post_init__(self, player: Player):
        logging.info("In %s" % __class__.__name__)


class StatisticsMenu(Menu):
    title: str = "Statistics"

    def __post_init__(self, player: Player):
        logging.info("In %s" % __class__.__name__)


class WeaponsMenu(Menu):
    title: str = "Weapons"

    def __post_init__(self, player: Player):
        logging.info("In %s" % __class__.__name__)


def main(player: Player):
    """Main function to handle menu interactions."""
    """
    print" STATS FOR "q$a$(.)q$r$l$
    print" 1:*ALIGNMENT        7:*HIT POINTS
    print" 2:*ARMOR/SHIELD     8:*MAP INFORMATION
    print" 3:*ATTRIBUTES       9:*MONEY
    print" 4:*CHARACTER NAMES 10:*STATISTICS
    print" 5:*COMBINATIONS    11:*WEAPONS
    print" 6:*FLAGS/COUNTERS    (*=Sub-menu)"
    """
    main_menu_items = [
        MenuItem("Alignment", submenu=AlignmentMenu, shortcuts=['al']),
        MenuItem("Armor & Shield", submenu=ArmorShieldMenu, shortcuts=['ar']),
        MenuItem("Attributes", submenu=AttributeMenu, shortcuts=['at']),
        MenuItem("Character Names", submenu=CharacterNamesMenu, shortcuts=['al']),
        MenuItem("Combinations", submenu=CombinationMenu, shortcuts=['c']),
        MenuItem("Flags & Counters", submenu=FlagsCountersMenu, shortcuts=['f']),
        MenuItem("Hit Points", submenu=HitPointsMenu, shortcuts=['h']),
        MenuItem("Map Information", submenu=MapInfoMenu, shortcuts=['mi']),
        MenuItem("Money", submenu=MoneyMenu, shortcuts=['mo']),
        MenuItem("Statistics", submenu=StatisticsMenu, shortcuts=['s']),
        MenuItem("Weapons", submenu=WeaponsMenu, shortcuts=['w']),
        MenuItem("Quit", action=lambda p: exit("Exiting character editor."), shortcuts=['q']),
    ]

    menu_stack: List[Menu] = [Menu(title="Main Menu", menu_items=main_menu_items, player=player)]

    while menu_stack:
        current_menu = menu_stack[-1]
        current_menu.display()
        choice = current_menu.get_choice()

        if choice is None:
            menu_stack.pop()
            continue

        if choice.submenu:
            # Instantiate the submenu and pass the player object
            submenu_instance = choice.submenu(player=current_menu.player)
            logging.info("Player '%s' passed to %s" % (current_menu.player.name, choice.submenu))
            menu_stack.append(submenu_instance)
        elif choice.action:
            choice.action(current_menu.player)
        else:
            print("This item has no action.")
            # input("\nPress Enter to continue...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)-8s | %(funcName)-20s | %(message)s')

    # Armor setup
    cloth_armor_setup = {"name": "Cloth Armor", "defense": 3, "weight": 2, "armor_class": 6}
    cloth_armor = Armor(**cloth_armor_setup)
    horse_armor = Armor(name="Barding", defense=5, weight=40, armor_class=3)
    banded_armor = Armor(name="Banded Armor", defense=10, weight=20, armor_class=5)
    small_shield = Shield(name="Small Shield", defense=5, weight=8, armor_class=5)
    power_armor = Armor(name="Power Armor", defense=50, weight=100, armor_class=1)

    phaser_setup = {"id_number": 1, "id_prefix": "W", "location": 1, "name": "Phaser",
                    "sound_effect": ("zap", "fizzle"), "stability": 4, "to_hit": 5, "price": 250,
                    "weapon_class": WeaponClass.ENERGY}
    phaser = Weapon(**phaser_setup)

    armory_list = [cloth_armor, horse_armor, banded_armor, small_shield, power_armor, phaser]

    strawberry_setup = {"name": "Strawberry", "inventory": [horse_armor], }
    strawberry = Horse(**strawberry_setup)

    spock_setup = {"name": "Spock", "inventory": [phaser], }
    spock = Ally(**spock_setup)

    rulan_setup = {"name": "Rulan", "allies": [spock, strawberry]}
    rulan = Player(**rulan_setup)
    print(rulan)  # uses __str__() property

    main(rulan)
