"""commands/ooc.py — Step outside the fiction for a second, in your room.

Broadcasts an out-of-character aside, visually distinct from in-character
speech (SAY) or action (POSE) -- a near-universal MU*/MUCK convention for
things like "brb, phone" without leaving the room-wide channel:
  ooc brb, phone.  →  [OOC] Rulan: brb, phone.

Unlike SAY/POSE there's no "You .../Name ..." split -- everyone in the
room, including the speaker, sees the exact same bracketed line.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class OocCommand(Command):
    name    = 'ooc'
    modes   = {Mode.GAME}

    help = Help(
        summary     = "Step outside the fiction for a quick aside.",
        description = (
            "Broadcasts an out-of-character message to your room, "
            "prefixed with [[OOC]] so it reads as clearly separate from "
            "in-character SAY/POSE output. Everyone in the room, "
            "including you, sees the identical line."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('ooc <message>', 'Send an out-of-character aside to the room'),
        ],
        examples = [
            ('ooc brb, phone.',   'OOC broadcasts the message to everyone in your '
                                  'room (yourself included) as "[OOC] Rulan: brb, '
                                  'phone." -- no verb, no quoting, just a clearly '
                                  'marked aside.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)
        text = ' '.join(args).strip()

        if not text:
            await ctx.send('Say what, out of character?')
            return CommandResult(False, 'No message.')

        # [[OOC]] escapes the brackets -- a bare [OOC] would be eaten by
        # highlight_brackets() as [bracketed]-highlight markup (see its
        # own doctest for the [[double-bracket]] escape convention).
        line = f'[[OOC]] {ctx.player.name}: {text}'
        await ctx.send(line)
        await ctx.send_room(line, exclude_self=True)
        return CommandResult.ok()
