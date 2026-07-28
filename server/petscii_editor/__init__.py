"""petscii_editor — in-game PETSCII banner/screen editor.

Continues TODO.md's 7/23/26 "Online PETSCII editor" entry: a visual
40x25 character+color grid editor for `graphics/banner-petscii.txt`-style
art, so Ryan doesn't have to hand-author `{glyph}`/`|token|` sequences
blind. canvas.py holds the Canvas data model and both the client-facing
wire format and the `{$xx}`/`|token|` text rendering; store.py persists
canvases to disk, disambiguating the new binary format from today's
plain `|token|` banner text by an explicit header tag rather than a
filename/extension convention.
"""
