"""commands/connect.py

The 'connect' command — handles login and guest access.

Available only in LOGIN mode (you can't connect again once you're already
in-game).  Auto-discovered by CommandProcessor.discover().
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from network_context import GameContext
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory

log = logging.getLogger(__name__)

# Path pattern for per-user credential files.
# Expected layout: run/server/net/login-<username>.json
# Each file must contain at least {"password": "<plaintext>"}.
# TODO: replace plaintext passwords with a proper hash (bcrypt / argon2).
_USER_DIR = Path("run") / "server" / "net"


def _load_credentials(username: str) -> dict | None:
    """Return the credential dict for *username*, or None if not found."""
    path = _USER_DIR / f"login-{username}.json"
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

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

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

        # --- guest ---
        if username == "guest":
            return await self._handle_guest(ctx)

        # --- full login: prompt for password if not supplied ---
        if password is None:
            password = await ctx.prompt("Password")
            if not password:
                return CommandResult.fail(
                    "Password is required.",
                    error="missing_password",
                )

        return await self._authenticate(ctx, username, password)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
        """Verify credentials and, on success, transition to GAME mode."""
        creds = _load_credentials(username)

        if creds is None:
            # Don't reveal whether the username exists.
            await ctx.send("Invalid username or password.")
            log.warning("Login attempt for unknown user %r", username)
            return CommandResult.fail(
                "Invalid username or password.",
                error="authentication_failed",
            )

        # TODO: replace with constant-time hash comparison (bcrypt).
        # Passwords are compared case-insensitively — C64 keyboards send
        # uppercase by default, so 'FESCUE' must match stored 'fescue'.
        if creds.get("password", "").lower() != password.lower():
            await ctx.send("Invalid username or password.")
            log.warning("Bad password for user %r", username)
            return CommandResult.fail(
                "Invalid username or password.",
                error="authentication_failed",
            )

        # --- success ---
        ctx.client.username = username

        # Replace the GuestPlayer stub with a real Player, preserving the
        # terminal settings that were negotiated before login.
        from player import Player
        char_name = creds.get('char_name') or username
        player = Player(name=char_name)
        guest_cs = getattr(ctx.player, 'client_settings', None)
        if guest_cs is not None:
            cs = player.client_settings
            for attr in ('screen_columns', 'translation', 'border_style', 'return_key'):
                if hasattr(guest_cs, attr):
                    setattr(cs, attr, getattr(guest_cs, attr))
        ctx.player = player

        # Switch the shared processor to GAME mode — no new processor needed.
        processor = getattr(ctx.client, "command_processor", None)
        if processor:
            processor.current_mode = Mode.GAME
            processor.context.update({"username": username, "is_authenticated": True})

        await ctx.send(f"Welcome back, {ctx.player.name}!")
        await ctx.send(f"You last connected on {ctx.player.last_connection}.")
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
