#!/usr/bin/env python3
"""tests/test_help.py

Unit tests for commands/help.py.

Run with:
    python -m pytest tests/test_help.py -v
    python -m unittest tests.test_help
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# 1. Fix sys.path FIRST so 'commands/' is findable from tests/commands/
#    __file__ is  .../server/tests/commands/test_help.py
#    ROOT  is  .../server/
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# 2. Now import from commands/ — path is correct
#
#    Historically this file stubbed out network_context/net_common here
#    with bare types.ModuleType(...) placeholders via sys.modules.setdefault(),
#    on the theory that commands.help needed protecting from those "heavy"
#    imports. It doesn't: commands/help.py only references GameContext
#    inside a `if TYPE_CHECKING:` guard (never imported at runtime), and
#    commands/base_command.py doesn't touch either module at all. Because
#    pytest imports every test module during collection (before any test
#    runs), that setdefault() permanently installed an empty, attribute-less
#    network_context stub in sys.modules for the rest of the pytest
#    session -- any other code anywhere in the suite that later did
#    `from network_context import GameContext` (e.g. base_classes.py, or
#    terminal.py's import chain) hit the stub instead of the real module
#    and failed with "cannot import name 'GameContext' from 'network_context'
#    (unknown location)". Several other files under tests/ do the same
#    setdefault()-a-stub trick for network_context/net_common; if one of
#    those starts causing this failure elsewhere, the fix is the same:
#    delete the stub once you've confirmed (by grepping that file's own
#    imports) that nothing it actually imports needs it.
# ---------------------------------------------------------------------------
from commands.help import (
    Help, HelpCategory, HelpCommand, format_help, _TOPICS,
    _find_topic_by_substring, _exact_category, _match_categories,
)
from commands.base_command import CommandResult
import commands.help as help_mod


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _make_ctx(screen_columns: int = 78):
    ctx = MagicMock()
    ctx.send  = AsyncMock()
    ctx.player.client_settings.screen_columns = screen_columns
    return ctx


def _make_processor(*commands):
    """Return a minimal processor-like stub pre-loaded with commands."""
    proc     = MagicMock()
    cmd_dict = {getattr(c, "name", str(i)): c for i, c in enumerate(commands)}
    proc.get_all_commands.return_value = cmd_dict
    proc.find_command.side_effect      = lambda name: (
        cmd_dict.get(name), name in cmd_dict
    )
    proc.search_commands.side_effect   = lambda term: [
        c for c in cmd_dict.values()
        if term.lower() in getattr(c, "name", "").lower()
        or term.lower() in getattr(getattr(c, "help", None), "summary", "").lower()
    ]
    return proc


def _make_cmd(name: str, aliases=None,
              category=HelpCategory.GENERAL, summary: str = ""):
    """Return a minimal command stub with a Help instance attached."""
    cmd         = MagicMock()
    cmd.name    = name
    cmd.aliases = aliases or []
    cmd.help    = Help(
        summary  = summary or f"Summary for {name}.",
        category = category,
        usage    = [(f"{name} <arg>", "Does something.")],
    )
    return cmd


def _ctx_with_processor(*commands):
    ctx  = _make_ctx()
    proc = _make_processor(*commands)
    ctx.client.command_processor = proc
    ctx.command_processor        = proc
    return ctx, proc


# ---------------------------------------------------------------------------
# Color helpers -- |token| markup for headings/rules/commands/aliases
# ---------------------------------------------------------------------------

class TestColorHelpers(unittest.TestCase):

    def test_heading_is_yellow(self):
        self.assertEqual(help_mod._heading("Usage:"), "|yellow|Usage:|reset|")

    def test_rule_is_dark_gray(self):
        self.assertEqual(help_mod._rule("---"), "|dark_gray|---|reset|")

    def test_cmd_is_cyan(self):
        self.assertEqual(help_mod._cmd("quote"), "|cyan|quote|reset|")

    def test_alias_is_darker_than_command(self):
        """The user's one explicit ask: aliases render in a slightly
        darker color than the command name itself."""
        cmd_color   = help_mod._cmd("quote")
        alias_color = help_mod._alias("(q)")
        self.assertIn("|cyan|", cmd_color)
        self.assertIn("|dark_gray|", alias_color)
        self.assertNotEqual(cmd_color.split("|")[1], alias_color.split("|")[1])

    def test_all_color_tokens_render_on_ansi_and_petscii(self):
        """Every token used here must exist in both ANSI_COLOR_CODES and
        PETSCII_CONTROL_CODES -- otherwise it'd silently break (or worse,
        show a literal '|token|' string) on one terminal type."""
        from formatting import ANSI_COLOR_CODES, PETSCII_CONTROL_CODES
        for token in ("yellow", "dark_gray", "cyan"):
            self.assertIn(token, ANSI_COLOR_CODES)
            self.assertIn(token, PETSCII_CONTROL_CODES)

    def test_vis_ljust_ignores_token_markup(self):
        colored = help_mod._cmd("go")  # 2 visible chars, much longer raw string
        padded  = help_mod._vis_ljust(colored, 10)
        from formatting import _visible_len
        self.assertEqual(_visible_len(padded), 10)

    def test_vis_ljust_no_padding_needed(self):
        text = "already-long-enough"
        self.assertEqual(help_mod._vis_ljust(text, 5), text)


# ---------------------------------------------------------------------------
# format_summary_table() — pure formatter, no I/O
# ---------------------------------------------------------------------------

class TestFormatSummaryTable(unittest.TestCase):

    def test_empty_items_returns_empty(self):
        self.assertEqual(help_mod.format_summary_table([], 78), [])

    def test_rows_alternate_stripe_color(self):
        items = [("say", "First."), ("shout", "Second."), ("page", "Third.")]
        lines = help_mod.format_summary_table(items, 78)
        self.assertIn("|mid_gray|",  lines[0])
        self.assertIn("|dark_gray|", lines[1])
        self.assertIn("|mid_gray|",  lines[2])

    def test_name_rendered_with_cmd_color(self):
        lines = help_mod.format_summary_table([("say", "Speak aloud.")], 78)
        self.assertIn("|cyan|say|reset|", lines[0])

    def test_no_line_exceeds_width(self):
        from formatting import _visible_len
        items = [("attack", "A very long summary " * 5)]
        lines = help_mod.format_summary_table(items, 40)
        for line in lines:
            self.assertLessEqual(_visible_len(line), 40)


# ---------------------------------------------------------------------------
# format_help() — pure formatter, no I/O
# ---------------------------------------------------------------------------

class TestFormatHelp(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(format_help(None))

    def test_plain_string_is_word_wrapped(self):
        out = format_help("short string")
        self.assertIsInstance(out, str)
        self.assertIn("short string", out)

    def _fmt(self, *args, **kwargs):
        """Return format_help output as a single joined string for assertions."""
        result = format_help(*args, **kwargs)
        return "\n".join(result) if isinstance(result, list) else (result or "")

    def test_summary_appears_in_output(self):
        h = Help(summary="Does the thing.")
        self.assertIn("Does the thing.", self._fmt(h))

    def test_command_name_appears_as_header(self):
        h = Help(summary="Thing.")
        self.assertIn("mytool", self._fmt(h, command_name="mytool"))

    def test_usage_section_present(self):
        h = Help(usage=[("cmd <arg>", "Does something.")])
        self.assertIn("Usage:", self._fmt(h))

    def test_single_example_label(self):
        out = self._fmt(Help(examples=[("cmd foo", "one example")]))
        self.assertIn("Example:", out)
        self.assertNotIn("Examples:", out)

    def test_multiple_examples_label(self):
        self.assertIn("Examples:", self._fmt(Help(examples=[("cmd foo", "first"), ("cmd bar", "second")])))

    def test_notes_section_present(self):
        out = self._fmt(Help(notes=["A useful note."]))
        self.assertIn("Notes:", out)
        self.assertIn("A useful note.", out)

    def test_admin_notes_hidden_by_default(self):
        h = Help(notes=["Regular note."], admin_notes=["Admin-only note."])
        out = self._fmt(h)
        self.assertIn("Regular note.", out)
        self.assertNotIn("Admin-only note.", out)

    def test_admin_notes_shown_when_privileged(self):
        h = Help(notes=["Regular note."], admin_notes=["Admin-only note."])
        out = self._fmt(h, is_privileged=True)
        self.assertIn("Regular note.", out)
        self.assertIn("Admin-only note.", out)

    def test_admin_notes_alone_shows_admin_notes_heading_when_privileged(self):
        h = Help(admin_notes=["Admin-only note."])
        out = self._fmt(h, is_privileged=True)
        self.assertIn("Admin Notes:", out)
        self.assertNotIn("|Notes:|", out)  # plain "Notes:" heading absent -- only Admin Notes
        self.assertIn("Admin-only note.", out)

    def test_admin_notes_render_as_separate_section_from_notes(self):
        h = Help(notes=["Regular note."], admin_notes=["Admin-only note."])
        out = self._fmt(h, is_privileged=True)
        self.assertIn("Notes:", out)
        self.assertIn("Admin Notes:", out)

    def test_admin_notes_alone_produces_no_notes_section_when_not_privileged(self):
        h = Help(admin_notes=["Admin-only note."])
        out = self._fmt(h, is_privileged=False)
        self.assertNotIn("Notes:", out)
        self.assertNotIn("Admin Notes:", out)
        self.assertNotIn("Admin-only note.", out)

    def test_petscii_notes_hidden_by_default(self):
        h = Help(notes=["Regular note."], petscii_notes=["PETSCII-only note."])
        out = self._fmt(h)
        self.assertIn("Regular note.", out)
        self.assertNotIn("PETSCII-only note.", out)

    def test_petscii_notes_shown_when_is_petscii(self):
        h = Help(notes=["Regular note."], petscii_notes=["PETSCII-only note."])
        out = self._fmt(h, is_petscii=True)
        self.assertIn("Regular note.", out)
        self.assertIn("PETSCII-only note.", out)

    def test_petscii_notes_and_admin_notes_are_independent(self):
        h = Help(admin_notes=["Admin-only."], petscii_notes=["PETSCII-only."])
        out = self._fmt(h, is_privileged=True, is_petscii=False)
        self.assertIn("Admin-only.", out)
        self.assertNotIn("PETSCII-only.", out)

    def test_all_sections_together(self):
        h = Help(
            summary     = "Short summary.",
            description = "Longer description.",
            usage       = [("cmd <arg>", "Does something.")],
            examples    = [("cmd foo", "An example.")],
            notes       = ["A note."],
        )
        out = self._fmt(h, command_name="cmd")
        for expected in ("Usage:", "Example:", "Notes:", "cmd <arg>", "A note."):
            self.assertIn(expected, out)

    def test_width_80_no_line_exceeds(self):
        # Lines may carry |token| color markup now (headings/rules/command
        # names) -- assert on visible width, not raw string length.
        from formatting import _visible_len
        h = Help(summary="x", usage=[("editplayer", "Edit your character interactively.")])
        lines = format_help(h, width=80)
        for line in (lines if isinstance(lines, list) else []):
            self.assertLessEqual(_visible_len(line), 80, f"Line too long: {line!r}")

    def test_width_40_no_line_exceeds(self):
        from formatting import _visible_len
        h = Help(summary="x", usage=[("editplayer", "Edit your character.")])
        lines = format_help(h, width=40)
        for line in (lines if isinstance(lines, list) else []):
            self.assertLessEqual(_visible_len(line), 40, f"Line too long: {line!r}")

    def test_aliases_section_present_when_given(self):
        h = Help(summary="Does the thing.")
        out = self._fmt(h, command_name="unwear", aliases=["remove", "doff"])
        self.assertIn("Aliases:", out)
        self.assertIn("remove", out)
        self.assertIn("doff", out)

    def test_aliases_section_absent_when_none_given(self):
        h = Help(summary="Does the thing.")
        out = self._fmt(h, command_name="unwear")
        self.assertNotIn("Aliases:", out)

    def test_aliases_section_absent_when_empty_list(self):
        h = Help(summary="Does the thing.")
        out = self._fmt(h, command_name="unwear", aliases=[])
        self.assertNotIn("Aliases:", out)


class TestSeeAlso(unittest.TestCase):
    """New in TADA: Help.see_also renders a 'See Also:' section of
    cyan-colored, comma-separated related command/topic names."""

    def _fmt(self, h, **kwargs):
        return "\n".join(format_help(h, **kwargs) or [])

    def test_absent_when_empty(self):
        h = Help(summary="x")
        self.assertNotIn("See Also:", self._fmt(h))

    def test_heading_present_when_set(self):
        h = Help(summary="x", see_also=["combat"])
        self.assertIn("See Also:", self._fmt(h))

    def test_names_rendered_in_cyan(self):
        h = Help(summary="x", see_also=["combat", "bhr"])
        out = self._fmt(h)
        self.assertIn("|cyan|combat|reset|", out)
        self.assertIn("|cyan|bhr|reset|", out)

    def test_names_comma_separated(self):
        h = Help(summary="x", see_also=["combat", "bhr"])
        out = self._fmt(h)
        self.assertIn("|cyan|combat|reset|, |cyan|bhr|reset|", out)

    def test_width_80_no_line_exceeds_with_many_entries(self):
        from formatting import _visible_len
        h = Help(summary="x", see_also=["combat", "weaponclass", "basedamage",
                                         "easeofuse", "weaponaffinity", "bhr"])
        lines = format_help(h, width=80)
        for line in lines:
            self.assertLessEqual(_visible_len(line), 80, f"Line too long: {line!r}")

    def test_width_40_no_line_exceeds_with_many_entries(self):
        from formatting import _visible_len
        h = Help(summary="x", see_also=["combat", "weaponclass", "basedamage",
                                         "easeofuse", "weaponaffinity", "bhr"])
        lines = format_help(h, width=40)
        for line in lines:
            self.assertLessEqual(_visible_len(line), 40, f"Line too long: {line!r}")


class TestCombatConceptTopics(unittest.TestCase):
    """New in TADA: combat/weaponclass/basedamage/easeofuse/weaponaffinity
    concept topics (Ryan: 'this is confusing even me') plus BHR's updated
    see_also -- all cross-link each other."""

    TOPIC_NAMES = ["combat", "weaponclass", "basedamage", "easeofuse",
                   "weaponaffinity", "bhr"]

    def test_all_new_topics_registered(self):
        for name in self.TOPIC_NAMES:
            self.assertIn(name, _TOPICS, f"{name!r} not registered as a topic")

    def test_alias_forms_also_resolve(self):
        for alias in ("best targets", "base damage", "ease of use",
                      "weapon affinity", "bad hombre", "badhombre"):
            self.assertIn(alias, _TOPICS, f"{alias!r} alias not registered")

    def test_every_see_also_entry_resolves_to_a_real_topic(self):
        # Guards against a typo'd see_also silently 404ing for a player
        # (see Help.see_also's docstring caveat).
        for name in self.TOPIC_NAMES:
            for ref in _TOPICS[name].see_also:
                self.assertIn(ref, _TOPICS, f"{name!r}.see_also has unresolvable {ref!r}")

    def test_combat_topic_renders_without_error(self):
        out = format_help(_TOPICS["combat"], command_name="combat", width=78)
        self.assertIsNotNone(out)
        self.assertTrue(any("Weapon Class" in line for line in out))


class TestCommandlineTopicBracketNotation(unittest.TestCase):
    """'commandline' concept topic now explains <required>/[optional]
    syntax (Ryan's request, tied to the [[..]]-escaping bug fixed in
    page/whisper/mail/teleport/connect's usage-reminder strings). Its
    description text uses literal [name]/[,name2] examples, which must
    be [[..]]-escaped since format_help() does NOT auto-escape
    Help.description the way it does usage/examples columns."""

    def test_mentions_angle_and_square_brackets(self):
        out = "\n".join(format_help(_TOPICS["commandline"], width=78) or [])
        self.assertIn("<name>", out)
        self.assertIn("required", out.lower())
        self.assertIn("optional", out.lower())

    def test_description_bracket_examples_survive_highlighting(self):
        from formatting import highlight_brackets, PlainCodec
        out = format_help(_TOPICS["commandline"], width=78) or []
        rendered = "\n".join(highlight_brackets(line, PlainCodec()) for line in out)
        self.assertIn("[name]", rendered)
        self.assertIn("[,name2]", rendered)


class TestPlayerMechanicsConceptTopics(unittest.TestCase):
    """honor/experience/armorcondition/specialweapon/examine/parties/
    eliteally concept topics -- TODO_HELP.md's 7/14/26 'implemented, no
    help topic yet' list."""

    TOPIC_NAMES = ["honor", "experience", "armorcondition", "specialweapon",
                   "examine", "parties", "eliteally"]

    def test_all_new_topics_registered(self):
        for name in self.TOPIC_NAMES:
            self.assertIn(name, _TOPICS, f"{name!r} not registered as a topic")

    def test_alias_forms_also_resolve(self):
        for alias in ("alignment", "xp level", "shield condition", "intactness",
                      "silver bullet", "look first", "party", "allies",
                      "elite ally"):
            self.assertIn(alias, _TOPICS, f"{alias!r} alias not registered")

    def test_every_see_also_entry_resolves_to_a_real_topic(self):
        for name in self.TOPIC_NAMES:
            for ref in _TOPICS[name].see_also:
                self.assertIn(ref, _TOPICS, f"{name!r}.see_also has unresolvable {ref!r}")

    def test_topics_render_without_error(self):
        from formatting import _visible_len
        for name in self.TOPIC_NAMES:
            out = format_help(_TOPICS[name], command_name=name, width=78)
            self.assertIsNotNone(out, f"{name!r} produced no output")
            for line in out:
                self.assertLessEqual(_visible_len(line), 78, f"{name!r} line too long: {line!r}")


class TestWorldConceptTopics(unittest.TestCase):
    """guilds/virtualareas/moreprompt/petscii/statrolling concept topics --
    TODO_HELP.md's 7/14/26 'concept topics worth adding' list, second batch."""

    TOPIC_NAMES = ["guilds", "virtualareas", "moreprompt", "petscii", "statrolling"]

    def test_all_new_topics_registered(self):
        for name in self.TOPIC_NAMES:
            self.assertIn(name, _TOPICS, f"{name!r} not registered as a topic")

    def test_alias_forms_also_resolve(self):
        for alias in ("guild", "virtual area", "more prompt", "ansi",
                      "client type", "roll stats", "4d6"):
            self.assertIn(alias, _TOPICS, f"{alias!r} alias not registered")

    def test_every_see_also_entry_resolves_to_a_real_topic(self):
        for name in self.TOPIC_NAMES:
            for ref in _TOPICS[name].see_also:
                self.assertIn(ref, _TOPICS, f"{name!r}.see_also has unresolvable {ref!r}")

    def test_topics_render_without_error(self):
        from formatting import _visible_len
        for name in self.TOPIC_NAMES:
            out = format_help(_TOPICS[name], command_name=name, width=78)
            self.assertIsNotNone(out, f"{name!r} produced no output")
            for line in out:
                self.assertLessEqual(_visible_len(line), 78, f"{name!r} line too long: {line!r}")

    def test_weaponaffinity_topic_mentions_all_nine_classes(self):
        out = "\n".join(format_help(_TOPICS["weaponaffinity"], width=78) or [])
        for cls in ("Wizard", "Druid", "Fighter", "Paladin", "Ranger",
                    "Thief", "Archer", "Assassin", "Knight"):
            self.assertIn(cls, out)

    def test_weaponaffinity_topic_mentions_all_nine_races(self):
        out = "\n".join(format_help(_TOPICS["weaponaffinity"], width=78) or [])
        for race in ("Human", "Ogre", "Pixie", "Elf", "Hobbit", "Gnome",
                     "Dwarf", "Orc", "Half-Elf"):
            self.assertIn(race, out)


class TestWorldConceptTopicsBatch2(unittest.TestCase):
    """itempersistence/horses/victory/pawnshop concept topics --
    TODO_HELP.md's 7/14/26 pass, third batch."""

    TOPIC_NAMES = ["itempersistence", "horses", "victory", "pawnshop"]

    def test_all_new_topics_registered(self):
        for name in self.TOPIC_NAMES:
            self.assertIn(name, _TOPICS, f"{name!r} not registered as a topic")

    def test_alias_forms_also_resolve(self):
        for alias in ("respawn", "horse", "mounts", "mount", "escape",
                      "conqueror", "pawn shop", "pawn"):
            self.assertIn(alias, _TOPICS, f"{alias!r} alias not registered")

    def test_every_see_also_entry_resolves_to_a_real_topic(self):
        for name in self.TOPIC_NAMES:
            for ref in _TOPICS[name].see_also:
                self.assertIn(ref, _TOPICS, f"{name!r}.see_also has unresolvable {ref!r}")

    def test_topics_render_without_error(self):
        from formatting import _visible_len
        for name in self.TOPIC_NAMES:
            out = format_help(_TOPICS[name], command_name=name, width=78)
            self.assertIsNotNone(out, f"{name!r} produced no output")
            for line in out:
                self.assertLessEqual(_visible_len(line), 78, f"{name!r} line too long: {line!r}")


class TestDwarfConceptTopic(unittest.TestCase):
    """dwarf concept topic -- The Dwarf shipped after TODO_HELP.md's
    7/14/26 pass (which had confirmed it 'Not Implemented' at the time),
    so this was a genuinely new gap found by re-checking current state."""

    def test_topic_registered(self):
        self.assertIn("dwarf", _TOPICS)

    def test_alias_forms_resolve(self):
        for alias in ("thedwarf", "the dwarf"):
            self.assertIn(alias, _TOPICS, f"{alias!r} alias not registered")

    def test_renders_without_error(self):
        from formatting import _visible_len
        out = format_help(_TOPICS["dwarf"], command_name="dwarf", width=78)
        self.assertIsNotNone(out)
        for line in out:
            self.assertLessEqual(_visible_len(line), 78, f"line too long: {line!r}")


class TestGuildsTopicDuelingIsReal(unittest.TestCase):
    """Regression guard: guilds/bhr topics previously (wrongly) claimed
    live dueling wasn't implemented -- combat/duel.py's DuelCommand
    already existed as of 7/14/26, so this was stale even before this
    session started. Confirms the corrected wording stuck."""

    def test_guilds_topic_does_not_claim_dueling_unimplemented(self):
        out = "\n".join(format_help(_TOPICS["guilds"], width=78) or [])
        self.assertNotIn("isn't implemented yet", out)
        self.assertIn("duel", out.lower())

    def test_guilds_topic_mentions_duel_command_in_usage(self):
        usage_cmds = [u[0] for u in _TOPICS["guilds"].usage]
        self.assertTrue(any("duel" in u for u in usage_cmds))

    def test_bhr_topic_mentions_duel(self):
        out = "\n".join(format_help(_TOPICS["bhr"], width=78) or [])
        self.assertIn("DUEL", out)


class TestFindTopicBySubstring(unittest.TestCase):
    """New in TADA: 'help ease' redirects to 'easeofuse' -- Ryan found
    typing a topic's full canonical name cumbersome. Only redirects when
    the substring is unambiguous (matches exactly one distinct topic)."""

    def test_unique_substring_resolves_to_canonical_name(self):
        self.assertEqual(_find_topic_by_substring("ease"), "easeofuse")
        self.assertEqual(_find_topic_by_substring("base"), "basedamage")
        self.assertEqual(_find_topic_by_substring("combat"), "combat")

    def test_exact_canonical_name_resolves_to_itself(self):
        self.assertEqual(_find_topic_by_substring("weaponclass"), "weaponclass")

    def test_ambiguous_substring_returns_none(self):
        # Matches weaponclass, weaponaffinity, "weapon affinity",
        # "class weapon", "best weapon", "bestweapon" -- more than one
        # distinct topic, so no redirect.
        self.assertIsNone(_find_topic_by_substring("weapon"))

    def test_no_match_returns_none(self):
        self.assertIsNone(_find_topic_by_substring("zzznotatopic"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_find_topic_by_substring(""))

    def test_case_insensitive(self):
        self.assertEqual(_find_topic_by_substring("EASE"), "easeofuse")


class TestMatchCategories(unittest.TestCase):
    """New in TADA: 'help concepts' resolves to the Concept category --
    Ryan kept mistyping 'help concept'. _match_categories() does
    bidirectional substring matching (token-in-category AND category-
    in-token) so both a trimmed prefix ('admin') and an extended/
    pluralized typo ('concepts') resolve, as long as it's unambiguous."""

    def test_exact_value_match(self):
        self.assertEqual(_exact_category("concept"), HelpCategory.CONCEPT)
        self.assertEqual(_exact_category("Combat"), HelpCategory.COMBAT)

    def test_exact_name_match(self):
        self.assertEqual(_exact_category("concept"), _exact_category("CONCEPT"))

    def test_exact_category_has_no_substring_fallback(self):
        # 'concepts' is NOT an exact match -- _exact_category must not
        # guess; that's _match_categories()' job.
        self.assertIsNone(_exact_category("concepts"))

    def test_match_categories_resolves_pluralized_typo(self):
        self.assertEqual(_match_categories("concepts"), [HelpCategory.CONCEPT])

    def test_match_categories_resolves_trimmed_prefix(self):
        self.assertEqual(_match_categories("admin"), [HelpCategory.ADMINISTRATIVE])

    def test_match_categories_exact_short_circuits_substring(self):
        # If the token exactly matches a category, that's the answer --
        # even though it might also substring-match others in principle.
        self.assertEqual(_match_categories("concept"), [HelpCategory.CONCEPT])

    def test_match_categories_short_token_is_ambiguous_not_a_guess(self):
        # A short token like 't' is a substring of most category names
        # ('administraTive', 'combaT', ...) -- must return every match,
        # not silently pick one, so a caller can tell it's ambiguous.
        matches = _match_categories("t")
        self.assertGreater(len(matches), 1)

    def test_match_categories_no_match_returns_empty(self):
        self.assertEqual(_match_categories("zzznotacategory"), [])

    def test_match_categories_empty_string_returns_empty(self):
        self.assertEqual(_match_categories(""), [])


class TestHelpConceptsIntegration(unittest.IsolatedAsyncioTestCase):
    """End-to-end: 'help concepts' (plural typo) via the real
    HelpCommand.execute() dispatch, not just the resolver functions."""

    async def test_help_concepts_shows_concept_category(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "concepts")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("Concept", output)

    async def test_help_concept_singular_still_works(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "concept")
        self.assertTrue(result.success)

    async def test_short_ambiguous_token_does_not_hijack_a_real_command(self):
        # Regression: an early version of this feature used the
        # bidirectional substring check at the very top of dispatch,
        # before command/alias lookup -- a short alias like 't' is a
        # substring of most category names, so it wrongly showed an
        # "ambiguous category" message instead of the real command's help.
        cmd  = _make_cmd("test", aliases=["t"])
        ctx  = _make_ctx()
        proc = MagicMock()
        proc.find_command.return_value     = (cmd, True)
        proc.get_all_commands.return_value = {"test": cmd}
        proc.search_commands.return_value  = []
        ctx.client.command_processor = proc
        ctx.command_processor        = proc
        result = await HelpCommand().execute(ctx, "t")
        self.assertTrue(result.success)
        self.assertNotIn("matches more than one category", result.message or "")


# ---------------------------------------------------------------------------
# _is_petscii_viewer
# ---------------------------------------------------------------------------

class TestIsPetsciiViewer(unittest.TestCase):

    def test_petscii_translation_is_petscii(self):
        from terminal import Translation
        ctx = _make_ctx()
        ctx.player.client_settings.translation = Translation.PETSCII
        self.assertTrue(help_mod._is_petscii_viewer(ctx))

    def test_ansi_translation_is_not_petscii(self):
        from terminal import Translation
        ctx = _make_ctx()
        ctx.player.client_settings.translation = Translation.ANSI
        self.assertFalse(help_mod._is_petscii_viewer(ctx))

    def test_no_player_returns_false(self):
        ctx = MagicMock()
        ctx.player = None
        self.assertFalse(help_mod._is_petscii_viewer(ctx))

    def test_no_client_settings_returns_false(self):
        ctx = MagicMock()
        ctx.player.client_settings = None
        self.assertFalse(help_mod._is_petscii_viewer(ctx))


# ---------------------------------------------------------------------------
# HelpCategory
# ---------------------------------------------------------------------------

class TestHelpCategory(unittest.TestCase):

    def test_expected_categories_present(self):
        names = {c.name for c in HelpCategory}
        for expected in ("GENERAL", "COMMUNICATION", "MOVEMENT",
                         "AUTHENTICATION", "COMBAT", "ADMINISTRATIVE"):
            self.assertIn(expected, names)

    def test_values_are_strings(self):
        for cat in HelpCategory:
            self.assertIsInstance(cat.value, str)


# ---------------------------------------------------------------------------
# HelpCommand.execute() dispatch
# ---------------------------------------------------------------------------

class TestHelpCommandExecute(unittest.IsolatedAsyncioTestCase):

    # --- no args → general help ---

    async def test_no_args_shows_general_help(self):
        ctx, _ = _ctx_with_processor(
            _make_cmd("say",  category=HelpCategory.COMMUNICATION),
            _make_cmd("look", category=HelpCategory.MOVEMENT),
        )
        result = await HelpCommand().execute(ctx)
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("Available Commands by Category", output)

    # --- specific command ---

    async def test_specific_command_shows_help(self):
        ctx, _ = _ctx_with_processor(_make_cmd("say", summary="Say something."))
        result = await HelpCommand().execute(ctx, "say")
        self.assertTrue(result.success)
        self.assertIn("say", result.message)

    async def test_nonexistent_command_fails(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "no_such_command")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "no_help")
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("No help found", output)

    async def test_specific_command_detail_shows_its_aliases(self):
        cmd = _make_cmd("unwear", aliases=["remove", "doff"], summary="Take off worn gear.")
        ctx, _ = _ctx_with_processor(cmd)
        result = await HelpCommand().execute(ctx, "unwear")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("Aliases:", output)
        self.assertIn("remove", output)
        self.assertIn("doff", output)

    async def test_specific_command_detail_omits_aliases_section_when_none(self):
        cmd = _make_cmd("say", summary="Say something.")
        ctx, _ = _ctx_with_processor(cmd)
        result = await HelpCommand().execute(ctx, "say")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertNotIn("Aliases:", output)

    async def test_alias_resolves_to_command(self):
        cmd  = _make_cmd("test", aliases=["t"])
        ctx  = _make_ctx()
        proc = MagicMock()
        proc.find_command.return_value     = (cmd, True)
        proc.get_all_commands.return_value = {"test": cmd}
        proc.search_commands.return_value  = []
        ctx.client.command_processor = proc
        ctx.command_processor        = proc
        result = await HelpCommand().execute(ctx, "t")
        self.assertTrue(result.success)

    # --- categories ---

    async def test_categories_token_lists_all(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "categories")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("General",  output)
        self.assertIn("Movement", output)

    async def test_category_name_shows_its_commands(self):
        ctx, _ = _ctx_with_processor(_make_cmd("go", category=HelpCategory.MOVEMENT))
        result = await HelpCommand().execute(ctx, "movement")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("go", output)

    # --- summary table ---

    async def test_summary_switch_lists_commands_with_summaries(self):
        from commands.base_command import Mode

        ctx, proc = _ctx_with_processor(
            _make_cmd("say", category=HelpCategory.COMMUNICATION,
                      summary="Say something to players in your room."),
            _make_cmd("attack", category=HelpCategory.COMBAT,
                      summary="Attack a monster or player."),
        )
        proc.current_mode = None
        for cmd in proc.get_all_commands.return_value.values():
            cmd.modes = {Mode.ANY}

        result = await HelpCommand().execute(ctx, "#summary")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("COMBAT",                                 output)
        self.assertIn("COMMUNICATION",                          output)
        self.assertIn("attack",                                 output)
        self.assertIn("Say something to players in your room.", output)

    async def test_summary_switch_zebra_stripes_alternate_rows(self):
        from commands.base_command import Mode

        ctx, proc = _ctx_with_processor(
            _make_cmd("say", category=HelpCategory.COMMUNICATION, summary="First."),
            _make_cmd("shout", category=HelpCategory.COMMUNICATION, summary="Second."),
        )
        proc.current_mode = None
        for cmd in proc.get_all_commands.return_value.values():
            cmd.modes = {Mode.ANY}

        await HelpCommand().execute(ctx, "#summary")
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("|mid_gray|",  output)
        self.assertIn("|dark_gray|", output)

    async def test_summary_switch_alias_sum_works(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "#sum")
        self.assertTrue(result.success)

    async def test_unknown_category_fails(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "#cat", "nonexistentcat")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "unknown_category")

    async def test_category_substring_matches_unambiguously(self):
        ctx, _ = _ctx_with_processor(_make_cmd("ban", category=HelpCategory.ADMINISTRATIVE))
        result = await HelpCommand().execute(ctx, "#cat", "admin")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("ban", output)

    async def test_category_substring_can_match_anywhere_in_name(self):
        ctx, _ = _ctx_with_processor(_make_cmd("go", category=HelpCategory.MOVEMENT))
        result = await HelpCommand().execute(ctx, "#cat", "move")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("go", output)

    async def test_category_substring_ambiguous_reports_all_matches(self):
        ctx, _ = _ctx_with_processor()
        # 'c' matches Combat, Communication, and Concept -- all start with 'c'.
        result = await HelpCommand().execute(ctx, "#cat", "c")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "ambiguous_category")
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("Combat", output)
        self.assertIn("Communication", output)
        self.assertIn("Concept", output)

    async def test_category_matches_across_reloaded_enum_identity(self):
        """Regression: 'reload commands.help' creates a brand-new
        HelpCategory class. Any command module that wasn't reloaded in
        the same breath still holds a reference to the *old*
        HelpCategory.ADMINISTRATIVE object -- enums compare by identity,
        so a naive `cat == matched` silently drops that command from its
        own category listing. Simulate that here with a separate Enum
        class sharing the same member name, standing in for the stale
        reference."""
        import enum

        class _StaleHelpCategory(enum.Enum):
            ADMINISTRATIVE = "Administrative"

        self.assertIsNot(_StaleHelpCategory.ADMINISTRATIVE, HelpCategory.ADMINISTRATIVE)

        stale_cmd = _make_cmd("ban", category=_StaleHelpCategory.ADMINISTRATIVE)
        ctx, _ = _ctx_with_processor(stale_cmd)
        result = await HelpCommand().execute(ctx, "administrative")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("ban", output)

    async def test_category_exact_match_still_wins_over_substring(self):
        """'general' is itself a full category name -- exact match must
        take priority even though it's also technically a substring of
        nothing else here; this guards the exact-match-first ordering."""
        ctx, _ = _ctx_with_processor(_make_cmd("look", category=HelpCategory.GENERAL))
        result = await HelpCommand().execute(ctx, "general")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("look", output)

    # --- search ---

    async def test_search_finds_matching_command(self):
        ctx, _ = _ctx_with_processor(_make_cmd("test", summary="A test command."))
        result = await HelpCommand().execute(ctx, "search", "tes")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("test", output)

    async def test_search_no_results(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "search", "xyzzy")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("No commands found", output)

    async def test_hash_search_is_an_alias_for_search(self):
        ctx, _ = _ctx_with_processor(_make_cmd("test", summary="A test command."))
        result = await HelpCommand().execute(ctx, "#search", "tes")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("test", output)

    async def test_search_shows_elided_snippet_of_match(self):
        ctx, _ = _ctx_with_processor(
            _make_cmd("caravan", summary="Join a caravan traveling through the mountain pass safely.")
        )
        result = await HelpCommand().execute(ctx, "#search", "mountain")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("mountain", output)
        self.assertIn("...", output)

    # --- edge cases ---

    async def test_graceful_without_processor(self):
        ctx = _make_ctx()
        ctx.client = MagicMock(spec=[])   # no command_processor attribute
        ctx.command_processor = None
        result = await HelpCommand().execute(ctx)
        self.assertTrue(result.success)

    async def test_falls_back_to_docstring_when_no_help_obj(self):
        cmd             = MagicMock()
        cmd.name        = "nodoc"
        cmd.aliases     = []
        cmd.help        = None
        cmd.execute.__doc__ = "Docstring help text."

        ctx  = _make_ctx()
        proc = MagicMock()
        proc.find_command.return_value     = (cmd, False)
        proc.get_all_commands.return_value = {"nodoc": cmd}
        proc.search_commands.return_value  = []
        ctx.client.command_processor = proc
        ctx.command_processor        = proc

        result = await HelpCommand().execute(ctx, "nodoc")
        self.assertTrue(result.success)
        self.assertIn("Docstring", result.message)

    # --- HelpCategory accessible via the module reference ---

    def test_help_mod_has_helpcategory(self):
        self.assertTrue(hasattr(help_mod, "HelpCategory"))
        self.assertIn(help_mod.HelpCategory.MOVEMENT,
                      list(help_mod.HelpCategory))


