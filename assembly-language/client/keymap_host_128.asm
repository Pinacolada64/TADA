; keymap_host_128.asm -- client-128.asm's side of keymap_menu.asm, the
; C64 client's Keymap Editor popup, built in from the same source (see
; constants_128.asm and the Makefile's keymap_menu_128.asm rule).
;
; The popup is written for a 40x25 VIC-II screen: it pokes SCREEN_RAM
; ($0400) and COLOR_RAM ($d800) directly and reaches its host only
; through nine JT_* entry points. On the C64 those are a jump table at
; $c000; here they're ordinary labels, below.
;
; 40 columns: the popup draws on the real screen, exactly as on the C64 --
; JT_SAVE_SCREEN backs the screen up and greys it, JT_RESTORE_SCREEN puts
; it back (tada-client.asm's save_screen/restore_screen).
;
; 80 columns: the VIC-II's $0400 screen still exists, it's just not what
; the monitor shows. So the popup keeps drawing there untouched, and
; km_present_tick -- run from the IRQ while the popup is open -- copies
; VIC rows 2-23 (the popup box plus the status row it also writes)
; onto the VDC at columns 20-59, KM_ROWS_PER_TICK rows per tick,
; translating VIC colors to VDC attributes. Only cells that changed since
; the last pass are written (km_shadow keeps what was last sent), so an
; idle popup costs a compare loop and nothing else. The dialogue around
; the box stays visible, greyed, and comes back from the scrollback save
; area ($1000 in VDC RAM) by block copy on close.
;
; IRQ safety: while km_present_on is set, the IRQ owns the VDC. Nothing
; in mainline touches the VDC during that time -- the status row is
; drawn to VIC row 23 instead (draw_status_row checks km_present_on), no
; dialogue output happens (there's no SwiftLink yet; once there is,
; output arriving during the popup will need holding back), and
; JT_RESTORE_SCREEN clears the flag before its own VDC work.
;
; This file (all of it, code and data) must stay below $4000: the KERNAL
; IRQ runs our handler with $FF00 = $00, BASIC ROM over $4000-$bfff.

KM_VIC_SCREEN       = $0400       ; SCREEN_RAM/COLOR_RAM/ROW_BYTES/MAX_COLS
KM_VIC_COLORS       = $d800       ; are client-128.asm's {const:}s, which
KM_COLS_40          = 40          ; don't reach {include:}d files
KM_COLS_80          = 80
KM_BACKUP           = $1300       ; 40 cols: 1000 chars then 1000 colors
KM_BACKUP_COLORS    = $16e8
KM_SHADOW_CHR_BASE  = $12b0       ; 80 cols: last-presented chars, rows 2-23,
KM_SHADOW_COL_BASE  = $1620       ; + row*40 ($1300-$166f), colors after
                                  ; them ($1670-$19df). $1300-$1bff is free
                                  ; RAM on the 128 ("reserved for foreign
                                  ; language systems and function key
                                  ; software" -- Programmer's Guide); only
                                  ; one of the two uses is ever live.
KM_SHADOW           = $1300
KM_SHADOW_BYTES     = 1760        ; 22 rows * 40 * (char + color)
KM_FIRST_ROW        = 2           ; keymap_menu.asm's BOX_TOP_ROW
KM_LAST_ROW         = 23          ; its STATUS_ROW_SCREEN row
KM_VDC_STATUS_ADDR  = $0730       ; VDC row 23 (23 * 80, by hand: c64list
                                  ; truncates products of byte constants)
KM_VDC_COL          = 20          ; VIC column 0 -> VDC column 20 (centered)
KM_ROWS_PER_TICK    = 3           ; full pass every 8 ticks, ~130ms
KM_GREY             = 12          ; tada-client.asm's POPUP_GREY_COLOR
KM_SCREEN_CELLS     = 1000

PFKEY               = $ff65
SETBNK              = $ff68

; --- JT_SAVE_SCREEN ---
JT_SAVE_SCREEN:
        lda screen_mode
        beq km_save_vdc
        jsr vsb_exit                ; the popup always opens on the live view
        lda #<KM_VIC_SCREEN
        ldy #>KM_VIC_SCREEN
        jsr km_set_src
        lda #<KM_BACKUP
        ldy #>KM_BACKUP
        jsr km_copy_1000
        lda #<KM_VIC_COLORS
        ldy #>KM_VIC_COLORS
        jsr km_set_src
        lda #<KM_BACKUP_COLORS
        ldy #>KM_BACKUP_COLORS
        jsr km_copy_1000
        lda #<KM_VIC_COLORS
        ldy #>KM_VIC_COLORS
        ldx #KM_GREY
        jmp km_fill_1000

km_save_vdc:
        jsr vs_cursor_off           ; the input row's VDC cursor, if Video
                                    ; Settings turned it on (video_menu_
                                    ; 128.asm) -- the editor puts it back
        jsr sb_exit                 ; the popup always opens on the live view
        jsr sb_save_live            ; dialogue rows 0-22 -> VDC $1000
        lda #0                      ; grey the dialogue: its attributes only,
        sta vdc_dst                 ; the characters stay readable
        sta vdc_dst+1
        lda #<DLG_BYTES
        sta vdc_count
        lda #>DLG_BYTES
        sta vdc_count+1
        ldx #KM_GREY
        lda dlg_vdc_colors,x
        ora #$80                    ; ALT (lowercase set)
        sta km_grey_attr
        jsr vdc_attr_fill
        ; The status row becomes the popup's 40-column one (VIC row 23,
        ; presented at columns 20-59) -- blank all 80 first, or the ends
        ; of the full-width status text show on either side of it.
        lda #<KM_VDC_STATUS_ADDR
        sta vdc_dst
        lda #>KM_VDC_STATUS_ADDR
        sta vdc_dst+1
        lda #$a0                    ; reverse space, like the status row
        ldx km_grey_attr
        ldy #VDC_COLS
        jsr vdc_fill_pair
        ; Blank the (invisible) VIC screen the popup is about to draw on,
        ; so any cell it leaves alone presents as a blank, not old boot
        ; text; white like the box itself.
        lda #<KM_VIC_SCREEN
        ldy #>KM_VIC_SCREEN
        ldx #' '
        jsr km_fill_1000
        lda #<KM_VIC_COLORS
        ldy #>KM_VIC_COLORS
        ldx #1
        jsr km_fill_1000
        ; Shadow = "nothing sent yet": $ff never matches a color and is
        ; almost never a screen code, so the first passes send everything.
        lda #<KM_SHADOW
        sta km_fill_store+1
        lda #>KM_SHADOW
        sta km_fill_store+2
        lda #<KM_SHADOW_BYTES
        sta km_count
        lda #>KM_SHADOW_BYTES
        sta km_count+1
        ldx #$ff
        jsr km_fill
        lda #KM_COLS_40              ; the status row is the popup's 40-column
        sta scr_cols                ; VIC row 23 while it's open
        lda #KM_FIRST_ROW
        sta km_pt_row
        lda #1
        sta km_present_on           ; the IRQ takes the VDC from here on
        rts

; vdc_attr_fill: A = attribute; fill vdc_count bytes of ATTRIBUTES from
; the character address in vdc_dst.
vdc_attr_fill:
        pha
        clc
        lda vdc_dst+1
        adc #VDC_ATTR_HI
        sta vdc_dst+1
        pla
        jmp vdc_fill

; --- JT_RESTORE_SCREEN ---
JT_RESTORE_SCREEN:
        lda screen_mode
        beq km_restore_vdc
        lda #<KM_BACKUP
        ldy #>KM_BACKUP
        jsr km_set_src
        lda #<KM_VIC_SCREEN
        ldy #>KM_VIC_SCREEN
        jsr km_copy_1000
        lda #<KM_BACKUP_COLORS
        ldy #>KM_BACKUP_COLORS
        jsr km_set_src
        lda #<KM_VIC_COLORS
        ldy #>KM_VIC_COLORS
        jsr km_copy_1000
        jmp draw_status_row

km_restore_vdc:
        lda #0
        sta km_present_on           ; mainline owns the VDC again (an IRQ
                                    ; already in progress finished before
                                    ; this instruction could run)
        lda #KM_COLS_80
        sta scr_cols
        jsr sb_restore_live         ; dialogue rows 0-22, chars + attributes
        jmp draw_status_row         ; the full-width row 23

; --- JT_RESUME / JT_RESUME_LOCAL: back to a fresh input line. The popup
; was entered from deep inside input_editor.asm (gk1 -> editor_key_hook
; -> km_dispatch -> km_open), and main_loop re-enters the editor from
; scratch, so the stack goes back to main_loop's own depth first --
; the same partial-line-is-dropped behavior as the C64's resume_local. ---
JT_RESUME:
JT_RESUME_LOCAL:
        ldx main_loop_sp
        txs
        jmp main_loop

; --- JT_STATUS_PUSH_RESET / JT_BUILD_STATUS_LINE: the C64 client has a
; rotating status queue; this client has one message plus an override.
; BUILD takes X/Y = a 0-terminated screen-code message and shows it in
; place of status_msg until the next key the input editor sees (an
; empty message just drops the override). Preserves X and Y. ---
JT_STATUS_PUSH_RESET:
        rts

JT_BUILD_STATUS_LINE:
        stx km_saved_x
        sty km_saved_y
        stx km_msg_peek+1
        sty km_msg_peek+2
km_msg_peek:
        lda $ffff                   ; self-modified: first message byte
        bne km_msg_set
        ldy #0                      ; empty -> no override
km_msg_set:
        stx status_override
        sty status_override+1
        jsr draw_status_row
        ldx km_saved_x
        ldy km_saved_y
        rts

; --- The popup's cursor: one VIC screen cell at km_cur_row/km_cur_col,
; shown by flipping its reverse bit, paced by input_editor.asm's own
; blinkctr/cursor_blink_mask (the input editor isn't running while the
; popup is open, so its IRQ-driven countdown is free to borrow). In 80
; columns the flip reaches the VDC through km_present_tick like any
; other popup drawing. GET/SET use the KERNAL_PLOT register order (X =
; row, Y = column). All four preserve X and Y. ---
JT_GET_CURSOR:
        ldx km_cur_row
        ldy km_cur_col
        rts

JT_SET_CURSOR:
        stx km_cur_row
        sty km_cur_col
        rts

JT_CURSOR_HIDE:
        lda km_cur_on
        beq km_cur_rts
        jmp km_cur_toggle

JT_UPDATE_CURSOR:
        lda cursor_blink_mask
        bne km_cur_blink
        lda km_cur_on               ; solid: just make sure it's shown
        bne km_cur_rts
        jmp km_cur_toggle
km_cur_blink:
        lda blinkctr
        bne km_cur_rts              ; not time yet
        lda cursor_blink_mask
        sta blinkctr
        ; fall through
km_cur_toggle:
        stx km_saved_x
        sty km_saved_y
        ldx km_cur_row
        clc
        lda km_row40_lo,x
        adc #<KM_VIC_SCREEN
        sta km_cur_load+1
        sta km_cur_store+1
        lda km_row40_hi,x
        adc #>KM_VIC_SCREEN
        sta km_cur_load+2
        sta km_cur_store+2
        ldy km_cur_col
km_cur_load:
        lda $ffff,y
        eor #$80
km_cur_store:
        sta $ffff,y
        lda km_cur_on
        eor #1
        sta km_cur_on
        ldx km_saved_x
        ldy km_saved_y
km_cur_rts:
        rts

; --- km_present_tick: IRQ side, 80 columns only (irq_handler calls it
; while km_present_on is set). See this file's header comment. ---
km_present_tick:
        lda #KM_ROWS_PER_TICK
        sta km_pt_left
km_pt_loop:
        jsr km_present_row
        ldx km_pt_row
        inx
        cpx #KM_LAST_ROW+1
        bcc km_pt_store
        ldx #KM_FIRST_ROW
km_pt_store:
        stx km_pt_row
        dec km_pt_left
        bne km_pt_loop
        rts

; One VIC row (km_pt_row) -> the same VDC row, columns 20-59: the changed
; characters first, then the changed colors.
km_present_row:
        ldx km_pt_row
        clc
        lda km_row40_lo,x
        adc #<KM_VIC_SCREEN
        sta km_pr_vic+1
        lda km_row40_hi,x
        adc #>KM_VIC_SCREEN
        sta km_pr_vic+2
        clc
        lda km_row40_lo,x
        adc #<KM_VIC_COLORS
        sta km_pr_col+1
        lda km_row40_hi,x
        adc #>KM_VIC_COLORS
        sta km_pr_col+2
        clc
        lda km_row40_lo,x
        adc #<KM_SHADOW_CHR_BASE
        sta km_pr_shc+1
        sta km_pr_shs+1
        lda km_row40_hi,x
        adc #>KM_SHADOW_CHR_BASE
        sta km_pr_shc+2
        sta km_pr_shs+2
        clc
        lda km_row40_lo,x
        adc #<KM_SHADOW_COL_BASE
        sta km_pr_scc+1
        sta km_pr_scs+1
        lda km_row40_hi,x
        adc #>KM_SHADOW_COL_BASE
        sta km_pr_scc+2
        sta km_pr_scs+2
        clc
        lda vdc_row_lo,x
        adc #KM_VDC_COL
        sta km_pr_vdc_lo
        lda vdc_row_hi,x
        adc #0
        sta km_pr_vdc_hi

        lda #$ff                    ; VDC update address: nowhere useful yet
        sta km_pr_next
        ldy #0
km_pr_chr_loop:
km_pr_vic:
        lda $ffff,y                 ; self-modified: VIC screen row
km_pr_shc:
        cmp $ffff,y                 ; self-modified: shadow chars
        beq km_pr_chr_next
km_pr_shs:
        sta $ffff,y
        jsr km_pr_put_chr
km_pr_chr_next:
        iny
        cpy #40
        bne km_pr_chr_loop

        lda #$ff
        sta km_pr_next
        ldy #0
km_pr_col_loop:
km_pr_col:
        lda $ffff,y                 ; self-modified: color RAM row
        and #$0f                    ; color RAM's upper nybble is noise
km_pr_scc:
        cmp $ffff,y                 ; self-modified: shadow colors
        beq km_pr_col_next
km_pr_scs:
        sta $ffff,y
        tax
        lda dlg_vdc_colors,x
        ora #$80                    ; ALT: lowercase set, as everywhere
        jsr km_pr_put_attr
km_pr_col_next:
        iny
        cpy #40
        bne km_pr_col_loop
        rts

; A = byte for column Y of the row: km_pr_put_chr to the character,
; km_pr_put_attr to its attribute. Re-aims the VDC update address only
; when it isn't already on this cell (consecutive changed cells just
; stream). Preserves Y.
km_pr_put_attr:
        sta km_pr_byte
        lda #VDC_ATTR_HI
        jmp km_pr_put
