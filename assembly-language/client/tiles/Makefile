# tiles/ -- tileset tools and the standalone tile demo (see
# ../TILESET_MEMORY_MAP.md). Kept apart from the client's own Makefile:
# nothing here is part of the client build.

WINE        = wine
C64LIST     = $(WINE) ~/bin/C64List4.06/c64List.exe
PYTHON      = ../../../server/.venv/bin/python3 -B
# The CC0 art pack (ArMM1998, "Zelda-like Tilesets and Sprites",
# opengameart.org) isn't checked in; point SHEET at its Overworld.png.
SHEET       ?= Overworld.png

all: tile_demo.prg

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

clean:
	rm -f tile_demo.prg tile_demo.sym

.PHONY: all demo-data run clean
