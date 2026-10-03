; --- build_rev.asm ---
; The boot-time build message ("build 42, 2026-Oct-01 13:02:56") shared
; by both clients. Ryan's ask, 2026-10-01 (C128 too, same day).
;
; {include:}d raw (no {const:}/{def:} of its own, so no _pp.asm pass --
; same as disk.asm) by tada-client.asm and client-128.asm. The including
; file supplies __BuildRev with its own {buildrev:<file>} -- each client
; keeps its own counter file (tada-client.buildrev, client-128.buildrev),
; since every c64list project needs its own. Screen codes are the same
; on both machines, so the one {alpha:pokealt} string serves both
; status rows.
;
; tada-client.asm pushes build_msg onto its status queue; client-128.asm
; shows it as a status_override (see its connect/go_offline). Either way
; strip_build_rev_zeros must run once before the first display.

; --- Build-date/time status message -- shown at boot as its own batch
; (status_push_buf's "first message of a fresh batch" behavior displays
; it immediately) until the first real event (e.g. a SID stream) pushes
; its own batch and replaces it. {alpha:pokealt} makes this `ascii`
; literal emit real screen codes at assembly time -- required since
; redraw_status_row pokes queue content straight into SCREEN_RAM rather
; than going through CHROUT's own PETSCII->screencode conversion. Reset
; to {alpha:normal} right after so this doesn't leak into anything below
; that uses plain `ascii`.
;
; The build number: {usedef:__BuildRev} expands to a bare number, not a
; quoted string like __BuildDate (and inside quotes c64list drops it --
; tried), so its five decimal digits are computed here at assembly time
; ($30 = '0' as a screen code too). c64list's expressions have no
; modulo, hence the N/10^k - N/10^(k+1)*10 spelling; c64list caps
; __BuildRev at 65535, so five digits always fit. strip_build_rev_zeros
; drops the leading zeros once at boot.
{alpha:pokealt}
build_msg:
        ascii "build "
build_rev_digits:
        byte $30+{usedef:__BuildRev}/10000
        byte $30+{usedef:__BuildRev}/1000-{usedef:__BuildRev}/10000*10
        byte $30+{usedef:__BuildRev}/100-{usedef:__BuildRev}/1000*10
        byte $30+{usedef:__BuildRev}/10-{usedef:__BuildRev}/100*10
        byte $30+{usedef:__BuildRev}-{usedef:__BuildRev}/10*10
        ascii ", "
        ascii {usedef:__BuildDate}
        ascii " "
        ascii {usedef:__BuildTime}
        byte 0
{alpha:normal}

; --- strip_build_rev_zeros: "build 00042 ..." -> "build 42 ..." ---
; Slides the rest of build_msg (null terminator included) left over
; build_rev_digits' leading zeros, in place, so every later push of
; build_msg (init_screen, keymap.asm's restore after loading the keymap
; file) already reads right. At most four zeros go, so build 0 keeps its
; "0". Call it ONCE: a second call would find nothing to strip for any
; build but 0, whose "0" it would then eat. Kept this small on purpose
; -- the C64 client had only 48 bytes left below OVERLAY_BUF when this
; went in (see check_overlay_margin.py).
strip_build_rev_zeros:
        ldx #0
strip_build_rev_count:
        lda build_rev_digits,x
        cmp #$30
        bne strip_build_rev_shift
        inx
        cpx #4
        bne strip_build_rev_count
strip_build_rev_shift:
        ldy #0
strip_build_rev_shift_loop:
        lda build_rev_digits,x
        sta build_rev_digits,y
        beq strip_build_rev_rts   ; copied the null terminator
        inx
        iny
        bne strip_build_rev_shift_loop  ; always -- the string is < 256
strip_build_rev_rts:
        rts
