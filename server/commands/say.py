import time
from typing import Dict, Any, List

from base_command import Command
from commands.command_types import CommandResult
from commands.help import HelpCategory, Help
from network_context import GameContext


class SayCommand(Command):
    """Broadcast a message to other players in the same room.

    This command chooses the verb (say/ask/exclaim) based on
    punctuation.
    """
    name = 'say'
    aliases = ['"']
    help = Help(
        summary="Say something to players in your room.",
        category=HelpCategory.COMMUNICATION,
        usage=[
            ("say <message>", "Speak aloud to everyone in the room"),
            ('"<message>', "Shorthand for 'say'"),
        ],
        examples=[
            ("say Hello there!", "Everyone in the room hears you"),
        ],
    )

    def __init__(self, context: Dict[str, Any] = None):
        super().__init__()
        self.quotation_mark = '"'

    async def execute(self, ctx: GameContext, *args: List[str]) -> CommandResult:
        # args will be the split input; the message is everything after the command
        args, switches = self.parse_args(*args)
        if not args:
            await ctx.send('What would you like to say?')

        # Reconstruct the message text from args
        message_text = ' '.join(args)
        # If message begins with a quote (shorthand for 'say'), strip it
        if message_text.startswith('"'):
            message_text = message_text[1:]

        verb = 'say'
        if args[-1].endswith('?'):
            verb = 'ask'
        elif args[-1].endswith('!'):
            verb = 'exclaim'

        who_says = ctx.player.name
        to_self = f'You {verb}, "{message_text}"'
        to_others = f'{who_says} {verb}s, "{message_text}"'

        await ctx.send_room(to_others)
        await ctx.send(to_self)
        return CommandResult.ok(f"{who_says} Say successful.")
