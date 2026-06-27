#!/bin/env python3
"""Whisper command implementation."""
from typing import Dict, Any, Optional, List, Set

from .base_command import Command, CommandResult
from commands.utils import get_player_from_context

class WhisperCommand(Command):
    """Handle the 'whisper' command for sending private messages to nearby players."""
    
    def __init__(self, context=None):
        super().__init__(context)
        self._whisper_recipients: Set[str] = set()
    
    @property
    def name(self) -> str:
        return "whisper"
    
    @property
    def aliases(self) -> List[str]:
        # can't be 'w', because that's an alias for 'go west'
        return ["wh"]
    
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        """Execute the whisper command.
        
        Args:
            data: Dictionary containing command data including:
                - target: The player to whisper to
                - message: The message to send
                - user_id: The ID of the user sending the whisper
                
        Returns:
            CommandResult: Result of the whisper command
        """
        target = data.get('target')
        message = data.get('message')
        user_id = data.get('user_id')
        
        if not target:
            return CommandResult(
                success=False,
                error='missing_target',
                message='Usage: whisper <player> <message> or w <player> <message>'
            )
            
        if not message:
            return CommandResult(
                success=False,
                error='missing_message',
                message='Please provide a message to whisper.'
            )
            
        # Get the client manager and user
        client_manager = self.context.get('client_manager')
        client = self.context.get('client') if isinstance(self.context, dict) else None
        player = get_player_from_context(self.context, client)

        if not client_manager:
            return CommandResult(
                success=False,
                error='server_error',
                message='Server error: Client manager not available.'
            )
            
        # Check if target is online
        if not client_manager.is_online(target):
            return CommandResult(
                success=False,
                error='player_offline',
                message=f'{target} is not online.'
            )
            
        # Check if target is ignoring whispers from this user
        if client_manager.is_ignoring(target, user_id):
            return CommandResult(
                success=False,
                error='ignored',
                message=f'{target} is not accepting whispers from you.'
            )
            
        # Check rate limiting
        if client_manager.is_rate_limited(user_id, 'whisper'):
            return CommandResult(
                success=False,
                error='rate_limited',
                message='You are sending whispers too quickly. Please wait a moment.'
            )
            
        # Get the target client and send the message
        target_client = client_manager.get_client(target)
        if target_client:
            # Format the whisper message
            whisper_msg = {
                'type': 'whisper',
                'from': user_id,
                'text': message,
                'timestamp': self.context.get('time', 0) if self.context else 0
            }
            
            # Send the message
            await target_client.handler.send_async_message(whisper_msg)
            
            # Update last whispered time for rate limiting
            client_manager.update_last_whisper(user_id, target)
            
            # Add to whisper history
            self._whisper_recipients.add(target)
            
            return CommandResult(
                success=True,
                message=f'You whisper to {target}: {message}'
            )
        
        return CommandResult(
            success=False,
            error='unknown_error',
            message='Failed to send whisper.'
        )

def register():
    """Register the whisper command with the command manager."""
    from .manager import command_manager
    command = WhisperCommand()
    command_manager.register_command(command)
    return command
