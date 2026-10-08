#!/usr/bin/env python3
"""tools/gen_help_pdf.py — Render every in-game help entry to a PDF manual.

Writes two documents:
  TADA_Help_Reference.pdf    every command and concept topic, as 'help'
                             shows it to a player
  TADA_Editor_Reference.pdf  the line editor's own '.h' help: every dot
                             command, the '.h colors' topic, and the
                             admin-only file commands (text_editor.py)

Walks the live command registry (CommandProcessor.discover()) and the
standalone concept topics (commands/help._TOPICS), formats each one with
commands.help.format_help() -- the same formatter the live 'help' command
uses -- and lays the result out as a PDF via reportlab.

format_help()'s output is meant for a real client's send pipeline, which
still has two escaping passes left to run on it (network_context.py's
ctx.send() -> tada_utilities.substitute_tokens(), then
formatting.ansi_encode()/petscii_encode() -> formatting.highlight_brackets()):
  - |color|...|reset| tokens get resolved to real color codes/removed
  - [[literal]] double-bracket escapes (written by format_help()'s
    _auto_escape(), see Help's class docstring) collapse to a literal
    [literal] via highlight_brackets()
  - %% double-percent escapes (see the "tokens" concept topic) collapse
    to a literal % via substitute_tokens()
This script has no live client/player to run the real pipeline against,
so it reproduces the same three collapses directly (strip |tokens|, run
highlight_brackets() with a PlainCodec, collapse %% -> %) -- skipping
any of them would leave the PDF showing raw [[...]] / %% escapes instead
of the literal text a player actually sees.

Usage:
    .venv/bin/python3 tools/gen_help_pdf.py [help.pdf] [--editor-output editor.pdf]

Both default to the server/ directory. The editor's help lives in
text_editor.py (each DotCommand's help_text, rendered through
_format_help_text() exactly as '.h <letter>' does), not in commands/help.py,
so it gets its own document rather than a category in the main one.

Re-run this whenever help text changes; there's no cached/derived state to
go stale otherwise.
"""
import argparse
import sys
from types import SimpleNamespace
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).parent.parent))

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

from commands.command_processor import CommandProcessor
from commands.help import _TOPICS, _TOPIC_PRIMARY_NAME, format_help
from formatting import highlight_brackets, plain_encode, PlainCodec

_PLAIN_CODEC = PlainCodec()


def strip_tokens(line: str) -> str:
    """Resolve a format_help() line down to what a player actually sees:
    strip |color| tokens via plain_encode() -- the plain-text client's own
    pass, which also shows an escaped ||token|| as the literal |token| (a
    bare |token| regex here used to eat it down to '||') -- collapse
    [[literal]] to [literal] (and apply [highlight] as plain text,
    delimiters removed) via highlight_brackets(), and collapse %% to a
    literal % -- see this module's docstring."""
    line = plain_encode(line)
    line = highlight_brackets(line, _PLAIN_CODEC)
    line = line.replace("%%", "%")
    return line


def collect_entries():
    """Return a list of {kind, name, aliases, category, lines} dicts, one
    per distinct command / concept topic."""
    cp = CommandProcessor()
    cp.discover()
    entries = []

    seen_ids = set()
    for name, cmd in sorted(cp.get_all_commands().items()):
        help_obj = getattr(cmd, "help", None)
        if help_obj is None or id(help_obj) in seen_ids:
            continue
        seen_ids.add(id(help_obj))
        aliases = [a for a in getattr(cmd, "aliases", []) if a != name]
        lines = [strip_tokens(l) for l in (format_help(help_obj, command_name=name, aliases=aliases) or [])]
        cat = getattr(help_obj, "category", None)
        entries.append({"kind": "command", "name": name, "aliases": aliases,
                         "category": cat.value if cat else "General", "lines": lines})

    seen_ids = set()
    for name, help_obj in sorted(_TOPICS.items()):
        if id(help_obj) in seen_ids:
            continue
        seen_ids.add(id(help_obj))
        primary = _TOPIC_PRIMARY_NAME.get(id(help_obj), name)
        other_aliases = [n for n, h in _TOPICS.items() if id(h) == id(help_obj) and n != primary]
        lines = [strip_tokens(l) for l in (format_help(help_obj, command_name=primary, aliases=other_aliases) or [])]
        cat = getattr(help_obj, "category", None)
        entries.append({"kind": "topic", "name": primary, "aliases": other_aliases,
                         "category": cat.value if cat else "Concept", "lines": lines})

    return entries


