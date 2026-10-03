; vic_screen.asm -- client-128.asm's 40-column (VIC-II) dialogue output,
; with a scrollback history kept in VDC RAM (Ryan's ask, 2026-10-01).
;
; The 40-column path used to print dialogue through KERNAL CHROUT inside
; an ESC-T/ESC-B window, so the editor did the scrolling and a row that
; left the top of the window was simply gone -- nothing to hook. Now it
; works like vdc_screen.asm's 80-column path: vic_putc keeps its own row,
; column and color, writes SCREEN_RAM and color RAM directly, and scrolls
; rows 1-22 up itself, saving row 0 to the history first. The KERNAL
; window stays the full screen (only input_editor.asm's PLOT/CHROUT on
; the input row still goes through the editor). The control codes
; handled, the deferred wrap and the scrollback keys all match
; vdc_screen.asm's.
;
; The history: in 40 columns the VDC isn't on screen, so its RAM is free
; storage. A row is 80 bytes there -- 40 screen codes, then 40 colors --
; half an 80-column row's 160, so the same RAM holds twice the rows.
; How much RAM there is comes from vdc_detect_ram (vdc.asm, Fred's
; program):
;   64K  R28 stays in 64K addressing for the session; $0000-$3FFF keep
;        the VDC's own screen, attributes and font (DLCHR again, blank
;        screen), so an 80-column monitor left plugged in shows a clean
;        empty screen. Save area $1000-$172F (the 80-column path's own
;        LIVE_SAVE spot), history $4000-$FFFF: VSB_LINES_64K rows.
;   16K  only $1000-$1FFF is spare beside the screen and font -- 28 rows
;        after the save area -- so this takes all of it: save area
;        $0000-$072F, history $0800-$3FFF, VSB_LINES_16K rows. The VDC's
;        80-column display is garbage from then on (nobody's watching it
;        in 40-column mode; it comes back at the next reset).
; Counts run past 255 here, so the ring position, count and scrollback
; offset are words, unlike vdc_screen.asm's bytes.
;
; Scrollback view: the first scroll-back key copies the live window
; (rows 0-22) into the VDC save area; every move then redraws all 23
; rows from VDC RAM -- history rows from the ring, the rest from the
; saved window (1840 VDC reads, a few hundredths of a second). Leaving
; scrollback copies the saved window back. Output, and any key but the
; scrollback ones, leave it first, as in 80 columns.
;
; Everything here runs in mainline only (no interrupt reaches it), so it
; sits above $4000 with the Keymap Editor; vdc_detect_ram is the one
; piece that has to stay low (its DLCHR call runs with BASIC's ROMs in).

VIC_COLS        = 40
VIC_SCR         = $0400          ; SCREEN_RAM -- spelled out for the
VIC_CLR         = $d800          ; +offset operands below
VIC_CLR_DELTA   = $d4            ; color RAM high byte = screen's + $d4
VIC_ROW_BYTES2  = 80             ; one row in VDC RAM: chars, then colors
VIC_SCROLL_TAIL = 112            ; 880 - 3*256: rows 1-22 -> 0-21 is three
                                 ; full pages and 112 bytes
VIC_DLG_CELLS   = 920            ; DLG_ROWS * VIC_COLS

VSB_LINES_64K   = 614            ; ($10000 - $4000) / 80
VSB_HIST_HI_64K = $40
VSB_SAVE_HI_64K = $10
VSB_LINES_16K   = 179            ; ($4000 - $0800) / 80
VSB_HIST_HI_16K = $08
VSB_SAVE_HI_16K = $00

; --- vic_screen_init: size the history from the VDC's RAM, set the VDC
; up for it, and start an empty dialogue at the top left in the editor's
; current color. The screen itself is cleared by init_window. ---
vic_screen_init:
        jsr vdc_detect_ram
        bcc vic_init_16k
        lda #<VSB_LINES_64K
        sta vsb_limit
        lda #>VSB_LINES_64K
        sta vsb_limit+1
        lda #VSB_HIST_HI_64K
        sta vsb_hist_hi
        lda #VSB_SAVE_HI_64K
        sta vsb_save_hi
        ; 64K addressing from here on -- it reshuffles what the 16K
        ; layout left in VDC RAM, so the font goes back in and the
        ; screen and attributes get blanked.
        ldx #VDC_R_RAM_CONFIG
        jsr vdc_read_reg
        ora #VDC_RAM_64K_BIT
        jsr vdc_write_reg
        jsr vdc_dlchr
        lda #0
        sta vdc_dst
        sta vdc_dst+1
        lda #' '
        ldx #0                  ; black on black
        ldy #>VDC_SCREEN_BYTES
        sty vdc_pair_count+1
        ldy #<VDC_SCREEN_BYTES
        jsr vdc_fill_pair_long
        jmp vic_init_state
vic_init_16k:
        lda #<VSB_LINES_16K
        sta vsb_limit
        lda #>VSB_LINES_16K
        sta vsb_limit+1
        lda #VSB_HIST_HI_16K
        sta vsb_hist_hi
        lda #VSB_SAVE_HI_16K
        sta vsb_save_hi
vic_init_state:
        lda $f1                 ; KERNAL_COLOR -- the editor's current color
        and #$0f
        sta vdlg_color
        lda #0
        sta vdlg_row
        sta vdlg_col
        sta vdlg_rvs
        sta vsb_head
        sta vsb_head+1
        sta vsb_count
        sta vsb_count+1
        sta vsb_offset
        sta vsb_offset+1
        rts


; --- vic_row_ptrs: X = row -> every self-modified screen/color RAM
; operand below pointed at that row (vic_putc's write, vic_blank_row,
; and the two VDC copies). Preserves X and Y. ---
vic_row_ptrs:
        lda vic_row_lo,x
        sta vic_w_chr+1
        sta vic_w_clr+1
        sta vic_b_chr+1
        sta vic_b_clr+1
        sta vic_r_chr+1
        sta vic_r_clr+1
        sta vic_s_chr+1
        sta vic_s_clr+1
        lda vic_row_hi,x
        sta vic_w_chr+2
        sta vic_b_chr+2
        sta vic_r_chr+2
        sta vic_s_chr+2
        clc
        adc #VIC_CLR_DELTA
        sta vic_w_clr+2
        sta vic_b_clr+2
        sta vic_r_clr+2
        sta vic_s_clr+2
        rts

; --- vic_putc: .A = one PETSCII byte for the dialogue window. Preserves
; X and Y. Same handling as vdc_screen.asm's dlg_putc: CR, RVS on/off,
; CLR, HOME and the 16 color codes; other control codes are ignored;
; wrapping is deferred past column 39. ---
vic_putc:
        stx vdlg_saved_x
        sty vdlg_saved_y
        pha
        jsr vsb_exit            ; output always lands in the live view
        pla
        jsr vic_putc_body
        ldx vdlg_saved_x
        ldy vdlg_saved_y
        rts

; bne-over-jmp throughout, as in dlg_putc_body (c64list doesn't check
; branch range).
vic_putc_body:
        cmp #13
        bne vic_not_cr
        jmp vic_cr
vic_not_cr:
        cmp #$12
        bne vic_not_rvs_on
        lda #1
        sta vdlg_rvs
        rts
vic_not_rvs_on:
        cmp #$92
        bne vic_not_rvs_off
        lda #0
        sta vdlg_rvs
        rts
vic_not_rvs_off:
        cmp #$13
        bne vic_not_home
        lda #0
        sta vdlg_row
        sta vdlg_col
        rts
vic_not_home:
        cmp #$93
        bne vic_not_clear
        jmp vic_clear
vic_not_clear:
        ldx #15
vic_color_scan:
        cmp dlg_color_codes,x   ; VIC-II color order, so X is the color
        beq vic_set_color
        dex
        bpl vic_color_scan
        cmp #$20
        bcc vic_ignore          ; $00-$1f: other control codes
        cmp #$80
        bcc vic_printable
        cmp #$a0
        bcc vic_ignore          ; $80-$9f: other control codes
vic_printable:
        jsr petscii_to_screen
        ldx vdlg_rvs
        beq vic_have_char
        ora #$80                ; reverse glyph
vic_have_char:
        sta vdlg_char
        lda vdlg_col
        cmp #VIC_COLS
        bcc vic_write
        jsr vic_newline         ; deferred wrap
vic_write:
        ldx vdlg_row
        jsr vic_row_ptrs
        ldy vdlg_col
        lda vdlg_char
vic_w_chr:
        sta $ffff,y             ; self-modified: this row's screen RAM
        lda vdlg_color
vic_w_clr:
        sta $ffff,y             ; self-modified: this row's color RAM
        inc vdlg_col
vic_ignore:
        rts

vic_set_color:
        stx vdlg_color
        rts

vic_cr:
        lda #0                  ; CR ends reverse
        sta vdlg_rvs
        ; fall through

; --- vic_newline: column 0 of the next row, scrolling the window (and
; saving its top row to history) from the bottom row. ---
vic_newline:
        lda #0
        sta vdlg_col
        lda vdlg_row
        cmp #DLG_LAST_ROW
        bcs vic_scroll
        inc vdlg_row
        rts
vic_scroll:
        ldx #0
        jsr vsb_push_row
        jsr vic_rows_up
        ldx #DLG_LAST_ROW
        jmp vic_blank_row

; --- vic_rows_up: rows 1-22 to 0-21, screen and color RAM, ascending
; (the destination is below the source, so that's safe). Row 22 is left
; as it was. ---
vic_rows_up:
        ldx #0
vic_up_page0:
        lda VIC_SCR+$28,x
        sta VIC_SCR,x
        lda VIC_CLR+$28,x
        sta VIC_CLR,x
        inx
        bne vic_up_page0
vic_up_page1:
        lda VIC_SCR+$128,x
        sta VIC_SCR+$100,x
        lda VIC_CLR+$128,x
        sta VIC_CLR+$100,x
        inx
        bne vic_up_page1
vic_up_page2:
        lda VIC_SCR+$228,x
        sta VIC_SCR+$200,x
        lda VIC_CLR+$228,x
        sta VIC_CLR+$200,x
        inx
        bne vic_up_page2
vic_up_tail:
        lda VIC_SCR+$328,x
        sta VIC_SCR+$300,x
        lda VIC_CLR+$328,x
        sta VIC_CLR+$300,x
        inx
        cpx #VIC_SCROLL_TAIL
        bne vic_up_tail
        rts

; --- vic_blank_row: X = row -> spaces in the current color. Preserves
; X. ---
vic_blank_row:
        jsr vic_row_ptrs
        ldy #0
vic_blank_loop:
        lda #' '
vic_b_chr:
        sta $ffff,y             ; self-modified
        lda vdlg_color
vic_b_clr:
        sta $ffff,y             ; self-modified
        iny
        cpy #VIC_COLS
        bne vic_blank_loop
        rts

; --- vic_clear (CLR from the server): every row in use goes to history
; first, then the window is blanked and the cursor homed. ---
vic_clear:
        lda vdlg_row            ; rows 0..vdlg_row are in use -- or only
        ldx vdlg_col            ; 0..vdlg_row-1 when the cursor sits at
        beq vic_clear_limit     ; the start of an empty row
        clc
        adc #1
vic_clear_limit:
        sta vdlg_clear_end
        lda #0
        sta vdlg_clear_row
vic_clear_push:
        ldx vdlg_clear_row
        cpx vdlg_clear_end
        bcs vic_clear_blank
        jsr vsb_push_row
        inc vdlg_clear_row
        jmp vic_clear_push
vic_clear_blank:
        ldx #0
vic_clear_rows:
        jsr vic_blank_row
        inx
        cpx #DLG_ROWS
        bcc vic_clear_rows
        lda #0
        sta vdlg_row
        sta vdlg_col
        rts

; --- vsb_row_addr: vsb_index (word) -> vsb_addr = .A * 256 + index * 80
; (index * 16 + index * 64; the index is at most 613, so it fits).
; Clobbers X. ---
vsb_row_addr:
        sta vsb_base_hi
        lda vsb_index
        sta vsb_addr
        lda vsb_index+1
        sta vsb_addr+1
        ldx #4
vsb_row_x16:
        asl vsb_addr
        rol vsb_addr+1
        dex
        bne vsb_row_x16
        lda vsb_addr
        sta vsb_x16
        lda vsb_addr+1
        sta vsb_x16+1
        asl vsb_addr
        rol vsb_addr+1
        asl vsb_addr
        rol vsb_addr+1          ; * 64
        clc
        lda vsb_addr
        adc vsb_x16
        sta vsb_addr
        lda vsb_addr+1
        adc vsb_x16+1
        clc
        adc vsb_base_hi
        sta vsb_addr+1
        rts

; --- vic_row_to_vdc: X = window row -> its 40 screen codes, then its 40
; colors, written to VDC RAM at vsb_addr. ---
vic_row_to_vdc:
        jsr vic_row_ptrs
        lda vsb_addr+1
        ldy vsb_addr
        jsr vdc_set_update
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy #0
vic_r_chr:
        lda $ffff,y             ; self-modified: this row's screen RAM
vic_to_vdc_chr_wait:
        bit VDC_ADDR_REG
        bpl vic_to_vdc_chr_wait
        sta VDC_DATA_REG
        iny
        cpy #VIC_COLS
        bne vic_r_chr
        ldy #0
vic_r_clr:
        lda $ffff,y             ; self-modified: this row's color RAM
vic_to_vdc_clr_wait:
        bit VDC_ADDR_REG
        bpl vic_to_vdc_clr_wait
        sta VDC_DATA_REG
        iny
        cpy #VIC_COLS
        bne vic_r_clr
        rts

; --- vdc_to_vic_row: X = window row <- the 80-byte row record at
; vsb_addr in VDC RAM. ---
vdc_to_vic_row:
        jsr vic_row_ptrs
        lda vsb_addr+1
        ldy vsb_addr
        jsr vdc_set_update
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy #0
vdc_to_vic_chr:
        bit VDC_ADDR_REG
        bpl vdc_to_vic_chr
        lda VDC_DATA_REG
vic_s_chr:
        sta $ffff,y             ; self-modified: this row's screen RAM
        iny
        cpy #VIC_COLS
        bne vdc_to_vic_chr
        ldy #0
vdc_to_vic_clr:
        bit VDC_ADDR_REG
        bpl vdc_to_vic_clr
        lda VDC_DATA_REG
vic_s_clr:
        sta $ffff,y             ; self-modified: this row's color RAM
        iny
        cpy #VIC_COLS
        bne vdc_to_vic_clr
        rts

; --- vsb_push_row: X = window row -> the next ring slot in VDC RAM. ---
vsb_push_row:
        stx vsb_row
        lda vsb_head
        sta vsb_index
        lda vsb_head+1
        sta vsb_index+1
        lda vsb_hist_hi
        jsr vsb_row_addr
        ldx vsb_row
        jsr vic_row_to_vdc
        inc vsb_head
        bne vsb_push_wrap
        inc vsb_head+1
vsb_push_wrap:
        lda vsb_head
        cmp vsb_limit
        bne vsb_push_count
        lda vsb_head+1
        cmp vsb_limit+1
        bne vsb_push_count
        lda #0
        sta vsb_head
        sta vsb_head+1
vsb_push_count:
        lda vsb_count
        cmp vsb_limit
        bne vsb_push_inc
        lda vsb_count+1
        cmp vsb_limit+1
        beq vsb_push_rts        ; full: the oldest row was just overwritten
vsb_push_inc:
        inc vsb_count
        bne vsb_push_rts
        inc vsb_count+1
vsb_push_rts:
        rts

; --- vsb_render_row: X = window row -> whatever the scrollback offset
; puts there. Rows above the offset are history (age = offset - row,
; ring slot = head - age, wrapped); the rest are saved live rows (row -
; offset). ---
vsb_render_row:
        stx vsb_row
        lda vsb_offset+1
        bne vsb_render_hist     ; offset >= 256: every row is history
        cpx vsb_offset
        bcc vsb_render_hist
        txa                     ; saved live row = row - offset
        sec
        sbc vsb_offset
        sta vsb_index
        lda #0
        sta vsb_index+1
        lda vsb_save_hi
        jmp vsb_render_from
vsb_render_hist:
        sec                     ; age = offset - row
        lda vsb_offset
        sbc vsb_row
        sta vsb_tmp
        lda vsb_offset+1
        sbc #0
        sta vsb_tmp+1
        sec                     ; slot = head - age
        lda vsb_head
        sbc vsb_tmp
        sta vsb_index
        lda vsb_head+1
        sbc vsb_tmp+1
        sta vsb_index+1
        bcs vsb_render_hist_ok
        clc                     ; borrowed: wrap around the ring
        lda vsb_index
        adc vsb_limit
        sta vsb_index
        lda vsb_index+1
        adc vsb_limit+1
        sta vsb_index+1
vsb_render_hist_ok:
        lda vsb_hist_hi
vsb_render_from:
        jsr vsb_row_addr
        ldx vsb_row
        jmp vdc_to_vic_row

vsb_redraw:
        lda #0
        sta vsb_loop
vsb_redraw_loop:
        ldx vsb_loop
        jsr vsb_render_row
        inc vsb_loop
        lda vsb_loop
        cmp #DLG_ROWS
        bcc vsb_redraw_loop
        rts

; --- vsb_save_live / vsb_restore_live: dialogue rows 0-22 to/from the
; VDC save area, one 80-byte record per row. ---
vsb_save_live:
        lda #0
        sta vsb_loop
vsb_save_loop:
        jsr vsb_save_addr
        ldx vsb_loop
        jsr vic_row_to_vdc
        inc vsb_loop
        lda vsb_loop
        cmp #DLG_ROWS
        bcc vsb_save_loop
        rts

vsb_restore_live:
        lda #0
        sta vsb_loop
vsb_restore_loop:
        jsr vsb_save_addr
        ldx vsb_loop
        jsr vdc_to_vic_row
        inc vsb_loop
        lda vsb_loop
        cmp #DLG_ROWS
        bcc vsb_restore_loop
        rts

; vsb_loop = window row -> vsb_addr = its record in the save area.
vsb_save_addr:
        lda vsb_loop
        sta vsb_index
        lda #0
        sta vsb_index+1
        lda vsb_save_hi
        jmp vsb_row_addr

; --- vsb_exit and the four scrollback moves -- vdc_screen.asm's sb_*,
; with word counts. Each redraws the status row, which shows the
; position while scrolled back. Every early-out has its own rts. ---
vsb_exit:
        lda vsb_offset
        ora vsb_offset+1
        bne vsb_exit_now
        rts
vsb_exit_now:
        lda #0
        sta vsb_offset
        sta vsb_offset+1
vsb_back_to_live:
        jsr vsb_restore_live
        jmp draw_status_row

vsb_line_back:
        lda vsb_offset          ; offset < count?
        cmp vsb_count
        lda vsb_offset+1
        sbc vsb_count+1
        bcc vsb_line_back_ok
        rts                     ; already at the oldest row
vsb_line_back_ok:
        lda vsb_offset
        ora vsb_offset+1
        bne vsb_line_back_move
        jsr vsb_save_live
vsb_line_back_move:
        inc vsb_offset
        bne vsb_line_back_draw
        inc vsb_offset+1
vsb_line_back_draw:
        jsr vsb_redraw
        jmp draw_status_row

vsb_line_fwd:
        lda vsb_offset
        ora vsb_offset+1
        bne vsb_line_fwd_ok
        rts
vsb_line_fwd_ok:
        lda vsb_offset
        bne vsb_line_fwd_lo
        dec vsb_offset+1
vsb_line_fwd_lo:
        dec vsb_offset
        lda vsb_offset
        ora vsb_offset+1
        bne vsb_line_fwd_move
        jmp vsb_back_to_live
vsb_line_fwd_move:
        jsr vsb_redraw
        jmp draw_status_row

vsb_page_back:
        lda vsb_count
        ora vsb_count+1
        bne vsb_page_back_ok
        rts
vsb_page_back_ok:
        lda vsb_offset
        ora vsb_offset+1
        bne vsb_page_back_move
        jsr vsb_save_live
vsb_page_back_move:
        clc
        lda vsb_offset
        adc #SB_PAGE
        sta vsb_offset
        lda vsb_offset+1
        adc #0
        sta vsb_offset+1
        lda vsb_offset          ; past the oldest row: clamp to count
        cmp vsb_count
        lda vsb_offset+1
        sbc vsb_count+1
        bcc vsb_page_back_draw
        lda vsb_count
        sta vsb_offset
        lda vsb_count+1
        sta vsb_offset+1
vsb_page_back_draw:
        jsr vsb_redraw
        jmp draw_status_row

vsb_page_fwd:
        lda vsb_offset
        ora vsb_offset+1
        bne vsb_page_fwd_ok
        rts
vsb_page_fwd_ok:
        sec
        lda vsb_offset
        sbc #SB_PAGE
        tax
        lda vsb_offset+1
        sbc #0
        bcc vsb_page_fwd_live   ; under 0: back to live
        sta vsb_offset+1
        stx vsb_offset
        ora vsb_offset
        bne vsb_page_fwd_move
vsb_page_fwd_live:
        lda #0
        sta vsb_offset
        sta vsb_offset+1
        jmp vsb_back_to_live
vsb_page_fwd_move:
        jsr vsb_redraw
        jmp draw_status_row

; --- vsb_status_text: "Scrollback: 001 of 614" (screen codes, 0-
; terminated) into sb_status_buf; A/Y = its address. Shorter than the
; 80-column message -- the page keys are named in the dialogue at
; connect instead (out_scroll_hint), and the row has the clock to leave
; room for. ---
vsb_status_text:
        ldx #0
        lda #<sb_msg_pos
        ldy #>sb_msg_pos
        jsr sb_append
        lda vsb_offset
        ldy vsb_offset+1
        jsr vsb_append_dec3w
        lda #<sb_msg_of
        ldy #>sb_msg_of
        jsr sb_append
        lda vsb_count
        ldy vsb_count+1
        jsr vsb_append_dec3w
        lda #0
        sta sb_status_buf,x
        lda #<sb_status_buf
        ldy #>sb_status_buf
        rts

; A/Y = 0-999 (low/high) -> three digits appended to sb_status_buf at X
; (X advances 3).
vsb_append_dec3w:
        sta vsb_tmp
        sty vsb_tmp+1
        ldy #'0'
vsb_dec_hundreds:
        sec
        lda vsb_tmp
        sbc #100
        sta vsb_dec_lo
        lda vsb_tmp+1
        sbc #0
        bcc vsb_dec_rest
        sta vsb_tmp+1
        lda vsb_dec_lo
        sta vsb_tmp
        iny
        jmp vsb_dec_hundreds
vsb_dec_rest:
        sty vsb_dec_lo          ; the hundreds digit, past dec3's '0'
        lda vsb_tmp
        jsr sb_append_dec3      ; under 100 now; X += 3
        lda vsb_dec_lo
        sta sb_status_buf-3,x
        rts

; --- vic_ram_msg_out: "VDC RAM: 64K -- 614 lines of scrollback." into
; the dialogue (go_offline's 40-column banner), straight from what
; vic_screen_init found. ---
vic_ram_msg_out:
        lda #<vic_ram_msg
        ldy #>vic_ram_msg
        jsr out_string
        lda #<vic_ram_msg_16k
        ldy #>vic_ram_msg_16k
        ldx vdc_ram_64k
        beq vic_ram_msg_size
        lda #<vic_ram_msg_64k
        ldy #>vic_ram_msg_64k
vic_ram_msg_size:
        jsr out_string
        ldx #0                  ; the limit, through sb_status_buf's
        lda vsb_limit           ; digit routine
        ldy vsb_limit+1
        jsr vsb_append_dec3w
        lda sb_status_buf
        jsr out_char
        lda sb_status_buf+1
        jsr out_char
        lda sb_status_buf+2
        jsr out_char
        lda #<vic_ram_msg_tail
        ldy #>vic_ram_msg_tail
        jmp out_string

; --- Dispatchers: client-128.asm and keymap_128.asm call these, and they
; pick vdc_screen.asm's (80 columns) or this file's (40) version. ---

; A = 0 (Z set) when the dialogue shows the live view, on either screen.
; Only one of the two offsets is ever in use.
sb_any_offset:
        lda sb_offset
        ora vsb_offset
        ora vsb_offset+1
        rts

sb_exit_any:
        lda screen_mode
        bne sb_exit_any_40
        jmp sb_exit
sb_exit_any_40:
        jmp vsb_exit

sb_page_back_any:
        lda screen_mode
        bne sb_page_back_any_40
        jmp sb_page_back
sb_page_back_any_40:
        jmp vsb_page_back

sb_page_fwd_any:
        lda screen_mode
        bne sb_page_fwd_any_40
        jmp sb_page_fwd
sb_page_fwd_any_40:
        jmp vsb_page_fwd

; A/Y = the scrollback position message for the status row.
sb_status_any:
        lda screen_mode
        bne sb_status_any_40
        jmp sb_status_text
sb_status_any_40:
        jmp vsb_status_text

; .A = CRSR UP ($91) or DOWN ($11): a line back / forward. Carry set
; (consumed), like vdc_key_hook.
scroll_key_hook:
        ldx screen_mode
        bne scroll_key_40
        jmp vdc_key_hook
scroll_key_40:
        cmp #$91
        bne scroll_key_40_down
        jsr vsb_line_back
        sec
        rts
scroll_key_40_down:
        jsr vsb_line_fwd
        sec
        rts

; The dialogue cursor's row blanked and the cursor back at its start --
; relocate_prompt taking the prompt out of the dialogue.
dlg_blank_cur_row:
        lda screen_mode
        bne dlg_blank_cur_40
        ldx dlg_row
        jsr dlg_blank_row
        lda #0
        sta dlg_col
        rts
dlg_blank_cur_40:
        ldx vdlg_row
        jsr vic_blank_row
        lda #0
        sta vdlg_col
        rts

; --- Tables ---

; Row start addresses in SCREEN_RAM, row * 40, rows 0-24.
vic_row_lo:
        byte $00,$28,$50,$78,$a0,$c8,$f0,$18,$40,$68,$90,$b8,$e0
        byte $08,$30,$58,$80,$a8,$d0,$f8,$20,$48,$70,$98,$c0
vic_row_hi:
        byte $04,$04,$04,$04,$04,$04,$04,$05,$05,$05,$05,$05,$05
        byte $06,$06,$06,$06,$06,$06,$06,$07,$07,$07,$07,$07

; PETSCII for out_string, {alpha:alt} for real capitals.
{alpha:alt}
vic_ram_msg:
        ascii "VDC RAM: "
        byte 0
vic_ram_msg_16k:
        ascii "16K -- "
        byte 0
vic_ram_msg_64k:
        ascii "64K -- "
        byte 0
vic_ram_msg_tail:
        ascii " lines of scrollback."
        byte 13, 0
{alpha:normal}

; --- Variables ---
vdlg_row:        byte 0
vdlg_col:        byte 0         ; 40 = past the right edge (deferred wrap)
vdlg_color:      byte 0         ; VIC-II color, 0-15
vdlg_rvs:        byte 0
vdlg_char:       byte 0
vdlg_saved_x:    byte 0
vdlg_saved_y:    byte 0
vdlg_clear_row:  byte 0
vdlg_clear_end:  byte 0
vsb_limit:       word 0         ; ring rows, from the VDC's RAM size
vsb_hist_hi:     byte 0         ; ring start (VDC RAM high byte)
vsb_save_hi:     byte 0         ; save area start (VDC RAM high byte)
vsb_head:        word 0         ; ring slot the next row goes into
vsb_count:       word 0         ; rows held, 0 to vsb_limit
vsb_offset:      word 0         ; rows scrolled back; 0 = live view
vsb_index:       word 0
vsb_addr:        word 0
vsb_x16:         word 0
vsb_base_hi:     byte 0
vsb_tmp:         word 0
vsb_row:         byte 0
vsb_loop:        byte 0
vsb_dec_lo:      byte 0
