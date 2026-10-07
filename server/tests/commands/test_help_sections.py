"""tests/commands/test_help_sections.py — flag-gated Help sections
(commands/help.py's HelpSection / Help.sections) and their first user,
'help helpstaff''s "Helpstaff" section."""
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.help import Help, HelpCommand, HelpSection, format_help, _viewer_flags
from commands.helpstaff import STAFF_SWITCHES, HelpstaffCommand
from flags import PlayerFlags


def _text(lines) -> str:
    return "\n".join(lines or [])


def _player(*flags_set):
    p = MagicMock()
    p.name = 'Viewer'
    p.client_settings.screen_columns = 78
    p.query_flag.side_effect = lambda f: f in flags_set
    return p


def _help_ctx(player, *commands):
    ctx = MagicMock()
    ctx.send = AsyncMock()
    ctx.player = player
    proc = MagicMock()
    cmd_dict = {c.name: c for c in commands}
    proc.get_all_commands.return_value = cmd_dict
    proc.find_command.side_effect = lambda name: (cmd_dict.get(name), name in cmd_dict)
    proc.search_commands.side_effect = lambda term: [
        c for c in cmd_dict.values()
        if term.lower() in c.help.summary.lower() or term.lower() in c.help.description.lower()
    ]
    ctx.client.command_processor = proc
    ctx.command_processor = proc
    return ctx


def _sent(ctx) -> str:
    return "\n".join(str(a) for call in ctx.send.await_args_list for a in call.args)


SAMPLE = Help(
    summary="Sample.",
    usage=[("sample", "Anyone can do this.")],
    sections=[HelpSection(
        title="Wizards",
        flags=(PlayerFlags.HELPSTAFF,),
        usage=[("sample #secret", "Only staff [<n>] see this.")],
        notes=["A staff-only note."],
    )],
)


class TestHelpSectionFormatting(unittest.TestCase):

    def test_hidden_without_flag(self):
        out = _text(format_help(SAMPLE, width=78))
        self.assertIn("Anyone can do this.", out)
        self.assertNotIn("Wizards", out)
        self.assertNotIn("#secret", out)
        self.assertNotIn("staff-only note", out)

    def test_shown_with_flag(self):
        out = _text(format_help(SAMPLE, width=78, viewer_flags={PlayerFlags.HELPSTAFF}))
        self.assertIn("Wizards:", out)
        self.assertIn("sample #secret", out)
        self.assertIn("A staff-only note.", out)

    def test_other_flags_do_not_unlock_it(self):
        out = _text(format_help(SAMPLE, width=78, viewer_flags={PlayerFlags.ORATOR}))
        self.assertNotIn("Wizards", out)

    def test_privileged_viewer_sees_every_section(self):
        out = _text(format_help(SAMPLE, width=78, is_privileged=True))
        self.assertIn("Wizards:", out)

    def test_section_usage_is_auto_escaped(self):
        # Same [optional] auto-escaping as plain usage rows.
        out = _text(format_help(SAMPLE, width=78, viewer_flags={PlayerFlags.HELPSTAFF}))
        self.assertIn("[[<n>]]", out)

    def test_section_comes_after_notes_and_before_admin_notes(self):
        h = Help(summary="S.", notes=["plain note"], admin_notes=["admin note"],
                 sections=[HelpSection(title="Staff", flags=(PlayerFlags.HELPSTAFF,),
                                       notes=["staff note"])])
        out = _text(format_help(h, width=78, is_privileged=True))
        self.assertLess(out.index("plain note"), out.index("Staff:"))
        self.assertLess(out.index("staff note"), out.index("admin note"))

    def test_viewer_flags_reads_player(self):
        ctx = MagicMock()
        ctx.player = _player(PlayerFlags.HELPSTAFF)
        self.assertEqual(_viewer_flags(ctx), {PlayerFlags.HELPSTAFF})

    def test_viewer_flags_without_player(self):
        self.assertEqual(_viewer_flags(object()), set())


