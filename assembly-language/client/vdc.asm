; vdc.asm -- 8563 VDC (80-column chip) primitives for client-128.asm.
;
; Modeled on the C128 screen editor's own VDC code, read straight out of
; VICE's kernal-318020-05.bin ($C000-$FFFF) on 2026-09-29 rather than
; recalled from references -- see 128_CLIENT_MECHANICS.md's "80-column
; (VDC) text output" section for the full disassembly notes:
;   $CDCC  write register: stx $d600 / bit $d600 (wait bit 7) / sta $d601
;   $CDDA  read register:  same handshake, lda $d601
;   $C40D  move one screen line (80-column branch at $C436): R24 bit 7 set
;          (COPY), R18/R19 = destination, R32/R33 = source, R30 = count --
;          writing R30 is what starts the copy. Done twice, once for the
;          characters and once for the attributes.
;   $C4A5  clear one screen line (80-column branch at $C4C0): R24 bit 7
;          clear (WRITE, i.e. fill), R18/R19 = start, one byte to R31 by
;          hand, then R30 = remaining count repeats it. $C53E then reads
;          R18/R19 back and tops up one byte at a time until the update
;          address reaches the end -- vdc_fill keeps that check.
;
; Handshake note: the editor never SEIs around these accesses, and its IRQ
; ($C194) never touches $D600/$D601 at all -- the only IRQ-side screen
; work is the 40-column cursor blink ($C6E7), which returns immediately
; when $D7 bit 7 says 80-column mode is active. So nothing here masks
; interrupts either; a future NMI/IRQ task must stay off the VDC (or save
; and restore $D600's selected register) for that to remain true.
;
; A block copy/fill keeps the chip busy after R30 is written; the status
; bit (bit 7 of $D600) stays clear until it finishes, so the very next
; vdc_write_reg/vdc_read_reg waits for it on its own -- the same reason
; the editor can chain R30 writes back to back.
;
; Symbols here are real c64list `=` assignments (not {const:}s), so they
; resolve inside every file client-128.asm {include:}s.

VDC_ADDR_REG      = $d600   ; write: register select; read bit 7: ready
VDC_DATA_REG      = $d601

VDC_R_CURSOR_MODE = $0a     ; bits 6-5: 00 solid, 01 off, 10/11 blink
VDC_R_UPDATE_HI   = $12     ; R18/R19: update (read/write) address
VDC_R_UPDATE_LO   = $13
VDC_R_BLOCK_CTRL  = $18     ; R24 bit 7: 1 = block COPY, 0 = block WRITE
VDC_R_WORD_COUNT  = $1e     ; R30: writing it runs the block op
VDC_R_DATA        = $1f     ; R31: data at the update address, which then
                            ; advances by one (reads and writes alike)
VDC_R_COPY_SRC_HI = $20     ; R32/R33: block copy source address
VDC_R_COPY_SRC_LO = $21

VDC_CURSOR_OFF    = $20     ; R10 value the editor itself uses ($CDAE)

; --- vdc_write_reg: X = register, A = value. Preserves A, X and Y. ---
vdc_write_reg:
        stx VDC_ADDR_REG
vdc_write_wait:
        bit VDC_ADDR_REG
        bpl vdc_write_wait
        sta VDC_DATA_REG
        rts

; --- vdc_read_reg: X = register -> A. Preserves X and Y. ---
vdc_read_reg:
        stx VDC_ADDR_REG
vdc_read_wait:
        bit VDC_ADDR_REG
        bpl vdc_read_wait
        lda VDC_DATA_REG
        rts

; --- vdc_set_update: A = high byte, Y = low byte -> R18/R19. Clobbers
; A/X, preserves Y. ---
vdc_set_update:
        ldx #VDC_R_UPDATE_HI
        jsr vdc_write_reg
        inx                     ; R19
        tya
        jmp vdc_write_reg

; --- vdc_put / vdc_get: one byte to/from R31 at the update address,
; which then advances. X ends up VDC_R_DATA; A/Y as documented. ---
vdc_put:
        ldx #VDC_R_DATA
        jmp vdc_write_reg

vdc_get:
        ldx #VDC_R_DATA
        jmp vdc_read_reg

; --- vdc_copy: VDC-internal block copy of vdc_count bytes from vdc_src
; to vdc_dst, ascending -- safe whenever vdc_dst <= vdc_src or the two
; ranges don't overlap (copying a region DOWN in memory, i.e. scrolling
; text UP, is fine; copying it up over itself is not -- do that a row at
; a time from the bottom, see sb_shift_down). No CPU byte traffic: the
; chip moves the data itself. Consumes vdc_count. ---
vdc_copy:
        ldx #VDC_R_BLOCK_CTRL
        jsr vdc_read_reg
        ora #$80                ; COPY
        jsr vdc_write_reg
        lda vdc_dst+1
        ldy vdc_dst
        jsr vdc_set_update
        ldx #VDC_R_COPY_SRC_HI
        lda vdc_src+1
        jsr vdc_write_reg
        inx                     ; R33
        lda vdc_src
        jsr vdc_write_reg
        jmp vdc_run_count

; --- vdc_fill: fill vdc_count (>= 1) bytes at vdc_dst with A. Consumes
; vdc_count. ---
vdc_fill:
        sta vdc_fill_val
        clc                     ; end address, for the ROM-style top-up
        lda vdc_dst             ; check below
        adc vdc_count
        sta vdc_end
        lda vdc_dst+1
        adc vdc_count+1
        sta vdc_end+1
        ldx #VDC_R_BLOCK_CTRL
        jsr vdc_read_reg
        and #$7f                ; WRITE (fill), not COPY
        jsr vdc_write_reg
        lda vdc_dst+1
        ldy vdc_dst
        jsr vdc_set_update
        lda vdc_fill_val
        jsr vdc_put             ; first byte by hand; R30 repeats it
        lda vdc_count
        bne vdc_fill_dec
        dec vdc_count+1
vdc_fill_dec:
        dec vdc_count
        jsr vdc_run_count
; The editor's $C53E: read the update address back and write one more
; byte while it's short of the end. Harmless when the fill already
; completed (the first compare falls straight through).
vdc_fill_check:
        ldx #VDC_R_UPDATE_HI
        jsr vdc_read_reg
        cmp vdc_end+1
        bcc vdc_fill_topup
        bne vdc_fill_done
        ldx #VDC_R_UPDATE_LO
        jsr vdc_read_reg
        cmp vdc_end
        bcs vdc_fill_done
vdc_fill_topup:
        lda #1
        ldx #VDC_R_WORD_COUNT
        jsr vdc_write_reg
        jmp vdc_fill_check
vdc_fill_done:
        rts

; --- vdc_run_count: write R30 in chunks of at most 255 until vdc_count
; bytes are covered (0 = nothing). Each write waits for the previous
; chunk through the ready-bit handshake. ---
vdc_run_count:
        lda vdc_count+1
        beq vdc_run_last
        lda #255
        ldx #VDC_R_WORD_COUNT
        jsr vdc_write_reg
        sec
        lda vdc_count
        sbc #255
        sta vdc_count
        bcs vdc_run_count
        dec vdc_count+1
        jmp vdc_run_count
vdc_run_last:
        lda vdc_count
        beq vdc_run_done
        ldx #VDC_R_WORD_COUNT
        jsr vdc_write_reg
vdc_run_done:
        rts

vdc_src:      word 0
vdc_dst:      word 0
vdc_count:    word 0
vdc_end:      word 0
vdc_fill_val: byte 0
