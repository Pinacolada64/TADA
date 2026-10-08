; vdc_screen.asm -- client-128.asm's 80-column (VDC) screen: dialogue
; output, the scrollback history, and the scrollback view.
;
; Layout (VDC RAM, 16K -- works on a stock flat 128; the 64K DCR chip
; would just leave more of it unused):
;   $0000-$07cf  screen   (rows 0-22 dialogue, 23 status, 24 input) --
;                the editor's own 80-column screen base ($0A2E = $00),
;                so KERNAL CHROUT/PLOT (input_editor.asm on row 24) and
;                this file draw into the same place
;   $0800-$0fcf  attributes ($0A2F = $08): bit 7 ALT charset (lowercase),
;                6 reverse, 5 underline, 4 blink, 3-0 RGBI color
;   $1000-$172f  scrollback's copy of the live dialogue window (chars)
;   $1800-$1f2f  ...and its attributes
;   $2000-$3fff  character set (INIT80 puts it here)
; Every character address has its attribute exactly $0800 above it, in
; the live screen and the save area alike, so "+$08 to the high byte"
; turns any character address here into its attribute address.
;
; Dialogue output doesn't go through CHROUT at all: dlg_putc keeps its own
; row/column and writes the VDC directly, and scrolls rows 1-22 up with
; one VDC block copy (plus one for the attributes) -- the chip moves the
; 1760 bytes itself, same mechanism as the editor's line mover ($C40D),
; without the editor's one-line-at-a-time loop. Rows 23/24 are never
; touched by a dialogue scroll, so no ESC-T/ESC-B window is needed in 80
; columns at all (the 40-column path still uses one).
;
; History: every row that scrolls off the top of the dialogue window (and
; every used row when the server clears it) is read back out of VDC RAM
; into a ring of HIST_LINES rows in main RAM, characters and attributes
; both, so colors survive scrollback. The ring lives in bank 0 under the
; BASIC ROMs ($6800-$bfbf), reached with $FF00 = $0e (I/O and KERNAL
; still in, BASIC out -- Compute's 128 Programmer's Guide Figure 7-5).
; client-128.asm has run with that configuration throughout since the
; Keymap Editor moved in (MMU_CLIENT_CONFIG); the copy loops below still
; set it themselves and put back whatever they found, which costs nothing
; and keeps them correct if they're ever called with ROMs in. This code
; sits below $4000, so it stays visible either way, and the KERNAL IRQ
; saves/restores $FF00 around itself, so interrupts stay on throughout.
;
; Scrollback view: the first scroll-back key block-copies the live window
; into the save area; the view is then drawn from history rows (CPU
; copies from the ring) and saved live rows (VDC block copies). Moving one
; line shifts the window by block copy and draws only the one new row;
; paging redraws all 23. Leaving scrollback copies the saved window back.
; Any dialogue output leaves scrollback first, so nothing is ever drawn
; into a scrolled-back view.

VDC_COLS           = 80
DLG_ROWS           = 23          ; dialogue rows 0-22
DLG_LAST_ROW       = 22
DLG_BYTES          = 1840        ; DLG_ROWS * VDC_COLS
DLG_SCROLL_BYTES   = 1760        ; DLG_LAST_ROW * VDC_COLS
VDC_SCREEN_BYTES   = 2000        ; 25 * VDC_COLS
VDC_STATUS_ROW     = 23          ; client-128.asm's STATUS_ROW
VDC_ATTR_HI        = $08         ; attribute = character address + $0800
LIVE_SAVE_HI       = $10         ; save area = live address + $1000

HIST_LINES         = 140         ; rows of history (140 * 80 = 11200 bytes each
HIST_CHARS_HI      = $68         ; for chars at $6800-$93bf and attributes
HIST_ATTR_HI       = $2c         ; $2c00 above them, $9400-$bfbf). Was 200
                                 ; rows at $4000 until the built-in Keymap
                                 ; Editor pushed the program past $4000,
                                 ; then 150 at $6000 (attributes $3000
                                 ; above) until the Video Settings popup
                                 ; (video_menu_128.asm, 2026-10-05) pushed
                                 ; it past $6000; the code must now end
                                 ; below $6800 (check_128_layout.py)