# ---------------------------------------------------------------------------
# Standalone concept topics (e.g. "help about") -- not tied to any Command,
# so they work at the LOGIN prompt too (help itself is Mode.ANY).
# ---------------------------------------------------------------------------

class TestHelpTopics(unittest.IsolatedAsyncioTestCase):

    async def test_about_topic_shows_up(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "about")
        self.assertTrue(result.success)
        self.assertIn("MUD", result.message)
        self.assertIn("Land of Spur", result.message)

    async def test_topic_aliases_all_resolve(self):
        for alias in ("about", "tada", "mud", "whatisthis"):
            ctx, _ = _ctx_with_processor()
            result = await HelpCommand().execute(ctx, alias)
            self.assertTrue(result.success, f"'{alias}' should resolve to the about topic")

    async def test_unambiguous_substring_redirects_to_the_topic(self):
        # 'help ease' -> the easeofuse topic, since it's the only
        # registered topic name/alias containing 'ease' -- Ryan's
        # request, typing the full canonical name was cumbersome.
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "ease")
        self.assertTrue(result.success)
        self.assertIn("Ease of use", result.message)

    async def test_ambiguous_substring_falls_through_to_no_help_found(self):
        # 'weapon' matches multiple distinct topics (weaponclass,
        # weaponaffinity, ...) -- must not guess, falls through to the
        # normal "no help found" message instead of picking one.
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "weapon")
        self.assertFalse(result.success)
        self.assertIn("No help found", " ".join(
            str(a) for call in ctx.send.await_args_list for a in call.args))

    async def test_topic_works_with_no_processor_state(self):
        # No real commands registered at all -- the LOGIN-mode scenario
        # this topic exists for still needs to work.
        ctx  = _make_ctx()
        proc = MagicMock()
        proc.find_command.return_value     = (None, False)
        proc.get_all_commands.return_value = {}
        proc.search_commands.return_value  = []
        ctx.client.command_processor = proc
        ctx.command_processor        = proc

        result = await HelpCommand().execute(ctx, "about")
        self.assertTrue(result.success)

    async def test_concept_category_lists_topics(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "concept")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn("about", output)


    def test_multi_paragraph_description_preserves_blank_line(self):
        help_obj = Help(
            summary="Multi-paragraph test.",
            description="First paragraph here.\n\nSecond paragraph here.",
        )
        formatted = format_help(help_obj)
        self.assertIn("", formatted)  # blank line between paragraphs
        joined = "\n".join(formatted)
        self.assertIn("First paragraph here.", joined)
        self.assertIn("Second paragraph here.", joined)

    async def test_rooms_topic_explains_outdoor_rooms(self):
        for alias in ("rooms", "room"):
            ctx, _ = _ctx_with_processor()
            result = await HelpCommand().execute(ctx, alias)
            self.assertTrue(result.success)
            self.assertIn("outdoors", result.message)

    async def test_categories_list_includes_descriptions(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "categories")
        self.assertTrue(result.success)
        output = " ".join(str(a) for call in ctx.send.await_args_list for a in call.args)
        normalized = " ".join(output.split())
        # Every category's one-line description should be present (normalize
        # whitespace since long descriptions wrap across lines).
        self.assertIn("Attacking, fleeing", normalized)      # Combat
        self.assertIn("not tied to one command", normalized)  # Concept