EDITOR_CATEGORY_ORDER = ["Commands", "Topics", "Admin-only commands"]

# Width the editor's examples tables (_format_examples_table()) are laid out
# at -- the same 78 columns a full-width terminal player gets.
EDITOR_WIDTH = 78


def collect_editor_entries():
    """Return entries for the line editor's '.h' help, read from a real
    text_editor.Editor -- its dot_command_table and privileged_commands are
    built per session, so a minimal stand-in context is enough (Editor()
    only reads ctx.player.client_settings.screen_columns)."""
    import text_editor

    ctx = SimpleNamespace(player=SimpleNamespace(
        client_settings=SimpleNamespace(screen_columns=EDITOR_WIDTH)))
    editor = text_editor.Editor(ctx)

    def entry(name, title, category, help_text):
        lines = [strip_tokens(l) for l in
                 text_editor._format_help_text(help_text, EDITOR_WIDTH)]
        return {"kind": "dot", "name": name, "title": title, "aliases": [],
                "category": category, "lines": lines, "has_header": False}

    entries = [entry(f".{c.command_key}", c.command_text, "Commands", c.help_text)
               for c in editor.dot_command_table]
    colors = entry(".h colors", "Colors", "Topics", text_editor._COLOR_TOPIC_TEXT)
    # The '!' paragraph '.h colors' adds for Commodore (PETSCII) players
    # only. Its '!!token!!' escapes are PETSCII markup, which plain_encode()
    # doesn't read, so resolve them the way a Commodore screen would.
    import formatting
    petscii = [highlight_brackets(formatting._PETSCII_TOKEN_RE.sub(
                   formatting._petscii_token_strip_replace, l), _PLAIN_CODEC)
               for l in text_editor._format_help_text(text_editor._COLOR_TOPIC_PETSCII_TEXT,
                                                      EDITOR_WIDTH)]
    colors["lines"] += ["", "Commodore (PETSCII) connections only:"] + petscii
    entries.append(colors)
    entries += [entry(f".{c.command_key}", c.command_text, "Admin-only commands", c.help_text)
                for c in editor.privileged_commands]
    intro = [strip_tokens(l) for l in text_editor.EDITOR_INTRO_LINES]
    intro.append(strip_tokens(text_editor.EDITOR_HELP_HINT))
    return entries, intro


CATEGORY_ORDER = [
    "General", "Movement", "Combat", "Communication", "Interaction",
    "Administrative", "Authentication", "Miscellaneous", "Concept",
]


