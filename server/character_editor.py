import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable, NamedTuple

from flags import PlayerFlags
from characters import PlayerStat, Alignment
from player import Player


def line_item(item_name: str, item_value: str | int, width: int = 30):
    return f"{item_name:.>{width}}: {item_value}"


@dataclass
class Menu(object):
    title: str = "Title"
    menu_items: list = field(default_factory=list)


class MenuItem(NamedTuple):
    """
    :param text: shortcut letters to type to select item (besides numeric item #)
    """
    # text of menu item:
    text: str = None
    # shortcut letters to type to select item (besides numeric item #):
    shortcut: Optional[str] = None
    # function which diplays line_item() value after dot leader:
    # if None, do not display a dot leader and the result of this function.
    dot_leader_handler: Optional[Callable] = None
    # submenu to go to after item selected:
    submenu: Optional[Menu] = None
    # function to edit item if submenu is None:
    edit_function: Optional[Callable] = None


@dataclass
class Menu:
    """Base class for menu systems with shared behavior."""
    title: str
    columns: int = 1
    menu_items: list[MenuItem] = field(default_factory=list)

    def display_menu(self) -> None:
        """Display menu options."""
        print(f"{self.title}\n{'=' * len(self.title)}")
        for index, (label, shortcut, _) in enumerate(self.menu_items, start=1):
            print(f"{index}. [{shortcut:>2}] {label}")

    def run_option(self, choice: str) -> None:
        """Run the handler method for a given choice."""
        for label, shortcut, handler in self.menu_items:
            if choice == shortcut:
                if callable(handler):
                    handler()
                else:
                    print(f"No valid handler found for {label}")
                return
        print("Invalid option. Please try again.")


# Refactored AlignmentMenu
@dataclass
class AlignmentMenu(Menu, Player):
    """Menu for alignment information options."""
    title = "Alignment Options"
    # player: Player  # Accepting Player or compatible object

    def __post_init__(self):
        """Initialize menu-specific items."""
        self.menu_items = [MenuItem("Natural Alignment", "n", self.show_natural_alignment, None, self.edit_natural_alignment),
                           MenuItem["Current Alignment", "c", self.show_current_alignment, None, self.edit_current_alignment],
                           ]

    def show_natural_alignment(self) -> None:
        """Show natural alignment"""
        print(f"{self.player.natural_alignment}")

    def show_current_alignment(self) -> None:
        """Show current alignment"""
        print(f"{self.player.natural_alignment}")

    def edit_natural_alignment(self) -> None:
        """Edit natural alignment"""
        print(f"Natural Alignment is dependent on character class.")
        print(f"{self.player.name}'s natural alignment (fixed) is {self.player.natural_alignment}.")

    def edit_current_alignment(self) -> None:
        """Edit current alignment"""
        print(f"Current Alignment is {self.player.current_alignment}.")
        print("Available alignments:")
        for i, alignment in enumerate(Alignment):  # Iterating over the Alignment enum
            print(f"- {alignment.value}")
        print("Choose an alignment option:")
        for i, alignment in enumerate(Alignment):
            print(f"{i + 1}: {alignment.name}")
        choice = input("Enter your choice: ").strip()
        try:
            alignment = Alignment(int(choice) - 1)
            self.player.current_alignment = alignment
            print(f"Current Alignment set to {self.player.current_alignment}.")
        except (ValueError, IndexError):
            print("Invalid alignment selected.")
            print(f"Current Alignment set to {player.current_alignment}.")
        else:
            print("No alignment selected.")
        return player.current_alignment


class ArmorShieldMenu(Menu):
    """Armor and shield options."""
    title: str = "Armor & Shield Options"

    def __post_init__(self):
        self.menu_items = [MenuItem("Armor Items", "a", None, None, self.edit_armor_items),
                           MenuItem("Shield Items", "s", None, None, self.edit_shield_items),
                           ]

    def edit_armor_items(self):
        print("Editing armor items...")

    def edit_shield_items(self):
        print("Editing shield items...")


