; sid_streaming.asm -- SID register-write stream: background reception
; service, diagnostics, and playback. Split out of tada-client.asm
; (2026-08-24) once that file got long enough that finding SID-specific
; logic amid screen/keyboard/transport code was getting hard -- pure
; code reorganization, no behavior change (verified via a clean,
; 0-error, same-total-size assembled .prg before/after the split; not
; byte-identical, since consolidating scattered code shifts downstream
; addresses -- see swiftlink.asm's header for why that's expected here).
;
; Deliberately does NOT include handle_recv_byte (tada-client.asm) or
; its sub-labels (handle_recv_byte_start/_len_lo/_len_hi/_store/...) --
; despite advancing sid_mode's own state machine, that whole function is
; a single interleaved dispatcher shared with the canvas/display/apply
; stream confirms for the *other* overlay modules (petscii_editor.asm,
; config_menu.asm), not a SID-exclusive routine. Untangling just the
; SID-shaped branches from that one function was judged too risky to do
; confidently in one pass -- it stays in tada-client.asm as a single
; unit, calling into this file's sid_stop/status_print_*/etc by name
; (resolved globally across {include:}s, same as everything else here).
;
; Depends on tada-client.asm's own declarations (referenced by name,
; resolved globally across {include:}s): sid_mode/sid_active/
; sid_remaining_lo/sid_remaining_hi/sid_background/sid_recv_last_jiffy/
; sid_byte_count/sid_dump_idx/sid_frames_played/sid_jiffy_start0-2/
; sid_jiffy_elapsed0-2/sid_stream_starts (all deliberately NOT zero page
; -- see tada-client.asm's own "Hard-won lessons" comment on why),
; SID_BUF (data), sl_recv (swiftlink.asm), linelen, status_service/
; status_push_reset/status_build_from_table/status_putc/status_push_buf
; (the generic status-row queue, not SID-specific), service_async_text/
; service_async_idle, term_chrout.
;
; SID_BASE/SID_FRAME_END DID move here (not just referenced), same
; {const:}-doesn't-cross-{include:} reason as swiftlink.asm's SL_*
; constants -- see that file's header for the full explanation.

; SID chip base address (25 registers, $D400-$D418)
SID_BASE = $d400

SID_FRAME_END = $ff      ; terminates one tick's (reg,val) pairs --
                           ; safe as a sentinel since SID only has
                           ; registers 0-24

; --- Background SID service, polled from read_line ---
; Keeps a still-arriving SID stream flowing into SID_BUF (and hence
; feeding sid_play) while the player is busy typing their next command,
; instead of it stalling until they submit a line -- see
; wait_for_data's own comment for why that hand-off happens.
;
; Always services a byte while mid-stream (sid_mode != 0) -- stream data
; never reaches display_char, so there's nothing to protect against yet.
; Once the stream ends (sid_mode back to 0), also keeps servicing
; -- but only while linelen is still 0, i.e. the player hasn't typed
; anything into this line yet. That covers the trailing response text
; every play command has waiting right behind its raw stream (the
; command loop's own "main > " prompt, queued up on the wire behind the
; whole transfer -- always the very next thing to arrive once the stream
; itself finishes): confirmed live 2026-08-18 that without this, that
; prompt just sat undisplayed in rx_buf -- cursor blinking, nothing
; visibly wrong, but no prompt text either -- until the player's next
; Enter (submitting an empty line) drove a fresh wait_for_data call that
; finally drained and showed it, one round-trip late. Still refuses to
; touch rx_buf once linelen is nonzero, i.e. once the player has actually
; started typing -- unsolicited server text (an ambient room/ally
; message, unrelated to anything just played) arriving at that point
; used to be left alone for wait_for_data to show normally on the next
; round-trip; it's now handed off to service_async_text (player mid-line)
; or service_async_idle (player hasn't typed anything yet -- an idle
; flood of ambient messages used to scroll the prompt away with nothing
; ever redrawing it, confirmed live 2026-08-18 stress-testing 40 rapid
; pages) instead, both of which display it without losing track of the
; prompt -- see their own comments. Still unconditionally drains silently
; whenever sid_mode != 0 (mid-SID-stream interleaving is a separate,
; already-handled case -- untouched here); that path never touches
; capture/display/prompt_buf since stream bytes never reach
; handle_recv_byte_text.
;
; Gadget flagged the gap this closes: frames.py's protocol has no in-band
; end-of-stream marker for a dropped/truncated transfer to fall back on
; (SID_FRAME_END only delimits one tick's register writes within already-
; arrived bytes -- see its own comment -- and sid_play_scan already bails
; safely, frame-by-frame, if it never shows up). But the *reception* side
; had nothing symmetrical: sid_mode counts down an exact byte length with
; no timeout, so a connection drop or server crash mid-stream left it
; stuck in mode 1/2/3/4 forever, silently swallowing every future byte
; into SID framing instead of text -- and since SID_STOP is only
; recognized from mode 0 (handle_recv_byte_text), the player couldn't
; even `#stop` their way out. sid_recv_last_jiffy (restamped on every
; byte that actually advances the state machine -- see its own comment)
; lets this branch notice "mid-stream, but no byte at all in
; SID_RECV_TIMEOUT_JIFFIES" and force the same recovery SID_STOP already
; does: sid_stop silences the chip and zeroes sid_mode/sid_active, handing
; the connection back to ordinary text mode same as a real #stop would.
sid_service_background:
        jsr status_service        ; rotate the status row's queued
                                    ; message every ~5s, regardless of
                                    ; what else this poll iteration does
        lda sid_mode
        bne sid_service_background_recv
        lda linelen
        beq sid_service_background_idle
        jmp service_async_text
sid_service_background_idle:
        jmp service_async_idle
sid_service_background_recv:
        jsr sl_recv
        bcs sid_service_background_got_byte
        lda $a2
        sec
        sbc sid_recv_last_jiffy
        cmp #SID_RECV_TIMEOUT_JIFFIES
        bcc sid_service_background_rts   ; still within the idle window
        jsr sid_stop                     ; gave up -- same recovery as #stop
        rts
sid_service_background_got_byte:
        jsr handle_recv_byte
sid_service_background_rts:
        rts

; --- SID diagnostics: status-row messages, not scrolling text ---
; Ported 2026-08-20 from the original CHROUT-based sid_print_* routines
; (same names, "status_print_" prefix) to build into the status queue
; instead -- each pushes one reverse-video message onto STATUS_ROW's
; rotation rather than printing a CR-terminated line into the scrolling
; dialogue area. Two call sites (handle_recv_byte_stop's 4-message group,
; handle_recv_byte_store_done's 3-message group) each start their own
; batch with status_push_reset first. Message text/values are otherwise
; unchanged from the originals -- see each routine's own history/reasoning
; comment, preserved below.
;
; status_print_hex_byte/nibble mirror sid_print_hex_byte/nibble exactly
; (same shift-and-mask structure) but write screen codes via status_putc
; into status_build_buf instead of CHROUT-ing PETSCII -- status_hex_digits
; is a SEPARATE table from sid_hex_digits (which stays, CHROUT-based, for
; load_overlay_error's unrelated use): digits 0-9 already match ASCII
; byte-for-byte in this charset, but letters A-F don't (screen code 'A'
; is $01, not ASCII $41), so a table meant for direct-poke display can't
; be shared with one meant for CHROUT.
status_print_hex_nibble:           ; .A = nibble (0-15)
        and #$0f
        tax
        lda status_hex_digits,x
        jsr status_putc
        rts

status_print_hex_byte:              ; .A = byte to print in hex
        pha
        lsr
        lsr
        lsr
        lsr
        jsr status_print_hex_nibble
        pla
        jsr status_print_hex_nibble
        rts

; --- Dump SID_BUF[0..11] as hex ---
; Ground truth for comparing against the server's own encoded bytes (see
; sid_engine.frames.encode_stream output) -- confirms whether stored
; frame data matches what was actually sent, independent of the byte
; *count* already being verified correct by status_print_byte_count.
; First 12 bytes only (not the original's 24) -- STATUS_SLOT_LEN caps a
; message at 39 visible chars, and 12 bytes * 3 chars ("xx ") fits that
; cleanly where 24 would silently truncate mid-byte.
status_print_bufdump:
        lda #0
        sta sid_dump_idx
status_print_bufdump_loop:
        ldx sid_dump_idx
        lda SID_BUF,x
        jsr status_print_hex_byte
        lda #' '
        jsr status_putc
        inc sid_dump_idx
        lda sid_dump_idx
        cmp #12
        bne status_print_bufdump_loop
        jsr status_push_buf
        rts

; --- "GOT $xxxx BYTES" -- diagnostic for the SID stream pipe ---
; Prints sid_byte_count (hi byte first) as 4 hex digits. Unconditional
; (not gated behind {ifdef:debug}) since this answers a real end-to-end
; question -- did the bytes the server said it sent actually arrive --
; not a temporary bug hunt.
status_print_byte_count:
        ldx #<status_lbl_got
        ldy #>status_lbl_got
        jsr status_build_from_table
        lda sid_byte_count+1
        jsr status_print_hex_byte
        lda sid_byte_count+0
        jsr status_print_hex_byte
        ldx #<status_lbl_bytes
        ldy #>status_lbl_bytes
        jsr status_build_from_table
        jsr status_push_buf
        rts

; --- "PLAYED $xxxx FRAMES" ---
; sid_frames_played counts every frame sid_play has successfully applied
; since the current stream started (reset in handle_recv_byte_start).
; Pushed on `play #stop` -- comparing this count against real elapsed
; (stopwatch) time gives the client's true empirical playback rate,
; cutting through any PAL/NTSC IRQ-rate guessing.
status_print_frames_played:
        ldx #<status_lbl_played
        ldy #>status_lbl_played
        jsr status_build_from_table
        lda sid_frames_played+1
        jsr status_print_hex_byte
        lda sid_frames_played+0
        jsr status_print_hex_byte
        ldx #<status_lbl_frames
        ldy #>status_lbl_frames
        jsr status_build_from_table
        jsr status_push_buf
        rts

; --- "ELAPSED $xxxxxx JIFFIES" ---
; current jiffy clock ($a0/$a1/$a2) minus the snapshot handle_recv_byte_
; start took when the stream began -- standard 3-byte subtract-with-
; borrow, low byte first. No BCD involved; the jiffy clock is a plain
; binary counter.
status_print_elapsed:
        sec
        lda $a2
        sbc sid_jiffy_start2
        sta sid_jiffy_elapsed2
        lda $a1
        sbc sid_jiffy_start1
        sta sid_jiffy_elapsed1
        lda $a0
        sbc sid_jiffy_start0
        sta sid_jiffy_elapsed0

        ldx #<status_lbl_elapsed
        ldy #>status_lbl_elapsed
        jsr status_build_from_table
        lda sid_jiffy_elapsed0
        jsr status_print_hex_byte
        lda sid_jiffy_elapsed1
        jsr status_print_hex_byte
        lda sid_jiffy_elapsed2
        jsr status_print_hex_byte
        ldx #<status_lbl_jiffies
        ldy #>status_lbl_jiffies
        jsr status_build_from_table
        jsr status_push_buf
        rts

; --- "RD=$xx WR=$xx" ---
; Raw current values of sid_rd/sid_wr at the moment #stop was processed.
; Ground truth for whether SID_BUF's producer/consumer indices are where
; they should be (matching sid_byte_count/sid_frames_played) or have
; drifted -- e.g. sid_wr still growing after "GOT" already pushed would
; mean more bytes are landing in SID_BUF than accounted for.
status_print_pointers:
        ldx #<status_lbl_rd
        ldy #>status_lbl_rd
        jsr status_build_from_table
        lda sid_rd
        jsr status_print_hex_byte
        ldx #<status_lbl_wr
        ldy #>status_lbl_wr
        jsr status_build_from_table
        lda sid_wr
        jsr status_print_hex_byte
        jsr status_push_buf
        rts

; --- "STARTS=$xx" ---
; sid_stream_starts counts every time handle_recv_byte_start fired (a
; real SID_STREAM_START+SID_STREAM_CONFIRM pair was seen) since the last
; #stop. A count > 1 when the player only issued one `play` command
; means something else on this connection is triggering stream starts --
; ambient/ally/room broadcasts most likely, given this is a live
; multiplayer server. Ground truth for whether the confirm-byte fix
; actually stopped spurious triggers or just made them rarer.
status_print_stream_starts:
        ldx #<status_lbl_starts
        ldy #>status_lbl_starts
        jsr status_build_from_table
        lda sid_stream_starts
        jsr status_print_hex_byte
        jsr status_push_buf
        rts

; {alpha:pokealt} label fragments for the status_print_* routines above,
; and the screen-code hex-digit table status_print_hex_nibble reads --
; see this section's own header comment for why these need pre-encoded
; screen codes rather than plain ascii. Sentence-case, not the original
; SPUR-style ALL-CAPS these were first ported as (Ryan's ask, 2026-08-20,
; once pokealt proved out via the build-date/time message) -- matches
; this port's own sentence-case convention for player-facing text.
{alpha:pokealt}
status_hex_digits:
        ascii "0123456789ABCDEF"
status_lbl_played:
        ascii "Played $"
        byte 0
status_lbl_frames:
        ascii " frames"
        byte 0
status_lbl_elapsed:
        ascii "Elapsed $"
        byte 0
status_lbl_jiffies:
        ascii " jiffies"
        byte 0
status_lbl_rd:
        ascii "Rd=$"
        byte 0
status_lbl_wr:
        ascii " wr=$"
        byte 0
status_lbl_starts:
        ascii "Starts=$"
        byte 0
status_lbl_got:
        ascii "Got $"
        byte 0
status_lbl_bytes:
        ascii " bytes"
        byte 0
{alpha:normal}

sid_print_hex_nibble:             ; .A = nibble (0-15)
        pha
        and #$0f
        tax
        lda sid_hex_digits,x
        jsr term_chrout
        pla
        rts

sid_print_hex_byte:                ; .A = byte to print in hex
        pha
        lsr
        lsr
        lsr
        lsr
        jsr sid_print_hex_nibble
        pla
        jsr sid_print_hex_nibble
        rts

sid_hex_digits:
        ascii "0123456789ABCDEF"

; --- Silence the SID chip and reset playback state ---
; Shared by init_sid (startup) and the SID_STOP control byte
; (handle_recv_byte_stop, for `play #stop`): clears all 25 SID registers
; -- including MODE_VOL, so anything currently sustaining goes silent
; immediately, not just "no further updates" -- and turns off sid_active/
; sid_mode. SID_BUF's indices don't need clearing here -- sid_active is
; 0 afterward either way, so sid_play won't touch them until a real
; SID_STREAM_START arrives and resets them itself.
sid_stop:
        ldx #24
        lda #0
sid_stop_loop:
        sta SID_BASE,x
        dex
        bpl sid_stop_loop
        sta sid_mode
        sta sid_active
        sta sid_stream_starts     ; TEMP diagnostic -- see its own comment
        rts

init_sid:
        jmp sid_stop

; --- SID playback (called every IRQ tick, unconditionally) ---
; Register-write frames arrive as (register-offset, value) byte pairs
; terminated by SID_FRAME_END ($ff) -- see sid_engine/frames.py. Consumes
; exactly one frame per call so playback tempo depends only on the IRQ
; rate, never on how many other jobs share the interrupt.
;
; A frame is only applied once it has arrived in full: the first pass
; (sid_play_scan) just looks for a terminator between sid_rd and sid_wr
; without touching any registers. If sid_wr is reached first, the frame
; hasn't fully arrived yet -- hold last tick's sound and try again next
; tick, rather than reading stale bytes past what's been received or
; applying only half a frame's writes.
sid_play:
        lda sid_active
        beq sid_play_rts

        ldx sid_rd
sid_play_scan:
        cpx sid_wr
        beq sid_play_rts          ; caught up to writer -- no full frame yet
        lda SID_BUF,x             ; a register-index byte -- FRAME_END is only
        inx                       ; ever meaningful here, never at the paired
        cmp #SID_FRAME_END        ; value byte that follows (see FRAME_END's
        beq sid_play_scan_found   ; own comment: a real register *value* of
                                   ; 255 is completely ordinary and must not
                                   ; be mistaken for end-of-frame -- confirmed
                                   ; live 2026-08-17: this scan used to check
                                   ; FRAME_END on *every* byte, index and
                                   ; value alike, so a genuine $ff value byte
                                   ; made it stop scanning one byte early --
                                   ; not at a real frame boundary. sid_play_
                                   ; apply then re-walked from sid_rd using
                                   ; correct index/value pairing, ran past
                                   ; the incomplete frame scan had validated,
                                   ; and kept reading unarrived/stale SID_BUF
                                   ; bytes as bogus (reg,val) pairs forever --
                                   ; this loop never returns on its own, and
                                   ; since sid_play runs every IRQ tick, that
                                   ; hung the entire interrupt chain (KERNAL
                                   ; IRQ never ran again either), which is
                                   ; what actually caused every "frozen,
                                   ; cursor stopped, no prompt" symptom this
                                   ; session -- not the protocol-byte changes.
        cpx sid_wr                ; skip the paired value byte -- but only if
        beq sid_play_rts          ; it's actually arrived yet (incomplete
                                   ; frame otherwise: bail, try again next tick)
        inx
        jmp sid_play_scan
sid_play_scan_found:
        ldx sid_rd
sid_play_apply:
        lda SID_BUF,x
        cmp #SID_FRAME_END
        beq sid_play_apply_done
        tay                       ; .y = SID register offset (0-24)
        inx
        lda SID_BUF,x
        sta SID_BASE,y
        inx
        jmp sid_play_apply
sid_play_apply_done:
        inx
        stx sid_rd
        inc sid_frames_played+0
        bne sid_play_rts
        inc sid_frames_played+1
sid_play_rts:
        rts
