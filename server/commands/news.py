"""commands/news.py — The NEWS command: bulletin-board style announcements.

Design per MECHANICS.md's "News & Mail" > "News / Bulletin Board" section.
Storage/visibility rules live in news.py (top-level); this module is just
the in-game command surface:

  news                 — list currently-active items (title + id + date)
  news <id>            — read one item in full, marks 'once' items seen
  news post            — (admin) write a new item
  news edit <id>       — (admin) change an existing item's body/lifetime
  news delete <id>     — (admin) remove an item

Login-time display ("what's new since you last logged in") is handled by
commands/connect.py, which calls the same news.py helpers this command uses
so the two stay in sync.

Post authoring here is a plain END-terminated multi-line prompt (same
convention as threaded_messages.py's create_new_thread()) rather than the
real line-editor in the not-yet-merged `text_editor` branch
(server/text_editor/*.py) -- swap this out once that branch lands. See
TODO.md.
"""
from __future__ import annotations

import datetime
import logging

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
import news as news_store
from formatting import hrule_char, make_rule

log = logging.getLogger(__name__)

# Width of the "Date" column in the news listing (ISO-8601 "YYYY-MM-DD" is
# 10 chars; the extra 3 columns of padding is what pushes "Title" over).
_DATE_COL_WIDTH = 13


