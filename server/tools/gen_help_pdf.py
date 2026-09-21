#!/usr/bin/env python3
"""tools/gen_help_pdf.py — Render every in-game help entry to a PDF manual.

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
    .venv/bin/python3 tools/gen_help_pdf.py [output.pdf]

Re-run this whenever help text changes; there's no cached/derived state to
go stale otherwise.
"""
import re
import sys
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
from formatting import highlight_brackets, PlainCodec

TOKEN_RE = re.compile(r"\|[a-z_]+\|")
_PLAIN_CODEC = PlainCodec()


def strip_tokens(line: str) -> str:
    """Resolve a format_help() line down to what a player actually sees:
    strip |color| tokens, collapse [[literal]] to [literal] (and apply
    [highlight] as plain text, delimiters removed) via highlight_brackets(),
    and collapse %% to a literal % -- see this module's docstring."""
    line = TOKEN_RE.sub("", line)
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


CATEGORY_ORDER = [
    "General", "Movement", "Combat", "Communication", "Interaction",
    "Administrative", "Authentication", "Miscellaneous", "Concept",
]


def build_pdf(entries, out_path: Path):
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
    for cat in by_cat:
        by_cat[cat].sort(key=lambda e: e["name"])
    ordered_cats = [c for c in CATEGORY_ORDER if c in by_cat]
    ordered_cats += [c for c in by_cat if c not in ordered_cats]

    story = []
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph("TADA", title_style))
    story.append(Paragraph("Command &amp; Concept Help Reference", subtitle_style))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"{sum(1 for e in entries if e['kind']=='command')} commands &nbsp;&bull;&nbsp; "
        f"{sum(1 for e in entries if e['kind']=='topic')} concept topics",
        subtitle_style))
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
            if e["aliases"]:
                header += "  <font color='#888888' size=10>(" + escape(", ".join(e["aliases"])) + ")</font>"
            story.append(Paragraph(header, entry_name_style))
            kind_label = "Command" if e["kind"] == "command" else "Concept topic"
            story.append(Paragraph(f"{kind_label} &mdash; {escape(cat)}", entry_meta_style))

            # format_help()'s first couple of lines are the name/category
            # header and a rule -- already rendered above, so skip through
            # the rule line to avoid duplicating them.
            text_lines, started = [], False
            for ln in e["lines"]:
                if not started:
                    if ln.strip() == "" or set(ln.strip()) <= {"-"}:
                        started = True
                    continue
                text_lines.append(ln)
            if not text_lines:
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
        title="TADA Command & Concept Help Reference",
    )
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "TADA_Help_Reference.pdf"
    entries = collect_entries()
    build_pdf(entries, out_path)
    n_cmd = sum(1 for e in entries if e["kind"] == "command")
    n_topic = sum(1 for e in entries if e["kind"] == "topic")
    print(f"Wrote {out_path} ({n_cmd} commands, {n_topic} concept topics)")


if __name__ == "__main__":
    main()
