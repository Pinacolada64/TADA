; test_screen_routines.asm
; Standalone harness for the fixed-status-row / custom-scroll routines
; proposed for tada-client.asm (see project memory: async-prompt/
; status-line phase 2). Deliberately has NO SwiftLink/server dependency
; -- boots straight into VICE, drives everything from synthetic data, so
; the scroll/status mechanism can be eyeballed and iterated on before it
; ever touches the real client. Plain c64list syntax throughout (no
; {const:}/{ifdef:} macro-preprocessor directives), so this assembles
; directly with c64list, no macro_preprocessor.py pass needed.
;
; What it exercises, in order:
;   1. Boot: upper/lower charset, clear screen, draw a blank reverse
;      STATUS_ROW.
;   2. Push a 4-message status batch (status_push_reset + 4x status_push_buf
;      via the same sid_print_*-style char-by-char builder pattern) --
;      proves the queue/redraw path and the "first message shows
;      immediately" behavior.
;   3. Print 40 numbered dummy lines through term_chrout, CR-terminated,
;      fast (no delay) -- forces >20 scroll-fixup events back to back.
;      Watch for: rows 0-22 scrolling normally, STATUS_ROW (23) never
;      corrupted/duplicated, input row (24) never disturbed mid-way.
;   4. Infinite loop: call status_service every iteration (rotates the
;      status queue every ~5 real seconds) while slowly printing one
;      more dummy line every ~2 seconds, so rotation and scrolling can
;      be watched happening independently, at a human-watchable pace.
;
; Build: c64list test_screen_routines.asm -prg:test_screen_routines -sym -ovr
; Run:   x64sc -8 test_screen_routines.prg (or drag into an already-running
;        VICE) -- autostarts straight into the test, no server/menu to
;        get through.

; --- VIC-II / screen constants (mirrors tada-client.asm) ---
VIC_MEMORY_CONTROL = $d018
CHARSET_UPPER_LOWER = $17
VIC_BORDER      = $d020
VIC_BACKGROUND  = $d021
VIC_BLACK       = $00

SCREEN_RAM      = $0400
COLOR_RAM       = $d800

CHROUT          = $ffd2
PLOT            = $fff0

; --- Screen layout under test ---
STATUS_ROW           = 23
DIALOGUE_LAST_ROW    = 22
ROW_BYTES            = 40
DIALOGUE_SHIFT_BYTES = 880      ; 22 rows worth (rows 1-22 -> rows 0-21)

STATUS_QUEUE_MAX     = 4
STATUS_SLOT_LEN      = 40       ; 39 visible chars max + null terminator
STATUS_ROTATE_JIFFIES_LO = $2c  ; 300 jiffies (~5s @ ~60Hz), low byte
STATUS_ROTATE_JIFFIES_HI = $01  ; 300 jiffies, high byte

; --- Zero page ---
scr_ptr_lo = $fb
scr_ptr_hi = $fc

        orig $0801
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00   ; 10 SYS2061

start:
        lda #CHARSET_UPPER_LOWER
        sta VIC_MEMORY_CONTROL
        lda #VIC_BLACK
        sta VIC_BORDER
        sta VIC_BACKGROUND
        lda #$93
        jsr CHROUT
        jsr redraw_status_row     ; blank reverse bar at boot, queue empty

        ; --- Step 2: push a 4-message status batch ---
        jsr status_push_reset
        ldx #<msg1
        ldy #>msg1
        jsr status_build_from_table
        jsr status_push_buf
        ldx #<msg2
        ldy #>msg2
        jsr status_build_from_table
        jsr status_push_buf
        ldx #<msg3
        ldy #>msg3
        jsr status_build_from_table
        jsr status_push_buf
        ldx #<msg4
        ldy #>msg4
        jsr status_build_from_table
        jsr status_push_buf

        ; --- Step 3a: 30 SHORT (non-wrapping) fast lines -- isolates the
        ; CR path (term_scroll_newline) with nothing else in play.
        lda #1
        sta test_line_num
test_burst_loop:
        jsr test_next_color
        jsr print_line_number
        ldy #0
test_burst_text:
        lda burst_text,y
        beq test_burst_text_done
        jsr term_chrout
        iny
        jmp test_burst_text
test_burst_text_done:
        lda #$0d
        jsr term_chrout
        inc test_line_num
        lda test_line_num
        cmp #31
        bne test_burst_loop

        ; --- Step 3b: 10 deliberately LONG (wrapping) fast lines --
        ; isolates the column-wrap path (term_scroll_fixup).
        lda #1
        sta test_wrap_num
