#!/usr/bin/env bash
# Render one or more Markdown files to PDF via pandoc + lualatex.
#
# Disables pandoc's default tex_math_dollars extension so bare/paired '$'
# in prose or inline code (e.g. SPUR BASIC string-variable names like
# `zu$[7]`, `xm$`, or a literal "$" sigil) are typeset as literal dollar
# signs instead of being parsed as inline LaTeX math. A Symbola fallback
# font is wired in so emoji used as status markers (✅, ⏸, ...) render
# instead of coming out blank in Latin Modern.
#
# Usage: scripts/md_to_pdf.sh FILE.md [FILE2.md ...]
# Output: FILE.pdf next to each input FILE.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FALLBACK_TEX="$(mktemp -t emoji-fallback-XXXXXX.tex)"
trap 'rm -f "$FALLBACK_TEX"' EXIT

cat > "$FALLBACK_TEX" <<'EOF'
\usepackage{fontspec}
\directlua{
  luaotfload.add_fallback("emojifallback", {"Symbola:mode=harf;"})
}
\setmainfont{latinmodern-math.otf}[RawFeature={fallback=emojifallback}]
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
    -H "$FALLBACK_TEX" \
    -o "$pdf"
done