def build_pdf(entries, out_path: Path, *, doc_title="TADA Command & Concept Help Reference",
              subtitle="Command &amp; Concept Help Reference", count_line=None,
              category_order=CATEGORY_ORDER, intro=None, sort_entries=True):
    """Lay *entries* out as a PDF: title page, contents, then one section
    per category. Shared by both documents -- an entry's "kind" picks its
    label line, and "has_header" (format_help() output, default True) says
    whether its first lines are a name/category header to skip."""
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitlePage", parent=styles["Title"], fontSize=28, spaceAfter=12)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=13,
                                     alignment=TA_CENTER, textColor=colors.HexColor("#555555"))
    cat_heading_style = ParagraphStyle("CatHeading", parent=styles["Heading1"], fontSize=20,
                                        spaceBefore=0, spaceAfter=14, textColor=colors.HexColor("#1a1a1a"))
    entry_name_style = ParagraphStyle("EntryName", parent=styles["Heading2"], fontSize=14,
                                       spaceBefore=0, spaceAfter=2, textColor=colors.HexColor("#0b4f6c"))
    entry_meta_style = ParagraphStyle("EntryMeta", parent=styles["Normal"], fontSize=8.5,
                                       textColor=colors.HexColor("#888888"), spaceAfter=6)
    body_mono_style = ParagraphStyle("BodyMono", parent=styles["Normal"], fontName="Courier",
                                      fontSize=8.7, leading=11.2, spaceAfter=0)
    toc_entry_style = ParagraphStyle("TocEntry", parent=styles["Normal"], fontSize=10, leading=14)
    toc_cat_style = ParagraphStyle("TocCat", parent=styles["Heading2"], fontSize=13,
                                    spaceBefore=10, spaceAfter=4)

    by_cat = defaultdict(list)
    for e in entries:
        by_cat[e["category"]].append(e)
    if sort_entries:
        for cat in by_cat:
            by_cat[cat].sort(key=lambda e: e["name"])
    ordered_cats = [c for c in category_order if c in by_cat]
    ordered_cats += [c for c in by_cat if c not in ordered_cats]

    story = []
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph("TADA", title_style))
    story.append(Paragraph(subtitle, subtitle_style))
    story.append(Spacer(1, 0.3 * inch))
    if count_line is None:
        count_line = (f"{sum(1 for e in entries if e['kind']=='command')} commands &nbsp;&bull;&nbsp; "
                      f"{sum(1 for e in entries if e['kind']=='topic')} concept topics")
    story.append(Paragraph(count_line, subtitle_style))
    if intro:
        story.append(Spacer(1, 0.5 * inch))
        for line in intro:
            story.append(Paragraph(escape(line), styles["Normal"]))
            story.append(Spacer(1, 4))
    story.append(PageBreak())

    story.append(Paragraph("Table of Contents", cat_heading_style))
    for cat in ordered_cats:
        story.append(Paragraph(escape(cat), toc_cat_style))
        story.append(Paragraph(", ".join(escape(e["name"]) for e in by_cat[cat]), toc_entry_style))
    story.append(PageBreak())

    for cat_i, cat in enumerate(ordered_cats):
        story.append(Paragraph(escape(cat), cat_heading_style))
        for e in by_cat[cat]:
            header = escape(e["name"])
            if e.get("title"):
                header += " &mdash; " + escape(e["title"])
            if e["aliases"]:
                header += "  <font color='#888888' size=10>(" + escape(", ".join(e["aliases"])) + ")</font>"
            story.append(Paragraph(header, entry_name_style))
            kind_label = {"command": "Command", "topic": "Concept topic",
                          "dot": "Editor command"}.get(e["kind"], "Entry")
            if e["kind"] == "dot" and cat == "Topics":
                kind_label = "Editor topic"
            story.append(Paragraph(f"{kind_label} &mdash; {escape(cat)}", entry_meta_style))

            # format_help()'s first couple of lines are the name/category
            # header and a rule -- already rendered above, so skip through
            # the rule line to avoid duplicating them. (Editor entries
            # have no such header.)
            if e.get("has_header", True):
                text_lines, started = [], False
                for ln in e["lines"]:
                    if not started:
                        if ln.strip() == "" or set(ln.strip()) <= {"-"}:
                            started = True
                        continue
                    text_lines.append(ln)
                if not text_lines:
                    text_lines = e["lines"]
            else:
                text_lines = e["lines"]

            html = "<br/>".join(
                escape(l).replace("  ", "&nbsp;&nbsp;") if l.strip() else "&nbsp;"
                for l in text_lines
            )
            story.append(Paragraph(html, body_mono_style))
            story.append(Spacer(1, 14))
        if cat_i != len(ordered_cats) - 1:
            story.append(PageBreak())

    def add_page_number(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor("#999999"))
        canvas_obj.drawCentredString(LETTER[0] / 2, 0.5 * inch, str(doc.page))
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(
        str(out_path), pagesize=LETTER,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title=doc_title,
    )
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


def main():
    server_dir = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Export in-game help to PDF.")
    parser.add_argument("output", nargs="?", default=server_dir / "TADA_Help_Reference.pdf",
                        type=Path, help="command & concept reference (default: %(default)s)")
    parser.add_argument("--editor-output", default=server_dir / "TADA_Editor_Reference.pdf",
                        type=Path, help="line editor reference (default: %(default)s)")
    args = parser.parse_args()

    entries = collect_entries()
    build_pdf(entries, args.output)
    n_cmd = sum(1 for e in entries if e["kind"] == "command")
    n_topic = sum(1 for e in entries if e["kind"] == "topic")
    print(f"Wrote {args.output} ({n_cmd} commands, {n_topic} concept topics)")

    editor_entries, intro = collect_editor_entries()
    n_dot = sum(1 for e in editor_entries if e["category"] == "Commands")
    n_priv = sum(1 for e in editor_entries if e["category"] == "Admin-only commands")
    build_pdf(editor_entries, args.editor_output,
              doc_title="TADA Line Editor Reference",
              subtitle="Line Editor Reference",
              count_line=f"{n_dot} dot commands &nbsp;&bull;&nbsp; {n_priv} admin-only commands",
              category_order=EDITOR_CATEGORY_ORDER, intro=intro,
              sort_entries=False)   # keep '.h''s own order
    print(f"Wrote {args.editor_output} ({n_dot} dot commands, {n_priv} admin-only, 1 topic)")


if __name__ == "__main__":
    main()
