; tada_screen_blit_test.asm
; Standalone harness exploring Ryan's alternative to
; test_screen_routines.asm's vblank-chunked scroll copy (2026-08-22): keep
; TWO 1K screen-character buffers and flip which one the VIC actually
; displays by changing VIC_MEMORY_CONTROL ($d018)'s screen-pointer bits,
; instead of copying 880 bytes of live, currently-displayed SCREEN_RAM in
; small pieces. The buffer NOT currently shown is built up at total
; leisure (no vblank pressure at all -- nobody's looking at it), then the
; flip itself is a handful of cycles, atomically swapping the whole 22-row
; glyph grid in one go. This structurally eliminates glyph tearing rather
; than just keeping each write burst inside a vblank window and hoping.
;
; What double buffering does NOT solve: COLOR_RAM ($d800) is a single
; fixed 1K chip, not bank-switchable the way screen/charset memory is --
; there is no second copy to flip to, so whatever gets poked there is
; live on whatever buffer is CURRENTLY displayed. The color shift still
; needs the same per-vblank chunked copy test_screen_routines.asm already
; uses, just now running alone (screen no longer shares that budget,
; since the screen shift moved entirely off-screen into the back buffer).
; This file is meant to make that trade-off visible/testable, not to
; claim tearing is fully solved -- see copy_color_chunked's own comment.
;
; --- Why VIC bank 3, and how the charset gets there ---
; Both screen buffers live in VIC bank 3 ($c000-$ffff, chosen over bank 0
; to leave $2000 -- OVERLAY_BUF in the real tada-client.asm -- alone for
; eventual integration), selected once at boot via $dd00 and never
; switched again.
;
; The char generator lives at bank-relative $1000-$17ff (absolute
; $d000-$d7ff) -- electrically real RAM, normally hidden from the CPU by
; I/O, reachable only via the well-known $01 processor-port "bank out I/O
; entirely" trick ($01=$30, LORAM/HIRAM/CHAREN all 0). Character ROM is
; only visible to the VIC itself in banks 0 and 2 (confirmed via C64-
; Wiki/Dustlayer research, 2026-08-22), which would normally force a
; ROM-image-copy dance to keep using the stock font in bank 3 -- moot
; here, though, since gothic-charset.asm (2026-08-22, {include:}'d below)
; supplies a complete custom 256-glyph charset of its own. switch_to_
; bank3_with_charset just copies THAT (an ordinary assembled label,
; always visible to the CPU, no ROM-banking read step needed at all) into
; the bank-3 RAM the VIC will read -- one $01=$30 window, one copy_block
; call. Done with interrupts off (SEI) for the whole dance -- fine for
; this isolated harness (nothing else can raise an IRQ/NMI here), but
; NOTE for real-client integration: SwiftLink's byte-arrival NMI is NOT
; maskable by SEI, and $01=$30 banks KERNAL's own NMI vector ($fffa) out
; to uninitialized RAM -- this MUST run before init_swiftlink enables the
; cartridge's RxD IRQ, or a byte arriving mid-dance would jump through
; garbage.
;
; Same house style as test_screen_routines.asm otherwise: no SwiftLink/
; server dependency, no {const:}/{ifdef:} macro-preprocessor directives,
; boots straight into synthetic wrap/scroll test data. Build/run
; identically:
;   c64list tada_screen_blit_test.asm -prg:tada_screen_blit_test -sym -ovr
;   x64sc tada_screen_blit_test.prg

; --- VIC-II / screen constants ---
VIC_MEMORY_CONTROL = $d018
VIC_BANK_SELECT = $dd00        ; CIA2 port A, bits 0-1 -- INVERTED bank
                                 ; encoding: 00=bank3, 01=bank2, 10=bank1,
                                 ; 11=bank0 (KERNAL boot default). Bits 2-7
                                 ; drive the serial/IEC bus -- preserved,
                                 ; never touched here.
VIC_BORDER      = $d020
VIC_BACKGROUND  = $d021
VIC_BLACK       = $00
HIBASE          = $0288        ; KERNAL's screen-high-byte shadow --
                                 ; CHROUT/PLOT compute addresses from this,
                                 ; not from VIC_MEMORY_CONTROL directly, so
                                 ; a buffer flip has to update both. Purely
                                 ; a CPU-side absolute address; unrelated
                                 ; to VIC_BANK_SELECT, needs no bank-
                                 ; relative adjustment.

; --- The two screen character buffers -- both in VIC bank 3 ---
; 1K-aligned, bank-relative slots 0 and 1 ($c000/$c400) -- comfortably
; below CHARGEN_DEST (slot 4, $d000) and clear of the always-fixed
; COLOR_RAM chip (slot 6, $d800 -- a separate 4-bit-wide chip visible at
; that physical address regardless of VIC bank selection, never usable as
; ordinary 8-bit screen/char RAM under any bank).
SCREEN_BUF_A    = $c000
SCREEN_BUF_B    = $c400
VIC_BANK_BASE   = $c000        ; bank 3's absolute base -- flip_screen_
                                 ; buffer subtracts this out to get the
                                 ; bank-relative value $d018 actually wants
COLOR_RAM       = $d800

; --- Character set relocation ---
; gothic_charset (the source data) is {include:}'d near the end of this
; file -- an ordinary assembled label, no ROM-visibility trick needed to
; read it, unlike a stock-font copy would require.
CHARGEN_DEST    = $d000        ; bank3-relative $1000 (char-ptr value 2,
                                 ; 2*$800) -- where the VIC (once in bank
                                 ; 3) will actually look for it
CHARGEN_SIZE    = 2048
CHARGEN_RAM_CONFIG = $30       ; LORAM=0, HIRAM=0, CHAREN=0 -- all RAM,
                                 ; including the cells behind $d000-$dfff
                                 ; (needed to WRITE there -- the CPU can't
                                 ; write through the KERNAL/IO view $01
                                 ; normally leaves mapped)
VIC_D018_INIT   = $04          ; screen-ptr nibble 0 (buffer A, $c000) |
                                 ; char-ptr value 2 ($d000) -- boot value,
                                 ; written once switch_to_bank3_with_
                                 ; charset finishes

CHROUT          = $ffd2
PLOT            = $fff0

; --- Screen layout under test ---
STATUS_ROW           = 23
DIALOGUE_LAST_ROW    = 22
ROW_BYTES            = 40
DIALOGUE_SHIFT_BYTES = 880      ; 22 rows worth (rows 1-22 -> rows 0-21)
STATUS_ROW_OFFSET    = 920      ; STATUS_ROW * ROW_BYTES

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
        jsr switch_to_bank3_with_charset  ; must run before anything below
                                            ; touches the screen -- sets
                                            ; front_hi/HIBASE/VIC_MEMORY_
                                            ; CONTROL/VIC_BANK_SELECT all
                                            ; together
        lda #VIC_BLACK
        sta VIC_BORDER
        sta VIC_BACKGROUND
        lda #$93
        jsr CHROUT
        jsr redraw_status_row     ; blank reverse bar at boot, queue empty

        ; --- Step 1b: build-date/time message, its own batch -- shows
        ; immediately (status_push_buf's own "first message of a fresh
        ; batch" behavior), same as a real boot would display it until
        ; the first real event (e.g. a SID stream) pushes its own batch
        ; and replaces it.
        jsr status_push_reset
        ldx #<build_msg
        ldy #>build_msg
        jsr status_build_from_table
        jsr status_push_buf

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
        ; CR path (term_scroll_advance_blit) ---
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
        ; isolates the column-wrap path ---
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
; from a rotating palette (see test_screen_routines.asm's own comment --
; unchanged here). ---
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
        ascii "short line"
        byte 0
wrap_text:
        ascii "the quick brown fox jumps over the lazy dog TAIL"
        byte 0
slow_text:
        ascii "rotation/scroll interaction check"
        byte 0

; ============================================================
; --- Routines under test ---
; ============================================================

; --- Generic length-parameterized block copy (self-modified addressing,
; same technique as tada-client.asm's copy_1000). Used here for the
; front-buffer-to-back-buffer screen-glyph shift -- no vblank gating at
; all, since the destination (back buffer) is never the one being
; displayed while this runs. ---
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

; --- switch_to_bank3_with_charset ---
; One-time boot setup: copies gothic_charset (our own custom 256-glyph
; charset, {include:}'d below -- see project memory, the "Olde English"
; charset idea) into RAM reachable by VIC bank 3, switches the VIC there,
; and leaves front_hi/HIBASE/VIC_MEMORY_CONTROL all pointing at
; SCREEN_BUF_A. See this file's header comment for the full reasoning
; (why bank 3, why this needs the $01=$30 all-RAM trick at all, the
; SEI/NMI caveat for real-client porting). No ROM-reading step needed --
; unlike a stock-font copy, gothic_charset is an ordinary assembled
; label, already sitting in plain CPU-visible RAM at all times, so this
; only needs ONE $01 banking window (to make the WRITE side -- the RAM
; behind $d000-$d7ff -- visible) around a single copy_block call.
switch_to_bank3_with_charset:
        sei

        ; --- 1. Select VIC bank 3 ---
        lda VIC_BANK_SELECT
        and #%11111100              ; bits 0-1 = 00 -> bank 3 (inverted
        sta VIC_BANK_SELECT          ; encoding -- see this const's comment)

        ; --- 2. Write gothic_charset into the RAM behind $d000-$dfff that
        ; VIC-in-bank-3 will see at its own bank-relative $1000-$17ff ---
        lda $01
        pha
        lda #CHARGEN_RAM_CONFIG
        sta $01
        lda #<gothic_charset
        sta copy_src_lo
        lda #>gothic_charset
        sta copy_src_hi
        lda #<CHARGEN_DEST
        sta copy_dst_lo
        lda #>CHARGEN_DEST
        sta copy_dst_hi
        lda #<CHARGEN_SIZE
        sta copy_remaining_lo
        lda #>CHARGEN_SIZE
        sta copy_remaining_hi
        jsr copy_block
        pla
        sta $01                     ; restore -- must happen before the
                                      ; very next jsr CHROUT et al, which
                                      ; need KERNAL ROM mapped

        ; --- 3. Point the VIC and KERNAL at SCREEN_BUF_A, char-ptr 2 ---
        lda #VIC_D018_INIT
        sta VIC_MEMORY_CONTROL
        lda #>SCREEN_BUF_A
        sta front_hi
        sta HIBASE

        cli
        rts

{include:gothic-charset.asm}

; --- copy_color_chunked ---
; COLOR_RAM's rows 1-22 -> rows 0-21 shift, alone -- the screen-glyph half
; of the old copy_dialogue_block_chunked is gone entirely now (replaced by
; flip_screen_buffer's atomic swap below), so this is the ONLY remaining
; piece that has to touch live, currently-displayed memory a chunk at a
; time. COLOR_RAM has no bank-switchable second copy on real C64 hardware
; -- whatever gets poked here is immediately visible on whatever buffer is
; CURRENTLY the front one, so this still needs the same per-vblank
; chunking test_screen_routines.asm used for both ranges together. Worth
; noting plainly: this means glyph tearing is now structurally impossible
; (flip_screen_buffer is atomic), but color-vs-glyph mismatch during the
; chunked window is still possible in principle, same class of risk as
; before, just confined to color alone. COLOR_CHUNK_BYTES is independently
; tunable now that color isn't sharing its vblank budget with a screen
; copy -- left equal to the old per-range chunk size for a fair first
; comparison, not because it's been proven optimal.
COLOR_CHUNK_BYTES = 220           ; 880 / 4
copy_color_chunked:
        lda #<(COLOR_RAM+ROW_BYTES)
        sta ccc_load+1
        lda #>(COLOR_RAM+ROW_BYTES)
        sta ccc_load+2
        lda #<COLOR_RAM
        sta ccc_store+1
        lda #>COLOR_RAM
        sta ccc_store+2
        lda #<DIALOGUE_SHIFT_BYTES
        sta copy_remaining_lo
        lda #>DIALOGUE_SHIFT_BYTES
        sta copy_remaining_hi
ccc_next_chunk:
        jsr wait_vblank
        lda #COLOR_CHUNK_BYTES
        sta ccc_chunk_remaining
ccc_loop:
ccc_load:
        lda $ffff
ccc_store:
        sta $ffff
        inc ccc_load+1
        bne ccc_src_ok
        inc ccc_load+2
ccc_src_ok:
        inc ccc_store+1
        bne ccc_dst_ok
        inc ccc_store+2
ccc_dst_ok:
        lda copy_remaining_lo
        bne ccc_dec_lo
        dec copy_remaining_hi
ccc_dec_lo:
        dec copy_remaining_lo
        lda copy_remaining_lo
        ora copy_remaining_hi
        beq ccc_done               ; whole 880-byte copy finished
        dec ccc_chunk_remaining
        bne ccc_loop                ; more bytes left in this chunk
        jmp ccc_next_chunk          ; chunk done -- wait for the next vblank
ccc_done:
        rts

ccc_chunk_remaining:
        byte 0

; --- flip_screen_buffer: atomically swap which 1K page the VIC displays ---
; Input: .A = the buffer's ABSOLUTE high byte to make the new front
; (SCREEN_BUF_A's or SCREEN_BUF_B's >, i.e. $c0 or $c4).
; Updates both:
;   - VIC_MEMORY_CONTROL ($d018) bits 4-7, the HARDWARE screen pointer
;     (unit $0400, VALUE RELATIVE TO THE CURRENT VIC BANK -- both buffers
;     are bank-3 slots, so the absolute high byte first gets VIC_BANK_BASE
;     subtracted back out before the shift) -- this is what actually
;     changes what's on the TV/monitor, and takes effect the instant it's
;     written (well, next time the VIC's own internal address latch reads
;     it, effectively immediate). new_nibble = relative_hi >> 2, since
;     relative_hi is always a multiple of 4 for a page that's also
;     1K-aligned; computed via two LSRs then four ASLs (net: clear the
;     bottom 2 bits, then shift into the top nibble) rather than a lookup
;     table, since it's a pure bit-shuffle with no data-dependent
;     branching.
;   - HIBASE ($0288), the KERNAL shadow byte CHROUT/PLOT actually consult
;     to compute where to poke -- without this, term_chrout's own `jsr
;     CHROUT` calls would keep printing into the now-hidden buffer instead
;     of the newly-visible one, invisibly diverging from what's on screen.
;     Set from the ABSOLUTE high byte (a plain CPU-side address, unrelated
;     to VIC bank selection), before the relative subtraction below.
; Existing charset-pointer bits (bits 0-3) are preserved by ANDing them
; back in from the register's current value, not just overwritten.
flip_screen_buffer:
        sta front_hi
        sta HIBASE
        sec
        sbc #>VIC_BANK_BASE          ; .A = bank-3-relative high byte (both
                                       ; buffers are bank-3 slots, not
                                       ; absolute -- the shift below needs
                                       ; the offset FROM $c000, not from $00)
        lsr
        lsr
        asl
        asl
        asl
        asl                         ; .A = (relative_hi >> 2) << 4
        sta flip_d018_val
        lda VIC_MEMORY_CONTROL
        and #$0f                    ; keep charset-pointer bits untouched
        ora flip_d018_val
        sta VIC_MEMORY_CONTROL
        rts

flip_d018_val:
        byte 0
front_hi:
        byte >SCREEN_BUF_A
back_hi:
        byte 0

; --- term_chrout / term_scroll_advance_blit ---
; Same STATUS_ROW-avoidance contract as test_screen_routines.asm's
; term_chrout (see that file's own header comment for the full CR/wrap
; reasoning -- unchanged here, still both reduce to "shift the dialogue
; window, nothing real ever needs to be preserved from STATUS_ROW").
; Preserves the caller's X/Y across the entire call -- same reasoning
; as before.
term_chrout:
        stx term_saved_x
        sty term_saved_y
        jsr CHROUT
        ldx $d6                    ; TBLX -- physical cursor row
        cpx #STATUS_ROW
        bcc term_chrout_rts
        jsr term_scroll_advance_blit
term_chrout_rts:
        ldx term_saved_x
        ldy term_saved_y
        rts

term_saved_x:
        byte 0
term_saved_y:
        byte 0

; --- wait_vblank: busy-wait until the raster beam reaches line 250 ---
; See test_screen_routines.asm's own comment -- unchanged reasoning, just
; now gating copy_color_chunked's chunks only, not a screen+color pair.
wait_vblank:
        lda $d012
        cmp #250
        bne wait_vblank
        rts

; --- term_scroll_advance_blit: the double-buffered replacement for
; test_screen_routines.asm's term_scroll_advance ---
; 1. Prepares the BACK buffer completely off-screen, at leisure: shifts
;    FRONT's rows 1-22 into BACK's rows 0-21 (single atomic copy_block
;    call -- no chunking needed, nobody's watching), blanks BACK's fresh
;    row 22, and stamps BACK's STATUS_ROW with the current queued message
;    (redraw_status_row_to) so the buffer is fully correct before it's
;    ever shown -- otherwise the flip below would reveal a stale or blank
;    status bar for one frame.
; 2. Chunk-shifts COLOR_RAM in place (still live/visible the whole time --
;    see copy_color_chunked's own comment on why this can't be double-
;    buffered too).
; 3. One final wait_vblank, then flips the buffers -- BACK becomes FRONT,
;    the glyph grid changes in one atomic write, and CHROUT/PLOT
;    transparently follow via HIBASE without any further changes needed
;    at call sites.
term_scroll_advance_blit:
        lda front_hi
        cmp #>SCREEN_BUF_A
        beq tsab_back_is_b
        lda #>SCREEN_BUF_A
        jmp tsab_back_known
tsab_back_is_b:
        lda #>SCREEN_BUF_B
tsab_back_known:
        sta back_hi

        ; --- 1a. Shift glyphs: front rows 1-22 -> back rows 0-21 ---
        lda #<ROW_BYTES
        sta copy_src_lo
        lda front_hi
        sta copy_src_hi
        lda #0
        sta copy_dst_lo
        lda back_hi
        sta copy_dst_hi
        lda #<DIALOGUE_SHIFT_BYTES
        sta copy_remaining_lo
        lda #>DIALOGUE_SHIFT_BYTES
        sta copy_remaining_hi
        jsr copy_block

        ; --- 1b. Blank back buffer's fresh row 22 ---
        ; scr_ptr = back_hi:00 + 880 ($0370) -- direct arithmetic instead
        ; of a row_offsets/set_screen_line lookup, since DIALOGUE_LAST_ROW
        ; is a fixed compile-time row here.
        lda #<880
        sta scr_ptr_lo
        lda back_hi
        clc
        adc #>880
        sta scr_ptr_hi
        ldy #0
        lda #$20
tsab_blank:
        sta (scr_ptr_lo),y
        iny
        cpy #40
        bne tsab_blank

        ; --- 1c. Stamp back buffer's STATUS_ROW before it's ever shown ---
        lda back_hi
        jsr redraw_status_row_to

        ; --- 2. Chunk-shift COLOR_RAM (still live the whole time) ---
        jsr copy_color_chunked

        ; --- 3. Flip: back becomes front, atomically ---
        jsr wait_vblank
        lda back_hi
        jsr flip_screen_buffer
        ldx #DIALOGUE_LAST_ROW
        ldy #0
        clc
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

; --- Test-only helper: see test_screen_routines.asm's own comment. ---
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
        jsr redraw_status_row       ; new batch, first message -- paint the
                                      ; CURRENT front buffer immediately
                                      ; (not a scroll-triggered repaint, so
                                      ; there's no "back buffer" involved)
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
        jsr redraw_status_row        ; rotation happens independently of any
                                       ; scroll -- always targets whatever
                                       ; is CURRENTLY the front buffer
        lda $a2
        sta status_rotate_last_lo
        lda $a1
        sta status_rotate_last_hi
        rts

; --- redraw_status_row: repaint the CURRENT FRONT buffer's STATUS_ROW ---
; Thin wrapper over redraw_status_row_to for the common case (every call
; site except the scroll routine's own back-buffer pre-paint doesn't care
; which buffer is front, it just wants "whatever's on screen right now").
redraw_status_row:
        lda front_hi
        ; falls through

; --- redraw_status_row_to: repaint an EXPLICIT buffer's STATUS_ROW ---
; Input: .A = target buffer's high byte.
; Needed because term_scroll_advance_blit must paint the BACK buffer's
; status row (the one about to become front) BEFORE flipping, not
; whichever buffer happens to be front at the moment it's called -- see
; that routine's own comment. Self-modifies only the high byte of each
; STA operand's absolute address (STATUS_ROW_OFFSET's low byte, $98, is
; identical in both buffers since both are 1K-aligned; only the page
; differs) -- target_hi = buffer_hi + 3, since STATUS_ROW_OFFSET (920,
; $0398) contributes high byte $03. Otherwise identical to test_screen_
; routines.asm's redraw_status_row: reverse video, padded to 40 columns,
; pure raw pokes (queue content is pre-encoded real screen codes already).
redraw_status_row_to:
        clc
        adc #>STATUS_ROW_OFFSET
        sta rsrt_store+2
        sta rsrt_pad_store+2
        sta rsrt_blank_store+2
        lda status_queue_count
        beq rsrt_blank
        lda status_queue_read
        jsr status_slot_addr         ; scr_ptr_lo/hi = &status_queue[read]
        ldy #0
rsrt_copy:
        cpy #39
        bcs rsrt_pad
        lda (scr_ptr_lo),y
        beq rsrt_pad
        ora #$80                     ; reverse video -- same $80-bit trick
rsrt_store:
        sta STATUS_ROW_OFFSET,y     ; high byte self-modified above
        iny
        jmp rsrt_copy
rsrt_pad:
        lda #$a0                     ; reverse-video space
rsrt_pad_loop:
        cpy #40
        bcs rsrt_rts
rsrt_pad_store:
        sta STATUS_ROW_OFFSET,y
        iny
        jmp rsrt_pad_loop
rsrt_rts:
        rts
rsrt_blank:
        ldy #0
        lda #$a0
rsrt_blank_loop:
rsrt_blank_store:
        sta STATUS_ROW_OFFSET,y
        iny
        cpy #40
        bne rsrt_blank_loop
        rts

; --- Test fixture messages (see test_screen_routines.asm's own comment
; on {alpha:pokealt} -- unchanged reasoning) ---
{alpha:pokealt}
build_msg:
        ascii "build "
        ascii {usedef:__BuildDate}
        ascii " "
        ascii {usedef:__BuildTime}
        byte 0
msg1:
        ascii "Played $0100 frames"
        byte 0
msg2:
        ascii "Elapsed $000200 jiffies"
        byte 0
msg3:
        ascii "rd=$40 wr=$80"
        byte 0
msg4:
        ascii "Starts=$03"
        byte 0
{alpha:normal}
