; tile_editor.asm -- edit a multicolor tileset's pixels and colors on the
; C64 itself (Ryan's ask, 2026-10-03: "touch up some of the graphics").
; Standalone, like tile_demo.asm; the client's loadable editor (see
; TILESET_MEMORY_MAP.md) can grow out of this later.
;
; Screen (VIC bank 3, raster split as in tile_demo.asm):
;   rows 0-7   tile palette, all 64 tiles 16 per row (cols 0-31), and the
;              selected tile repeated 3x4 (cols 34-39) to check seams --
;              the real tile charset, multicolor
;   row 8      divider: char $a0 in color 0 (solid black in both charsets
;              and both modes), with a white bar under the selected tile
;   rows 9-24  the selected tile zoomed: 8x16 fat pixels, each drawn as 2x1
;              solid cells in its own color (cols 0-15), and a panel
;              (cols 18-39) -- ROM lowercase font, hires, black background
;
; Keys: CRSR move, SPACE plot, 1-4 pen (bg/$d022/$d023/char color), E pick
; the pen under the cursor, F1/F3/F5 cycle the shared colors, F7 the char
; color of the quarter under the cursor, +/- tile, C/V copy/paste a tile,
; U undo (again: redo), S/L save/load "TILESET" on the current drive,
; Q or RUN/STOP quit.
;
; Data: one TILESET block (tileset_file.py has the format), embedded as
; the default (default_tileset.bin) and LOADed/SAVEd whole. The editor
; reads and writes this copy -- the VIC's copy at $e000 sits under the
; KERNAL, where CPU writes land but reads see ROM -- and writes every
; change through to $e000. Tiles 8 (blank, char $20) and 40 (divider,
; char $a0) are the split's reserved tiles and can't be edited.

SCREEN          = $c400
COLOR_RAM       = $d800
CLR_DELTA       = $14            ; color RAM high byte = screen's + $14
TILE_CHARS      = $e000
TEXT_CHARS      = $e800
LOAD_BUF        = $4000          ; LOAD lands here first, then gets checked

D018_TILES      = $18            ; screen $c400 | chars $e000
D018_TEXT       = $1a            ; screen $c400 | chars $e800
D016_TILES      = $18            ; multicolor on, 40 columns
D016_TEXT       = $08            ; multicolor off
SPLIT_LINE      = 115            ; 51 + 8*8: first line of the divider row
TOP_LINE        = 251            ; first line after row 24

DIV_ROW         = 8
GRID_ROW        = 9
PANEL_COL       = 18
MSG_ROW         = 24
MSG_LEN         = 22
PREVIEW_COL     = 34
SOLID           = $a0
BLANK           = $20
CURSOR_CHAR     = $66            ; checkerboard, in both ROM fonts
RESERVED_BLANK  = 8              ; tile numbers the split depends on
RESERVED_DIV    = 40

; TILESET block layout (see tileset_file.py)
OFS_CHARS       = 3
OFS_COLORS      = 2051
OFS_BG          = 2307           ; bg, mc1, mc2 in a row
OFS_MC1         = 2308
OFS_MC2         = 2309
WS_SIZE         = 2310

ZP_A            = $fb            ; two scratch pointers (free in a
ZP_B            = $fd            ; standalone program)

SETMSG          = $ff90
SCNKEY          = $ff9f
READST          = $ffb7
SETLFS          = $ffba
SETNAM          = $ffbd
OPEN            = $ffc0
CLOSE           = $ffc3
CHKIN           = $ffc6
CLRCHN          = $ffcc
CHRIN           = $ffcf
LOAD            = $ffd5
SAVE            = $ffd8
GETIN           = $ffe4

        orig $0801
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00   ; 10 SYS2061

start:
        sei
        lda #0
        jsr SETMSG                ; no "SAVING"/"SEARCHING" on the hidden
                                  ; KERNAL screen
        jsr build_rows

        ; --- ROM lowercase font -> $e800 (same as tile_demo.asm) ---
        lda #$33
        sta $01
        ldx #0
copy_font:
        lda $d800,x
        sta TEXT_CHARS,x
        lda $d900,x
        sta TEXT_CHARS+$100,x
        lda $da00,x
        sta TEXT_CHARS+$200,x
        lda $db00,x
        sta TEXT_CHARS+$300,x
        lda $dc00,x
        sta TEXT_CHARS+$400,x
        lda $dd00,x
        sta TEXT_CHARS+$500,x
        lda $de00,x
        sta TEXT_CHARS+$600,x
        lda $df00,x
        sta TEXT_CHARS+$700,x
        inx
        bne copy_font
        lda #$37
        sta $01

        jsr sync_all_vic

        ; --- VIC: bank 3, split registers, blank screen ---
        lda $dd00
        and #%11111100
        sta $dd00
        lda #D018_TILES
        sta $d018
        lda #D016_TILES
        sta $d016
        lda #0
        sta $d020
        jsr apply_shared

        ldx #24
