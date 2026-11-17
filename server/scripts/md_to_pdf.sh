#!/usr/bin/env bash
# Render one or more Markdown files to PDF via pandoc + lualatex.
#
# Disables pandoc's default tex_math_dollars extension so bare/paired '$'
# in prose or inline code (e.g. SPUR BASIC string-variable names like
# `zu$[7]`, `xm$`, or a literal "$" sigil) are typeset as literal dollar
# signs instead of being parsed as inline LaTeX math. A Symbola fallback
# font is wired in so emoji used as status markers (✅, ⏸, ...) render
# instead of coming out blank in Latin Modern. Tables get light zebra
# striping (xcolor's `table` option + `\rowcolors`, applies to pandoc's
# longtable output via colortbl) for readability in the long
# module/function reference tables. autowidth.lua sizes each table's
# columns by their contents, so short columns stay narrow and long ones
# get the room (pandoc otherwise splits a wide pipe table's width by the
# dashes in its |---|---| line, or lets a narrow-source one run off the
# page).
#
# Usage: scripts/md_to_pdf.sh FILE.md [FILE2.md ...]
# Output: FILE.pdf next to each input FILE.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREAMBLE_TEX="$(mktemp -t pdf-preamble-XXXXXX.tex)"
trap 'rm -f "$PREAMBLE_TEX"' EXIT

cat > "$PREAMBLE_TEX" <<'EOF'
\usepackage{fontspec}
\directlua{
  luaotfload.add_fallback("emojifallback", {"Symbola:mode=harf;"})
}
\setmainfont{latinmodern-math.otf}[RawFeature={fallback=emojifallback}]
\usepackage[table]{xcolor}
\rowcolors{2}{black!5}{white}
EOF

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 FILE.md [FILE2.md ...]" >&2
  exit 1
fi

for md in "$@"; do
  pdf="${md%.md}.pdf"
  echo "Rendering $md -> $pdf"
  pandoc "$md" \
    -f markdown-tex_math_dollars \
    -t pdf --pdf-engine=lualatex \
    -V geometry:margin=1in -V colorlinks=true --toc \
    -H "$PREAMBLE_TEX" \
    --lua-filter="$SCRIPT_DIR/autowidth.lua" \
    -o "$pdf"
done
