#!/bin/env python3
"""
menu_system.py

Hierarchical menu system for TADA.
All functions accept a GameContext (or TerminalContext) as their first
argument, so the same menu code works both locally and over the network.

Typical usage:
    from menu_system import Menu, MenuItem, run_menu

    main_menu = Menu(title='Main Menu')
    main_menu.add_item(MenuItem(text='Edit monsters', shortcuts=['E'],
                                action=some_async_fn))
    main_menu.add_item(MenuItem(text='Quit',          shortcuts=['Q']))

    await run_menu(ctx, [main_menu])
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, List, Optional, Union

if TYPE_CHECKING:
    from context import GameContext


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MenuItem:
    """
    One entry in a Menu.

    Attributes:
        text:               Visible label, or a callable that returns one.
        shortcuts:          One or more mnemonic letters (e.g. ['E', 'e']).
        dot_leader_handler: Optional callable returning a right-aligned value
                            displayed after a dot leader, e.g. a current setting.
        submenu:            A nested Menu opened when this item is chosen.
        action:             Async (or sync) callable executed when chosen.
                            Receives ctx as its only argument.
    """
    text:               Union[str, Callable]      = ''
    shortcuts:          Union[str, List[str]]      = field(default_factory=list)
    dot_leader_handler: Optional[Callable]         = None
    submenu:            Optional['Menu']           = None
    action:             Optional[Callable]         = None

    def __post_init__(self):
        if not self.shortcuts:
            self.shortcuts = []
        elif isinstance(self.shortcuts, str):
            self.shortcuts = [self.shortcuts]

    @property
    def is_header(self) -> bool:
        """True if this item is a section header (no action or submenu)."""
        return bool(self.text) and not self.action and not self.submenu


@dataclass
class Menu:
    """
    A titled list of MenuItems.

    Attributes:
        title:      Displayed at the top of the menu.
        columns:    1 (default) or 2 for a two-column layout.
        menu_items: Ordered list of MenuItem objects.
    """
    title:      str            = ''
    columns:    int            = 1
    menu_items: List[MenuItem] = field(default_factory=list)

    def add_item(self, item: MenuItem) -> None:
        self.menu_items.append(item)

    @property
    def selectable(self) -> List[MenuItem]:
        """Items that can be selected (not headers)."""
        return [i for i in self.menu_items if not i.is_header]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_menu_lines(ctx: 'GameContext', menu: 'Menu') -> List[str]:
    """
    Return a list of formatted strings representing the menu.
    Screen width is read from ctx.player.client_settings.screen_columns.
    """
    try:
        screen_columns = ctx.player.client_settings.screen_columns
    except AttributeError:
        screen_columns = 80

    _H = {'single': '─', 'double': '═'}
    try:
        h_char = _H.get(ctx.player.client_settings.border_style, '-')
    except AttributeError:
        h_char = '-'
    rule = h_char * screen_columns

    # --- Pass 1: build base strings and evaluate all dot leaders ---
    selectable_count = 0
    item_rows = []  # (item, base | None, dot_text | None)

    for item in menu.menu_items:
        if item.is_header:
            item_rows.append((item, None, None))
            continue

        selectable_count += 1
        shortcuts = f"[{','.join(item.shortcuts)}]" if item.shortcuts else ''
        label     = item.text() if callable(item.text) else str(item.text)
        base      = f'{selectable_count:2d}. {shortcuts:8} {label}'

        dot_text = None
        if item.dot_leader_handler is not None:
            try:
                val = (item.dot_leader_handler(ctx)
                       if callable(item.dot_leader_handler) else item.dot_leader_handler)
                if val is not None:
                    dot_text = str(val)
            except Exception:
                pass

        item_rows.append((item, base, dot_text))

    # --- Compute uniform dot geometry across all items that have values ---
    # 3 = one space before dots + colon + one space after colon
    max_base  = max((len(b) for _, b, d in item_rows if b and d), default=0)
    max_val   = max((len(d) for _, b, d in item_rows if b and d), default=0)
    dot_width = max(0, screen_columns - max_base - max_val - 3)

    # --- Pass 2: render ---
    lines: List[str] = ['', f'[{menu.title}]', rule]

    for item, base, dot_text in item_rows:
        if item.is_header:
            lines.append(str(item.text))
            continue

        if dot_text:
            item_dots = max_base + dot_width - len(base)
            if item_dots > 0:
                lines.append(f'{base} {"." * item_dots}: {dot_text}')
            else:
                lines.append(f'{base}: {dot_text}'[:screen_columns])
        else:
            lines.append(base)

    lines.append(rule)

    if menu.columns == 2:
        mid       = (len(lines) + 1) // 2
        col_width = max(20, screen_columns // 2)
        return [
            (lines[i] if i < len(lines) else '').ljust(col_width) +
            (lines[i + mid] if (i + mid) < len(lines) else '').ljust(col_width)
            for i in range(mid)
        ]

    return [ln.rstrip() for ln in lines]


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

async def print_menu(ctx: 'GameContext', menu: 'Menu') -> None:
    """Format and send the menu to the player via ctx.send()."""
    await ctx.send(format_menu_lines(ctx, menu))


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

async def get_user_choice(ctx: 'GameContext',
                          menu: 'Menu',
                          stack_depth: int = 1) -> Optional[MenuItem]:
    """
    Prompt the player for a menu choice and return the selected MenuItem,
    or None if the player cancels (empty input).

    Accepts:
      - A number (1-based index into selectable items)
      - A shortcut letter (matched case-insensitively)
      - Empty input → returns None (go up / quit)
    """
    selectable = menu.selectable
    num_items  = len(selectable)
    try:
        return_key = ctx.player.client_settings.return_key
    except AttributeError:
        return_key = 'Enter'

    action = 'quit' if stack_depth == 1 else 'go up a level'
    preamble = (f'Enter a number (1-{num_items}), a shortcut letter, '
                f'or [{return_key}] to {action}.')

    raw = await ctx.prompt(prompt_text='Choice', preamble_lines=[preamble])
    if not raw:
        return None

    option = raw.strip().lower()

    # Numeric selection
    if option.isdigit():
        idx = int(option)
        if 1 <= idx <= num_items:
            return selectable[idx - 1]
        await ctx.send(f'Please enter a number between 1 and {num_items}.')
        return None

    # Shortcut matching (case-insensitive)
    for item in menu.menu_items:
        if any(option == s.lower() for s in item.shortcuts):
            return item

    await ctx.send(f"'{raw}' is not a valid choice.")
    return None


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

async def navigate_menu(ctx: 'GameContext',
                        menu_stack: List['Menu']) -> None:
    """
    Interactive async menu loop.
    Pushes submenus onto the stack; pops on empty input; exits when stack empty.
    """
    while menu_stack:
        current = menu_stack[-1]
        await print_menu(ctx, current)

        choice = await get_user_choice(ctx, current, stack_depth=len(menu_stack))

        if choice is None:
            menu_stack.pop()
            if not menu_stack:
                await ctx.send('Exiting menu.')
            continue

        if choice.submenu:
            menu_stack.append(choice.submenu)
            continue

        if choice.action:
            try:
                result = choice.action(ctx)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logging.exception("Menu action '%s' raised an exception", choice.text)
            continue

        # Item has neither submenu nor action — treat as cancel/back
        menu_stack.pop()


async def run_menu(ctx: 'GameContext',
                   menu_hierarchy: Union['Menu', List['Menu']]) -> None:
    """
    Entry point for running a menu hierarchy.

    :param ctx:            GameContext or TerminalContext
    :param menu_hierarchy: A single Menu or a list of Menus (stack order,
                           first item is shown first).
    """
    if isinstance(menu_hierarchy, Menu):
        stack = [menu_hierarchy]
    else:
        stack = list(menu_hierarchy)

    if not stack:
        return

    await navigate_menu(ctx, stack)
