"""
Command handler for processing player commands in the server.
"""
import logging
from typing import Dict, Any, Optional

from .commands.base import CommandResult
from .command_processor import CommandProcessor
from .player import Player

class CommandHandler:
    """Handles player commands with the command processor."""
    
    def __init__(self, player: Player, client_manager, server):
        """Initialize the command handler.
        
        Args:
            player: The player instance
            client_manager: The client manager instance
            server: The server instance
        """
        self.player = player
        self.client_manager = client_manager
        self.server = server
        self._command_processor = None
        
    @property
    def command_processor(self) -> CommandProcessor:
        """Get or create a command processor for this handler."""
        if self._command_processor is None:
            from command_processor import create_command_processor
            self._command_processor = create_command_processor({
                'player': self.player,
                'client_manager': self.client_manager,
                'server': self.server,
                'handler': self
            })
        return self._command_processor
    
    async def handle_command(self, input_text: str, data: Optional[Dict[str, Any]] = None) -> CommandResult:
        """Handle a command from the player.
        
        Args:
            input_text: The raw input text from the player
            data: Additional data for the command
            
        Returns:
            CommandResult: The result of the command execution
        """
        if not input_text.strip():
            return CommandResult(
                success=False,
                error='empty_input',
                message='Please enter a command.'
            )
        
        # Log the command
        logging.debug("Player %s command: %s", self.player.id, input_text)
        
        # Update last command for repeat with Return/Enter
        self.player.last_command = input_text
        
        # Prepare the context
        context = {
            'player': self.player,
            'client_manager': self.client_manager,
            'server': self.server,
            **(data or {})
        }
        
        # Process the command
        return await self.command_processor.process_input(input_text, context)
    
    def get_all_commands(self):
        return self.command_processor.get_all_commands()
    
    async def handle_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a message from the player.
        
        Args:
            data: The message data from the client
            
        Returns:
            Dict: The response data to send back to the client
        """
        if 'text' not in data:
            return {}
            
        input_text = data['text'].strip()
        if not input_text:
            return {}
            
        # Process the command
        result = await self.handle_command(input_text, data)
        
        # Prepare the response
        response = {
            'type': 'command_result',
            'success': result.success,
            'message': result.message,
            **(result.data or {})
        }
        
        if result.error:
            response['error'] = result.error
            
        return response
