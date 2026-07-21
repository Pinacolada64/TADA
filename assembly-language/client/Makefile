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

# --- ROM paths ---
VICE_ROMS       = $(HOME)/.local/share/vice/C64
KERNAL          = $(VICE_ROMS)/kernal-901246-01.bin
BASIC           = $(VICE_ROMS)/basic-901226-01.bin
CHARGEN         = $(VICE_ROMS)/chargen-901225-01.bin

# --- JiffyDOS ROMs ---
JIFFYDOS_C64    = $(HOME)/Documents/c64/JiffyDOS/JiffyC1541.ROM
JIFFYDOS_1541   = /usr/local/share/vice/DRIVES/dos1541-325302-01+901229-05.bin
JIFFYDOS_1581   = $(HOME)/Documents/c64/JiffyDOS/Jiffy1581.rom

# --- SwiftLink / TADA server ---
SL_PORT         = 34064
SL_HOST         = 127.0.0.1
SL_BAUD         = 19200

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
monitor-commands: $(TARGET)-vice-labels
	echo "ll \"$(TARGET)-vice-labels\"" > monitor-commands

# Default target: build everything
all: $(TARGET).prg $(TARGET)-vice-labels monitor-commands

# --- VICE launch ---
vice: all
	$(LAUNCH_VICE) \
	-kernal $(KERNAL) \
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
	-dos1541 $(JIFFYDOS_C64) \
	-dos1541II $(JIFFYDOS_1541) \
	-dos1581 $(JIFFYDOS_1581) \
	-iecdevice8 -device8 1 -fs8 "." \
	-moncommands "monitor-commands" \
	-autostart $(TARGET).prg

# --- Utility targets ---

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
	      monitor-commands

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

.PHONY: all vice preprocess build clean status
