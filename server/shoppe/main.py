import logging
import asyncio
from typing import Dict, List, Any

from commands.base_command import Command, CommandResult
from net_common import Message, to_jsonb, MessageType
from menu_system import Menu, MenuItem, async_print_menu, async_get_user_choice
from simple_client import send_message

import shoppe.elevator as elevator_module
from commands.utils import get_player_from_context


class ShoppeCommand(Command):
    """A command for the shoppe."""

    async def execute(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, context: Dict[str, Any], args: List[str]) -> CommandResult:
        logging.info("Executing ShoppeCommand with args=%s", args)
        try:
            try:
                # Build a simple shoppe menu using the menu_system Menu and MenuItem
                shoppe_menu = Menu(title="Shoppe", columns=1)

                # determine player from context (so nested handlers can use it)
                player = get_player_from_context(context, None)
                if player is None and context and isinstance(context, dict):
                    player = context.get('player')

                # Simple action handlers that will send a small response back to the client
                async def visit_wizard():
                    msg = Message(lines=["You visit the wizened wizard. He studies you carefully."], prompt='')
                    writer.write(to_jsonb(msg) + b"\n")
                    await writer.drain()

                async def bank():
                    # TODO: implement a queue where multiple people in line must wait their turn to be served
                    msg = Message(lines=["You approach the Bank of SPUR. They smile and take your gold."], prompt='')
                    writer.write(to_jsonb(msg) + b"\n")
                    await writer.drain()

                async def elevator():
                    msg = Message(lines=["A burly guard stands here, his arms crossed. He looks you up and down..."], prompt='')
                    # send message using server-style writer to avoid mixing helpers
                    await send_message(writer, msg)
                    # Debug: notify client we are about to call elevator.execute (SYSTEM so client displays immediately)
                    try:
                        pre = Message(lines=["DEBUG-SYSTEM: entering elevator.execute"], type=MessageType.SYSTEM)
                        writer.write(to_jsonb(pre) + b"\n")
                        await writer.drain()
                        await elevator_module.execute(self, reader, writer, context={'player': player}, args=[])
                        try:
                            post = Message(lines=["DEBUG-SYSTEM: elevator.execute returned"], type=MessageType.SYSTEM)
                            writer.write(to_jsonb(post) + b"\n")
                            await writer.drain()
                        except Exception:
                            pass
                    except Exception as e:
                        # Report the exception back to the client so we can see it
                        try:
                            err = Message(lines=[f"ERROR in elevator.execute: {e}"], type=MessageType.SYSTEM)
                            writer.write(to_jsonb(err) + b"\n")
                            await writer.drain()
                        except Exception:
                            logging.exception("Failed to report elevator exception to client")

                async def locker(reader=reader, writer=writer):
                    msg = Message(lines=["You open your locker and find it empty."], prompt='')
                    await send_message(writer, msg)

                # Add MenuItem objects. Note: Menu.add_item expects MenuItem instances.
                shoppe_menu.add_item(MenuItem(text="Ye Olde Bank of SPUR", shortcuts="B", action=bank))
                # Run the elevator handler directly (it will be awaited by the menu loop)
                shoppe_menu.add_item(MenuItem(text="Ride the Elevator", shortcuts="E", action=elevator))
                shoppe_menu.add_item(MenuItem(text="Locker", shortcuts="L", action=locker))
                shoppe_menu.add_item(MenuItem(text="Visit the Wizard", shortcuts="W", action=visit_wizard))
                shoppe_menu.add_item(MenuItem(text="Exit Shoppe", shortcuts="X", action=None))

                # Send the menu to the client and wait for a choice using the async helpers
                # We construct a small client-like object containing reader/writer for the helpers
                client_like = type('ClientLike', (), {})()
                client_like.writer = writer
                client_like.reader = reader
                client_like.return_key = 'Enter'
                client_like.client_settings = {'screen_columns': 80}

                while True:
                    # Use the async print function to present the menu
                    await async_print_menu(client_like, shoppe_menu)

                    # Get user choice
                    chosen = await async_get_user_choice(client_like, shoppe_menu, stack_depth=1)

                    if chosen is None:
                        # user backed out or invalid; nothing to do
                        result_msg = Message(lines=["You leave the shoppe."], prompt='')
                        writer.write(to_jsonb(result_msg) + b"\n")
                        await writer.drain()
                        break
                    else:
                        # if the action is an async callable, await it; if sync, call it
                        action = chosen.action
                        logging.info("Shoppe: invoking action %s", getattr(action, '__name__', repr(action)))
                        if asyncio.iscoroutinefunction(action):
                            await action()
                            logging.info("Shoppe: action %s completed", getattr(action, '__name__', repr(action)))
                        elif callable(action):
                            # wrap sync call in executor if it might block; here we assume small
                            maybe_result = action()
                            if asyncio.iscoroutine(maybe_result):
                                await maybe_result
                                logging.info("Shoppe: sync action %s completed coroutine", getattr(action, '__name__', repr(action)))

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
