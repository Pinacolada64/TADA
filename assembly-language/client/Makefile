# Makefile for TADA C64 Client
# Build pipeline:
#   tada-client.asm
#     -> macro_preprocessor.py -> tada-client_pp.asm
#     -> C64List               -> tada-client.prg + tada-client_pp.sym
#     -> convert_labels        -> tada-client-vice-labels
#     -> VICE                  -> running program with debuggable labels

# --- Tools ---
WINE            = wine
C64LIST         = $(WINE) ~/bin/C64List4.06/c64List.exe
PREPROCESSOR    = python3 ./macro_preprocessor.py
CONVERT_LABELS  = python3 ./c64list-to-vice-labels.py
LAUNCH_VICE     = x64sc

# --- Target ---
TARGET          = tada-client

# --- Loadable overlay modules ---
# Separate .prg files, loaded on demand at OVERLAY_BUF (see tada-client.asm's
# own comment on load_petscii_editor) rather than compiled into TARGET --
# Ryan's call: split the client into loadable sub-modules instead of growing
# tada-client.asm itself indefinitely. Each needs its own preprocess+assemble
# pass, same pipeline as TARGET, and must end up in whatever directory VICE's
# `-fs8 "."` (or a real 1541/1581) serves as device 8, since the resident
# program LOADs it by filename at runtime -- this Makefile's own directory
# already doubles as that build/serve directory.
MODULES         = petscii_editor config_menu help_menu keymap_menu

petscii_editor_pp.asm: petscii_editor.asm
	$(PREPROCESSOR) petscii_editor.asm

petscii_editor.prg: petscii_editor_pp.asm
	$(C64LIST) petscii_editor_pp.asm -prg:petscii_editor -sym -ovr

config_menu_pp.asm: config_menu.asm
	$(PREPROCESSOR) config_menu.asm

config_menu.prg: config_menu_pp.asm
	$(C64LIST) config_menu_pp.asm -prg:config_menu -sym -ovr

help_menu_pp.asm: help_menu.asm
	$(PREPROCESSOR) help_menu.asm

help_menu.prg: help_menu_pp.asm
	$(C64LIST) help_menu_pp.asm -prg:help_menu -sym -ovr

keymap_menu_pp.asm: keymap_menu.asm
	$(PREPROCESSOR) keymap_menu.asm

keymap_menu.prg: keymap_menu_pp.asm
	$(C64LIST) keymap_menu_pp.asm -prg:keymap_menu -sym -ovr

# --- ROM paths ---
# Stock KERNAL/BASIC/CHARGEN -- kept around for reference/fallback even
# though `vice:` now boots JiffyDOS's KERNAL instead (see below); BASIC
# and CHARGEN are untouched by JiffyDOS, still stock either way.
VICE_ROMS       = $(HOME)/.local/share/vice/C64
KERNAL          = $(VICE_ROMS)/kernal-901227-03.bin
BASIC           = $(VICE_ROMS)/basic-901226-01.bin
CHARGEN         = $(VICE_ROMS)/chargen-901225-01.bin

# --- JiffyDOS ROMs ---
# JIFFYDOS_KERNAL replaces the computer's own KERNAL (-kernal, 8KB
# $e000-$ffff, same size/slot as stock KERNAL above -- verified via `ls
# -la` before wiring this in) with JiffyDOS's fast-loader-aware version.
# JIFFYDOS_1541/_1541II are drive-side JiffyDOS ROMs (16KB $c000-$ffff)
# for -dos1541/-dos1541II respectively -- both ends (computer + drive)
# need JiffyDOS installed for the fast-load protocol to actually kick in;
# one side alone still loads at stock 1541 speed. Ryan's ask 2026-08-17:
# swap these in for `make vice` since this project's edit-rebuild-reload
# loop hits LOAD constantly, and stock KERNAL+1541 speed makes that loop
# painfully slow.
JIFFYDOS_KERNAL = $(HOME)/Documents/c64/JiffyDOS/Jiffydos-Kernal.rom
JIFFYDOS_1541   = $(HOME)/Documents/c64/JiffyDOS/JiffyC1541.ROM
JIFFYDOS_1541II = $(HOME)/Documents/c64/JiffyDOS/Jiffy1541-II.rom
JIFFYDOS_1581   = $(HOME)/Documents/c64/JiffyDOS/Jiffy1581.rom

# --- SwiftLink / TADA server ---
SL_PORT         = 34064
SL_HOST         = 127.0.0.1
SL_BAUD         = 38400

# --- Build pipeline ---

