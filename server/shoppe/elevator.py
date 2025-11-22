import logging
import asyncio
from typing import Dict, List, Any, Optional, cast

from commands.base_command import CommandResult
from net_common import Message, to_jsonb, MessageType
from menu_system import Menu, MenuItem, async_print_menu, async_get_user_choice
from simple_client import send_message
from tada_utilities import prompt_client
from player import Player
from commands.utils import get_player_from_context

async def get_combination(reader, writer, context, player: Player) -> bool:
    """
    Ask the player for the combination to use the elevator.
    """
    # Debug: notify server log and client that get_combination was entered
    logging.debug('get_combination: entered')
    try:
        writer.write(to_jsonb(Message(lines=["DEBUG: get_combination entered"], prompt='')) + b"\n")
        await writer.drain()
    except Exception:
        # best-effort debug send; continue
        logging.debug('get_combination: could not send debug message to client')
    # also send a SYSTEM message to force client to display
    try:
        writer.write(to_jsonb(Message(lines=["DEBUG-SYSTEM: get_combination entered"], type=MessageType.SYSTEM)) + b"\n")
        await writer.drain()
    except Exception:
        pass

    # ensure player has a combinations mapping
    if not hasattr(player, 'combinations') or player.combinations is None:
        try:
            player.combinations = {}
        except Exception:
            # can't set combinations; fail safe
            player.combinations = {}

    # get combination from player data
    # FIXME: in final revision, player instantiation won't set a random combination, but will require finding the
    #  randomly placed SCRAP OF PAPER in-game
    scrap_of_paper = player.combinations.get(CombinationTypes.ELEVATOR)
    logging.debug("Elevator combination set to %s", scrap_of_paper)

    # If there's no combination, refuse entry
    if not scrap_of_paper:
        apostrophe = "'"
        msg = (f'The burly guard crosses his arms. "Sorry, I can{apostrophe}t let you use the elevator without '
              'a combination."')
        await send_message(writer, Message(lines=[msg]))
        return False

    # Prompt the player up to max_tries times. Use await on prompt_client.
    tries = 1
    max_tries = 5
    apostrophe = "'"
    while tries <= max_tries:
        prompt_text = f"Enter your elevator combination [Attempt {tries} of {max_tries}]: "
        ans = await prompt_client(reader=reader, writer=writer, player_obj=player, prompt_text=prompt_text)
        if not ans:
            # empty input or client disconnected
            msg = f'The guard frowns. "You{apostrophe}re telling me you don{apostrophe}t have a combination?"'
            await send_message(writer, Message(lines=[msg]))
            continue
        try:
            entered_combination = Combination.from_string(ans)
        except Exception:
            tries += 1
            msg = f'The guard frowns. "You{apostrophe}re telling me you don{apostrophe}t have a combination?"'
            await send_message(writer, Message(lines=[msg]))
            continue

        if entered_combination != scrap_of_paper:
            tries += 1
            msg = f'The guard frowns. "That{apostrophe}s not the right combination."'
            await send_message(writer, Message(lines=[msg], prompt=''))
            continue

        # correct
        return True

    # out of attempts
    return False


def level_out_of_range_message(level: int) -> str:
    """Generate a message for when the requested level is out of range."""

    def out_of_range(obstacle: str) -> str:
        apostrophe = "'"
        return (f'The guard looks alarmed. "Not on your life, we{apostrophe}d go straight through the {obstacle}!" '
                f'He pauses for a moment, scratching his chin. "That [would] be kind of fun, but I don{apostrophe}t '
                f'think my boss would be very happy with me."')

    if level < 1:
        return out_of_range("basement")
    else:
        return out_of_range("roof")