class TestColorsTopic(unittest.IsolatedAsyncioTestCase):
    """'help colors' (aliases 'color'/'markup') documents the |token|
    mini-language (formatting.py's ANSI_COLOR_CODES/PETSCII_CONTROL_CODES/
    |tab| syntax and the new ':count' + '||escape||' additions). Its own
    usage/example text has to survive the *real* rendering pipeline
    (format_lines -> ansi_encode/plain_encode) intact, not just show up
    unprocessed in a mocked ctx.send() -- see the full-pipeline tests
    below, which is what caught the escape mechanism's original bugs."""

    async def test_topic_aliases_all_resolve(self):
        for alias in ("colors", "color", "markup"):
            ctx, _ = _ctx_with_processor()
            result = await HelpCommand().execute(ctx, alias)
            self.assertTrue(result.success, f"'{alias}' should resolve to the colors topic")

    async def test_mentions_tab_and_count_syntax(self):
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "colors")
        self.assertIn("tab", result.message.lower())
        self.assertIn(":5", result.message)

    async def test_bang_note_hidden_from_non_petscii_viewer(self):
        """Help.petscii_notes (the '!' alternate-delimiter note) should not
        show up for an ANSI/plain-text viewer -- it's PETSCII-specific
        keyboard trivia that's just noise otherwise."""
        ctx, _ = _ctx_with_processor()
        result = await HelpCommand().execute(ctx, "colors")
        self.assertNotIn("Shift+-", result.message)

    async def test_bang_note_shown_to_petscii_viewer(self):
        from terminal import Translation
        ctx, _ = _ctx_with_processor()
        ctx.player.client_settings.translation = Translation.PETSCII
        result = await HelpCommand().execute(ctx, "colors")
        self.assertIn("Shift+-", result.message)

    async def test_bang_note_escaped_so_it_shows_literally(self):
        """The petscii_notes example (!!red!!some text!!reset!!) has to be
        double-bang escaped, same as the ||red||...||reset|| examples
        elsewhere in this topic are double-pipe escaped -- an unescaped
        single-bang version would actually apply the color/reset on a real
        PETSCII connection instead of showing the syntax."""
        from terminal import Translation
        ctx, _ = _ctx_with_processor()
        ctx.player.client_settings.translation = Translation.PETSCII
        result = await HelpCommand().execute(ctx, "colors")
        self.assertIn("!!red!!", result.message)

    def test_full_pipeline_petscii_bang_note_renders_literally(self):
        """Regression: the petscii_notes example must survive the *real*
        PETSCII rendering pipeline (format_lines -> petscii_encode) as
        literal '!red!...!reset!' text, not get actually color-applied."""
        from formatting import format_lines, petscii_encode_lines
        from terminal import ClientSettings, Translation
        from commands.help import _TOPICS

        help_obj = _TOPICS["colors"]
        formatted = format_help(help_obj, command_name="colors", width=78,
                                rule_char="-", is_petscii=True)
        cs = ClientSettings()
        cs.translation    = Translation.PETSCII
        cs.screen_columns = 40
        lines   = format_lines(formatted, cs)
        encoded = petscii_encode_lines(lines)
        decoded = encoded.decode('petscii_c64en_lc', errors='replace')
        self.assertIn('!red!', decoded)
        self.assertIn('!reset!', decoded)

    async def test_no_longer_clashes_with_a_colors_command(self):
        """Regression: commands/example_commands.py used to register a
        real 'colors'/'color' command (ColorsCommand) -- since _TOPICS is
        checked before commands in HelpCommand.execute(), 'help colors'
        silently shadowed that command's own help entirely. The command's
        output moved to 'test #colors' so the names aren't contested."""
        import commands.example_commands as example_commands
        self.assertFalse(hasattr(example_commands, 'ColorsCommand'))

    def test_full_pipeline_ansi_renders_no_stray_warnings(self):
        """Every |token|-shaped example in the topic must be either a
        deliberate live demo or properly ||escaped|| -- an unescaped,
        accidental |word| in the source text logs an 'unknown token'
        warning every time a player views this page."""
        import logging
        from formatting import format_lines, ansi_encode_lines
        from terminal import ClientSettings
        from commands.help import _TOPICS

        help_obj = _TOPICS["colors"]
        formatted = format_help(help_obj, command_name="colors", width=78, rule_char="-")
        lines = format_lines(formatted, ClientSettings())

        with self.assertNoLogs(logging.getLogger(), level="WARNING"):
            ansi_encode_lines(lines)

    def test_full_pipeline_plain_preserves_escaped_examples(self):
        """Escaped ||token|| examples must survive PLAIN clients the same
        way they survive ANSI ones -- regression for the bug where
        _expand_tab_tokens() collapsed the escape too early, leaving a
        bare |tab| for plain_encode() to strip as if it were live markup."""
        from formatting import format_lines, plain_encode_lines
        from terminal import ClientSettings
        from commands.help import _TOPICS

        help_obj = _TOPICS["colors"]
        formatted = format_help(help_obj, command_name="colors", width=78, rule_char="-")
        lines = format_lines(formatted, ClientSettings())
        plain = ' '.join(plain_encode_lines(lines))

        self.assertIn('|tab|', plain)
        self.assertIn('|tab:5|', plain)
        self.assertIn('|color|', plain)
        self.assertIn('|code|', plain)


class TestCommandLineTopicAdminGating(unittest.IsolatedAsyncioTestCase):
    """'help commandline' concept topic -- its admin_notes (mentioning
    #version/#ver) should only show for Admin/Dungeon Master viewers."""

    async def test_regular_player_does_not_see_version_note(self):
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: False
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertTrue(result.success)
        self.assertNotIn("#version", result.message)

    async def test_admin_sees_version_note(self):
        from flags import PlayerFlags
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: flag == PlayerFlags.ADMIN
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertIn("#version", result.message)

    async def test_dungeon_master_sees_version_note(self):
        from flags import PlayerFlags
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: flag == PlayerFlags.DUNGEON_MASTER
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertIn("#version", result.message)

    async def test_general_content_visible_to_everyone(self):
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: False
        result = await HelpCommand().execute(ctx, "commandline")
        self.assertIn("switch", result.message.lower())

    async def test_alias_switches_also_resolves(self):
        ctx, _ = _ctx_with_processor()
        ctx.player.query_flag = lambda flag: False
        result = await HelpCommand().execute(ctx, "switches")
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s %(name)s: %(message)s")
    unittest.main()