# Split-out modules pulled into $(TARGET)_pp.asm via {include:...} (a
# native c64list directive -- see macro_preprocessor.py's
# C64LIST_DIRECTIVES, passed through unexpanded). c64list resolves
# labels across the include globally, but it does NOT run this
# project's own macro_preprocessor.py over included files, so each one
# needs its own preprocessing pass first, same as $(TARGET) itself --
# {include:screen-handler_pp.asm} in tada-client.asm names the
# preprocessed file, not the raw source.
SPLIT_MODULES   = screen-handler screen-output keymap keyboard_rollover

# Step 1: preprocess macros and constants
$(TARGET)_pp.asm: $(TARGET).asm $(addsuffix _pp.asm,$(SPLIT_MODULES))
	$(PREPROCESSOR) $(TARGET).asm

screen-handler_pp.asm: screen-handler.asm
	$(PREPROCESSOR) screen-handler.asm

screen-output_pp.asm: screen-output.asm
	$(PREPROCESSOR) screen-output.asm

keymap_pp.asm: keymap.asm
	$(PREPROCESSOR) keymap.asm

keyboard_rollover_pp.asm: keyboard_rollover.asm
	$(PREPROCESSOR) keyboard_rollover.asm

# Step 2: assemble to .prg and .sym in one pass
$(TARGET).prg: $(TARGET)_pp.asm
	$(C64LIST) $(TARGET)_pp.asm -prg:$(TARGET) -sym -ovr
	@# Fail if the resident program has grown into OVERLAY_BUF -- see
	@# tada-client.asm's OVERLAY_BUF comment (this collision has recurred
	@# three times as floating labels drift upward).
	python3 ./check_overlay_margin.py $(TARGET)_pp.sym

# Step 3: convert symbols to VICE label format
# Note: C64List names the sym file after the input file (tada-client_pp.sym)
$(TARGET)-vice-labels: $(TARGET).prg
	$(CONVERT_LABELS) $(TARGET)_pp.sym $(TARGET)-vice-labels

# Step 4: generate VICE monitor commands to auto-load labels
monitor-commands: $(TARGET)-vice-labels
	echo "ll \"$(TARGET)-vice-labels\"" > monitor-commands

# Default target: build everything
all: $(TARGET).prg $(TARGET)-vice-labels monitor-commands $(addsuffix .prg,$(MODULES))

# --- VICE launch ---
# Builds and attaches the real .d64 (see the $(TARGET).d64 rule below) rather
# than -fs8 "." host-filesystem passthrough -- confirmed live that -fs8 only
# ever exposes the single autostarted file, not the rest of the directory
# (autostart appears to synthesize its own virtual single-file disk image
# that shadows the real fs8 dir), so LOAD"$",8 never saw petscii_editor.prg
# that way. Autostarting the .d64 image itself boots normally off it and
# leaves the whole directory genuinely browsable/loadable at runtime.
vice: all $(TARGET).d64
	$(LAUNCH_VICE) \
	-kernal $(JIFFYDOS_KERNAL) \
	-basic $(BASIC) \
	-chargen $(CHARGEN) \
	-acia1 \
	-rsdev3 "$(SL_HOST):$(SL_PORT)" \
	-rsdev3baud "$(SL_BAUD)" \
	-rsuserdev "2" \
	-myaciadev "2" \
	-drive8type 1541 \
	-drive10type 1581 \
	-drive11type 1581 \
	-dos1541 $(JIFFYDOS_1541) \
	-dos1541II $(JIFFYDOS_1541II) \
	-dos1581 $(JIFFYDOS_1581) \
	-8 $(TARGET).d64 \
	-moncommands "monitor-commands" \
	-remotemonitor \
	-remotemonitoraddress "127.0.0.1:6510" \
	-autostart $(TARGET).d64

# --- Utility targets ---

# Build a real .d64 disk image holding both the resident client and the
# petscii_editor overlay module, as an alternative to VICE's `-fs8 "."`
# host-filesystem passthrough for device 8 (which `make vice` still uses
# day to day) -- useful for testing against a real mounted disk image, or
# eventually writing to a real floppy for actual hardware.
#
# Uses c1541 (part of VICE, native -- no wine/wine32 dependency, unlike
# c64list's own -d64 flag, which this originally tried and got blocked
# on a missing wine32/multiarch install) to format a fresh image and
# write both programs into it.
#
# CASE MATTERS, verified live in this session (VICE remote monitor: LOAD
# against a real c1541-written disk, checking the KERNAL's own carry/
# error-code result -- not just theory): c1541 -write's destination name
# does its own ASCII-case -> PETSCII-range conversion, and it's the
# OPPOSITE of what you'd guess -- lowercase input produces the $41-$5A
# ("unshifted key") byte range, UPPERCASE input produces $C1-$DA ("shifted
# key"). "PETSCII.ED" below is deliberately typed in caps so it lands as
# $C1-$DA, because that's what a real C64 disk directory actually stores
# for uppercase letters (confirmed the hard way: tada-client.asm's
# load_petscii_editor originally sent plain `ascii "PETSCII.ED"` --
# literal $41-$5A ASCII bytes -- and got KERNAL error $04, FILE NOT FOUND,
# even though both encodings display identically on screen). tada-
# client.asm's own petscii_editor_filename now uses the matching raw
# $d0,$c5,$d4,... byte literals rather than `ascii` for exactly this
# reason -- keep the two in sync if either changes.
$(TARGET).d64: $(TARGET).prg petscii_editor.prg config_menu.prg help_menu.prg keymap_menu.prg
	rm -f $(TARGET).d64
	c1541 -format "tada,00" d64 $(TARGET).d64
	c1541 $(TARGET).d64 -write $(TARGET).prg "tada-client"
	c1541 $(TARGET).d64 -write petscii_editor.prg "PETSCII.ED"
	c1541 $(TARGET).d64 -write config_menu.prg "CONFIG.MNU"
	c1541 $(TARGET).d64 -write help_menu.prg "HELP.MNU"
	c1541 $(TARGET).d64 -write keymap_menu.prg "KEYMAP.ED"

