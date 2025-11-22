from typing import Dict, Any, List
from commands.base_command import BaseCommand, CommandResult
from commands.command_processor import command
from commands.context import Context
from net_common import Mode
from commands.utils import get_player_from_context


@command(name="guest", summary="Connect as a temporary guest")
class GuestConnectCommand(BaseCommand):
    """Assign a unique GuestN username and return a CommandResult that tells the server
    to transition the client into guest/app mode.
    """
    # Only available during login flow; not kept for authenticated players
    login_only = True

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        # Context may contain either the string key 'client' or Context.CLIENT enum key
        client = None
        if isinstance(context, dict):
            client = context.get('client') or context.get(Context.CLIENT)
        player = get_player_from_context(context, client)

        username = 'Guest1'
        try:
            if client and getattr(client, 'server', None):
                server = client.server
                existing = {getattr(c, 'username', None) for c in server.clients.values()}
                base = 'Guest'
                n = 1
                while f"{base}{n}" in existing:
                    n += 1
                username = f"{base}{n}"
            else:
                # fallback to global client_manager if available
                try:
                    # why import from net_common? because client_manager is defined there
                    from net_common import client_manager
                    existing = {getattr(ci.handler, 'username', None) for ci in client_manager.clients.values()}
                    base = 'Guest'
                    n = 1
                    while f"{base}{n}" in existing:
                        n += 1
                    username = f"{base}{n}"
                except Exception:
                    username = 'Guest1'
        except Exception:
            username = 'Guest1'

        message = f"Welcome, {username}! You are connected as a guest. This means you cannot build things."
        return CommandResult(
            success=True,
            message=message,
            data={'authenticated': False, 'mode': Mode.guest, 'username': username}
        )