clear_rows:
        txa
        pha
        lda #0
        jsr at
        ldy #39
clear_row:
        lda #BLANK
        sta (ZP_A),y
        lda #0
        sta (ZP_B),y
        dey
        bpl clear_row
        pla
        tax
        dex
        bpl clear_rows

        ldx #<panel_labels
        ldy #>panel_labels
        jsr print_list

        ; --- interrupts: CIA1 timer off, two raster IRQs ---
        lda #$7f
        sta $dc0d
        lda $dc0d
        lda #<irq_split
        sta $0314
        lda #>irq_split
        sta $0315
        lda $d011
        and #$7f
        sta $d011
        lda #SPLIT_LINE
        sta $d012
        lda #1
        sta $d01a
        sta $d019
        cli

        jsr redraw_all
        ldx #<msg_hello
        ldy #>msg_hello
        jsr show_msg

; --- main loop: blink the cursor, dispatch one key per frame ---
main_loop:
        lda frame
ml_wait:
        cmp frame
        beq ml_wait
        jsr blink
        jsr GETIN
        beq main_loop
        sta last_key
        ldx #NUM_KEYS-1
ml_find:
        cmp key_codes,x
        beq ml_found
        dex
        bpl ml_find
        jmp main_loop
ml_found:
        lda key_lo,x
        sta ml_call+1
        lda key_hi,x
        sta ml_call+2
ml_call:
        jsr $ffff
        jmp main_loop

; ============================================================
; Key handlers (called with jsr, return with rts)
; ============================================================

key_right:
        jsr cursor_off
        lda cur_x
        cmp #7
        bcs cursor_moved
        inc cur_x
        jmp cursor_moved
key_left:
        jsr cursor_off
        lda cur_x
        beq cursor_moved
        dec cur_x
        jmp cursor_moved
key_down:
        jsr cursor_off
        lda cur_y
        cmp #15
        bcs cursor_moved
        inc cur_y
        jmp cursor_moved
key_up:
        jsr cursor_off
        lda cur_y
        beq cursor_moved
        dec cur_y
cursor_moved:
        jsr draw_panel_values     ; the char color under the cursor
        lda #1
        sta blink_on
        jmp draw_cursor_cell

key_pen:
        lda last_key
        sec
        sbc #$31                  ; '1'-'4' -> 0-3
        sta pen
        jmp draw_panel_values

key_pick:
        jsr locate_cursor
        jsr pix_get
        sta pen
        jmp draw_panel_values

key_plot:
        jsr check_reserved
        bcs kp_rts
        jsr save_undo
        jsr locate_cursor
        lda pen
        jsr pix_set
        lda #0                    ; show the new pixel, not the cursor
        sta blink_on
        jsr draw_cursor_cell
        jmp clear_msg
kp_rts:
        rts

; F1/F3/F5: cycle bg/mc1/mc2 through all 16 colors
key_shared:
        jsr save_undo
        lda last_key
        sec
        sbc #$85                  ; F1/F3/F5 = $85-$87 -> 0-2
        tax
        lda work+OFS_BG,x
        clc
        adc #1
        and #15
        sta work+OFS_BG,x
        jsr apply_shared
        jmp redraw_all

; F7: cycle the char color (0-7) of the quarter under the cursor
key_charcol:
        jsr check_reserved
        bcs kc_rts
        jsr save_undo
        jsr locate_cursor
        ldx px_ch
        lda work+OFS_COLORS,x
        clc
        adc #1
        and #7
        ora #8                    ; keep the multicolor flag
        sta work+OFS_COLORS,x
        jmp redraw_all
kc_rts:
        rts

key_next:
        lda cur_tile
        clc
        adc #1
        and #63
        sta cur_tile
        jmp tile_changed
key_prev:
        lda cur_tile
        sec
        sbc #1
        and #63
        sta cur_tile
tile_changed:
        jsr clear_msg
        jmp redraw_all

key_copy:
        jsr set_tile_ptr          ; ZP_A = tile's 32 bytes, X = first char
        ldy #31
kcp_px:
        lda (ZP_A),y
        sta clip_px,y
        dey
        bpl kcp_px
        ldy #0
kcp_col:
        lda work+OFS_COLORS,x
        sta clip_col,y
        inx
        iny
        cpy #4
        bne kcp_col
        lda #1
        sta have_clip
        ldx #<msg_copied
        ldy #>msg_copied
        jmp show_msg