MMU_CR             = $ff00
MMU_HIST_CONFIG    = $0e         ; bank 0 RAM $4000-$bfff, I/O, KERNAL ROM
SB_PAGE            = 20          ; lines per Page Up/Page Down

; --- vdc_screen_init: hardware cursor off (input_editor.asm draws its
; own), take the editor's current attribute as the dialogue default, and
; clear all 25 rows. ---
vdc_screen_init:
        ldx #VDC_R_CURSOR_MODE
        lda #VDC_CURSOR_OFF
        jsr vdc_write_reg
        lda $f1                 ; editor's current attribute -- in 80
        and #$8f                ; columns a VDC attribute byte. Keep ALT +
        sta dlg_attr            ; color, drop blink/underline/reverse --
        sta dlg_base_attr       ; the same mask the editor uses ($C529)
        lda #0
        sta dlg_row
        sta dlg_col
        sta dlg_rvs
        sta hist_head
        sta hist_count
        sta sb_offset
        sta vdc_dst
        sta vdc_dst+1
        lda #<VDC_SCREEN_BYTES
        sta vdc_count
        lda #>VDC_SCREEN_BYTES
        sta vdc_count+1
        lda #' '
        jsr vdc_fill
        lda #VDC_ATTR_HI
        sta vdc_dst+1
        lda #<VDC_SCREEN_BYTES
        sta vdc_count
        lda #>VDC_SCREEN_BYTES
        sta vdc_count+1
        lda dlg_attr
        jmp vdc_fill

; --- vdc_rowcol: X = row, Y = column -> A = high, Y = low byte of that
; cell's character address. Preserves X; carry clear on return. ---
vdc_rowcol:
        tya
        clc
        adc vdc_row_lo,x
        tay
        lda vdc_row_hi,x
        adc #0
        rts

; --- dlg_putc: .A = one PETSCII byte for the dialogue window. Preserves
; X and Y (callers loop with them, same as around CHROUT). Handles CR,
; RVS on/off, CLR, HOME and the 16 color codes; other control codes are
; ignored. Wrapping is deferred: a character in column 79 leaves the
; cursor "past the edge", and only the next printable character moves to
; a new row -- so a server line of exactly 80 characters followed by CR
; doesn't leave a blank row behind it. ---
dlg_putc:
        stx dlg_saved_x
        sty dlg_saved_y
        pha
        jsr sb_exit             ; output always lands in the live view
        pla
        jsr dlg_putc_body
        ldx dlg_saved_x
        ldy dlg_saved_y
        rts

; The control-code dispatch uses bne-over-jmp throughout: a plain beq to
; dlg_cr came out 143 bytes away, and c64list assembled it silently into
; a branch to garbage (caught by disassembling the .prg).
dlg_putc_body:
        cmp #13
        bne dlg_not_cr
        jmp dlg_cr
dlg_not_cr:
        cmp #$12
        bne dlg_not_rvs_on
        jmp dlg_rvs_on
dlg_not_rvs_on:
        cmp #$92
        bne dlg_not_rvs_off
        jmp dlg_rvs_off
dlg_not_rvs_off:
        cmp #$13
        bne dlg_not_home
        jmp dlg_home
dlg_not_home:
        cmp #$93
        bne dlg_not_clear
        jmp dlg_clear
dlg_not_clear:
        ldx #15
dlg_color_scan:
        cmp dlg_color_codes,x
        beq dlg_set_color
        dex
        bpl dlg_color_scan
        cmp #$20
        bcc dlg_ignore          ; $00-$1f: other control codes
        cmp #$80
        bcc dlg_printable
        cmp #$a0
        bcc dlg_ignore          ; $80-$9f: other control codes
dlg_printable:
        jsr petscii_to_screen
        ldx dlg_rvs
        beq dlg_have_char
        ora #$80                ; reverse glyph, same as the 40-column screen