async def execute(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, context: Dict[str, Any], args: List[str]) -> CommandResult:
    logging.info("Executing ElevatorCommand with args=%s", args)

    # Determine player from context if available, otherwise create a lightweight fallback
    player: Optional[Player] = None
    # prefer the context-provided Player, fallback to client attribute
    player = get_player_from_context(context, None)
    if player is None and context and isinstance(context, dict):
        # older callers may pass a 'player' key in context; get_player_from_context handles that
        player = context.get('player')
    if player is None:
        try:
            player = Player()
        except Exception:
            class _MiniPlayer:
                def __init__(self):
                    self.map_level = 1
                    self.combinations = {}
            player = cast(Player, cast(object, _MiniPlayer()))

    level_names = [
        # 1:
        "The Land of the Enchanted",
        # 2:
        "Dark Side",
        # 3:
        "The Shadowed Land",
        # 4:
        "Maze of Alleyways",
        # 5:
        "Land of the Wraiths",
        # 6:
        "A Brave New World",
        # 7:
        "The House",
    ]

    try:
        ok = await get_combination(reader, writer, context, player)
        if not ok:
            return CommandResult(success=False, error='no_combination', message='Could not retrieve elevator combination')

        # helper to send the elevator motion text (user-requested)
        async def send_elevator_motion(target_level: int):
            current = getattr(player, 'map_level', 1)
            if target_level < 1 or target_level > len(level_names):
                msg_text = level_out_of_range_message(target_level)
                await send_message(writer, Message(lines=[msg_text]))
                return

            # choose direction
            direction = 'upwards' if target_level > current else 'downwards' if target_level < current else 'nowhere'
            level_name = level_names[target_level - 1]
            motion = (f'The guard closes the doors, throws a lever, and the elevator creaks {direction} towards {level_name}. '
                      f'Once there, he opens the doors again.')

            # update player's current level
            try:
                setattr(player, 'map_level', target_level)
            except Exception:
                # ignore if player object doesn't support attribute assignment
                pass

            await send_message(writer, Message(lines=[motion], prompt=''))

        # simple action handlers for menu items
        async def list_levels():
            lines = ["Available levels:"] + [f" {i+1}. {name}" for i, name in enumerate(level_names)]
            await send_message(writer, Message(lines=lines, prompt=''))

        async def go_up_level():
            current = getattr(player, 'map_level', 1) or 1
            target = min(current + 1, len(level_names))
            await send_elevator_motion(target)

        async def go_down_level():
            current = getattr(player, 'map_level', 1) or 1
            target = max(current - 1, 1)
            await send_elevator_motion(target)

        # generate go_to_level_N handlers dynamically
        async def make_go_to(level_index: int):
            async def _inner():
                await send_elevator_motion(level_index)
            return _inner

        go_to_level_1 = await make_go_to(1)
        go_to_level_2 = await make_go_to(2)
        go_to_level_3 = await make_go_to(3)
        go_to_level_4 = await make_go_to(4)
        go_to_level_5 = await make_go_to(5)
        go_to_level_6 = await make_go_to(6)
        go_to_level_7 = await make_go_to(7)

        # Build a simple elevator menu using the menu_system Menu and MenuItem
        shoppe_menu = Menu(title="Elevator", columns=1)

        # Add MenuItem objects. Note: Menu.add_item expects MenuItem instances.
        shoppe_menu.add_item(MenuItem(text="List levels", shortcuts="l", action=list_levels))
        shoppe_menu.add_item(MenuItem(text="Go up a level", shortcuts="u", action=go_up_level))
        shoppe_menu.add_item(MenuItem(text="Go down a level", shortcuts="d", action=go_down_level))
        shoppe_menu.add_item(MenuItem(text=level_names[0], shortcuts="1", action=go_to_level_1))
        shoppe_menu.add_item(MenuItem(text=level_names[1], shortcuts="2", action=go_to_level_2))
        shoppe_menu.add_item(MenuItem(text=level_names[2], shortcuts="3", action=go_to_level_3))
        shoppe_menu.add_item(MenuItem(text=level_names[3], shortcuts="4", action=go_to_level_4))
        shoppe_menu.add_item(MenuItem(text=level_names[4], shortcuts="5", action=go_to_level_5))
        shoppe_menu.add_item(MenuItem(text=level_names[5], shortcuts="6", action=go_to_level_6))
        shoppe_menu.add_item(MenuItem(text=level_names[6], shortcuts="7", action=go_to_level_7))
        shoppe_menu.add_item(MenuItem(text="Exit Elevator", shortcuts="X", action=None))

        # Use the same client_like object construction as shoppe/main.py
        client_like = type('ClientLike', (), {})()
        client_like.writer = writer
        client_like.reader = reader
        client_like.return_key = 'Enter'
        client_like.client_settings = {'screen_columns': 80}

        while True:
            # show menu
            await async_print_menu(client_like, shoppe_menu)
            chosen = await async_get_user_choice(client_like, shoppe_menu, stack_depth=1)
            if chosen is None:
                result_msg = Message(lines=["You leave the elevator."], prompt='')
                await send_message(writer, result_msg)
                break
            else:
                action = chosen.action
                if asyncio.iscoroutinefunction(action):
                    await action()
                elif callable(action):
                    maybe = action()
                    if asyncio.iscoroutine(maybe):
                        await maybe

        return CommandResult(success=True, message="Command executed successfully.")

    except Exception:
        logging.exception("Failed to write to client")
        return CommandResult(success=False, error='execution_error', message='Failed to execute elevator command')


class ElevatorHelp:
    """Help text for the Shoppe command."""

    def __init__(self):
        self.category = "Movement"
        self.summary = "The elevator [...]"
        self.description = "Command description for the elevator command."
        self.usage = "elevator [<parameter>]"
