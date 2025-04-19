import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable

# TADA-specific imports:
from flags import PlayerFlags
from characters import Player
from tada_utilities import input_string


def edit_string(prompt: str, current_string: str, player=Player) -> str:
    user_input = input(f"Edit {prompt}: ")
    if user_input is None or user_input == current_string:
        if not player.query_flag(PlayerFlags.EXPERT_MODE):
            print(f"Keeping '{current_string}'.")
        return current_string
    else:
        if not player.query_flag(PlayerFlags.EXPERT_MODE):
            print(f"Changing '{current_string}' to '{user_input}.'")
        return user_input


@dataclass
class MenuItem:
    """
    Represents a menu item in a hierarchical menu system.

    This class is a named tuple that defines a menu item with text, an optional
    shortcut, an optional dot leader handler function, an optional submenu, and
    an optional edit function. It is designed to facilitate menu system
    configuration and interaction by providing pre-defined attributes and a method
    to display the menu item as a formatted string. The menu item can either lead
    to a submenu, execute a function, or display an edited output.

    Attributes:
        text (str): Text of the menu item.
        shortcut (Optional[str]): Shortcut letters to type to select the item, in
            addition to the numeric item number.
        dot_leader_handler (Optional[Callable]): Function which displays the
            `line_item` value after the dot leader. If None, dot leaders
            and the function result are not shown.
        submenu (Optional[Menu]): Submenu to navigate to after the item is
            selected.
        edit_function (Optional[Callable]): Function to edit the item if
            a submenu is not present.
    """
    # text of menu item:
    text: str | Callable = None
    # shortcut letters to type to select item (besides numeric item #):
    shortcut: Optional[str] = None
    # function which displays line_item() value after dot leader:
    # if None, do not display a dot leader and the result of this function.
    dot_leader_handler: Optional[Callable] = None
    # submenu to go to after item selected:
    submenu: Optional['Menu'] = None
    # function to edit item if submenu is None:
    edit_function: Optional[Callable] = None

    def line_item(self, width: int = 40):
        """
        Returns a formatted line item with optional dot leaders.

        This method generates a line item string, optionally formatted with
        dot leaders, based on the provided width and the presence of
        a dot leader handler. If text is provided and a custom
        dot leader handler function is defined, the formatted output
        will ensure alignment and utilize the handler as necessary.

        Parameters:
            width (int, optional): The total width of the formatted line. Defaults to 40.

        Returns:
            str: The formatted line item, either as the plain text or with dot leaders
            and custom handling if applicable.
        """
        logging.debug("width: %s" % width)
        # e.g., calling player.flag_line_item() to handle the entire line of menu text:
        if self.text is None:
            self.text = ""
        if self.dot_leader_handler is None:
            return f"{self.text.ljust(width, ' ')}"
        elif callable(self.dot_leader_handler):
            logging.debug("dot_leader_handler: %s" % self.dot_leader_handler)
            return f"{self.text.ljust(width, '.')}: {self.dot_leader_handler(self)}"


@dataclass
class Menu:
    """Base class for menu systems with shared behavior."""
    title: str
    columns: int = 1
    menu_items: list[MenuItem] = field(default_factory=list)

    def add_item(self, item: MenuItem):
        self.menu_items.append(item)


class CharacterNames(Menu):
    def show_main_char_name(self):
        return player.name

    def edit_main_char_name(self):
        name = input_string("Edit main character name", player.name)
        player.name = name

    def edit_ally_1_name(self):
        name = edit_string("ally 1's name", player.ally[1].name)