dlg_have_char:
        sta dlg_char
        lda dlg_col
        cmp #VDC_COLS
        bcc dlg_write
        jsr dlg_newline         ; deferred wrap, see above
dlg_write:
        ldx dlg_row
        ldy dlg_col
        jsr vdc_rowcol
        sta dlg_addr_hi
        sty dlg_addr_lo
        jsr vdc_set_update
        lda dlg_char
        jsr vdc_put
        lda dlg_addr_hi
        clc
        adc #VDC_ATTR_HI
        ldy dlg_addr_lo
        jsr vdc_set_update
        lda dlg_attr
        jsr vdc_put
        inc dlg_col
dlg_ignore:
        rts

dlg_set_color:
        lda dlg_attr
        and #$f0
        ora dlg_vdc_colors,x
        sta dlg_attr
        rts

dlg_rvs_on:
        lda #1
        sta dlg_rvs
        rts

dlg_rvs_off:
        lda #0
        sta dlg_rvs
        rts

dlg_home:
        lda #0
        sta dlg_row
        sta dlg_col
        rts

dlg_cr:
        lda #0                  ; CR ends reverse, as on the C64/128 screen
        sta dlg_rvs             ; editors
        ; fall through

; --- dlg_newline: column 0 of the next row, scrolling the window (and
; saving its top row to history) from the bottom row. ---
dlg_newline:
        lda #0
        sta dlg_col
        lda dlg_row
        cmp #DLG_LAST_ROW
        bcs dlg_scroll
        inc dlg_row
        rts
dlg_scroll:
        ldx #0
        jsr hist_push_row
        jsr dlg_rows_up
        ldx #DLG_LAST_ROW
        jmp dlg_blank_row

; --- dlg_rows_up: block-copy dialogue rows 1-22 to 0-21 (characters,
; then attributes). Row 22 is left as it was. ---
dlg_rows_up:
        lda #VDC_COLS
        sta vdc_src
        lda #0
        sta vdc_src+1
        sta vdc_dst
        sta vdc_dst+1
        lda #<DLG_SCROLL_BYTES
        ldy #>DLG_SCROLL_BYTES
        jmp vdc_copy_pair

; --- dlg_blank_row: X = row -> spaces in the current color. ---
dlg_blank_row:
        ldy #0
        jsr vdc_rowcol
        sta vdc_dst+1
        sty vdc_dst
        lda #' '
        ldx dlg_attr
        ldy #VDC_COLS
        jmp vdc_fill_pair

; --- dlg_clear (CLR from the server): save every row in use to history
; first, so a clear doesn't throw text away, then blank the window and
; home the cursor. ---
dlg_clear:
        lda dlg_row             ; rows 0..dlg_row are in use -- or only
        ldx dlg_col             ; 0..dlg_row-1 when the cursor sits at the
        beq dlg_clear_limit     ; start of an empty row
        clc
        adc #1
dlg_clear_limit:
        sta dlg_clear_end
        lda #0
        sta dlg_clear_row
dlg_clear_push:
        ldx dlg_clear_row
        cpx dlg_clear_end
        bcs dlg_clear_blank
        jsr hist_push_row
        inc dlg_clear_row
        jmp dlg_clear_push
dlg_clear_blank:
        lda #0
        sta vdc_dst
        sta vdc_dst+1
        sta dlg_row
        sta dlg_col
        lda #' '
        ldx dlg_attr
        ldy #>DLG_BYTES
        sty vdc_pair_count+1
        ldy #<DLG_BYTES
        jmp vdc_fill_pair_long

; --- vdc_copy_pair: A/Y = count (low/high). Block-copies that many
; characters from vdc_src to vdc_dst, then the same span of attributes
; ($0800 above both). vdc_src/vdc_dst end up at the attribute addresses. ---
vdc_copy_pair:
        sta vdc_pair_count
        sty vdc_pair_count+1
        sta vdc_count
        sty vdc_count+1
        jsr vdc_copy
        clc
        lda vdc_src+1
        adc #VDC_ATTR_HI
        sta vdc_src+1
        clc
        lda vdc_dst+1
        adc #VDC_ATTR_HI
        sta vdc_dst+1
        lda vdc_pair_count
        sta vdc_count
        lda vdc_pair_count+1
        sta vdc_count+1
        jmp vdc_copy

