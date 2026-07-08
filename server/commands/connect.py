"""commands/connect.py

The 'connect' command — handles login and guest access.

Available only in LOGIN mode (you can't connect again once you're already
in-game).  Auto-discovered by CommandProcessor.discover().
"""

from __future__ import annotations

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

# Guild welcome messages matching original SPUR symbols.
_GUILD_WELCOME = {
    Guild.CLAW:  ("The Guild of the Claw bids",   r"you, 'Welcome!' \|/"),
    Guild.SWORD: ("The Guild of the Sword bids",   "you, 'Welcome!' -}----"),
    Guild.FIST:  ("The Guild of the Iron Fist bids", "you, 'Welcome!' ==[]"),
}


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
        if guild in _GUILD_WELCOME:
            line1, line2 = _GUILD_WELCOME[guild]
            login_lines += [line1, line2]

        login_lines.append(f"You last connected on {player.last_connection}.")
        login_lines.append("")

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
        #       once GUILD_FOLLOW_MODE is fully wired into movement.

        # TODO: show "You followed {name} to your current location" — requires
        #       storing the guild-follow leader name in player/misc data.

        # TODO: warn if Amulet of Life has expired (AMULET_OF_LIFE_ENERGIZED flag
        #       cleared between sessions based on time elapsed).

        # TODO: warn if Wizard's Glow spell has dissipated (spell decay on logout).

        # Party members waiting.
        party = getattr(player, 'party', None)
        if party:
            members = list(party)
            if members:
                names = [m.name for m in members]
                if len(names) == 1:
                    waiting = names[0]
                elif len(names) == 2:
                    waiting = f"{names[0]} and {names[1]}"
                else:
                    waiting = ", ".join(names[:-1]) + f" and {names[-1]}"
                verb = "are" if len(names) > 1 else "is"
                login_lines.append(f"{waiting} {verb} waiting for you!")

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
