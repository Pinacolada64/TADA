; client-128.asm
; TADA Commodore 128 client -- early skeleton, NOT functional yet.
;
; See assembly-language/client/128_CLIENT_MECHANICS.md for the feature
; wishlist this is starting to work through. Runs in 128 native mode
; (not the C64-compatibility "GO 64" mode tada-client.asm targets) --
; separate binary, separate memory map, separate KERNAL. Does not share
; code with tada-client.asm; anything genuinely reusable (SwiftLink
; init, the receive-buffer protocol) gets pulled over deliberately once
; this has enough of its own scaffolding to need it, not blindly copied
; up front.
;
; Today this does the first two items on that wishlist: read the 40/80
; column switch at startup, and (VIC/40-column path only -- the 80-
; column/VDC path is still just a placeholder message) set up a
; scrolling dialogue window via ESC-T/ESC-B, a static status row, and a
; static input row below it, mirroring tada-client.asm's STATUS_ROW/
; PROMPT_ROW layout for a familiar player experience across both
; clients. Still no SwiftLink, no server connection, no tab-stop sync
; client code (that part already landed server-side only, see
; terminal.c128_tab_sync_bytes()).
;
; Verified against Compute's 128 Programmer's Guide (pdftotext -layout;
; see 128_CLIENT_MECHANICS.md's own citation note about why a naive
; extract of this book's tables can't be trusted) rather than guessed:
;   - Native-mode BASIC program text starts at $1C01 (7169), not the
;     C64's $0801 -- different memory map, so the BASIC-stub loader
;     bytes below are recomputed for this load address, not copied from
;     tada-client.asm's C64 stub.
;   - $D505 (54533 decimal), the MMU mode configuration register: bit 7
;     reads the 40/80-column switch (1 = up = 40 columns/VIC-II, 0 =
;     down = 80 columns/VDC). "Read and acted upon only at power on or
;     reset" -- not a live togglable interrupt source (that's RESTORE,
;     a completely separate key wired to CIA 2's NMI line), so this is
;     safe to read exactly once at startup with no interrupt-handler
;     interaction to worry about.
;   - ESC-T sets a window's top-left corner, ESC-B its bottom-right --
;     both "at current cursor position" (a prior PLOT positions the
;     cursor, then the escape locks that corner in), same underlying
;     mechanism as the BASIC-level `WINDOW x1,y1,x2,y2[,clear]`
;     statement ($FE $1A, "Not available in BASIC 2.0" -- 128-only).
;   - Critically, PLOT's own KERNAL doc says: "the position is relative
;     to the current window, not the screen" once a window is active,
;     and errors ("Position outside window if carry set") if asked to
;     move outside it. That means the status/input rows below the
;     dialogue window can't be reached via ordinary PLOT/CHROUT once the
;     window is set up -- they need raw SCREEN_RAM pokes instead, same
;     as tada-client.asm's own redraw_status_row already does for the
;     C64's STATUS_ROW (bypassing CHROUT/PLOT there for exactly this
;     kind of reason, if for a different underlying cause).

; MMU mode configuration register -- bit 7 is the 40/80 switch.
{const: MMU_MODE_CONFIG $d505}
{const: SWITCH_40_COL_MASK $80}

; KERNAL
{const: KERNAL_CHROUT $ffd2}
{const: KERNAL_PLOT   $fff0}
{const: KERNAL_GETIN  $ffe4}

