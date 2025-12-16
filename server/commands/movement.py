# movement
import asyncio
import logging
from typing import List, cast

from commands.base_command import BaseCommand, CommandResult, HelpCategory
from commands.command_processor import command
from commands.help import BaseHelpText
from net_common import Message, MessageType, Mode
from player import Player
from commands.utils import get_player_from_context

# human-friendly direction text
compass_txts = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west', 'u': 'up', 'd': 'down'}


@command(name='move', aliases=['n', 's', 'e', 'w', 'u', 'd', 'north', 'south', 'east', 'west', 'up', 'down', 'go'],
         summary="Move in compass directions")
class MoveCommand(BaseCommand):
    """Move the player's character between rooms.

    The command accepts: 'n', 'north', 'go north', 'go n', etc.
    It expects `context` to contain a 'client' (the server-side client object)
    which has a reference to `server` (the Server instance) and a `room` attribute.
    """

    async def execute(self, context: dict, args: List[str]) -> CommandResult:
        # Resolve client and server/map
        client = None
        if isinstance(context, dict):
            client = context.get('client') or context.get('client')
        if client is None:
            return CommandResult(success=False, error='no_client', message='No client in command context')

        # Prefer server provided in the processor context (create_command_processor sets this),
        # but fall back to client.server if present.
        server = None
        try:
            if isinstance(context, dict):
                server = context.get('server') or None
        except Exception:
            server = None
        if server is None:
            server = getattr(client, 'server', None)
        if server is None:
            # If server is not available, provide a helpful instruction to the caller
            return CommandResult(success=False, error='no_server', message='Server not available in command context')

        # Determine direction token
        if not args:
            # Try to pick up the raw input from context (processor sets RAW_INPUT)
            token = None
            try:
                token = (context.get('raw_input') or '').strip().split()[0].lower()
            except Exception:
                token = None
            if not token:
                return CommandResult(success=False, error='no_direction', message='Usage: n|s|e|w|u|d or go <direction>')
        else:
            token = args[0].lower()

        if token in ('go', 'move') and len(args) > 1:
            token = args[1].lower()

        # Resolve player object from context (may be used by modules called below)
        try:
            player = get_player_from_context(context, client)
        except Exception:
            player = getattr(client, 'player', None)

        # normalize to single-letter directions where possible
        dir_map = {
            'north': 'n', 'n': 'n',
            'south': 's', 's': 's',
            'east': 'e', 'e': 'e',
            'west': 'w', 'w': 'w',
            'up': 'u', 'u': 'u',
            'down': 'd', 'd': 'd'
        }

        direction = dir_map.get(token)
        if not direction:
            return CommandResult(success=False, error='bad_direction', message=f'Unknown direction: {token}')

        # Current room number
        try:
            cur_room_no = int(getattr(client, 'room', 1) or 1)
        except Exception:
            return CommandResult(success=False, error='bad_room', message='Invalid current room')

        # Special-case: moving north from room 49 (to 37) should call the bar module
        if direction == 'n' and cur_room_no == 49:
            logging.info("Player in room 49 moving north: invoking bar module")
            try:
                import bar.main as bar_mod
            except Exception as e:
                logging.exception("Failed to import bar.main: %s", e)
                return CommandResult(success=False, error='bar_import', message=f'Failed to import bar module: {e}')

            original_room = cur_room_no
            # mark as in bar room temporarily (use server helper if present to sync Player too)
            try:
                if hasattr(server, '_sync_player_location'):
                    server._sync_player_location(client, 0)
                else:
                    client.room = 0
            except Exception:
                try:
                    client.room = 0
                except Exception:
                    pass

            # Adapter to capture bar output
            class _BarAdapter:
                def __init__(self):
                    self.buf = []
                    class CS:
                        screen_rows = 24
                        screen_columns = 80
                        translation = None
                    self.client_settings = CS()

                def output(self, text):
                    if isinstance(text, list):
                        for t in text:
                            self.buf.append(str(t))
                    else:
                        self.buf.append(str(text))

            adapter = _BarAdapter()
            try:
                if hasattr(bar_mod, 'bar_help'):
                    # bar_help expects a Player; adapter provides the minimal output()/client_settings interface
                    bar_mod.bar_help(cast(Player, adapter))
                elif hasattr(bar_mod, 'main'):
                    # try calling main with a Player-like object first, then fallback to no-arg call
                    try:
                        bar_mod.main(cast(Player, adapter))
                    except TypeError:
                        try:
                            bar_mod.main()
                        except Exception:
                            logging.debug('bar.main() failed or is interactive; no workable entrypoint found')
            except Exception:
                logging.exception('bar module call failed')
                client.room = original_room
                return CommandResult(success=False, error='bar_error', message='Bar module execution failed')

            # deliver adapter output via server helper if possible
            try:
                if hasattr(server, '_send_lines_to_client'):
                    server._send_lines_to_client(client, adapter.buf)
                    client.room = original_room
                    return CommandResult(success=True, message='Bar displayed', data={'room': original_room})
                else:
                    client.room = original_room
                    return CommandResult(success=True, message='\n'.join(adapter.buf), data={'room': original_room})
            except Exception:
                logging.exception('Failed to deliver bar output to client')
                client.room = original_room
                return CommandResult(success=False, error='bar_error', message='Failed to send bar output')

        game_map = getattr(server, 'game_map', None)
        if not game_map or cur_room_no not in game_map.rooms:
            return CommandResult(success=False, error='map_missing', message='Map not available')

        room = game_map.rooms[cur_room_no]

        # check exits
        exits = getattr(room, 'exits', {}) or {}

        # First, try explicit directional exits (n/e/s/w/u/d)
        dest_no = None
        if direction in exits and exits[direction]:
            dest = exits[direction]
            try:
                dest_no = int(dest)
            except Exception:
                return CommandResult(success=False, error='bad_exit', message='Invalid exit target')
        else:
            # No explicit directional exit. Check for rc/rt transports when moving up/down
            if direction in ('u', 'd'):
                try:
                    rc = int(exits.get('rc', 0) or 0)
                except Exception:
                    rc = 0
                try:
                    rt = int(exits.get('rt', 0) or 0)
                except Exception:
                    rt = 0

                # rc==1 means Up, rc==2 means Down
                if (rc == 1 and direction == 'u') or (rc == 2 and direction == 'd'):
                    # transport to Shoppe
                    if rt == 0:
                        logging.info("Attempting to import shoppe.main for Shoppe handling")
                        try:
                            import shoppe.main as shop_mod
                        except Exception as e:
                            logging.exception("Failed to import shoppe.main: %s", e)
                            return CommandResult(success=False, error='shoppe_error', message=f'Shoppe module import failed: {e}')

                        # Remember current room to return player later
                        original_room = cur_room_no
                        # Mark client and player as being in virtual shoppe room (optional)
                        try:
                            if hasattr(server, '_sync_player_location'):
                                server._sync_player_location(client, 0)
                            else:
                                client.room = 0
                                try:
                                    if player is not None:
                                        player.map_room = 0
                                except Exception:
                                    pass
                        except Exception:
                            try:
                                client.room = 0
                            except Exception:
                                pass

                        # If shop_mod provides a ShoppeCommand, use it for the interactive flow
                        if hasattr(shop_mod, 'ShoppeCommand'):
                            try:
                                shop_cmd = shop_mod.ShoppeCommand()
                                ctx = {'client': client, 'server': server}
                                result = shop_cmd.execute(getattr(client, 'reader', None), getattr(client, 'writer', None), ctx, [])
                                if asyncio.iscoroutine(result):
                                    result = await result
                            except Exception:
                                logging.exception('ShoppeCommand execution failed')
                                # restore room and return error
                                client.room = original_room
                                return CommandResult(success=False, error='shoppe_error', message='Shoppe interaction failed')

                        # fallback: older modules may export a bar_help function that writes to an adapter
                        elif hasattr(shop_mod, 'bar_help'):
                            class _BarAdapter:
                                def __init__(self):
                                    self.buf = []
                                    class CS:
                                        screen_rows = 24
                                        screen_columns = 80
                                        translation = None
                                    self.client_settings = CS()

                                def output(self, text):
                                    if isinstance(text, list):
                                        for t in text:
                                            self.buf.append(str(t))
                                    else:
                                        self.buf.append(str(text))

                            adapter = _BarAdapter()
                            try:
                                shop_mod.bar_help(adapter)
                            except Exception:
                                logging.exception('bar_help failed')
                                client.room = original_room
                                return CommandResult(success=False, error='shoppe_error', message='Shoppe bar_help failed')

                            # Send adapter output back to client via server API if available
                            try:
                                if hasattr(server, '_send_lines_to_client'):
                                    server._send_lines_to_client(client, adapter.buf)
                                else:
                                    # If server can't send lines, return them in the CommandResult so caller can forward them
                                    client.room = original_room
                                    return CommandResult(success=True, message='\n'.join(adapter.buf), data={'room': original_room})
                            except Exception:
                                logging.exception('Failed to deliver bar_help output to client')
                                client.room = original_room
                                return CommandResult(success=False, error='shoppe_error', message='Failed to send shoppe output')

                        else:
                            # shoppe module didn't provide expected interfaces
                            logging.error('shoppe.main has no ShoppeCommand or bar_help')
                            client.room = original_room
                            return CommandResult(success=False, error='shoppe_error', message='Shoppe module missing entry points')

                        # After shoppe interaction completes, restore player's room to the original map room
                        client.room = original_room
                        # Describe the room to the player again
                        try:
                            lines = server._describe_room(client)
                        except Exception:
                            logging.exception('Failed to describe room after leaving shoppe')
                            lines = ["You return to the map."]

                        # Return description to caller
                        return CommandResult(success=True, message=lines, data={'room': original_room})
                else:
                    return CommandResult(success=False, error='no_exit', message='You cannot go that way.')

        # perform the move
        old_room = cur_room_no
        # Special handling: if moving up/down is represented via room.rc/rt rather than a directional exit
        # and this destination is the Shoppe (rt == 0), invoke merchant annex (bar) module's non-interactive helpers
        # Use server helper to keep client and Player in sync
        try:
            if hasattr(server, '_sync_player_location'):
                server._sync_player_location(client, dest_no)
            else:
                # fallback behavior if server helper not present
                client.room = dest_no
                try:
                    player_obj = get_player_from_context(context, client)
                    if player_obj is not None:
                        try:
                            player_obj.map_room = int(dest_no) if dest_no is not None else dest_no
                            lv = getattr(client, 'map_level', None) or getattr(server, 'map_level', getattr(server, 'level', 1))
                            try:
                                player_obj.map_level = int(lv)
                            except Exception:
                                player_obj.map_level = lv
                        except Exception:
                            logging.exception('Failed to set player map_room/map_level (fallback)')
                except Exception:
                    logging.debug('No player object to update for movement (fallback)')
        except Exception:
            logging.exception('Failed to sync player location')

        # announce to others (async broadcast)
        try:
            ann = Message(lines=[f"{getattr(client, 'username', 'Someone')} moves {compass_txts.get(direction, direction)}."],
                          type=MessageType.ANNOUNCEMENT, mode=Mode.app)
            # fire-and-forget but await so errors propagate in tests; server may handle exceptions
            await server.broadcast_message(getattr(client, 'addr', None), ann)
        except Exception:
            logging.exception('Failed to broadcast movement announcement')

        # Return the new room description to the mover
        try:
            lines = server._describe_room(client)
        except Exception:
            logging.exception('Failed to build room description after move')
            lines = [f"You move {compass_txts.get(direction, direction)}."]

        return CommandResult(success=True, message=lines, data={'room': dest_no})
