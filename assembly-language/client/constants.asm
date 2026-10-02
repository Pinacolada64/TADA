; constants.asm — shared addresses for the resident jump table (JT_*) and
; the PROTO_TABLE protocol-byte block, {include:}d (real c64list include,
; resolved at assembly time -- not this project's own {const:} macro-
; preprocessor directive) by every file that needs them: tada-client.asm,
; config_menu.asm, petscii_editor.asm.
;
; This is addresses only, not values/routines. The jump table's actual
; `jmp` targets and the protocol-byte VALUES (SID_STREAM_CONFIRM = $02,
; etc) are still only defined once, in tada-client.asm itself -- both are
; copied up into this fixed block at boot by init_jump_table.
; config_menu.asm/petscii_editor.asm don't need any of that, just these
; addresses, since they `jsr`/`lda` them (absolute) to reach whatever the
; resident client put there rather than embedding a literal.
;
; Keeping even the addresses in one shared file (instead of each of the
; three files re-declaring the same `NAME = $addr` lines by hand) is what
; closes the loophole that caused the 2026-08-17 incident this whole
; mechanism exists to prevent: a value changed in tada-client.asm, the
; server, and PROTO_TABLE's own declaration all got updated together, but
; two hand-copied `{const: ...}` blocks in the overlay modules didn't. A
; single `{include:constants.asm}` can't drift out of sync with itself.
;
; JT_BASE/PROTO_TABLE moved here from $0340 (the KERNAL "datasette
; buffer", $033c-$03fb, unused by a stock KERNAL since this client never
; touches the tape) to $c000 the same evening, on Ryan's hunch: JiffyDOS
; documents using part of that same buffer for its own fast-load state,
; and a real Commodore-hardware crash (CPU JAM landing in KERNAL ROM,
; confirmed live via the VICE remote monitor) reproduced with a JiffyDOS
; KERNAL but not with a stock one, pointing at exactly this kind of
; collision. $c000-$cfff is genuine RAM on a stock C64 regardless of
; banking config (unlike $a000-$bfff, which is BASIC ROM unless banked
; out) -- nothing else in this codebase uses it (confirmed by grep before
; picking it), and neither stock nor JiffyDOS KERNAL/BASIC touch it.
;
; Ordinary `NAME = value` assignments (not `{const:}`) are safe here
; specifically because {include:} always lands before this file's first
; use in each including file -- see tada-client.asm's "Popup box
; position" comment in config_menu.asm for why a plain `=` constant
; can't be forward-referenced the way {const:} can.
JT_BASE                      = $c000
JT_SL_SEND                   = $c000
JT_SL_RECV                   = $c003
JT_RESUME                    = $c006
JT_SAVE_SCREEN                = $c009
JT_RESTORE_SCREEN             = $c00c
JT_SET_BLINK_MASK             = $c00f
PROTO_TABLE                  = $c012
PROTO_STREAM_START           = $c012
PROTO_SID_STREAM_CONFIRM     = $c013
PROTO_CANVAS_STREAM_CONFIRM  = $c014
PROTO_CANVAS_STREAM_CANCEL   = $c015
PROTO_DISPLAY_STREAM_CONFIRM = $c016
PROTO_DISPLAY_STREAM_CANCEL  = $c017
PROTO_APPLY_STREAM_CONFIRM   = $c018
PROTO_HELP_STREAM_CONFIRM    = $c019

; JT_RESUME (jmp prompt_loop) unconditionally calls wait_for_data --
; block for a server byte -- before it ever calls read_line. Fine for
; every OTHER overlay module, all reached via a server-sent trigger
; byte, where the server has almost always already sent (or is about
; to send) something else by the time the popup closes. keymap_menu.asm
; is explicitly local-only (no server round trip at all, see its own
; header comment) -- closing it via JT_RESUME left the client blocked
; in wait_for_data_first's tight sl_recv poll forever, since nothing
; server-side has any reason to send anything just because a purely
; local popup closed. Confirmed live 2026-09-14 via the VICE monitor:
; reproduced identically via both Save and Cancel (rules out anything
; specific to either exit path), GETIN itself still worked fine when
; called directly (rules out the keyboard buffer), and the status-line
; clock froze too (consistent with mainline never reaching anywhere
; past the tight poll, not a keyboard-specific issue). JT_RESUME_LOCAL
; (jmp resume_local, tada-client.asm) skips straight past wait_for_data
; for exactly this case -- safe because read_line's own entry point
; already unconditionally resets linelen/cursor_pos to 0 regardless of
; how it was reached (a pre-existing characteristic, not something this
; introduces): a player mid-line when they press F7 already lost that
; partial text under the OLD hardcoded-F7-check code too, since that
; also `jmp`'d away from read_line's own call frame the same way.
; resume_local runs read_line THEN send_line THEN loops back to prompt_
; loop, NOT a bare jmp straight into read_line -- see resume_local's own
; comment for a second, later bug (2026-09-22) that plain jmp caused:
; read_line_done's own rts has nowhere correct to return to without a
; jsr read_line ahead of it.
JT_RESUME_LOCAL              = $c01a

