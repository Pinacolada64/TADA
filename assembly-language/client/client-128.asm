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
; column switch at startup, and (VIC/40-column path) set up a
; scrolling dialogue window via ESC-T/ESC-B, a static status row, and a
; static input row below it, mirroring tada-client.asm's STATUS_ROW/
; PROMPT_ROW layout for a familiar player experience across both
; clients. Still no SwiftLink, no server connection, no tab-stop sync
; client code (that part already landed server-side only, see
; terminal.c128_tab_sync_bytes()).
;
; The 80-column (VDC) path (2026-09-29) keeps the same row layout but
; draws dialogue itself -- vdc.asm (8563 register/block-copy/fill
; primitives, modeled on the editor ROM's own $CDCC/$C40D/$C4A5) and
; vdc_screen.asm (dialogue output with block-copy scrolling, a 150-row
; scrollback history in bank 0 RAM under BASIC, CRSR UP/DOWN to view
; it). The input row still goes through input_editor.asm's KERNAL
; PLOT/CHROUT, which the editor points at the VDC in 80 columns.
;
; The Keymap Editor (same day) is the C64 client's own keymap_menu.asm,
; built in (keymap_host_128.asm hosts it, keymap_128.asm holds the table
; and dispatch); F7 opens it in either mode, and KEYMAP.CFG is shared
; with the C64 client. See 128_CLIENT_MECHANICS.md's Keymap Editor
; section, and MMU_CLIENT_CONFIG below for why the program may now
; extend past $4000.
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

; Editor zero page: bit 7 set = the editor is driving the 80-column
; (VDC) screen. See start's comment on why this, not the switch.
{const: EDITOR_MODE_80 $d7}

; Widest screen (VDC) -- sizes inputbuf and status_line; scr_cols holds
; the live width (40 or 80).
{const: MAX_COLS 80}

; MMU configuration for the whole run: bank 0 RAM at $4000-$bfff (BASIC
; ROM out), I/O and the KERNAL in -- Compute's 128 Programmer's Guide
; figure 7-5. The Keymap Editor (keymap_menu.asm, built in) pushes the
; program past $4000, and the scrollback history lives in $6000-$bfff.
; Checked against the ROMs 2026-09-29 before relying on it: the editor
; ($C000-$CFFF) never writes $FF00, and the KERNAL only does so in
; save/restore pairs (INDFET/INDSTA for LOAD/SAVE, DMA, the IRQ/NMI/BRK
; stubs) or in JSRFAR/JMPFAR, which this client never calls. The one
; catch: the KERNAL IRQ runs irq_handler with $FF00 = $00, so everything
; an interrupt reaches must stay below $4000 -- see check_128_layout.py.
{const: MMU_CONFIG_REG    $ff00}
{const: MMU_CLIENT_CONFIG $0e}

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
        ; Select the lowercase/uppercase charset (CHR$(14)), same as
        ; tada-client.asm -- the server encodes Commodore text with
        ; petscii_c64en_lc, so e.g. the Hourglass clock's "PM" arrives
        ; as shifted $d0/$cd and only reads as letters in this charset.
        ; This used to force uppercase/graphics (CHR$(142), 2026-08-24,
        ; on the belief that status_msg/demo_msg/echo_prefix were
        ; encoded for it). Rendering x128's screen RAM through the real
        ; chargen ROM on 2026-09-29 showed otherwise: status_msg's
        ; {alpha:pokealt} codes ("C" = $43, "o" = $0f) are lowercase-
        ; charset codes, so under CHR$(142) "TADA" and "Commodore"'s "C"
        ; were drawing as graphics glyphs.
        lda #14
        jsr KERNAL_CHROUT
        ; ...and keep it: CHR$(11) disables SHIFT+C= charset switching
        ; (sets LOCKS $f7 = 128), the same lock tada-client.asm sets on
        ; the C64. 128 mode's own codes per Compute's 128 Programmer's
        ; Guide CHR$ table -- 11 disable / 12 enable; the C64's 8/9 are
        ; 64-mode only (9 is TAB here).
        lda #11
        jsr KERNAL_CHROUT

        lda #MMU_CLIENT_CONFIG
        sta MMU_CONFIG_REG
        jsr km_init_keyboard      ; F-keys -> single codes, CTRL+CRSR fix
        jsr init_keymap           ; KEYMAP.CFG, or the defaults

        ; Which screen is the editor actually driving? $D7 bit 7 (set =
        ; 80 columns) rather than the $D505 switch bit: the switch is only
        ; read at reset, and ESC-X can swap screens afterwards -- $D7 is
        ; what CHROUT/PLOT (input_editor.asm) will really draw on, and
        ; it's the flag the editor's own VDC code tests ($C161, $C6E7).
        bit EDITOR_MODE_80
        bmi eighty_col_mode
        jmp forty_col_mode

; --- 80 columns: our own VDC dialogue output (vdc_screen.asm) with block-
; copy scrolling and a scrollback history; no ESC-T/ESC-B window at all,
; since dialogue output never goes through CHROUT here. ---
eighty_col_mode:
        lda #0
        sta screen_mode          ; 0 = VDC/80-column
        lda #MAX_COLS
        sta scr_cols
        jsr init_irq
        jsr vdc_screen_init
        jsr draw_status_row
        ldx #0
eighty_msg_loop:
        lda eighty_msg,x
        beq eighty_msg_done
        jsr out_char
        inx
        jmp eighty_msg_loop
eighty_msg_done:
        jmp main_loop

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
;
; In 80 columns there's no window to widen: the editor's window is the
; whole screen and dialogue output bypasses CHROUT (vdc_screen.asm).
main_loop:
        tsx                       ; JT_RESUME_LOCAL (the Keymap Editor
        stx main_loop_sp          ; closing) comes back to this depth
        lda screen_mode
        beq main_loop_vdc
        jsr set_window_full
        jsr call_sliding_input
        jsr set_window_narrow
        jmp main_loop_line
main_loop_vdc:
        jsr call_sliding_input
main_loop_line:
        jsr clock_test_command    ; "clock <text>" sets the status-row
        bcs main_loop             ; clock locally -- see its own comment
        jsr fill_test_command     ; "fill" prints FILL_TEST_LINES lines
        bcs main_loop             ; to scroll back through
        ldx #0
echo_prefix_loop:
        lda echo_prefix,x
        beq echo_body
        jsr out_char
        inx
        jmp echo_prefix_loop
echo_body:
        ldx #0
echo_body_loop:
        lda inputbuf,x
        beq echo_done
        jsr out_char
        inx
        jmp echo_body_loop
echo_done:
        lda #13
        jsr out_char
        jmp main_loop

; --- out_char: .A = PETSCII for the dialogue area, whichever screen.
; 40 columns: CHROUT into the ESC-T/ESC-B window. 80 columns: dlg_putc.
; Preserves X (and Y) either way -- callers index strings with X. ---
out_char:
        pha
        lda screen_mode
        beq out_char_vdc
        pla
        jmp KERNAL_CHROUT
out_char_vdc:
        pla
        jmp dlg_putc

; --- editor_key_hook: called by input_editor.asm for every key. .A =
; the GETIN byte; carry set = consumed (the editor just redraws), carry
; clear = .A is what the editor should handle (normally the key itself).
;
; Order: any key first clears a status-row override ("Saved keymap."
; etc.). In 80 columns, plain CRSR UP/DOWN (any modifier but CTRL, so C=
; still pages) belong to scrollback (vdc_key_hook); every other key
; leaves scrollback. Then the keymap (keymap_128.asm's km_dispatch) gets
; the key -- word jumps, home/end, macros, F7 for the editor. So in 80
; columns a keymap binding on plain CRSR UP/DOWN (the defaults' Home/
; End) is shadowed by scrollback; in 40 columns it works as on the C64. ---
editor_key_hook:
        sta editor_hook_key
        lda status_override+1
        beq editor_hook_no_msg
        lda #0
        sta status_override+1
        jsr draw_status_row
editor_hook_no_msg:
        lda screen_mode
        bne editor_hook_keymap
        lda editor_hook_key
        cmp #$91
        beq editor_hook_crsr
        cmp #$11
        bne editor_hook_leave_sb
editor_hook_crsr:
        lda $d3
        and #4                    ; CTRL + CRSR: keymap territory
        bne editor_hook_leave_sb
        lda editor_hook_key
        jmp vdc_key_hook
editor_hook_leave_sb:
        jsr sb_exit
editor_hook_keymap:
        lda editor_hook_key
        jmp km_dispatch

editor_hook_key:
        byte 0

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
        jsr KERNAL_PLOT           ; row 0 is always in-bounds for any
                                   ; window, safe regardless of what's
                                   ; currently active
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'T'
        jsr KERNAL_CHROUT

        ; Can't PLOT to INPUT_ROW here the way set_window_narrow does --
        ; confirmed live 2026-08-24 (debug_plot_carry/_x/_y instrumentation,
        ; since removed): the OLD (narrow, WIN_TOP-WIN_BOTTOM) window is
        ; still the active constraint until ESC-B completes, since ESC-T
        ; alone doesn't redefine the window -- so a PLOT trying to move
        ; to INPUT_ROW (below WIN_BOTTOM) gets rejected outright (carry
        ; set, X/Y left unchanged at the requested-but-refused position,
        ; cursor doesn't actually move). This is the actual root cause
        ; of the "can't type anything" bug Ryan hit live: drwstr's own
        ; later PLOT(INPUT_ROW,...) calls were failing the exact same
        ; way, so the whole line editor was drawing wherever the cursor
        ; was stuck instead of the input row -- GETIN/putchr were
        ; working correctly the entire time (confirmed via inputbuf
        ; contents), only the on-screen feedback was broken.
        ;
        ; Fix: poke the KERNAL's own cursor-position zero page directly
        ; instead of calling PLOT, bypassing its boundary check -- ESC-B
        ; defines the window's bottom-right corner at wherever the
        ; cursor position claims to be, not specifically wherever the
        ; immediately-preceding PLOT call put it. $EB (row) / $EC (col)
        ; are the correct addresses for this on native 128 mode --
        ; confirmed via Compute's 128 Programmer's Guide's own zero-page
        ; map ("235 $EB Current cursor line", "236 $EC Current cursor
        ; column"), NOT the C64's $D6/$D3 (a real difference this file
        ; almost inherited by assumption the way tada-client.asm's own
        ; conventions were carried over elsewhere in this port).
        lda #INPUT_ROW
        sta $eb
        lda #39
        sta $ec
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'B'
        jsr KERNAL_CHROUT
        rts

; --- draw_status_row: raw SCREEN_RAM pokes, reverse video, same
; convention as tada-client.asm's redraw_status_row (bit 7 set on a
; screen code displays reverse video on this charset). Static
; placeholder message for now -- no status queue/rotation yet, that's
; tada-client.asm's status_queue machinery, not ported here yet.
; The Hourglass clock (clock_len bytes of clock_buf, 0 = none) owns the
; row's right end, same as tada-client.asm's redraw_status_row_to: the
; message stops one column short of it (a gap), so with no clock the
; message is capped at 39 columns.
;
; Both screens share this: the row is built in status_line (scr_cols
; wide) and then copied to SCREEN_RAM (40 columns) or VDC row 23 (80,
; vdc_draw_status_line). While scrolled back (80 columns only), the
; scrollback position message replaces status_msg. ---
draw_status_row:
        ldx #0
        lda #(' ' | REVERSE_BIT)
draw_status_blank_loop:
        sta status_line,x
        inx
        cpx scr_cols
        bne draw_status_blank_loop

        ldx sb_offset
        beq draw_status_not_sb
        jsr sb_status_text
        jmp draw_status_have_msg
draw_status_not_sb:
        lda status_override       ; a one-off message (the Keymap Editor's
        ldy status_override+1     ; "Saved keymap.") until the next key
        bne draw_status_have_msg
        lda #<status_msg
        ldy #>status_msg
draw_status_have_msg:
        sta draw_status_read+1
        sty draw_status_read+2
        lda scr_cols
        sec
        sbc #1
        sec
        sbc clock_len
        sta draw_status_limit
        ldx #0
draw_status_msg_loop:
        cpx draw_status_limit
        bcs draw_status_clock
draw_status_read:
        lda $ffff,x               ; self-modified: status_msg or sb_status_buf
        beq draw_status_clock
        ora #REVERSE_BIT
        sta status_line,x
        inx
        jmp draw_status_msg_loop
draw_status_clock:
        lda scr_cols
        sec
        sbc clock_len
        tax                       ; first clock column
        ldy #0
draw_status_clock_loop:
        cpx scr_cols
        bcs draw_status_blit
        lda clock_buf,y
        ora #REVERSE_BIT
        sta status_line,x
        inx
        iny
        jmp draw_status_clock_loop
draw_status_blit:
        lda screen_mode           ; VIC: 40 columns, or 80 columns with the
        ora km_present_on         ; Keymap Editor open (its status row is
        bne draw_status_vic       ; VIC row 23 then, see keymap_host_128.asm)
        jmp vdc_draw_status_line
draw_status_vic:
        ldx #0
draw_status_vic_loop:
        lda status_line,x
        sta SCREEN_RAM+STATUS_ROW_OFFSET,x
        inx
        cpx #ROW_BYTES
        bne draw_status_vic_loop
        rts

draw_status_limit:
        byte 0

; --- Hourglass clock (PlayerFlags.HOURGLASS) -- the display half of
; tada-client.asm's CLOCK_STREAM_CONFIRM ($0b) stream, ported ahead of
; SwiftLink: nothing here receives it from the server yet. Once a
; receive dispatcher exists, its clock-stream handler reads the 16-bit
; length (high byte ignored), calls clock_reset, clock_putc once per
; body byte, then clock_commit -- the same steps as tada-client.asm's
; clock_recv, split up so they don't assume a receive routine that
; doesn't exist here yet. An empty body (clock_reset + clock_commit
; with no putc) hides the clock.
;
; Body bytes are PETSCII, converted to screen codes with the standard
; mapping -- matches the server's petscii_c64en_lc codec now that this
; client runs the lowercase charset (see start's CHR$(14) comment), so
; "PM" (shifted $d0/$cd) shows as capital letters.
CLOCK_MAX = 12                    ; tada-client.asm's CLOCK_MAX / commands/
                                  ; c64_display.py's CLOCK_MAX
clock_reset:
        lda #0
        sta clock_recv_idx
        rts

; .A = one PETSCII body byte. Anything past CLOCK_MAX is dropped, so a
; caller can keep feeding a longer body without losing stream sync.
; Preserves X/Y.
clock_putc:
        stx clock_saved_x
        ldx clock_recv_idx
        cpx #CLOCK_MAX
        bcs clock_putc_rts
        jsr petscii_to_screen
        sta clock_buf,x
        inc clock_recv_idx
clock_putc_rts:
        ldx clock_saved_x
        rts

clock_commit:
        lda clock_recv_idx
        sta clock_len
        jmp draw_status_row       ; tail call

; .A (a printable PETSCII code, $20-$7f or $a0-$ff) -> screen code --
; same mapping as tada-client.asm's so_petscii_to_screen (this client's
; own old petscii_to_screencode went away with input_editor.asm).
petscii_to_screen:
        cmp #$40
        bcc p2s_rts         ; $20-$3f: unchanged
        cmp #$60
        bcc p2s_sub40       ; $40-$5f -> $00-$1f
        cmp #$80
        bcc p2s_sub20       ; $60-$7f -> $40-$5f
        cmp #$c0
        bcc p2s_sub40       ; $a0-$bf -> $60-$7f
        cmp #$ff
        beq p2s_pi
        and #$7f                  ; $c0-$fe -> $40-$7e
p2s_rts:
        rts
p2s_sub40:
        sec
        sbc #$40
        rts
p2s_sub20:
        sec
        sbc #$20
        rts
p2s_pi:
        lda #$5e                  ; $ff is pi, same glyph as $de
        rts

; --- clock_test_command: local stand-in for the server's clock stream
; until SwiftLink is wired in. If inputbuf starts with "clock", feeds
; everything after it (one separating space skipped) through clock_
; reset/putc/commit and returns carry set (main_loop skips the echo);
; a bare "clock" hides the clock. Anything else: carry clear, untouched.
; Delete once a real receive path calls clock_reset/putc/commit. ---
clock_test_command:
        ldx #0
clock_test_match:
        lda clock_test_word,x
        beq clock_test_matched
        cmp inputbuf,x
        bne clock_test_no
        inx
        jmp clock_test_match
clock_test_matched:
        jsr clock_reset
        lda inputbuf,x
        cmp #' '
        bne clock_test_feed
        inx
clock_test_feed:
        lda inputbuf,x
        beq clock_test_done
        jsr clock_putc
        inx
        jmp clock_test_feed
clock_test_done:
        jsr clock_commit
        sec
        rts
clock_test_no:
        clc
        rts

clock_test_word:
        ascii "clock"
        byte 0

; --- fill_test_command: another local stand-in until SwiftLink lands.
; A bare "fill" prints FILL_TEST_LINES numbered lines through out_char --
; enough to scroll the 80-column history well past one screen. Each line
; switches color twice (yellow text, white number) so scrollback can be
; checked for keeping attributes, not just characters. Carry set =
; handled. Delete along with clock_test_command. ---
FILL_TEST_LINES = 60
fill_test_command:
        ldx #0
fill_test_match:
        lda fill_test_word,x
        beq fill_test_matched
        cmp inputbuf,x
        bne fill_test_no
        inx
        jmp fill_test_match
fill_test_matched:
        lda inputbuf,x
        bne fill_test_no          ; "fill" exactly, nothing after it
        lda #1
        sta fill_test_n
fill_test_line:
        ldx #0
fill_test_text_loop:
        lda fill_test_text,x
        beq fill_test_number
        jsr out_char
        inx
        jmp fill_test_text_loop
fill_test_number:
        lda fill_test_n
        jsr dec3
        ldx #0
fill_test_digit_loop:
        lda dec3_buf,x
        jsr out_char
        inx
        cpx #3
        bne fill_test_digit_loop
        lda #13
        jsr out_char
        inc fill_test_n
        lda fill_test_n
        cmp #FILL_TEST_LINES+1
        bcc fill_test_line
        sec
        rts
fill_test_no:
        clc
        rts

fill_test_word:
        ascii "fill"
        byte 0
fill_test_text:
        byte $9e                  ; yellow
{alpha:alt}
        ascii "Scrollback test line "
{alpha:normal}
        byte $05, 0               ; white for the number
fill_test_n:
        byte 0

; --- dec3: .A (0-255) -> dec3_buf = three ASCII/PETSCII digits, which
; are also their own screen codes ($30-$39). Preserves X and Y. ---
dec3:
        sty dec3_saved_y
        ldy #'0'
dec3_hundreds:
        cmp #100
        bcc dec3_hundreds_done
        sbc #100                  ; carry set from the cmp
        iny
        jmp dec3_hundreds
dec3_hundreds_done:
        sty dec3_buf
        ldy #'0'
dec3_tens:
        cmp #10
        bcc dec3_tens_done
        sbc #10
        iny
        jmp dec3_tens
dec3_tens_done:
        sty dec3_buf+1
        ora #'0'
        sta dec3_buf+2
        ldy dec3_saved_y
        rts

dec3_buf:
        byte 0,0,0
dec3_saved_y:
        byte 0

clock_buf:
        area CLOCK_MAX, 0
clock_len:
        byte 0                    ; 0 = no clock shown (hourglass off)
clock_recv_idx:
        byte 0
clock_saved_x:
        byte 0

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
        lda km_present_on         ; Keymap Editor open in 80 columns: copy
        beq irq_handler_chain     ; its changes to the VDC (see
        jsr km_present_tick       ; keymap_host_128.asm)
irq_handler_chain:
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
{include:vdc.asm}
{include:vdc_screen.asm}
{include:keymap_host_128.asm}

irq_orig:
        byte 0,0                 ; saved KERNAL IRQ vector, set by init_irq

irq_task_ptr:
        byte 0                   ; byte offset into irq_task_table, self-modified

irq_task_table:
        word irq_task_cursor_blink
IRQ_TASK_TABLE_LEN = 2           ; entries * 2 -- keep in sync with the table above

; --- Data ---

; screen_mode: 0 = VDC (80-column), 1 = VIC-II (40-column). Set once at
; startup by the $D7 check above; main_loop, out_char, editor_key_hook
; and draw_status_row branch on it. scr_cols is the matching width.
screen_mode:
        byte 0
scr_cols:
        byte ROW_BYTES

forty_msg:
        ascii "40-column mode (vic-ii) detected."
        byte 13, 0

; Printed through out_char (dlg_putc) at 80-column startup. {alpha:alt}
; so capitals come out as real shifted PETSCII ($c1-$da) -- plain ascii
; folds everything to $41-$5a, i.e. lowercase in this charset (confirmed
; reading VDC RAM 2026-09-29: "VDC" showed as "vdc").
{alpha:alt}
eighty_msg:
        ascii "80-column mode (VDC) detected."
        byte 13
        ascii "Dialogue rows 0-22 scroll by VDC block copy; status row 23, input row 24."
        byte 13
        ascii "CRSR up/down scrolls back through history a line, C= + CRSR a page."
        byte 13
        ascii "Type fill for 60 test lines."
        byte 13, 13, 0
{alpha:normal}

; Sent through CHROUT into the scrolling window -- plain PETSCII/ASCII
; text is fine here (not raw screen codes -- unlike status_msg below,
; this never gets poked directly to SCREEN_RAM). {alpha:alt} for real
; capitals, same as eighty_msg (plain ascii folds them to lowercase).
{alpha:alt}
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
{alpha:normal}

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
; column (scr_cols, up to MAX_COLS=80) plus a null terminator --
; call_sliding_input points strptr at this before every call.
inputbuf:
        area MAX_COLS+1, 0

; status_line: draw_status_row builds the status row here (screen codes,
; scr_cols wide) before copying it to whichever screen is live.
status_line:
        area MAX_COLS, 0

; status_override: a message draw_status_row shows instead of status_msg
; (high byte 0 = none), set by JT_BUILD_STATUS_LINE, cleared by the next
; key editor_key_hook sees.
status_override:
        word 0
main_loop_sp:
        byte 0

; --- Above this line: everything an interrupt can reach, which must stay
; below $4000 (see MMU_CLIENT_CONFIG). Below: the Keymap Editor, which
; runs only in mainline, so it can sit above $4000. keymap_menu.asm is the
; C64 client's own source, built for the 128 by the Makefile's
; keymap_menu_128.asm rule (constants_128.asm instead of constants.asm,
; no overlay `orig`). ---
{include:keymap_menu_128_pp.asm}
{include:keymap_128.asm}
