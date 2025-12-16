# filepath: /home/ryan/Documents/c64/TADA/TADA/server/menu_system.py
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Union, Any
import asyncio

# Bring in Player for type annotations and for callers that pass Player objects
from player import Player
import net_common as nc
# Rebind commonly used symbols to preserve existing names
Message = nc.Message
to_jsonb = nc.to_jsonb
from simple_client import send_message, receive_message


# --- Menu data structures --------------------------------------------------
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
        text: Visible text for the item (or header)
        shortcuts: list or single shortcut letter (e.g. 'E' or ['E','e'])
        dot_leader_handler: optional callable to generate a dot-leader value
        submenu: nested Menu when selecting this opens a submenu
        action: callable executed when this item is chosen
    """
    text: Union[str, Callable] = ""
    shortcuts: Union[str, List[str]] = field(default_factory=list)
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
            self.shortcuts = [self.shortcuts]


@dataclass
class Menu:
    """Base class for menu systems with shared behavior.

    :param title: The title of the menu.
    :param columns: The number of columns to display the menu items in: 1 | 2.
    :param menu_items: The list of MenuItem objects to display.
    """
    title: str
    columns: int = 1
    menu_items: List[MenuItem] = field(default_factory=list)

    def add_item(self, item: MenuItem):
        """Adds a MenuItem to the menu.

        :param item: MenuItem to add.
        """
        self.menu_items.append(item)


# --- Formatting helpers ---------------------------------------------------
def format_menu_lines(menu: Menu, columns: int = 1, screen_columns: int = 80, player: Optional[Player] = None) -> List[
    str]:
    """Return a list of formatted lines representing the menu.

    Keeps formatting in one place so sync and async flows match.
    """
    lines: List[str] = ["", f"[{menu.title}]", "-" * 40]

    selectable_count = 0
    for item in menu.menu_items:
        # If an item has no action/submenu but has text, treat it as a header
        if item.submenu is None and item.action is None and item.text:
            lines.append(str(item.text))
            continue
        selectable_count += 1
        shortcuts = f"[{','.join(item.shortcuts)}]" if item.shortcuts else ""
        base = f"{selectable_count:2d}. {shortcuts:8} {item.text}"
        # If a dot_leader_handler is provided, call it and render a dot leader to the right
        dot_text = None
        try:
            if item.dot_leader_handler is not None:
                if callable(item.dot_leader_handler):
                    # Prefer calling handler with player if it accepts a parameter; fallback to no-arg call
                    try:
                        dot_val = item.dot_leader_handler(player)
                    except TypeError:
                        # handler likely takes no arguments
                        dot_val = item.dot_leader_handler()
                else:
                    dot_val = item.dot_leader_handler
                if dot_val is not None:
                    dot_text = str(dot_val)
        except Exception:
            # don't let a handler error break menu rendering
            dot_text = None

        if dot_text:
            # compute available space for dots between base and dot_text
            available = max(2, screen_columns - len(base) - len(dot_text) - 2)
            dots = '.' * available
            lines.append(f"{base} {dots} {dot_text}")
        else:
            lines.append(base)

    lines.append("-" * 40)

    # Two-column layout (basic implementation)
    if columns == 2:
        mid = (len(lines) + 1) // 2
        col_width = max(20, screen_columns // 2)
        col_lines = []
        for i in range(mid):
            a = lines[i] if i < len(lines) else ""
            b = lines[i + mid] if (i + mid) < len(lines) else ""
            col_lines.append(a.ljust(col_width) + b.ljust(col_width))
        return col_lines

    return [ln.rstrip() for ln in lines]


def is_header_item(menu_item: 'MenuItem') -> bool:
    """A helper to determine if an item is just a text header."""
    # A header is defined as an item with text but no action or submenu.
    return bool(menu_item.text) and not menu_item.action and not menu_item.submenu


# --- Synchronous server-side helpers --------------------------------------
def print_menu(player_handler: Any, player: Player, menu: Menu) -> None:
    """Print the menu to a server-side player handler.

    player_handler must provide output(lines, player) and flush_output().
    Falls back to local printing if handler isn't available.
    """
    screen_columns = 80
    try:
        cs = getattr(player, 'client_settings', None)
        if isinstance(cs, dict):
            screen_columns = cs.get('screen_columns', 80)
        elif hasattr(cs, 'screen_columns'):
            screen_columns = getattr(cs, 'screen_columns', 80)
    except Exception:
        screen_columns = 80

    lines = format_menu_lines(menu, columns=menu.columns, screen_columns=screen_columns, player=player)

    try:
        player_handler.output(lines, player)
        try:
            player_handler.flush_output()
        except Exception:
            pass
    except Exception:
        for l in lines:
            print(l)


def get_user_choice(player_handler: Any, player: Player, menu: Menu, stack_depth: int) -> Optional[MenuItem]:
    """Prompt the server-side player handler for a choice and return the MenuItem."""
    num_items = len([i for i in menu.menu_items if not (i.submenu is None and i.action is None and i.text)])
    enter_key = getattr(player, 'return_key', 'Enter')
    enter_action = 'quit' if stack_depth == 1 else 'go up a level'
    prompt_lines = f"Type the option number (1-{num_items}) or letters (shortcuts) to select an option, or [{enter_key}] to {enter_action}."

    try:
        choice = player_handler.prompt_request(prompt_lines, prompt='Choice: ')
    except Exception:
        try:
            text = input('Choice: ')
            choice = {'text': text}
        except Exception:
            return None

    if choice is None or choice.get('text') is None:
        return None

    option = str(choice.get('text')).strip().lower()
    if not option:
        return None

    if option.isnumeric():
        idx = int(option)
        selectable = [itm for itm in menu.menu_items if not (itm.submenu is None and itm.action is None and itm.text)]
        if 1 <= idx <= len(selectable):
            return selectable[idx - 1]
        return None

    for itm in menu.menu_items:
        if any(option == s.lower() for s in itm.shortcuts):
            return itm
    return None


# --- Async client-side helpers (used by shoppe/main) ----------------------
async def async_print_menu(client: Any, menu: Menu) -> None:
    """Asynchronously send a menu to a connected client using client.writer."""
    screen_columns = 80
    try:
        cs = getattr(client, 'client_settings', None)
        if isinstance(cs, dict):
            screen_columns = cs.get('screen_columns', 80)
        elif hasattr(cs, 'screen_columns'):
            screen_columns = getattr(cs, 'screen_columns', 80)
    except Exception:
        screen_columns = 80

    # try to acquire a player object from client (may be None)
    p = getattr(client, 'player', None)
    lines = format_menu_lines(menu, columns=menu.columns, screen_columns=screen_columns, player=p)

    writer = getattr(client, 'writer', None)
    if writer is None:
        return
    msg = Message(lines=lines, prompt='Choice: ')
    try:
        writer.write(to_jsonb(msg) + b"\n")
        await writer.drain()
    except Exception:
        return


async def async_get_user_choice(*args, **kwargs) -> Optional[MenuItem]:
    """Prompt the remote client for a choice and return the selected MenuItem.

    This function accepts two calling styles used in the codebase:
      1) async_get_user_choice(reader, writer, client, menu, stack_depth)
      2) async_get_user_choice(client, menu, stack_depth)
    It also supports keyword arguments: reader=, writer=, client=, menu=, stack_depth=.

    Returns the selected MenuItem or None when the user cancels/goes up.
    """
    # Parse positional and keyword args flexibly.
    reader = kwargs.get('reader')
    writer = kwargs.get('writer')
    client = kwargs.get('client')
    menu = kwargs.get('menu')
    stack_depth = kwargs.get('stack_depth', 1)

    # If called as async_get_user_choice(client, menu, stack_depth)
    if not (reader or writer) and args:
        first = args[0]
        # If first arg looks like a client-like object (has writer/reader), use that style
        if hasattr(first, 'writer') or hasattr(first, 'reader'):
            client = first
            if len(args) > 1:
                menu = args[1]
            if len(args) > 2:
                stack_depth = args[2]
        else:
            # assume reader, writer, client, menu, stack_depth positional ordering
            if len(args) > 0:
                reader = args[0]
            if len(args) > 1:
                writer = args[1]
            if len(args) > 2:
                client = args[2]
            if len(args) > 3:
                menu = args[3]
            if len(args) > 4:
                stack_depth = args[4]

    # Basic validation
    if menu is None:
        return None

    if client is None:
        # try to derive client from writer if possible
        client = kwargs.get('client') or (None)

    # derive writer/reader from client object when available
    if (writer is None or reader is None) and client is not None:
        try:
            writer = getattr(client, 'writer', writer)
            reader = getattr(client, 'reader', reader)
        except Exception:
            pass

    if writer is None or reader is None or client is None:
        return None

    # count selectable items and build prompt
    num_items = len([item for item in menu.menu_items if not is_header_item(item)])
    enter_key = getattr(client, 'return_key', 'Enter')
    enter_function = "quit" if stack_depth == 1 else "go up a level"
    lines = (f"Type the option number (1-{num_items}) or letters (shortcuts) to select an option, "
             f"or [{enter_key}] to {enter_function}.")

    # ensure lines is a list so clients iterate over entries, not characters
    msg = Message(lines=[lines], prompt='Choice: ')
    try:
        await send_message(writer, msg)
        obj = await receive_message(reader)
        option = ''
        if isinstance(obj, dict) and 'lines' in obj and obj['lines']:
            option = str(obj['lines'][0]).strip().lower()
        elif isinstance(obj, dict) and 'text' in obj:
            option = str(obj['text']).strip().lower()
        if not option:
            return None
    except Exception:
        return None

    if option.isnumeric():
        idx = int(option)
        selectable = [itm for itm in menu.menu_items if not (itm.submenu is None and itm.action is None and itm.text)]
        if 1 <= idx <= len(selectable):
            return selectable[idx - 1]
        return None

    for itm in menu.menu_items:
        # shortcuts may be a list
        try:
            shortcuts = itm.shortcuts or []
            for s in shortcuts:
                if option == str(s).lower():
                    return itm
        except Exception:
            pass
    return None


# --- High-level navigation helpers ----------------------------------------
def display_menu(player_handler: Any, player: Player, menu_stack: List[Menu]) -> None:
    """Display the current menu (top of the stack) synchronously."""
    if not menu_stack:
        return
    current = menu_stack[-1]
    print_menu(player_handler, player, current)


def navigate_menu(player_handler: Any, player: Player, menu_stack: List[Menu]) -> None:
    """Interactive synchronous menu loop for server-side handlers."""
    while menu_stack:
        display_menu(player_handler, player, menu_stack)
        current = menu_stack[-1]
        choice = get_user_choice(player_handler, player, current, len(menu_stack))
        if choice is None:
            menu_stack.pop()
            if not menu_stack:
                try:
                    player_handler.output(["Exiting menu system."], player)
                except Exception:
                    pass
                try:
                    player_handler.flush_output()
                except Exception:
                    pass
                return
            continue
        if choice.submenu:
            menu_stack.append(choice.submenu)
            continue
        if callable(choice.action):
            try:
                res = choice.action()
                if asyncio.iscoroutine(res):
                    asyncio.run(res)
            except Exception:
                logging.exception('Menu action failed')
            try:
                player_handler.flush_output()
            except Exception:
                pass
            continue


def run_menu(player: Player, player_handler: Any, menu_hierarchy: List[Menu]) -> None:
    """Entry point for running a synchronous menu for a player."""
    if player_handler is None:
        class _Minimal:
            def __init__(self, player_obj: Player):
                self._player = player_obj

            def output(self, lines, player_obj=None):
                try:
                    self._player.output(lines)
                except Exception:
                    if isinstance(lines, (list, tuple)):
                        for l in lines:
                            print(l)
                    else:
                        print(lines)

            def prompt_request(self, prompt_lines, prompt: str = '', choices=None):
                for l in (prompt_lines or []):
                    print(l)
                try:
                    text = input(prompt)
                except Exception:
                    text = ''
                return {'text': text}

        player_handler = _Minimal(player)

    if not menu_hierarchy:
        return
    menu_stack = menu_hierarchy[:] if isinstance(menu_hierarchy, list) else [menu_hierarchy]
    navigate_menu(player_handler, player, menu_stack)
