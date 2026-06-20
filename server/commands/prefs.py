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
  X  Expert Mode      PlayerFlags.EXPERT_MODE   (On / Off)
  H  Clock Display    PlayerFlags.HOURGLASS      (12-hour / 24-hour)
  B  Border Style     ctx.player.border_style    (ascii / single / double)
                      — ANSI terminals only; PETSCII has one fixed style
  C  Colors           client_settings.colors.text_color
                      client_settings.colors.highlight_color
"""

from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags


class PrefsCommand(Command):
    """Open the player preferences menu."""

    name    = 'prefs'
    aliases = ['preferences', 'settings']
    modes   = {Mode.LOGIN, Mode.GAME}

    help = Help(
        summary     = 'Open the player preferences menu.',
        description = (
            'Lets you adjust display and gameplay preferences: Expert Mode, '
            'clock format, box border style, and terminal colors.  '
            'Changes take effect immediately.'
        ),
        category = HelpCategory.GENERAL,
        usage    = [
            ('prefs', 'Open the preferences menu.'),
        ],
        notes = [
            "Press Enter at the menu prompt to save and exit.",
            "Type 'XM' in-game to toggle Expert Mode quickly.",
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
        expert     = ctx.player.query_flag(PlayerFlags.EXPERT_MODE)
        hourglass  = ctx.player.query_flag(PlayerFlags.HOURGLASS)
        colors     = getattr(cs, 'colors', None)
        text_col   = getattr(colors, 'text_color',      'White') if colors else 'White'
        hi_col     = getattr(colors, 'highlight_color', 'Red')   if colors else 'Red'
        border_key = getattr(cs, 'border_style', 'single')

        t = Table(headers=['Key', 'Setting', 'Current Value'],
                  border_style=border_style_for_ctx(ctx))
        t.add_row(['X', 'Expert Mode', 'On' if expert else 'Off'])
        t.add_row(['H', 'Hourglass Display', 'On' if hourglass else 'Off'])
        if not is_petscii:
            t.add_row(['B', 'Border Style',  border_key.title()])
        t.add_row(['C', 'Colors', f'{text_col} text, {hi_col} highlight'])

        valid_keys = ['X', 'H', 'C'] if is_petscii else ['X', 'H', 'B', 'C']
        keys_str   = ' '.join(valid_keys)
        return_key = getattr(cs, 'return_key', 'Enter')
        menu = (
            ['', '|yellow|User Preferences|reset|', '']
            + t.render(width=cs.screen_columns)
            + ['', f"{keys_str} to change  —  {return_key} to save and exit", '']
        )

        raw = await ctx.prompt('prefs', preamble_lines=menu)
        if raw is None:
            return False
        ans = raw.strip().lower()

        if ans == '?':
            await ctx.send(
                'X — toggle Expert Mode',
                'H — toggle Hourglass (clock display)',
                'B — choose border style (ANSI only)',
                'C — choose text and highlight colors',
                f'{return_key} — save and exit',
            )
            continue

        if not ans or ans in ('q', 'quit', 'done', 'exit'):
            return True

        if ans == 'x':
            if ctx.player.query_flag(PlayerFlags.EXPERT_MODE):
                ctx.player.clear_flag(PlayerFlags.EXPERT_MODE)
                await ctx.send('Expert Mode: |red|Off|reset|')
            else:
                ctx.player.set_flag(PlayerFlags.EXPERT_MODE)
                await ctx.send('Expert Mode: |green|On|reset|')

        elif ans == 'h':
            if ctx.player.query_flag(PlayerFlags.HOURGLASS):
                ctx.player.clear_flag(PlayerFlags.HOURGLASS)
                await ctx.send('[Hourglass display:] |white|Off|reset|')
            else:
                ctx.player.set_flag(PlayerFlags.HOURGLASS)
                await ctx.send('[Hourglass display:] |white|On|reset|')

        elif ans == 'b' and not is_petscii:
            await _pick_border_style(ctx, codec)

        elif ans == 'c':
            await _pick_colors(ctx, is_petscii)

        else:
            await ctx.send(f'Enter {",".join(valid_keys)}, or press Enter to save and exit.')


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
        ('1', 'ascii'),
        ('2', 'single'),
        ('3', 'double'),
    ]

    lines = ['', '|yellow|Border Style|reset|', '']
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
        if ans == num or ans.lower() == key:
            cs.border_style = key
            await ctx.send(f'Border style set to {key.title()}.')
            return
    await ctx.send('Border style unchanged.')


async def _pick_colors(ctx, is_petscii: bool = False) -> None:
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
                await ctx.send(f'{label} color unchanged — number out of range.')
        else:
            await ctx.send(f'{label} color unchanged.')
