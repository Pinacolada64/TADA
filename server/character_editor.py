import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable

# TADA imports:
from menu_system import Menu, MenuItem
from base_classes import Alignment, WeaponClass
# Assuming these are defined in other files as per your imports
from characters import PlayerStat
from flags import PlayerFlags
from player import Player
from tada_utilities import input_string


# --- Mock Objects for Demonstration ---

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
class AlignmentMenu(Menu):
    title: str = "Alignment Options"

    def __post_init__(self):
        self.menu_items = [
            MenuItem("Natural Alignment", 'n', self.edit_natural_alignment,
                     dot_leader_handler=lambda p: p.natural_alignment),
            MenuItem("Current Alignment", 'c', self.edit_current_alignment,
                     dot_leader_handler=lambda p: p.current_alignment),
        ]

    def edit_natural_alignment(self, player: Player):
        print(f"\nNatural Alignment is dependent on character class.")
        print(f"{player.name}'s natural alignment (fixed) is {player.natural_alignment.value}.")
        # input("\nPress Enter to continue...")

    def edit_current_alignment(self, player: Player):
        print(f"\nCurrent Alignment is {player.current_alignment.value.title()}.")
        alignments = list(Alignment)
        current_alignment_menu = Menu("Available alignments")
        # for i, alignment in enumerate(alignments, 1):
        #     print(f"{i}: {alignment.title()}")
        for i, a in enumerate(alignments, 1):
            # current_alignment_menu.menu_items[i] = MenuItem(a, str(i))
            current_alignment_menu.add_item(MenuItem(a, str(i)))
        try:
            choice = int(input("Enter your choice: ").strip()) - 1
            if 0 <= choice < len(alignments):
                player.current_alignment = alignments[choice]
                print(f"Current Alignment set to {player.current_alignment}.")
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


class CharacterNames(Menu):
    def show_main_char_name(self):
        return player.name

    def edit_main_char_name(self, player):
        name = input_string("Main character name", self.name, player, "reminder: player.name")
        player.name = name


