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
MODULES         = petscii_editor config_menu

petscii_editor_pp.asm: petscii_editor.asm
	$(PREPROCESSOR) petscii_editor.asm

petscii_editor.prg: petscii_editor_pp.asm
	$(C64LIST) petscii_editor_pp.asm -prg:petscii_editor -sym -ovr

config_menu_pp.asm: config_menu.asm
	$(PREPROCESSOR) config_menu.asm

config_menu.prg: config_menu_pp.asm
	$(C64LIST) config_menu_pp.asm -prg:config_menu -sym -ovr

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

# Step 1: preprocess macros and constants
$(TARGET)_pp.asm: $(TARGET).asm
	$(PREPROCESSOR) $(TARGET).asm

# Step 2: assemble to .prg and .sym in one pass
$(TARGET).prg: $(TARGET)_pp.asm
	$(C64LIST) $(TARGET)_pp.asm -prg:$(TARGET) -sym -ovr

# Step 3: convert symbols to VICE label format
# Note: C64List names the sym file after the input file (tada-client_pp.sym)
$(TARGET)-vice-labels: $(TARGET).prg
	$(CONVERT_LABELS) $(TARGET)_pp.sym $(TARGET)-vice-labels

# Step 4: generate VICE monitor commands to auto-load labels
# TEMP (2026-08-17, Ryan+Claude live debugging the play-#test SID-stream
# hang): also auto-arms watchpoints on sid_mode/sid_remaining_lo/hi so
# they survive killing and relaunching VICE between attempts -- a fresh
# remote-monitor connection doesn't carry over watchpoints set on a
# previous VICE process. Revert to just the `ll` line once that bug's
# found and fixed.
monitor-commands: $(TARGET)-vice-labels
	echo "ll \"$(TARGET)-vice-labels\"" > monitor-commands
	echo "watch store 0314 0319" >> monitor-commands

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
$(TARGET).d64: $(TARGET).prg petscii_editor.prg config_menu.prg
	rm -f $(TARGET).d64
	c1541 -format "tada,00" d64 $(TARGET).d64
	c1541 $(TARGET).d64 -write $(TARGET).prg "tada-client"
	c1541 $(TARGET).d64 -write petscii_editor.prg "PETSCII.ED"
	c1541 $(TARGET).d64 -write config_menu.prg "CONFIG.MNU"

d64: $(TARGET).d64

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
	      $(addsuffix _pp.asm,$(MODULES)) \
	      $(addsuffix _pp.sym,$(MODULES)) \
	      $(addsuffix .prg,$(MODULES)) \
	      $(addsuffix .sym,$(MODULES)) \
	      $(TARGET).d64

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

.PHONY: all vice d64 preprocess build clean status
