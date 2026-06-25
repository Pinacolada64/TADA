"""commands/who.py — List online players with connection and idle times."""
from datetime import datetime, timedelta

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext


def _fmt_delta(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    h, rem = divmod(total, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f'{h}h {m:02d}m'
    if m:
        return f'{m}m {s:02d}s'
    return f'{s}s'


class WhoCommand(Command):
    name    = 'who'
    aliases = []
    modes   = {Mode.GAME, Mode.LOGIN}

    help = Help(
        summary     = 'List currently online players.',
        description = (
            'Shows each connected player with how long they have been online '
            'and how long since they last typed a command. '
            'Admins also see the IP address of each connection.'
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [('who', 'List online players')],
        examples = [('who', 'Show the online roster')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        now      = datetime.now()
        player   = ctx.player
        is_admin = player.query_flag(PlayerFlags.ADMIN)

        clients = getattr(ctx.server, 'clients', {})

        rows = []
        for client in clients.values():
            client_player = getattr(getattr(client, 'ctx', None), 'player', None)
            name = getattr(client_player, 'name', None) or 'Unknown'

            connected_at = getattr(client, 'connected_at', None)
            last_input   = getattr(client, 'last_input',   None)

            connected_str = _fmt_delta(now - connected_at) if connected_at else '?'
            idle_str      = _fmt_delta(now - last_input)   if last_input   else '?'

            rows.append((name, connected_str, idle_str, client))

        rows.sort(key=lambda r: r[0].lower())

        lines = []
        if is_admin:
            lines.append(f"{'Name':<16} {'Online':>8}  {'Idle':>8}  IP")
            lines.append('-' * 48)
        else:
            lines.append(f"{'Name':<16} {'Online':>8}  {'Idle':>8}")
            lines.append('-' * 36)

        if not rows:
            lines.append('  No players online.')
        else:
            for name, connected_str, idle_str, client in rows:
                line = f'{name:<16} {connected_str:>8}  {idle_str:>8}'
                if is_admin:
                    addr = getattr(client, 'addr', None)
                    ip   = addr[0] if isinstance(addr, (tuple, list)) and addr else str(addr or '?')
                    line += f'  {ip}'
                lines.append(line)

        lines.append('')
        lines.append(f'{len(rows)} player(s) online.')

        await ctx.send(lines)
        return CommandResult.ok()
