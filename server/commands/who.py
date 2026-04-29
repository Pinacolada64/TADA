#!/bin/env python3
"""Who command implementation."""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from commands.base_command import Command, CommandResult, HelpCategory
from commands.command_processor import command

import net_common

from commands.help import BaseHelpText
from commands.utils import get_player_from_context


class WhoHelp(BaseHelpText):
    name = 'who'
    aliases = []

    def __init__(self):
        super().__init__()
        self.category = HelpCategory.COMMUNICATION
        self.summary = 'List currently online players'
        self.description = (
            "Show connected players with their connected time and idle time. Admins may see additional details like IP addresses."
        )
        self.usage = [
            ("who", "Show list of currently online players"),
            ("who <filter>", "(Optional) Filter the list by name or criteria")
        ]
        self.examples = [
            ("who", "List currently online players"),
        ]

    def help_text(self) -> str:
        return (
            "Who Command\n"
            "-----------\n"
            "Usage: who\n\n"
            "Displays currently connected players, their connection time, and idle time.\n"
            "Admins may see additional information such as IP addresses.\n"
        )


@command(name='who', category=HelpCategory.COMMUNICATION,
         summary='List currently online players')
class WhoCommand(Command):
    """List online players (who).

    Shows connected players, connected time and idle time. If the caller appears
    to be an admin, show IP addresses when available.
    """

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        try:
            client_manager = getattr(net_common, 'client_manager', None)
            if client_manager is None:
                return CommandResult(success=False, error='no_client_manager', message='Client manager not available')

            # Determine if caller is admin
            caller = context.get('client') or context.get('caller') or None
            player = get_player_from_context(context, caller)
            is_admin = False
            try:
                is_admin = bool(getattr(caller, 'is_admin', False) or context.get('is_admin', False) or context.get('user_level') == 'admin')
            except Exception:
                is_admin = False

            # Pull online client info; keep order deterministic
            try:
                clients_info = list(client_manager.get_online_client_info())
            except Exception:
                # Fallbacks: older ClientManager APIs
                try:
                    clients_info = list(client_manager._clients.values())
                except Exception:
                    clients_info = []

            lines: List[str] = []
            header = "Name       Connected            Idle"
            if is_admin:
                header += "             IP"
            lines.append(header)

            now = datetime.now()
            players_lines: List[str] = []

            for c in sorted(clients_info, key=lambda x: x.get('player_name') or x.get('user_id') or ''):
                # c is a dict-like client info
                player_name = c.get('player_name') or c.get('user_id') or 'Unknown'
                connected_time = c.get('connected_time')
                if isinstance(connected_time, (int, float)):
                    # epoch seconds
                    try:
                        ct = datetime.fromtimestamp(float(connected_time))
                    except Exception:
                        ct = None
                else:
                    ct = connected_time if isinstance(connected_time, datetime) else None

                connected_str = ct.strftime('%Y-%m-%d %H:%M:%S') if ct else 'Unknown'

                last_activity = c.get('last_activity')
                if isinstance(last_activity, (int, float)):
                    try:
                        la = datetime.fromtimestamp(float(last_activity))
                    except Exception:
                        la = None
                else:
                    la = last_activity if isinstance(last_activity, datetime) else None

                idle = now - la if la else timedelta(seconds=0)
                idle_str = str(idle).split('.')[0]

                row = f"{player_name:10} {connected_str:20} {idle_str:16}"
                if is_admin:
                    addr = c.get('address') or c.get('ip') or ''
                    if isinstance(addr, (list, tuple)) and addr:
                        addr = addr[0]
                    row += f" {str(addr):15}"
                players_lines.append(row)

            if not players_lines:
                lines.append("No players online.")
            else:
                lines.extend(players_lines)

            return CommandResult(success=True, message=lines, data={'type': 'who', 'count': len(players_lines)})

        except Exception as e:
            logging.exception("Error in WhoCommand.execute")
            return CommandResult(success=False, error='command_error', message=f'Error running who: {e}')


def register():
    """Compatibility helper for older registration codepaths."""
    return WhoCommand()
