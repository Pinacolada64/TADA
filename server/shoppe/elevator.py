import logging
import asyncio
import sys
import traceback
from typing import Dict, List, Any, Optional, cast

from commands.base_command import CommandResult
import net_common as nc
Message = nc.Message
from_jsonb = nc.from_jsonb
MessageType = nc.MessageType
from menu_system import Menu, MenuItem, async_print_menu, async_get_user_choice
from simple_client import send_message
from tada_utilities import prompt_client
from player import Player, set_up_combinations
from commands.utils import get_player_from_context
from base_classes import CombinationTypes, Combination

def wrong_combination() -> Message:
    """Return a standard "wrong combination" message."""
    apostrophe = "'"
    return Message(lines=[f'The guard frowns. "That{apostrophe}s not the right combination."'])

async def get_combination(reader, writer, player: Player, *,
                          is_interactive: bool = False,
                          provided_ans: Optional[str] = None) -> bool:
    """
    Ask the player for the combination to use the elevator.

    :param reader: asyncio StreamReader for the client
    :param writer: asyncio StreamWriter for the client
    :param player: Player object representing the current player
    :param provided_ans: Optional non-interactive answer (string) to use instead of prompting
    :param is_interactive: If False, use provided_ans as combination instead of prompting user
    :return: True if the correct combination was provided, False otherwise
    """
    elevator_combo = player.combinations.get(CombinationTypes.ELEVATOR) if hasattr(player, 'combinations') else None
    logging.debug(f"get_combination: entered with elevator_combo={elevator_combo}, provided_ans={provided_ans}")

    if not hasattr(player, 'combinations'):
        player.combinations = set_up_combinations()
        logging.debug("get_combination: initialized player.combinations to empty dict")

    scrap_of_paper = player.combinations.get(CombinationTypes.ELEVATOR)
    if not scrap_of_paper:
        msg = f'The burly guard crosses his arms. "Sorry, I can\'t let you use the elevator without a combination."'
        await send_message(writer, Message(lines=[msg]))
        return False

    if not is_interactive:
        try:
            entered_combination = Combination.from_string(provided_ans)
        except Exception:
            entered_combination = None
        if entered_combination and entered_combination.combination == scrap_of_paper.combination:
            return True
        await send_message(writer, wrong_combination())
        return False

    tries = 1
    max_tries = 5
    while tries <= max_tries:
        prompt_text = f"Enter your elevator combination [Attempt {tries} of {max_tries}]: "
        logging.debug(f"get_combination: sending prompt to client: {prompt_text}")
        ans = await prompt_client(reader=reader, writer=writer, player_obj=player, prompt_text=prompt_text)
        if not ans:
            msg = f'The guard frowns. "You\'re telling me you don\'t have a combination?"'
            await send_message(writer, Message(lines=[msg]))
            tries += 1
            continue
        try:
            entered_combination = Combination.from_string(ans)
            if entered_combination.combination == scrap_of_paper.combination:
                return True
        except Exception:
            pass
        await send_message(writer, wrong_combination())
        tries += 1

    await send_message(writer, Message(lines=["Out of attempts."]))
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

async def execute(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, context: Dict[str, Any], args: List[str]) -> CommandResult | None:
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
        # ensure context includes the player object
        if isinstance(context, dict):
            context['player'] = player
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
        # allow a provided combination via args[0] or context keys for non-interactive use
        provided = None
        try:
            if args and len(args) > 0 and args[0]:
                provided = args[0]
        except Exception:
            provided = None
        if provided is None and context and isinstance(context, dict):
            provided = context.get('elevator_combination') or context.get('combination')

        # If no provided combination was given, run interactive prompting; otherwise use non-interactive check
        if provided is None:
            ok = await get_combination(reader, writer, player, is_interactive=True)
        else:
            ok = await get_combination(reader, writer, player, provided_ans=provided)
        if not ok:
            return CommandResult(success=False, error='no_combination', message='Could not retrieve elevator combination')

        else:
            # helper to send the elevator motion text (user-requested)
            async def send_elevator_motion(target_level: int):
                 current = getattr(player, 'map_level', 1)
                 if target_level < 1 or target_level > len(level_names):
                     msg_text = level_out_of_range_message(target_level)
                     await send_message(writer, Message(lines=msg_text))
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

                 # Keep client-level state in sync if a client is present in context
                 try:
                     if isinstance(context, dict):
                         client_obj = context.get('client') or getattr(player, 'client', None)
                         if client_obj is not None:
                             try:
                                 client_obj.map_level = target_level
                             except Exception:
                                 try:
                                     setattr(client_obj, 'map_level', target_level)
                                 except Exception:
                                     pass
                 except Exception:
                     pass

                 await send_message(writer, Message(lines=motion, prompt=''))

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

            # If args include a target level number, use it directly (non-interactive)
            target_level = None
            try:
                if args and len(args) > 0 and args[0]:
                    # if provided combination was present earlier, args[0] would be combination; check second arg
                    if len(args) > 1:
                        target_level = int(args[1])
            except Exception:
                target_level = None

            if target_level is not None:
                await send_elevator_motion(target_level)
            else:
                # Build interactive levels menu
                lvl_menu = Menu(title='Elevator Levels', columns=1)
                for idx, name in enumerate(level_names, start=1):
                    def make_level_action(n):
                        async def action():
                            await send_elevator_motion(n)
                        return action
                    lvl_menu.add_item(MenuItem(text=f"{idx}. {name}", shortcuts=str(idx), action=make_level_action(idx)))
                # add quit option
                lvl_menu.add_item(MenuItem(text='Cancel', shortcuts='X', action=None))

                # client-like object for menu helpers
                client_like = type('ClientLike', (), {})()
                client_like.writer = writer
                client_like.reader = reader
                client_like.return_key = 'Enter'
                client_like.client_settings = getattr(context.get('client'), 'client_settings', {'screen_columns':80}) if isinstance(context, dict) and context.get('client') else {'screen_columns':80}
                client_like.player = player

                # display menu and get choice
                await async_print_menu(client_like, lvl_menu)
                choice = await async_get_user_choice(client_like, lvl_menu, 1)
                if choice and choice.action:
                    act = choice.action
                    if asyncio.iscoroutinefunction(act):
                        await act()
                    else:
                        maybe = act()
                        if asyncio.iscoroutine(maybe):
                            await maybe

    except Exception as exc:
        # Extract the most relevant traceback frame to get filename and lineno
        tb = sys.exc_info()[2]
        try:
            last = traceback.extract_tb(tb)[-1]
            filename = last.filename
            lineno = last.lineno
        except Exception:
            filename = '<unknown>'
            lineno = 0
        logging.error("Elevator.execute failed at %s:%d - %s", filename, lineno, exc, exc_info=True)
        return CommandResult(success=False, error='execution_error', message=f'Failed to execute elevator command (at {filename}:{lineno})')

    # Completed elevator interaction
    return CommandResult(success=True, message='Elevator interaction complete')
