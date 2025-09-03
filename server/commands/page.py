#!/bin/env python3
"""Page command implementation."""
from typing import Dict, Any, Optional, List, Set

from .base import Command, CommandResult

class PageCommand(Command):
    """Handle the 'page' command for sending private messages."""
    
    def __init__(self, context=None):
        super().__init__(context)
        self._page_recipients: Set[str] = set()
    
    @property
    def name(self) -> str:
        return "page"
    
    @property
    def aliases(self) -> List[str]:
        return ["tell", "msg"]
    
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        """Execute the page command.
        
        Args:
            data: Dictionary containing command data including:
                - target: The player to page (or 'reply' to reply to the last pager)
                - message: The message to send
                - user_id: The ID of the user sending the page
                
        Returns:
            CommandResult: Result of the page command
        """
        target = data.get('target')
        message = data.get('message')
        user_id = data.get('user_id')
        
        if not target:
            return CommandResult(
                success=False,
                error='missing_target',
                message='Usage: page <player> <message> or page reply <message>'
            )
            
        if not message:
            return CommandResult(
                success=False,
                error='missing_message',
                message='Please provide a message.'
            )
        
        # Get the client manager from context
        client_manager = self.context.get('client_manager')
        if not client_manager:
            return CommandResult(
                success=False,
                error='server_error',
                message='Unable to process page: client manager not available.'
            )
        
        # Handle reply to last pager
        if target.lower() == 'reply':
            if not self._page_recipients:
                return CommandResult(
                    success=False,
                    error='no_recipients',
                    message='No one has paged you yet.'
                )
            target = next(iter(self._page_recipients))
        
        # Verify target is online
        if not client_manager.is_online(target):
            return CommandResult(
                success=False,
                error='player_offline',
                message=f'{target} is not online.'
            )
        
        # Format the message
        formatted_message = f"[PAGE from {user_id}] {message}"
        
        # Send the page
        client_manager.send_to(
            target,
            {
                'type': 'page',
                'from': user_id,
                'message': message,
                'mode': 'app'  # Assuming the recipient is in app mode
            }
        )
        
        # Record this recipient for reply
        self._page_recipients.add(target)
        
        # Send confirmation to sender
        return CommandResult(
            success=True,
            message=f"Page sent to {target}.",
            data={
                'type': 'page_sent',
                'to': target,
                'message': message
            }
        )
    
    def help_text(self) -> str:
        return """\
        Page Command
        -----------
        Usage: page <player> <message>
               page reply <message>
        
        Sends a private message to another player.
        
        Examples:
          page bob Hello there!     - Sends a message to 'bob'
          page reply Got it!        - Replies to the last person who paged you
        
        Aliases: tell, msg
        """

def register():
    """Register the page command."""
    return PageCommand()