class FlagsAndCounters(Menu):
    """Edit player's flags and counters"""

    def show_admin_flag(self, player: Player):
        # we just want the result from the Admin flag query string,
        # so split string into "Administrator....", ": ", "Yes/No",
        # return list index 1 (the Yes/No, On/Off, True/False result)
        return player.show_flag(PlayerFlags.ADMIN).split(": ")[1]

    def edit_admin_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.ADMIN, True)

    def show_architect_flag(self, player: Player):
        return player.show_flag(PlayerFlags.ARCHITECT).split(": ")[1]

    def edit_architect_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.ARCHITECT, True)

    def show_debug_flag(self, player: Player):
        return player.show_flag(PlayerFlags.DEBUG_MODE).split(": ")[1]

    def edit_debug_flag(self, player: Player):
        """
        Cannot enable Debug Mode without first being a Dungeon Master or
        Administrator.
        :return:
        """
        if not player.query_flag(PlayerFlags.DEBUG_MODE):  # Check if DEBUG_MODE is off
            # Check if both ADMIN and DUNGEON_MASTER are off:
            if not player.query_flag(PlayerFlags.ADMIN) or not player.query_flag(PlayerFlags.DUNGEON_MASTER):
                player.output("Debug Mode cannot be enabled unless either the Dungeon Master or"
                              " Administrator flags are already enabled.")
                return
            player.set_flag(PlayerFlags.DEBUG_MODE)
        else:
            player.clear_flag(PlayerFlags.DEBUG_MODE)  # Toggle off if it is on.

    def show_dm_flag(self, player: Player):
        return player.show_flag(PlayerFlags.DUNGEON_MASTER).split(": ")[1]

    def edit_dm_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.DUNGEON_MASTER, True)

    def show_expert_flag(self, player: Player):
        return player.show_flag(PlayerFlags.EXPERT_MODE).split(": ")[1]

    def edit_expert_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.EXPERT_MODE, True)

    def show_orator_flag(self, player: Player):
        return player.show_flag(PlayerFlags.ORATOR).split(": ")[1]

    def edit_orator_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.ORATOR, True)

    def show_has_horse_flag(self, player: Player):
        return player.show_flag(PlayerFlags.HAS_HORSE).split(": ")[1]

    def edit_has_horse_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.HAS_HORSE, True)

    def show_mounted_flag(self, player: Player):
        return player.show_flag(PlayerFlags.MOUNTED).split(": ")[1]

    def edit_mounted_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.MOUNTED, True)

    def show_hunger_flag(self, player: Player):
        return player.show_flag(PlayerFlags.HUNGER).split(": ")[1]

    def edit_hunger_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.HUNGER, True)

    def show_poison_flag(self, player: Player):
        return player.show_flag(PlayerFlags.POISON).split(": ")[1]

    def edit_poison_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.POISON, True)

    def show_thirst_flag(self, player: Player):
        return player.show_flag(PlayerFlags.THIRST).split(": ")[1]

    def edit_thirst_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.THIRST, True)

    def show_thug_flag(self, player: Player):
        return player.show_flag(PlayerFlags.THUG_ATTACK).split(": ")[1]

    def edit_thug_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.THUG_ATTACK, True)

    def show_tired_flag(self, player: Player):
        return player.show_flag(PlayerFlags.TIRED).split(": ")[1]

    def edit_tired_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.TIRED, True)

    def show_unconscious_flag(self, player: Player):
        return player.show_flag(PlayerFlags.UNCONSCIOUS).split(': ')[1]

    def toggle_unconscious_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.UNCONSCIOUS, True)

    def show_wraith_king_alive_flag(self, player: Player):
        return player.show_flag(PlayerFlags.WRAITH_KING_ALIVE).split(": ")[1]

    def edit_wraith_king_alive_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.WRAITH_KING_ALIVE, True)

    def show_wraith_master_flag(self, player: Player):
        return player.show_flag(PlayerFlags.WRAITH_MASTER).split(": ")[1]

    def edit_wraith_master_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.HUNGER, True)

    def show_more_flag(self, player: Player):
        return player.show_flag(PlayerFlags.MORE_PROMPT).split(": ")[1]

    def edit_more_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.MORE_PROMPT, True)

    def show_compass_used_flag(self, player: Player):
        return player.show_flag(PlayerFlags.COMPASS_USED).split(": ")[1]

    def edit_compass_used_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.COMPASS_USED, True)

    def show_disease_flag(self, player: Player):
        return player.show_flag(PlayerFlags.DISEASE).split(": ")[1]

    def edit_disease_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.DISEASE)

    def show_dwarf_alive_flag(self, player: Player):
        return player.show_flag(PlayerFlags.DWARF_ALIVE).split(": ")[1]

    def edit_dwarf_alive_flag(self, player: Player):
        player.toggle_flag(PlayerFlags.DWARF_ALIVE, True)


@dataclass
class HitPointsMenu(Menu):
    title: str = "Hit Points"

    def __post_init__(self):
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


def old_menu_system(player: Player):
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
        MenuItem("Alignment", 'al', submenu=AlignmentMenu),
        MenuItem("Armor & Shield", 'ar', submenu=ArmorShieldMenu),
        MenuItem("Attributes", 'at', submenu=AttributeMenu),
        MenuItem("Character Names", 'n', submenu=CharacterNamesMenu),
        MenuItem("Combinations", 'c', submenu=CombinationMenu),
        MenuItem("Flags & Counters", 'f', submenu=FlagsCountersMenu),
        MenuItem("Hit Points", 'h', submenu=HitPointsMenu),
        MenuItem("Map Information", 'mi', submenu=MapInfoMenu),
        MenuItem("Money", 'mo', submenu=MoneyMenu),
        MenuItem("Statistics", 's', submenu=StatisticsMenu),
        MenuItem("Weapons", 'w', submenu=WeaponsMenu),
        MenuItem("Quit", 'q', action=lambda p: exit("Exiting character editor.")),
    ]

    menu_stack: List[Menu] = [Menu(title="Main Menu", menu_items=main_menu_items)]

    while menu_stack:
        current_menu = menu_stack[-1]
        current_menu.display_menu()
        choice = current_menu.get_user_choice()

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


