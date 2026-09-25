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
; act on the KERNAL's own PNT/PNTR ($d1-$d3, zero page, so directly
; readable/writable by keymap_menu.asm without a trampoline of their
; own) and the resident cursor_phase byte; key_capture_combo's own
; comment explains how it keeps those two trampolines and $d1-$d3
; correctly scoped to just its own capture-wait sub-state.
JT_CURSOR_HIDE               = $c023
JT_UPDATE_CURSOR             = $c026

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
; $c029, not $c023 -- JT_CURSOR_HIDE/JT_UPDATE_CURSOR (above) took the
; 6 bytes this used to start at.
KEYMAP_TABLE_PTR             = $c029