; VIC-II text screen -- same default location and 25x40 layout as the
; C64 (native 128 mode's 40-column path uses the same VIC-II chip).
; SCREEN_RAM itself is one of macro_preprocessor.py's own built-in
; {const:}s (already $0400 -- redefining it errors "Cannot redefine
; built-in constant"), so only ROW_BYTES needs declaring here.
{const: ROW_BYTES   40}

; Screen row layout -- mirrors tada-client.asm's STATUS_ROW (23) /
; PROMPT_ROW (24) exactly, so a player switching between the C64 and
; C128 clients sees the same layout. WIN_TOP/WIN_BOTTOM bound the
; scrolling dialogue window (rows 0-22); STATUS_ROW/INPUT_ROW sit below
; it, reached only via raw SCREEN_RAM pokes (see header comment).
{const: WIN_TOP      0}
{const: WIN_BOTTOM   22}
{const: STATUS_ROW    23}
{const: INPUT_ROW     24}
{const: STATUS_ROW_OFFSET 920}   ; STATUS_ROW * ROW_BYTES
{const: INPUT_ROW_OFFSET  960}   ; INPUT_ROW * ROW_BYTES

; Reverse-video bit -- same convention as tada-client.asm's status row
; (a screen code with bit 7 set displays reverse video on this charset,
; same as the C64's).
{const: REVERSE_BIT $80}

        orig $1c01

; BASIC stub: 10 SYS7181 (native-128-mode load address is $1c01, not the
; C64's $0801 -- see header comment -- so this next-line-pointer/target
; pair is recomputed for that, not the C64 client's stub bytes).
        byte $0d,$1c,$0a,$00,$9e,$37,$31,$38,$31,$00,$00,$00

start:
        lda MMU_MODE_CONFIG
        and #SWITCH_40_COL_MASK
        bne forty_col_mode

eighty_col_mode:
        lda #0
        sta screen_mode          ; 0 = VDC/80-column
        ldx #0
eighty_msg_loop:
        lda eighty_msg,x
        beq done
        jsr KERNAL_CHROUT
        inx
        jmp eighty_msg_loop

forty_col_mode:
        lda #1
        sta screen_mode          ; 1 = VIC-II/40-column

        jsr init_irq              ; install the IRQ dispatcher (just the
                                   ; blink-cursor task so far) before
                                   ; anything else touches the screen
        jsr init_window
        jsr draw_status_row

        ; Demo: a few lines of filler dialogue text, printed via ordinary
        ; CHROUT -- confirms the window actually confines/scrolls this
        ; text to rows 0-22 rather than running over the status/input
        ; rows below it. NEEDS LIVE VICE CONFIRMATION -- assembles clean
        ; and follows the documented ESC-T/ESC-B contract, but the
        ; window-scrolling *behavior* itself hasn't been visually
        ; verified yet (no automated test harness reaches real hardware/
        ; emulator behavior for this).
        ldx #0
demo_msg_loop:
        lda demo_msg,x
        beq main_loop
        jsr KERNAL_CHROUT
        inx
        jmp demo_msg_loop

; --- Main loop: read a line from the input row, echo it into the
; scrolling dialogue window. No server connection yet -- this just
; proves the three-region layout (scrolling window / static status row
; / static input row) works together before SwiftLink gets wired in.
;
; The line editor itself is sliding-input.asm's ported insert/delete/
; cursor-movement/word-jump core (input_editor.asm) -- its drwstr
; redraw goes through PLOT, which is window-relative once ESC-T/ESC-B
; is active (see this file's header comment), and INPUT_ROW (24) sits
; below the normal WIN_BOTTOM=22 dialogue window. So the window is
; widened to the full screen for the duration of the call and narrowed
; back after -- narrowing does NOT re-clear (see set_window_narrow),
; since that would wipe the scrolled dialogue history on every line. ---
main_loop:
        jsr set_window_full
        jsr call_sliding_input
        jsr set_window_narrow
        ldx #0
echo_prefix_loop:
        lda echo_prefix,x
        beq echo_body
        jsr KERNAL_CHROUT
        inx
        jmp echo_prefix_loop
echo_body:
        ldx #0
echo_body_loop:
        lda inputbuf,x
        beq echo_done
        jsr KERNAL_CHROUT
        inx
        jmp echo_body_loop
echo_done:
        lda #13
        jsr KERNAL_CHROUT
        jmp main_loop

done:
        rts

; --- init_window: define the scrolling dialogue region (rows WIN_TOP-
; WIN_BOTTOM) via ESC-T (top-left corner)/ESC-B (bottom-right corner).
; Both escapes act on wherever the cursor currently is -- PLOT it first,
; then send the escape to lock that corner in. Once both corners are
; set, PLOT's own coordinates become window-relative (see this file's
; header comment) -- status_row/input_row below the window are reached
; via raw SCREEN_RAM pokes instead, never through PLOT/CHROUT again
; after this runs. ---
init_window:
        jsr set_window_narrow

        ; ESC-T/ESC-B set the window's bounds but do NOT clear its
        ; contents or home the cursor the way the BASIC-level
        ; WINDOW x1,y1,x2,y2[,clear] statement does -- confirmed live in
        ; VICE 2026-08-24: without this, the autostart boot text ("ready.",
        ; "load...", "searching for *", ...) was still sitting in the
        ; window area, and the demo text below started printing from
        ; wherever the cursor happened to be after boot (mid-screen), not
        ; the window's top-left.
        ;
        ; CLR_HOME (147, this project's existing PETSCII_CONTROL_CODES
        ; 'clear' value -- formatting.py) sent TWICE fixes it: the first
        ; press only homes the cursor (Ryan's call, confirmed live) --
        ; clearing a window apparently needs the cursor already at its
        ; home position first -- and the second, now genuinely at home,
        ; performs the real clear. No KERNAL routine found in Compute's
        ; 128 Programmer's Guide for "clear the current window" directly
        ; callable from assembly (only the BASIC WINDOW statement's own
        ; optional clear parameter, which isn't a bare routine call) --
        ; if one turns up later this can shrink to a single JSR.
        lda #147
        jsr KERNAL_CHROUT
        jsr KERNAL_CHROUT
        rts

; --- set_window_narrow / set_window_full: ESC-T/ESC-B window-bound
; helpers. set_window_narrow (rows WIN_TOP-WIN_BOTTOM) is the normal
; dialogue-window bound, used both at boot (init_window, which also
; clears) and after each input_editor.asm call (which must NOT clear,
; since that would wipe the scrolled dialogue history -- see
; main_loop's comment). set_window_full extends the bottom edge down
; to INPUT_ROW so the editor's PLOT-based redraw can reach it. ---
set_window_narrow:
        clc
        ldx #WIN_TOP
        ldy #0
        jsr KERNAL_PLOT
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'T'
        jsr KERNAL_CHROUT

        clc
        ldx #WIN_BOTTOM
        ldy #39
        jsr KERNAL_PLOT
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'B'
        jsr KERNAL_CHROUT
        rts

set_window_full:
        clc
        ldx #WIN_TOP
        ldy #0
        jsr KERNAL_PLOT
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'T'
        jsr KERNAL_CHROUT

        clc
        ldx #INPUT_ROW
        ldy #39
        jsr KERNAL_PLOT
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'B'
        jsr KERNAL_CHROUT
        rts

; --- draw_status_row: raw SCREEN_RAM pokes, reverse video, same
; convention as tada-client.asm's redraw_status_row (bit 7 set on a
; screen code displays reverse video on this charset). Static
; placeholder message for now -- no status queue/rotation yet, that's
; tada-client.asm's status_queue machinery, not ported here yet. ---
draw_status_row:
        ldx #0
draw_status_blank_loop:
        lda #(' ' | REVERSE_BIT)
        sta SCREEN_RAM+STATUS_ROW_OFFSET,x
        inx
        cpx #ROW_BYTES
        bne draw_status_blank_loop

        ldx #0
draw_status_msg_loop:
        lda status_msg,x
        beq draw_status_done
        ora #REVERSE_BIT
        sta SCREEN_RAM+STATUS_ROW_OFFSET,x
        inx
        jmp draw_status_msg_loop
draw_status_done:
        rts

; read_input_row/petscii_to_screencode used to live here -- superseded
; 2026-08-24 by input_editor.asm's ported sliding-input.asm core
; (insert/delete/cursor-movement/word-jump, not just append/backspace),
; called from main_loop as call_sliding_input. That routine draws via
; PLOT/CHROUT rather than raw SCREEN_RAM pokes, so it needs the window
; widened first (see main_loop's comment) -- and it handles the Shift+
; Space -> underscore display convention itself now (drwstr substitutes
; $a0 -> $e4 at display time only; see input_editor.asm's header).

; --- IRQ dispatcher: install, round-robin one job per tick ---
; Same shape as tada-client.asm's own init_irq/irq_handler/
; irq_dispatch_next -- ported deliberately for parity across both
; clients, not independently invented. Hooks CINV ($0314/$0315),
; confirmed the same address/purpose on the 128 as the C64 (Compute's
; 128 Programmer's Guide: "CINV vector to IRQ handler routine"). Not
; independently re-verified here: whether the 128's KERNAL IRQ entry
; stub pushes A/X/Y before jumping through CINV the same way the C64's
; $FF48 does (which is what lets irq_handler skip saving registers
; itself, relying on the eventual jmp (irq_orig) to fall through to the
; stock handler's own pla/tax/pla/tay/pla/rti) -- inherited from the
; C64 pattern on the reasonable assumption of shared KERNAL heritage,
; same as this file's other C64-inherited-but-128-plausible assumptions.
; Only one real job exists yet (irq_task_cursor_blink, from
; input_editor.asm) -- no heartbeat placeholder needed since there's no
; ambiguity to prove the dispatch mechanism against.
init_irq:
        sei
        lda $0314
        sta irq_orig+0
        lda $0315
        sta irq_orig+1
        lda #<irq_handler
        sta $0314
        lda #>irq_handler
        sta $0315
        cli
        rts

irq_handler:
        jsr irq_dispatch_next
        jmp (irq_orig)

irq_dispatch_next:
        ldy irq_task_ptr
        lda irq_task_table,y
        sta irq_dispatch_jmp+1
        iny
        lda irq_task_table,y
        sta irq_dispatch_jmp+2
        iny
        cpy #IRQ_TASK_TABLE_LEN
        bcc irq_dispatch_next_store
        ldy #0
irq_dispatch_next_store:
        sty irq_task_ptr
irq_dispatch_jmp:
        jmp $ffff

{include:input_editor.asm}

irq_orig:
        byte 0,0                 ; saved KERNAL IRQ vector, set by init_irq

irq_task_ptr:
        byte 0                   ; byte offset into irq_task_table, self-modified

irq_task_table:
        word irq_task_cursor_blink
IRQ_TASK_TABLE_LEN = 2           ; entries * 2 -- keep in sync with the table above

; --- Data ---

; screen_mode: 0 = VDC (80-column), 1 = VIC-II (40-column). Set once at
; startup by the 40/80-switch check above; nothing reads it yet -- next
; step is branching actual VIC-II vs VDC init routines on it, per
; 128_CLIENT_MECHANICS.md's wishlist, instead of just reporting which
; one was detected the way this stub does today.
screen_mode:
        byte 0

forty_msg:
        ascii "40-column mode (vic-ii) detected."
        byte 13, 0

eighty_msg:
        ascii "80-column mode (vdc) detected."
        byte 13, 0

; Sent through CHROUT into the scrolling window -- plain PETSCII/ASCII
; text is fine here (not raw screen codes -- unlike status_msg below,
; this never gets poked directly to SCREEN_RAM).
demo_msg:
        ascii "40-column mode (vic-ii) detected."
        byte 13
        ascii "Scrolling dialogue window: rows 0-22."
        byte 13
        ascii "Status row: row 23 (below). Input row: row 24."
        byte 13, 13, 0

echo_prefix:
        ascii "You typed: "
        byte 0

; status_msg: raw screen codes via {alpha:pokealt} (see
; sid_streaming.asm's status_lbl_* for the same convention and its own
; comment on why -- draw_status_row pokes this straight into SCREEN_RAM,
; never through CHROUT, so it needs pre-encoded screen codes rather than
; plain PETSCII/ASCII).
{alpha:pokealt}
status_msg:
        ascii "TADA -- Commodore 128 client (early stub)"
        byte 0
{alpha:normal}

; inputbuf: input_editor.asm's line buffer, one byte per input-row
; column (ROW_BYTES=40) plus a null terminator -- call_sliding_input
; points strptr at this before every call.
inputbuf:
        area ROW_BYTES+1, 0
