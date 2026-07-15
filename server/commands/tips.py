"""commands/tips.py — Tip of the day, ported from SPUR-data/tips.txt.

  tips        — show the next tip (cycles through tips.json, wrapping
                back to the first after the last)
  tips #on    — show a tip automatically at login (default)
  tips #off   — stop showing a tip at login; 'tips' still works manually

Login-time display is commands/connect.py's _login_tip_lines(), which
calls tips.py's next_tip() directly (same convention as
_login_news_lines()/news.py) -- both advance the same
command_settings.tips.tip_number cursor, so a session's login tip and a
manually-typed 'tips' right after don't repeat the same one.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from tips import format_tip_box, load_tips, next_tip


class TipsCommand(Command):
    name    = 'tips'
    aliases = ['tip']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Show a tip of the day.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('tips',     'Show the next tip.'),
            ('tips #on',  'Show a tip automatically each time you log in.'),
            ('tips #off', 'Stop showing a tip at login (tips still works manually).'),
        ],
        examples = [
            ('tips',     'Read the next tip.'),
            ('tips #off', "Don't show a tip at login."),
        ],
        description = (
            "Cycles through a list of gameplay tips (ported from SPUR's own "
            'tip screen). Each call to TIPS shows the next one in order, '
            'wrapping back to the first after the last.'
        ),
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        _positional, switches = self.parse_args(*args)
        player = ctx.player

        if '#on' in switches:
            player.command_settings.tips.enabled = True
            player.unsaved_changes = True
            await ctx.send('Tips will be shown when you log in.')
            return CommandResult.ok('Tips enabled.')

        if '#off' in switches:
            player.command_settings.tips.enabled = False
            player.unsaved_changes = True
            await ctx.send("Tips won't be shown when you log in. (TIPS still works any time.)")
            return CommandResult.ok('Tips disabled.')

        all_tips = load_tips()
        tip = next_tip(player)
        if tip is None:
            await ctx.send('No tips available.')
            return CommandResult.fail('No tips loaded.', error='no_tips')

        box = format_tip_box(ctx, tip, player.command_settings.tips.tip_number, len(all_tips))
        await ctx.send('', *box, '')
        return CommandResult.ok('Showed a tip.')
