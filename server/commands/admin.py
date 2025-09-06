"""
Admin Commands Module

This module implements administrative commands for the TADA server. These commands
provide server management and moderation capabilities that should only be accessible
to administrators.

Command Structure:
------------------
- Each command is a class that inherits from the base Command class
- Commands use the Locks attribute to enforce permission requirements
- The `admin_only` flag can be set to True to restrict access to administrators

Command Execution Flow:
-----------------------
1. User enters a command in the client
2. Command is sent to the server
3. CommandManager receives and validates the command
4. If the command has locks or admin restrictions, they are checked
5. If all checks pass, the command's _execute() method is called
6. The result is sent back to the client

Example Admin Command:
----------------------
class ExampleAdminCommand(Command):
    '''Example admin command with documentation'''
    name = "example"
    aliases = ["ex", "examp"]
    admin_only = True
    
    def help_text(self) -> str:
        return '''Example admin command.
        
        Usage: example <argument>
        This is an example of how to create an admin command.'''
    
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        # Implementation here
        return CommandResult(success=True, message="Command executed")

Security Notes:
--------------
- Always validate user permissions in _execute()
- Never trust client-side validation
- Log all admin actions for auditing
- Use proper error handling and user feedback
- Consider rate limiting for sensitive operations

See Also:
---------
- base.py: Base Command class definition
- manager.py: Command registration and execution
- help.py: Help command implementation
"""

from server.locks import LockType


class RestartCommand(Command):
    """Admin command to restart the server"""
    name = "restart"
    aliases = ["reboot", "shutdown"]
    locks = [PlayerFlag.ADMINISTRATOR is True]

    def help_text(self) -> str:
        return (
            f"Restarts the server. Only available to administrators.\n"
            f"Usage: {self.name} [reason]"
        )

    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        # Get the user who executed the command
        user = data.get('user')
        reason = data.get('args', 'No reason provided')

        # add "shutdown", "shutdown now", "shutdown 10 minutes", "shutdown 5:00 pm",
        #  "shutdown 5pm", "shutdown 5:00", "shutdown next Thursday 5pm" etc. to the command
        if not user or not user.is_admin:
            return CommandResult(
                success=False,
                message="Error: This command requires administrator privileges.",
                data={"error": "insufficient_permissions"}
            )
            
        # Log the restart
        logger.warning(f"Server restart initiated by {user.name}. Reason: {reason}")
        
        # Broadcast to all users
        broadcast_message = f"Server restarting in 10 seconds (by {user.name}). Reason: {reason}"
        
        # Perform restart (this would be implemented in your server code)
        # await server_restart(delay=10, reason=reason, message=broadcast_message)
        
        return CommandResult(
            success=True,
            message="Server restart initiated. All users will be disconnected in 10 seconds.",
            data={"restart_scheduled": True}
        )

class ShutdownCommand(Command):
    """Admin command to shutdown the server"""
    name = "shutdown"
    aliases = ["shut"]
    locks = [PlayerFlag.ADMINISTRATOR is True]

    def help_text(self) -> str:
        return (
            f"Shuts down the server. Only available to administrators.\n"
            f"Usage: {self.name} [reason]"
        )

    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        # Get the user who executed the command
        user = data.get('user')
        reason = data.get('args', 'No reason provided')

        # Check if the user has the required permissions
        if not user or not user.is_admin:
            return CommandResult(
                success=False,
                message="Error: This command requires administrator privileges.",
                data={"error": "insufficient_permissions"}
            )
            
        # Log the shutdown
        logger.warning(f"Server shutdown initiated by {user.name}. Reason: {reason}")
        
        # Broadcast to all users
        broadcast_message = f"Server shutting down in 10 seconds (by {user.name}). Reason: {reason}"
        
        # Perform shutdown (this would be implemented in your server code)
        # await server_shutdown(delay=10, reason=reason, message=broadcast_message)
        
        return CommandResult(
            success=True,
            message="Server shutdown initiated. All users will be disconnected in 10 seconds.",
            data={"shutdown_scheduled": True}
        )