; JT_STATUS_PUSH_RESET/JT_BUILD_STATUS_LINE -- added 2026-09-18 so
; keymap_menu.asm (a standalone .prg, same reasoning as KEYMAP_TABLE_PTR
; below: doesn't {include:} tada-client.asm/screen-handler.asm and so
; can't reach status_push_reset/build_status_line by label) can push its
; own status-row messages for Save/Cancel, the same way keymap.asm's
; own init_keymap/load_keymap_menu already do directly (being {include:}'d
; into the resident program, not a separate .prg). Same X/Y-pointer
; calling convention as calling build_status_line directly -- see that
; routine's own comment in screen-handler.asm.
JT_STATUS_PUSH_RESET         = $c01d
JT_BUILD_STATUS_LINE         = $c020

; JT_CURSOR_HIDE/JT_UPDATE_CURSOR -- added 2026-09-18 so keymap_menu.asm
; can blink a real cursor (Ryan's ask) at the end of key_capture_combo's
; live modifier/key readout while its own kcc_wait loop polls GETIN,
; the same way read_line_loop already blinks one at the input line's
; own cursor_pos. Same reasoning as JT_STATUS_PUSH_RESET above for why
; this needs a trampoline at all (cursor_hide/update_cursor are plain
; labels in tada-client.asm, unreachable from a separate .prg). Unlike
; that pair, the caller doesn't pass anything in X/Y -- both routines
; act on the resident cursor position (set via JT_SET_CURSOR below;
; the KERNAL's own PNT/PNTR, $d1-$d3, until 2026-09-28) and the
; resident cursor_phase byte; key_capture_combo's own comment explains
; how it keeps those trampolines and the saved cursor position
; correctly scoped to just its own capture-wait sub-state.
JT_CURSOR_HIDE               = $c023
JT_UPDATE_CURSOR             = $c026

; JT_GET_CURSOR/JT_SET_CURSOR/JT_CLEAR_SCREEN -- added 2026-09-28 when
; screen-output.asm took the screen over from KERNAL CHROUT/PLOT. The
; resident cursor (the one term_chrout prints at and cursor_toggle
; blinks) is now screen-output.asm's own crsr_row/crsr_col, not the
; KERNAL's PNT/PNTR ($d1-$d3), so overlays can't just poke those any
; more. GET returns .X = row, .Y = column; SET takes the same (the
; KERNAL_PLOT register order). keymap_menu.asm uses GET/SET to park the
; blink cursor on its own popup rows and put it back afterward;
; petscii_editor.asm uses CLEAR_SCREEN (blank every row but STATUS_ROW,
; repaint STATUS_ROW, home the resident cursor) where it used to CHROUT
; a $93.
JT_GET_CURSOR                = $c029
JT_SET_CURSOR                = $c02c
JT_CLEAR_SCREEN              = $c02f

; Not a jump-table entry or protocol byte -- a 2-byte pointer (lo, hi)
; to keymap_table's real runtime address, written once by init_keymap
; at boot. keymap_table can't get a fixed hand-chosen address the way
; BACKUP_CHARS/BACKUP_COLORS/OVERLAY_BUF do (no safe gap of 378+ free
; bytes was found between the resident program's own natural end and
; BACKUP_CHARS at $1900), so keymap_menu.asm (a separate standalone
; .prg, same as config_menu.asm/petscii_editor.asm -- doesn't {include:}
; keymap.asm and so can't see its `keymap_table = ...` symbol at
; assembly time even if that address WERE fixed) reads this pointer at
; runtime instead of needing to know or guess the address in advance.
; $c032, not $c023 -- JT_CURSOR_HIDE/JT_UPDATE_CURSOR (above) took the
; 6 bytes this used to start at, then JT_GET_CURSOR/JT_SET_CURSOR/
; JT_CLEAR_SCREEN the 9 after that ($c029 until 2026-09-28).
; POPUP_SCREEN -- where the overlays poke their popups: tada-client.asm's
; SCREEN_BUF_A, the VIC-bank-3 screen buffer every loader makes front
; (ensure_buffer_a_front) before jumping to OVERLAY_BUF. The overlays
; used macro_preprocessor.py's built-in SCREEN_RAM ($0400) instead,
; which the client stopped displaying when the double-buffered bank-3
; screen (a9001e4) reached master with PR #61 -- every C64 popup drew
; off-screen and only its color-RAM greying showed (found 2026-10-01).
; Keep in step with SCREEN_BUF_A.
POPUP_SCREEN                 = $c400

KEYMAP_TABLE_PTR             = $c032

; CONFIG_SETTINGS_PTR -- same idea as KEYMAP_TABLE_PTR, for the client
; settings block (keymap.asm's config_settings) saved in TADA64.CFG
; right after keymap_table. Written by init_keymap at boot; read by
; drive_menu.asm (DRIVE.MNU), which can't see keymap.asm's symbols.
; Added 2026-10-01 with the drive picker.
CONFIG_SETTINGS_PTR          = $c034

; JT_RUN_UNDER_IO -- added 2026-10-02 with config_menu.asm's Border
; style setting. jsr's the routine at .X/.Y (lo/hi) with $01 set to
; all-RAM, so it can read and write the charset in the RAM behind
; $d000 (POPUP_CHARGEN) -- with I/O banked out, SwiftLink's receive
; NMI would read garbage from $de00 (see run_under_io in tada-client.
; asm for how it's held off). The routine may not touch I/O or call
; the KERNAL. Sits after the two pointers above rather than with the
; rest of the jump table; init_jump_table writes it the same way.
JT_RUN_UNDER_IO              = $c036

; POPUP_CHARGEN -- where the client's charset lives: tada-client.asm's
; CHARGEN_DEST, the RAM behind $d000 that VIC bank 3 reads its glyphs
; from. Keep in step with CHARGEN_DEST.
POPUP_CHARGEN                = $d000

; Border-style state, kept in overlay RAM ABOVE every overlay module's
; image (the largest, keymap_menu, ends near $4cb0; check_overlay_
; margin.py --modules fails the .d64 build if one ever reaches here) so
; it survives other overlays loading over OVERLAY_BUF -- config_menu.asm
; isn't resident, and once it has swapped in the double-line glyphs the
; only copy of the Gothic originals is the backup here. Not $9e00-$9fff:
; that's where the KERNAL would put RS-232 buffers if device 2 were ever
; opened. tada-client.asm's switch_to_bank3_with_charset clears
; BORDER_SIG at boot, since that's when the charset is freshly Gothic
; again (a soft reset leaves this RAM as it was).
BORDER_STATE                 = $9000
BORDER_SIG                   = $9000  ; +0,+1: BORDER_SIG_0/_1 once the
                                      ;     backup has been taken
BORDER_CUR_STYLE             = $9002  ; +2: style in the charset now,
                                      ;     0 = Single (Gothic), 1 = Double
BORDER_BACKUP                = $9008  ; +8: the Gothic box glyphs, 8 bytes
                                      ;     each, in config_menu.asm's
                                      ;     glyph_codes order
BORDER_STATE_END             = $9060  ; BORDER_BACKUP + 11 glyphs * 8, by
                                      ; hand (see CONFIG_FILE_SIZE)
BORDER_SIG_0                 = $54    ; 'T' -- two bytes so stray power-on
BORDER_SIG_1                 = $42    ; 'B'    RAM can't pass for valid

; config_settings' layout -- byte offsets into the block, shared by the
; client (keymap.asm), the overlays and the 128 client (keymap_128.asm
; keeps the same layout after its own keymap_table).
CONFIG_VERSION       = 1      ; bump when the block's layout changes
CFG_VERSION          = 0      ; +0: CONFIG_VERSION when it was saved
CFG_DATA_DRIVE       = 1      ; +1: the data drive (session logs and
                              ;     other data files -- the client's own
                              ;     files and TADA64.CFG stay on the
                              ;     drive it was loaded from); 0 = none
                              ;     chosen yet, use that drive
CONFIG_SETTINGS_SIZE = 8      ; +2..+7 reserved, zero

; TADA64.CFG's whole size: keymap_table (keymap.asm's KEYMAP_TABLE_SIZE,
; 432) + the settings block. What keymap_menu.asm's and drive_menu.asm's
; SAVEs write, from KEYMAP_TABLE_PTR. By hand -- see keymap.asm's
; KEYMAP_TABLE_SIZE comment on c64list truncating computed values.
CONFIG_FILE_SIZE     = 440    ; 432 + 8