class FlagsAndCounters(Menu):
    """Edit flags & counters"""
    def show_admin_flag(self):
        # we just want the result from the Admin flag query string,
        # so split string into "Administrator", ": ", "Yes/No".
        # return list index 1 (the "Yes/No", "On/Off" result)
        return player.show_flag(PlayerFlags.ADMIN).split(": ")[1]

    def edit_admin_flag(self):
        player.toggle_flag(PlayerFlags.ADMIN, True)

    def show_architect_flag(self):
        return player.show_flag(PlayerFlags.ARCHITECT).split(": ")[1]

    def edit_architect_flag(self):
        player.toggle_flag(PlayerFlags.ARCHITECT, True)

    def show_debug_flag(self):
        return player.show_flag(PlayerFlags.DEBUG_MODE).split(": ")[1]

    def edit_debug_flag(self):  # Pass player as an argument
        """
        Cannot enable Debug Mode without first being a Dungeon Master or
        Administrator.
        :return:
        """
        if not player.query_flag(PlayerFlags.DEBUG_MODE):  # Check if DEBUG_MODE is off
            # Check if both ADMIN and DUNGEON_MASTER are off:
            if not player.query_flag(PlayerFlags.ADMIN) or not player.query_flag(PlayerFlags.DUNGEON_MASTER):
                print("Debug Mode cannot be enabled without first being a Dungeon Master or an Administrator.")
                return
            player.toggle_flag(PlayerFlags.DEBUG_MODE, True)
        else:
            player.toggle_flag(PlayerFlags.DEBUG_MODE, False)  # Toggle off if it is on.

    def show_dm_flag(self):
        return player.show_flag(PlayerFlags.DUNGEON_MASTER).split(": ")[1]

    def edit_dm_flag(self):
        player.toggle_flag(PlayerFlags.DUNGEON_MASTER, True)

    def show_expert_flag(self):
        return player.show_flag(PlayerFlags.EXPERT_MODE).split(": ")[1]

    def edit_expert_flag(self):
        player.toggle_flag(PlayerFlags.EXPERT_MODE, True)

    def show_orator_flag(self):
        return player.show_flag(PlayerFlags.ORATOR).split(": ")[1]

    def edit_orator_flag(self):
        player.toggle_flag(PlayerFlags.ORATOR, True)

    def show_has_horse_flag(self):
        return player.show_flag(PlayerFlags.HAS_HORSE).split(": ")[1]

    def edit_has_horse_flag(self):
        player.toggle_flag(PlayerFlags.HAS_HORSE, True)

    def show_mounted_flag(self):
        return player.show_flag(PlayerFlags.MOUNTED).split(": ")[1]

    def edit_mounted_flag(self):
        player.toggle_flag(PlayerFlags.MOUNTED, True)

    def show_hunger_flag(self):
        return player.show_flag(PlayerFlags.HUNGER).split(": ")[1]

    def edit_hunger_flag(self):
        player.toggle_flag(PlayerFlags.HUNGER, True)

    def show_poison_flag(self):
        return player.show_flag(PlayerFlags.POISON).split(": ")[1]

    def edit_poison_flag(self):
        player.toggle_flag(PlayerFlags.POISON, True)

    def show_thirst_flag(self):
        return player.show_flag(PlayerFlags.THIRST).split(": ")[1]

    def edit_thirst_flag(self):
        player.toggle_flag(PlayerFlags.THIRST, True)

    def show_thug_flag(self):
        return player.show_flag(PlayerFlags.THUG_ATTACK).split(": ")[1]

    def edit_thug_flag(self):
        player.toggle_flag(PlayerFlags.THUG_ATTACK, True)

    def show_tired_flag(self):
        return player.show_flag(PlayerFlags.TIRED).split(": ")[1]

    def edit_tired_flag(self):
        player.toggle_flag(PlayerFlags.TIRED, True)

    def show_wraith_king_alive_flag(self):
        return player.show_flag(PlayerFlags.WRAITH_KING_ALIVE).split(": ")[1]

    def edit_wraith_king_alive_flag(self):
        player.toggle_flag(PlayerFlags.WRAITH_KING_ALIVE, True)

    def show_wraith_master_flag(self):
        return player.show_flag(PlayerFlags.WRAITH_MASTER).split(": ")[1]

    def edit_wraith_master_flag(self):
        player.toggle_flag(PlayerFlags.HUNGER, True)

    def show_more_flag(self):
        return player.show_flag(PlayerFlags.MORE_PROMPT).split(": ")[1]

    def edit_more_flag(self):
        player.toggle_flag(PlayerFlags.MORE_PROMPT, True)

    def show_compass_used_flag(self):
        return player.show_flag(PlayerFlags.COMPASS_USED).split(": ")[1]

    def edit_compass_used_flag(self):
        player.toggle_flag(PlayerFlags.COMPASS_USED, True)

    def show_disease_flag(self):
        return player.show_flag(PlayerFlags.DISEASE).split(": ")[1]

    def edit_disease_flag(self):
        player.toggle_flag(PlayerFlags.DISEASE)

    def show_dwarf_alive_flag(self):
        return player.show_flag(PlayerFlags.DWARF_ALIVE).split(": ")[1]

    def edit_dwarf_alive_flag(self):
        player.toggle_flag(PlayerFlags.DWARF_ALIVE, True)

    def show_option_4(self):
        """Example of calling a function using dot_leader_helper() function"""
        return f"Called {self.__class__.__qualname__}"

    def edit_option_4(self):
        print(f"{self.__class__.__qualname__}: Option 4 selected.")

    def show_autoduel_flag(self):
        return player.show_flag(PlayerFlags.GUILD_AUTODUEL).split(": ")[1]

    def edit_autoduel_flag(self):
        player.toggle_flag(PlayerFlags.GUILD_AUTODUEL, True)

    def show_guild_follow_flag(self):
        return player.show_flag(PlayerFlags.GUILD_FOLLOW_MODE).split(": ")[1]

    def edit_guild_follow_flag(self):
        player.toggle_flag(PlayerFlags.GUILD_FOLLOW_MODE, True)

    def show_guild_member_flag(self):
        return player.show_flag(PlayerFlags.GUILD_MEMBER).split(": ")[1]

    def edit_guild_member_flag(self):
        player.toggle_flag(PlayerFlags.GUILD_MEMBER, True)

    def show_hourglass_flag(self):
        return player.show_flag(PlayerFlags.HOURGLASS).split(": ")[1]

    def edit_hourglass_flag(self):
        player.toggle_flag(PlayerFlags.HOURGLASS, True)

    def show_gauntlets_worn_flag(self):
        return player.show_flag(PlayerFlags.GAUNTLETS_WORN).split(": ")[1]

    def edit_gauntlets_worn_flag(self):
        player.toggle_flag(PlayerFlags.GAUNTLETS_WORN, True)

    def show_room_descs_flag(self):
        return player.show_flag(PlayerFlags.ROOM_DESCRIPTIONS).split(": ")[1]

    def edit_room_descs_flag(self):
        player.toggle_flag(PlayerFlags.ROOM_DESCRIPTIONS, True)

    def show_unconscious_flag(self):
        return player.show_flag(PlayerFlags.UNCONSCIOUS).split(": ")[1]

    def edit_unconscious_flag(self):
        player.toggle_flag(PlayerFlags.UNCONSCIOUS, True)

    def show_amulet_energized_flag(self):
        return player.show_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED).split(": ")[1]

    def edit_amulet_energized_flag(self):
        player.toggle_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED, True)

    def show_ring_worn_flag(self):
        return player.show_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED).split(": ")[1]

    def edit_ring_worn_flag(self):
        player.toggle_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED, True)

    def show_spur_alive_flag(self):
        return player.show_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED).split(": ")[1]

    def edit_spur_alive_flag(self):
        player.toggle_flag(PlayerFlags.AMULET_OF_LIFE_ENERGIZED, True)

