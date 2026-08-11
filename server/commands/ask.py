"""commands/ask.py — Ask something aloud, phrased as a question.

Works like SAY, but always uses the "asks" verb instead of picking one
from trailing punctuation. In Gollum's cave (encounters/gollum.py), while
he's alive, a bare ASK (or ASK RIDDLE / ASK GOLLUM) opens a menu of
riddles to pose to him instead of just broadcasting text.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext

# Phrasings that open the riddle menu rather than being broadcast verbatim
# -- bare ASK included, since that's the natural first thing to try.
_MENU_TRIGGERS = {'', 'riddle', 'riddles', 'gollum', 'gollum riddle',
                  'gollum riddles', 'gollum a riddle', 'a riddle'}


class AskCommand(Command):
    name    = 'ask'
    modes   = {Mode.GAME}

    help = Help(
        summary     = "Ask a question aloud, or ask Gollum a riddle in his cave.",
        description = (
            "Broadcasts a message to your room, phrased as a question -- "
            'the same as SAY, but always using the "asks" verb. Inside '
            "Gollum's cave, while he's alive, a bare ASK (or ASK RIDDLE) "
            "opens a menu of riddles to pose to him instead."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('ask',            "Ask Gollum a riddle, if he's nearby"),
            ('ask <message>',  'Ask something aloud to everyone in your room'),
        ],
        examples = [
            ('ask riddle',           'ASK works like SAY, but always phrased as a question. '
                                      "In Gollum's cave, while he's alive, \"ask riddle\" opens a "
                                      'menu of riddles to pose to him instead of broadcasting text.'),
            ('ask What time is it?', 'Everywhere else (or once Gollum is gone), ASK just '
                                      'broadcasts your question to the room using the "asks" '
                                      'verb -- other players see \'Rulan asks, "What time is '
                                      'it?"\''),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _switches = self.parse_args(*args)
        text = ' '.join(args).strip()

        from encounters.gollum import current_gollum, ask_riddle_menu, riddle_response
        gollum = current_gollum(ctx)

        if gollum and text.lower() in _MENU_TRIGGERS:
            await ask_riddle_menu(ctx)
            return CommandResult.ok()

        if not text:
            await ctx.send('Ask what?')
            return CommandResult(False, 'No message.')

        name = ctx.player.name
        await ctx.send(f'You ask, "{text}"')
        await ctx.send_room(f'{name} asks, "{text}"', exclude_self=True)

        if gollum:
            response = riddle_response(gollum)
            if response:
                await ctx.send_room(response)

        return CommandResult.ok()
