from typing import Dict, Any, List
import logging

from commands.base_command import Command, CommandResult, HelpCategory
from commands.command_processor import command
from commands.utils import get_player_from_context
from flags import PlayerFlags


@command(name='#', aliases=['teleport'], summary='Admin: teleport to a room number')
class TeleportCommand(Command):
    """Teleport the caller (admin only) to the specified room number.

    Usage: # <room_number>
    Shorthand: #37 will be handled by the processor and passed as args=['37'].
    """

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        # Resolve client and server
        client = None
        if isinstance(context, dict):
            client = context.get('client') or context.get('client')
        if client is None:
            return CommandResult(success=False, error='no_client', message='No client information available')

        server = context.get('server') if isinstance(context, dict) else None
        if server is None:
            server = getattr(client, 'server', None)

        # Permission check: prefer PlayerFlags.ADMIN on the player's flags, fall back to client/context is_admin
        is_admin = False
        try:
            player = get_player_from_context(context, client)
            if player is not None:
                qf = getattr(player, 'query_flag', None)
                if callable(qf):
                    try:
                        is_admin = bool(qf(PlayerFlags.ADMIN))
                    except Exception:
                        is_admin = False
                else:
                    # If player is a dict-like structure, look up flags mapping
                    try:
                        flags_map = getattr(player, 'flags', None) or (player.get('flags') if isinstance(player, dict) else None)
                        if flags_map:
                            # flags_map may map PlayerFlags to Flag objects or bools
                            val = flags_map.get(PlayerFlags.ADMIN)
                            if isinstance(val, bool):
                                is_admin = val
                            elif val is not None:
                                # Flag dataclass: check its 'status' attribute
                                is_admin = bool(getattr(val, 'status', False))
                    except Exception:
                        is_admin = False
            # fallback to client/context
            if not is_admin:
                is_admin = bool(getattr(client, 'is_admin', False) or context.get('is_admin', False))
        except Exception:
            is_admin = bool(getattr(client, 'is_admin', False) or context.get('is_admin', False))
        if not is_admin:
            return CommandResult(success=False, error='permission_denied', message='Teleport is admin-only')

        if not args or not args[0]:
            return CommandResult(success=False, error='missing_arg', message='Usage: #<room_number> or # <room_number>')

        try:
            dest = int(str(args[0]).strip())
        except Exception:
            return CommandResult(success=False, error='bad_arg', message='Room number must be an integer')

        # If server/map available, validate destination
        game_map = getattr(server, 'game_map', None)
        if game_map and dest not in game_map.rooms:
            return CommandResult(success=False, error='bad_room', message=f'Room {dest} does not exist')

        # Update client and player room information using server helper
        try:
            if server and hasattr(server, '_sync_player_location'):
                server._sync_player_location(client, dest)
            else:
                try:
                    client.room = dest
                except Exception:
                    setattr(client, 'room', dest)
                try:
                    player = get_player_from_context(context, client)
                    if player is not None:
                        player.map_room = dest
                except Exception:
                    pass
        except Exception:
            pass

        # Describe the room to the teleported player if server has helper
        try:
            if server and hasattr(server, '_describe_room'):
                lines = server._describe_room(client)
            else:
                lines = [f'You teleport to room {dest}.']
        except Exception:
            logging.exception('Failed to describe room after teleport')
            lines = [f'You teleport to room {dest}.']

        return CommandResult(success=True, message=lines, data={'room': dest})


class TeleportHelp:
    name = '#'
    def __init__(self):
        self.category = HelpCategory.MOVEMENT
        self.summary = 'Teleport to a room (admin only)'
        self.description = 'Teleport instantly to the specified room number. Usage: #37 or # 37'
        self.usage = [('#<room>', 'Teleport to room <room>')]

# command-line smoke test:
"""
python3 - << 'PY'
> from commands.command_processor import create_command_processor
> class DummyPlayer:
>     def __init__(self, admin=False):
>         self.admin = admin
>     def query_flag(self, f):
>         from flags import PlayerFlags
>         return f == PlayerFlags.ADMIN and self.admin
> class DummyClient:
>     def __init__(self, player):
>         self.player = player
>         self.server = type('S',(),{'game_map': None})()
> proc = create_command_processor(DummyClient(DummyPlayer(admin=True)))
> print('Commands:', sorted([c.name for c in proc.get_all_commands()]))
> print('Run #37 ->', __import__('asyncio').run(proc.process_input('#37')))
> PY
"""