def is_section_header(menu_item: MenuItem):
    return menu_item.dot_leader_handler is None and menu_item.edit_function is None and menu_item.submenu is None

def print_menu(menu: Menu):
    """Prints the given menu with options."""
    print()
    # tally up all non-header items to get a true item menu count:
    num_items = len([item for item in menu.menu_items if not is_section_header(item)])
    # display menu title:
    if menu.title:
        print(menu.title)
    print("-" * (20 * menu.columns))

    if menu.columns == 2:
        logging.debug("Columns: 2")
        midpoint = (num_items + 1) // 2  # Calculate midpoint for even/odd lists
        item_number = 0
        for i in range(max(midpoint, num_items - midpoint)):  # Iterate up to the larger column size
            """
            Introducing section headers:
            If menu.menu_items[i].dot_leader_handler, .submenu and .edit_function are all None,
            the item is a section header, and no number should be displayed for it.
            """
            section_header_1 = is_section_header(menu.menu_items[i])
            # only increment internal numbering if not a section header:
            if not section_header_1:
                item_number += 1
            column_1_num = f"{item_number: >2}. " if not section_header_1 else "   "
            column_1_item = menu.menu_items[i].line_item()

            section_header_2 = is_section_header(menu.menu_items[i + midpoint - 1])
            column_2_num = f"{i + midpoint + 1: >2}. " if not section_header_2 else "   "
            column_2_item = menu.menu_items[i + midpoint].line_item() if i + midpoint < num_items else None
            line = []
            if column_1_item:
                line.append(f"{column_1_num}{column_1_item.ljust(menu.columns * 20, ' ')}")
            else:
                # Add space padding to maintain alignment
                line.append(" " * (20 * menu.columns))
            if column_2_item:
                line.append(f"{column_2_num}{column_2_item.ljust(menu.columns * 20, ' ')}")
            else:
                pass
                # line.append("<<<empty>>>")
            print(''.join(line))
    else:
        # 1 column
        logging.debug("Columns: 1")
        item_number = 0
        for i, option in enumerate(menu.menu_items):
            section_header_1 = is_header_item(option)
            if not section_header_1:
                item_number += 1
            column_1_num = f"{item_number: >2}. " if not section_header_1 else "    "
            # TODO: shortcut = f"{option.shortcut} / " if option.shortcut else "     "
            print(f"{column_1_num}{option.line_item(width=31).ljust(menu.columns * 20, ' ')}")
    print("-" * (20 * menu.columns))


