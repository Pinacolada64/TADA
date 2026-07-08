"""commands/prefs.py

Player preferences menu — available in both LOGIN and GAME modes so new
players see it during character creation and existing players can reach it
any time with the PREFS command.

Entry points
------------
PrefsCommand.execute()  — command dispatch (returns CommandResult)
prefs_menu(ctx)         — standalone coroutine used by new_player._edit_settings();
                          returns True on normal exit, False on disconnect.

Settings managed here
---------------------
  X  Expert Mode      PlayerFlags.EXPERT_MODE    (On / Off)
  H  Clock Display    PlayerFlags.HOURGLASS      (On / Off)
                      — just shows/hides a clock; doesn't yet control
                        12-hour (AM/PM) vs 24-hour format or timezone.
                        TODO: add those as real settings.
  M  More Prompt      PlayerFlags.MORE_PROMPT    (On / Off) — pause between
                      screenfuls of output; also toggleable via the
                      standalone 'mp' command (commands/more_prompt.py)
  B  Border Style     ctx.player.border_style    (ascii / single / double)
                      — ANSI terminals only; PETSCII has one fixed style
  C  Colors           client_settings.colors.text_color
                      client_settings.colors.highlight_color
"""

from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags

# Detailed per-setting explanations shown by typing 'h' + the setting's key
# (e.g. 'hx', 'hb') at the prefs menu prompt -- one entry per key in
# prefs_menu()'s valid_keys, keyed by lowercase letter.
_SETTING_HELP: dict[str, list[str]] = {
    'x': [
        '',
        '|yellow|Expert Mode|reset|',
        "Hides beginner-oriented tips, hints, and confirmation text "
        "throughout the game once you're comfortable with the commands. "
        "Affects things like READY's weapon-class breakdown and various "
        "menu prompts -- the underlying commands work the same either way.",
        '',
    ],
    'h': [
        '',
        '|yellow|Hourglass Display|reset|',
        "Shows the current time in front of your command prompt. Purely "
        "a visual clock -- it doesn't yet affect in-game time limits or "
        "control 12-hour (AM/PM) vs 24-hour formatting or timezone.",
        '',
    ],
    'm': [
        '',
        '|yellow|More Prompt|reset|',
        "When output would be longer than one screen, pauses with a "
        "'-- More --' prompt between pages: Enter for the next page, "
        "B or - to go back a page, Q to stop reading early. When off, "
        "everything is sent at once and scrolls by regardless of length. "
        "Same setting as the standalone 'mp' command.",
        '',
    ],
    'b': [
        '',
        '|yellow|Border Style|reset|',
        "Controls the box-drawing characters used around tables and "
        "boxed text (ASCII, Single-line, or Double-line). ANSI terminals "
        "only -- PETSCII (C64/C128) clients always use one fixed style.",
        '',
    ],
    'c': [
        '',
        '|yellow|Colors|reset|',
        "Sets the text color and highlight color used for |white|[bracketed]"
        "|reset| text throughout your session, e.g. item names or emphasis "
        "in messages.",
        '',
    ],
}


