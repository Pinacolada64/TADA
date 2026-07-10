"""commands/page.py — Page a private message to one or more online players.

Syntax:
  page <targets>=<message>   send a page (targets: comma/space-delimited
                              names, quote names with spaces, #groupname
                              to address a saved group -- see
                              commands/groups.py)
  page #ignore <name>        block <name> from paging you
  page #unignore <name>      remove that block
  page #haven                block ALL incoming pages
  page #unhaven               allow pages again

#ignore/#unignore/#haven/#unhaven are reserved control words, so a saved
group cannot be named "ignore", "unignore", "haven", or "unhaven".

If a target isn't currently online, offers to leave the message as mail
for them. Mail *reading* isn't implemented yet (no `mail` command exists
-- see MECHANICS.md's "Mail / Paging" section and TODO.md) but this still
persists it to run/server/mail/<name>.json in the schema that section
already specifies, so a future `mail` command has something to read.

Examples:
    page Alice=Are you there?
    page Alice,Bob=Party at the inn
    page "Dark Lord"=Surrender now
    page #friends=Where is everyone?
    page #ignore Bob
    page #haven
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from commands.messaging import parse_targets, expand_groups, find_online, player_exists, is_in_combat
from network_context import GameContext

_CONTROL_WORDS = {'#ignore', '#unignore', '#haven', '#unhaven'}

_MAIL_DIR = Path('run') / 'server' / 'mail'


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
            ('page #ignore <name>',             'Block <name> from paging you'),
            ('page #unignore <name>',           'Remove that block'),
            ('page #haven',                     'Block all incoming pages'),
            ('page #unhaven',                   'Allow pages again'),
        ],
        examples = [
            ('page Alice=Are you there?',       'Alice receives your page from anywhere'),
            ('page Alice,Bob=Party at the inn', 'Both Alice and Bob receive your page'),
            ('page #friends=Where is everyone?','Everyone in your "friends" group'),
            ('p Bob=Meet me at the inn',        'Alias p works the same way'),
            ('page #ignore Bob',                'Bob can no longer page you'),
            ('page #haven',                     'Nobody can page you until #unhaven'),
        ],
        notes = [
            'Use [whisper] to restrict delivery to players in your room.',
            'If a target is offline, you will be offered to leave the message as mail.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not args:
            await ctx.send('Page whom?  Usage: page <name[,name2]>=<message>')
            return CommandResult.fail('No arguments.')

        first = args[0].lower()
        if first in _CONTROL_WORDS:
            return await self._control(ctx, first, args[1:])

        return await self._send_page(ctx, args)

    # ------------------------------------------------------------------
    # #ignore / #unignore / #haven / #unhaven
    # ------------------------------------------------------------------

    async def _control(self, ctx: GameContext, word: str, rest: tuple) -> CommandResult:
        cs = ctx.player.command_settings

        if word == '#haven':
            cs.haven = True
            ctx.player.unsaved_changes = True
            await ctx.send('You will no longer receive pages. (page #unhaven to undo)')
            return CommandResult.ok('Haven on.')

        if word == '#unhaven':
            cs.haven = False
            ctx.player.unsaved_changes = True
            await ctx.send('You can receive pages again.')
            return CommandResult.ok('Haven off.')

        if not rest:
            await ctx.send(f'Usage: page {word} <name>')
            return CommandResult.fail('Missing name.', error='missing_args')

        name = ' '.join(rest).strip()
        key  = name.lower()

        if word == '#ignore':
            if key not in (n.lower() for n in cs.ignored_pagers):
                cs.ignored_pagers.append(name)
                ctx.player.unsaved_changes = True
            await ctx.send(f'You will no longer receive pages from {name}.')
            return CommandResult.ok('Ignored.')

        # #unignore
        before = len(cs.ignored_pagers)
        cs.ignored_pagers = [n for n in cs.ignored_pagers if n.lower() != key]
        if len(cs.ignored_pagers) != before:
            ctx.player.unsaved_changes = True
        await ctx.send(f'{name} can page you again.')
        return CommandResult.ok('Unignored.')

    # ------------------------------------------------------------------
    # Sending a page
    # ------------------------------------------------------------------

    async def _send_page(self, ctx: GameContext, args: tuple) -> CommandResult:
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

        deliverable = []
        for tctx in found_ctxs:
            tcs     = getattr(tctx.player, 'command_settings', None)
            haven   = getattr(tcs, 'haven', False) if tcs else False
            ignored = getattr(tcs, 'ignored_pagers', []) if tcs else []
            if haven:
                await ctx.send(f'{tctx.player.name} is not accepting pages right now.')
                continue
            if my_name.lower() in (n.lower() for n in ignored):
                await ctx.send(f'{tctx.player.name} is ignoring your pages.')
                continue
            deliverable.append(tctx)

        for n in not_found:
            await self._offer_mail(ctx, n, message)

        if not deliverable:
            return CommandResult.ok()

        names_str = ', '.join(tctx.player.name for tctx in deliverable)
        await ctx.send(f'You page {names_str}, "{message}"')

        queued_names = []
        for tctx in deliverable:
            if is_in_combat(tctx):
                # Queue instead of interrupting mid-fight -- surfaced as
                # "[PAGE] ..." lines the next time they're prompted (see
                # network_context.py's _pop_pending_pages()).
                pending = getattr(tctx.player, 'pending_pages', None)
                if pending is None:
                    pending = []
                    tctx.player.pending_pages = pending
                pending.append(f'{my_name} pages you, "{message}"')
                await tctx.send('You sense you have a page waiting for you.')
                queued_names.append(tctx.player.name)
            else:
                await tctx.send(f'{my_name} pages you, "{message}"')

        if queued_names:
            await ctx.send(f'({", ".join(queued_names)} {"is" if len(queued_names) == 1 else "are"} '
                            f'in combat -- your page will show up for them after.)')

        return CommandResult.ok()

    # ------------------------------------------------------------------
    # Offline fallback
    # ------------------------------------------------------------------

    async def _offer_mail(self, ctx: GameContext, name: str, message: str) -> None:
        """*name* isn't online -- offer to leave the page as mail for them."""
        if not player_exists(ctx.server, name):
            await ctx.send(f'{name} is not online, and no such player exists.')
            return

        await ctx.send(f'{name} is not online.')
        raw = await ctx.prompt(f'Leave this as a mail message for {name}? (y/N)')
        if not raw or raw.strip().lower() not in ('y', 'yes'):
            return

        _MAIL_DIR.mkdir(parents=True, exist_ok=True)
        mail_file = _MAIL_DIR / f'{name.lower()}.json'
        try:
            inbox = json.loads(mail_file.read_text()) if mail_file.exists() else []
        except Exception:
            inbox = []
        inbox.append({
            'from':      ctx.player.name,
            'timestamp': datetime.datetime.now().isoformat(),
            'body':      message,
            'read':      False,
        })
        mail_file.write_text(json.dumps(inbox, indent=2))
        await ctx.send(f"Message left for {name}. (There's no `mail` command yet to read it -- see TODO.md.)")