def find_menu_item_by_shortcut(choice: str, items: list[MenuItem]) -> Optional[MenuItem]:
    """Helper function to find a menu item by its shortcut."""
    for item in items:
        if item.shortcut and choice == item.shortcut.lower():
            logging.debug("Shortcut '%s' selected.", choice)
            return item
    # shortcut not found:
    return None


def find_menu_item_by_number(choice: int, menu: Menu) -> Optional[MenuItem]:
    """
    Helper function to find a menu item by its option number.
    Since unnumbered section headers can be displayed, simply picking the index of a
    menu item won't work anymore:

    Flags & Counters
    --------------------
        Section Header
     1. Administrator..................: No
     2. Architect......................: No
     3. Debug Mode.....................: On
     4. Dungeon Master.................: No
     5. Orator.........................: Yes
        Guild Options
     6. Guild AutoDuel.................: Off
     7. Guild Follow Mode..............: Off
     8. Guild Member...................: No
        Horse options
    """
    items = [item for item in menu.menu_items if not is_header_item(item)]
    internal_number = 0  # menu numbering starts at 1
    while internal_number < choice:
        if not is_header_item(items[internal_number]):
            logging.debug("choice: %i, not header: %s" % (choice, items[internal_number].text))
            internal_number += 1
    logging.debug("exit: internal_number: %i, item: %s" % (internal_number, items[internal_number]))
    return internal_number


def is_header_item(menu_item: MenuItem) -> bool:
    return menu_item.dot_leader_handler is None and menu_item.submenu is None and menu_item.edit_function is None


def get_user_choice(menu: Menu, stack_depth: int) -> Optional[MenuItem]:
    """
    Gets the user's choice and returns either None, or the corresponding MenuItem object.

    :param menu: A Menu object containing menu items.
    :param stack_depth: how many levels deep in the menu hierarchy we are
        (used to display an appropriate message about what hitting Enter does)
    :return: The selected MenuItem object, or None if the user chooses to go up a menu level/quit.
    """
    # count all non-header items in menu to give accurate item count:
    selectable_items = [item for item in menu.menu_items if not is_header_item(item)]
    num_items = len(selectable_items)
    enter_function = "quit" if stack_depth == 1 else "go up a level"
    while True:
        print(f"Enter your choice [1-{num_items}], type [shortcut letters] to select an option, "
              f"or [Enter] to {enter_function}.")
        menu_choice = input(f"Enter your choice: ").strip().lower()

        if not menu_choice:  # No input, user wants to leave menu or quit
            return None

        shortcut_item = find_menu_item_by_shortcut(menu_choice, menu.menu_items)
        if shortcut_item:  # Found a match based on shortcut.
            return shortcut_item

        # Check if user entered a valid menu item number:
        if menu_choice.isdigit():
            option_number = int(menu_choice)
            if 1 < option_number < num_items:
                # account for unnumbered section headers if present:
                # return zero-based list index instead of 1-based menu numbering
                opt: MenuItem = selectable_items[option_number - 1]
                return opt
        print("Invalid choice. Please try again.")


def display_menu(menu_stack: list[Menu]) -> None:
    """ Displays the current menu from the menu stack. """
    current_menu = menu_stack[-1]  # Get the current menu (top of the stack)
    print_menu(current_menu)


def navigate_menu(menu_stack: list[Menu]) -> None:
    """
    Handles navigation through the current menu and its submenus.

    :param menu_stack: A stack tracking the current menu depth.
    """
    while menu_stack:
        logging.debug("%s" % menu_stack)
        # Display the current menu
        display_menu(menu_stack)

        # Get the user's choice
        current_menu = menu_stack[-1]  # Top of the stack
        # pass depth of stack so that the message about what Enter does is more accurate:
        choice = get_user_choice(current_menu, len(menu_stack))

        if choice is None:
            # Go back to the previous menu (pop current menu)
            menu_stack.pop()
            if not menu_stack:
                print("Exiting menu system.")
                return  # No more menus left
        elif choice.submenu:
            # Push the submenu onto the stack
            menu_stack.append(choice.submenu)
        # TODO: handle choice.edit_function is NotImplemented -- flag as not done yet
        elif callable(choice.edit_function):
            # Call the edit function for this menu item
            choice.edit_function(player)


