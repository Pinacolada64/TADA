"""commands/groups.py — Manage named groups for whisper and page targeting.

Groups are stored on the player's command_settings and persist across logins.
Reference a group in whisper/page with #groupname as one of the targets.

Usage:
    groups                       — list all your groups
    groups <name>                — show members of a group
    groups #add <group> <player> — add a player to a group (creates it if new)
    groups #remove <group> <player> — remove a player from a group
    groups #delete <group>       — delete an entire group
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import player_exists
from network_context import GameContext


class GroupsCommand(Command):
    name    = 'groups'
    aliases = ['grp', 'group']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Manage named groups for whisper and page targeting.',
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('groups [#list]',                  'List all your groups'),
            ('groups [#list] <name>',           'Show members of a group'),
            ('groups #add <group> <player> [...]', 'Add one or more players to a group'),
            ('groups #remove <group> <player>', 'Remove a player from a group'),
            ('groups #delete <group>',          'Delete an entire group'),
        ],
        examples = [
            ('groups #add friends Alice Bob',     'Add Alice and Bob to group "friends"'),
            ('whisper #friends=Meet me now!',    'Whisper to everyone in "friends"'),
            ('groups #delete friends',           'Delete the "friends" group'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, switches = self.parse_args(*args)
        cs = getattr(ctx.player, 'command_settings', None)
        if cs is None:
            await ctx.send('Command settings not available.')
            return CommandResult.ok()

        if not switches:
            return await self._list(ctx, cs, args)

        sub = switches[0].lstrip('#').lower()
        if sub in ('list', 'ls'):
            return await self._list(ctx, cs, args)
        elif sub == 'add':
            return await self._add(ctx, cs, args)
        elif sub in ('remove', 'rm', 'del'):
            return await self._remove(ctx, cs, args)
        elif sub == 'delete':
            return await self._delete(ctx, cs, args)
        else:
            await ctx.send(f'Unknown option "#{sub}". Use #list, #add, #remove, or #delete.')
            return CommandResult.ok()

    # ------------------------------------------------------------------

    async def _list(self, ctx, cs, args) -> CommandResult:
        if args:
            # Show members of one group
            key     = args[0].lower()
            members = cs.groups.get(key)
            if members is None:
                await ctx.send(f'No group named "{args[0]}".')
                return CommandResult.ok()
            if not members:
                await ctx.send(f'Group "{key}" is empty.')
                return CommandResult.ok()
            lines = [f'Group "{key}":', ''] + [f'  {m}' for m in sorted(members)]
            await ctx.send(lines)
            return CommandResult.ok()

        if not cs.groups:
            await ctx.send('You have no groups.  Use: groups #add <group> <player> [player2 ...]')
            return CommandResult.ok()

        lines = ['Your groups:', '']
        for gname, members in sorted(cs.groups.items()):
            member_str = ', '.join(sorted(members)) if members else '(empty)'
            lines.append(f'  {gname}: {member_str}')
        await ctx.send(lines)
        return CommandResult.ok()

    async def _add(self, ctx, cs, args) -> CommandResult:
        if len(args) < 2:
            await ctx.send('Usage: groups #add <group> <player> [player2 ...]')
            return CommandResult.fail('Missing arguments.')
        group_name   = args[0].lower()
        player_names = args[1:]
        if group_name not in cs.groups:
            cs.groups[group_name] = []
        existing  = [m.lower() for m in cs.groups[group_name]]
        added     = []
        unknown   = []
        for name in player_names:
            if not player_exists(ctx.server, name):
                unknown.append(name)
                continue
            if name.lower() not in existing:
                cs.groups[group_name].append(name)
                existing.append(name.lower())
                added.append(name)
        for name in unknown:
            await ctx.send(f'Unknown player "{name}".')
        if added:
            ctx.player.unsaved_changes = True
            await ctx.send(f'Added {", ".join(added)} to group "{group_name}".')
        elif not unknown:
            # All names were valid but already in the group
            await ctx.send(f'Nobody new to add to group "{group_name}".')
        return CommandResult.ok()

    async def _remove(self, ctx, cs, args) -> CommandResult:
        if len(args) < 2:
            await ctx.send('Usage: groups #remove <group> <player>')
            return CommandResult.fail('Missing arguments.')
        group_name  = args[0].lower()
        player_name = args[1]
        members     = cs.groups.get(group_name)
        if members is None:
            await ctx.send(f'No group named "{group_name}".')
            return CommandResult.ok()
        before = len(members)
        cs.groups[group_name] = [m for m in members if m.lower() != player_name.lower()]
        if len(cs.groups[group_name]) < before:
            ctx.player.unsaved_changes = True
            await ctx.send(f'Removed {player_name} from group "{group_name}".')
        else:
            await ctx.send(f'{player_name} is not in group "{group_name}".')
        return CommandResult.ok()

    async def _delete(self, ctx, cs, args) -> CommandResult:
        if not args:
            await ctx.send('Usage: groups #delete <group>')
            return CommandResult.fail('Missing group name.')
        group_name = args[0].lower()
        if group_name in cs.groups:
            del cs.groups[group_name]
            ctx.player.unsaved_changes = True
            await ctx.send(f'Group "{group_name}" deleted.')
        else:
            await ctx.send(f'No group named "{group_name}".')
        return CommandResult.ok()
