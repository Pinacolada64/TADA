import logging
from typing import List, Dict, Any

from commands.base_command import BaseCommand, CommandResult, HelpCategory
# The @command decorator is imported from the main processor file
from commands.command_processor import command
from commands.help import BaseHelpText
from net_common import client_manager

logger = logging.getLogger(__name__)


@command(name="look", aliases=["l"], summary="Examines the current room or an object.")
class LookCommand(BaseCommand):
    """
    The Look command is used to observe your immediate surroundings or inspect
    a specific object, creature, or player in the area.
    """

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        # Check if the command was run via an alias
        command_used = context.get('raw_input', '').split()[0]

        if args:
            target = args[0]
            if target.lower() in ["me", "self"]:
                return CommandResult(success=True,
                                     message=f"You examine yourself. Your username is {context.get('username', 'a guest')}.")
            return CommandResult(success=True,
                                 message=f"You use '{command_used}' to inspect {target}. It appears to be... ordinary.")
        else:
            # sample 'look' command for a mocked-up room:
            return CommandResult(success=True, lines=[
                "You are in a dimly lit chamber.",
                "A large wooden door is to the north.",
                f"You used the alias '{command_used}' to look around."
            ], message="Look successful.")

class LookHelp(BaseHelpText):
    @property
    def name(self):
        return "look"

    @property
    def aliases(self):
        return ['look', 'l']

    @property
    def summary(self):
        return "Examine an object or yourself."

    @property
    def usage(self):
        return ""
@command(name="say", aliases=['"'])
class SayCommand(BaseCommand):
    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(success=False,
                                 error="no_message",
                                 message="What would you like to say?")

        message = " ".join(args)
        verb = "say"
        if message.endswith("?"):
            verb = "ask"
        elif message.endswith("!"):
            verb = "exclaim"
        quotation = '"'

        broadcast_message = f"{context.get('username', 'Guest')} "
        logger.info(f"Broadcast: {context.get('username', 'Guest')} {verb}s, {quotation}{message}{quotation}")

        # tell all users in the room except the player saying something what they said:
        client_manager.tell_room(message=message, exclude=context.get('username'))

        return CommandResult(
            success=True,
            message=f"You tell the room: '{message}'",
            data={'text': message}
        )

class SayHelp(BaseHelpText):
    def __init__(self):
        super().__init__()
        self.category = HelpCategory.COMMUNICATION
        self.summary = "Speak a message to everyone in the room."