# --- Additional logic for rc/rt transports (Shoppe) ---
# Note: rc/rt transports are encoded in room.exits as 'rc' and 'rt'.
# If player attempted 'up' or 'down' and the room has rc==1/2 with rt==0 (Shoppe), handle specially.
# We'll attempt to detect this earlier in the command execution to avoid no_exit for 'down' when rc exists.

class MoveHelp(BaseHelpText):
    """Help provider for the 'move' command."""
    name = 'move'
    aliases = ['n', 's', 'e', 'w', 'u', 'd', 'go']

    def __init__(self):
        super().__init__()
        self.category = HelpCategory.MOVEMENT
        self.summary = 'Move in compass directions'
        self.description = (
            "Use movement commands to travel between rooms. You can use single-letter directions "
            "(n, s, e, w, u, d) or the full words (north, south, east, west, up, down). You can also use "
            "'go <direction>' or the alias 'go'."
        )
        self.usage = [
            ("n|s|e|w|u|d", "Move one step in the specified compass direction"),
            ("go <direction>", "Alternate form: go north / go n")
        ]
        self.examples = [
            ("n", "Move north"),
            ("go west", "Move west using 'go'")
        ]

    def help_text(self, is_recursive: bool = False) -> str:
        return (
            "Move Command\n"
            "------------\n"
            "Usage: n|s|e|w|u|d\n"
            "       go <direction>\n\n"
            "Move between connected rooms in the specified direction.\n\n"
            "Examples:\n"
            "  n            - Move north\n"
            "  go south     - Move south using 'go'\n"
        )
