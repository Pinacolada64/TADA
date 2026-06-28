"""commands/page.py — Page a private message to one or more online players.

Syntax:  page <targets>=<message>
Targets: a comma- or space-delimited list of names; quote names that contain
         spaces; use #groupname to address everyone in a saved group.

Unlike whisper, the target does not need to be in the same room.

Examples:
    page Alice=Are you there?
    page Alice,Bob=Party at the inn
    page "Dark Lord"=Surrender now
    page #friends=Where is everyone?
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import parse_targets, expand_groups, find_online
from network_context import GameContext


class PageCommand(Command):
    name    = 'page'
    aliases = ['tell', 'msg', 'p']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Send a private message to one or more online players.',
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('page <name>=<message>',           'Page one player'),
            ('page <name>,<name2>=<message>',   'Page multiple players'),
            ('page #<group>=<message>',         'Page everyone in a group'),
        ],
        examples = [
            ('page Alice=Are you there?',       'Alice receives your page from anywhere'),
            ('page Alice,Bob=Party at the inn', 'Both Alice and Bob receive your page'),
            ('page #friends=Where is everyone?','Everyone in your "friends" group'),
            ('p Bob=Meet me at the inn',        'Alias p works the same way'),
        ],
        notes = ['Use [whisper] to restrict delivery to players in your room.'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        # Don't call parse_args: #groupname tokens start with '#' and would be
        # classified as switches, breaking the targets=message syntax.
        if not args:
            await ctx.send('Page whom?  Usage: page <name[,name2]>=<message>')
            return CommandResult.fail('No arguments.')

        raw = ' '.join(args)

        if '=' not in raw:
            await ctx.send('Usage: page <name[,name2]>=<message>')
            return CommandResult.fail('Missing =.')

        targets_str, _, message = raw.partition('=')
        message = message.strip()

        if not message:
            await ctx.send('Page what?  Usage: page <name[,name2]>=<message>')
            return CommandResult.fail('Missing message.')

        target_names = parse_targets(targets_str)
        if not target_names:
            await ctx.send('Page whom?  Usage: page <name[,name2]>=<message>')
            return CommandResult.fail('Missing target name.')

        my_name = ctx.player.name

        # Remove self from target list silently
        target_names = [n for n in target_names if n.lower() != my_name.lower()]
        if not target_names:
            await ctx.send('You cannot page yourself.')
            return CommandResult.ok()

        # Expand group tokens
        target_names, unknown_groups = expand_groups(ctx.player, target_names)
        for g in unknown_groups:
            await ctx.send(f'You have no group named "{g[1:]}".')

        if not target_names:
            return CommandResult.ok()

        found_ctxs, not_found = find_online(ctx, target_names)
        for n in not_found:
            await ctx.send(f'{n} is not online.')

        if not found_ctxs:
            return CommandResult.ok()

        names_str = ', '.join(tctx.player.name for tctx in found_ctxs)
        await ctx.send(f'You page {names_str}, "{message}"')
        for tctx in found_ctxs:
            await tctx.send(f'{my_name} pages you, "{message}"')

        return CommandResult.ok()
