"""commands/connect.py

The 'connect' command — handles login and guest access.

Available only in LOGIN mode (you can't connect again once you're already
in-game).  Auto-discovered by CommandProcessor.discover().
"""

from __future__ import annotations

import datetime
import json
import logging

from base_classes import Guild, PlayerRace
from flags import PlayerFlags
from net_common import user_dir, verify_password
from network_context import GameContext
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory

log = logging.getLogger(__name__)

# Path pattern for per-user credential files.
# Expected layout: <run_server_dir>/net/login-<username>.json
# Each file must contain at least {"password": "<bcrypt hash>"} -- see
# net_common.hash_password()/verify_password(). Older accounts created
# before hashing was added store plaintext there; verify_password()
# handles both and signals an upgrade hash on a successful legacy match.

# Carrying capacity by race, matching original SPUR values.
# TODO: enforce this cap in inventory add/pickup logic.
# Stored as tuples because PlayerRace (StrEnum) is not hashable.
_CARRY_CAPACITY = [
    (PlayerRace.ELF,    9),
    (PlayerRace.DWARF,  9),
    (PlayerRace.ORC,    9),
    (PlayerRace.HOBBIT, 8),
    (PlayerRace.GNOME,  8),
    (PlayerRace.PIXIE,  7),
]
_DEFAULT_CARRY_CAPACITY = 10

def _carry_capacity(race) -> int:
    for key, cap in _CARRY_CAPACITY:
        if race == key:
            return cap
    return _DEFAULT_CARRY_CAPACITY

# Guild welcome messages matching original SPUR symbols. Stored as a
# (lead-in, sign-off) pair since SPUR itself prints them as two `print`
# statements, but they're one continuous sentence -- see guild_welcome_line().
_GUILD_WELCOME = {
    Guild.CLAW:  ("The Guild of the Claw bids",   r"you, 'Welcome!' \|/"),
    Guild.SWORD: ("The Guild of the Sword bids",   "you, 'Welcome!' -}----"),
    Guild.FIST:  ("The Guild of the Iron Fist bids", "you, 'Welcome!' ==[]"),
}


def guild_welcome_line(guild) -> str | None:
    """Return the one-line SPUR guild welcome message for *guild*, or None
    if *guild* has no welcome message (Civilian, Outlaw).

    The two halves must render as a single sentence on one line -- sending
    them as two separate ctx.send() lines breaks it mid-sentence.
    """
    parts = _GUILD_WELCOME.get(guild)
    return f"{parts[0]} {parts[1]}" if parts else None


def _party_waiting_line(party) -> str | None:
    """Return the SPUR.LOGON.S ally-greeting line ("X is/are waiting for
    you!") for a player's *party*, or None if it's empty.

    SPUR (master only -- skip has no equivalent):
      if a1 zz$=d1$:if a2 zz$=d1$+" and "+d2$:zz=1:if a3 zz$=d1$+", "+d2$+" and "+d3$
      if a1 then if a3 then if not a2 zz$=d1$+" and "+d3$:zz=1
      if not a1 then if a3 zz$=d3$
      zw$=" is":if zz=1 zw$=" are"
      if zz$<>"" print zz$;zw$" waiting for you!"

    This port's party is a plain list rather than fixed a1/a2/a3 slots,
    so every member is joined instead of replicating the "a2 missing"
    gap logic above -- functionally equivalent since a gap can't occur
    in a list.
    """
    members = list(party) if party else []
    if not members:
        return None
    names = [m.name for m in members]
    if len(names) == 1:
        waiting = names[0]
    elif len(names) == 2:
        waiting = f"{names[0]} and {names[1]}"
    else:
        waiting = ", ".join(names[:-1]) + f" and {names[-1]}"
    verb = "are" if len(names) > 1 else "is"
    return f"{waiting} {verb} waiting for you!"


def _login_news_lines(player) -> list[str]:
    """Build the login-time news display for *player*, honoring their
    command_settings.news_show_all preference (full directory every login
    vs. just what's new since player.last_connection). Marks 'once' items
    as seen and persists that back to news.json.

    Reuses news.py's helpers directly rather than commands/news.py's
    NewsCommand, since this runs before the player has a live prompt loop.
    """
    import news as news_store

    items = news_store.load_news()
    if not items:
        return []

    today   = datetime.date.today()
    since   = getattr(player, 'last_connection', None)
    show_all = getattr(player.command_settings, 'news_show_all', False)

    visible = [it for it in items if news_store.is_visible(it, player.name, today)]
    if show_all:
        to_show = visible
    else:
        to_show = [it for it in visible if news_store.is_new_since(it, since)]

    if not to_show:
        return []

    lines = ['', '|yellow|--- News ---|reset|']
    for it in to_show:
        lines += news_store.format_item(it)
        lines.append('')
        if it.get('lifetime') == 'once':
            news_store.mark_seen(it, player.name)

    news_store.save_news(items)
    return lines


