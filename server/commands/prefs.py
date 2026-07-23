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
  N  News Display     command_settings.news_show_all  (New only / Full directory)
  T  Client Type      client_settings.screen_columns/screen_rows/translation
                      — presets (C64/C128/TADA client) or a custom size.
                        Available over a real PETSCII connection too (a
                        C128 can switch 40<->80 col after login, same
                        choice as terminal negotiation) -- _pick_client_type()
                        just keeps a real PETSCII session's translation
                        pinned to PETSCII regardless of which preset/custom
                        answer is picked, the same way it already keeps a
                        non-PETSCII session from being switched *to*
                        PETSCII. Folded in from what used to be character
                        creation's own standalone "Client Type" step.
  K  Tab Key          client_settings.tab_settings.has_tab_key/tab_width
  L  Line Ending      client_settings.line_ending  (LF / CR / CRLF)
                      — stored only for now, not yet enforced on every
                        line sent (see terminal.py's ClientSettings).
  S  Menu Colors      client_settings.menu_colors (menu_system.MenuColor)
                      — colors used to render menus (editplayer, config,
                        etc): item numbers, shortcuts, labels, hrules,
                        dot leaders/values. 'Default' clears the override
                        (None falls back to menu_system.DEFAULT_MENU_
                        COLORS); 'Custom' walks through each part.
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
        '|cyan|Expert Mode|reset|',
        "Hides beginner-oriented tips, hints, and confirmation text "
        "throughout the game once you're comfortable with the commands. "
        "Affects things like READY's weapon-class breakdown and various "
        "menu prompts -- the underlying commands work the same either way.",
        '',
    ],
    'h': [
        '',
        '|cyan|Hourglass Display|reset|',
        "Shows the current time in front of your command prompt. Purely "
        "a visual clock -- it doesn't yet affect in-game time limits or "
        "control 12-hour (AM/PM) vs 24-hour formatting or timezone.",
        '',
    ],
    'm': [
        '',
        '|cyan|More Prompt|reset|',
        "When output would be longer than one screen, pauses with a "
        "'-- More --' prompt between pages: Enter for the next page, "
        "B or - to go back a page, Q to stop reading early. When off, "
        "everything is sent at once and scrolls by regardless of length. "
        "Same setting as the standalone 'mp' command.",
        '',
    ],
    'b': [
        '',
        '|cyan|Border Style|reset|',
        "Controls the box-drawing characters used around tables and "
        "boxed text (ASCII, Single-line, or Double-line). ANSI terminals "
        "only -- PETSCII (C64/C128) clients always use one fixed style.",
        '',
    ],
    'c': [
        '',
        '|cyan|Colors|reset|',
        "Sets the text color and highlight color used for |white|[bracketed]"
        "|reset| text throughout your session, e.g. item names or emphasis "
        "in messages.",
        '',
    ],
    'n': [
        '',
        '|cyan|News Display|reset|',
        "Controls what the NEWS command shows you at login. 'New only' (the "
        "default) shows just what's posted since your last login. 'Full "
        "directory' shows every currently-active news item every time you "
        "log in, whether you've seen it before or not.",
        '',
    ],
    't': [
        '',
        '|cyan|Client Type|reset|',
        "Sets your screen size and color translation -- pick a Commodore "
        "64/128 preset, the TADA client preset, or a Custom size (20-132 "
        "columns, 10-60 rows) with ANSI color or plain text. On a real "
        "Commodore connection, only the screen size actually changes -- "
        "translation stays PETSCII regardless of which preset you pick, "
        "since PETSCII color codes only work over that port.",
        '',
    ],
    'k': [
        '',
        '|cyan|Tab Key|reset|',
        "Whether your client sends a real Tab keypress. If not, tabs are "
        "simulated with a configurable number of spaces instead.",
        '',
    ],
    'l': [
        '',
        '|cyan|Line Ending|reset|',
        "LF (Unix-style), CR (classic Mac / some Commodore terminals), or "
        "CRLF (Windows-style). Stored for your client, but not yet enforced "
        "on every line sent -- most terminals handle any of the three fine.",
        '',
    ],
    'z': [
        '',
        '|cyan|Timezone|reset|',
        "Which timezone dates and times are shown in -- the login "
        "screen's 'You last connected on ...' line and the Hourglass "
        "clock (more player-facing dates are planned). 'Server Local' "
        "(the default) shows the server's own local time as-is; picking "
        "a named zone converts to it instead.",
        '',
    ],
    'd': [
        '',
        '|cyan|Date Format|reset|',
        "How dates are written out, e.g. 'July 16, 2026' vs '07/16/2026' "
        "vs '2026-07-16'. Applies to the same dates as Timezone above.",
        '',
    ],
    'f': [
        '',
        '|cyan|Time Format|reset|',
        "12-hour ('2:30 PM') or 24-hour ('14:30') time. Affects the "
        "Hourglass clock (PREFS 'H') and any other time-of-day display.",
        '',
    ],
    's': [
        '',
        '|cyan|Menu Colors|reset|',
        "Sets the colors used to draw menus (EDITPLAYER, CONFIG, etc): "
        "item numbers, shortcut letters, menu text, horizontal rules, and "
        "dot-leader lines/values. 'Default' clears any custom scheme; "
        "'Custom' lets you pick a color for each part individually.",
        '',
    ],
}

