#!/bin/env python3
"""Who command implementation."""
from typing import Dict, Any, List
from datetime import datetime, timedelta

from .base import Command, CommandResult

class WhoCommand(Command):
    """
    Handle the 'who' command for listing online players.
    If an Administrator runs the command, the player's IP address will also be shown.
    """
    
    # Class-level constant for help text
    HELP_TEXT = """\
    Who Command
    -----------
    Usage: who
    
    Lists all currently online players, their connected time, and their idle time.
    
    Examples:
      who    - Shows the list of online players
    
    Aliases: players, online
    """
    
    @property
    def name(self) -> str:
        return "who"
    
    def help_summary(self) -> str:
        return "Lists all currently online players, their connected time, and their idle time."
    
    def help_text(self) -> str:
        text = self.HELP_TEXT
        
        # Add admin-specific help if user is admin
        user = self.context.get('user')
        if user and hasattr(user, 'is_admin') and user.is_admin:
            text += "\nAdministrator privilege required to see IP addresses."
            
        return text
    
    @property
    def aliases(self) -> List[str]:
        return ["players", "online"]
    
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        """Execute the who command.
        
        Args:
            data: Dictionary containing command data (unused for this command)
            
        Returns:
            CommandResult: Result containing the list of online players
        """
        # Get the client manager from context
        client_manager = self.context.get('client_manager')
        if not client_manager:
            return CommandResult(
                success=False,
                error='server_error',
                message='Unable to get online players: client manager not available.'
            )
        
        # Get all connected clients
        clients = client_manager.get_connected_clients()
        online_players = []
        
        # Get current time for idle calculation
        current_time = datetime.now()
        
        # Get the user making the request
        user = self.context.get('user')
        
        # Prepare player information
        for client in clients:
            if hasattr(client, 'player') and client.player:
                player = client.player
                # Format connected time
                connected_time = client.connected_time.strftime('%Y-%m-%d %H:%M:%S') if hasattr(client, 'connected_time') else 'Unknown'
                
                # Calculate idle time
                idle_seconds = (current_time - client.last_activity).total_seconds() if hasattr(client, 'last_activity') else 0
                idle_time = str(timedelta(seconds=int(idle_seconds)))
                
                # Format player info
                player_info = f"{player.name:10} {connected_time:20} {idle_time:16}"
                
                # Add IP address if user is admin
                if hasattr(user, 'is_admin') and user.is_admin and hasattr(client, 'address') and client.address:
                    ip_address = client.address[0] if isinstance(client.address, tuple) else str(client.address)
                    player_info += f" {ip_address:15}"
                
                online_players.append(player_info)
        
        # Create header
        header = "Name       Connected            Idle"
        if hasattr(user, 'is_admin') and user.is_admin:
            header += "             IP Address"
        
        # Sort players by name
        online_players.sort()
        count = len(online_players)
        
        return CommandResult(
            success=True,
            message=[f"{header}", "Players online ({count}):", "\n".join(online_players)],
            data={
                'type': 'who',
                'players': online_players,
                'count': count
            }
        )

def register():
    """Register the who command."""
    return WhoCommand()