; --- vdc_fill_pair: fill Y (1-255) characters at vdc_dst with A and
; their attributes with X. vdc_fill_pair_long: same, but the count is Y
; (low) + vdc_pair_count+1 (high, set by the caller). ---
vdc_fill_pair:
        pha
        lda #0
        sta vdc_pair_count+1
        pla
vdc_fill_pair_long:
        sty vdc_pair_count
        stx vdc_pair_attr
        sty vdc_count
        ldy vdc_pair_count+1
        sty vdc_count+1
        jsr vdc_fill
        clc
        lda vdc_dst+1
        adc #VDC_ATTR_HI
        sta vdc_dst+1
        lda vdc_pair_count
        sta vdc_count
        lda vdc_pair_count+1
        sta vdc_count+1
        lda vdc_pair_attr
        jmp vdc_fill

; --- hist_push_row: X = VDC row. Reads its 80 characters and 80
; attributes back out of VDC RAM into the next history slot. ---
hist_push_row:
        stx hist_row
        lda hist_head
        jsr hist_slot_addr
        lda hist_addr
        sta hist_w_chr+1
        sta hist_w_attr+1
        lda hist_addr+1
        sta hist_w_chr+2
        clc
        adc #HIST_ATTR_HI
        sta hist_w_attr+2
        lda MMU_CR
        sta hist_saved_mmu
        lda #MMU_HIST_CONFIG
        sta MMU_CR

        ldx hist_row
        ldy #0
        jsr vdc_rowcol
        jsr vdc_set_update
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy #0
hist_push_chr:
        bit VDC_ADDR_REG
        bpl hist_push_chr
        lda VDC_DATA_REG
hist_w_chr:
        sta $ffff,y             ; self-modified: this slot's characters
        iny
        cpy #VDC_COLS
        bne hist_push_chr

        ldx hist_row
        ldy #0
        jsr vdc_rowcol
        adc #VDC_ATTR_HI        ; carry clear from vdc_rowcol
        jsr vdc_set_update
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy #0
hist_push_attr:
        bit VDC_ADDR_REG
        bpl hist_push_attr
        lda VDC_DATA_REG
hist_w_attr:
        sta $ffff,y             ; self-modified: this slot's attributes
        iny
        cpy #VDC_COLS
        bne hist_push_attr

        lda hist_saved_mmu
        sta MMU_CR
        inc hist_head
        lda hist_head
        cmp #HIST_LINES
        bcc hist_push_count
        lda #0
        sta hist_head
hist_push_count:
        lda hist_count
        cmp #HIST_LINES
        bcs hist_push_rts       ; full: the oldest row was just overwritten
        inc hist_count
hist_push_rts:
        rts

; --- hist_slot_addr: A = ring slot (0 to HIST_LINES-1) -> hist_addr =
; its character address, HIST_CHARS_HI*256 + slot*80 (slot*16 +
; slot*64). ---
hist_slot_addr:
        sta hist_addr
        lda #0
        sta hist_addr+1
        asl hist_addr
        rol hist_addr+1
        asl hist_addr
        rol hist_addr+1
        asl hist_addr
        rol hist_addr+1
        asl hist_addr
        rol hist_addr+1         ; *16
        lda hist_addr
        sta hist_x16
        lda hist_addr+1
        sta hist_x16+1
        asl hist_addr
        rol hist_addr+1
        asl hist_addr
        rol hist_addr+1         ; *64
        clc
        lda hist_addr
        adc hist_x16
        sta hist_addr
        lda hist_addr+1
        adc hist_x16+1          ; *80, at most 15920 -- no carry out
        adc #HIST_CHARS_HI
        sta hist_addr+1
        rts