# Named strftime presets offered by the 'D' (Date Format) picker --
# _DATE_FORMAT_NAMES reverses this for the summary table so a matching
# stored format shows its friendly name instead of the raw strftime
# pattern; anything else (a value never set through this picker) shows
# as 'Custom'.
_DATE_FORMAT_PRESETS = [
    ('1', 'Month Day, Year', '%B %d, %Y'),
    ('2', 'MM/DD/YYYY',      '%m/%d/%Y'),
    ('3', 'DD/MM/YYYY',      '%d/%m/%Y'),
    ('4', 'YYYY-MM-DD',      '%Y-%m-%d'),
    ('5', 'Day Month Year',  '%d %B %Y'),
]
_DATE_FORMAT_NAMES = {fmt: name for _, name, fmt in _DATE_FORMAT_PRESETS}

# Named strftime presets offered by the 'F' (Time Format) picker. Labels
# are bracket-highlighted on their own option number ('[1]2-hour',
# '[2]4-hour') so the highlighted digit visually matches the number you'd
# type to pick it. _TIME_FORMAT_NAMES reverses this for the summary
# table (bracket-stripped, since that display isn't a menu prompt).
_TIME_FORMAT_PRESETS = [
    ('1', '[1]2-hour', '%I:%M %p'),
    ('2', '[2]4-hour', '%H:%M'),
]
_TIME_FORMAT_NAMES = {fmt: name.replace('[', '').replace(']', '')
                      for _, name, fmt in _TIME_FORMAT_PRESETS}

# A representative, non-exhaustive spread of IANA zones for the 'Z'
# (Timezone) picker's numbered shortlist -- typed free text is also
# accepted and validated against the full zoneinfo database, so this
# isn't the only way to reach a given zone, just the fast path for
# common ones.
_TIMEZONE_PRESETS = [
    ('1', '',                     'Server Local'),
    ('2', 'UTC',                  'UTC'),
    ('3', 'America/New_York',     'US Eastern'),
    ('4', 'America/Chicago',      'US Central'),
    ('5', 'America/Denver',       'US Mountain'),
    ('6', 'America/Los_Angeles',  'US Pacific'),
    ('7', 'Europe/London',        'UK'),
    ('8', 'Europe/Berlin',        'Central Europe'),
    ('9', 'Asia/Tokyo',           'Japan'),
    ('10', 'Australia/Sydney',    'Australia Eastern'),
]


def _server_local_label() -> str:
    """'Server Local', naming the configured zone if a sysop has set one
    (config.server_timezone -- setup/server_setup.py / the in-game CONFIG
    command) so a player isn't left guessing what "local" means."""
    try:
        from config import config
        tz = (config.server_timezone or '').strip()
    except Exception:
        tz = ''
    return f'Server Local ({tz})' if tz else 'Server Local'


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

