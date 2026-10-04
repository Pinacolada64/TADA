# tiles/ -- tileset tools and the standalone tile demo (see
# ../TILESET_MEMORY_MAP.md). Kept apart from the client's own Makefile:
# nothing here is part of the client build.

WINE        = wine
C64LIST     = $(WINE) ~/bin/C64List4.06/c64List.exe
PYTHON      ?= ../../../server/.venv/bin/python3 -B
# The CC0 art pack (ArMM1998, "Zelda-like Tilesets and Sprites",
# opengameart.org) isn't checked in; point SHEET at its Overworld.png.
SHEET       ?= Overworld.png

all: tile_demo.prg tile_editor.prg

# Step 1 (needs SHEET): regenerate the demo's map + charset data
demo-data:
	$(PYTHON) make_demo_map.py $(SHEET) --layout demo_map.json \
	    --remap overworld_remap.json --colors 5,13,10 -o . \
	    --preview samples/demo_map_preview.png

# Step 2: assemble (the generated data is checked in, so this works
# without the art pack)
tile_demo.prg: tile_demo.asm tile_demo_data.asm demo_charset.bin demo_map.bin demo_colors.bin
	$(C64LIST) tile_demo.asm -prg:tile_demo -sym -ovr

run: tile_demo.prg
	x64sc -autostartprgmode 1 -autostart tile_demo.prg

# --- Tile editor ---
# default_tileset.bin (embedded as the editor's starting set) comes from
# tile_convert.py's tileset mode + tileset_file.py pack --raw; needs SHEET.
default-tileset:
	$(PYTHON) tile_convert.py tileset $(SHEET) --cells "0,4,9,20" --under 5,10 \
	    --remap overworld_remap.json --colors 5,13,10 -o ts_meadow
	$(PYTHON) tileset_file.py pack ts_meadow --raw -o default_tileset.bin

tile_editor.prg: tile_editor.asm default_tileset.bin
	$(C64LIST) tile_editor.asm -prg:tile_editor -sym -ovr

# A disk with the editor and a TILESET file (the default set), so L works
# straight away and S has somewhere to save.
tileset.prg: default_tileset.bin
	printf '\000\100' | cat - default_tileset.bin > $@   # load address $4000

tile_editor.d64: tile_editor.prg tileset.prg
	rm -f $@
	c1541 -format "tile editor,te" d64 $@ -write tile_editor.prg "tile editor" \
	    -write tileset.prg "tileset"

run-editor: tile_editor.d64
	x64sc -8 tile_editor.d64 -autostart tile_editor.d64

clean:
	rm -f tile_demo.prg tile_demo.sym tile_editor.prg tile_editor.sym \
	    tileset.prg tile_editor.d64

.PHONY: all demo-data default-tileset run run-editor clean
