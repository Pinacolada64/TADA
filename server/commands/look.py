from commands.base_command import Command
from commands.help import Help, HelpCategory
from network_context import GameContext
from tada_utilities import PronounType, get_pronoun

# Usage:
# processor = CommandProcessor()
# processor.register(LookCommand())

class LookCommand(Command):
    """
    The Look command is used to observe your immediate surroundings or inspect
    a specific object, creature, or player in the area.
    """
    help_info = Help(
        summary="Examines the current room, or an object in the room.",
        description="a more detailed description of 'look'.",
        category=HelpCategory.INTERACTION,
        usage=[("look", "Look at the current room"),
                                  ("l", "Alias for 'look'"),
                                  ("l me", "Look at yourself"),
                                  ("l self", "Look at yourself"),
                                  ("l myself", "Look at yourself"),
                                  ("l <object>", "Look at <object>: player, item, monster, FIXME: anything else?")]
                         )

    async def execute(self, ctx: GameContext, *args):
        args, switches = Command.parse_args(ctx, args)
        # Using your existing GameContext features directly
        room_desc = "You are in a cozy room."
        player_name = getattr(ctx.player.name, 'name', "Unknown player")
        if args is None:
            # Examine the current room
                await ctx.send(room_desc)
                await ctx.send_room(f"{player_name} looks around.")
        target = args[1]
        if target.lower() in ["me", "self", "myself"]:
            await ctx.send(f"You examine yourself. Your username is {player_name}.")
            # use PRONOUN_TYPE.REFLEXIVE here to return 'himself', 'herself', 'itself':
            reflexive = get_pronoun(ctx.player, PronounType.REFLEXIVE)
            await ctx.send_room(f"{player_name} examines {reflexive}.")
            return
        if switches == "#help":
            await ctx.send(LookCommand.help('look'))
            return
        """
        # Check if the command was run via an alias
        command_used = context.get('raw_input', '').split()[0]

            return CommandResult(success=True, lines=[
                "You are in a dimly lit chamber.",
                "A large wooden door is to the north.",
                f"You used the alias '{command_used}' to look around."
            ], message="Look successful.")
        """