; --- hist_age_slot: A = age (1 = newest row in history) -> A = its ring
; slot. ---
hist_age_slot:
        sta hist_tmp
        lda hist_head
        sec
        sbc hist_tmp
        bcs hist_age_rts
        adc #HIST_LINES         ; borrowed: carry is clear, wrap around
hist_age_rts:
        rts

; --- sb_draw_hist_row: X = window row, A = age -> that history row drawn
; there (CPU copy, 160 VDC writes). ---
sb_draw_hist_row:
        stx sb_row
        jsr hist_age_slot
        jsr hist_slot_addr
        lda hist_addr
        sta hist_r_chr+1
        sta hist_r_attr+1
        lda hist_addr+1
        sta hist_r_chr+2
        clc
        adc #HIST_ATTR_HI
        sta hist_r_attr+2
        lda MMU_CR
        sta hist_saved_mmu
        lda #MMU_HIST_CONFIG
        sta MMU_CR

        ldx sb_row
        ldy #0
        jsr vdc_rowcol
        jsr vdc_set_update
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy #0
hist_r_chr:
        lda $ffff,y             ; self-modified: this slot's characters
sb_hist_chr_wait:
        bit VDC_ADDR_REG
        bpl sb_hist_chr_wait
        sta VDC_DATA_REG
        iny
        cpy #VDC_COLS
        bne hist_r_chr

        ldx sb_row
        ldy #0
        jsr vdc_rowcol
        adc #VDC_ATTR_HI        ; carry clear from vdc_rowcol
        jsr vdc_set_update
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy #0
hist_r_attr:
        lda $ffff,y             ; self-modified: this slot's attributes
sb_hist_attr_wait:
        bit VDC_ADDR_REG
        bpl sb_hist_attr_wait
        sta VDC_DATA_REG
        iny
        cpy #VDC_COLS
        bne hist_r_attr

        lda hist_saved_mmu
        sta MMU_CR
        rts

; --- sb_draw_live_row: X = window row, A = row of the saved live window
; -> block-copied there from the save area. ---
sb_draw_live_row:
        stx sb_row
        tax
        lda vdc_row_lo,x
        sta vdc_src
        lda vdc_row_hi,x
        clc
        adc #LIVE_SAVE_HI
        sta vdc_src+1
        ldx sb_row
        lda vdc_row_lo,x
        sta vdc_dst
        lda vdc_row_hi,x
        sta vdc_dst+1
        lda #VDC_COLS
        ldy #0
        jmp vdc_copy_pair

; --- sb_render_row: X = window row -> whatever the current scrollback
; offset puts there. Rows above the offset are history (age = offset -
; row); the rest are saved live rows (row - offset). ---
sb_render_row:
        cpx sb_offset
        bcs sb_render_live
        stx sb_tmp
        lda sb_offset
        sec
        sbc sb_tmp
        jmp sb_draw_hist_row
sb_render_live:
        stx sb_tmp
        txa
        sec
        sbc sb_offset
        ldx sb_tmp
        jmp sb_draw_live_row

sb_redraw:
        lda #0
        sta sb_loop
sb_redraw_loop:
        ldx sb_loop
        jsr sb_render_row
        inc sb_loop
        lda sb_loop
        cmp #DLG_ROWS
        bcc sb_redraw_loop
        rts

; --- sb_save_live / sb_restore_live: the whole dialogue window to/from
; the save area, one block copy each for characters and attributes. ---
sb_save_live:
        lda #0
        sta vdc_src
        sta vdc_src+1
        sta vdc_dst
        lda #LIVE_SAVE_HI
        sta vdc_dst+1
        jmp sb_copy_window

sb_restore_live:
        lda #0
        sta vdc_src
        sta vdc_dst
        sta vdc_dst+1
        lda #LIVE_SAVE_HI
        sta vdc_src+1
sb_copy_window:
        lda #<DLG_BYTES
        ldy #>DLG_BYTES
        jmp vdc_copy_pair

