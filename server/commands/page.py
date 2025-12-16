#!/bin/env python3
"""Page command implementation."""
import time
from typing import Dict, Any, Optional, List, Set

from .base_command import Command, CommandResult
from commands.help import BaseHelpText, HelpCategory
from commands import command_processor
from commands.utils import get_player_from_context


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
        return ["tell", "msg", "p"]
    
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
                message='Usage: page <player> <message> or p <player> <message>'
            )
            
        if not message:
            return CommandResult(
                success=False,
                error='missing_message',
                message='Please provide a message.'
            )
        
        # Get the client manager and user
        client_manager = self.context.get('client_manager')
        # If available, derive the current player from the context for use by page handlers
        client = self.context.get('client') if isinstance(self.context, dict) else None
        player = get_player_from_context(self.context, client)
        if not client_manager:
            return CommandResult(
                success=False,
                error='server_error',
                message='Server error: Client manager not available.'
            )
            
        # Check if this is a reply to the last page
        if target.lower() == 'reply':
            if not self._page_recipients:
                return CommandResult(
                    success=False,
                    error='no_previous_page',
                    message='No one to reply to. Use: page <player> <message>'
                )
            target = next(iter(self._page_recipients))
        
        # Check if target is online
        if not client_manager.is_online(target):
            return CommandResult(
                success=False,
                error='player_offline',
                message=f'{target} is not online.'
            )
            
        # Check if target is ignoring pages from this user
        if client_manager.is_ignoring(target, user_id):
            return CommandResult(
                success=False,
                error='ignored',
                message=f'{target} is not accepting pages from you.'
            )
            
        # Check rate limiting
        if client_manager.is_rate_limited(user_id, 'page'):
            return CommandResult(
                success=False,
                error='rate_limited',
                message='You are sending pages too quickly. Please wait a moment.'
            )
            
        # Get the target client and send the message
        target_client = client_manager.get_client(target)
        if target_client:
            # Format the page message
            page_msg = {
                'type': 'page',
                'from': user_id,
                'text': message,
                'timestamp': time.time()
            }
            
            # Send the message
            await target_client.handler.send_async_message(page_msg)
            
            # Update last paged time for rate limiting
            client_manager.update_last_page(user_id, target)
            
            # Add to page history for reply
            self._page_recipients.add(target)
            
            return CommandResult(
                success=True,
                message=f'You paged {target}: {message}'
            )
        
        return CommandResult(
            success=False,
            error='unknown_error',
            message='Failed to send page.'
        )
    
class PageHelp(BaseHelpText):
    """Help provider for the 'page' command."""
    name = "page"
    aliases = ["p"]

    def __init__(self):
        super().__init__()
        self.category = HelpCategory.COMMUNICATION
        self.summary = "Send a private message to a player in either the same room as you, or another room."
        self.description = (
            "The 'page' command allows you to send a message to other players either in your current location, "
            "or in another room."
        )
        self.usage = [
            ("page <player> <message>", "Send a private message to <player>"),
            ("page reply <message>", "Reply to the last person who paged you"),
            ("page #last", "Show last paged players")
        ]
        self.examples = [
            ("page bob Hello", "Send 'Hello' to player 'bob'"),
            ("p alice Hi", "Alias 'p' is shorthand for page")
        ]
        self.notes = [
            "You can use 'help page' to see this text.",
            "Aliases: p, tell, msg"
        ]

    def help_text(self) -> str:
        return (
            "Page Command\n"
            "-----------\n"
            "Usage: page <player> <message>\n"
            "       page reply <message>\n\n"
            "Sends a private message to another player.\n\n"
            "Examples:\n"
            "  page bob Hello there!     - Sends a message to 'bob'\n"
            "  p alice Are you there?    - Sends a message using alias 'p'\n"
            "\nAliases: tell, msg, p"
        )

def register():
    """Register the page command with the command processor."""
    command = PageCommand()
    try:
        command_processor.register_command(command)
    except Exception:
        # command_processor may not expose register_command at import time; ignore
        pass
    return command
