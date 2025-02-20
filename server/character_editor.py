import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List

from flags import Player, PlayerFlags


class MainMenu(Enum):
    """Main menu options."""
    TITLE = "Main Menu"
    ALIGNMENT = "Alignment"
    ARMOR_SHIELD = "Armor & Shield"
    ATTRIBUTES = "Attributes"
    CHARACTER_NAMES = "Character Names"
    COMBINATIONS = "Combinations"
    FLAGS_COUNTERS = "Flags & Counters"
    HIT_POINTS = "Hit Points"
    MAP_INFO = "Map Info"
    MONEY = "Money"
    STATISTICS = "Statistics"
    WEAPONS = "Weapons"
    EXIT = "Exit"


class AlignmentMenu(Enum):
    """Alignment information sub-menu options."""
    TITLE = "Alignment Options"
    NATURAL_ALIGNMENT = "Natural Alignment"
    CURRENT_ALIGNMENT = "Current Alignment"


class ArmorShieldMenu(Enum):
    """Armor and shield options."""
    TITLE = "Armor & Shield Options"
    ARMOR_ITEMS = "Armor Items"
    SHIELD_ITEMS = "Shield Items"


class FlagsCountersMenu(Enum):
    """Flags & counters configuration options."""
    TITLE = "Flags & Counters"
    # HUNGRY_FLAG = flags.Player.show_flag_line_item(flag=PlayerFlags.HUNGER, leading_num=None)
    # THIRSTY_FLAG = flags.Player.show_flag_line_item(flag=PlayerFlags.THIRST, leading_num=None)
    HUNGER_FLAG = "Hunger"
    THIRSTY_FLAG = "Thirst"
    TIRED_FLAG = "Tired"


def build_flags_menu(flags: dict) -> list:
    """
    Builds a menu of flags with formatted line items to display with show_menu().

    :param flags: A dictionary of player flags.
    :return: list: A list of formatted flag line items for the menu.
    """
    leading_number = None  # A clearer constant for leading number behavior
    return [player.show_flag_line_item(flag=flag, leading_num=leading_number) for flag in flags]


def dict_to_enum(name: Enum, items: dict) -> Enum:
    """Convert a dict [from build_flags_menu()] into an Enum [for print_menu()] with numbered options."""
    logging.debug("dict_to_enum: %s" % items)
    return Enum(name, {i: item for i, item in enumerate(items)})


def print_menu(menu_enum: Enum, columns: int = 1):
    """Prints the given menu with options."""
    menu_list = list(menu_enum)[1:]  # Convert Enum to list for indexing
    print()
    # display menu title:
    print(menu_enum.TITLE.value)
    print("-" * (20 * columns))

    if columns == 2:
        logging.debug("Columns: 2")
        num_items = len(menu_list)
        midpoint = (num_items + 1) // 2  # Calculate midpoint for even/odd lists

        for i in range(max(midpoint, num_items - midpoint)):  # Iterate up to the larger column size
            column_1_num = i + 1
            column_1_item = menu_list[i] if i < len(menu_list) else None

            column_2_num = i + midpoint + 1
            column_2_item = menu_list[i + midpoint] if i + midpoint < len(menu_list) else None

            line = ""

            if column_1_item:
                line += f"{column_1_num: >2}. {column_1_item.value.title().ljust(20, ' ')}"
            else:
                line += " " * 24  # Add space padding to maintain alignment

            if column_2_item:
                line += f"{column_2_num: >2}. {column_2_item.value.title()}"

            print(line)

    else:
        for num, option in enumerate(menu_list, start=1):
            print(f"{num: >2}. {option.value.title()}")

    print("-" * (20 * columns))


class MenuOption(Enum):
    """Demo of the print_menu() function"""
    TITLE = "Menu Options"
    OPTION_1 = "Option 1"
    OPTION_2 = "Option 2"
    OPTION_3 = "Option 3"
    OPTION_4 = "Option 4"
    OPTION_5 = "Option 5"
    OPTION_6 = "Option 6"
    OPTION_7 = "Option 7"  # example of an odd number of items