class NewsCommand(Command):
    name    = 'news'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Read the news / bulletin board.',
        description = (
            'Lists currently-active news items. Pick one by number to read '
            'it in full. Admins can post, edit, and delete items here too.'
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('news',            'List currently-active news items.'),
            ('news <id>',       'Read one item in full.'),
            ('news post',       '(Admin) Write a new news item.'),
            ('news edit <id>',  '(Admin) Edit an existing item.'),
            ('news delete <id>', '(Admin) Remove an item.'),
        ],
        notes = [
            "Whether NEWS shows just what's new since your last login or "
            "a full directory every time is controlled by PREFS (key N).",
            "Bare 'news' stays in the listing -- press Enter with no "
            "number to leave it.",
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)
        sub = positional[0].lower() if positional else ''

        if sub == 'post':
            return await self._post(ctx)
        if sub == 'edit' and len(positional) > 1:
            return await self._edit(ctx, positional[1])
        if sub == 'delete' and len(positional) > 1:
            return await self._delete(ctx, positional[1])
        if positional and positional[0].isdigit():
            return await self._read_one(ctx, int(positional[0]))

        return await self._list(ctx)

    # ------------------------------------------------------------------
    # Player-facing
    # ------------------------------------------------------------------

    async def _list(self, ctx) -> CommandResult:
        """Show the news listing and stay in it -- reading an item just
        redisplays the listing -- until the player presses Enter to leave.
        While active, the player's virtual location (commands/whereat.py)
        reads 'Reading news'.
        """
        items = news_store.load_news()
        today = datetime.date.today()
        visible = [it for it in items if news_store.is_visible(it, ctx.player.name, today)]

        if not visible:
            await ctx.send('No news right now.')
            return CommandResult.ok('No news.')

        previous_location = getattr(ctx.client, 'virtual_location', None)
        ctx.client.virtual_location = 'Reading news'
        try:
            while True:
                items = news_store.load_news()
                visible = [it for it in items if news_store.is_visible(it, ctx.player.name, today)]
                if not visible:
                    await ctx.send('No more news to read.')
                    return CommandResult.ok('No news.')

                rule_width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
                lines = [
                    '', '|yellow|News|reset|', '',
                    f"  Num  {'Date':<{_DATE_COL_WIDTH}}Title",
                    make_rule(rule_width, hrule_char(ctx)),
                ]
                for it in visible:
                    posted = it.get('posted_at', '')[:10]
                    lines.append(f"  {it['id']:>3}. {posted:<{_DATE_COL_WIDTH}}{it.get('title', '(untitled)')}")
                lines.append('')

                raw = await ctx.prompt(
                    f'Read which (# or {ctx.player.return_key} to exit)',
                    preamble_lines=lines,
                )
                if raw is None or not raw.strip():
                    return CommandResult.ok('Exited news.')

                choice = raw.strip()
                if choice.isdigit():
                    await self._read_one(ctx, int(choice))
                else:
                    await ctx.send(f"'{choice}' is not a valid news id.")
        finally:
            ctx.client.virtual_location = previous_location

    async def _read_one(self, ctx, item_id: int) -> CommandResult:
        items = news_store.load_news()
        item = next((it for it in items if it.get('id') == item_id), None)
        if item is None:
            await ctx.send('No such news item.')
            return CommandResult.fail('Unknown news item.', error='not_found')

        await ctx.send([''] + news_store.format_item(item) + [''])

        if item.get('lifetime') == 'once':
            news_store.mark_seen(item, ctx.player.name)
            news_store.save_news(items)

        return CommandResult.ok('Displayed news item.')

    # ------------------------------------------------------------------
    # Admin-only
    # ------------------------------------------------------------------

    def _require_admin(self, ctx) -> bool:
        return bool(ctx.player.query_flag(PlayerFlags.ADMIN))

    async def _post(self, ctx) -> CommandResult:
        if not self._require_admin(ctx):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        title = await ctx.prompt('Title')
        if not title or not title.strip():
            await ctx.send('Cancelled — no title given.')
            return CommandResult.fail('No title.', error='missing_title')

        lifetime = await self._pick_lifetime(ctx)
        if lifetime is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        await ctx.send("Enter the news body. Type 'END' alone on a line to finish.")
        body = await self._read_body(ctx)

        items = news_store.load_news()
        item = {
            'id':         news_store.next_id(items),
            'title':      title.strip(),
            'body':       body,
            'author':     ctx.player.name,
            'posted_at':  datetime.datetime.now().isoformat(),
            'lifetime':   lifetime['lifetime'],
            'seen_by':    [],
        }
        if lifetime['lifetime'] == 'range':
            item['start_date'] = lifetime['start_date']
            item['end_date']   = lifetime['end_date']

        items.append(item)
        news_store.save_news(items)
        await ctx.send(f"News item #{item['id']} posted.")
        log.info('ADMIN NEWS POST: %s posted news #%s %r', ctx.player.name, item['id'], title)
        return CommandResult.ok('Posted news item.')

    async def _edit(self, ctx, id_str: str) -> CommandResult:
        if not self._require_admin(ctx):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        if not id_str.isdigit():
            await ctx.send('Usage: news edit <id>')
            return CommandResult.fail('Bad id.', error='bad_args')

        items = news_store.load_news()
        item = next((it for it in items if it.get('id') == int(id_str)), None)
        if item is None:
            await ctx.send('No such news item.')
            return CommandResult.fail('Unknown news item.', error='not_found')

        await ctx.send(f"Editing #{item['id']}: {item.get('title', '')}")
        title = await ctx.prompt(f"Title [{item.get('title', '')}]")
        if title and title.strip():
            item['title'] = title.strip()

        lifetime = await self._pick_lifetime(ctx, allow_skip=True)
        if lifetime is not None:
            item['lifetime'] = lifetime['lifetime']
            if lifetime['lifetime'] == 'range':
                item['start_date'] = lifetime['start_date']
                item['end_date']   = lifetime['end_date']
            else:
                item.pop('start_date', None)
                item.pop('end_date', None)

        await ctx.send("Enter the new body ('END' alone to finish), or type END "
                       "immediately to keep the current text.")
        body = await self._read_body(ctx)
        if body:
            item['body'] = body

        news_store.save_news(items)
        await ctx.send(f"News item #{item['id']} updated.")
        log.info('ADMIN NEWS EDIT: %s edited news #%s', ctx.player.name, item['id'])
        return CommandResult.ok('Updated news item.')

    async def _delete(self, ctx, id_str: str) -> CommandResult:
        if not self._require_admin(ctx):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        if not id_str.isdigit():
            await ctx.send('Usage: news delete <id>')
            return CommandResult.fail('Bad id.', error='bad_args')

        items = news_store.load_news()
        item = next((it for it in items if it.get('id') == int(id_str)), None)
        if item is None:
            await ctx.send('No such news item.')
            return CommandResult.fail('Unknown news item.', error='not_found')

        items.remove(item)
        news_store.save_news(items)
        await ctx.send(f"News item #{item['id']} deleted.")
        log.info('ADMIN NEWS DELETE: %s deleted news #%s', ctx.player.name, item['id'])
        return CommandResult.ok('Deleted news item.')

    # ------------------------------------------------------------------
    # Authoring helpers
    # ------------------------------------------------------------------

    async def _pick_lifetime(self, ctx, allow_skip: bool = False) -> dict | None:
        from parse_date import parse_date_range

        prompt_extra = ' (or Enter to keep current)' if allow_skip else ''
        raw = await ctx.prompt(
            'Lifetime',
            preamble_lines=[
                '',
                'How long should this item be shown?',
                "  once       - shown once per player, then suppressed",
                "  permanent  - always shown until deleted",
                "  <daterange> - active only in a date window, e.g. 'Jul 1 to Jul 31'",
                '',
            ],
        )
        if raw is None:
            return None
        ans = raw.strip()
        if not ans:
            return None if allow_skip else {'lifetime': 'permanent'}

        low = ans.lower()
        if low == 'once':
            return {'lifetime': 'once'}
        if low == 'permanent':
            return {'lifetime': 'permanent'}

        date_range = parse_date_range(ans)
        if date_range is not None:
            start, end = date_range
            return {'lifetime': 'range', 'start_date': start.isoformat(), 'end_date': end.isoformat()}

        await ctx.send("Didn't understand that — defaulting to 'permanent'.")
        return {'lifetime': 'permanent'}

    async def _read_body(self, ctx) -> list[str]:
        """Multi-line body entry, terminated by a lone 'END' line."""
        lines: list[str] = []
        while True:
            raw = await ctx.prompt('')
            if raw is None or raw.strip().upper() == 'END':
                break
            lines.append(raw)
        return lines
