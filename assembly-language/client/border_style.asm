; border_style.asm -- the C64 client's Border style: Single (the Gothic
; box glyphs gothic_charset ships with) or Double (CP437-style double
; lines), picked in Video Settings (config_menu.asm) and saved in
; TADA64.CFG's config_settings (CFG_BORDER_STYLE). Ryan's ask,
; 2026-10-02. {include:}d by tada-client.asm -- resident, not part of
; CONFIG.MNU, so a saved Double can be put back at boot without loading
; the popup; CONFIG.MNU reaches set_border_style through
; JT_SET_BORDER_STYLE.
;
; The 11 box-drawing screen codes in bs_glyph_codes get redefined in the
; charset itself (CHARGEN_DEST, the RAM behind $d000), so every box on
; screen -- server tables and popup frames alike -- switches at once.
; The Gothic originals are backed up at boot (bs_backup_gothic) to
; BORDER_BACKUP, in overlay RAM above every module's image -- see
; constants.asm's BORDER_STATE comment.
;
; No macro-preprocessor directives, so (like constants.asm and gothic-
; charset.asm) included directly, not via a _pp.asm copy.

BS_GLYPH_COUNT = 11            ; bs_glyph_codes' entries, by hand (see
                               ; constants.asm's BORDER_STATE_END)

; --- bs_backup_gothic: copy the Gothic box glyphs to BORDER_BACKUP ---
; Boot only, from switch_to_bank3_with_charset, while gothic_charset's
; source image (BACKUP_CHARS) is still intact -- it becomes the screen
; backup at the first popup -- so this reads plain RAM: no I/O banking
; needed. Leaves BORDER_CUR_STYLE = 0, Single, which is what the charset
; was just loaded with. A glyph's offset is code*8; every code here is
; under $80, so that's lo = code<<3, hi = code>>5.
bs_backup_gothic:
        lda #<BORDER_BACKUP
        sta bsb_dst+1
        lda #>BORDER_BACKUP
        sta bsb_dst+2
        ldy #0
bsb_glyph:
        lda bs_glyph_codes,y
        lsr
        lsr
        lsr
        lsr
        lsr
        sta bs_offset_hi
        lda bs_glyph_codes,y
        asl
        asl
        asl
        clc
        adc #<gothic_charset
        sta bsb_src+1
        lda bs_offset_hi
        adc #>gothic_charset      ; + the carry out of the low byte
        sta bsb_src+2
        ldx #0
bsb_byte:
bsb_src:
        lda $ffff,x
bsb_dst:
        sta $ffff,x
        inx
        cpx #8
        bne bsb_byte
        lda bsb_dst+1             ; next glyph's 8 bytes in the backup
        clc
        adc #8
        sta bsb_dst+1
        bcc bsb_no_carry
        inc bsb_dst+2
bsb_no_carry:
        iny
        cpy #BS_GLYPH_COUNT
        bne bsb_glyph
        lda #0
        sta BORDER_CUR_STYLE
        rts

; --- set_border_style: .A = 0 Single, anything else Double ---
; JT_SET_BORDER_STYLE. Copies that style's glyphs into the charset if
; they aren't the ones already there, and records it in
; BORDER_CUR_STYLE. Any nonzero .A counts as Double, so a stray byte in
; an old or hand-edited TADA64.CFG can't index past the two styles.
; Called at boot (start:, once SwiftLink is up -- run_under_io holds its
; NMI off) with the saved style, and by CONFIG.MNU for its live
; preview, Save and Cancel. Clobbers .A/.X/.Y.
set_border_style:
        cmp #0
        beq sbs_have
        lda #1
sbs_have:
        cmp BORDER_CUR_STYLE
        beq sbs_rts
        sta BORDER_CUR_STYLE
        cmp #0
        bne sbs_double
        lda #<BORDER_BACKUP       ; Single: the Gothic originals
        sta bst_src+1
        lda #>BORDER_BACKUP
        sta bst_src+2
        jmp sbs_copy