km_pr_put_chr:
        sta km_pr_byte
        lda #0
km_pr_put:
        cpy km_pr_next
        beq km_pr_write
        sta km_pr_hi_add
        sty km_pr_y
        clc
        tya
        adc km_pr_vdc_lo
        tay
        lda km_pr_vdc_hi
        adc km_pr_hi_add
        jsr vdc_set_update          ; A = high, Y = low
        ldx #VDC_R_DATA
        stx VDC_ADDR_REG
        ldy km_pr_y
km_pr_write:
km_pr_wait:
        bit VDC_ADDR_REG
        bpl km_pr_wait
        lda km_pr_byte
        sta VDC_DATA_REG
        iny
        sty km_pr_next
        dey
        rts

; --- km_init_keyboard: two 128-specific keyboard fixes the shared
; keymap needs, run once at startup. ---
;
; 1. Function keys: the 128's editor expands F1-F8 into whole strings
;    ("list"+RETURN for F7, ...) before GETIN ever sees a key, so the
;    C64 client's default "F7 opens the editor" binding (and any F-key
;    binding at all) could never fire. PFKEY reprograms each one to a
;    single byte, the C64's own F-key code, so GETIN returns $85-$8c
;    just like on the C64. (The player's BASIC F-key strings come back
;    with a reset.)
; 2. CTRL + the main CRSR keys: the 128's CTRL decode table ($FB8B)
;    maps them to $ff, "no key" -- the same KERNAL quirk the C64 client
;    fixed in keyboard_rollover.asm. The 128 editor reads its decode
;    tables through RAM pointers at $033e (normal, shift, C=, CTRL, ALT,
;    caps; SCNKEY $C647), so this copies the CTRL table to RAM, maps
;    CRSR RIGHT/DOWN (key numbers 2 and 7) to $1d/$11 like the unshifted
;    table, and points $0344 at the copy. (The top-row arrow keys
;    already worked with CTRL.)
km_init_keyboard:
        lda #1
        sta km_fk_num
