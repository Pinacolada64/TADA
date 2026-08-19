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