async def prefs_menu(ctx, from_new_player: bool = False) -> bool:
    """Display and edit player preferences.

    Loops until the player presses Enter (or disconnects).
    Returns True on clean exit, False on disconnect.

    :param from_new_player: set by new_player.py's _edit_settings() --
        changes the "Enter to ..." line's wording, since an alpha tester
        was worried pressing Return here would quit character creation
        entirely instead of just saving and moving to the next step. Also
        shows a one-time orientation blurb before the menu loop starts.
    """
    from formatting import border_style_for_ctx, codec_for_settings, ANSICodec, PETSCIICodec
    from table import Table

    if from_new_player:
        await ctx.send(
            '',
            "These are your terminal preferences -- how TADA looks and "
            "behaves for you (colors, More Prompt, Expert Mode, etc). "
            "Don't worry about getting these perfect: you can change any "
            "of them later with the PREFS command. Not sure what a "
            "setting does? Type h followed by its letter (e.g. 'hx') for "
            "an explanation.",
        )

    cs = ctx.player.client_settings

    while True:
        # Recomputed every iteration, not once before the loop: the 'T'
        # (Client Type) picker can change translation mid-session (e.g.
        # ANSI -> Plain), and codec/is_petscii need to reflect that on the
        # very next redraw, not just the next time PREFS is opened fresh.
        codec       = codec_for_settings(cs)
        is_petscii  = isinstance(codec, PETSCIICodec)
        expert      = ctx.player.is_expert # query_flag(PlayerFlags.EXPERT_MODE)
        hourglass   = ctx.player.query_flag(PlayerFlags.HOURGLASS)
        more_prompt = ctx.player.query_flag(PlayerFlags.MORE_PROMPT)
        colors      = getattr(cs, 'colors', None)
        text_col    = getattr(colors, 'text_color',      'White') if colors else 'White'
        hi_col      = getattr(colors, 'highlight_color', 'Red')   if colors else 'Red'
        border_key  = getattr(cs, 'border_style', 'single')

        tab         = getattr(cs, 'tab_settings', None)
        tab_summary = ('Real Tab key' if getattr(tab, 'has_tab_key', True)
                       else f'Spaces ({getattr(tab, "tab_width", 8)})')
        from terminal import LineEnding
        line_ending      = getattr(cs, 'line_ending', LineEnding.LF)
        line_ending_name = {LineEnding.LF: 'LF', LineEnding.CR: 'CR', LineEnding.CRLF: 'CRLF'}.get(line_ending, 'LF')

        t = Table(headers=['Key', 'Setting', 'Current Value', 'Help'],
                  border_style=border_style_for_ctx(ctx))
        t.add_row(['X', 'Expert Mode', 'On' if expert else 'Off', 'hx'])
        t.add_row(['H', 'Hourglass Display', 'On' if hourglass else 'Off', 'hh'])
        t.add_row(['M', 'More Prompt', 'On' if more_prompt else 'Off', 'hm'])
        if not is_petscii:
            t.add_row(['B', 'Border Style',  border_key.title(), 'hb'])
        t.add_row(['C', 'Colors', f'{text_col} text, {hi_col} highlight', 'hc'])
        news_all = getattr(ctx.player.command_settings, 'news_show_all', False)
        t.add_row(['N', 'News Display', 'Full directory' if news_all else 'New only', 'hn'])
        t.add_row(['T', 'Client Type', f'{cs.screen_columns}x{cs.screen_rows}', 'ht'])
        t.add_row(['K', 'Tab Key', tab_summary, 'hk'])
        t.add_row(['L', 'Line Ending', line_ending_name, 'hl'])
        tz_name    = getattr(cs, 'timezone', '') or _server_local_label()
        t.add_row(['Z', 'Timezone', tz_name, 'hz'])
        date_fmt_name = _DATE_FORMAT_NAMES.get(getattr(cs, 'date_format', ''), 'Custom')
        t.add_row(['D', 'Date Format', date_fmt_name, 'hd'])
        time_fmt_name = _TIME_FORMAT_NAMES.get(getattr(cs, 'time_format', ''), 'Custom')
        t.add_row(['F', 'Time Format', time_fmt_name, 'hf'])
        from menu_system import MENU_COLOR_PRESETS
        _cur_menu_colors = getattr(cs, 'menu_colors', None)
        menu_colors_name = next(
            (name for name, mc in MENU_COLOR_PRESETS if mc == _cur_menu_colors), None,
        ) or ('Default' if _cur_menu_colors is None else 'Custom')
        t.add_row(['S', 'Menu Colors', menu_colors_name, 'hs'])

        valid_keys = ['X', 'H', 'M']
        if not is_petscii:
            valid_keys.append('B')
        valid_keys += ['C', 'N', 'T', 'K', 'L', 'Z', 'D', 'F', 'S']
        keys_str   = ' '.join(valid_keys)
        return_key = getattr(cs, 'return_key', 'Enter')
        menu = (
            ['', '|yellow|User Preferences|reset|', '']
            + t.render(width=cs.screen_columns)
            + ['', f"{keys_str} to change, h<key> for details (e.g. h{valid_keys[0].lower()}), "
                   f"{return_key} to "
                   + ('continue creating your character' if from_new_player
                      else 'save settings and exit'),
                   '']
        )

        raw = await ctx.prompt('prefs', preamble_lines=menu)
        if raw is None:
            if from_new_player:
                from commands.new_player import _CreationAbandoned
                raise _CreationAbandoned()
            return False
        ans = raw.strip().lower()

        if ans == '?':
            help_lines = [
                'X - toggle Expert Mode',
                'H - toggle Hourglass (clock display)',
                "M - toggle More Prompt (pause between screenfuls; also 'mp' in-game)",
            ]
            if not is_petscii:
                help_lines.append('B - choose border style (ANSI only)')
            help_lines += [
                'C - choose text and highlight colors',
                'N - toggle News Display (new only / full directory)',
                'T - choose client type / screen size',
            ]
            help_lines += [
                'K - set whether your client has a real Tab key (and its width)',
                'L - choose line ending (LF / CR / CRLF)',
                'Z - choose your display timezone',
                'D - choose your preferred date format',
                'F - choose 12-hour or 24-hour time format',
                'S - choose the menu color scheme',
                f"h<key> - explain what a setting does, e.g. h{valid_keys[0].lower()}",
                f'{return_key} - save and exit',
            ]
            await ctx.send(*help_lines)
            continue

        if from_new_player and ans in ('q', 'quit'):
            from commands.new_player import _confirm_quit_or_continue
            await _confirm_quit_or_continue(ctx)   # returns only if (C)ontinue was chosen
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

        elif ans == 'n':
            option = "|white|News Display: "
            cs2 = ctx.player.command_settings
            cs2.news_show_all = not getattr(cs2, 'news_show_all', False)
            await ctx.send(f"{option}{'|green|Full directory' if cs2.news_show_all else '|green|New only'}|reset|")

        elif ans == 't':
            await _pick_client_type(ctx)

        elif ans == 'k':
            await _pick_tab_settings(ctx)

        elif ans == 'l':
            await _pick_line_ending(ctx)

        elif ans == 'z':
            await _pick_timezone(ctx)

        elif ans == 'd':
            await _pick_date_format(ctx)

        elif ans == 'f':
            await _pick_time_format(ctx)

        elif ans == 's':
            await _pick_menu_colors(ctx)

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
    # style_key must be the lowercase form make_box()/_HRULE_CHAR expect
    # ('ascii'/'single'/'double') -- Ryan found live that border style
    # picking was broken: (num, key) here used to be (['1', 'a'], 'ASCII')
    # unpacked into two variables, so `num` was a whole list (displayed
    # as its Python repr, e.g. "['1', 'a']. ASCII") and `key` was the
    # capitalized display name -- passed straight to make_box(border_
    # style=key), which only recognizes the lowercase form, so every
    # preview silently rendered identically (always falling through to
    # single-line) regardless of which style was actually being shown.
    # Selection matching was equally broken (`ans == num` compared a str
    # to a list, always False) and even a coincidental match saved the
    # wrong-cased value, so _HRULE_CHAR and make_box's own lookups
    # elsewhere never recognized the stored preference either.
    options = [
        ('1', 'a', 'ascii',  'ASCII'),
        ('2', 's', 'single', 'Single'),
        ('3', 'd', 'double', 'Double'),
    ]

    lines = ['', '|yellow|Border Style:|reset|', '']
    for num, letter, style_key, label in options:
        top = make_box([''], width=14, codec=codec, border_style=style_key)[0]
        lines.append(f'  {num}. {label:<8} {top}')
    lines.append('')

    raw = await ctx.prompt('border style', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Border style unchanged.')
        return
    ans = raw.strip().lower()
    for num, letter, style_key, label in options:
        if ans in (num, letter, style_key, label.lower()):
            cs.border_style = style_key
            await ctx.send(f'Border style set to {label}.')
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


# Validated range for a custom screen size (_pick_client_type()'s 'Custom'
# option) -- generous enough to cover anything from a tiny terminal to a
# wide modern window, while still catching an obvious typo (e.g. '0' or
# a stray extra digit) that would otherwise break box-drawing/pagination
# math elsewhere.
_MIN_COLS, _MAX_COLS = 20, 132
_MIN_ROWS, _MAX_ROWS = 10, 60


async def _pick_client_type(ctx) -> None:
    """Choose a client/screen-size preset, or enter a custom size.

    Folded in from what used to be character creation's own standalone
    "Client Type" step (commands/new_player.py) -- now reachable any time
    via PREFS, not just once during creation, and with a real custom
    width/height option the old step never had.
    """
    from table import Table
    from formatting import border_style_for_ctx
    from terminal import Translation

    cs = ctx.player.client_settings
    # A real Commodore connection (raw PETSCII byte transport, the
    # dedicated PETSCII port) vs. an ANSI/JSON client (tada_client.py,
    # telnet, etc). Found live (server/hardcopy.0): picking a "Commodore"
    # preset from an ANSI/JSON session switched that session's own
    # translation to PETSCII, so every subsequent send -- tables, this
    # very menu -- went out as raw Commodore control-code bytes, which a
    # Linux terminal just displays as garbage (and could mangle terminal
    # state). Screen-size presets are still offered either way, but the
    # PETSCII *translation* only actually applies over a real PETSCII
    # connection.
    #
    # Compared by class *name*, not isinstance()/identity: several test
    # modules stub sys.modules['network_context'] with incomplete fakes
    # (see tests/test_wild_horse_placement.py's note), which can leave a
    # PETSCIINetworkContext imported here bound to a different class
    # object than the one an actual PETSCIINetworkContext instance was
    # built from -- the same reload/duplicate-module-identity gotcha
    # documented in commands/reload.py, just via test stubbing instead of
    # a hot reload.
    is_real_petscii = any(cls.__name__ == 'PETSCIINetworkContext' for cls in type(ctx).__mro__)
    # Real Translation enum members, not bare strings -- formatting.py's
    # codec_for_settings() compares `t == Translation.PETSCII` etc., which
    # silently falls through to PlainCodec for a plain str that merely
    # *looks* like 'PETSCII' (found live: the old character-creation
    # "Client Type" step this was folded in from had exactly this bug --
    # every player who picked a Commodore preset there got PlainCodec
    # instead of PETSCIICodec, since PETSCIINetworkContext.for_guest()'s
    # own enum-based assignment was the only path that ever worked).
    presets = [
        ('1', 'Commodore 64',  40, 25, Translation.PETSCII),
        ('2', 'Commodore 128', 40, 25, Translation.PETSCII),
        ('3', 'Commodore 128', 80, 25, Translation.PETSCII),
        ('4', 'TADA Client',   80, 25, Translation.ANSI),
    ]

    t = Table(headers=['##', 'Computer Type', 'Screen Size', 'Translation'],
              border_style=border_style_for_ctx(ctx))
    for num, label, cols, rows, encoding in presets:
        t.add_row([num, label, f'{cols} x {rows}', encoding.name])
    t.add_row(['5', 'Custom', f'{_MIN_COLS}-{_MAX_COLS} x {_MIN_ROWS}-{_MAX_ROWS}', 'ANSI or Plain'])

    lines = (
        ['', '|yellow|Client Type:|reset|', '']
        + t.render(width=cs.screen_columns)
        + ['']
    )
    raw = await ctx.prompt('client type', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Client type unchanged.')
        return
    ans = raw.strip()

    for num, label, cols, rows, encoding in presets:
        if ans == num:
            cs.screen_columns = cols
            cs.screen_rows    = rows
            if encoding == Translation.PETSCII and not is_real_petscii:
                # Apply the screen size, but never switch a non-PETSCII
                # transport's translation to PETSCII -- that's what
                # produced raw Commodore control bytes in a Linux
                # terminal. Leave translation exactly as it was.
                await ctx.send(
                    f'Client type set to: {label} screen size ({cols}x{rows}), '
                    f'but keeping {cs.translation.name if hasattr(cs.translation, "name") else cs.translation} '
                    "translation -- PETSCII color codes only work over a real "
                    "Commodore connection (the dedicated PETSCII port), not this one."
                )
                return
            if encoding != Translation.PETSCII and is_real_petscii:
                # Mirror image of the guard above: apply the screen size,
                # but never switch a *real* PETSCII connection's
                # translation away from PETSCII -- ANSI escape codes sent
                # to real Commodore hardware would garble its display.
                await ctx.send(
                    f'Client type set to: {label} screen size ({cols}x{rows}), '
                    "but keeping PETSCII translation -- ANSI color codes don't "
                    "work over a real Commodore connection."
                )
                return
            cs.translation = encoding
            # The Commodore 128's keyboard has a real Tab key (the C64's
            # doesn't), and so does any ANSI/TADA client -- set as a side
            # effect of picking this client type, not asked separately.
            if label != 'Commodore 64':
                cs.has_tab  = True
                cs.tab_char = chr(9)
            else:
                cs.has_tab = False
            await ctx.send(f'Client type set to: {label}, {cols}x{rows} screen size.')
            return

    if ans != '5':
        await ctx.send(f'Client type unchanged -- enter a number between 1 and 5.')
        return

    raw_cols = await ctx.prompt(f'Screen columns ({_MIN_COLS}-{_MAX_COLS})')
    if raw_cols is None or not raw_cols.strip().isdigit():
        await ctx.send('Client type unchanged.')
        return
    cols = int(raw_cols.strip())
    if not (_MIN_COLS <= cols <= _MAX_COLS):
        await ctx.send(f'Client type unchanged -- columns must be {_MIN_COLS}-{_MAX_COLS}.')
        return

    raw_rows = await ctx.prompt(f'Screen rows ({_MIN_ROWS}-{_MAX_ROWS})')
    if raw_rows is None or not raw_rows.strip().isdigit():
        await ctx.send('Client type unchanged.')
        return
    rows = int(raw_rows.strip())
    if not (_MIN_ROWS <= rows <= _MAX_ROWS):
        await ctx.send(f'Client type unchanged -- rows must be {_MIN_ROWS}-{_MAX_ROWS}.')
        return

    cs.screen_columns = cols
    cs.screen_rows    = rows

    if is_real_petscii:
        # Same guard as the preset branch above -- a real Commodore
        # connection can pick a custom screen size, but its translation
        # stays PETSCII; ANSI/Plain aren't real options over that port,
        # so don't even ask.
        await ctx.send(f'Client type set to: Custom, {cols}x{rows} screen size, '
                        'keeping PETSCII translation.')
        return

    raw_trans = await ctx.prompt('ANSI color or Plain text? (A/P)')
    translation = Translation.ASCII if (raw_trans or '').strip().lower().startswith('p') else Translation.ANSI
    cs.translation = translation
    # Custom is only ever ANSI or Plain -- neither is the C64's no-real-
    # tab-key case, so both get a real Tab key like TADA Client does.
    cs.has_tab  = True
    cs.tab_char = chr(9)
    await ctx.send(f'Client type set to: Custom, {cols}x{rows} screen size, {translation.name}.')


def _tab_test_line() -> str:
    """Build a sample line using |tab| so a player can see what their
    current tab setting actually looks like -- goes through the normal
    ctx.send() -> format_lines() pipeline, so it expands exactly like any
    other |tab|/|tab:N| token in game text (see formatting._expand_tab_tokens())."""
    return 'Tab test:|tab|1|tab|2|tab|3'


async def _pick_tab_settings(ctx) -> None:
    """Toggle whether the client has a real Tab key, and (when simulating
    tabs with spaces instead) the tab width."""
    from terminal import TabSettings

    cs  = ctx.player.client_settings
    tab = getattr(cs, 'tab_settings', None)
    if tab is None:
        tab = TabSettings()
        cs.tab_settings = tab

    raw = await ctx.prompt(
        'Y/N',
        preamble_lines=[
            '',
            '|yellow|Tab Key|reset|',
            f"Does your client have a working Tab key? Currently: "
            f"{'Yes' if tab.has_tab_key else 'No'}.",
            "If not, tabs are simulated with spaces instead.",
            _tab_test_line(),
        ],
    )
    if raw is None or not raw.strip():
        await ctx.send('Tab settings unchanged.')
        return
    tab.has_tab_key = raw.strip().lower().startswith('y')
    await ctx.send(f"Tab key: {'Yes' if tab.has_tab_key else 'No'}.")

    if tab.has_tab_key:
        await ctx.send(_tab_test_line())
        return

    raw_width = await ctx.prompt(
        f'Tab width (0-{cs.screen_columns})',
        preamble_lines=[f'Current tab width: {tab.tab_width}'],
    )
    if raw_width is None or not raw_width.strip().isdigit():
        return
    width = int(raw_width.strip())
    if 0 <= width <= cs.screen_columns:
        tab.tab_width  = width
        tab.tab_output = ' ' * width
        await ctx.send(f'Tab width set to {width}.', _tab_test_line())
    else:
        await ctx.send(f'Tab width unchanged -- must be 0-{cs.screen_columns}.')


async def _pick_line_ending(ctx) -> None:
    """Choose the line-ending style (CR, LF, or CRLF)."""
    from terminal import LineEnding

    cs = ctx.player.client_settings
    options = [
        ('1', 'LF',   LineEnding.LF,   'Unix-style (\\n)'),
        ('2', 'CR',   LineEnding.CR,   'Classic Mac / some Commodore terminals (\\r)'),
        ('3', 'CRLF', LineEnding.CRLF, 'Windows-style (\\r\\n)'),
    ]
    current = getattr(cs, 'line_ending', LineEnding.LF)
    current_label = next((label for _, label, val, _ in options if val == current), 'LF')

    lines = ['', '|yellow|Line Ending:|reset|', f'Current: {current_label}', '']
    for num, label, _val, desc in options:
        lines.append(f'  {num}. {label:<5} {desc}')
    lines.append('')

    raw = await ctx.prompt('line ending', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Line ending unchanged.')
        return
    ans = raw.strip()
    for num, label, val, _desc in options:
        if ans == num or ans.lower() == label.lower():
            cs.line_ending = val
            await ctx.send(f'Line ending set to {label}.')
            return
    await ctx.send('Line ending unchanged.')


async def _pick_timezone(ctx) -> None:
    """Choose a display timezone from a shortlist, or type any IANA zone
    name (e.g. 'Asia/Kolkata') -- validated against the full zoneinfo
    database. 'Server Local' (an empty stored value) skips conversion
    entirely rather than assuming UTC."""
    import zoneinfo

    cs = ctx.player.client_settings
    current = getattr(cs, 'timezone', '') or _server_local_label()

    lines = ['', '|yellow|Timezone:|reset|', f'Current: {current}', '']
    for num, _zone, label in _TIMEZONE_PRESETS:
        if label == 'Server Local':
            label = _server_local_label()
        lines.append(f'  {num:>2}. {label}')
    lines += ['', "Or type any IANA zone name, e.g. 'Asia/Kolkata'.", '']

    raw = await ctx.prompt('timezone', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Timezone unchanged.')
        return
    ans = raw.strip()

    for num, zone, label in _TIMEZONE_PRESETS:
        if ans == num or ans.lower() == label.lower():
            cs.timezone = zone
            await ctx.send(f'Timezone set to {label}.')
            return

    if ans in zoneinfo.available_timezones():
        cs.timezone = ans
        await ctx.send(f'Timezone set to {ans}.')
        return

    await ctx.send(f"Timezone unchanged -- '{ans}' isn't a recognized zone name.")


async def _pick_date_format(ctx) -> None:
    """Choose a date display format from a few common presets, previewed
    against today's date."""
    import datetime

    cs = ctx.player.client_settings
    current = getattr(cs, 'date_format', '') or '%B %d, %Y'
    sample  = datetime.datetime.now()

    lines = ['', '|yellow|Date Format:|reset|', '']
    for num, label, fmt in _DATE_FORMAT_PRESETS:
        lines.append(f'  {num}. {label:<16} {sample.strftime(fmt)}')
    lines += ['', f'Current: {_DATE_FORMAT_NAMES.get(current, current)}', '']

    raw = await ctx.prompt('date format', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Date format unchanged.')
        return
    ans = raw.strip()
    for num, label, fmt in _DATE_FORMAT_PRESETS:
        if ans == num or ans.lower() == label.lower():
            cs.date_format = fmt
            await ctx.send(f'Date format set to {label} ({sample.strftime(fmt)}).')
            return
    await ctx.send(f'Date format unchanged -- enter a number between 1 and {len(_DATE_FORMAT_PRESETS)}.')


async def _pick_time_format(ctx) -> None:
    """Choose 12-hour or 24-hour time display, previewed against the
    current time. Affects the Hourglass clock (network_context.py/
    terminal_context.py's prompt()) and any other time-of-day display."""
    import datetime

    cs = ctx.player.client_settings
    current = getattr(cs, 'time_format', '') or '%H:%M'
    sample  = datetime.datetime.now()

    lines = ['', '|yellow|Time Format:|reset|', '']
    for num, label, fmt in _TIME_FORMAT_PRESETS:
        lines.append(f'  {num}. {label:<8} {sample.strftime(fmt)}')
    lines += ['', f'Current: {_TIME_FORMAT_NAMES.get(current, current)}', '']

    raw = await ctx.prompt('time format', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Time format unchanged.')
        return
    ans = raw.strip()
    for num, label, fmt in _TIME_FORMAT_PRESETS:
        plain = label.replace('[', '').replace(']', '')
        if ans == num or ans.lower() == plain.lower():
            cs.time_format = fmt
            await ctx.send(f'Time format set to {plain} ({sample.strftime(fmt)}).')
            return
    await ctx.send(f'Time format unchanged -- enter a number between 1 and {len(_TIME_FORMAT_PRESETS)}.')


# Which MenuColor field each step of the 'Custom' picker sets, and the
# player-facing label shown while picking it.
_MENU_COLOR_FIELDS = [
    ('rule',       'Horizontal Rules'),
    ('number',     'Item Numbers'),
    ('shortcut',   'Shortcuts'),
    ('label',      'Menu Text'),
    ('dot_leader', 'Dot Leaders'),
    ('dot_value',  'Dot Leader Values'),
]


def _menu_color_preview(ctx, mc) -> list[str]:
    """Render a real mock menu -- title, hrules, a few numbered/shortcut
    items with dot-leader values, a header row -- through the actual
    menu_system.format_menu_lines(), with *mc* (menu_system.MenuColor)
    passed as that one menu's color override. This shows exactly what
    picking *mc* would look like on every real menu (EDITPLAYER, CONFIG,
    etc), not just a hand-built approximation of the layout."""
    from menu_system import Menu, MenuItem, format_menu_lines

    async def _noop(ctx):
        pass

    menu = Menu(title='Sample Menu', colors=mc)
    menu.add_item(MenuItem(text='-- Section --'))
    menu.add_item(MenuItem('Alignment',       shortcuts='al', action=_noop,
                            dot_leader_handler=lambda ctx: 'Neutral'))
    menu.add_item(MenuItem('Hit Points',      shortcuts='hp', action=_noop,
                            dot_leader_handler=lambda ctx: '42'))
    menu.add_item(MenuItem('Flags/Counters',  shortcuts='fl', action=_noop,
                            dot_leader_handler=lambda ctx: 'On'))
    return format_menu_lines(ctx, menu)


def _menu_color_swatch(mc) -> str:
    """A compact inline swatch (one 2-char block per field, in that
    field's own color) so a preset can be told apart from the list
    without opening it -- same six fields/order as _MENU_COLOR_FIELDS."""
    fields = (mc.rule, mc.number, mc.shortcut, mc.label, mc.dot_leader, mc.dot_value)
    return ''.join(f'|{c}|##|reset|' for c in fields)


async def _pick_menu_colors(ctx) -> None:
    """Choose the color scheme used to render menus (menu_system.
    MenuColor) -- item numbers, shortcuts, menu text, hrules, and dot
    leaders/values (EDITPLAYER, CONFIG, etc. all share menu_system.
    format_menu_lines(), so this covers every menu in the game).

    Offers menu_system.MENU_COLOR_PRESETS by number ('Default' clears
    client_settings.menu_colors back to None, which format_menu_lines()
    reads as "use menu_system.DEFAULT_MENU_COLORS"; the others store a
    copy of that named preset), plus one more option for 'Custom', which
    walks through each part from the same palette _pick_colors() uses,
    one prompt at a time, previewing the result as it's built.
    """
    from dataclasses import replace
    from terminal import ColorName
    from formatting import COLOR_NAME_TO_TOKEN, border_style_for_ctx
    from menu_system import MenuColor, DEFAULT_MENU_COLORS, MENU_COLOR_PRESETS
    from table import Table

    _SKIP   = {ColorName.RESET, ColorName.REVERSE_ON, ColorName.REVERSE_OFF}
    palette = [cn for cn in ColorName if cn not in _SKIP and COLOR_NAME_TO_TOKEN.get(cn)]

    cs      = ctx.player.client_settings
    current = cs.menu_colors if isinstance(cs.menu_colors, MenuColor) else DEFAULT_MENU_COLORS

    custom_num = len(MENU_COLOR_PRESETS) + 1
    lines = ['', '|yellow|Menu Colors|reset|', ''] + _menu_color_preview(ctx, current) + ['']
    for i, (name, mc) in enumerate(MENU_COLOR_PRESETS, 1):
        lines.append(f'  {i:>2}. {name:<18} {_menu_color_swatch(mc)}')
    lines.append(f'  {custom_num:>2}. Custom (pick each part)')
    lines.append('')

    raw = await ctx.prompt('menu colors', preamble_lines=lines)
    if raw is None or not raw.strip():
        await ctx.send('Menu colors unchanged.')
        return
    ans = raw.strip()

    if ans.isdigit():
        idx = int(ans) - 1
        if 0 <= idx < len(MENU_COLOR_PRESETS):
            name, mc = MENU_COLOR_PRESETS[idx]
            # None for the literal Default preset (mc is the shared
            # DEFAULT_MENU_COLORS instance) so a later change to that
            # module-level default keeps applying; a real copy for every
            # other preset so it can't be mutated by editing DEFAULT_
            # MENU_COLORS later.
            cs.menu_colors = None if mc is DEFAULT_MENU_COLORS else replace(mc)
            await ctx.send(f'Menu colors set to {name}.', *_menu_color_preview(ctx, mc))
            return
        if idx == len(MENU_COLOR_PRESETS):
            pass  # Custom -- fall through below
        else:
            await ctx.send('Menu colors unchanged -- number out of range.')
            return
    else:
        await ctx.send('Menu colors unchanged.')
        return

    def _palette_rows() -> list[str]:
        t = Table(headers=['#', 'Color', 'Sample'], border_style=border_style_for_ctx(ctx))
        for i, cn in enumerate(palette, 1):
            token  = COLOR_NAME_TO_TOKEN[cn]
            t.add_row([str(i), cn.value, f'|{token}|{cn.value}|reset|'])
        return t.render(width=cs.screen_columns)

    # Work on a copy -- never mutate the shared DEFAULT_MENU_COLORS
    # instance itself when *current* was the fallback, not a real
    # per-player override.
    new_scheme = replace(current)
    palette_rows = _palette_rows()

    for attr, label in _MENU_COLOR_FIELDS:
        cur_token = getattr(new_scheme, attr)
        cur_name  = next((cn.value for cn in palette if COLOR_NAME_TO_TOKEN[cn] == cur_token), cur_token)
        await ctx.send(*(['', f'|yellow|{label}|reset| (current: {cur_name}):'] + palette_rows + ['']))
        raw = await ctx.prompt(f'{label} #')
        if raw is None:
            return
        val = raw.strip()
        if not val:
            continue
        if val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(palette):
                setattr(new_scheme, attr, COLOR_NAME_TO_TOKEN[palette[idx]])
            else:
                await ctx.send(f'{label} unchanged -- number out of range.')
        else:
            await ctx.send(f'{label} unchanged.')

    cs.menu_colors = new_scheme
    await ctx.send('Menu colors updated.', *_menu_color_preview(ctx, new_scheme))