km_fkey_loop:
        ldx km_fk_num
        lda km_fkey_codes-1,x
        sta km_fk_char
        lda #<km_fk_char            ; PFKEY takes .A = the zero-page
        sta $fb                     ; address of a 3-byte pointer (lo,
        lda #>km_fk_char            ; hi, bank); $fb-$fd are free until
        sta $fc                     ; the input editor first runs
        lda #0
        sta $fd
        lda #$fb
        ldx km_fk_num
        ldy #1
        jsr PFKEY
        inc km_fk_num
        lda km_fk_num
        cmp #9
        bne km_fkey_loop

        ldx #0
km_ctrl_copy:
        lda $fb8b,x                 ; KERNAL ROM CTRL table, 89 bytes
        sta km_ctrl_table,x
        inx
        cpx #89
        bne km_ctrl_copy
        lda #$1d
        sta km_ctrl_table+2
        lda #$11
        sta km_ctrl_table+7
        sei
        lda #<km_ctrl_table
        sta $0344
        lda #>km_ctrl_table
        sta $0345
        cli
        rts

; F1..F8 in PFKEY key-number order (1 = F1, 2 = F2, ...) -> the C64's
; codes for them.
km_fkey_codes:
        byte $85,$89,$86,$8a,$87,$8b,$88,$8c

; --- Small memory helpers (self-modified absolute addressing; no zero
; page, which the input editor owns). ---
km_set_src:
        sta km_copy_load+1
        sty km_copy_load+2
        rts

; A/Y = destination; copies KM_SCREEN_CELLS bytes from km_set_src's.
km_copy_1000:
        sta km_copy_store+1
        sty km_copy_store+2
        lda #<KM_SCREEN_CELLS
        sta km_count
        lda #>KM_SCREEN_CELLS
        sta km_count+1
km_copy_loop:
km_copy_load:
        lda $ffff
km_copy_store:
        sta $ffff
        inc km_copy_load+1
        bne km_copy_no_carry1
        inc km_copy_load+2
km_copy_no_carry1:
        inc km_copy_store+1
        bne km_copy_no_carry2
        inc km_copy_store+2
km_copy_no_carry2:
        jsr km_count_down
        bne km_copy_loop
        rts

; A/Y = destination, X = value; KM_SCREEN_CELLS bytes.
km_fill_1000:
        sta km_fill_store+1
        sty km_fill_store+2
        lda #<KM_SCREEN_CELLS
        sta km_count
        lda #>KM_SCREEN_CELLS
        sta km_count+1
; km_fill: X = value, km_fill_store+1/+2 = destination, km_count bytes.
km_fill:
        stx km_fill_value
km_fill_loop:
        lda km_fill_value
km_fill_store:
        sta $ffff
        inc km_fill_store+1
        bne km_fill_no_carry
        inc km_fill_store+2
km_fill_no_carry:
        jsr km_count_down
        bne km_fill_loop
        rts

; km_count - 1; Z set when it reaches 0.
km_count_down:
        lda km_count
        bne km_count_lo
        dec km_count+1
km_count_lo:
        dec km_count
        lda km_count
        ora km_count+1
        rts

; row * 40, rows 0-24 (VIC screen / color RAM row offsets)
km_row40_lo:
        byte $00,$28,$50,$78,$a0,$c8,$f0,$18,$40,$68,$90,$b8,$e0
        byte $08,$30,$58,$80,$a8,$d0,$f8,$20,$48,$70,$98,$c0
km_row40_hi:
        byte $00,$00,$00,$00,$00,$00,$00,$01,$01,$01,$01,$01,$01
        byte $02,$02,$02,$02,$02,$02,$02,$03,$03,$03,$03,$03

km_grey_attr:    byte 0
km_present_on:   byte 0          ; 1 = popup open in 80 columns, IRQ presents
km_pt_row:       byte 0
km_pt_left:      byte 0
km_pr_vdc_lo:    byte 0
km_pr_vdc_hi:    byte 0
km_pr_next:      byte 0
km_pr_byte:      byte 0
km_pr_hi_add:    byte 0
km_pr_y:         byte 0
km_cur_row:      byte 0
km_cur_col:      byte 0
km_cur_on:       byte 0
km_saved_x:      byte 0
km_saved_y:      byte 0
km_count:        word 0
km_fill_value:   byte 0
km_fk_num:       byte 0
km_fk_char:      byte 0
km_ctrl_table:
        area 89, 0
