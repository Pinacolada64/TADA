"""commands/password.py — change your account login password."""
import json
import logging

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from net_common import hash_password, user_dir, verify_password

log = logging.getLogger(__name__)


class PasswordCommand(Command):
    """Change the password used to log in (separate from your character name)."""

    name    = 'password'
    aliases = ['passwd']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Change your account login password.',
        description = (
            "Prompts for your current password, then a new one (entered "
            "twice to confirm). This is your login password, not your "
            "character name -- it's kept separate for a planned link to a "
            "CommodoreServer.com account."
        ),
        category = HelpCategory.AUTHENTICATION,
        usage    = [('password', 'Change your login password.')],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        username = getattr(ctx.player, 'id', None)
        if not username:
            await ctx.send("You don't have a login account to change a password on.")
            return CommandResult.fail("No account.", error="no_account")

        path = user_dir() / f'login-{username}.json'
        try:
            creds = json.loads(path.read_text())
        except Exception:
            log.exception("Failed to read credential file for %r", username)
            await ctx.send("Something went wrong reading your account.  Try again later.")
            return CommandResult.fail("Read failed.", error="read_failed")

        current = await ctx.prompt('Current password')
        if current is None:
            return CommandResult.fail("Password change abandoned.", error="abandoned")
        matched, _ = verify_password(current.strip(), creds.get('password', ''))
        if not matched:
            await ctx.send("Incorrect password.")
            log.warning("Wrong current password on password-change attempt for %r", username)
            return CommandResult.fail("Incorrect password.", error="wrong_password")

        while True:
            pw1 = await ctx.prompt(
                'New password',
                preamble_lines=['', 'Choose a new password (at least 4 characters).'],
            )
            if pw1 is None:
                return CommandResult.fail("Password change abandoned.", error="abandoned")
            pw1 = pw1.strip()
            # TODO: if pw1 is blank (bare Enter), treat it as "keep the
            # current password" -- send "Password unchanged." and return
            # CommandResult.ok() instead of falling through to the
            # too-short error/reprompt below.
            if len(pw1) < 4:
                await ctx.send("Password must be at least 4 characters.  Try again.")
                continue

            pw2 = await ctx.prompt('Confirm new password')
            if pw2 is None:
                return CommandResult.fail("Password change abandoned.", error="abandoned")
            if pw2.strip() != pw1:
                await ctx.send("Passwords do not match.  Try again.")
                continue
            break

        creds['password'] = hash_password(pw1)
        try:
            path.write_text(json.dumps(creds, indent=2))
        except Exception:
            log.exception("Failed to write new password for %r", username)
            await ctx.send("Something went wrong saving your new password.  Try again later.")
            return CommandResult.fail("Write failed.", error="write_failed")

        await ctx.send("Password changed.")
        log.info("Password changed for %r", username)
        return CommandResult.ok("Password changed.")