key_paste:
        lda have_clip
        bne kpa_ok
        ldx #<msg_no_clip
        ldy #>msg_no_clip
        jmp show_msg
kpa_ok:
        jsr check_reserved
        bcs kpa_rts
        jsr save_undo
        jsr set_tile_ptr
        ldy #31
kpa_px:
        lda clip_px,y
        sta (ZP_A),y
        sta (ZP_B),y              ; and the VIC's copy
        dey
        bpl kpa_px
        ldy #0
kpa_col:
        lda clip_col,y
        sta work+OFS_COLORS,x
        inx
        iny
        cpy #4
        bne kpa_col
        jsr redraw_all
        ldx #<msg_pasted
        ldy #>msg_pasted
        jmp show_msg
kpa_rts:
        rts

; U: swap the undo snapshot with the tile it was taken from (so U again
; redoes). The snapshot also holds the three shared colors.
key_undo:
        lda have_undo
        bne ku_ok
        ldx #<msg_no_undo
        ldy #>msg_no_undo
        jmp show_msg
ku_ok:
        lda undo_tile
        sta cur_tile
        jsr set_tile_ptr
        ldy #31
ku_px:
        lda (ZP_A),y
        pha
        lda undo_px,y
        sta (ZP_A),y
        sta (ZP_B),y
        pla
        sta undo_px,y
        dey
        bpl ku_px
        ldy #0
ku_col:
        lda work+OFS_COLORS,x
        pha
        lda undo_col,y
        sta work+OFS_COLORS,x
        pla
        sta undo_col,y
        inx
        iny
        cpy #4
        bne ku_col
        ldx #2
ku_sh:
        lda work+OFS_BG,x
        pha
        lda undo_shared,x
        sta work+OFS_BG,x
        pla
        sta undo_shared,x
        dex
        bpl ku_sh
        jsr apply_shared
        jsr redraw_all
        ldx #<msg_undone
        ldy #>msg_undone
        jmp show_msg

key_quit:
        pla                       ; drop main_loop's jsr return address
        pla
        sei
        lda #0
        sta $d01a
        lda #$ff
        sta $d019
        lda #$31                  ; stock IRQ handler
        sta $0314
        lda #$ea
        sta $0315
        lda #$81                  ; CIA1 timer A IRQ back on
        sta $dc0d
        lda $dd00
        ora #%00000011            ; bank 0
        sta $dd00
        lda #$17                  ; screen $0400, lowercase ROM font
        sta $d018
        lda #$c8
        sta $d016
        lda #14
        sta $d020
        lda #6
        sta $d021
        lda #$80
        jsr SETMSG                ; KERNAL messages back on for BASIC
        cli
        lda #$93                  ; CLR
        jmp $ffd2                 ; CHROUT, which RTSes to BASIC

; ============================================================
; Disk: S saves, L loads "TILESET" on the current drive
; ============================================================