; --- sb_shift_down: window rows 0-21 -> 1-22, a row at a time from the
; bottom (a block copy only runs upward through memory, so one big copy
; down over itself would smear row 0 everywhere). ---
sb_shift_down:
        lda #DLG_LAST_ROW-1
        sta sb_loop
sb_shift_loop:
        ldx sb_loop
        lda vdc_row_lo,x
        sta vdc_src
        lda vdc_row_hi,x
        sta vdc_src+1
        lda vdc_row_lo+1,x
        sta vdc_dst
        lda vdc_row_hi+1,x
        sta vdc_dst+1
        lda #VDC_COLS
        ldy #0
        jsr vdc_copy_pair
        dec sb_loop
        bpl sb_shift_loop
        rts

; --- sb_exit and the four scrollback moves. Each redraws the status row,
; which shows the position while scrolled back (see draw_status_row).
; Every early-out has its own rts right there -- c64list doesn't check
; branch range, and these routines are long enough that one shared rts
; would drift out of reach. ---
sb_exit:
        lda sb_offset
        bne sb_exit_now
        rts
sb_exit_now:
        lda #0
        sta sb_offset
sb_back_to_live:
        jsr sb_restore_live
        jmp draw_status_row

sb_line_back:
        lda sb_offset
        cmp hist_count
        bcc sb_line_back_ok
        rts                     ; already at the oldest row
sb_line_back_ok:
        lda sb_offset
        bne sb_line_back_move
        jsr sb_save_live
sb_line_back_move:
        inc sb_offset
        jsr sb_shift_down
        ldx #0
        jsr sb_render_row
        jmp draw_status_row

sb_line_fwd:
        lda sb_offset
        bne sb_line_fwd_ok
        rts
sb_line_fwd_ok:
        dec sb_offset
        bne sb_line_fwd_move
        jmp sb_back_to_live
sb_line_fwd_move:
        jsr dlg_rows_up
        ldx #DLG_LAST_ROW
        jsr sb_render_row
        jmp draw_status_row

sb_page_back:
        lda hist_count
        bne sb_page_back_ok
        rts
sb_page_back_ok:
        lda sb_offset
        bne sb_page_back_move
        jsr sb_save_live
sb_page_back_move:
        lda sb_offset
        clc
        adc #SB_PAGE
        bcs sb_page_back_clamp
        cmp hist_count
        bcc sb_page_back_set
sb_page_back_clamp:
        lda hist_count
sb_page_back_set:
        sta sb_offset
        jsr sb_redraw
        jmp draw_status_row

sb_page_fwd:
        lda sb_offset
        bne sb_page_fwd_ok
        rts
sb_page_fwd_ok:
        sec
        sbc #SB_PAGE
        bcs sb_page_fwd_set
        lda #0
sb_page_fwd_set:
        sta sb_offset
        lda sb_offset
        bne sb_page_fwd_move
        jmp sb_back_to_live
sb_page_fwd_move:
        jsr sb_redraw
        jmp draw_status_row

; --- vdc_key_hook: client-128.asm's editor_key_hook hands it plain (or
; SHIFTed) CRSR UP/DOWN in 80 columns: scroll back / forward a line.
; Always consumes the key (carry set). Paging used to be hardwired here
; too (C= + CRSR); since 2026-09-29 it's the keymap's Page Up/Page Down
; (keymap_128.asm, ALT + the grey arrows by default), so it can be
; rebound. ---
vdc_key_hook:
        cmp #$91
        bne vdc_key_down
        jsr sb_line_back
        sec
        rts
vdc_key_down:
        jsr sb_line_fwd
        sec
        rts

; --- vdc_draw_status_line: client-128.asm's status_line buffer (80
; screen codes) to row 23, attributes in the default color. ---
vdc_draw_status_line:
        ldx #VDC_STATUS_ROW
        ldy #0
        jsr vdc_rowcol
        sta vdc_dst+1
        sty vdc_dst
        jsr vdc_set_update
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy #0
vdc_status_loop:
        lda status_line,y
