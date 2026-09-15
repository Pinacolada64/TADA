; --- 3-key-rollover.asm ---
; Cleaned-up, buildable version of 3-key-rollover-source.lbl (a raw
; disassembler-labeled dump, untracked in the repo before this) --
; Ryan's parked idea (see [[project_3_key_rollover_idea]] in project
; memory): a custom IRQ-driven keyboard-scan routine that replaces the
; KERNAL's own SCNKEY, maintaining a live "matrix coordinate of the
; CURRENTLY held key" (SFDX) rather than just a buffered keypress
; event -- SFDX reverting to $40 (no key) the instant a key is
; released is real hold/release tracking, which plain GETIN/$028D
; can't give (GETIN only reports presses, not releases).
;
; Internal branch-target labels (c509/c534/etc) are kept as their
; original disassembly addresses rather than renamed to describe what
; they do -- this file is for understanding/testing the routine
; end-to-end before any real integration decision, not a finished,
; production-ready rewrite. The header comments below describe what
; each section is actually doing, verified against real KERNAL
; zero-page/hardware addresses, not assumed from the file's name alone
; (see project memory's own "how to apply" note on this file).
;
; NOT included here, deliberately: the original's own $0318 (NMI
; vector) hook. The original `install` routine hard-overwrites the NMI
; vector for its own RESTORE-key/cassette handling -- fine in total
; isolation (this demo), but on the real client $0318 is the SwiftLink
; receive handler (tada-client.asm's init_nmi/nmi_handler); installing
; this driver unmodified there would silently kill all network I/O.
; Stripped out now so this file already reflects what real integration
; would need, rather than testing something that can't actually be
; reused as-is. The cursor-blink logic this routine also reimplements
; (BLNSW/BLNCT/GDBLN/BLNON) is LEFT IN here (nothing else competes for
; it in this standalone demo) but would need reconciling with
; tada-client.asm's own update_cursor/cursor_toggle blink mechanism
; before any real integration -- not attempted here.
;
; Real KERNAL zero-page/hardware addresses this driver uses (matches
; the stock KERNAL's own layout, not custom locations):
CAS1    = $c0   ; Tape Motor Interlock (temp storage, unused in this demo's
                  ; own logic -- kept only because the disassembly writes it)
LSTX    = $c5   ; Matrix coordinate of the LAST key pressed, $40 = none
SFDX    = $cb   ; Matrix coordinate of the key CURRENTLY held, $40 = none --
                  ; this is the whole reason for this experiment: live
                  ; press/release state, not a buffered event
BLNSW   = $cc   ; Cursor blink enable: 0 = flash cursor
BLNCT   = $cd   ; Countdown timer to next cursor blink
GDBLN   = $ce   ; Character currently under the cursor
BLNON   = $cf   ; Flag: was the last cursor blink on or off
PNT     = $d1   ; Pointer to the current screen line's address (2 bytes)
PNTR    = $d3   ; Cursor column on the current line
USER    = $f3   ; Pointer to the current screen line's Color RAM address
KEYTAB  = $f5   ; Vector: keyboard decode table (2 bytes)
COLOR   = $0286 ; Current foreground text color
GDCOL   = $0287 ; Color of the character under the cursor
SHFLAG  = $028d ; SHIFT/CTRL/Commodore live modifier flags -- SAME address
                  ; tada-client.asm's own keymap_dispatch already reads
KEYLOG  = $028f ; Vector: keyboard-decode-table setup routine
CINV    = $0314 ; IRQ vector
CIAPRA  = $dc00 ; CIA #1 Data Port A (keyboard matrix column select)
CIAPRB  = $dc01 ; CIA #1 Data Port B (keyboard matrix row read)
SCRNSTOR   = $ea1c ; KERNAL: .a=char, PNT=screen addr, .x=color -> poke both
COLRSYNC   = $ea24 ; KERNAL: sync the Color RAM pointer to the screen pointer
KERNAL_CHROUT = $ffd2
KERNAL_UDTIM  = $ffea ; KERNAL: advance the software jiffy clock

        orig $c500      ; free RAM on a stock C64 regardless of banking
                          ; (same reasoning constants.asm gives for using
                          ; $c000-$cfff in the real client) -- the
                          ; original disassembly relocated this to $cd00
                          ; to dodge some other collision; nothing else
                          ; is resident in this standalone demo, so the
                          ; original $c500 is fine here

        jmp install
        jmp uninstall
        jmp c5ea

; --- IRQ handler: cursor blink, then keyboard scan, then fall into
; the stock KERNAL IRQ tail (jiffy clock + STOP-key check + RTI) ---
c509:
        jsr KERNAL_UDTIM
        lda BLNSW
        bne c539
        dec BLNCT
        bne c539
        lda #$14
        sta BLNCT
        ldy PNTR
        lsr BLNON
        ldx GDCOL
        lda (PNT),y
        bcs c534
        inc BLNON
        sta GDBLN
        jsr COLRSYNC
        lda (USER),y
        sta GDCOL
        ldx COLOR
        lda GDBLN
c534:
        eor #$80
        jsr SCRNSTOR
c539:
        ; Cassette-sense bit-4-of-$01 logic, verbatim from the original
        ; dump -- this demo has no tape drive, but leaving it in costs
        ; nothing and keeps this section a faithful copy of the real
        ; scan-and-blink tail for later comparison.
        lda $01
        and #$10
        beq c549
        ldy #$00
        sty CAS1
        lda $01
        ora #$20
        bne c551
c549:
        lda CAS1
        bne c553
        lda $01
        and #$1f
c551:
        sta $01
c553:
        jsr c559        ; the keyboard scan itself
        jmp $ea7e       ; stock KERNAL IRQ tail: jiffy clock, STOP-key
                          ; long-press check, pla/tax/tay/pla/rti

; --- c559: debounce + read the raw matrix, dispatch to the decoder ---
c559:
        lda #$00
        sta CIAPRA
c55e:
        lda CIAPRB
        cmp CIAPRB
        bne c55e
        cmp #$ff
        beq c5a3
        jsr c758
        bcc c5a8
        jsr c658
        jsr c758
        bcc c5a8
        jsr c68d
        jsr c6bb
        jsr c6fb
        lda #$81
        sta KEYTAB
        lda #$eb
        sta KEYTAB+1
        ldx #$ff
        bit c778
        bmi c5bc
        lda c779
        cmp #$ff
        bne c59d
        lda SHFLAG
        beq c5bc
        lda #$40
c59d:
        sta SFDX        ; SFDX now holds the matrix coordinate of the
                          ; key currently down -- read this live from
                          ; the demo loop for real hold/release state
        tay
        jmp (KEYLOG)    ; hand off to the stock decode-table routine --
                          ; still fills the ordinary $0277 keyboard
                          ; buffer, so plain GETIN keeps working exactly
                          ; as normal for regular typing
c5a3:
        lda #$7f
        sta CIAPRA
c5a8:
        lda #$ff
        ldx #$02
c5ac:
        sta c779,x
        dex
        bpl c5ac
        jsr c6b5
        ldx #$ff
        lda #$00
        sta c778
        ; falls through into c5bc (no branch in the original here)
c5bc:
        lda #$40        ; $40 = no key currently held
        sta SFDX
        tay
        jmp $eb26       ; back into the stock decode-table's own tail

; --- install / uninstall ---
; Only hooks CINV ($0314) -- the original also hooked NMINV ($0318)
; for its own RESTORE-key handling, deliberately removed here (see
; this file's own header comment on why).
install:
        jsr c5ea
        rts
c5ea:
        sei
        lda #<c509
        ldy #>c509
        sta CINV
        sty CINV+1
        cli
        ldx #$02
        lda #$ff
c604:
        sta c779,x
        dex
        bpl c604
        lda #$00
        sta c778
        rts
uninstall:
        sei
        lda #$31        ; stock KERNAL IRQ vector low byte ($ea31)
        ldy #$ea
        sta CINV
        sty CINV+1
        cli
        rts

; --- c658/c663/c676: prime CIAPRA for an 8-column scan ---
c658:
        ldx #$ff
        ldy #$ff
        lda #$fe
        sta KEYTAB
        jmp c676
c663:
        lda CIAPRB
        cmp CIAPRB
        bne c663
        sty CIAPRA
        eor #$ff
        sta c76d,x
        sec
        rol KEYTAB
c676:
        lda KEYTAB
        sta CIAPRA
        inx
        cpx #$08
        bcc c663
        rts

; --- c68d/c6b5/c6bb: SHIFT/CTRL/Commodore modifier-bit extraction ---
c681:
        byte $01,$06,$07,$07
c685:
        byte $80,$10,$20,$04
c689:
        byte $01,$01,$02,$04
c68d:
        jsr c6b5
        ldy #$03
c692:
        ldx c681,y
        lda c76d,x
        and c685,y
        beq c6b1
        lda c689,y
        ora SHFLAG
        sta SHFLAG
        lda c685,y
        eor #$ff
        and c76d,x
        sta c76d,x
c6b1:
        dey
        bpl c692
        rts
c6b5:
        lda #$00
        sta SHFLAG
        rts

; --- c6bb/c6cd: convert the raw column bitmaps into matrix coordinates ---
c6bb:
        ldx #$02
        lda #$ff
c6bf:
        sta c775,x
        dex
        bpl c6bf
        ldy #$00
        sty KEYTAB
        ldx #$00
        stx SFDX
c6cd:
        lda c76d,x
        beq c6ee
        ldy SFDX
c6d4:
        lsr
        bcc c6e9
        pha
        stx KEYTAB+1
        ldx KEYTAB
        cpx #$03
        bcs c6e6
        tya
        sta c775,x
        inc KEYTAB
c6e6:
        ldx KEYTAB+1
        pla
c6e9:
        iny
        cmp #$00
        bne c6d4
c6ee:
        clc
        lda SFDX
        adc #$08
        sta SFDX
        inx
        cpx #$08
        bcc c6cd
        rts

; --- c6fb: 3-key-rollover debounce -- reconcile this scan's matrix
; coordinates against the previous scan's, the actual "rollover" logic
; the whole routine is named for ---
c6fb:
        ldy #$00
c6fd:
        lda c779,y
        cmp #$ff
        beq c728
        ldx #$02
c706:
        cmp c775,x
        beq c723
        dex
        bpl c706
        tya
        tax
c710:
        lda c77a,x
        sta c779,x
        inx
        cpx #$02
        bcc c710
        lda #$ff
        sta c77b
        sta c778
c723:
        iny
        cpy #$03
        bcc c6fd
c728:
        ldy #$00
c72a:
        lda c775,y
        cmp #$ff
        beq c757
        ldx #$02
c733:
        cmp c779,x
        beq c752
        dex
        bpl c733
        pha
        ldx #$01
c73e:
        lda c779,x
        sta c77a,x
        dex
        bpl c73e
        lda #$00
        sta c778
        pla
        sta c779
        ldy #$03
c752:
        iny
        cpy #$03
        bcc c72a
c757:
        rts

; --- c758: a second debounced read, used to tell "no key at all" (all
; columns read $ff) apart from "at least one key down" before the
; real scan runs ---
c758:
        lda #$ff
        sta CIAPRA
c75d:
        lda CIAPRB
        cmp CIAPRB
        bne c75d
        cmp #$ff
        lda #$7f
        sta CIAPRA
        rts

; --- Scratch state -- own copy per scan, not shared with anything else ---
c76d:
        byte 0,0,0,0,0,0,0,0
c775:
        byte 0,0,0
c778:
        byte 0
c779:
        byte 0
c77a:
        byte 0
c77b:
        byte 0,0,0
