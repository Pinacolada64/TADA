"""tools/ansi_to_html.py — convert a raw ANSI-colored terminal transcript
(e.g. a captured bot session log) into HTML with <span> color markup.

Usage as a library:
    from tools.ansi_to_html import ansi_to_html
    html_fragment = ansi_to_html(raw_text)

Usage as a CLI:
    python tools/ansi_to_html.py session.log > session.html
    python tools/ansi_to_html.py session.log --standalone > session.html

The CSS class names (ansi-red, ansi-brgreen, etc.) are left for the caller
to style -- this module only marks up spans, it doesn't ship a palette.
--standalone wraps the fragment in a minimal dark-terminal <html> page with
a starter palette, for quick local viewing.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

# SGR (Select Graphic Rendition) codes this tool understands, mapped to a
# CSS class name. Reset codes (0, 39, 49) close the current span instead of
# opening a new one.
_SGR_FG = {
    '30': 'ansi-black',   '31': 'ansi-red',     '32': 'ansi-green',
    '33': 'ansi-yellow',  '34': 'ansi-blue',    '35': 'ansi-magenta',
    '36': 'ansi-cyan',    '37': 'ansi-white',
    '90': 'ansi-brblack', '91': 'ansi-brred',   '92': 'ansi-brgreen',
    '93': 'ansi-bryellow','94': 'ansi-brblue',  '95': 'ansi-brmagenta',
    '96': 'ansi-brcyan',  '97': 'ansi-brwhite',
}
_SGR_RESET = {'0', '39'}

_SGR_RE = re.compile(r'\x1b\[(\d+)m')


def ansi_to_html(text: str) -> str:
    """Convert \\x1b[NNm ANSI color codes in *text* to <span class="ansi-*">
    markup. Unrecognised codes (bg colors, bold, underline, etc.) are
    stripped silently. Plain text is HTML-escaped throughout.
    """
    out: list[str] = []
    pos = 0
    open_span = False
    for m in _SGR_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        code = m.group(1)
        if open_span:
            out.append('</span>')
            open_span = False
        cls = _SGR_FG.get(code)
        if cls:
            out.append(f'<span class="{cls}">')
            open_span = True
        pos = m.end()
    out.append(html.escape(text[pos:]))
    if open_span:
        out.append('</span>')
    return ''.join(out)


_STANDALONE_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>ANSI transcript</title>
<style>
  body {{ background:#0b0e12; color:#d7dde3; font-family:ui-monospace,Menlo,Consolas,monospace;
          padding:2rem; white-space:pre-wrap; line-height:1.4; }}
  .ansi-black{{color:#5b6472}} .ansi-red{{color:#e5626b}} .ansi-green{{color:#7fd08a}}
  .ansi-yellow{{color:#e8c15c}} .ansi-blue{{color:#6ea8e0}} .ansi-magenta{{color:#c98bdb}}
  .ansi-cyan{{color:#5fd0c9}} .ansi-white{{color:#eef1f4}}
  .ansi-brblack{{color:#818e9c}} .ansi-brred{{color:#ff8790}} .ansi-brgreen{{color:#9be8a4}}
  .ansi-bryellow{{color:#ffd876}} .ansi-brblue{{color:#8fc2f2}} .ansi-brmagenta{{color:#e2a8f0}}
  .ansi-brcyan{{color:#7de8e0}} .ansi-brwhite{{color:#ffffff}}
</style></head><body>{body}</body></html>
"""


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log_file', type=Path, help='captured transcript with raw ANSI codes')
    parser.add_argument('--standalone', action='store_true',
                         help='wrap output in a minimal dark-terminal HTML page instead of a bare fragment')
    args = parser.parse_args(argv)

    text = args.log_file.read_text(encoding='utf-8')
    body = ansi_to_html(text)
    output = _STANDALONE_TEMPLATE.format(body=body) if args.standalone else body
    sys.stdout.write(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