d64: $(TARGET).d64

# --- Debug build ---
# A second, separately-named .prg/.d64 with -def:keymap_debug passed to
# c64list, for trying out {ifdef:keymap_debug}...{endif} code (keymap.
# asm's dispatch rework) without touching $(TARGET).prg/$(TARGET).d64
# (the normal build above) at all -- Ryan's ask, 2026-09-02: build a
# debug variant instead of risking the working copy while a new
# dispatch path is still being verified live.
#
# A dedicated parser variable (keymap_debug), deliberately NOT the
# pre-existing "debug" one $(TARGET).asm already has and unconditionally
# {undef:}s near its top -- confirmed live 2026-09-02 that -def:debug
# alone doesn't even work around that ({def:}/{undef:} process
# sequentially, so a later {undef:} always wins over an earlier
# command-line -def:), and more importantly that "debug" wakes up an
# old, apparently-never-actually-run-before per-character trace
# elsewhere in tada-client.asm that corrupts real keyboard input (see
# the keymap_debug ifdef block's own comment in tada-client.asm for the
# root cause). keymap_debug sidesteps both problems: unaffected by that
# {undef:}, and doesn't share a name with anything else in the file, so
# this could just reuse $(TARGET)_pp.asm directly as c64list's input --
# no sed-stripping needed the way working around "debug" would have
# required -- EXCEPT c64list names its .sym output after the INPUT
# file regardless of -prg:, so assembling $(TARGET)_pp.asm twice (once
# per build) would make the second run silently overwrite the first
# build's own $(TARGET)_pp.sym. A plain `cp` to a distinctly-named
# input file avoids that, still far simpler than the sed version.
DEBUG_TARGET = $(TARGET)-debug

$(DEBUG_TARGET)_pp.asm: $(TARGET)_pp.asm
	cp $(TARGET)_pp.asm $(DEBUG_TARGET)_pp.asm

$(DEBUG_TARGET).prg: $(DEBUG_TARGET)_pp.asm
	$(C64LIST) $(DEBUG_TARGET)_pp.asm -prg:$(DEBUG_TARGET) -sym -ovr -def:keymap_debug

$(DEBUG_TARGET).d64: $(DEBUG_TARGET).prg petscii_editor.prg config_menu.prg help_menu.prg keymap_menu.prg
	rm -f $(DEBUG_TARGET).d64
	c1541 -format "tada,00" d64 $(DEBUG_TARGET).d64
	c1541 $(DEBUG_TARGET).d64 -write $(DEBUG_TARGET).prg "tada-client"
	c1541 $(DEBUG_TARGET).d64 -write petscii_editor.prg "PETSCII.ED"
	c1541 $(DEBUG_TARGET).d64 -write config_menu.prg "CONFIG.MNU"
	c1541 $(DEBUG_TARGET).d64 -write help_menu.prg "HELP.MNU"
	c1541 $(DEBUG_TARGET).d64 -write keymap_menu.prg "KEYMAP.ED"

debug-d64: $(DEBUG_TARGET).d64

# Just preprocess, useful for checking macro/const output
preprocess: $(TARGET)_pp.asm

# Full build without launching VICE
build: all

# Clean all generated files
clean:
	rm -f $(TARGET)_pp.asm \
	      $(TARGET)_pp.prg \
	      $(TARGET)_pp.sym \
	      $(TARGET).prg \
	      $(TARGET)-vice-labels \
	      monitor-commands \
	      $(addsuffix _pp.asm,$(SPLIT_MODULES)) \
	      $(addsuffix _pp.asm,$(MODULES)) \
	      $(addsuffix _pp.sym,$(MODULES)) \
	      $(addsuffix .prg,$(MODULES)) \
	      $(addsuffix .sym,$(MODULES)) \
	      $(TARGET).d64 \
	      $(DEBUG_TARGET)_pp.asm \
	      $(DEBUG_TARGET)_pp.sym \
	      $(DEBUG_TARGET).prg \
	      $(DEBUG_TARGET).d64