sbs_double:
        lda #<bs_double_glyphs
        sta bst_src+1
        lda #>bs_double_glyphs
        sta bst_src+2
sbs_copy:
        ldx #<bs_transfer
        ldy #>bs_transfer
        jmp run_under_io          ; tail call
sbs_rts:
        rts

; bs_transfer: the GLYPH_COUNT glyphs at bst_src -> the charset. Runs
; only via run_under_io (all RAM mapped, no I/O, no KERNAL). CHARGEN_DEST
; is page-aligned ($d000), so a glyph's address is just lo = code<<3,
; hi = >CHARGEN_DEST + code>>5.
bs_transfer:
        ldy #0
bst_glyph:
        lda bs_glyph_codes,y
        asl
        asl
        asl
        sta bst_dst+1
        lda bs_glyph_codes,y
        lsr
        lsr
        lsr
        lsr
        lsr
        clc
        adc #>CHARGEN_DEST
        sta bst_dst+2
        ldx #0
bst_byte:
bst_src:
        lda $ffff,x
bst_dst:
        sta $ffff,x
        inx
        cpx #8
        bne bst_byte
        lda bst_src+1             ; next glyph's 8 bytes in the source
        clc
        adc #8
        sta bst_src+1
        bcc bst_no_carry
        inc bst_src+2
bst_no_carry:
        iny
        cpy #BS_GLYPH_COUNT
        bne bst_glyph
        rts

bs_offset_hi:
        byte 0

; The 11 box-drawing screen codes border style redefines -- table.py's
; PETSCII Border set server-side, plus the popups' own frames. Order
; matters: BORDER_BACKUP and bs_double_glyphs both hold one glyph per
; entry, in this order. BS_GLYPH_COUNT must match by hand.
bs_glyph_codes:
        byte $40, $5b, $5d, $6b, $6d, $6e, $70, $71, $72, $73, $7d

; Double style: CP437's double-line box set (U+2550-256C), drawn on the
; same 8x8 grid -- vertical lines on columns 2 and 5, straddling the
; Gothic single line's columns 3-4; horizontal lines on rows 2 and 4,
; one blank row between (Ryan's call, 2026-10-02: the lower line on row
; 5 sat a pixel too low), so a mix of the two styles (e.g. a server
; table drawn while the other style was in place) still meets near the
; middle of each cell. Same `bits` pseudo op as gothic-charset.asm.
bs_double_glyphs:
;   $40 ═ horizontal
        bits ........
        bits ........
        bits ********
        bits ........
        bits ********
        bits ........
        bits ........
        bits ........

;   $5b ╬ cross
        bits ..*..*..
        bits ..*..*..
        bits ***..***
        bits ........
        bits ***..***
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..

;   $5d ║ vertical
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..

;   $6b ╠ left tee
        bits ..*..*..
        bits ..*..*..
        bits ..*..***
        bits ..*.....
        bits ..*..***
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..

;   $6d ╚ bottom-left
        bits ..*..*..
        bits ..*..*..
        bits ..*..***
        bits ..*.....
        bits ..******
        bits ........
        bits ........
        bits ........

;   $6e ╗ top-right
        bits ........
        bits ........
        bits ******..
        bits .....*..
        bits ***..*..
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..

;   $70 ╔ top-left
        bits ........
        bits ........
        bits ..******
        bits ..*.....
        bits ..*..***
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..

;   $71 ╩ bottom tee
        bits ..*..*..
        bits ..*..*..
        bits ***..***
        bits ........
        bits ********
        bits ........
        bits ........
        bits ........

;   $72 ╦ top tee
        bits ........
        bits ........
        bits ********
        bits ........
        bits ***..***
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..

;   $73 ╣ right tee
        bits ..*..*..
        bits ..*..*..
        bits ***..*..
        bits .....*..
        bits ***..*..
        bits ..*..*..
        bits ..*..*..
        bits ..*..*..

;   $7d ╝ bottom-right
        bits ..*..*..
        bits ..*..*..
        bits ***..*..
        bits .....*..
        bits ******..
        bits ........
        bits ........
        bits ........