def main():
    """Main function to handle menu interactions."""
    # menu setup - menus must be defined in reverse order because of submenu dependencies
    # (i.e., MainMenu references submenu SubMenu [which needs to be defined before MainMenu
    # in order to work properly])
    # to display flag status with a dot leader, currently setting
    # text=player.show_flag_line_item(PlayerFlags.ADMIN, None) does not work. Not sure why.
    # instead, use 'text="string"' and dot_leader_handler=<class.method>, as below.
    flags_and_counters = Menu("Flags & Counters", columns=1)
    flags_and_counters.add_item(MenuItem("Section Header"))
    flags_and_counters.add_item(MenuItem(PlayerFlags.ADMIN.value,
                                         dot_leader_handler=FlagsAndCounters.show_admin_flag,
                                         edit_function=FlagsAndCounters.edit_admin_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.ARCHITECT.value,
                                         dot_leader_handler=FlagsAndCounters.show_architect_flag,
                                         edit_function=FlagsAndCounters.edit_architect_flag))
    # can only enable Debug Mode if already Administrator or Dungeon Master:
    flags_and_counters.add_item(MenuItem(PlayerFlags.DEBUG_MODE.value,
                                         dot_leader_handler=FlagsAndCounters.show_debug_flag,
                                         edit_function=FlagsAndCounters.edit_debug_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.DUNGEON_MASTER.value,
                                         dot_leader_handler=FlagsAndCounters.show_dm_flag,
                                         edit_function=FlagsAndCounters.edit_dm_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.ORATOR.value,
                                         dot_leader_handler=FlagsAndCounters.show_orator_flag,
                                         edit_function=FlagsAndCounters.edit_orator_flag))
    """
    This simply returns and displays 'None':
    flags_and_counters.add_item(MenuItem("Debug Mode",
                                         dot_leader_handler=player.show_flag_line_item(PlayerFlags.DEBUG_MODE, None),
                                         edit_function=player.toggle_flag(PlayerFlags.DEBUG_MODE)
                                         ))
    """
    flags_and_counters.add_item(MenuItem("Guild Options"))
    flags_and_counters.add_item(MenuItem(PlayerFlags.GUILD_AUTODUEL.value,
                                         dot_leader_handler=FlagsAndCounters.show_autoduel_flag,
                                         edit_function=FlagsAndCounters.edit_autoduel_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.GUILD_FOLLOW_MODE.value,
                                         dot_leader_handler=FlagsAndCounters.show_guild_follow_flag,
                                         edit_function=FlagsAndCounters.edit_guild_follow_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.GUILD_MEMBER.value,
                                         dot_leader_handler=FlagsAndCounters.show_guild_member_flag,
                                         edit_function=FlagsAndCounters.edit_guild_member_flag))
    flags_and_counters.add_item(MenuItem("Horse options"))
    flags_and_counters.add_item(MenuItem(PlayerFlags.HAS_HORSE.value,
                                         dot_leader_handler=FlagsAndCounters.show_has_horse_flag,
                                         edit_function=FlagsAndCounters.edit_has_horse_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.MOUNTED.value,
                                         dot_leader_handler=FlagsAndCounters.show_mounted_flag,
                                         edit_function=FlagsAndCounters.edit_has_horse_flag))
    flags_and_counters.add_item(MenuItem("Option toggles"))
    flags_and_counters.add_item(MenuItem(PlayerFlags.EXPERT_MODE.value,
                                         dot_leader_handler=FlagsAndCounters.show_expert_flag,
                                         edit_function=FlagsAndCounters.edit_expert_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.HOURGLASS.value,
                                         dot_leader_handler=FlagsAndCounters.show_hourglass_flag,
                                         edit_function=FlagsAndCounters.edit_hourglass_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.MORE_PROMPT.value,
                                         dot_leader_handler=FlagsAndCounters.show_more_flag,
                                         edit_function=FlagsAndCounters.edit_more_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.ROOM_DESCRIPTIONS.value,
                                         dot_leader_handler=FlagsAndCounters.show_room_descs_flag,
                                         edit_function=FlagsAndCounters.edit_room_descs_flag))
    flags_and_counters.add_item(MenuItem("Health issues"))
    flags_and_counters.add_item(MenuItem(PlayerFlags.DISEASE.value,
                                         dot_leader_handler=FlagsAndCounters.show_disease_flag,
                                         edit_function=FlagsAndCounters.edit_disease_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.HUNGER.value,
                                         dot_leader_handler=FlagsAndCounters.show_hunger_flag,
                                         edit_function=FlagsAndCounters.edit_hunger_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.POISON.value,
                                         dot_leader_handler=FlagsAndCounters.show_poison_flag,
                                         edit_function=FlagsAndCounters.edit_poison_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.THIRST.value,
                                         dot_leader_handler=FlagsAndCounters.show_thirst_flag,
                                         edit_function=FlagsAndCounters.edit_thirst_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.TIRED.value,
                                         dot_leader_handler=FlagsAndCounters.show_tired_flag,
                                         edit_function=FlagsAndCounters.edit_tired_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.UNCONSCIOUS.value,
                                         dot_leader_handler=FlagsAndCounters.show_unconscious_flag,
                                         edit_function=FlagsAndCounters.edit_unconscious_flag))
    flags_and_counters.add_item(MenuItem("Game States"))
    flags_and_counters.add_item(MenuItem(PlayerFlags.AMULET_OF_LIFE_ENERGIZED.value,
                                         dot_leader_handler=FlagsAndCounters.show_amulet_energized_flag,
                                         edit_function=FlagsAndCounters.edit_amulet_energized_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.COMPASS_USED.value,
                                         dot_leader_handler=FlagsAndCounters.show_compass_used_flag,
                                         edit_function=FlagsAndCounters.edit_compass_used_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.DWARF_ALIVE.value,
                                         dot_leader_handler=FlagsAndCounters.show_dwarf_alive_flag,
                                         edit_function=FlagsAndCounters.edit_dwarf_alive_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.GAUNTLETS_WORN.value,
                                         dot_leader_handler=FlagsAndCounters.show_gauntlets_worn_flag,
                                         edit_function=FlagsAndCounters.edit_gauntlets_worn_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.RING_WORN.value,
                                         dot_leader_handler=FlagsAndCounters.show_ring_worn_flag,
                                         edit_function=FlagsAndCounters.edit_ring_worn_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.SPUR_ALIVE.value,
                                         dot_leader_handler=FlagsAndCounters.show_spur_alive_flag,
                                         edit_function=FlagsAndCounters.edit_spur_alive_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.THUG_ATTACK.value,
                                         dot_leader_handler=FlagsAndCounters.show_thug_flag,
                                         edit_function=FlagsAndCounters.edit_thug_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.WRAITH_KING_ALIVE.value,
                                         dot_leader_handler=FlagsAndCounters.show_wraith_king_alive_flag,
                                         edit_function=FlagsAndCounters.edit_wraith_king_alive_flag))
    flags_and_counters.add_item(MenuItem(PlayerFlags.WRAITH_MASTER.value,
                                         dot_leader_handler=FlagsAndCounters.show_wraith_master_flag,
                                         edit_function=FlagsAndCounters.edit_wraith_master_flag))

    name_menu = Menu("Character Names", columns=1)
    name_menu.add_item(MenuItem("Main Character", "m",
                                dot_leader_handler=CharacterNames.show_main_char_name,
                                edit_function=CharacterNames.edit_main_char_name))
    name_menu.add_item(MenuItem("Ally 1 Name", "1", NameMenu.show_ally_1_name, NameMenu.edit_ally_1_name))

    main_menu = Menu("Main Menu", columns=2)
    main_menu.add_item(MenuItem("Alignment", edit_function=NotImplemented))
    main_menu.add_item(MenuItem("Armor & Shield", edit_function=NotImplemented))
    main_menu.add_item(MenuItem("Attributes", edit_function=NotImplemented))
    main_menu.add_item(MenuItem("Character Names", submenu=name_menu))
    main_menu.add_item(MenuItem("Combinations", edit_function=NotImplemented))
    main_menu.add_item(MenuItem("Flags & Counters", submenu=flags_and_counters))
    main_menu.add_item(MenuItem("Hit Points", edit_function=NotImplemented))
    main_menu.add_item(MenuItem("Map Info", edit_function=NotImplemented))
    main_menu.add_item(MenuItem("Money", edit_function=NotImplemented))

    # Use a stack to track menu depth
    menu_stack: List[Menu] = [main_menu]
    navigate_menu(menu_stack)


if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')

    player = Player(name="Rulan")
    main()
