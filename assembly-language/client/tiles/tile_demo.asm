; tile_demo.asm -- scroll a multicolor tile map around with the cursor
; keys, with a text status line under it in the ROM's lowercase font:
; both charsets on screen at once via a raster split. First hands-on
; test of TILESET_MEMORY_MAP.md (Ryan's ask, 2026-10-02).
;
; Standalone (no SwiftLink, no client), so it shows the split and the
; art, not the NMI/CIA-tick jitter the memory map worries about.
;
; Data comes from make_demo_map.py: demo_charset.bin (the tile charset),
; demo_map.bin / demo_colors.bin (MAP_W x MAP_H char codes and color RAM
; values), tile_demo_data.asm (sizes + shared colors). Rebuild those, then
; `make` here.
;
; Memory, per TILESET_MEMORY_MAP.md's C64 map (VIC bank 3):
;   $c400        screen
;   $e000-$e7ff  tile charset   -- RAM under the KERNAL: CPU writes go
;   $e800-$efff  text font         straight through, no $01 banking
;   rows 0-22    map window, multicolor, tile charset
;   row 23       divider: DIVIDER_CHAR ($a0) in color 0 is solid black in
;                both charsets and both modes, so the moment the split
;                switches charsets mid-row can't show
;   row 24       status line, hires, text font
;
; Interrupts: CIA1's timer IRQ is switched off; two raster IRQs alternate
; through $0314 (the KERNAL entry stub has already pushed A/X/Y, and
; $ea81 pulls them back and RTIs):
;   SPLIT_LINE (row 23's first line) -> text font, multicolor off, black bg
;   TOP_LINE (bottom border)         -> tile charset, multicolor on, map bg;
;                                       KERNAL SCNKEY (keyboard + repeat),
;                                       frame counter

{include:tile_demo_data.asm}

SCREEN          = $c400
COLOR_RAM       = $d800
TILE_CHARS      = $e000
TEXT_CHARS      = $e800
VIEW_ROWS       = 23
DIVIDER_OFFSET  = 920            ; row 23 * 40
STATUS_OFFSET   = 960            ; row 24 * 40
NUM_COL         = 34             ; where "xx,yy" goes on the status row

D018_TILES      = $18            ; screen $c400 (1<<4) | chars $e000 (4<<1)
D018_TEXT       = $1a            ; screen $c400        | chars $e800 (5<<1)
D016_TILES      = $18            ; multicolor on, 40 columns
D016_TEXT       = $08            ; multicolor off, 40 columns
SPLIT_LINE      = 235            ; 51 + 8*23
TOP_LINE        = 251            ; first line after row 24

KEY_UP          = $91
KEY_DOWN        = $11
KEY_LEFT        = $9d
KEY_RIGHT       = $1d
KEY_Q           = $51            ; 'q' (and 'Q' unshifted) from GETIN
KEY_STOP        = $03

SCNKEY          = $ff9f
GETIN           = $ffe4

        orig $0801
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00   ; 10 SYS2061

start:
        sei

        ; --- tile charset -> $e000 (writes reach the RAM under the KERNAL) ---
        ldx #0
copy_tiles:
        lda demo_charset,x
        sta TILE_CHARS,x
        lda demo_charset+$100,x
        sta TILE_CHARS+$100,x
        lda demo_charset+$200,x
        sta TILE_CHARS+$200,x
        lda demo_charset+$300,x
        sta TILE_CHARS+$300,x
        lda demo_charset+$400,x
        sta TILE_CHARS+$400,x
        lda demo_charset+$500,x
        sta TILE_CHARS+$500,x
        lda demo_charset+$600,x
        sta TILE_CHARS+$600,x
        lda demo_charset+$700,x
        sta TILE_CHARS+$700,x
        inx
        bne copy_tiles

        ; --- ROM lowercase font -> $e800 ---
        lda #$33                  ; character ROM in at $d000 for reads
        sta $01
copy_font:
        lda $d800,x               ; ROM's second (upper/lowercase) set
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

        ; --- VIC: bank 3, colors, divider and status rows ---
        lda $dd00
        and #%11111100            ; bank 3 (inverted encoding)
        sta $dd00
        lda #D018_TILES
        sta $d018
        lda #D016_TILES
        sta $d016
        lda #0
        sta $d020
        lda #MAP_BG
        sta $d021
        lda #MAP_MC1
        sta $d022
        lda #MAP_MC2
        sta $d023

        ldx #39
init_rows:
        lda #DIVIDER_CHAR
        sta SCREEN+DIVIDER_OFFSET,x
        lda #0                    ; color 0, multicolor flag off: solid black
        sta COLOR_RAM+DIVIDER_OFFSET,x
        lda status_text,x
        sta SCREEN+STATUS_OFFSET,x
        lda #1                    ; white
        sta COLOR_RAM+STATUS_OFFSET,x
        dex
        bpl init_rows

        ; --- interrupts: CIA1 timer off, raster IRQ on ---
        lda #$7f
        sta $dc0d
        lda $dc0d                 ; ack anything pending
        lda #<irq_split
        sta $0314
        lda #>irq_split
        sta $0315
        lda $d011
        and #$7f                  ; raster compare bit 8 = 0 (both lines < 256)
        sta $d011
        lda #SPLIT_LINE
        sta $d012
        lda #1
        sta $d01a
        sta $d019
        cli

        jsr draw_view

; --- main loop: one key per frame, redraw after the next TOP_LINE IRQ ---
main_loop:
        lda frame
wait_frame:
        cmp frame
        beq wait_frame
        jsr GETIN
        beq main_loop
        cmp #KEY_RIGHT
        beq go_right
        cmp #KEY_LEFT
        beq go_left
        cmp #KEY_DOWN
        beq go_down
        cmp #KEY_UP
        beq go_up
        cmp #KEY_Q
        beq quit
        cmp #KEY_STOP
        beq quit
        jmp main_loop

go_right:
        lda view_x
        cmp #MAP_W-40
        bcs main_loop
        inc view_x
        jmp moved
go_left:
        lda view_x
        beq main_loop
        dec view_x
        jmp moved
go_down:
        lda view_y
        cmp #MAP_H-VIEW_ROWS
        bcs main_loop
        inc view_y
        jmp moved
go_up:
        lda view_y
        beq main_loop
        dec view_y
moved:
        jsr draw_view
        jmp main_loop

; --- quit: put back the stock VIC/IRQ setup and return to BASIC ---
quit:
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
        cli
        lda #$93                  ; CLR
        jmp $ffd2                 ; CHROUT, which RTSes to BASIC

; --- draw_view: rows 0-22 from the map at (view_x, view_y) ---
; Self-modified absolute,Y addresses instead of zero-page pointers:
; dv_map/dv_col walk the map and color arrays (MAP_W apart per row),
; dv_scr/dv_clr walk screen and color RAM (40 apart).
draw_view:
        ; map offset = view_y * MAP_W + view_x
        lda #<demo_map
        sta dv_map+1
        lda #>demo_map
        sta dv_map+2
        lda #<demo_colors
        sta dv_col+1
        lda #>demo_colors
        sta dv_col+2
        ldx view_y
        beq dv_add_x
dv_mul:
        jsr dv_next_src_row
        dex
        bne dv_mul
dv_add_x:
        lda dv_map+1
        clc
        adc view_x
        sta dv_map+1
        bcc dv_add_x2
        inc dv_map+2
dv_add_x2:
        lda dv_col+1
        clc
        adc view_x
        sta dv_col+1
        bcc dv_dest
        inc dv_col+2
dv_dest:
        lda #<SCREEN
        sta dv_scr+1
        lda #>SCREEN
        sta dv_scr+2
        lda #<COLOR_RAM
        sta dv_clr+1
        lda #>COLOR_RAM
        sta dv_clr+2
        ldx #VIEW_ROWS
dv_row:
        ldy #39
dv_cell:
dv_map:
        lda $ffff,y
dv_scr:
        sta $ffff,y
dv_col:
        lda $ffff,y
dv_clr:
        sta $ffff,y
        dey
        bpl dv_cell
        jsr dv_next_src_row
        lda dv_scr+1
        clc
        adc #40
        sta dv_scr+1
        sta dv_clr+1              ; same low byte: $c400/$d800 both $00
        bcc dv_row_done
        inc dv_scr+2
        inc dv_clr+2
dv_row_done:
        dex
        bne dv_row
        jmp print_pos

; advance both source pointers by one map row (MAP_W bytes)
dv_next_src_row:
        lda dv_map+1
        clc
        adc #MAP_W
        sta dv_map+1
        bcc dv_nsr_col
        inc dv_map+2
dv_nsr_col:
        lda dv_col+1
        clc
        adc #MAP_W
        sta dv_col+1
        bcc dv_nsr_done
        inc dv_col+2
dv_nsr_done:
        rts

; --- print_pos: "xx,yy" at the end of the status row ---
print_pos:
        lda view_x
        ldx #NUM_COL
        jsr print_dec2
        lda #$2c                  ; ','
        sta SCREEN+STATUS_OFFSET+NUM_COL+2
        lda view_y
        ldx #NUM_COL+3
        ; fall through
; .A (0-99) as two decimal digits at status row column .X
print_dec2:
        ldy #$2f                  ; tens digit, screen code '0'-1
pd_tens:
        iny
        sec
        sbc #10
        bcs pd_tens
        adc #$3a                  ; undo the last subtract, + screen code '0'
        sta SCREEN+STATUS_OFFSET+1,x
        tya
        sta SCREEN+STATUS_OFFSET,x
        rts

; --- raster IRQs ---
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
        sta $d019                 ; ack raster
        jmp $ea81                 ; pull Y/X/A, rti

irq_top:
        lda #D018_TILES
        sta $d018
        lda #D016_TILES
        sta $d016
        lda #MAP_BG
        sta $d021
        lda #<irq_split
        sta $0314
        lda #>irq_split
        sta $0315
        lda #SPLIT_LINE
        sta $d012
        lda #1
        sta $d019
        jsr SCNKEY                ; keyboard + KERNAL key repeat
        inc frame
        jmp $ea81

; --- data ---
view_x:
        byte 0
view_y:
        byte 0
frame:
        byte 0

{alpha:pokealt}
status_text:
        ascii "Tile demo: CRSR scrolls, Q quits  00,00 "
{alpha:normal}

demo_charset:
        embed "demo_charset.bin"
demo_map:
        embed "demo_map.bin"
demo_colors:
        embed "demo_colors.bin"