class BootCommand(Command):
    """Admin command to boot ill-behaving players"""
    name = "boot"
    aliases = ["kick"]
    locks = [PlayerFlag.ADMINISTRATOR is True]

    def help_text(self) -> str:
        return (
            f"Boots a player. Only available to administrators.\n"
            f"Usage: {self.name} <player_name> [reason]"
        )
    
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        # Get the user who executed the command
        user = data.get('user')
        player_name = data.get('args', 'No player name provided')
        reason = data.get('args', 'No reason provided')

        # Check if the user has the required permissions
        if not user or not user.is_admin:
            return CommandResult(
                success=False,
                message="Error: This command requires administrator privileges.",
                data={"error": "insufficient_permissions"}
            )
            
        # Log the boot
        logger.warning(f"Player {player_name} booted by {user.name}. Reason: {reason}")
        
        # Broadcast to all users
        broadcast_message = f"Player {player_name} booted by {user.name}. Reason: {reason}"
        
        # Perform boot (this would be implemented in your server code)
        # await server_boot(player_name, reason=reason, message=broadcast_message)
        
        return CommandResult(
            success=True,
            message="Player booted successfully.",
            data={"booted_player": player_name}
        )
        
class BanCommand(Command):
    """Admin command to ban players or IP addresses for a specified duration"""
    name = "ban"
    locks = [LockType.IS_ADMINISTRATOR]

    def help_text(self) -> str:
        return ([
            f"Bans a player or IP address, optionally for a specified duration. Only available to administrators."
            f"{self.name} <player_name> [duration] [reason]\n"
            f"{self.name} <ip_address> [duration] [reason]\n"
            f"{self.name} #list \n"
        ])
    
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        # Get the user who executed the command
        user = data.get('user')
        ip_address = data.get('ip_address', 'No IP address provided')
        player_name = data.get('args', 'No player name provided')
        duration = data.get('args', 'No duration provided')
        reason = data.get('args', 'No reason provided')
        show_ban_list = data.get('args', '#list', "Not showing ban list")

        # Check if the user has the required permissions
        if not user or not user.is_admin:
            return CommandResult(
                success=False,
                message="Error: This command requires administrator privileges.",
                data={"error": "insufficient_permissions"}
            )

        if show_ban_list == "#list":
            # TODO: locate ban list file and display it
            return CommandResult(
                success=True,
                message="Ban list displayed.",
                data={"ban_list": "Ban list displayed."}
            )

        # Log the ban
        logger.warning(f"Player {player_name} banned by {user.name}. Duration: {duration}. Reason: {reason}. IP Address: {ip_address}")
        
        # Broadcast to all users
        broadcast_message = f"Player {player_name} banned by {user.name}. Duration: {duration}. Reason: {reason}. IP Address: {ip_address}"
        
        # Perform ban (this would be implemented in your server code)
        # await server_ban(player_name, duration=duration, reason=reason, message=broadcast_message)
        
        return CommandResult(
            success=True,
            message="Player banned successfully.",
            data={"banned_player": player_name}
        )

# other admin type commands

class UnbanCommand(Command):
    """Admin command to unban players or IP addresses"""
    name = "unban"
    locks = [LockType.IS_ADMINISTRATOR]

    def help_text(self) -> str:
        return ([
            f"Unbans a player or IP address. Only available to administrators.\n"
            f"{self.name} <player_name> [reason]"
        ])
    
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        # Get the user who executed the command
        user = data.get('user')
        player_name = data.get('args', 'No player name provided')
        ip_address = data.get('ip_address', 'No IP address provided')
        reason = data.get('args', 'No reason provided')

        # Check if the user has the required permissions
        if not user or not user.is_admin:
            return CommandResult(
                success=False,
                message="Error: This command requires administrator privileges.",
                data={"error": "insufficient_permissions"}
            )
            
        # Log the unban
        logger.info(f"Player {player_name} unbanned by {user.name}. Reason: {reason}. IP Address: {ip_address}")
        
        # Broadcast to all users
        broadcast_message = f"Player {player_name} unbanned by {user.name}. Reason: {reason}. IP Address: {ip_address}"
        
        # Perform unban (this would be implemented in your server code)
        # await server_unban(player_name, reason=reason, message=broadcast_message)
        
        return CommandResult(
            success=True,
            message="Player unbanned successfully.",
            data={"unbanned_player": player_name}
        )