vdc_status_wait:
        bit VDC_ADDR_REG
        bpl vdc_status_wait
        sta VDC_DATA_REG
        iny
        cpy #VDC_COLS
        bne vdc_status_loop
        clc
        lda vdc_dst+1
        adc #VDC_ATTR_HI
        sta vdc_dst+1
        lda #VDC_COLS
        sta vdc_count
        lda #0
        sta vdc_count+1
        lda dlg_base_attr
        jmp vdc_fill

; --- sb_status_text: builds the scrollback position message (screen
; codes, 0-terminated) into sb_status_buf; returns A/Y = its address.
; The page keys are looked up in the keymap (keymap_128.asm's slots 15-
; 16) and named the way the Keymap Editor names them, so the message
; follows a rebinding -- "Scrollback: 001 of 043 -- CRSR: a line, Alt+
; Grey Up/Alt+Grey Down: a page" with the defaults. ---
sb_status_text:
        ldx #0
        lda #<sb_msg_pos
        ldy #>sb_msg_pos
        jsr sb_append
        lda sb_offset
        jsr sb_append_dec3
        lda #<sb_msg_of
        ldy #>sb_msg_of
        jsr sb_append
        lda hist_count
        jsr sb_append_dec3
        lda #<sb_msg_keys
        ldy #>sb_msg_keys
        jsr sb_append
        lda keymap_table+KM_PAGE_SLOT_OFFSET
        ldy keymap_table+KM_PAGE_SLOT_OFFSET+1
        jsr sb_append_page_key
        lda #<sb_msg_slash
        ldy #>sb_msg_slash
        jsr sb_append
        lda keymap_table+KM_PAGE_SLOT_OFFSET+BINDING_SIZE
        ldy keymap_table+KM_PAGE_SLOT_OFFSET+BINDING_SIZE+1
        jsr sb_append_page_key
        lda #<sb_msg_page
        ldy #>sb_msg_page
        jsr sb_append
        lda #0
        sta sb_status_buf,x
        lda #<sb_status_buf
        ldy #>sb_status_buf
        rts

; A/Y = 0-terminated string, appended to sb_status_buf at X (X advances).
; Stops at VDC_COLS characters whatever the pieces add up to: the first
; version of the message ran 82 characters into this 81-byte buffer and
; overwrote irq_orig (the next thing in memory), so the next IRQ jumped
; into zeroed RAM -- a screen full of "break" from the 128's monitor on
; the first CRSR UP (found live by Ryan, 2026-09-29).
sb_append:
        sta sb_append_read+1
        sty sb_append_read+2
        ldy #0
sb_append_read:
        lda $ffff,y             ; self-modified
        beq sb_append_rts
        cpx #VDC_COLS
        bcs sb_append_rts
        sta sb_status_buf,x
        inx
        iny
        jmp sb_append_read
sb_append_rts:
        rts

; .A = a page slot's modifier bits, .Y = its matrix key number -> the
; combo's name (screen codes) appended to sb_status_buf at X (X
; advances, capped like sb_append); "none" if nothing is bound. Same
; steps as client-128.asm's out_page_key, through the Keymap Editor's
; describe_combo -- which borrows scr_ptr_lo/hi, the input editor's
; strptr ($fb/$fc). This runs while a line is being typed (scrolling
; back is done mid-line), so those two bytes are put back afterwards.
sb_append_page_key:
        stx sb_pk_index
        sta list_trigger_mod
        cpy #KM_KEY_NONE
        bcs sb_page_key_none
        tya
        ora list_trigger_mod
        beq sb_page_key_none        ; mod = key = 0: nothing captured
        lda key_num_unshifted,y
        sta list_trigger_key
        lda scr_ptr_lo
        pha
        lda scr_ptr_hi
        pha
        lda #<list_trigger_mod
        sta scr_ptr_lo
        lda #>list_trigger_mod
        sta scr_ptr_hi
        jsr describe_combo          ; screen codes at row_scratch+15
        pla
        sta scr_ptr_hi
        pla
        sta scr_ptr_lo
        ldx sb_pk_index
        ldy #0