def _login_tip_lines(ctx) -> list[str]:
    """Build the login-time tip display, honoring the player's
    command_settings.tips.enabled preference ('tips #on'/'tips #off').

    Reuses tips.py's next_tip()/format_tip_box() directly (same
    convention as _login_news_lines() above) -- this advances the same
    command_settings.tips.tip_number cursor commands/tips.py's bare
    'tips' command does, so the login tip and a manually-typed 'tips'
    right after don't repeat. Takes ctx (not just player) since the box
    border style/codec are terminal-aware (client_settings).
    """
    import tips as tips_store

    player = ctx.player
    if not getattr(player.command_settings, 'tips', None) or not player.command_settings.tips.enabled:
        return []

    all_tips = tips_store.load_tips()
    tip = tips_store.next_tip(player)
    if tip is None:
        return []
    box = tips_store.format_tip_box(ctx, tip, player.command_settings.tips.tip_number, len(all_tips))
    return [''] + box


def _load_credentials(username: str) -> dict | None:
    """Return the credential dict for *username*, or None if not found."""
    path = user_dir() / f"login-{username}.json"
    if not path.exists():
        return None
    try:
        with path.open() as f:
            return json.load(f)
    except Exception:
        log.exception("Failed to read credential file for %r", username)
        return None


class ConnectCommand(Command):
    """Authenticate a player and transition them into the game world.

    Handles three cases:
      connect guest               — anonymous guest session
      connect <user> <password>   — full login
      connect <user>              — prompts for password interactively
    """

    name    = "connect"
    aliases = ["con", "login"]
    modes   = {Mode.LOGIN}

    help = Help(
        summary     = "Connect to the server and log in.",
        description = (
            "Authenticates you and drops you into the game world.  "
            "Guest sessions are temporary and do not persist between connections.  "
            "The guest name increments automatically ('Guest 1', 'Guest 2', …) "
            "based on how many guests are already online."
        ),
        category = HelpCategory.AUTHENTICATION,
        usage    = [
            ("connect <username> <password>", "Log in with your credentials."),
            ("connect <username>",            "Log in — you will be prompted for your password."),
            ("connect guest",                 "Enter as a temporary guest."),
        ],
        examples = [
            ("connect alexa s3cr3t",  "Log in as 'alexa'."),
            ("connect guest",         "If two guests are online you become 'Guest 3'."),
        ],
        notes = [
            "Passwords are not case-sensitive.",
            "Type 'new' to create a new account.",
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        if not positional:
            await ctx.send(
                "Usage:  connect <username> [<password>]",
                "        connect guest",
                "Type 'new' to create a new character.",
            )
            return CommandResult.fail(
                "Please supply a username and password.",
                error="missing_args",
            )

        username = positional[0].lower()
        password = positional[1] if len(positional) > 1 else None

        logging.debug(f"{username}:{password}")

        if username == "guest":
            return await self._handle_guest(ctx)

        if password is None:
            password = await ctx.prompt("Password")
            if not password:
                return CommandResult.fail(
                    "Password is required.",
                    error="missing_password",
                )

        return await self._authenticate(ctx, username, password)

    async def _handle_guest(self, ctx: GameContext) -> CommandResult:
        """Set up a guest session."""
        # Count guests already online to pick the next available number.
        # ctx.server.clients is a dict of addr -> Client.
        guest_count = 0
        try:
            for client in ctx.server.clients.values():
                name = getattr(client, "username", "") or ""
                if name.lower().startswith("guest"):
                    guest_count += 1
        except AttributeError:
            pass  # server or clients not available (e.g. in tests)

        guest_name = f"Guest {guest_count + 1}" if guest_count else "Guest"

        ctx.client.username = guest_name
        ctx.player.name = guest_name

        # Switch the shared processor to GAME mode — no new processor needed.
        processor = getattr(ctx.client, "command_processor", None)
        if processor:
            processor.current_mode = Mode.GAME
            processor.context.update({"username": guest_name, "is_authenticated": False})

        await ctx.send(
            f"Welcome, {guest_name}!",
            "You are connected as a guest.  Your session will not be saved.",
            "Type 'help' for a list of commands.",
        )
        log.info("Guest connected as %r from %s", guest_name,
                 getattr(ctx.client, "addr", "unknown"))
        return CommandResult(
            success=True,
            message=f"Connected as {guest_name}.",
            data={"authenticated": True, "username": guest_name},
        )

    async def _authenticate(self, ctx: GameContext,
                            username: str, password: str) -> CommandResult:
        """Verify credentials, load player state, and transition to GAME mode."""
        creds = _load_credentials(username)

        if creds is None:
            await ctx.send("Invalid username or password.")
            log.warning("Login attempt for unknown user %r", username)
            return CommandResult.fail(
                "Invalid username or password.",
                error="authentication_failed",
            )

        matched, rehashed = verify_password(password, creds.get("password", ""))
        if not matched:
            await ctx.send("Invalid username or password.")
            log.warning("Bad password for user %r", username)
            return CommandResult.fail(
                "Invalid username or password.",
                error="authentication_failed",
            )

        # Transparently upgrade a legacy plaintext account to a bcrypt hash
        # now that we know the password is correct.
        if rehashed:
            try:
                creds["password"] = rehashed
                (user_dir() / f"login-{username}.json").write_text(
                    json.dumps(creds, indent=2)
                )
                log.info("Upgraded legacy plaintext password to bcrypt for %r", username)
            except Exception:
                log.exception("Failed to upgrade password hash for %r", username)

        # Ban check — after password so we don't reveal which accounts exist,
        # but before loading player data.
        from commands.ban import is_banned
        banned, ban_msg = is_banned(username)
        if banned:
            await ctx.send(ban_msg)
            log.warning("Blocked banned user %r from logging in", username)
            return CommandResult.fail("Account suspended.", error="banned")

        # Flavor text while loading — original SPUR displayed this while
        # reading the player record from disk.
        await ctx.send(
            "There is a large... well... illusion here, obviously from the great SPUR "
            "himself.  Somehow you are told to wait until your... death (?!) papers are "
            "completely in order.  A tingling runs up your spine as you wonder if your "
            "spine will be there, in one piece tomorrow."
        )

        # --- success ---
        # Replace the GuestPlayer stub with a real Player, preserving the
        # terminal settings that were negotiated before login.
        from player import Player
        char_name = creds.get('char_name') or username
        player = Player(name=char_name, id=username)  # __init__ calls _load() internally

        # Carry over terminal settings negotiated before login.
        guest_cs = getattr(ctx.player, 'client_settings', None)
        if guest_cs is not None:
            cs = player.client_settings
            for attr in ('screen_columns', 'translation', 'border_style', 'return_key'):
                if hasattr(guest_cs, attr):
                    setattr(cs, attr, getattr(guest_cs, attr))
        ctx.player = player
        ctx.client.username = username

        # Resumable character creation: a paused, unfinished character
        # (commands/new_player.py's main_flow()'s _handle_abandon_or_pause())
        # has creation_done=False and a saved creation_step. Route back into
        # main_flow() at that step instead of the normal game loop -- still
        # Mode.LOGIN at this point, so the processor mode switch and normal
        # welcome text below never run for these players.
        if getattr(player, 'creation_done', True) is False:
            from commands.new_player import main_flow
            return await main_flow(
                ctx, player=player,
                resume_step=getattr(player, 'creation_step', 0) or 0,
            )

        # Set carrying capacity by race.
        # TODO: enforce cap in inventory add/pickup; currently just stored on player.
        race = getattr(player, 'race', None)
        player.max_inventory_size = _carry_capacity(race)

        # Switch the shared processor to GAME mode — no new processor needed.
        processor = getattr(ctx.client, "command_processor", None)
        if processor:
            processor.current_mode = Mode.GAME
            processor.context.update({"username": username, "is_authenticated": True})

        # --- Aggregate all login text into one send so the C64 terminal
        #     doesn't scroll past the welcome block before the player can read it.
        login_lines: list[str] = []

        # Welcome message.
        # TODO: append ", Wraith Master of Spur!" if player has WRAITH_MASTER flag.
        wraith = player.query_flag(PlayerFlags.WRAITH_MASTER)
        title  = ", Wraith Master of Spur!" if wraith else "!"
        login_lines.append(f"Welcome, {player.name}{title}")

        # TODO: track and display "The last Adventurer was {name}" (requires a
        #  global last-player record written on quit, e.g. run/server/last_player.txt).

        # Guild welcome.
        guild = getattr(player, 'guild', Guild.CIVILIAN)
        welcome = guild_welcome_line(guild)
        if welcome:
            login_lines.append(welcome)

        # New in TADA: was the raw str(datetime) repr ("2026-07-11
        # 14:32:01.123456"); %B %d, %Y matches this codebase's other
        # player-facing date formatting (editplayer.py birthday, ban.py
        # suspension date). No per-player timezone/format preference yet
        # -- see TODO.md.
        login_lines.append(f"You last connected on {player.last_connection.strftime('%B %d, %Y')}.")
        login_lines.append("")

        # News since last login -- see news.py for storage/visibility rules
        # and commands/news.py for the standalone 'news' command that reuses
        # the same helpers.
        news_lines = _login_news_lines(player)
        if news_lines:
            login_lines += news_lines

        # Tip of the day -- see commands/tips.py and tips.py.
        tip_lines = _login_tip_lines(ctx)
        if tip_lines:
            login_lines += tip_lines

        player.last_connection = datetime.datetime.now()
        player.unsaved_changes = True

        # --- Status summary ---
        login_lines += ["Current status:", ""]

        room_desc = player.query_flag(PlayerFlags.ROOM_DESCRIPTIONS)
        login_lines.append(f"Room descriptions: {'On' if room_desc else 'Off'}")

        poisoned = player.query_flag(PlayerFlags.POISON)
        login_lines.append(f"You {'ARE' if poisoned else 'are NOT'} poisoned.")

        diseased = player.query_flag(PlayerFlags.DISEASE)
        login_lines.append(f"You {'ARE' if diseased else 'are NOT'} diseased.")

        autoduel = player.query_flag(PlayerFlags.GUILD_AUTODUEL)
        login_lines.append(f"Auto duel: {'ON' if autoduel else 'OFF'}")

        # TODO: show "Your character WILL/WILL NOT follow other guild members"
        #       once GUILD_FOLLOW_MODE is fully wired into movement. Gate on
        #       real guild membership when this lands (SPUR.MISC5.S:202's
        #       vv>=3 -- Civilian AND Outlaw are both below that cutoff, per
        #       commands/stats.py's own Guild Follow line, Ryan's request).

        # TODO: show "You followed {name} to your current location" — requires
        #       storing the guild-follow leader name in player/misc data.

        # TODO: warn if Amulet of Life has expired (AMULET_OF_LIFE_ENERGIZED flag
        #       cleared between sessions based on time elapsed).

        # TODO: warn if Wizard's Glow spell has dissipated (spell decay on logout).

        # Party members waiting (SPUR.LOGON.S ally greeting -- master only).
        waiting_line = _party_waiting_line(getattr(player, 'party', None))
        if waiting_line:
            login_lines.append(waiting_line)

        await ctx.send(login_lines)

        # TODO: daily time limit check — if today's play time >= limit, show
        #       "Alas...the sun has set on yet another adventurer..." and disconnect.
        #       Requires tracking eu (elapsed time today) in player data.

        # Broadcast to room so other players see the arrival.
        await ctx.send_room(f'{player.name} has awakened.', exclude_self=True)

        log.info("User %r authenticated from %s", username,
                 getattr(ctx.client, "addr", "unknown"))
        return CommandResult(
            success=True,
            message=f"Authenticated as {username}.",
            data={"authenticated": True, "username": username},
        )

    # ------------------------------------------------------------------
    # TODO: _show_login_status
    # Keep as a stub — will be used when multi-character support lands.
    # At that point, load characters from the user's login-x.json file
    # and let the player choose which one to enter the world with.
    # ------------------------------------------------------------------

    async def _show_login_status(self, ctx: GameContext) -> CommandResult:
        """Show available characters for an already-authenticated user.

        Not yet wired into execute() — placeholder for multi-character support.
        """
        username = getattr(ctx.client, "username", None)
        if not username:
            await ctx.send(
                "You are not currently logged in.",
                "Use: connect <username> <password>",
                "     connect guest",
                "     new  (to create a character)",
            )
            return CommandResult.ok()

        # TODO: load character list from login-<username>.json
        characters: list = []

        if characters:
            char_list = "\n  ".join(characters)
            await ctx.send(
                f"Welcome back, {username}!",
                "Your characters:",
                f"  {char_list}",
                "To play a character, type: play <character>",
            )
        else:
            await ctx.send(
                f"Welcome, {username}!",
                "You don't have any characters yet.",
                "To create a new character, type: new",
            )
        return CommandResult.ok()
