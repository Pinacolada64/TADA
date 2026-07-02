"""commands/ban.py — Admin ban/unban management.

Ban entry schema (run/server/net/ban-list.json):
  {
    "<username>": {
      "reason":    "...",
      "banned_by": "...",
      "banned_at": "<iso timestamp>",
      "ban_start": "YYYY-MM-DD",   # optional — ban not active before this date
      "ban_end":   "YYYY-MM-DD"    # optional — ban expires after this date
    }
  }

If ban_start / ban_end are absent the ban is permanent.

The login hook in connect.py calls is_banned() before authenticating.

Ban command syntax
------------------
  ban <user> [reason]                     permanent ban
  ban <user> until <date> [reason]        expires at end of date
  ban <user> from <date> to <date> [reason]   active only in that window
  ban #view                               list all bans
  unban <user>                            remove ban
"""
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext
from parse_date import parse_date, parse_date_range

log = logging.getLogger(__name__)

_BAN_FILE = Path('run') / 'server' / 'net' / 'ban-list.json'


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def load_bans() -> dict:
    """Return the ban list dict (username → entry). Empty dict if file missing."""
    try:
        if _BAN_FILE.exists():
            return json.loads(_BAN_FILE.read_text())
    except Exception:
        log.exception('Failed to load ban list')
    return {}


def save_bans(bans: dict) -> None:
    _BAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BAN_FILE.write_text(json.dumps(bans, indent=2))


# ---------------------------------------------------------------------------
# Ban check (called from connect.py at login)
# ---------------------------------------------------------------------------

def is_banned(username: str) -> tuple[bool, str]:
    """Check whether *username* is currently banned.

    Returns (True, message) if the ban is active, (False, '') otherwise.
    The message is suitable for sending directly to the player.
    """
    bans = load_bans()
    entry = bans.get(username.lower())
    if not entry:
        return False, ''

    today      = date.today()
    reason     = entry.get('reason', '(no reason given)')
    ban_start  = _parse_stored_date(entry.get('ban_start'))
    ban_end    = _parse_stored_date(entry.get('ban_end'))

    # Dated ban — check window
    if ban_start is not None or ban_end is not None:
        if ban_start and today < ban_start:
            # Ban hasn't started yet — let them in (unusual edge case)
            return False, ''
        if ban_end:
            if today > ban_end:
                # Ban has expired
                return False, ''
            return True, (
                f'Your account has been suspended until {ban_end.strftime("%B %d, %Y")}.\n'
                f'Reason: {reason}\n'
                f'You may log in again after that date.'
            )
        # ban_start set but no ban_end — treat as permanent from that date
        return True, f'Your account has been permanently suspended.\nReason: {reason}'

    # No dates — permanent ban
    return True, f'Your account has been permanently suspended.\nReason: {reason}'


def _parse_stored_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------

# Matches "until <date>" at the start of the remainder text after the username.
_UNTIL_RE  = re.compile(r'^until\s+(.+?)(?:\s{2,}|\s*$)(.*)', re.IGNORECASE | re.DOTALL)
# Matches "from <date> to <date>" at the start.
# End date may be multi-word (e.g. "Jul 31 2026"); lazy repetition stops at
# double-space separator or end of string.
_FROM_RE   = re.compile(r'^(from\s+\S.*?\bto\b\s+(?:\S+(?:\s+\S+)*?))(?:\s{2,}|\s*$)(.*)', re.IGNORECASE | re.DOTALL)