test_wrap_loop:
        jsr test_next_color
        lda #'W'
        jsr term_chrout
        lda #'R'
        jsr term_chrout
        lda #'A'
        jsr term_chrout
        lda #'P'
        jsr term_chrout
        lda #' '
        jsr term_chrout
        lda test_wrap_num
        jsr print_decimal_byte
        lda #' '
        jsr term_chrout
        ldy #0
test_wrap_text:
        lda wrap_text,y
        beq test_wrap_text_done
        jsr term_chrout
        iny
        jmp test_wrap_text
test_wrap_text_done:
        lda #$0d
        jsr term_chrout
        inc test_wrap_num
        lda test_wrap_num
        cmp #11
        bne test_wrap_loop

        ; --- Step 4: slow loop -- watch rotation + scrolling independently ---
        lda #31
        sta test_line_num
test_slow_loop:
        jsr status_service
        lda $a2
        sec
        sbc test_slow_last
        cmp #120                 ; ~2 seconds between dummy lines
        bcc test_slow_loop
        lda $a2
        sta test_slow_last
        jsr test_next_color
        jsr print_line_number
        ldy #0
test_slow_text:
        lda slow_text,y
        beq test_slow_text_done
        jsr term_chrout
        iny
        jmp test_slow_text
test_slow_text_done:
        lda #$0d
        jsr term_chrout
        inc test_line_num
        jmp test_slow_loop

test_wrap_num:
        byte 0

