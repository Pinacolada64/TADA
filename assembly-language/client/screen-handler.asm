; --- screen-handler.asm ---
; Async mid-line/idle message display: shows incoming server text above
; the prompt while the player is typing or sitting idle, without
; corrupting their unsubmitted input line or losing track of the
; prompt. Split out of tada-client.asm (see [[project_async_prompt_status_line]]
; in project memory) to start separating concerns into their own files,
; the way ImageBBS's shdlr.s is its own module rather than living inside
; the main program -- Ryan's call, 2026-08-19.
;
; Pulled into tada-client.asm via {include:screen-handler_pp.asm} (see
; the Makefile's own preprocessing step for this file) -- c64list
; resolves labels across the include globally, so everything here can
; freely reference and be referenced by tada-client.asm's own labels
; (CHROUT, QTSW, linelen, cursor_pos, linebuf, rx_head, rx_tail, sl_recv,
; handle_recv_byte, sid_mode, status_build_from_table, status_push_buf).
; This file is pure code motion: no behavior change from when these
; routines lived directly in tada-client.asm.

; --- build_status_line: push one complete status-row message in one
; call ---
; X/Y = lo/hi of a null-terminated, {alpha:pokealt}-encoded string (see
; tada-client.asm's status queue section for why pokealt matters).
; Convenience wrapper for the common single-fragment case (e.g. the
; boot-time build-date/time message) -- status_build_from_table +
; status_push_buf are still called directly, not through this, for
; compound messages that interleave runtime-computed content (hex
; digits, decimal numbers) between multiple label fragments, since a
; single static string can't include those (see the SID diagnostics'
; status_print_* routines in tada-client.asm for that pattern).
;
; Padding a short message out to the full 40-column width with $a0
; (reverse-video space) once it hits its null terminator happens in
; redraw_status_row at DISPLAY time, not here at build time -- already
; tested and working that way, so this wrapper doesn't change it.
;
; TODO (Ryan, 2026-08-20): once hourglass_mode display is wired up
; (PlayerFlags.HOURGLASS, see the deferred phase-2 design in project
; memory), the clock belongs on the RIGHT side of STATUS_ROW -- whatever
; renders that will need to co-exist with this left-aligned message
; content and redraw_status_row's own padding, not fight over the same
; columns. Not designed yet; flagging so build_status_line's contract
; (a left-aligned, null-terminated string) doesn't quietly become
; something the clock rendering can't fit next to.
build_status_line:
        jsr status_build_from_table
        jmp status_push_buf

; --- sync_prompt_buf: freeze cur_line_buf/cur_line_len into prompt_buf/
; prompt_len ---
; Called at points known to represent "the current prompt is now fully
; displayed" -- see the comment on cur_line_buf's declaration.
sync_prompt_buf:
        ldy #0
sync_prompt_buf_loop:
        cpy cur_line_len
        bcs sync_prompt_buf_done
        lda cur_line_buf,y
        sta prompt_buf,y
        iny
        jmp sync_prompt_buf_loop
sync_prompt_buf_done:
        sty prompt_len
        rts

; --- relocate_prompt_to_row24 ---
; Called right after sync_prompt_buf settles at wait_for_data's two
; return points. The client has no protocol signal for "this is a
; prompt label" distinct from ordinary dialogue text -- everything comes
; through display_char identically. Ryan's call: treat "the settled
; line ends in '>' (optionally followed by a trailing space)" as the
; signal instead, since every real prompt in this codebase is generated
; by ctx.prompt() and follows that convention ("main > ", "login > ",
; etc -- see network_context.py). If it matches, it gets redrawn a
; second time, pinned to PROMPT_ROW, so the player always types in the
; same fixed place right under STATUS_ROW. Anything that doesn't match
; this pattern (rare) is left exactly where it naturally landed.
;
; Deliberately does NOT erase the original inline copy first (confirmed
; live 2026-08-20 this is the right call, not just a shortcut): doing so
; means walking $9d (CRSR LEFT) back across however many rows the prompt
; spans, and that walk is not reliable this deep into a session with
; many custom (raw-memory, KERNAL-bypassing) scrolls behind it --
; observed CRSR LEFT jump from row 22 stright to row 8 crossing a
; boundary it should never cross in one step, almost certainly because
; term_scroll_advance's raw SCREEN_RAM/COLOR_RAM copies (deliberately
; bypassing KERNAL's own scroll -- that's this whole session's premise)
; never update whatever internal screen-line bookkeeping stock CHROUT's
; CRSR LEFT/RIGHT consult to decide where "the previous row" is, so that
; bookkeeping silently drifts out of sync with what's actually on screen
; the more custom scrolls accumulate. Left as a known open question for
; the sliding-input follow-up, which will also lean on relative cursor
; movement -- worth re-examining there rather than re-litigating here.
; The accepted cost of skipping the erase: the prompt text briefly
; appears twice (once inline where it naturally landed, once pinned at
; PROMPT_ROW) until ordinary scrolling carries the inline copy away,
; which happens within a line or two of normal play.
relocate_prompt_to_row24:
        lda prompt_relocate_enabled
        beq relocate_prompt_rts    ; still mid SwiftLink negotiation --
                                     ; see start:'s own comment
        lda prompt_len
        beq relocate_prompt_rts    ; empty -- nothing to relocate
        ldx prompt_len
        dex                         ; X = index of last char
        lda prompt_buf,x
        cmp #'>'
        beq relocate_prompt_is_prompt
        cmp #' '
        bne relocate_prompt_rts    ; neither '>' nor a trailing space
        cpx #0
        beq relocate_prompt_rts    ; lone space, nothing before it
        dex
        lda prompt_buf,x
        cmp #'>'
        bne relocate_prompt_rts
relocate_prompt_is_prompt:
        ldx #PROMPT_ROW              ; KERNAL_PLOT: X=row, Y=col
        ldy #0
        clc
        jsr KERNAL_PLOT
        lda #0
        sta async_idx
relocate_prompt_redraw_loop:
        lda async_idx
        cmp prompt_len
        bcs relocate_prompt_rts
        tax
        lda prompt_buf,x
        jsr term_chrout
        lda #0
        sta QTSW
        inc async_idx
        jmp relocate_prompt_redraw_loop
relocate_prompt_rts:
        rts

; --- erase_input_line / reprint_input_line ---
; Bracket a service_async_text drain: erase blanks the input line
; (prompt_buf + linebuf's on-screen echo) back to column 0 so incoming
; async text prints on a clean row; reprint puts the same prompt and
; typed-so-far buffer back afterward, cursor restored to cursor_pos.
; Uses async_idx/async_count (plain memory) as loop counters, not X/Y,
; since CHROUT does not reliably preserve them here -- see
; read_line_loop's own comment on this, and redraw_tail for the same
; pattern already proven for the line-editor's own redraws.
erase_input_line:
        lda prompt_len
        clc
        adc cursor_pos
        sta async_count
        jsr async_step_back       ; back to column 0 of the input line
        lda prompt_len
        clc
        adc linelen
        sta async_count
        jsr async_blank           ; blank the whole line
        lda prompt_len
        clc
        adc linelen
        sta async_count
        jsr async_step_back       ; back to column 0 again
        rts

reprint_input_line:
        lda #0
        sta async_idx
reprint_input_line_prompt_loop:
        lda async_idx
        cmp prompt_len
        bcs reprint_input_line_prompt_done
        tax
        lda prompt_buf,x
        jsr term_chrout            ; real content, not navigation -- needs
                                     ; the same STATUS_ROW protection as
                                     ; any other freshly-printed text (see
                                     ; async_step_back/async_blank's own
                                     ; comment for why *those* deliberately
                                     ; don't use term_chrout, unlike this)
        lda #0
        sta QTSW                  ; guard against a literal '"' toggling
        inc async_idx             ; the KERNAL's quote mode -- same reason
        jmp reprint_input_line_prompt_loop ; as read_line_store's own reset
reprint_input_line_prompt_done:
        lda #0
        sta async_idx
reprint_input_line_line_loop:
        lda async_idx
        cmp linelen
        bcs reprint_input_line_line_done
        tax
        lda linebuf,x
        jsr term_chrout
        lda #0
        sta QTSW
        inc async_idx
        jmp reprint_input_line_line_loop
reprint_input_line_line_done:
        lda linelen                ; step the cursor back from end-of-line
        sec                       ; onto cursor_pos, same as redraw_tail
        sbc cursor_pos
        sta async_count
        jsr async_step_back
        rts

; Both loops below call plain CHROUT, not term_chrout -- deliberately:
; term_chrout's own STATUS_ROW handling (term_scroll_advance) shifts the
; whole dialogue window up a row, which is correct for genuinely NEW
; content but wrong here. These two are pure navigation/erasure over
; content that's already on screen (stepping back over an already-
; displayed prompt+typed line, or blanking it back out) -- landing on
; STATUS_ROW mid-walk doesn't mean new content needs a home, it just
; means the walk needs to hop over the reserved row and keep going.
; Confirmed live 2026-08-20: without this, a prompt+typed-line long
; enough to wrap (e.g. the MORE-pagination prompt combined with
; whatever was already on that logical line) walked erase_input_line's
; blind CRSR-LEFT stepping straight onto STATUS_ROW and blanked it to
; plain (non-reverse) spaces -- the status bar visibly disappeared.
async_step_back:
async_step_back_loop:
        lda async_count
        beq async_step_back_done
        dec async_count
        lda #$9d                  ; CRSR LEFT
        jsr CHROUT
        ldx $d6                    ; TBLX -- landed on the reserved row?
        cpx #STATUS_ROW
        bne async_step_back_loop   ; no -- ordinary case, keep going
        ldx #DIALOGUE_LAST_ROW     ; yes -- hop straight over it to the
        ldy #39                     ; last column of the row above
        clc                         ; (KERNAL_PLOT: X=row, Y=col)
        jsr KERNAL_PLOT
        jmp async_step_back_loop
async_step_back_done:
        rts

async_blank:
async_blank_loop:
        lda async_count
        beq async_blank_done
        dec async_count
        lda #$20
        jsr CHROUT
        ldx $d6
        cpx #STATUS_ROW
        bne async_blank_loop
        ldx #24                    ; blanking forward hit the reserved
        ldy #0                      ; row -- hop over it to the start of
        clc                         ; the row below instead of scrolling
        jsr KERNAL_PLOT
        jmp async_blank_loop
async_blank_done:
        rts

; --- service_async_text: display buffered incoming text mid-line ---
; Called from sid_service_background once sid_mode == 0 and linelen != 0
; (the player has started typing). Cheaply returns immediately if
; nothing is buffered; otherwise erases the visible input line, drains
; rx_buf through the normal dispatch, debounces briefly on each gap
; (same "settle countdown" idea as wait_for_data, just shorter, so a
; message sent as several separate server-side writes coalesces into one
; redraw instead of flickering per chunk), then reprints the prompt and
; typed-so-far line once truly idle.
service_async_text:
        lda rx_tail
        cmp rx_head
        beq service_async_text_rts ; nothing buffered -- cheap return
        jsr erase_input_line
service_async_text_poll:
        ldx #$08
        ldy #$00
service_async_text_wait:
        jsr sl_recv
        bcs service_async_text_got_byte
        dey
        bne service_async_text_wait
        dex
        bne service_async_text_wait
        jmp service_async_text_settled
service_async_text_got_byte:
        jsr handle_recv_byte
        jmp service_async_text_poll
service_async_text_settled:
        jsr reprint_input_line
service_async_text_rts:
        rts

; --- service_async_idle: keep the prompt visible through an idle flood ---
; Called from sid_service_background once sid_mode == 0 and linelen == 0
; (nobody has typed anything yet). Unlike service_async_text there's no
; typed-so-far line to protect, so this just drains and displays normally
; -- no erase beforehand. The only real risk is the *previous* prompt
; scrolling away with nothing to replace it: confirmed live 2026-08-18
; that flooding an idle player with 40 rapid pages left the cursor
; blinking with no visible prompt at all once they'd all scrolled past,
; since nothing re-prints a prompt unless the server actually sends a new
; one (ambient pages don't trigger that).
; Distinguishes the two cases once the drain settles by cur_line_len (see
; capture_line_byte -- reset to 0 on every CR):
;   == 0 -- every message that arrived ended in a CR, i.e. the current
;           screen row is genuinely blank right now (the true prompt
;           already scrolled off). Redraw prompt_buf so something is
;           visible again, and mirror it back into cur_line_buf so this
;           routine's own bookkeeping matches what's now on screen.
;   != 0 -- the current row already holds real just-arrived text with no
;           trailing CR (the ordinary case: the server actually did send
;           a fresh prompt, e.g. the trailing "main > " right behind a
;           finished SID stream). That's already correctly on screen;
;           leave it alone and just sync prompt_buf to match, same as
;           wait_for_data does at its own return points.
service_async_idle:
        lda rx_tail
        cmp rx_head
        beq service_async_idle_rts ; nothing buffered -- cheap return
service_async_idle_poll:
        ldx #$08
        ldy #$00
service_async_idle_wait:
        jsr sl_recv
        bcs service_async_idle_got_byte
        dey
        bne service_async_idle_wait
        dex
        bne service_async_idle_wait
        jmp service_async_idle_settled
service_async_idle_got_byte:
        jsr handle_recv_byte
        jmp service_async_idle_poll
service_async_idle_settled:
        lda sid_mode
        bne service_async_idle_rts ; a stream started mid-flood -- leave
                                    ; display as-is, sid_mode != 0 now
                                    ; routes future bytes through the
                                    ; ordinary silent recv path
        lda cur_line_len
        bne service_async_idle_sync ; real text (e.g. a fresh prompt)
                                     ; already sits on the current line
        lda #0
        sta async_idx
service_async_idle_prompt_loop:
        lda async_idx
        cmp prompt_len
        bcs service_async_idle_copyback
        tax
        lda prompt_buf,x
        jsr term_chrout             ; real content -- see reprint_input_
                                      ; line's own comment on this
        lda #0
        sta QTSW
        inc async_idx
        jmp service_async_idle_prompt_loop
service_async_idle_copyback:
        ldy #0
service_async_idle_copyback_loop:
        cpy prompt_len
        bcs service_async_idle_copyback_done
        lda prompt_buf,y
        sta cur_line_buf,y
        iny
        jmp service_async_idle_copyback_loop
service_async_idle_copyback_done:
        sty cur_line_len
        rts
service_async_idle_sync:
        jsr sync_prompt_buf
service_async_idle_rts:
        rts

; --- capture_line_byte: mirror a displayed text byte into cur_line_buf ---
; Called from handle_recv_byte_text for every plain text byte (not SID
; control bytes -- those never reach display_char). Resets cur_line_len
; to 0 on CR, otherwise appends (capped at the buffer's 40 bytes, silently
; dropping anything past that -- only affects fidelity of very long
; unbroken lines, not correctness). Preserves .A throughout so the caller
; can still hand the same byte to display_char afterward.
capture_line_byte:
        cmp #$0d
        bne capture_line_byte_store
        pha
        lda #0
        sta cur_line_len
        pla
        rts
capture_line_byte_store:
        ldy cur_line_len
        cpy #40
        bcs capture_line_byte_rts
        sta cur_line_buf,y
        iny
        sty cur_line_len
capture_line_byte_rts:
        rts

; --- Data ---

; --- Async mid-line message display state ---
; cur_line_buf/cur_line_len is a rolling capture of whatever text is on
; the current output line right now (reset on CR, appended to otherwise
; -- see capture_line_byte, called from handle_recv_byte_text for every
; plain text byte). prompt_buf/prompt_len is a frozen snapshot of that,
; taken at a point known to represent "the current prompt" (wait_for_data
; returning, or sid_service_background catching a post-SID-stream prompt
; up) -- see sync_prompt_buf. The two have to be separate: while
; service_async_text is draining an ambient message mid-line, cur_line_buf
; keeps rolling to track that incoming text, but prompt_buf must stay
; untouched so reprint_input_line still has the original prompt to redraw
; once the message finishes.
cur_line_buf:
        area 40,$00
cur_line_len:
        byte 0
prompt_buf:
        area 40,$00
prompt_len:
        byte 0
async_idx:
        byte 0                   ; scratch for reprint_input_line/erase_input_line
async_count:
        byte 0                   ; -- same convention as redraw_idx/redraw_count,
                                  ; plain memory since CHROUT doesn't reliably
                                  ; preserve X/Y here
