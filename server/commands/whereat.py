"""commands/whereat.py — Show where all online players are located."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext, GuestPlayer
from flags import PlayerFlags


def _is_privileged(player) -> bool:
    return (player.query_flag(PlayerFlags.ADMIN)
            or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _location_columns(client, server) -> tuple[str, str, str]:
    """Resolve (level, room #, room name) column values for a connected
    client. Virtual locations (bar/shoppe/elevator/guild HQ/etc --
    presence.py's enter_area()) have no level or room number of their
    own -- shown as '-' in those columns, with the virtual location's
    own label in the room-name column."""
    vl = getattr(client, 'virtual_location', None)
    if vl:
        return ('-', '-', vl)
    ctx = getattr(client, 'ctx', None)
    player = getattr(ctx, 'player', None)
    room_no = getattr(client, 'room', None) or getattr(player, 'map_room', None)
    if room_no is not None and getattr(server, 'game_map', None):
        level = int(getattr(player, 'map_level', 1) or 1)
        room = server.game_map.get_room(level, int(room_no))
        if room:
            return (str(level), str(room_no), room.name)
    return ('-', '-', '(unknown)')


class WhereatCommand(Command):
    name    = 'whereat'
    aliases = ['wa']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Show where all online players are located.',
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('whereat',       'List all visible online players and their locations'),
            ('wa #hide',      'Hide your location from other players'),
            ('wa #show',      'Make your location visible again'),
        ],
        notes = [
            'Admins and Dungeon Masters always see everyone\'s true location.',
            'Hidden players appear as "(Hidden)" to other players.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, switches = self.parse_args(*args)
        player = ctx.player

        # Sub-commands: #hide / #show (routed into switches by parse_args)
        if switches:
            sub = switches[0].lstrip('#').lower()
            cs = getattr(player, 'command_settings', None)
            if cs is None:
                await ctx.send('Command settings not available.')
                return CommandResult.ok()
            if sub == 'hide':
                cs.whereat_hidden = True
                player.unsaved_changes = True
                await ctx.send('Your location is now hidden from other players.')
            elif sub == 'show':
                cs.whereat_hidden = False
                player.unsaved_changes = True
                await ctx.send('Your location is now visible to other players.')
            else:
                await ctx.send(f'Unknown option "#{sub}". Use #hide or #show.')
            return CommandResult.ok()

        privileged = _is_privileged(player)
        server     = ctx.server

        rows = []
        for client in server.clients.values():
            peer_ctx    = getattr(client, 'ctx', None)
            peer_player = getattr(peer_ctx, 'player', None)
            if peer_player is None or isinstance(peer_player, GuestPlayer):
                continue

            peer_cs     = getattr(peer_player, 'command_settings', None)
            is_hidden   = getattr(peer_cs, 'whereat_hidden', False)
            name        = getattr(peer_player, 'name', '???')

            if is_hidden and not privileged:
                level, room_no, room_name = '-', '-', '(Hidden)'
            else:
                level, room_no, room_name = _location_columns(client, server)
                if is_hidden:
                    room_name += ' [hidden]'   # admin hint that the player is hiding

            rows.append((name, level, room_no, room_name))

        if not rows:
            await ctx.send('No players are currently online.')
            return CommandResult.ok()

        rows.sort(key=lambda r: r[0].lower())
        name_w  = min(max(len('Player'), *(len(r[0]) for r in rows)) + 2, 20)
        level_w = max(len('Level'), *(len(r[1]) for r in rows)) + 2
        room_w  = max(len('Room #'), *(len(r[2]) for r in rows)) + 2

        from formatting import hrule_char, underline
        width = 78
        try:
            width = ctx.player.client_settings.screen_columns
        except AttributeError:
            pass

        lines = [*underline('Whereat', ctx), '']
        lines.append(f"{'Player'.ljust(name_w)}{'Level'.ljust(level_w)}"
                     f"{'Room #'.ljust(room_w)}Room Name")
        for name, level, room_no, room_name in rows:
            lines.append(f'{name.ljust(name_w)}{level.ljust(level_w)}'
                         f'{room_no.ljust(room_w)}{room_name}')
        lines.append('')

        await ctx.send(lines)
        return CommandResult.ok()