sb_page_key_copy:
        cpy describe_combo_col
        beq sb_page_key_rts
        cpx #VDC_COLS
        bcs sb_page_key_rts
        lda row_scratch+15,y
        sta sb_status_buf,x
        inx
        iny
        jmp sb_page_key_copy
sb_page_key_none:
        ldx sb_pk_index
        lda #<sb_msg_none
        ldy #>sb_msg_none
        jmp sb_append
sb_page_key_rts:
        rts

sb_pk_index:
        byte 0

; A = 0-255 -> three digits appended to sb_status_buf at X (only ever
; early in the message, so always in bounds; the buffer's slack covers it
; regardless).
sb_append_dec3:
        jsr dec3
        lda dec3_buf
        sta sb_status_buf,x
        lda dec3_buf+1
        sta sb_status_buf+1,x
        lda dec3_buf+2
        sta sb_status_buf+2,x
        inx
        inx
        inx
        rts

; --- Tables ---

; Row start addresses, row * 80, rows 0-24.
vdc_row_lo:
        byte $00,$50,$a0,$f0,$40,$90,$e0,$30,$80,$d0,$20,$70,$c0
        byte $10,$60,$b0,$00,$50,$a0,$f0,$40,$90,$e0,$30,$80
vdc_row_hi:
        byte $00,$00,$00,$00,$01,$01,$01,$02,$02,$02,$03,$03,$03
        byte $04,$04,$04,$05,$05,$05,$05,$06,$06,$06,$07,$07

; PETSCII color codes in VIC-II color order (black, white, red, cyan,
; purple, green, blue, yellow, orange, brown, light red, dark grey, grey,
; light green, light blue, light grey) and the VDC RGBI color the editor
; shows for each in 80 columns -- both tables read out of kernal-318020-
; 05.bin: $CE4C and $CE5C, the pair the editor itself indexes at
; $C7DC/$C7F0 (see 128_CLIENT_MECHANICS.md).
dlg_color_codes:
        byte $90,$05,$1c,$9f,$9c,$1e,$1f,$9e,$81,$95,$96,$97,$98,$99,$9a,$9b
dlg_vdc_colors:
        byte $00,$0f,$08,$07,$0b,$04,$02,$0d,$0a,$0c,$09,$06,$01,$05,$03,$0e

; Scrollback status message pieces -- raw screen codes, drawn straight
; into VDC RAM, same convention as client-128.asm's status_msg.
{alpha:pokealt}
sb_msg_pos:
        ascii "Scrollback: "
        byte 0
sb_msg_of:
        ascii " of "
        byte 0
sb_msg_keys:
        ascii " -- CRSR: a line, "
        byte 0
sb_msg_slash:
        ascii "/"
        byte 0
sb_msg_page:
        ascii ": a page"
        byte 0
sb_msg_none:
        ascii "none"
        byte 0
{alpha:normal}

; --- Variables ---
dlg_row:          byte 0
dlg_col:          byte 0        ; 80 = past the right edge (deferred wrap)
dlg_attr:         byte 0        ; current attribute (color + ALT)
dlg_base_attr:    byte 0        ; attribute at startup (status row, defaults)
dlg_rvs:          byte 0
dlg_char:         byte 0
dlg_addr_lo:      byte 0
dlg_addr_hi:      byte 0
dlg_saved_x:      byte 0
dlg_saved_y:      byte 0
dlg_clear_row:    byte 0
dlg_clear_end:    byte 0
vdc_pair_count:   word 0
vdc_pair_attr:    byte 0
hist_head:        byte 0        ; ring slot the next row goes into
hist_count:       byte 0        ; rows held, 0 to HIST_LINES
hist_row:         byte 0
hist_addr:        word 0
hist_x16:         word 0
hist_tmp:         byte 0
hist_saved_mmu:   byte 0
sb_offset:        byte 0        ; rows scrolled back; 0 = live view
sb_row:           byte 0
sb_tmp:           byte 0
sb_loop:          byte 0
sb_status_buf:
        area VDC_COLS+4, 0      ; VDC_COLS + terminator + dec3 slack