class AttributeMenu(Menu):
    """Show/edit player attributes."""
    title = "Attributes"
    menu_items: list = field(default_factory=list)

    def __post_init__(self):
        self.menu_items = [
            line_item(stat.value, self.player.get_stat(stat), width=30) for stat in PlayerStat
        ]


class CharacterNamesMenu(Menu):
    title: str = "Character Names"

    def __post_init__(self):
        menu_items = [MenuItem["Main Character Name", "m", self.show_main_char_name, None, self.edit_main_char_name],
                      MenuItem["Ally 1 Name", None, self.show_ally_1_name, None, self.edit_ally_1_name],
                      MenuItem["Ally 2 Name", None, self.show_ally_2_name, None, self.edit_ally_2_name],
                      MenuItem["Ally 3 Name", None, self.show_ally_3_name, None, self.edit_ally_3_name],
                      MenuItem["Horse Name", None, self.show_horse_name, None, self.edit_horse_name],
                      ]

    def show_main_char_name(self):
        print(f"{player.name}")

    def edit_main_char_name(self):
        print("Edit main character name")
        new_name = input("Enter new name: ")
        player.name = new_name
        print(f"Main character name set to {player.name}.")
        return player.name

    def show_ally_1_name(self):
        print(f"{player.ally_1_name}")

    def edit_ally_1_name(self):
        print("Edit ally 1 name")
        new_name = input("Enter new name: ")
        player.ally_1_name = new_name
        print(f"Ally 1 name set to {player.ally_1_name}.")
        return player.ally_1_name

    def show_ally_2_name(self):
        print(f"{player.ally_2_name}")

    def edit_ally_2_name(self):
        print("Edit ally 2 name")
        new_name = input("Enter new name: ")
        player.ally_2_name = new_name
        print(f"Ally 2 name set to {player.ally_2_name}.")
        return player.ally_2_name

class FlagsCountersMenu(Menu, Player):
    """Flags & counters configuration options."""
    title: "Flags & Counters"
    menu_items = [MenuItem(text=Player.show_flag(flag), shortcut=None,
                           dot_leader_handler=lambda flag=flag: player.show_flag_line_item(flag, None),
                           submenu=None, edit_function=None) for flag in PlayerFlags]

    def build_flags_menu(self, flags: dict) -> list:
        """
        Builds a menu of flags with formatted line items to display with show_menu().

        :param flags: A dictionary of player flags.
        :return: list: A list of formatted flag line items for the menu.
        """
        # leading_num = None since print_menu() adds item numbers
        return [player.show_flag_line_item(flag=flag, leading_num=None) for i, flag in enumerate(flags)]


class MainMenu(Menu):
    """Main menu options."""
    # 'None' simply indicates code isn't ready yet.
    title = "Main Menu"
    menu_items = [MenuItem["Alignment", "al", None, AlignmentMenu, None],
                  MenuItem["Armor & Shield", "ar", None, ArmorShieldMenu, None],
                  MenuItem["Attributes", "at", None, AttributeMenu, None],
                  MenuItem["Character Names", "cn", None, CharacterNamesMenu, None],
                  MenuItem["Combinations", "co", None, None, None],
                  MenuItem["Flags & Counters", "f", None, FlagsCountersMenu, None],
                  MenuItem["Hit Points", "h", None, None, None],
                  MenuItem["Map Info", "mi", None, None, None],
                  MenuItem["Money", "mo", None, None, None],
                  MenuItem["Statistics", "s", None, None, None],
                  MenuItem["Weapons", "w", None, None, None],
                  MenuItem["Quit", "q", None, None, None],
                  ]


