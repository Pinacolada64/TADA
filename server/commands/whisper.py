"""commands/whisper.py — Whisper a private message to one or more players in the same room.

Syntax:  whisper <targets>=<message>
Targets: a comma- or space-delimited list of names; quote names that contain
         spaces; use #groupname to address everyone in a saved group.

Use #reply (or #r) as the target to whisper back to whoever you last
whispered with, without retyping their name -- the last correspondent is
remembered in CommandSettings.last_whispered.

Examples:
    whisper Bob=Did you see that?
    whisper Alice,Bob=Let's sneak out
    whisper "Dark Lord"=I come in peace
    whisper #friends=Meet at the inn
    whisper #r=me too
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import (
    parse_targets, expand_groups, find_online, substitute_reply,
)
from network_context import GameContext


class WhisperCommand(Command):
    name    = 'whisper'
    # can't be 'w' — that's an alias for 'go west'
    aliases = ['wh']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Whisper a private message to one or more players in your room.',
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('whisper <name>=<message>',           'Whisper to one player'),
            ('whisper <name>,<name2>=<message>',   'Whisper to multiple players'),
            ('whisper #<group>=<message>',         'Whisper to everyone in a group'),
            ('whisper #r=<message>',               'Whisper back to your last correspondent'),
        ],
        examples = [
            ('whisper Bob=Did you see that?',      "WHISPER sends a message only the "
                                                    "named target(s) can see, unlike SAY "
                                                    "-- everyone else in the room stays "
                                                    "unaware you said anything. Only Bob "
                                                    "hears this one, and only because "
                                                    "he's in the same room as you (use "
                                                    "PAGE instead for cross-room "
                                                    "messages)."),
            ('whisper Alice,Bob=Lets go',          'Comma-separate names to whisper the '
                                                    'same message to several people at '
                                                    'once, same as PAGE.'),
            ('whisper #friends=Meet at the inn',   'A saved GROUPS name works as a '
                                                    'target too, whispering to everyone '
                                                    'in it who happens to be in the room '
                                                    'with you.'),
            ('whisper #r=me too',                  "'#reply' (or '#r') stands in for the "
                                                    'last player you whispered with -- '
                                                    'either direction -- so you can '
                                                    "answer without retyping their name."),
        ],
        notes = ['Target must be in the same room.  Use [page] for cross-room messages.'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        # Don't call parse_args: #groupname tokens start with '#' and would be
        # classified as switches, breaking the targets=message syntax.
        if not args:
            await ctx.send('Whisper to whom?  Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('No arguments.')

        raw = ' '.join(args)

        if '=' not in raw:
            await ctx.send('Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('Missing =.')

        targets_str, _, message = raw.partition('=')
        message = message.strip()

        if not message:
            await ctx.send('Whisper what?  Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('Missing message.')

        target_names = parse_targets(targets_str)
        if not target_names:
            await ctx.send('Whisper to whom?  Usage: whisper <name[[,name2]]>=<message>')
            return CommandResult.fail('Missing target name.')

        # '#reply' / '#r' -> whoever you last whispered with
        target_names, unresolved_reply = substitute_reply(
            target_names, ctx.player.command_settings.last_whispered)
        if unresolved_reply:
            await ctx.send("You haven't whispered with anyone yet.")
            return CommandResult.fail('No one to reply to.')

        my_name = ctx.player.name

        # Remove self from target list silently
        target_names = [n for n in target_names if n.lower() != my_name.lower()]
        if not target_names:
            await ctx.send('You mutter to yourself, but no one notices.')
            return CommandResult.ok()

        # Expand group tokens
        target_names, unknown_groups = expand_groups(ctx.player, target_names)
        for g in unknown_groups:
            await ctx.send(f'You have no group named "{g[1:]}".')

        if not target_names:
            return CommandResult.ok()

        found_ctxs, not_found = find_online(ctx, target_names, same_room_only=True)
        for n in not_found:
            await ctx.send(f'{n} is not here.')

        if not found_ctxs:
            return CommandResult.ok()

        names_str = ', '.join(tctx.player.name for tctx in found_ctxs)
        await ctx.send(f'You whisper to {names_str}, "{message}"')
        for tctx in found_ctxs:
            await tctx.send(f'{my_name} whispers to you, "{message}"')
            # Recipient's '#reply' now points back at the sender.
            tctx.player.command_settings.last_whispered = my_name
            tctx.player.unsaved_changes = True

        # Sender's '#reply' points at the last person actually reached.
        ctx.player.command_settings.last_whispered = found_ctxs[-1].player.name
        ctx.player.unsaved_changes = True

        return CommandResult.ok()
