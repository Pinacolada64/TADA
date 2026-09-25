; --- keyboard_rollover.asm ---
; Real-client integration of the standalone 3-key-rollover keyboard scan
; (see [[project_3_key_rollover_idea]] / [[project_3_key_rollover_keymap_demo]]
; in project memory -- that standalone demo, branch
; experiment/3-key-rollover-keymap-demo, confirmed live 2026-09-15 that
; SFDX ($cb) gives genuine hold/release tracking, unlike GETIN's
; buffered press-only events). Split out of tada-client.asm the same way
; screen-handler.asm/keymap.asm were, {include:}'d as
; keyboard_rollover_pp.asm.
;
; This is a straight functional replacement for the KERNAL's own
; keyboard-scan-and-decode routine (the block inside stock $ea31 that
; used to run via irq_handler's old `jmp (irq_orig)` chain-through) --
; NOT a copy of the standalone demo's own IRQ handler (c509 in
; 3-key-rollover.asm), which also reimplemented cursor-blink logic.
; That blink logic is deliberately NOT ported here: this client already
; has its own working cursor_toggle/update_cursor (tada-client.asm),
; which independently reads/writes the same PNT/PNTR ($d1-$d3)
; zero-page vars on its own polled schedule. Running both blink
; mechanisms would fight over the same screen cell's reverse-video bit
; on two different timers (IRQ tick vs. polled) -- a real double-blink
; bug, not just redundant work. Leaving blink out entirely turns out to
; cost nothing extra: none of the scan/decode routines below (c559
; onward in the original disassembly) touch PNT/PNTR/USER ($d1-$d3/$f3)
; at all -- only the blink block did -- so this split isn't a
; workaround, it's simply not including code this client doesn't need.
;
; Zero-page usage (all verified against the original disassembly, and
; against this exact codebase's own already-fixed history of a zero-page
; collision at $f3-$f6 -- see tada-client.asm's own comment near
; sid_wr/sid_rd for that history):
;   SFDX ($cb)   -- stock KERNAL var, matrix coordinate of the key
;                    CURRENTLY held ($40 = none). Untouched by this
;                    client elsewhere; this is the live hold/release
;                    state a future keymap-editor live display would
;                    read (not wired up yet -- this file only replaces
;                    the scan itself).
;   KEYTAB ($f5/$f6) -- stock KERNAL var, reused here for exactly its
;                    stock purpose (a scratch bit-rotate pointer during
;                    the column scan, then the keyboard decode-table
;                    vector right before handing off to the stock
;                    decode routine at $eb48) -- the same reuse pattern
;                    the real KERNAL's own $ea31 handler already does.
;                    This client's only other references to $f3-$f6 are
;                    comments describing the OLD bug (unrelated
;                    variables that used to live there and got moved
;                    out) -- confirmed via grep before writing this
;                    file, so there is no live collision.
;   USER ($f3)   -- NOT used anywhere in this file (only the dropped
;                    blink block used it).
;
; Real KERNAL addresses this file jumps into, confirmed byte-for-byte
; identical between stock KERNAL and this project's JiffyDOS KERNAL
; (checked live via VICE remote monitor against
; ~/Documents/c64/JiffyDOS/Jiffydos-Kernal.rom, 2026-09-15 -- JiffyDOS
; only patches disk I/O, not the keyboard/IRQ chain):
;   $EB48 -- stock keyboard decode-table entry point (KEYLOG vector
;             target), reads SHFLAG and picks unshifted/shifted/
;             commodore/control decode table.
;   $EB26 -- stock decode routine's own "no key" tail.
KEYTAB  = $f5   ; keyboard decode-table vector (2 bytes) -- stock reuse
KEYLOG  = $028f ; vector: keyboard-decode-table setup routine (stock)
SHFLAG  = $028d ; SHIFT/CTRL/Commodore live modifier flags -- same
                  ; address this client's own keymap_dispatch reads
CIAPRA  = $dc00 ; CIA #1 Data Port A (keyboard matrix column select)
CIAPRB  = $dc01 ; CIA #1 Data Port B (keyboard matrix row read)
KERNAL_UDTIM = $ffea ; KERNAL: advance the software jiffy clock --
                  ; irq_handler calls this in place of chaining to
                  ; irq_orig, since kr_scan below replaces the rest of
                  ; what stock $ea31 used to do for this client

