import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Union

from flags import PlayerFlags
from player import Player


def edit_string(prompt: str, data: str) -> str:
    user_input = input(f"Edit {prompt}: ")
    if user_input in ['', data]:
        print(f"Keeping '{data}'.")
        return data
    else:
        print(f"Changing '{data}' to '{user_input}.'")
        return user_input


@dataclass
class MenuItem:
    """
    Represents a menu item in a hierarchical menu system.

    This class defines a menu item with text, an optional shortcut, an optional
    dot leader handler function, an optional submenu, and an optional edit function.
    It is designed to facilitate menu system configuration and interaction by
    providing pre-defined attributes and a method to display the menu item as a
    formatted string. The menu item can either lead to a submenu, execute a function,
    or display an edited output.

    Attributes:
        text (str): Text of the menu item.
        shortcuts (Optional[str | list]): Shortcut letters to type to select the item,
            in addition to the numeric item number.
        dot_leader_handler (Optional[Callable]): Function which displays the
            `line_item` value after the dot leader. If None, dot leaders
            and the function result are not shown.
        submenu (Optional[Menu]): Submenu to navigate to after the item is
            selected.
        action (Optional[Callable]): Function to edit the item if
            a submenu is not present.
    """
    # text of menu item:
    text: str | Callable = None
    # shortcut letters to type to select item (besides numeric item #):
    # Allow a single string OR a list of strings during creation
    shortcuts: Union[str, List[str]] = ""
    # function which displays line_item() value after dot leader:
    # if None, do not display a dot leader and the result of this function.
    dot_leader_handler: Optional[Callable] = None
    # submenu to go to after item selected:
    submenu: Optional['Menu'] = None
    # function to call when item selected (if submenu is None):
    action: Optional[Callable] = None

    def __post_init__(self):
        """
        Ensures the 'shortcuts' attribute is always a list, required
        for the check_shortcut_conflicts() function to work properly.
        """
        if not self.shortcuts:
            self.shortcuts = []
        elif isinstance(self.shortcuts, str):
            # If a single string was provided, convert it to a list
            self.shortcuts = [self.shortcuts]

    def line_item(self, width: int = 40):
        """
        Returns a formatted line item with optional dot leaders.

        This method generates a line item string, optionally formatted with
        dot leaders, based on the provided width and the presence of
        a dot leader handler. If text is provided and a custom
        dot leader handler function is defined, the formatted output
        will ensure alignment and use the handler as necessary.

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
        return None


@dataclass
class Menu:
    """Base class for menu systems with shared behavior."""
    title: str
    columns: int = 1
    menu_items: list[MenuItem] = field(default_factory=list)

    def add_item(self, item: MenuItem):
        self.menu_items.append(item)

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


def check_shortcut_conflicts(menu: 'Menu'):
    """
    Finds duplicate shortcuts, flags the item text, and disambiguate
    the shortcut by adding an incremental number.
    """
    logging.info("Checking for shortcut conflicts...")

    # 1. Get a flat list of all non-empty shortcuts
    all_shortcuts = [
        s.lower() for item in menu.menu_items for s in item.shortcuts if s
    ]

    # 2. Count occurrences to find which shortcuts are duplicates
    shortcut_counts = Counter(all_shortcuts)
    duplicates = {
        shortcut for shortcut, count in shortcut_counts.items() if count > 1
    }

    if not duplicates:
        return  # No conflicts found, nothing to do.

    logging.warning("Duplicate shortcuts found: %s" % " ".join(duplicates))

    # 3. Iterate through items to apply changes where needed
    disambiguation_counters = Counter()
    for item in menu.menu_items:
        # We need to modify the item's shortcut list in place
        new_shortcuts = []
        modified = False
        for shortcut in item.shortcuts:
            if shortcut.lower() in duplicates:
                modified = True
                disambiguation_counters.update([shortcut.lower()])
                count = disambiguation_counters[shortcut.lower()]
                new_shortcut = f"{shortcut}{count}"
                new_shortcuts.append(new_shortcut)
                logging.info("Updated '%s' to '%s'" % (shortcut, new_shortcut))
            else:
                new_shortcuts.append(shortcut)

        if modified:
            # Add the warning text only if it's not already there
            if "[duplicate shortcut]" not in item.text:
                item.text += " [duplicate shortcut]"
            item.shortcuts = new_shortcuts


def is_header_item(menu_item: 'MenuItem') -> bool:
    """A helper to determine if an item is just a text header."""
    # A header is defined as an item with text but no action or submenu.
    """
    In the example below, "Section Header," "Guild," and "Horse Options"
    are header items (and thus are not numbered, since they can't be selected):
    
    Flags & Counters
    --------------------
        Section Header
     1. Administrator.....................: No
     2. Architect.........................: No
     3. Debug Mode........................: On
     4. Dungeon Master....................: No
     5. Orator............................: No
        Guild
     6. Guild AutoDuel....................: Off
     7. Guild Follow Mode.................: Off
     8. Guild Member......................: No
        Horse Options
     9. Has Horse.........................: Yes
    [...]
    """
    return bool(menu_item.text) and not menu_item.action and not menu_item.submenu


def format_menu_item(menu_item: 'MenuItem', current_item_num: int, menu: 'Menu') -> (str, int):
    """
    Formats a single menu item into a string and returns the next item number.

    Args:
        menu_item: The MenuItem object to format.
        current_item_num: The number of the last real item that was printed.
        menu: The parent Menu object, used for column width context.

    Returns:
        A tuple containing the formatted string line and the updated item number.
    """
    """
    TODO: Don't tab over if no shortcuts in menu items:
    e.g.,
    1. No shortcut key
    2. No shortcut key

    vs.
    1. [i]  Item with shortcut
    2.      Item without shortcut
    """
    header = is_header_item(menu_item)
    next_item_num = current_item_num

    if header:
        # For headers, only return the text, indented.
        return f"    {menu_item.text}", next_item_num

    # For regular items, increment the number and format the line
    next_item_num += 1
    num_str = f"{next_item_num: >2}."

    # Format shortcuts, handling cases with none, one, or multiple
    if menu_item.shortcuts:
        shortcut_str = f'[{",".join(menu_item.shortcuts)}]'
    else:
        shortcut_str = ""

    # Combine all parts into the final display line
    # Note: Using menu_item.text instead of a .line_item() method
    display_text = f"{num_str} {shortcut_str:<10} {menu_item.text}"
    return display_text, next_item_num


def find_menu_item_by_shortcut(choice: str, items: list[MenuItem]) -> Optional[MenuItem]:
    """Helper function to find a menu item by its shortcut."""
    logging.info("choice: %s" % choice)
    # Convert the user's choice to lowercase once for efficiency.
    choice_lower = choice.lower()
    logging.info(f"Searching for choice: '{choice_lower}'")

    for item in items:
        # Create a new list of lowercase shortcuts for comparison.
        lowercase_shortcuts = [s.lower() for s in item.shortcuts]

        # Check if the user's lowercase choice is in the new lowercase list.
        if choice_lower in lowercase_shortcuts:
            logging.debug(f"Shortcut '{choice_lower}' found in item: {item.text}")
            return item
    return None


def find_menu_item_by_number(choice: int, menu: Menu) -> MenuItem | None:
    """
    Helper function to find a menu item by its option number.
    Since unnumbered section headers can be displayed, simply picking the index of a
    menu item won't work.

    :param choice: The 1-based number the user selected.
    :param menu: Menu object to iterate through to find correct choice

    :return: The index of the selected item, or None if not found.
    """
    option_count = 0  # This will count only the selectable (non-header) items.
    # this keeps track of how many header items were iterated over, adds it to option_count
    # to return the correct menu item:
    header_count = 0
    # Use enumerate to get both the index and the item at the same time.
    for index, item in enumerate(menu.menu_items, start=1):
        # Skip any item that is a header.
        if is_header_item(item):
            header_count += 1
            logging.debug("header: %i, item: %s" % (header_count, item.text))
            continue

        # If it's a regular item, increment our option counter.
        option_count += 1
        logging.debug("  item: %i, item: %s" % (option_count, item.text))

        # Check if this option number is the one the user chose.
        if option_count == choice:
            logging.debug(f"User choice '{choice}' matches option_count.")
            # We found it! Return the index (but add header_count to get correct index).
            return header_count + option_count

    # If the loop finishes, the user's choice was larger than the number of items.
    logging.warning(f"User choice '{choice}' is not a valid menu option.")
    return None

def print_menu(player: Player, menu: 'Menu'):
    """Prints the given menu with options, delegating formatting to a helper.
    :param player: Player object
    :param menu: menu object
    """
    player.output(["", f"[{menu.title}]", "", ("-" * 40 * menu.columns)])
    check_shortcut_conflicts(menu)

    # --- Pass 1: Generate all formatted lines ---
    all_lines = []
    item_number = 0
    for item in menu.menu_items:
        # The item_number is updated on each iteration
        formatted_line, item_number = format_menu_item(item, item_number, menu)
        all_lines.append(formatted_line)

    # --- Pass 2: Arrange the generated lines into columns ---
    if menu.columns == 2:
        midpoint = (len(all_lines) + 1) // 2
        for i in range(midpoint):
            col1 = all_lines[i]
            # Get the corresponding item for the second column, if it exists
            col2 = all_lines[i + midpoint] if (i + midpoint) < len(all_lines) else ""
            player.output(f"{col1:<40}{col2}")  # ljust provides consistent padding
    else:
        # For a single column, only print each line
        for line in all_lines:
            player.output(line)

    player.output("-" * 40 * menu.columns)


def get_user_choice(player: Player, menu: Menu, stack_depth: int) -> Optional[MenuItem]:
    """
    Gets the user's choice and returns either None, or the corresponding MenuItem object.

    :param player: Player object
    :param menu: A Menu object containing menu items.
    :param stack_depth: how many levels deep in the menu system we are
    :return: The selected MenuItem object, or None if the user chooses to go up a menu level/quit.
    """
    while True:
        if not player.query_flag(PlayerFlags.EXPERT_MODE):
            # count all non-header items in menu to give accurate item count:
            num_items = len([item for item in menu.menu_items if not is_header_item(item)])
            enter_function = "quit" if stack_depth == 1 else "go up a level"
            player.output(f"Type the number of an option (1-{num_items}) or letters (shortcuts) to select an option, "
                          f"or [Enter] to {enter_function}.")
        choice = input(f"Choice: ").strip().lower()

        if not choice:  # No input, user wants to go back.
            return None

        if choice.isalnum():  # combination of numbers and letters
            shortcut_item = find_menu_item_by_shortcut(choice, menu.menu_items)
            if shortcut_item:  # Found a match based on shortcut.
                logging.debug("Shortcut '%s' selected.", choice)
                return shortcut_item

        # Check if user entered a valid menu item number:
        if choice.isdigit():
            option_num = int(choice)
            if 1 <= option_num <= len(menu.menu_items):
                # account for unnumbered section headers if present:
                selected_num = find_menu_item_by_number(option_num, menu)
                return menu.menu_items[selected_num - 1]  # Correct index for user-friendly numbering.
        print("Invalid choice. Please try again.")


def display_menu(player: Player, menu_stack: list[Menu]) -> None:
    """ Displays the current menu from the menu stack.
    :param player:  Player object
    """
    current_menu = menu_stack[-1]  # Get the current menu (top of the stack)
    print_menu(player, current_menu)


def navigate_menu(player: Player, menu_stack: list[Menu]) -> None:
    """
    Handles navigation through the current menu and its submenus.

    :param player: Player object
    :param menu_stack: A stack tracking the current menu depth.
    """
    while menu_stack:
        logging.debug("%s" % menu_stack)
        # Display the current menu
        display_menu(player, menu_stack)

        # Get the user's choice
        current_menu = menu_stack[-1]  # Top of the stack
        # pass depth of stack so that the message about what Enter does is more accurate:
        # return 'choice', MenuItem to act upon:
        choice = get_user_choice(player, current_menu, len(menu_stack))

        if choice is None:
            # Go back to the previous menu (pop current menu)
            menu_stack.pop()
            if not menu_stack:
                print("Exiting menu system.")
                return  # No more menus left
        elif choice.submenu:
            # Push the submenu onto the stack
            menu_stack.append(choice.submenu)
        # TODO: handle choice.action is NotImplemented -- flag as not done yet
        elif callable(choice.action):
            # Call the edit function for this menu item
            choice.action(player)

        logging.debug("Unhandled edge case for %s" % choice.text)

if __name__ == '__main__':
    # set up logging
    log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')

    player = Player(name="Rulan")
