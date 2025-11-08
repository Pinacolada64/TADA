import logging
import asyncio
from typing import Dict, List, Any

from commands.base_command import Command, CommandResult
from net_common import Message, to_jsonb
from menu_system import Menu, MenuItem, async_print_menu, async_get_user_choice


class ShoppeCommand(Command):
    """A command for the shoppe."""

    async def execute(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, context: Dict[str, Any], args: List[str]) -> CommandResult:
        logging.info("Executing ShoppeCommand with args=%s", args)
        try:
            try:
                # Build a simple shoppe menu using the menu_system Menu and MenuItem
                shoppe_menu = Menu(title="Shoppe", columns=1)

                # Simple action handlers that will send a small response back to the client
                async def visit_wizard():
                    msg = Message(lines=["You visit the wizened wizard. He studies you carefully."], prompt='')
                    writer.write(to_jsonb(msg) + b"\n")
                    await writer.drain()

                async def bank():
                    msg = Message(lines=["You approach the Bank of SPUR. They smile and take your gold."], prompt='')
                    writer.write(to_jsonb(msg) + b"\n")
                    await writer.drain()

                async def elevator():
                    msg = Message(lines=["You step onto the elevator. It creaks but works."], prompt='')
                    writer.write(to_jsonb(msg) + b"\n")
                    await writer.drain()

                async def locker():
                    msg = Message(lines=["You open your locker and find it empty."], prompt='')
                    writer.write(to_jsonb(msg) + b"\n")
                    await writer.drain()

                # Add MenuItem objects. Note: Menu.add_item expects MenuItem instances.
                shoppe_menu.add_item(MenuItem(text="Visit the Wizard", shortcuts="W", action=visit_wizard))
                shoppe_menu.add_item(MenuItem(text="Ye Olde Bank of SPUR", shortcuts="B", action=bank))
                shoppe_menu.add_item(MenuItem(text="Ride the Elevator", shortcuts="E", action=elevator))
                shoppe_menu.add_item(MenuItem(text="Locker", shortcuts="L", action=locker))
                shoppe_menu.add_item(MenuItem(text="Exit Shoppe", shortcuts="X", action=None))

                # Send the menu to the client and wait for a choice using the async helpers
                # We construct a small client-like object containing reader/writer for the helpers
                client_like = type('ClientLike', (), {})()
                client_like.writer = writer
                client_like.reader = reader
                client_like.return_key = 'Enter'
                client_like.client_settings = {'screen_columns': 80}

                # Use the async print function to present the menu
                await async_print_menu(client_like, shoppe_menu)

                # Get user choice
                chosen = await async_get_user_choice(client_like, shoppe_menu, stack_depth=1)

                if chosen is None:
                    # user backed out or invalid; nothing to do
                    result_msg = Message(lines=["You leave the shoppe."], prompt='')
                    writer.write(to_jsonb(result_msg) + b"\n")
                    await writer.drain()
                else:
                    # if the action is an async callable, await it; if sync, call it
                    action = chosen.action
                    if asyncio.iscoroutinefunction(action):
                        await action()
                    elif callable(action):
                        # wrap sync call in executor if it might block; here we assume small
                        maybe_result = action()
                        if asyncio.iscoroutine(maybe_result):
                            await maybe_result

            except Exception:
                logging.exception("Failed to write to client")

            return CommandResult(success=True, message="Command executed successfully.")
        except Exception as e:
            logging.exception("Error executing ShoppeCommand")
            return CommandResult(success=False, error='execution_error', message=str(e))


class ShoppeHelpText:
    """Help text for the Shoppe command."""
    def __init__(self):
        self.category = "MISCELLANEOUS"
        self.summary = ("The shoppe allows you to buy and sell items, visit a wizard to learn spells, and many other things."
                        "A short summary of what the shoppe command is for.")
        self.description = "Command description for the shoppe command."
        self.usage = "shoppe [<parameter>]"
