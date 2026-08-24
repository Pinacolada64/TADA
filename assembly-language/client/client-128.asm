; client-128.asm
; TADA Commodore 128 client -- early skeleton, NOT functional yet.
;
; See assembly-language/client/128_CLIENT_MECHANICS.md for the feature
; wishlist this is starting to work through. Runs in 128 native mode
; (not the C64-compatibility "GO 64" mode tada-client.asm targets) --
; separate binary, separate memory map, separate KERNAL. Does not share
; code with tada-client.asm; anything genuinely reusable (SwiftLink
; init, the receive-buffer protocol) gets pulled over deliberately once
; this has enough of its own scaffolding to need it, not blindly copied
; up front.
;
; Today this only does the first item on that wishlist: read the 40/80
; column switch at startup and report which video chip (VIC-II or VDC)
; is driving the screen. Nothing else is wired up -- no SwiftLink, no
; server connection, no screen editor window (ESC-T/ESC-B), no tab-stop
; sync (that part already landed server-side only, see
; terminal.c128_tab_sync_bytes() -- it needs no client code at all since
; it just sends ESC-Y/ESC-Z over the existing tada-client.asm PETSCII
; connection).
;
; Verified against Compute's 128 Programmer's Guide (pdftotext -layout;
; see 128_CLIENT_MECHANICS.md's own citation note about why a naive
; extract of this book's tables can't be trusted) rather than guessed:
;   - Native-mode BASIC program text starts at $1C01 (7169), not the
;     C64's $0801 -- different memory map, so the BASIC-stub loader
;     bytes below are recomputed for this load address, not copied from
;     tada-client.asm's C64 stub.
;   - $D505 (54533 decimal), the MMU mode configuration register: bit 7
;     reads the 40/80-column switch (1 = up = 40 columns/VIC-II, 0 =
;     down = 80 columns/VDC). "Read and acted upon only at power on or
;     reset" -- not a live togglable interrupt source (that's RESTORE,
;     a completely separate key wired to CIA 2's NMI line), so this is
;     safe to read exactly once at startup with no interrupt-handler
;     interaction to worry about.

; MMU mode configuration register -- bit 7 is the 40/80 switch.
{const: MMU_MODE_CONFIG $d505}
{const: SWITCH_40_COL_MASK $80}

; KERNAL
{const: KERNAL_CHROUT $ffd2}

        orig $1c01

; BASIC stub: 10 SYS7181 (native-128-mode load address is $1c01, not the
; C64's $0801 -- see header comment -- so this next-line-pointer/target
; pair is recomputed for that, not the C64 client's stub bytes).
        byte $0d,$1c,$0a,$00,$9e,$37,$31,$38,$31,$00,$00,$00

start:
        lda MMU_MODE_CONFIG
        and #SWITCH_40_COL_MASK
        bne forty_col_mode

eighty_col_mode:
        lda #0
        sta screen_mode          ; 0 = VDC/80-column
        ldx #0
eighty_msg_loop:
        lda eighty_msg,x
        beq done
        jsr KERNAL_CHROUT
        inx
        jmp eighty_msg_loop

forty_col_mode:
        lda #1
        sta screen_mode          ; 1 = VIC-II/40-column
        ldx #0
forty_msg_loop:
        lda forty_msg,x
        beq done
        jsr KERNAL_CHROUT
        inx
        jmp forty_msg_loop

done:
        rts

; --- Data ---

; screen_mode: 0 = VDC (80-column), 1 = VIC-II (40-column). Set once at
; startup by the 40/80-switch check above; nothing reads it yet -- next
; step is branching actual VIC-II vs VDC init routines on it, per
; 128_CLIENT_MECHANICS.md's wishlist, instead of just reporting which
; one was detected the way this stub does today.
screen_mode:
        byte 0

forty_msg:
        ascii "40-column mode (vic-ii) detected."
        byte 13, 0

eighty_msg:
        ascii "80-column mode (vdc) detected."
        byte 13, 0