def main(player: Player):
    """Main function to handle menu interactions."""
    # menu setup - menus must be defined in reverse order because of submenu dependencies
    # (i.e., MainMenu references submenu SubMenu [which needs to be defined before MainMenu
    # in order to work properly]
    # FIXME: to display flag status with a dot leader, currently setting
    #  text=player.show_flag_line_item(PlayerFlags.ADMIN, None) does not work. Not sure why.
    # instead, use 'text="string"' and dot_leader_handler=<class.method>, as below.
    flags_and_counters = Menu("Flags & Counters", columns=1)
    """
    This simply returns and displays 'None':
    MenuItem("Debug Mode",
           dot_leader_handler=player.show_flag_line_item(PlayerFlags.DEBUG_MODE, None),
           action=player.toggle_flag(PlayerFlags.DEBUG_MODE, True)
           ),
    """
    menu_items = [MenuItem("Section Header"),
                  MenuItem(PlayerFlags.ADMIN.value,
                           dot_leader_handler=lambda p: player.show_flag_status(PlayerFlags.ADMIN),
                           action=FlagsAndCounters.edit_admin_flag),
                  MenuItem(PlayerFlags.ARCHITECT.value,
                           dot_leader_handler=FlagsAndCounters.show_architect_flag,
                           action=FlagsAndCounters.edit_architect_flag),
                  # can only enable Debug Mode if already Administrator or Dungeon Master:
                  MenuItem(PlayerFlags.DEBUG_MODE.value,
                           dot_leader_handler=FlagsAndCounters.show_debug_flag,
                           action=FlagsAndCounters.edit_debug_flag),
                  MenuItem(PlayerFlags.DUNGEON_MASTER.value,
                                    dot_leader_handler=FlagsAndCounters.show_dm_flag,
                                    action=FlagsAndCounters.edit_dm_flag),
                  MenuItem(PlayerFlags.ORATOR.value,
                                    dot_leader_handler=FlagsAndCounters.show_orator_flag,
                                    action=FlagsAndCounters.edit_orator_flag),
                  MenuItem("Guild"),
                  MenuItem(PlayerFlags.GUILD_AUTODUEL.value,
                           dot_leader_handler=FlagsAndCounters.show_autoduel_flag,
                           action=FlagsAndCounters.edit_autoduel_flag),
                  MenuItem(PlayerFlags.GUILD_FOLLOW_MODE.value,
                           dot_leader_handler=FlagsAndCounters.show_guild_follow_flag,
                           action=FlagsAndCounters.edit_guild_follow_flag),
                  MenuItem(PlayerFlags.GUILD_MEMBER.value,
                           dot_leader_handler=FlagsAndCounters.show_guild_member_flag,
                           action=FlagsAndCounters.edit_guild_member_flag),
                  MenuItem("Horse options"),
                  MenuItem(PlayerFlags.HAS_HORSE.value,
                           dot_leader_handler=FlagsAndCounters.show_has_horse_flag,
                           action=FlagsAndCounters.edit_has_horse_flag),
                  MenuItem(PlayerFlags.MOUNTED.value,
                           dot_leader_handler=FlagsAndCounters.show_mounted_flag,
                           action=FlagsAndCounters.edit_has_horse_flag),
                  MenuItem("Option toggles"),
                  MenuItem(PlayerFlags.EXPERT_MODE.value,
                           dot_leader_handler=FlagsAndCounters.show_expert_flag,
                           action=FlagsAndCounters.edit_expert_flag),
                  MenuItem(PlayerFlags.HOURGLASS.value,
                           dot_leader_handler=FlagsAndCounters.show_hourglass_flag,
                           action=FlagsAndCounters.edit_hourglass_flag),
                  MenuItem(PlayerFlags.MORE_PROMPT.value,
                           dot_leader_handler=FlagsAndCounters.show_more_flag,
                           action=FlagsAndCounters.edit_more_flag),
                  MenuItem(PlayerFlags.ROOM_DESCRIPTIONS.value,
                           dot_leader_handler=FlagsAndCounters.show_room_descs_flag,
                           action=FlagsAndCounters.edit_room_descs_flag),
                  MenuItem("Health issues"),
                  MenuItem(PlayerFlags.DISEASE.value,
                           dot_leader_handler=FlagsAndCounters.show_disease_flag,
                           action=FlagsAndCounters.edit_disease_flag),
                  MenuItem(PlayerFlags.HUNGER.value,
                           dot_leader_handler=FlagsAndCounters.show_hunger_flag,
                           action=FlagsAndCounters.edit_hunger_flag),
                  MenuItem(PlayerFlags.POISON.value,
                           dot_leader_handler=FlagsAndCounters.show_poison_flag,
                           action=FlagsAndCounters.edit_poison_flag),
                  MenuItem(PlayerFlags.THIRST.value,
                           dot_leader_handler=FlagsAndCounters.show_thirst_flag,
                           action=FlagsAndCounters.edit_thirst_flag),
                  MenuItem(PlayerFlags.TIRED.value,
                           dot_leader_handler=FlagsAndCounters.show_tired_flag,
                           action=FlagsAndCounters.edit_tired_flag),
                  MenuItem(PlayerFlags.UNCONSCIOUS.value,
                           dot_leader_handler=FlagsAndCounters.show_unconscious_flag,
                           action=FlagsAndCounters.edit_unconscious_flag),
                  MenuItem("Game States"),
                  MenuItem(PlayerFlags.AMULET_OF_LIFE_ENERGIZED.value,
                           dot_leader_handler=FlagsAndCounters.show_amulet_energized_flag,
                           action=FlagsAndCounters.edit_amulet_energized_flag),
                  MenuItem(PlayerFlags.COMPASS_USED.value,
                           dot_leader_handler=FlagsAndCounters.show_compass_used_flag,
                           action=FlagsAndCounters.edit_compass_used_flag),
                  MenuItem(PlayerFlags.DWARF_ALIVE.value,
                           dot_leader_handler=FlagsAndCounters.show_dwarf_alive_flag,
                           action=FlagsAndCounters.edit_dwarf_alive_flag),
                  MenuItem(PlayerFlags.GAUNTLETS_WORN.value,
                           dot_leader_handler=FlagsAndCounters.show_gauntlets_worn_flag,
                           action=FlagsAndCounters.edit_gauntlets_worn_flag),
                  MenuItem(PlayerFlags.RING_WORN.value,
                           dot_leader_handler=FlagsAndCounters.show_ring_worn_flag,
                           action=FlagsAndCounters.edit_ring_worn_flag),
                  MenuItem(PlayerFlags.SPUR_ALIVE.value,
                           dot_leader_handler=FlagsAndCounters.show_spur_alive_flag,
                           action=FlagsAndCounters.edit_spur_alive_flag),
                  MenuItem(PlayerFlags.THUG_ATTACK.value,
                           dot_leader_handler=FlagsAndCounters.show_thug_flag,
                           action=FlagsAndCounters.edit_thug_flag),
                  MenuItem(PlayerFlags.WRAITH_KING_ALIVE.value,
                           dot_leader_handler=FlagsAndCounters.show_wraith_king_alive_flag,
                           action=FlagsAndCounters.edit_wraith_king_alive_flag),
                  MenuItem(PlayerFlags.WRAITH_MASTER.value,
                           dot_leader_handler=FlagsAndCounters.show_wraith_master_flag,
                           action=FlagsAndCounters.edit_wraith_master_flag),
                  ]

    name_menu = Menu("Character Names", columns=1)
    name_menu.add_item(MenuItem("Main Character", "m",
                                dot_leader_handler=lambda p: player.name,
                                action=CharacterNames.edit_main_char_name))

    alignment_menu = Menu("Alignment Menu", columns=1)
    alignment_menu.add_item(MenuItem("Natural Alignment", "N",
                                     dot_leader_handler=lambda: {player.natural_alignment},
                                     action=AlignmentMenu.edit_natural_alignment(player)))

    main_menu = Menu("Main Menu", columns=2)
    main_menu.add_item(MenuItem("Alignment", "A", submenu=AlignmentMenu))
    main_menu.add_item(MenuItem("Armor & Shield", "A", action=NotImplemented))
    main_menu.add_item(MenuItem("Attributes", "A", action=NotImplemented))
    main_menu.add_item(MenuItem("Character Names", "C", submenu=name_menu))
    main_menu.add_item(MenuItem("Combinations", "CO", action=NotImplemented))
    main_menu.add_item(MenuItem("Flags & Counters", "F", submenu=flags_and_counters))
    main_menu.add_item(MenuItem("Hit Points", "H", action=NotImplemented))
    main_menu.add_item(MenuItem("Map Info", "M", action=NotImplemented))
    main_menu.add_item(MenuItem("Silver", "S", action=NotImplemented))

    # Use a stack to track menu depth
    menu_stack: List[Menu] = [main_menu]
    # initiate navigation:
    main_menu.navigate_menu(menu_stack)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)-8s | %(funcName)20s() | %(message)s')

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
