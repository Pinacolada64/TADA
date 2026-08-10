"""commands/whereat.py — Show where all online players are located."""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext, GuestPlayer
from flags import PlayerFlags
from formatting import underline


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
        summary  = 'Show where all online players are located. '
                   'You may hide your location from other players if you wish.',
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('whereat',       'List all visible online players and their locations'),
            ('wa #hide',      'Hide your location from other players'),
            ('wa #show',      'Make your location visible again'),
            ('wa #population', 'Show a room-by-room population summary instead of a player list'),
        ],
        notes = [
            'Other players may see the room name.',
            'Hidden players appear as "(Hidden)" to other players.',
        ],
        admin_notes = ["Admins and Dungeon Masters see everyone's level #, room #, and "
                       "room name even if the player is hiding from others."]
        )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, switches = self.parse_args(*args)
        player = ctx.player

        # Sub-commands: #hide / #show / #pop (routed into switches by parse_args)
        if switches:
            sub = switches[0].lstrip('#').lower()
            if sub in ('pop', 'population'):
                return await self._show_population(ctx, player)
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
                await ctx.send(f'Unknown option "#{sub}". Use #hide, #show, or #population.')
            return CommandResult.ok()

        privileged = _is_privileged(player)
        server     = ctx.server
        rows = [r[:4] for r in self._gather_rows(server, privileged)]

        if not rows:
            await ctx.send('No players are currently online.')
            return CommandResult.ok()

        rows.sort(key=lambda r: r[0].lower())
        name_w = min(max(len('Player'), *(len(r[0]) for r in rows)) + 2, 20)

        lines = [*underline('Whereat', ctx), '']
        if privileged:
            level_w = max(len('Level'), *(len(r[1]) for r in rows)) + 2
            room_w  = max(len('Room #'), *(len(r[2]) for r in rows)) + 2
            lines.append(f"{'Player'.ljust(name_w)}{'Level'.ljust(level_w)}"
                         f"{'Room #'.ljust(room_w)}Room Name")
            for name, level, room_no, room_name in rows:
                lines.append(f'{name.ljust(name_w)}{level.ljust(level_w)}'
                             f'{room_no.ljust(room_w)}{room_name}')
        else:
            lines.append(f"{'Player'.ljust(name_w)}Room Name")
            for name, level, room_no, room_name in rows:
                lines.append(f'{name.ljust(name_w)}{room_name}')
        lines.append('')

        await ctx.send(lines)
        return CommandResult.ok()

    @staticmethod
    def _gather_rows(server, privileged: bool) -> list[tuple[str, str, str, str, bool]]:
        """Collect (name, level, room #, room name, is_hidden) for every
        visible online player."""
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

            rows.append((name, level, room_no, room_name, is_hidden))
        return rows

    async def _show_population(self, ctx: GameContext, player) -> CommandResult:
        """'wa #pop' -- room-by-room population summary. Admins/DMs see
        Level, Room #, and Population; everyone else sees Room Name and
        Population. Rooms with more than one occupant show an aggregate
        count; hidden players (as seen by non-privileged viewers) are
        bucketed together under '(Hidden)' rather than de-anonymized."""
        privileged = _is_privileged(player)
        server     = ctx.server
        rows       = [r[:4] for r in self._gather_rows(server, privileged)]

        if not rows:
            await ctx.send('No players are currently online.')
            return CommandResult.ok()

        counts: dict[tuple, int] = {}
        order: list[tuple] = []
        for _name, level, room_no, room_name in rows:
            key = (level, room_no, room_name)
            if key not in counts:
                counts[key] = 0
                order.append(key)
            counts[key] += 1

        order.sort(key=lambda k: (k[0], k[1], k[2].lower()))

        lines = [*underline('Whereat - Population', ctx), '']
        if privileged:
            level_w = max(len('Level'), *(len(k[0]) for k in order)) + 2
            room_w  = max(len('Room #'), *(len(k[1]) for k in order)) + 2
            lines.append(f"{'Level'.ljust(level_w)}{'Room #'.ljust(room_w)}Population")
            for key in order:
                level, room_no, _room_name = key
                lines.append(f'{level.ljust(level_w)}{room_no.ljust(room_w)}{counts[key]}')
        else:
            name_w = max(len('Room Name'), *(len(k[2]) for k in order)) + 2
            lines.append(f"{'Room Name'.ljust(name_w)}Population")
            for key in order:
                _level, _room_no, room_name = key
                lines.append(f'{room_name.ljust(name_w)}{counts[key]}')
        lines.append('')

        await ctx.send(lines)
        return CommandResult.ok()