class TestHelpHelpstaff(unittest.IsolatedAsyncioTestCase):
    """The real 'help helpstaff' as different viewers."""

    async def _help(self, player) -> str:
        ctx = _help_ctx(player, HelpstaffCommand())
        result = await HelpCommand().execute(ctx, 'helpstaff')
        self.assertTrue(result.success)
        return _sent(ctx)

    async def test_plain_player_sees_no_staff_switches(self):
        out = await self._help(_player())
        for public in ('helpstaff #ask', 'helpstaff #show', 'helpstaff #cancel'):
            self.assertIn(public, out)
        for hidden in ('Helpstaff:', '#faq', '#queue', '#on', '#off',
                       '#list', '#accept', '#decline', 'Staff'):
            self.assertNotIn(hidden, out, hidden)

    async def test_member_sees_helpstaff_section(self):
        out = await self._help(_player(PlayerFlags.HELPSTAFF))
        self.assertIn('Helpstaff:', out)
        for switch in ('#faq #add', '#queue', '#on', '#accept <name>'):
            self.assertIn(switch, out)
        self.assertNotIn('Admin Notes:', out)     # a member isn't an Admin

    async def test_admin_and_dm_see_it_too(self):
        for flag in (PlayerFlags.ADMIN, PlayerFlags.DUNGEON_MASTER):
            out = await self._help(_player(flag))
            self.assertIn('Helpstaff:', out, flag)
            self.assertIn('#faq', out, flag)

    async def test_search_does_not_reveal_staff_switches(self):
        # 'help #search' only searches summary/description, which hold
        # nothing staff-only.
        ctx = _help_ctx(_player(), HelpstaffCommand())
        await HelpCommand().execute(ctx, '#search', 'faq')
        self.assertNotIn('helpstaff', _sent(ctx).lower())


class TestStaffSwitchesHiddenFromPlayers(unittest.IsolatedAsyncioTestCase):

    async def test_plain_player_gets_unknown_option(self):
        for switch in sorted(STAFF_SWITCHES):
            ctx = MagicMock()
            ctx.send = AsyncMock()
            ctx.player = _player()
            result = await HelpstaffCommand().execute(ctx, switch, 'x')
            self.assertFalse(result.success, switch)
            self.assertEqual(result.error, 'bad_option', switch)
            self.assertIn(f"Unknown option '{switch}'", _sent(ctx), switch)
            self.assertNotIn('helpstaff member', _sent(ctx).lower(), switch)

    def test_staff_switches_are_exactly_the_gated_section(self):
        # Every switch in the Helpstaff section is hidden from players, and
        # nothing in the public usage is.
        section = HelpstaffCommand.help.sections[0]
        gated = {row[0].split()[1] for row in section.usage}
        public = {row[0].split()[1] for row in HelpstaffCommand.help.usage if ' ' in row[0]}
        self.assertEqual(gated, set(STAFF_SWITCHES))
        self.assertFalse(public & STAFF_SWITCHES)


if __name__ == '__main__':
    unittest.main()


class TestUsageSyntaxColor(unittest.TestCase):
    """Usage/Examples syntax is wrapped in |command|...|reset| (the
    viewer's PREFS command color), including a section's usage and a
    syntax too long for its column that gets its own line."""

    def test_usage_and_examples_colored(self):
        h = Help(summary="S.", usage=[("say <message>", "Speak.")],
                 examples=[("say Hello!", "Greet.")])
        out = _text(format_help(h, width=78))
        self.assertIn("|command|say <message>|reset|", out)
        self.assertIn("|command|say Hello!|reset|", out)

    def test_section_usage_colored(self):
        out = _text(format_help(SAMPLE, width=78, viewer_flags={PlayerFlags.HELPSTAFF}))
        self.assertIn("|command|sample #secret|reset|", out)

    def test_long_syntax_on_its_own_line_is_colored(self):
        out = format_help(HelpstaffCommand.help, 'helpstaff', width=40,
                          viewer_flags={PlayerFlags.HELPSTAFF})
        own_line = next(l for l in out if 'helpstaff #accept <name>' in l)
        self.assertEqual(own_line.strip(), '|command|helpstaff #accept <name>|reset|')