def get_user_choice(menu_enum: Enum, menu_stack: list):
    """Gets user input and validates it within the menu.

    :param menu_enum: the menu Enum to validate options against
    :param menu_stack: list representing how many menu levels deep we are,
     used for displaying "Enter: Up a level"
    :returns: enum_member: menu item selected, or None if Return hit
    """
    while True:
        try:
            # first item in [menu_stack] is always <enum 'MainMenu'>
            logging.debug("menu_stack: %s" % menu_stack)
            if len(menu_stack) > 1:
                print("Enter: Go up a level")
            # len()-1 accounts for first item being the menu title:
            prompt = f"Enter your choice [1-{len(menu_enum)-1}]: "
            choice = input(prompt)
            print()
            if not choice:  # Check for empty input (Enter key)
                return None  # Return None to indicate "go back"
            option_number = int(choice) - 1  # Corrected: subtract 1 for 0-based indexing
            if 0 <= option_number < len(menu_enum):  # Corrected: check against list length
                return list(menu_enum)[option_number]  # Return the enum member
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def main():
    """Main function to handle menu interactions."""
    menu_stack: List[Enum] = [MainMenu]  # Use a stack to track menu depth
    while menu_stack:
        current_menu = menu_stack[-1]  # Get the current menu
        num_columns = 1 if len(current_menu) < 10 else 2
        print_menu(current_menu, columns=num_columns)
        choice = get_user_choice(current_menu, menu_stack)
        logging.debug("Current choice: %s" % choice)

        if choice is None:  # Go back if Enter is pressed
            menu_stack.pop()  # Remove the current menu from the stack
            continue  # Go to the previous menu

        # change current_menu to selection
        # current_menu = [MainMenu, AlignmentMenu, ArmorShieldMenu, None, None, FlagsCountersMenu,
        #                 None, None, None, None, None, None][int(choice)]

        # Handle menu choices
        logging.debug("current_menu: %s" % current_menu)
        logging.debug("choice: %s" % choice)
        if current_menu == MainMenu:
            if choice == MainMenu.ALIGNMENT:
                menu_stack.append(AlignmentMenu)
                print_menu(AlignmentMenu)
                alignment_option = get_user_choice(AlignmentMenu, menu_stack)
                if alignment_option == AlignmentMenu.NATURAL_ALIGNMENT:
                    print("Natural Alignment is dependent on character class")
                if alignment_option == AlignmentMenu.CURRENT_ALIGNMENT:
                    print("Current Alignment chosen")

            elif choice == MainMenu.FLAGS_COUNTERS:
                logging.debug("MainMenu.FLAGS_COUNTERS selected")
                menu_stack.append(FlagsCountersMenu)
                print("Flags & Counters")
                # display character flags:

                """
                # Extracted function to build menu of flags
                flags_list = build_flags_menu(player.flags)
                logging.debug(flags_list)
                flags_menu_enum = dict_to_enum("FlagCounterMenu", flags_list)
                print_menu(flags_menu_enum)  # Display the menu
                flags_option = get_user_choice(flags_menu_enum, menu_stack)
                """
                # Example usage
                flags_list = ["Flag 1", "Flag 2", "Flag 3"]
                flags_menu_enum = dict_to_enum(FlagsCountersMenu, flags_list)

                # Now `FlagsMenuEnum` can be passed to `print_menu`
                print_menu(flags_menu_enum)

            elif current_menu == ArmorShieldMenu:
                # ... handle Armor & Shield choices
                print("Armor & Shield options")
            # ... handle other menus

        elif current_menu == FlagsCountersMenu:
            print("Flags & Counters")
            for i, flag in player.flags:
                player.show_flag_line_item(flag=flag, leading_num=i)


if __name__ == "__main__":
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')

    player = Player(name="Rulan", id_num=1)

    # Example Usage:
    print("Two columns:")
    print_menu(MenuOption, columns=2)
    print("One column:")
    print_menu(MenuOption)

    main()