def _parse_ban_args(tokens: list[str]) -> tuple[Optional[date], Optional[date], str]:
    """Parse tokens after the username into (ban_start, ban_end, reason).

    Recognised prefixes (case-insensitive):
      until <date>               → ban_start=None, ban_end=<date>
      from <date> to <date>      → ban_start=<date>, ban_end=<date>
      (anything else)            → permanent ban, whole thing is reason
    """
    if not tokens:
        return None, None, '(no reason given)'

    text = ' '.join(tokens)

    # "until <date> [reason]"
    m = _UNTIL_RE.match(text)
    if m:
        date_str, rest = m.group(1).strip(), m.group(2).strip()
        end = parse_date(date_str)
        if end is not None:
            return None, end, rest or '(no reason given)'

    # "from <date> to <date> [reason]"
    m = _FROM_RE.match(text)
    if m:
        range_str, rest = m.group(1).strip(), m.group(2).strip()
        result = parse_date_range(range_str)
        if result is not None:
            start, end = result
            return start, end, rest or '(no reason given)'

    # No date prefix — permanent ban, everything is the reason
    return None, None, text


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class BanCommand(Command):
    name    = 'ban'
    aliases = ['unban']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Ban or unban a player account.',
        description = (
            'Admin only. Bans prevent login at the next connect attempt; '
            'does not disconnect a player who is already online.'
        ),
        category = HelpCategory.ADMINISTRATIVE,
        usage = [
            ('ban <user> [reason]',                       'Permanent ban with optional reason.'),
            ('ban <user> until <date> [reason]',          'Temporary ban expiring at date.'),
            ('ban <user> from <date> to <date> [reason]', 'Ban active only in date window.'),
            ('ban #view',                                 'List all bans (also: ban #list).'),
            ('unban <user>',                              'Remove a ban.'),
        ],
        notes = [
            'Date syntax for temporary bans:',
            '  until Jul 31          expires end of that date',
            '  until 7/31/26         same, numeric form',
            '  from Jul 1 to Jul 31  active only within that window',
            '',
            'Omit a date to make the ban permanent.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        positional, switches = self.parse_args(*args)
        invoked_as = getattr(ctx, '_invoked_as', self.name)

        if invoked_as == 'unban':
            return await self._unban(ctx, positional)

        if '#view' in switches or '#list' in switches:
            return await self._view(ctx)

        if not positional:
            await ctx.send(
                'Usage: ban <user> [reason]  |  ban <user> until <date> [reason]  '
                '|  ban #view  |  unban <user>'
            )
            return CommandResult.fail('No argument.', error='missing_args')

        return await self._ban(ctx, positional)

    # ------------------------------------------------------------------

    async def _ban(self, ctx: GameContext, positional: list) -> CommandResult:
        target = positional[0].lower()
        ban_start, ban_end, reason = _parse_ban_args(positional[1:])

        bans   = load_bans()
        already = target in bans
        entry  = {
            'reason':    reason,
            'banned_by': ctx.player.name,
            'banned_at': datetime.now(timezone.utc).isoformat(),
        }
        if ban_start:
            entry['ban_start'] = ban_start.isoformat()
        if ban_end:
            entry['ban_end'] = ban_end.isoformat()
        bans[target] = entry
        save_bans(bans)

        verb = 'Updated ban on' if already else 'Banned'
        if ban_start and ban_end:
            period = f'{ban_start} to {ban_end}'
        elif ban_end:
            period = f'until {ban_end}'
        elif ban_start:
            period = f'from {ban_start} (permanent)'
        else:
            period = 'permanent'
        await ctx.send(f'{verb} {target} ({period}): {reason}')
        log.warning('ADMIN BAN: %s banned %r period=%s reason=%r',
                    ctx.player.name, target, period, reason)
        return CommandResult.ok()

    async def _unban(self, ctx: GameContext, positional: list) -> CommandResult:
        if not positional:
            await ctx.send('Usage: unban <user>')
            return CommandResult.fail('No username.', error='missing_args')

        target = positional[0].lower()
        bans   = load_bans()
        if target not in bans:
            await ctx.send(f'{target} is not banned.')
            return CommandResult.ok()

        del bans[target]
        save_bans(bans)
        await ctx.send(f'Ban lifted for {target}.')
        log.warning('ADMIN UNBAN: %s unbanned %r', ctx.player.name, target)
        return CommandResult.ok()

    async def _view(self, ctx: GameContext) -> CommandResult:
        bans = load_bans()
        if not bans:
            await ctx.send('No players are currently banned.')
            return CommandResult.ok()

        today = date.today()
        lines = ['', f'Banned accounts ({len(bans)}):', '']
        for username, entry in sorted(bans.items()):
            issued  = entry.get('banned_at', '?')[:10]
            by      = entry.get('banned_by', '?')
            why     = entry.get('reason', '?')
            b_start = _parse_stored_date(entry.get('ban_start'))
            b_end   = _parse_stored_date(entry.get('ban_end'))

            if b_start and b_end:
                period = f'{b_start} – {b_end}'
            elif b_end:
                period = f'until {b_end}'
            elif b_start:
                period = f'from {b_start}'
            else:
                period = 'permanent'

            # Mark expired or not-yet-active bans
            if b_end and today > b_end:
                status = ' [EXPIRED]'
            elif b_start and today < b_start:
                status = ' [pending]'
            else:
                status = ''

            lines.append(f'  {username:<20} issued {issued}  by {by}  {period}{status}')
            lines.append(f'    reason: {why}')
        lines.append('')
        await ctx.send(lines)
        return CommandResult.ok()