; --- test_next_color: send the next PETSCII color-change control code
; from a rotating palette, so each new line gets a visually (and, more
; importantly, numerically-checkable-via-monitor) distinct COLOR_RAM
; value. Exercises the half of term_scroll_advance's shift that the
; earlier all-one-color tests never touched -- a broken/omitted color
; shift would have been completely invisible before this, since every
; cell was always the same color regardless of whether it moved
; correctly. Sent via term_chrout like any other byte (color-change
; codes don't move $D6, so they never trigger the scroll fixup, but
; routing them through the same call keeps this consistent with real
; dialogue text and confirms color codes don't confuse it). ---
test_colors:
        byte 5, 28, 30, 159, 156, 158   ; white, red, green, cyan,
                                          ; purple, yellow
TEST_COLORS_LEN = 6
test_color_idx:
        byte 0

test_next_color:
        ldx test_color_idx
        lda test_colors,x
        jsr term_chrout
        inx
        cpx #TEST_COLORS_LEN
        bne test_next_color_store
        ldx #0
test_next_color_store:
        stx test_color_idx
        rts

; --- print_line_number: "LINE " + 2-digit decimal test_line_num ---
print_line_number:
        lda #'L'
        jsr term_chrout
        lda #'I'
        jsr term_chrout
        lda #'N'
        jsr term_chrout
        lda #'E'
        jsr term_chrout
        lda #' '
        jsr term_chrout
        lda test_line_num
        jsr print_decimal_byte
        lda #' '
        jsr term_chrout
        rts

; .a = 0-99 -> two ASCII digits via term_chrout
print_decimal_byte:
        ldx #0
pdb_tens:
        cmp #10
        bcc pdb_ones
        sec
        sbc #10
        inx
        jmp pdb_tens
pdb_ones:
        pha
        txa
        clc
        adc #'0'
        jsr term_chrout
        pla
        clc
        adc #'0'
        jsr term_chrout
        rts

test_line_num:
        byte 0
test_slow_last:
        byte 0

burst_text:
        ascii "short line"          ; "LINE NN short line" -- well under 40
        byte 0                       ; cols, never wraps -- isolates the
                                       ; CR-only path
wrap_text:
        ascii "the quick brown fox jumps over the lazy dog TAIL"
        byte 0                       ; "WRAP NN " + this is >40 cols --
                                       ; always wraps, ending in the
                                       ; visibly-distinct "TAIL" marker so
                                       ; the wrapped remainder is easy to
                                       ; spot on its own row
slow_text:
        ascii "rotation/scroll interaction check"
        byte 0

; ============================================================
; --- Routines under test (candidates for tada-client.asm) ---
; ============================================================

; --- set_screen_line: scr_ptr_lo/hi = SCREEN_RAM + row*40 ---
set_screen_line:
        asl
        tax
        lda row_offsets,x
        clc
        adc #<SCREEN_RAM
        sta scr_ptr_lo
        lda row_offsets+1,x
        adc #>SCREEN_RAM
        sta scr_ptr_hi
        rts

row_offsets:
        word 0,   40,  80,  120, 160, 200, 240, 280, 320, 360
        word 400, 440, 480, 520, 560, 600, 640, 680, 720, 760
        word 800, 840, 880, 920, 960

; --- Generic length-parameterized block copy (self-modified addressing,
; same technique as tada-client.asm's copy_1000) ---
; Input: copy_src_lo/hi, copy_dst_lo/hi, copy_remaining_lo/hi
copy_block:
        lda copy_src_lo
        sta copy_src_load+1
        lda copy_src_hi
        sta copy_src_load+2
        lda copy_dst_lo
        sta copy_dst_store+1
        lda copy_dst_hi
        sta copy_dst_store+2
copy_block_loop:
copy_src_load:
        lda $ffff
copy_dst_store:
        sta $ffff
        inc copy_src_load+1
        bne copy_block_src_ok
        inc copy_src_load+2
copy_block_src_ok:
        inc copy_dst_store+1
        bne copy_block_dst_ok
        inc copy_dst_store+2
copy_block_dst_ok:
        lda copy_remaining_lo
        bne copy_block_dec_lo
        dec copy_remaining_hi
copy_block_dec_lo:
        dec copy_remaining_lo
        lda copy_remaining_lo
        ora copy_remaining_hi
        bne copy_block_loop
        rts

copy_dialogue_block:
        lda #<DIALOGUE_SHIFT_BYTES
        sta copy_remaining_lo
        lda #>DIALOGUE_SHIFT_BYTES
        sta copy_remaining_hi
        jmp copy_block

copy_src_lo:
        byte 0
copy_src_hi:
        byte 0
copy_dst_lo:
        byte 0
copy_dst_hi:
        byte 0
copy_remaining_lo:
        byte 0
copy_remaining_hi:
        byte 0

; --- term_chrout / term_scroll_advance ---
; See this file's header comment / tada-client.asm's planned integration
; for the full reasoning. Short version: call term_chrout instead of
; CHROUT for anything that can legitimately advance the cursor a row at
; a time (dialogue text, typed-char echo). After every such call, if the
; cursor landed in STATUS_ROW, fix it up before the player ever sees it
; -- KERNAL's own whole-screen scroll (row 24 trigger) never fires
; because the cursor is corrected back down before it can ever reach
; row 24.
;
; A bare CR and a column wrap both land the cursor on STATUS_ROW, and it
; turns out they need IDENTICAL handling, not the two-case split this
; routine had in its first two passes (2026-08-20) -- both were wrong in
; the same direction (assuming a column wrap writes its character into
; the *new* row, STATUS_ROW), and both smeared stale reverse-video
; status-bar bytes into the scrolled dialogue history as a result:
;   - A bare CR: CHROUT's newline handling is *only* a cursor move, no
;     character payload -- STATUS_ROW's memory is untouched, still
;     whatever the status bar last drew there.
;   - A column wrap: ordinary terminal behavior writes the wrapping
;     character into the *old* row's last column (row 22 col 39), not
;     into STATUS_ROW at all -- the cursor only *moves* to STATUS_ROW
;     col 0 in preparation for whatever comes next, same as a CR. That
;     character is already correctly carried forward by the shift below
;     (row 22 is within its normal 1-22 source range) -- there is never
;     anything real in STATUS_ROW to relocate for either trigger.
; So both cases reduce to: shift the dialogue window up, blank the fresh
; row 22, reposition the cursor there. No STATUS_ROW content ever needs
; touching or preserving, and redraw_status_row (called elsewhere, e.g.
; on rotation) is the only thing that ever legitimately paints it.
;
; Preserves the caller's X/Y across the entire call, restored right
; before every exit -- confirmed live (2026-08-20) this matters, not
; just defensive box-checking: term_scroll_advance uses Y freely as its
; own loop counter, and CHROUT itself is already documented elsewhere in
; this client as not reliably preserving X. A caller that uses X/Y as
; its own loop index across a run of term_chrout calls (e.g. printing a
; string char-by-char) silently got its index clobbered by whichever
; branch fired here -- looked exactly like an infinite loop (the same
; 40-column window kept reprinting forever) before this fix, since the
; index variable kept getting reset to whatever value the internal
; blank-loop last left it at.
term_chrout:
        stx term_saved_x
        sty term_saved_y
        jsr CHROUT
        ldx $d6                    ; TBLX -- physical cursor row
        cpx #STATUS_ROW
        bcc term_chrout_rts
        jsr term_scroll_advance
term_chrout_rts:
        ldx term_saved_x
        ldy term_saved_y
        rts

term_saved_x:
        byte 0
term_saved_y:
        byte 0

; --- wait_vblank: busy-wait until the raster beam reaches line 250 ---
; Comfortably past the visible area on both PAL (312 lines/frame) and
; NTSC (262 lines/frame) -- moves the START of the scroll's screen-
; memory writes to an off-screen moment, rather than however mid-frame
; the triggering character happened to land. Does NOT fully eliminate
; tearing on its own: the shift itself (two 880-byte copies, screen +
; color, ~3.5ms of CPU time) runs longer than a single vblank window
; (well under 1ms) and spills back into active drawing time regardless.
; A complete fix would chunk the copy across several frames instead of
; doing it atomically -- deferred; this cheap version is worth trying
; first and reevaluating visually before adding that complexity. $d012
; alone (without checking $d011 bit 7) is sufficient for line 250 since
; that's well under 256.
wait_vblank:
        lda $d012
        cmp #250
        bne wait_vblank
        rts

; Shift the dialogue window up, rows 1-22 -> rows 0-21 (screen + color),
; discarding old row 0, then blank the fresh row 22 and reposition the
; cursor there -- see term_chrout's own comment for why both of its
; triggers (CR, column wrap) reduce to exactly this with nothing further
; to preserve from STATUS_ROW.
term_scroll_advance:
        jsr wait_vblank
        lda #<(SCREEN_RAM+ROW_BYTES)
        sta copy_src_lo
        lda #>(SCREEN_RAM+ROW_BYTES)
        sta copy_src_hi
        lda #<SCREEN_RAM
        sta copy_dst_lo
        lda #>SCREEN_RAM
        sta copy_dst_hi
        jsr copy_dialogue_block

        lda #<(COLOR_RAM+ROW_BYTES)
        sta copy_src_lo
        lda #>(COLOR_RAM+ROW_BYTES)
        sta copy_src_hi
        lda #<COLOR_RAM
        sta copy_dst_lo
        lda #>COLOR_RAM
        sta copy_dst_hi
        jsr copy_dialogue_block

        lda #DIALOGUE_LAST_ROW
        jsr set_screen_line         ; scr_ptr_lo/hi = row 22 base
        ldy #0
        lda #$20
term_scroll_advance_blank:
        sta (scr_ptr_lo),y
        iny
        cpy #40
        bne term_scroll_advance_blank
        ldx #DIALOGUE_LAST_ROW       ; PLOT: X=row, Y=col (verified live
        ldy #0                       ; against this VICE build, NOT the
        clc                          ; commonly-assumed opposite)
        jsr PLOT
        rts

; ============================================================
; --- Status queue (reverse-video, rotating, fixed row 23) ---
; ============================================================

status_build_buf:
        area STATUS_SLOT_LEN, 0
status_build_idx:
        byte 0

status_queue0:
        area STATUS_SLOT_LEN, 0
status_queue1:
        area STATUS_SLOT_LEN, 0
status_queue2:
        area STATUS_SLOT_LEN, 0
status_queue3:
        area STATUS_SLOT_LEN, 0

status_slot_lo:
        byte <status_queue0, <status_queue1, <status_queue2, <status_queue3
status_slot_hi:
        byte >status_queue0, >status_queue1, >status_queue2, >status_queue3

status_queue_count:
        byte 0
status_queue_write:
        byte 0
status_queue_read:
        byte 0
status_rotate_last_lo:
        byte 0
status_rotate_last_hi:
        byte 0
status_col:
        byte 0
status_saved_col:
        byte 0
status_saved_row:
        byte 0

; --- Test-only helper: copy a null-terminated table string into
; status_build_buf via status_putc (production code builds these char by
; char inline, e.g. porting sid_print_hex_byte's digit-by-digit style --
; this stand-in just proves status_putc/status_push_buf themselves). ---
; Input: X/Y = lo/hi of a null-terminated string.
status_build_from_table:
        stx scr_ptr_lo
        sty scr_ptr_hi
        ldy #0
status_build_from_table_loop:
        lda (scr_ptr_lo),y
        beq status_build_from_table_done
        jsr status_putc
        iny
        jmp status_build_from_table_loop
status_build_from_table_done:
        rts

; Preserves the caller's Y across the call -- confirmed live (2026-08-20)
; this matters: status_build_from_table's own string-index loop uses Y,
; and the first version of this routine silently clobbered it (Y ended
; the call holding status_build_idx's post-increment value instead of
; the caller's original index+1), skipping every other source character
; -- the missing "L" in "PLAYED" was this bug.
status_putc:
        sty status_putc_saved_y
        ldy status_build_idx
        cpy #STATUS_SLOT_LEN-1
        bcs status_putc_rts
        sta status_build_buf,y
        iny
        sty status_build_idx
status_putc_rts:
        ldy status_putc_saved_y
        rts

status_putc_saved_y:
        byte 0

status_push_reset:
        lda #0
        sta status_queue_count
        sta status_queue_write
        sta status_queue_read
        rts

status_push_buf:
        ldy status_build_idx
        lda #0
        sta status_build_buf,y
        lda status_queue_write
        jsr status_slot_addr
        ldy #0
status_push_buf_copy:
        lda status_build_buf,y
        sta (scr_ptr_lo),y
        beq status_push_buf_copied
        iny
        cpy #STATUS_SLOT_LEN
        bcc status_push_buf_copy
status_push_buf_copied:
        lda #0
        sta status_build_idx
        inc status_queue_write
        lda status_queue_write
        cmp #STATUS_QUEUE_MAX
        bcc status_push_buf_no_wrap
        lda #0
        sta status_queue_write
status_push_buf_no_wrap:
        lda status_queue_count
        cmp #STATUS_QUEUE_MAX
        bcs status_push_buf_count_done
        inc status_queue_count
status_push_buf_count_done:
        lda status_queue_count
        cmp #1
        bne status_push_buf_rts
        lda #0
        sta status_queue_read
        jsr redraw_status_row
        lda $a2
        sta status_rotate_last_lo
        lda $a1
        sta status_rotate_last_hi
status_push_buf_rts:
        rts

; .a = slot index 0..3 -> scr_ptr_lo/hi
status_slot_addr:
        tay
        lda status_slot_lo,y
        sta scr_ptr_lo
        lda status_slot_hi,y
        sta scr_ptr_hi
        rts

status_service:
        lda status_queue_count
        cmp #2
        bcc status_service_rts
        lda $a2
        sec
        sbc status_rotate_last_lo
        sta status_elapsed_lo
        lda $a1
        sbc status_rotate_last_hi
        sta status_elapsed_hi
        lda status_elapsed_hi
        cmp #STATUS_ROTATE_JIFFIES_HI
        bcc status_service_rts
        bne status_service_due
        lda status_elapsed_lo
        cmp #STATUS_ROTATE_JIFFIES_LO
        bcc status_service_rts
status_service_due:
        jsr status_rotate
status_service_rts:
        rts

status_elapsed_lo:
        byte 0
status_elapsed_hi:
        byte 0

status_rotate:
        inc status_queue_read
        lda status_queue_read
        cmp status_queue_count
        bcc status_rotate_redraw
        lda #0
        sta status_queue_read
status_rotate_redraw:
        jsr redraw_status_row
        lda $a2
        sta status_rotate_last_lo
        lda $a1
        sta status_rotate_last_hi
        rts

; --- redraw_status_row: repaint STATUS_ROW with the currently-selected
; queued message (or an all-blank bar if the queue is empty), reverse
; video, padded to 40 columns. Saves/restores the real cursor position
; around this so it never disturbs wherever dialogue text or the input
; cursor actually is. ---
redraw_status_row:
        sec
        jsr PLOT                    ; read current position -> X=row, Y=col
        stx status_saved_row
        sty status_saved_col
        ldx #STATUS_ROW
        ldy #0
        clc
        jsr PLOT                    ; move to (row 23, col 0)
        lda #0
        sta status_col
        lda status_queue_count
        beq redraw_status_row_pad
        lda status_queue_read
        jsr status_slot_addr
redraw_status_row_text:
        ldy status_col
        cpy #39
        bcs redraw_status_row_pad
        lda (scr_ptr_lo),y
        beq redraw_status_row_pad
        jsr CHROUT
        inc status_col
        jmp redraw_status_row_text
redraw_status_row_pad:
        ldy status_col
redraw_status_row_pad_loop:
        cpy #40
        bcs redraw_status_row_reverse
        lda #$20
        jsr CHROUT
        iny
        sty status_col
        jmp redraw_status_row_pad_loop
redraw_status_row_reverse:
        lda #STATUS_ROW
        jsr set_screen_line
        ldy #0
redraw_status_row_reverse_loop:
        lda (scr_ptr_lo),y
        ora #$80
        sta (scr_ptr_lo),y
        iny
        cpy #40
        bne redraw_status_row_reverse_loop
        ldx status_saved_row
        ldy status_saved_col
        clc
        jsr PLOT
        rts

; --- Test fixture messages (ordinary ASCII -- status_putc stores it
; as-is, CHROUT does the ASCII/PETSCII->screencode conversion when
; redraw_status_row prints it, same as everywhere else in the client) ---
msg1:
        ascii "PLAYED $0100 FRAMES"
        byte 0
msg2:
        ascii "ELAPSED $000200 JIFFIES"
        byte 0
msg3:
        ascii "RD=$40 WR=$80"
        byte 0
msg4:
        ascii "STARTS=$03"
        byte 0
