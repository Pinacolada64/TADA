#!/usr/bin/env bash
# Rebuild PDFs for every reference doc in one shot, via md_to_pdf.sh.
#
# "Reference docs" here means the maintained roadmap/catalog files meant
# to be read as a document (MECHANICS.md, FUNCTIONS.md, DATA_FILES.md,
# RESEARCH.md, CHARISMA_AUDIT.md, GENDER_AUDIT.md, LEVEL_AUDIT.md,
# tools/BOT_README.md, ../programming-notes/spur-variables.md) -- not
# dated task logs (TODO.md, BOTS_TODO.md, TODO_HELP.md) or the top-level
# project READMEs, which aren't meant to be rendered to PDF.
#
# Usage: scripts/generate_docs.sh
# Output: one PDF per doc, next to its Markdown source (server/*.pdf,
# server/tools/*.pdf, programming-notes/*.pdf)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DOCS=(
  "$SERVER_DIR/MECHANICS.md"
  "$SERVER_DIR/FUNCTIONS.md"
  "$SERVER_DIR/DATA_FILES.md"
  "$SERVER_DIR/RESEARCH.md"
  "$SERVER_DIR/CHARISMA_AUDIT.md"
  "$SERVER_DIR/GENDER_AUDIT.md"
  "$SERVER_DIR/LEVEL_AUDIT.md"
  "$SERVER_DIR/tools/BOT_README.md"
  "$SERVER_DIR/../programming-notes/spur-variables.md"
)

"$SCRIPT_DIR/md_to_pdf.sh" "${DOCS[@]}"