# Show build status and server reachability
status:
	@echo "=== Build status ==="
	@ls -la $(TARGET).asm 2>/dev/null || echo "$(TARGET).asm: NOT FOUND"
	@ls -la $(TARGET)_pp.asm 2>/dev/null || echo "$(TARGET)_pp.asm: not built"
	@ls -la $(TARGET).prg 2>/dev/null || echo "$(TARGET).prg: not built"
	@ls -la $(TARGET)_pp.sym 2>/dev/null || echo "$(TARGET)_pp.sym: not built"
	@ls -la $(TARGET)-vice-labels 2>/dev/null || echo "$(TARGET)-vice-labels: not built"
	@echo "=== TADA server ==="
	@nc -z $(SL_HOST) $(SL_PORT) 2>/dev/null && \
		echo "$(SL_HOST):$(SL_PORT) REACHABLE" || \
		echo "$(SL_HOST):$(SL_PORT) NOT REACHABLE"

# --- Commodore 128 client (client-128.asm) ---
# Separate program, separate memory map/KERNAL from tada-client.asm
# above -- see client-128.asm's own header comment. No SwiftLink/
# server connection yet, so no ACIA flags or d64 image needed (unlike
# vice: above); just assemble and autostart. input_editor.asm (the
# ported sliding-input.asm line editor) is {include:}'d directly, with
# no {const:}/{def:} macros of its own, so -- unlike screen-handler.asm
# above -- it does NOT need its own macro_preprocessor.py pass; it's
# still listed as a prerequisite below since c64list reads it straight
# off disk when it hits the {include:} line.
TARGET128       = client-128
LAUNCH_VICE128  = x128

# The Keymap Editor popup is the C64 client's own keymap_menu.asm, built
# into the 128 client rather than loaded as an overlay: this rule swaps
# in constants_128.asm (the 128 host's keyboard addresses; the JT_*
# entry points are labels in keymap_host_128.asm) and comments out the
# overlay's `orig`, then it gets its own preprocessing pass like any
# split module. -def:c128 turns on its {ifdef:c128} parts (the 128's
# extra key numbers).
keymap_menu_128.asm: keymap_menu.asm
	sed -e 's/{include:constants.asm}/{include:constants_128.asm}/' \
	    -e 's/^\([[:space:]]*\)orig \$$3800/\1; orig $$3800 -- KEYMAP.ED overlay address, unused when built into client-128/' \
	    keymap_menu.asm > keymap_menu_128.asm

keymap_menu_128_pp.asm: keymap_menu_128.asm constants_128.asm
	$(PREPROCESSOR) keymap_menu_128.asm

$(TARGET128)_pp.asm: $(TARGET128).asm input_editor.asm vdc.asm vdc_screen.asm keymap_host_128.asm keymap_128.asm keymap_menu_128_pp.asm
	$(PREPROCESSOR) $(TARGET128).asm

$(TARGET128).prg: $(TARGET128)_pp.asm
	$(C64LIST) $(TARGET128)_pp.asm -prg:$(TARGET128) -sym -ovr -def:c128
	python3 ./check_128_layout.py $(TARGET128).prg $(TARGET128)_pp.sym

$(TARGET128)-vice-labels: $(TARGET128).prg
	$(CONVERT_LABELS) $(TARGET128)_pp.sym $(TARGET128)-vice-labels

monitor-commands-128: $(TARGET128)-vice-labels
	echo "ll \"$(TARGET128)-vice-labels\"" > monitor-commands-128

all128: $(TARGET128).prg $(TARGET128)-vice-labels monitor-commands-128

# Positional trailing .prg argument autostarts it directly, same as
# every live-testing launch this session -- no -autostart/d64 needed
# since there's no overlay module or disk image to bundle yet. Own
# remote-monitor port (6511) so this can run alongside `make vice`
# (port 6510) without colliding.
vice128: all128
	$(LAUNCH_VICE128) \
	-moncommands "monitor-commands-128" \
	-remotemonitor \
	-remotemonitoraddress "127.0.0.1:6511" \
	$(TARGET128).prg

preprocess128: $(TARGET128)_pp.asm

build128: all128

clean128:
	rm -f $(TARGET128)_pp.asm \
	      keymap_menu_128.asm keymap_menu_128_pp.asm \
	      $(TARGET128)_pp.prg \
	      $(TARGET128)_pp.sym \
	      $(TARGET128).prg \
	      $(TARGET128)-vice-labels \
	      monitor-commands-128

.PHONY: all vice d64 debug-d64 preprocess build clean status all128 vice128 preprocess128 build128 clean128