def print_menu(title: Optional[str], menu_items: list, columns: int = 1):
    """Prints the given menu with options."""
    print()
    num_items = len(menu_items)
    # display menu title:
    if title:
        print(title)
    print("-" * (20 * columns))

    if columns == 2:
        logging.debug("Columns: 2")
        midpoint = (num_items + 1) // 2  # Calculate midpoint for even/odd lists

        for i in range(max(midpoint, num_items - midpoint)):  # Iterate up to the larger column size
            column_1_num = i + 1
            column_1_item = menu_items[i][0] if i < num_items else None

            column_2_num = i + midpoint + 1
            column_2_item = menu_items[i + midpoint][0] if i + midpoint < num_items else None

            line = ""

            if column_1_item:
                line += f"{column_1_num: >2}. {column_1_item.title().ljust(20, ' ')}"
            else:
                line += " " * 24  # Add space padding to maintain alignment

            if column_2_item:
                line += f"{column_2_num: >2}. {column_2_item.title()}"

            print(line)

    else:
        for num, option in enumerate(menu_items, start=1):
            shortcut = f"[{option['shortcut']}] / " if option['shortcut'] else "      "
            print(f"{shortcut} {num: >2}. {option['text'].title()}")

    print("-" * (20 * columns))


class MenuOptionDemo(Menu):
    """Demo of the print_menu() function"""
    title: str = "Menu Options Demo"
    columns: int = 2

    def __postinit__(self):
        # example of an odd number of items:
        self.menu_items = [MenuItem["Option 1", None, None, None, self.run_option_1],
                     MenuItem["Option 2", None, None, None, self.run_option_2],
                     MenuItem["Option 3", None, None, None, self.run_option_3],
                     MenuItem["Option 4", None, None, None, MenuOptionDemo.run_option_4],
                     MenuItem["Option 5", None, None, None, MenuOptionDemo.run_option_5],
                     MenuItem["Option 6", None, None, None, MenuOptionDemo.run_option_6],
                     MenuItem["Option 7", None, None, None, MenuOptionDemo.run_option_7],
                     ]

    def run_option_1(self):
        print("Option 1 selected.")

    def run_option_2(self):
        print("Option 2 selected.")

    def run_option_3(self):
        print("Option 3 selected.")

    def run_option_4(self):
        print("Option 4 selected.")

    def run_option_5(self):
        print("Option 5 selected.")

    def run_option_6(self):
        print("Option 6 selected.")

    def run_option_7(self):
        print("Option 7 selected.")


def get_user_choice(menu_items: list):
    """
    Gets the user's choice and calls the corresponding class method or a standalone function.

    :param menu_items: A list of menu items mapped to tuples (class_ref, method_name/function).
    """
    while True:
        try:
            # first item in [menu_stack] is always <enum 'MainMenu'>
            logging.debug("menu_stack: %s" % menu_stack)
            if len(menu_stack) > 1:
                print("Enter: Go up a level")
            # len()-1 accounts for first item being the menu title:
            prompt = f"Enter your choice [1-{len(menu_enum) - 1}]: "
            choice = input(prompt)
            print()
            if not choice:  # Check for empty input (Enter key)
                return None  # Return None to indicate "go back"
            option_number = int(choice) - 1  # Corrected: subtract 1 for 0-based indexing
            if 0 <= option_number < len(menu_enum):  # Corrected: check against list length
                return list(menu_enum)[option_number + 1]  # Return the enum member
            else:
                print("Invalid menu item configuration.")
        elif callable(selected_item):
            # Case 3: Direct callable function
            selected_item()
        else:
            print("Unknown menu item type. Please verify the configuration.")


def main():
    """Main function to handle menu interactions."""
    menu_stack: List[Menu] = [MainMenu]  # Use a stack to track menu depth
    while menu_stack:
        current_menu = menu_stack[-1]  # Get the current menu from top of stack
        num_columns = 1 if len(current_menu) < 10 else 2
        print_menu(current_menu, columns=num_columns)
        get_user_choice(current_menu, menu_stack)

        if choice is None:  # Go back if Enter is pressed
            menu_stack.pop()  # Remove the current menu from the stack
            continue  # Go to the previous menu

        # Handle menu choices
        # FIXME: this code is messy. refactor code to put each menu in a function call?
        logging.debug("current_menu: %s" % current_menu)
        logging.debug("choice: %s" % choice)


if __name__ == "__main__":
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')

    player = Player(name="Rulan", id_num=1)

    # Example Usage:
    show_demo = False
    if show_demo:
        print("Two columns:")
        print_menu(MenuOptionDemo, columns=2)
        print("One column:")
        print_menu(MenuOptionDemo, columns=1)

    main()
