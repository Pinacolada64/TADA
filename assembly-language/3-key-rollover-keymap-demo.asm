; --- 3-key-rollover-keymap-demo.asm ---
; Standalone experiment (Ryan's ask, 2026-09-15): does 3-key-rollover.asm's
; live SFDX (matrix coordinate of the CURRENTLY held key, $40 = none)
; actually give reliable real-time press/release tracking, well enough
; to drive the "live modifier + key display, blanks on release" combo-
; capture UI idea from [[project_keymap_editor_idea]]? Not integrated
; into the real client at all -- see 3-key-rollover.asm's own header
; comment for why (NMI vector conflict with SwiftLink, cursor-blink
; conflict with the real client's own update_cursor).
;
; What this demo does: installs the driver, then loops showing a live
; readout of held modifiers (from SHFLAG/$028D, same address the real
; client's keymap_dispatch already reads) and the currently-held key's
; letter/symbol (from GETIN, blanked the instant SFDX reverts to $40,
; not a timeout) -- exactly the "C=            C" / "   Shift Ctrl J"
; style display Ryan described. RUN/STOP uninstalls the driver and
; exits back to BASIC.
{include:basic_stub.asm}
; NOTE: 3-key-rollover.asm is {include:}'d at the very END of this
; file, not here -- it has its own `orig $c500` directive, which would
; otherwise jump the assembler's position past MAIN: below, breaking
; the BASIC stub's `SYS 2061` (which expects MAIN to land right after
; the stub, at $080D). Caught live via c64list's own "Large change in
; origin" warning on a first attempt with the include up here.

SCREEN_RAM = $0400
KERNAL_GETIN  = $ffe4
; KERNAL_CHROUT already defined by 3-key-rollover.asm ({include:}'d
; above) -- c64list treats symbol names case-insensitively, so
; redeclaring it here is a real redefinition error, not just a style
; nit.

; (zp),y indirect addressing needs a REAL zero-page pointer -- $fb-$fe
; are free and don't collide with anything 3-key-rollover.asm itself
; uses (CAS1/LSTX/SFDX/BLNSW/BLNCT/GDBLN/BLNON/PNT/PNTR/USER/KEYTAB
; are all $c0-$c1/$c5/$cb-$cf/$d1-$d3/$f3-$f6).
mod_row_ptr = $fb       ; 2 bytes ($fb/$fc)
key_row_ptr = $fd       ; 2 bytes ($fd/$fe)

MAIN:
        ; Pack-Scatter (c64list 4.06+, Ryan's find): 3-key-rollover.asm's
        ; `orig $c500` was otherwise forcing a huge empty gap into the
        ; .prg (195 blocks!) between this code and the driver's fixed
        ; address. {scatter} here compiles to a jsr into c64list's own
        ; appended restore routine, which packs every `orig`'d block
        ; (just the driver's, in this file) to the end of the assembled
        ; code and un-packs it back to $c500 at runtime, before
        ; anything below gets a chance to call into it. Must run before
        ; the jsr install right after it -- that's the whole point.
        {scatter}
        jsr install

        lda #$93        ; clear screen
        jsr KERNAL_CHROUT
        ldx #0
banner_loop:
        lda banner_text,x
        beq banner_done
        jsr KERNAL_CHROUT
        inx
        jmp banner_loop
banner_done:

        lda #0
        sta last_key
        sta shown_mod

demo_loop:
        ; --- Live modifier row: redraw only when SHFLAG actually
        ; changes, straight off $028D (SFDX is for the KEY row below;
        ; this is the same modifier-bit source the real client uses) ---
        lda SHFLAG
        and #$07        ; SHIFT(1)/Commodore(2)/CTRL(4) -- same 3 bits
                          ; keymap_dispatch already masks against
        cmp shown_mod
        beq demo_skip_mod
        sta shown_mod
        jsr draw_mod_row
demo_skip_mod:

        ; --- Raw diagnostic row (row 9): GETIN's return byte and SFDX,
        ; every single iteration, unfiltered -- added live 2026-09-15
        ; after Ryan found a real key+modifier combo (e.g. Ctrl+J)
        ; wasn't showing on the key row at all, to see whether GETIN
        ; genuinely returns nothing for that case or the display logic
        ; below is just failing to show what it got.
        jsr KERNAL_GETIN
        sta diag_getin
        lda SFDX
        sta diag_sfdx
        jsr draw_diag_row

        ; --- Key row: GETIN gives us WHICH key; SFDX tells us whether
        ; it's still down -- this is the whole point of the driver ---
        lda diag_getin
        cmp #0
        beq demo_check_release
        cmp #$03        ; RUN/STOP -- exit the demo
        beq demo_exit
        sta last_key
        jsr draw_key_row
        jmp demo_loop
demo_check_release:
        lda last_key
        beq demo_loop   ; nothing captured yet, nothing to blank
        lda SFDX
        cmp #$40        ; $40 = no key currently held
        bne demo_loop   ; still down (or a different key now down) --
                          ; leave the display as-is
        lda #0
        sta last_key
        jsr blank_key_row
        jmp demo_loop

demo_exit:
        jsr uninstall
        lda #$93
        jsr KERNAL_CHROUT
        rts

; --- draw_mod_row: repaint row 10 with whichever of Shift/Ctrl/C= are
; currently held (shown_mod's bits), left to right, space-separated ---
MOD_SHIFT = 1
MOD_CMDRE = 2
MOD_CTRL  = 4

draw_mod_row:
        ldx #<(SCREEN_RAM+10*40)
        ldy #>(SCREEN_RAM+10*40)
        stx mod_row_ptr
        sty mod_row_ptr+1
        ldy #0
        ; blank the row first
mod_row_clear:
        lda #$20
        sta (mod_row_ptr),y
        iny
        cpy #40
        bne mod_row_clear
        lda #0
        sta mod_row_col         ; reset -- persists across mdr_copy
                                   ; calls below, so each redraw must
                                   ; start it fresh or the text would
                                   ; keep marching rightward forever
        lda shown_mod
        and #MOD_SHIFT
        beq mdr_try_cmdre
        ldx #<shift_name
        ldy #>shift_name
        jsr mdr_copy
mdr_try_cmdre:
        lda shown_mod
        and #MOD_CMDRE
        beq mdr_try_ctrl
        ldx #<cmdre_name
        ldy #>cmdre_name
        jsr mdr_copy
mdr_try_ctrl:
        lda shown_mod
        and #MOD_CTRL
        beq mdr_done
        ldx #<ctrl_name
        ldy #>ctrl_name
        jsr mdr_copy
mdr_done:
        rts
; .x/.y = lo/hi of a NUL-terminated name (already includes its own
; trailing space, e.g. "SHIFT ") -> append at mod_row_col, advancing
; it. X walks the SOURCE string's own index; Y is reloaded from
; mod_row_col for the DESTINATION column each iteration -- keeping
; these separate is the fix for an earlier draft that wrongly reused
; one register for both.
mdr_copy:
        stx mdr_load+1
        sty mdr_load+2
        ldx #0
mdr_copy_loop:
mdr_load:
        lda $ffff,x
        beq mdr_copy_done
        ldy mod_row_col
        sta (mod_row_ptr),y
        inc mod_row_col
        inx
        jmp mdr_copy_loop
mdr_copy_done:
        rts

mod_row_col:
        byte 0

; --- draw_key_row / blank_key_row: row 11, a single character showing
; the currently-held key (letter/symbol where possible, else "$XX" hex,
; matching keymap_menu.asm's own describe_combo fallback convention) ---
draw_key_row:
        jsr blank_key_row
        lda last_key
        cmp #$41
        bcc dkr_try_symbol
        cmp #$5b
        bcs dkr_try_symbol
        jsr key_row_putc        ; 'A'-'Z': PETSCII == screen code here
        rts
dkr_try_symbol:
        lda last_key
        cmp #$20
        bcc dkr_hex
        cmp #$40
        bcs dkr_hex
        jsr key_row_putc
        rts
dkr_hex:
        lda #'$'
        jsr key_row_putc
        lda last_key
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda hex_digits,x
        jsr key_row_putc
        pla
        and #$0f
        tax
        lda hex_digits,x
        jsr key_row_putc
        rts
key_row_putc:
        pha
        lda #<(SCREEN_RAM+11*40+15)
        sta key_row_ptr
        lda #>(SCREEN_RAM+11*40+15)
        sta key_row_ptr+1
        ldy key_row_col
        pla
        sta (key_row_ptr),y
        inc key_row_col
        rts
blank_key_row:
        lda #<(SCREEN_RAM+11*40+15)
        sta key_row_ptr
        lda #>(SCREEN_RAM+11*40+15)
        sta key_row_ptr+1
        ldy #0
        sty key_row_col
blank_key_row_loop:
        lda #$20
        sta (key_row_ptr),y
        iny
        cpy #10
        bne blank_key_row_loop
        rts

key_row_col:
        byte 0

; --- draw_diag_row: row 9, "G=xx S=xx" -- GETIN's raw return byte and
; SFDX, every iteration, unfiltered. Absolute indexed addressing (not
; a zero-page pointer) since this is a single fixed-offset 10-byte
; blit, same as poke_line's own shape in the real client.
diag_getin:
        byte 0
diag_sfdx:
        byte 0

draw_diag_row:
        lda diag_getin
        jsr diag_put_23
        lda diag_sfdx
        jsr diag_put_78
        ldx #0
diag_blit_loop:
        lda diag_template,x
        sta SCREEN_RAM+9*40,x
        inx
        cpx #10
        bne diag_blit_loop
        rts
; .a = byte -> two hex digits into diag_template+2/+3
diag_put_23:
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda hex_digits,x
        sta diag_template+2
        pla
        and #$0f
        tax
        lda hex_digits,x
        sta diag_template+3
        rts
; .a = byte -> two hex digits into diag_template+7/+8
diag_put_78:
        pha
        lsr
        lsr
        lsr
        lsr
        tax
        lda hex_digits,x
        sta diag_template+7
        pla
        and #$0f
        tax
        lda hex_digits,x
        sta diag_template+8
        rts

{alpha:poke}
diag_template:
        ascii "G=00 S=00 "
{alpha:normal}

; banner_text is printed via CHROUT (plain PETSCII/ASCII expected) --
; NOT under {alpha:poke}, unlike the strings below it, which are all
; poked directly into screen memory instead (mdr_copy/key_row_putc,
; which need real screen-code bytes at assemble time). Mixing these
; up was a real bug caught live: banner_text printed as garbage
; because CHROUT was handed screen codes, not PETSCII.
banner_text:
        ascii "3-KEY ROLLOVER LIVE DEMO"
        byte 13,13
        ascii "HOLD SHIFT/CTRL/C= AND A KEY --"
        byte 13
        ascii "ROW 10 SHOWS MODIFIERS HELD LIVE,"
        byte 13
        ascii "ROW 11 SHOWS THE KEY, BLANKING THE"
        byte 13
        ascii "INSTANT IT'S RELEASED (VIA SFDX,"
        byte 13
        ascii "NOT A TIMEOUT). STOP TO EXIT."
        byte 0

{alpha:poke}
shift_name:
        ascii "SHIFT "
        byte 0
cmdre_name:
        ascii "C= "
        byte 0
ctrl_name:
        ascii "CTRL "
        byte 0
hex_digits:
        ascii "0123456789ABCDEF"
{alpha:normal}

; Own scratch vars -- plain memory, not zero page (nothing here needs
; (zp),y/(zp,x) indirect addressing), same "avoid zero page unless
; truly needed" convention the real client follows. Declared here
; (after MAIN, not before it) so they don't push MAIN's own address
; past what the BASIC stub's `SYS 2061` expects -- see this file's own
; note by the {include:basic_stub.asm} line above.
last_key:
        byte 0          ; last GETIN byte seen, 0 = nothing captured yet
shown_mod:
        byte 0          ; SHFLAG bits currently displayed, so the row
                          ; only gets repainted when something changed

{include:3-key-rollover.asm}