key_save:
        ldx #<msg_saving
        ldy #>msg_saving
        jsr show_msg
        jsr get_device
        ; scratch any old copy first (SAVE won't overwrite)
        lda #SCRATCH_LEN
        ldx #<scratch_cmd
        ldy #>scratch_cmd
        jsr SETNAM
        lda #15
        ldx dev
        ldy #15
        jsr SETLFS
        jsr OPEN
        bcs disk_no_drive
        jsr READST
        bmi disk_close_no_drive
        lda #15
        jsr CLOSE
        lda #NAME_LEN
        ldx #<file_name
        ldy #>file_name
        jsr SETNAM
        lda #1
        ldx dev
        ldy #0
        jsr SETLFS
        lda #<work
        sta ZP_A
        lda #>work
        sta ZP_A+1
        lda #ZP_A
        ldx #<(work+WS_SIZE)
        ldy #>(work+WS_SIZE)
        jsr SAVE
        bcs disk_kernal_err
        jmp show_drive_status

disk_close_no_drive:
        lda #15
        jsr CLOSE
disk_no_drive:
        ldx #<msg_no_drive
        ldy #>msg_no_drive
        jmp show_msg

; .A = KERNAL error code (carry set from LOAD/SAVE)
disk_kernal_err:
        cmp #4
        beq dke_nf
        cmp #5
        beq disk_no_drive
        ldx #<msg_disk_err
        ldy #>msg_disk_err
        jmp show_msg
dke_nf:
        ldx #<msg_not_found
        ldy #>msg_not_found
        jmp show_msg

key_load:
        ldx #<msg_loading
        ldy #>msg_loading
        jsr show_msg
        jsr get_device
        lda #NAME_LEN
        ldx #<file_name
        ldy #>file_name
        jsr SETNAM
        lda #1
        ldx dev
        ldy #0                    ; relocate to .X/.Y, ignore the file's
        jsr SETLFS                ; own load address
        lda #0
        ldx #<LOAD_BUF
        ldy #>LOAD_BUF
        jsr LOAD
        bcs disk_kernal_err
        ; right size (.X/.Y = end address) and magic?
        cpx #<(LOAD_BUF+WS_SIZE)
        bne kl_bad
        cpy #>(LOAD_BUF+WS_SIZE)
        bne kl_bad
        lda LOAD_BUF
        cmp #$54                  ; 'T'
        bne kl_bad
        lda LOAD_BUF+1
        cmp #$53                  ; 'S'
        bne kl_bad
        lda LOAD_BUF+2
        cmp #1                    ; format version
        bne kl_bad
        lda #<LOAD_BUF
        sta ZP_A
        lda #>LOAD_BUF
        sta ZP_A+1
        lda #<work
        sta ZP_B
        lda #>work
        sta ZP_B+1
        lda #<WS_SIZE
        sta cnt_lo
        lda #>WS_SIZE
        sta cnt_hi
        jsr copy_mem
        jsr sync_all_vic
        lda #0
        sta have_undo
        jsr apply_shared
        jsr redraw_all
        ldx #<msg_loaded
        ldy #>msg_loaded
        jmp show_msg
kl_bad:
        ldx #<msg_bad_file
        ldy #>msg_bad_file
        jmp show_msg

; Read the drive's error channel into the message line ("00, OK,00,00")
show_drive_status:
        lda #0
        jsr SETNAM
        lda #15
        ldx dev
        ldy #15
        jsr SETLFS
        jsr OPEN
        bcc sds_open              ; (disk_no_drive is out of branch range)
        jmp disk_no_drive
sds_open:
        ldx #15
        jsr CHKIN
        bcc sds_chkin
        jmp disk_close_no_drive
sds_chkin:
        lda #0
        sta ds_i
ds_read:
        jsr CHRIN
        cmp #$0d
        beq ds_end
        cmp #$40                  ; PETSCII letters $41-$5a -> screen
        bcc ds_store              ; codes $01-$1a
        cmp #$60
        bcs ds_store
        and #$1f
ds_store:
        ldx ds_i
        sta msg_buf,x
        inc ds_i
        cpx #MSG_LEN-1
        bcs ds_end
        jsr READST
        beq ds_read
ds_end:
        ldx ds_i
        lda #0
        sta msg_buf,x
        jsr CLRCHN
        lda #15
        jsr CLOSE
        ldx #<msg_buf
        ldy #>msg_buf
        jmp show_msg

get_device:
        lda $ba                   ; the drive this program came from
        cmp #8
        bcs gd_ok
        lda #8
gd_ok:
        sta dev
        rts

; ============================================================
; Pixels
; ============================================================

; locate_cursor: px_x/px_y = the cursor, then pix_locate
locate_cursor:
        lda cur_x
        sta px_x
        lda cur_y
        sta px_y
        ; fall through
; pix_locate: for fat pixel (px_x 0-7, px_y 0-15) of cur_tile, set px_ch
; (its char), px_shift (right-shift that brings its bit pair to bits
; 0-1) and the self-modified addresses of its byte in the working copy
; (pix_rd, pix_rd2, pix_wr) and in the VIC's copy (pix_vic).
pix_locate:
        lda px_y
        and #8
        lsr
        lsr                       ; 0 or 2: bottom half
        sta tmp
        lda px_x
        lsr
        lsr                       ; 0 or 1: right half
        ora tmp
        sta tmp
        lda cur_tile
        asl
        asl
        ora tmp
        sta px_ch                 ; char = tile*4 + quarter
        lda #0
        sta px_hi
        lda px_ch
        asl
        rol px_hi
        asl
        rol px_hi
        asl
        rol px_hi                 ; char*8
        sta px_lo
        lda px_y
        and #7
        ora px_lo
        sta px_lo                 ; + row within the char
        clc
        adc #<(work+OFS_CHARS)
        sta pix_rd+1
        sta pix_rd2+1
        sta pix_wr+1
        lda px_hi
        adc #>(work+OFS_CHARS)
        sta pix_rd+2
        sta pix_rd2+2
        sta pix_wr+2
        lda px_lo
        sta pix_vic+1             ; TILE_CHARS' low byte is 0
        lda px_hi
        clc
        adc #>TILE_CHARS
        sta pix_vic+2
        lda px_x
        and #3
        asl
        sta tmp
        lda #6
        sec
        sbc tmp
        sta px_shift              ; 6 - 2*(x mod 4)
        rts

; pix_get: .A = the pixel's bit pair (0-3); call pix_locate first
pix_get:
pix_rd:
        lda $ffff
        ldx px_shift
        beq pg_done
pg_shift:
        lsr
        dex
        bne pg_shift
pg_done:
        and #3
        rts

; pix_set: .A = new bit pair; call pix_locate first
pix_set:
        sta tmp2
        lda #3
        ldx px_shift
        beq ps_mask
ps_mask_l:
        asl
        dex
        bne ps_mask_l
ps_mask:
        eor #$ff
        sta tmp                   ; everything but this pixel's pair
        lda tmp2
        ldx px_shift
        beq ps_val
ps_val_l:
        asl
        dex
        bne ps_val_l
ps_val:
        sta tmp2
pix_rd2:
        lda $ffff
        and tmp
        ora tmp2
pix_wr:
        sta $ffff
pix_vic:
        sta $ffff
        rts

; bits_color: .A = bit pair -> its color (bg/mc1/mc2, or px_ch's char
; color for %11)
bits_color:
        cmp #3
        beq bc_char
        tax
        lda work+OFS_BG,x
        rts
bc_char:
        ldx px_ch
        lda work+OFS_COLORS,x
        and #7
        rts

; check_reserved: carry set (and a message) if cur_tile can't be edited
check_reserved:
        lda cur_tile
        cmp #RESERVED_BLANK
        beq cr_yes
        cmp #RESERVED_DIV
        beq cr_yes
        clc
        rts
cr_yes:
        ldx #<msg_reserved
        ldy #>msg_reserved
        jsr show_msg
        sec
        rts

; save_undo: snapshot cur_tile's pixels + colors and the shared colors
save_undo:
        lda cur_tile
        sta undo_tile
        jsr set_tile_ptr
        ldy #31
su_px:
        lda (ZP_A),y
        sta undo_px,y
        dey
        bpl su_px
        ldy #0
su_col:
        lda work+OFS_COLORS,x
        sta undo_col,y
        inx
        iny
        cpy #4
        bne su_col
        ldx #2
su_sh:
        lda work+OFS_BG,x
        sta undo_shared,x
        dex
        bpl su_sh
        lda #1
        sta have_undo
        rts

; set_tile_ptr: ZP_A = cur_tile's 32 bytes in the working copy, ZP_B =
; the same in the VIC's copy, .X = its first char (index into the colors)
set_tile_ptr:
        lda cur_tile
        lsr
        lsr
        lsr
        sta tmp2                  ; tile*32, high byte
        lda cur_tile
        asl
        asl
        asl
        asl
        asl                       ; tile*32, low byte
        sta tmp
        clc
        adc #<(work+OFS_CHARS)
        sta ZP_A
        lda tmp2
        adc #>(work+OFS_CHARS)
        sta ZP_A+1
        lda tmp
        sta ZP_B
        lda tmp2
        clc
        adc #>TILE_CHARS
        sta ZP_B+1
        lda cur_tile
        asl
        asl
        tax
        rts

; sync_all_vic: working charset -> $e000
sync_all_vic:
        lda #<(work+OFS_CHARS)
        sta ZP_A
        lda #>(work+OFS_CHARS)
        sta ZP_A+1
        lda #<TILE_CHARS
        sta ZP_B
        lda #>TILE_CHARS
        sta ZP_B+1
        lda #0
        sta cnt_lo
        lda #8                    ; 2048 bytes
        sta cnt_hi
        ; fall through
; copy_mem: cnt_hi:cnt_lo bytes from (ZP_A) to (ZP_B)
copy_mem:
        ldy #0
cm_loop:
        lda cnt_lo
        ora cnt_hi
        beq cm_done
        lda (ZP_A),y
        sta (ZP_B),y
        inc ZP_A
        bne cm_a
        inc ZP_A+1
cm_a:
        inc ZP_B
        bne cm_b
        inc ZP_B+1
cm_b:
        lda cnt_lo
        bne cm_c
        dec cnt_hi
cm_c:
        dec cnt_lo
        jmp cm_loop
cm_done:
        rts

apply_shared:
        lda work+OFS_MC1
        sta $d022
        lda work+OFS_MC2
        sta $d023
        rts                       ; $d021: the raster IRQs set it

; ============================================================
; Drawing
; ============================================================

redraw_all:
        jsr draw_palette
        jsr draw_preview
        jsr draw_divider
        jsr draw_grid
        jsr draw_panel_values
        lda #1
        sta blink_on
        jmp draw_cursor_cell

; at: .X = row, .A = column -> ZP_A = screen address, ZP_B = color RAM
at:
        clc
        adc row_lo,x
        sta ZP_A
        sta ZP_B
        lda row_hi,x
        adc #0
        sta ZP_A+1
        clc
        adc #CLR_DELTA
        sta ZP_B+1
        rts

build_rows:
        lda #<SCREEN
        sta tmp
        lda #>SCREEN
        sta tmp2
        ldx #0
br_loop:
        lda tmp
        sta row_lo,x
        lda tmp2
        sta row_hi,x
        lda tmp
        clc
        adc #40
        sta tmp
        bcc br_next
        inc tmp2
br_next:
        inx
        cpx #25
        bne br_loop
        rts

; Palette: char for row r, column c = (r>>1)*64 + (c>>1)*4 + (r&1)*2 + (c&1)
draw_palette:
        ldx #0
dp_row:
        stx loop_r
        txa
        and #1
        asl
        sta tmp
        txa
        lsr
        asl
        asl
        asl
        asl
        asl
        asl
        ora tmp
        sta dp_base
        lda #0
        jsr at
        ldy #0
dp_col:
        tya
        and #1
        sta tmp
        tya
        lsr
        asl
        asl
        ora tmp
        ora dp_base
        sta (ZP_A),y
        tax
        lda work+OFS_COLORS,x
        sta (ZP_B),y
        iny
        cpy #32
        bne dp_col
        lda #BLANK                ; gap before the preview
        sta (ZP_A),y
        iny
        sta (ZP_A),y
        lda #0
        sta (ZP_B),y
        dey
        sta (ZP_B),y
        ldx loop_r
        inx
        cpx #8
        bne dp_row
        rts

; Preview: cur_tile repeated 3 across, 4 down
draw_preview:
        lda cur_tile
        asl
        asl
        sta dp_base
        ldx #0
pv_row:
        stx loop_r
        txa
        and #1
        asl
        ora dp_base
        sta tmp
        lda #PREVIEW_COL
        jsr at
        ldy #0
pv_col:
        tya
        and #1
        ora tmp
        sta (ZP_A),y
        tax
        lda work+OFS_COLORS,x
        sta (ZP_B),y
        iny
        cpy #6
        bne pv_col
        ldx loop_r
        inx
        cpx #8
        bne pv_row
        rts

; Divider: solid black, white under the selected tile's two columns
draw_divider:
        ldx #DIV_ROW
        lda #0
        jsr at
        ldy #39
dd_loop:
        lda #SOLID
        sta (ZP_A),y
        lda #0
        sta (ZP_B),y
        dey
        bpl dd_loop
        lda cur_tile
        and #15
        asl
        tay
        lda #1
        sta (ZP_B),y
        iny
        sta (ZP_B),y
        rts

; Zoomed tile: fat pixel (x, y) = 2 solid cells at row GRID_ROW+y, col 2x
draw_grid:
        lda #0
        sta grid_y
dg_row:
        lda #0
        sta grid_x
dg_px:
        lda grid_x
        sta px_x
        lda grid_y
        sta px_y
        jsr pix_locate
        jsr pix_get
        jsr bits_color
        sta tmp3
        lda grid_y
        clc
        adc #GRID_ROW
        tax
        lda grid_x
        asl
        jsr at
        ldy #0
        lda #SOLID
        sta (ZP_A),y
        iny
        sta (ZP_A),y
        lda tmp3
        sta (ZP_B),y
        dey
        sta (ZP_B),y
        inc grid_x
        lda grid_x
        cmp #8
        bne dg_px
        inc grid_y
        lda grid_y
        cmp #16
        bne dg_row
        rts

; The cursor's two cells: checkerboard (blink_on) or the pixel itself
draw_cursor_cell:
        lda cur_y
        clc
        adc #GRID_ROW
        tax
        lda cur_x
        asl
        jsr at
        lda blink_on
        beq dcc_pix
        ldx #1                    ; white
        lda #CURSOR_CHAR
        bne dcc_put
dcc_pix:
        jsr locate_cursor
        jsr pix_get
        jsr bits_color
        tax
        lda #SOLID
dcc_put:
        ldy #0
        sta (ZP_A),y
        iny
        sta (ZP_A),y
        txa
        sta (ZP_B),y
        dey
        sta (ZP_B),y
        rts

cursor_off:
        lda #0
        sta blink_on
        jmp draw_cursor_cell

; blink: toggle the cursor every 16 frames
blink:
        lda frame
        and #$10
        cmp last_phase
        beq bl_rts
        sta last_phase
        lda blink_on
        eor #1
        sta blink_on
        jmp draw_cursor_cell
bl_rts:
        rts

; Panel values: tile number, pens (selected one reversed) + swatches, the
; shared colors and the char color under the cursor, each with a swatch
draw_panel_values:
        jsr locate_cursor         ; px_ch = char under the cursor
        ldx px_ch
        lda work+OFS_COLORS,x
        and #7
        sta under_col
        ldx #9
        lda #24
        jsr at
        lda cur_tile
        ldy #0
        jsr dec2
        ldx #10
        lda #23
        jsr at
        ldy #0
pn_digit:
        tya
        clc
        adc #$31                  ; '1'
        cpy pen
        bne pn_put
        ora #$80                  ; reversed
pn_put:
        sta (ZP_A),y
        lda #1
        sta (ZP_B),y
        iny
        cpy #4
        bne pn_digit
        ldx #11
        lda #23
        jsr at
        ldy #0
pn_swatch:
        lda #SOLID
        sta (ZP_A),y
        cpy #3
        beq pn_char
        lda work+OFS_BG,y
        jmp pn_col
pn_char:
        lda under_col
pn_col:
        sta (ZP_B),y
        iny
        cpy #4
        bne pn_swatch
        ; rows 13-16: bg, mc1, mc2, char color
        lda #0
        sta loop_r
pv_line:
        lda loop_r
        clc
        adc #13
        tax
        lda #26
        jsr at
        ldx loop_r
        cpx #3
        beq pv_under
        lda work+OFS_BG,x
        jmp pv_have
pv_under:
        lda under_col
pv_have:
        sta tmp3
        ldy #0
        jsr dec2
        ldy #3
        lda #SOLID
        sta (ZP_A),y
        lda tmp3
        sta (ZP_B),y
        inc loop_r
        lda loop_r
        cmp #4
        bne pv_line
        rts

; dec2: .A (0-99) as two white digits at (ZP_A),y and (ZP_A),y+1
dec2:
        ldx #$2f
d2_tens:
        inx
        sec
        sbc #10
        bcs d2_tens
        adc #$3a                  ; undo the last subtract, + '0'
        pha
        txa
        sta (ZP_A),y
        lda #1
        sta (ZP_B),y
        iny
        pla
        sta (ZP_A),y
        lda #1
        sta (ZP_B),y
        rts

; print_list: .X/.Y = a list of (row, col, color, text..., 0), ended by $ff
print_list:
        stx pl_src+1
        sty pl_src+2
pl_entry:
        jsr pl_get
        cmp #$ff
        beq pl_done
        tax
        jsr pl_get
        jsr at
        jsr pl_get
        sta pl_color
        ldy #0
pl_char:
        jsr pl_get
        beq pl_entry
        sta (ZP_A),y
        lda pl_color
        sta (ZP_B),y
        iny
        bne pl_char
pl_done:
        rts

; pl_get: next byte from pl_src, Z set if it's 0 (.X/.Y untouched)
pl_get:
pl_src:
        lda $ffff
        inc pl_src+1
        bne pl_get_z
        inc pl_src+2
pl_get_z:
        cmp #0
        rts

; show_msg: .X/.Y = 0-terminated screen codes for the message line
show_msg:
        stx pl_src+1
        sty pl_src+2
        jsr clear_msg
        ldy #0
sm_char:
        jsr pl_get
        beq sm_done
        sta (ZP_A),y
        lda #7                    ; yellow
        sta (ZP_B),y
        iny
        cpy #MSG_LEN
        bne sm_char
sm_done:
        rts

; clear_msg: blank the message line (leaves ZP_A/ZP_B pointing at it)
clear_msg:
        ldx #MSG_ROW
        lda #PANEL_COL
        jsr at
        ldy #MSG_LEN-1
        lda #BLANK
cm_blank:
        sta (ZP_A),y
        dey
        bpl cm_blank
        rts

; ============================================================
; Raster IRQs (same split as tile_demo.asm)
; ============================================================

irq_split:
        lda #D018_TEXT
        sta $d018
        lda #D016_TEXT
        sta $d016
        lda #0
        sta $d021
        lda #<irq_top
        sta $0314
        lda #>irq_top
        sta $0315
        lda #TOP_LINE
        sta $d012
        lda #1
        sta $d019
        jmp $ea81

irq_top:
        lda #D018_TILES
        sta $d018
        lda #D016_TILES
        sta $d016
        lda work+OFS_BG
        sta $d021
        lda #<irq_split
        sta $0314
        lda #>irq_split
        sta $0315
        lda #SPLIT_LINE
        sta $d012
        lda #1
        sta $d019
        jsr SCNKEY
        inc frame
        jmp $ea81

; ============================================================
; Data
; ============================================================

; key -> handler
key_codes:
        byte $1d,$9d,$11,$91,$20,$31,$32,$33,$34,$45
        byte $85,$86,$87,$88,$2b,$2d,$43,$56,$55,$53
        byte $4c,$51,$03
key_codes_end:
NUM_KEYS = key_codes_end - key_codes
key_lo:
        byte <key_right,<key_left,<key_down,<key_up,<key_plot
        byte <key_pen,<key_pen,<key_pen,<key_pen,<key_pick
        byte <key_shared,<key_shared,<key_shared,<key_charcol
        byte <key_next,<key_prev,<key_copy,<key_paste,<key_undo
        byte <key_save,<key_load,<key_quit,<key_quit
key_hi:
        byte >key_right,>key_left,>key_down,>key_up,>key_plot
        byte >key_pen,>key_pen,>key_pen,>key_pen,>key_pick
        byte >key_shared,>key_shared,>key_shared,>key_charcol
        byte >key_next,>key_prev,>key_copy,>key_paste,>key_undo
        byte >key_save,>key_load,>key_quit,>key_quit

; "TILESET" -- unshifted PETSCII, what LOAD"TILESET",8 typed at the
; power-up screen produces
file_name:
        byte $54,$49,$4c,$45,$53,$45,$54
NAME_LEN = 7
scratch_cmd:
        byte $53,$30,$3a,$54,$49,$4c,$45,$53,$45,$54   ; "S0:TILESET"
SCRATCH_LEN = 10

{alpha:pokealt}
panel_labels:
        byte 9,PANEL_COL,15
        ascii "Tile"
        byte 0
        byte 10,PANEL_COL,15
        ascii "Pen"
        byte 0
        byte 13,PANEL_COL,15
        ascii "F1 bg"
        byte 0
        byte 14,PANEL_COL,15
        ascii "F3 mc1"
        byte 0
        byte 15,PANEL_COL,15
        ascii "F5 mc2"
        byte 0
        byte 16,PANEL_COL,15
        ascii "F7 char"
        byte 0
        byte 18,PANEL_COL,12
        ascii "CRSR move  SPC plot"
        byte 0
        byte 19,PANEL_COL,12
        ascii "1-4 pen    E pick"
        byte 0
        byte 20,PANEL_COL,12
        ascii "+/- tile   U undo"
        byte 0
        byte 21,PANEL_COL,12
        ascii "C copy     V paste"
        byte 0
        byte 22,PANEL_COL,12
        ascii "S save L load Q quit"
        byte 0
        byte $ff

msg_hello:
        ascii "Tile editor ready."
        byte 0
msg_reserved:
        ascii "Tile reserved (split)."
        byte 0
msg_copied:
        ascii "Tile copied."
        byte 0
msg_no_clip:
        ascii "Nothing copied yet."
        byte 0
msg_pasted:
        ascii "Tile pasted."
        byte 0
msg_no_undo:
        ascii "Nothing to undo."
        byte 0
msg_undone:
        ascii "Undone. U again: redo"
        byte 0
msg_saving:
        ascii "Saving..."
        byte 0
msg_loading:
        ascii "Loading..."
        byte 0
msg_loaded:
        ascii "Loaded."
        byte 0
msg_no_drive:
        ascii "No drive?"
        byte 0
msg_not_found:
        ascii "TILESET not found."
        byte 0
msg_disk_err:
        ascii "Disk error."
        byte 0
msg_bad_file:
        ascii "Not a TILESET file."
        byte 0
{alpha:normal}

; state
cur_tile:       byte 0
cur_x:          byte 0
cur_y:          byte 0
pen:            byte 3            ; char color: the one most touch-ups want
blink_on:       byte 0
last_phase:     byte 0
frame:          byte 0
last_key:       byte 0
have_clip:      byte 0
have_undo:      byte 0
undo_tile:      byte 0
dev:            byte 8
under_col:      byte 0

; scratch
tmp:            byte 0
tmp2:           byte 0
tmp3:           byte 0
px_x:           byte 0
px_y:           byte 0
px_ch:          byte 0
px_lo:          byte 0
px_hi:          byte 0
px_shift:       byte 0
grid_x:         byte 0
grid_y:         byte 0
loop_r:         byte 0
dp_base:        byte 0
pl_color:       byte 0
cnt_lo:         byte 0
cnt_hi:         byte 0
ds_i:           byte 0

row_lo:         area 25,0
row_hi:         area 25,0
undo_px:        area 32,0
undo_col:       area 4,0
undo_shared:    area 3,0
clip_px:        area 32,0
clip_col:       area 4,0
msg_buf:        area MSG_LEN+1,0

; The TILESET block: the default set, then whatever L loads / S saves
work:
        embed "default_tileset.bin"