class PrefsCommand(Command):
    """Open the player preferences menu."""

    name    = 'prefs'
    aliases = ['preferences', 'settings']
    modes   = {Mode.LOGIN, Mode.GAME}

    help = Help(
        summary     = 'Open the player preferences menu.',
        description = (
            'Lets you adjust display and gameplay preferences: Expert Mode, '
            'clock format, More Prompt (pause between screenfuls of output), '
            'box border style, and terminal colors.  '
            'Changes take effect immediately.'
        ),
        category = HelpCategory.GENERAL,
        usage    = [
            ('prefs', 'Open the preferences menu.'),
        ],
        notes = [
            "Press Enter at the menu prompt to save and exit.",
            "Type 'XM' in-game to toggle Expert Mode quickly.",
            "Type 'h' followed by a setting's key (e.g. 'hx', 'hm') at the "
            "menu prompt for a fuller explanation of what it does.",
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        ok = await prefs_menu(ctx)
        if not ok:
            return CommandResult.fail('Preferences menu closed.', error='disconnected')
        return CommandResult.ok('Preferences saved.')


# ---------------------------------------------------------------------------
# Public coroutine — called directly by new_player._edit_settings()
# ---------------------------------------------------------------------------

async def prefs_menu(ctx) -> bool:
    """Display and edit player preferences.

    Loops until the player presses Enter (or disconnects).
    Returns True on clean exit, False on disconnect.
    """
    from formatting import border_style_for_ctx, codec_for_settings, ANSICodec, PETSCIICodec
    from table import Table

    codec      = codec_for_settings(ctx.player.client_settings)
    is_petscii = isinstance(codec, PETSCIICodec)
    cs         = ctx.player.client_settings

    while True:
        expert      = ctx.player.is_expert # query_flag(PlayerFlags.EXPERT_MODE)
        hourglass   = ctx.player.query_flag(PlayerFlags.HOURGLASS)
        more_prompt = ctx.player.query_flag(PlayerFlags.MORE_PROMPT)
        colors      = getattr(cs, 'colors', None)
        text_col    = getattr(colors, 'text_color',      'White') if colors else 'White'
        hi_col      = getattr(colors, 'highlight_color', 'Red')   if colors else 'Red'
        border_key  = getattr(cs, 'border_style', 'single')

        t = Table(headers=['Key', 'Setting', 'Current Value', 'Help'],
                  border_style=border_style_for_ctx(ctx))
        t.add_row(['X', 'Expert Mode', 'On' if expert else 'Off', 'hx'])
        t.add_row(['H', 'Hourglass Display', 'On' if hourglass else 'Off', 'hh'])
        t.add_row(['M', 'More Prompt', 'On' if more_prompt else 'Off', 'hm'])
        if not is_petscii:
            t.add_row(['B', 'Border Style',  border_key.title(), 'hb'])
        t.add_row(['C', 'Colors', f'{text_col} text, {hi_col} highlight', 'hc'])

        valid_keys = ['X', 'H', 'M', 'C'] if is_petscii else ['X', 'H', 'M', 'B', 'C']
        keys_str   = ' '.join(valid_keys)
        return_key = getattr(cs, 'return_key', 'Enter')
        menu = (
            ['', '|yellow|User Preferences|reset|', '']
            + t.render(width=cs.screen_columns)
            + ['', f"{keys_str} to change, h<key> for details (e.g. h{valid_keys[0].lower()}), "
                   f"{return_key} to save and exit", '']
        )

        raw = await ctx.prompt('prefs', preamble_lines=menu)
        if raw is None:
            return False
        ans = raw.strip().lower()

        if ans == '?':
            await ctx.send(
                'X - toggle Expert Mode',
                'H - toggle Hourglass (clock display)',
                "M - toggle More Prompt (pause between screenfuls; also 'mp' in-game)",
                'B - choose border style (ANSI only)',
                'C - choose text and highlight colors',
                f"h<key> - explain what a setting does, e.g. h{valid_keys[0].lower()}",
                f'{return_key} - save and exit',
            )
            continue

        if not ans or ans in ('q', 'quit', 'done', 'exit'):
            return True

        if len(ans) == 2 and ans[0] == 'h' and ans[1].upper() in valid_keys:
            await ctx.send(*_SETTING_HELP[ans[1]])
            continue

        if ans == 'x':
            option = "|white|Expert Mode: "
            if ctx.player.query_flag(PlayerFlags.EXPERT_MODE):
                ctx.player.clear_flag(PlayerFlags.EXPERT_MODE)
                await ctx.send(f'{option}|red|Off|reset|')
            else:
                ctx.player.set_flag(PlayerFlags.EXPERT_MODE)
                await ctx.send(f'{option}|green|On|reset|')

        elif ans == 'h':
            option = "|white|Hourglass display: "
            if ctx.player.query_flag(PlayerFlags.HOURGLASS):
                ctx.player.clear_flag(PlayerFlags.HOURGLASS)
                await ctx.send(f'{option}|red|Off|reset|')
            else:
                ctx.player.set_flag(PlayerFlags.HOURGLASS)
                await ctx.send(f'{option}|green|On|reset|')

        elif ans == 'm':
            await toggle_more_prompt(ctx)

        elif ans == 'b' and not is_petscii:
            await _pick_border_style(ctx, codec)

        elif ans == 'c':
            await _pick_colors(ctx)

        else:
            await ctx.send(f'Choose {",".join(valid_keys)}, or press {return_key} to save and exit.')


async def toggle_more_prompt(ctx) -> None:
    """Toggle PlayerFlags.MORE_PROMPT; shared by the 'M' menu key and the
    standalone 'mp' quick-toggle command (commands/more_prompt.py)."""
    option = "|white|More Prompt: "
    if ctx.player.query_flag(PlayerFlags.MORE_PROMPT):
        ctx.player.clear_flag(PlayerFlags.MORE_PROMPT)
        await ctx.send(f'{option}|red|Off|reset|')
    else:
        ctx.player.set_flag(PlayerFlags.MORE_PROMPT)
        await ctx.send(f'{option}|green|On|reset|')


# ---------------------------------------------------------------------------
# Sub-pickers
# ---------------------------------------------------------------------------

async def _pick_border_style(ctx, codec) -> None:
    """Choose a box-drawing border style (ANSI terminals only).

    Shows a one-line top-border preview for each style.
    The choice is saved to ctx.player.client_settings.border_style.
    """
    from formatting import make_box

    cs = ctx.player.client_settings
    options = [
        (['1', 'a'], 'ASCII'),
        (['2', 's'], 'Single'),
        (['3', 'd'], 'Double'),
    ]

    lines = ['', '|yellow|Border Style:|reset|', '']
    for num, key in options:
        top = make_box([''], width=14, codec=codec, border_style=key)[0]
        lines.append(f'  {num}. {key.title():<8} {top}')
    lines.append('')

    raw = await ctx.prompt('border style', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Border style unchanged.')
        return
    ans = raw.strip()
    for num, key in options:
        if ans == num or ans.lower() in key:
            cs.border_style = key
            await ctx.send(f'Border style set to {key.title()}.')
            return
    await ctx.send('Border style unchanged.')


async def _pick_colors(ctx) -> None:
    """Pick text color and [bracket] highlight color from a numbered palette.

    Colors are shown as live |token| swatches so they render in the actual
    color on ANSI terminals.
    """
    from terminal import ColorName
    from formatting import COLOR_NAME_TO_TOKEN, border_style_for_ctx
    from table import Table

    _SKIP   = {ColorName.RESET, ColorName.REVERSE_ON, ColorName.REVERSE_OFF}
    palette = [cn for cn in ColorName if cn not in _SKIP]

    cs     = ctx.player.client_settings
    colors = getattr(cs, 'colors', None)
    if colors is None:
        from terminal import TerminalColors
        colors = TerminalColors()
        try:
            cs.colors = colors
        except Exception:
            pass

    def _palette_rows() -> list[str]:
        t = Table(headers=['#', 'Color', 'Sample'],
                  border_style=border_style_for_ctx(ctx))
        for i, cn in enumerate(palette, 1):
            token  = COLOR_NAME_TO_TOKEN.get(cn, '')
            swatch = f'|{token}|{cn.value}|reset|' if token else cn.value
            t.add_row([str(i), cn.value, swatch])
        return t.render(width=cs.screen_columns)

    for attr, label in (('text_color', 'Text'), ('highlight_color', '[bracket] Highlight')):
        current = getattr(colors, attr, None)
        await ctx.send(*(['', f'|yellow|{label} Color|reset| (current: {current}):']
                         + _palette_rows() + ['']))
        raw = await ctx.prompt(f'{label} #')
        if raw is None:
            return
        val = raw.strip()
        if val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(palette):
                chosen = palette[idx]
                if colors:
                    setattr(colors, attr, chosen)
                await ctx.send(f'{label} color set to {chosen.value}.')
            else:
                await ctx.send(f'{label} color unchanged - number out of range.')
        else:
            await ctx.send(f'{label} color unchanged.')