; --- kr_scan: entry point, called once per IRQ tick in place of the
; stock scan (see tada-client.asm's irq_handler) ---
kr_scan:
        lda #$00
        sta CIAPRA
kr_c55e:
        lda CIAPRB
        cmp CIAPRB
        bne kr_c55e
        cmp #$ff
        beq kr_c5a3
        jsr kr_c758
        bcc kr_c5a8
        jsr kr_c658
        jsr kr_c758
        bcc kr_c5a8
        jsr kr_c68d
        jsr kr_c6bb
        jsr kr_c6fb
        lda #$81
        sta KEYTAB
        lda #$eb
        sta KEYTAB+1
        ldx #$ff
        bit kr_c778
        bmi kr_c5bc
        lda kr_c779
        cmp #$ff
        bne kr_c59d
        lda SHFLAG
        beq kr_c5bc
        lda #$40
kr_c59d:
        sta $cb         ; SFDX -- live matrix coordinate of the key
                          ; currently down (real hold/release state)
        tay
        jmp (KEYLOG)    ; hand off to the stock decode routine -- still
                          ; fills the ordinary $0277 keyboard buffer, so
                          ; GETIN keeps working exactly as before
kr_c5a3:
        lda #$7f
        sta CIAPRA
kr_c5a8:
        lda #$ff
        ldx #$02
kr_c5ac:
        sta kr_c779,x
        dex
        bpl kr_c5ac
        jsr kr_c6b5
        ldx #$ff
        lda #$00
        sta kr_c778
kr_c5bc:
        lda #$40        ; $40 = no key currently held
        sta $cb         ; SFDX
        tay
        jmp $eb26       ; back into the stock decode routine's own tail

; --- kr_c658/kr_c663/kr_c676: prime CIAPRA for an 8-column scan ---
kr_c658:
        ldx #$ff
        ldy #$ff
        lda #$fe
        sta KEYTAB
        jmp kr_c676
kr_c663:
        lda CIAPRB
        cmp CIAPRB
        bne kr_c663
        sty CIAPRA
        eor #$ff
        sta kr_c76d,x
        sec
        rol KEYTAB
kr_c676:
        lda KEYTAB
        sta CIAPRA
        inx
        cpx #$08
        bcc kr_c663
        rts

; --- kr_c68d/kr_c6b5/kr_c6bb: SHIFT/CTRL/Commodore modifier-bit
; extraction (same $028D/SHFLAG this client's own keymap_dispatch
; already reads) ---
kr_c681:
        byte $01,$06,$07,$07
kr_c685:
        byte $80,$10,$20,$04
kr_c689:
        byte $01,$01,$02,$04
kr_c68d:
        jsr kr_c6b5
        ldy #$03
kr_c692:
        ldx kr_c681,y
        lda kr_c76d,x
        and kr_c685,y
        beq kr_c6b1
        lda kr_c689,y
        ora SHFLAG
        sta SHFLAG
        lda kr_c685,y
        eor #$ff
        and kr_c76d,x
        sta kr_c76d,x
kr_c6b1:
        dey
        bpl kr_c692
        rts
kr_c6b5:
        lda #$00
        sta SHFLAG
        rts

; --- kr_c6bb/kr_c6cd: convert the raw column bitmaps into matrix
; coordinates ---
kr_c6bb:
        ldx #$02
        lda #$ff
kr_c6bf:
        sta kr_c775,x
        dex
        bpl kr_c6bf
        ldy #$00
        sty KEYTAB
        ldx #$00
        stx $cb         ; SFDX
kr_c6cd:
        lda kr_c76d,x
        beq kr_c6ee
        ldy $cb         ; SFDX
kr_c6d4:
        lsr
        bcc kr_c6e9
        pha
        stx KEYTAB+1
        ldx KEYTAB
        cpx #$03
        bcs kr_c6e6
        tya
        sta kr_c775,x
        inc KEYTAB
kr_c6e6:
        ldx KEYTAB+1
        pla
kr_c6e9:
        iny
        cmp #$00
        bne kr_c6d4
kr_c6ee:
        clc
        lda $cb         ; SFDX
        adc #$08
        sta $cb         ; SFDX
        inx
        cpx #$08
        bcc kr_c6cd
        rts

; --- kr_c6fb: 3-key-rollover debounce -- reconcile this scan's matrix
; coordinates against the previous scan's ---
kr_c6fb:
        ldy #$00
kr_c6fd:
        lda kr_c779,y
        cmp #$ff
        beq kr_c728
        ldx #$02
kr_c706:
        cmp kr_c775,x
        beq kr_c723
        dex
        bpl kr_c706
        tya
        tax
kr_c710:
        lda kr_c77a,x
        sta kr_c779,x
        inx
        cpx #$02
        bcc kr_c710
        lda #$ff
        sta kr_c77b
        sta kr_c778
kr_c723:
        iny
        cpy #$03
        bcc kr_c6fd
kr_c728:
        ldy #$00
kr_c72a:
        lda kr_c775,y
        cmp #$ff
        beq kr_c757
        ldx #$02
kr_c733:
        cmp kr_c779,x
        beq kr_c752
        dex
        bpl kr_c733
        pha
        ldx #$01
kr_c73e:
        lda kr_c779,x
        sta kr_c77a,x
        dex
        bpl kr_c73e
        lda #$00
        sta kr_c778
        pla
        sta kr_c779
        ldy #$03
kr_c752:
        iny
        cpy #$03
        bcc kr_c72a
kr_c757:
        rts

; --- kr_c758: a second debounced read, used to tell "no key at all"
; (all columns read $ff) apart from "at least one key down" before the
; real scan runs ---
kr_c758:
        lda #$ff
        sta CIAPRA
kr_c75d:
        lda CIAPRB
        cmp CIAPRB
        bne kr_c75d
        cmp #$ff
        lda #$7f
        sta CIAPRA
        rts

; --- Scratch state -- own copy per scan, not shared with anything else ---
kr_c76d:
        byte 0,0,0,0,0,0,0,0
kr_c775:
        byte 0,0,0
kr_c778:
        byte 0
kr_c779:
        byte 0
kr_c77a:
        byte 0
kr_c77b:
        byte 0,0,0
