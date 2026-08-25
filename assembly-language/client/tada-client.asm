; tada-client.asm
; TADA C64 Client - Milestone 1
; SwiftLink init, connect to server, negotiate terminal, echo to screen
;
; Build:
;   make build
;
; Requires: SwiftLink cartridge at $de00
;           TADA server listening on 127.0.0.1:34064

; VIC-II colors
{const: VIC_BLACK $00}
{const: VIC_WHITE $01}

; VIC-II chip addresses
{const: VIC_BORDER     $d020}
{const: VIC_BACKGROUND $d021}

; Memory control register -- bits 1-3 pick which 2K character-data chunk
; the VIC-II reads, banked in over the character ROM's two sets at boot
; ($21 = uppercase+graphics, the KERNAL default; $23 = uppercase+
; lowercase, same effect as the SHIFT+Commodore-key toggle). Ryan's call:
; the client now boots straight into upper/lowercase mode so mixed-case
; text (config_menu.asm's Video Settings popup, PREFS's help copy, etc.)
; actually displays as real lower/uppercase rather than folding to all
; caps. Doesn't affect box-drawing glyphs -- config_menu.asm's PETSCII
; corner/line codes ($70/$6e/$6d/$7d/$40/$5d) render identically in both
; character sets (confirmed both via cbmcodecs2's screencode_c64_uc/_lc
; codecs agreeing on the exact same byte for each, and live in VICE:
; SHIFT+C= still shows the box intact) -- only the actual letter codes
; differ between the two sets.
{const: VIC_MEMORY_CONTROL $d018}
{const: CHARSET_UPPER_LOWER $17}

; Comment out to strip all {ifdef:debug}...{endif} diagnostic output
; (the <XX>/[XX] read_line trace, hex_digits/print_hex_byte helpers, etc).
{undef: debug}

; SwiftLink ACIA registers/constants -- moved to swiftlink.asm (2026-08-24)
; alongside the routines that use them, since {const:} is
; macro_preprocessor.py's own textual substitution (resolved only within
; the file it runs on, unlike a real c64list `NAME = value` symbol) --
; it doesn't carry across {include:}s the way constants.asm's addresses
; do, so these had to become plain assignments to be usable from a
; separate included file at all.

; SID chip base address (25 registers, $D400-$D418) -- moved to
; sid_streaming.asm (2026-08-24) alongside SID_FRAME_END below and the
; routines that actually use them (sid_stop/sid_play*); nothing left in
; this file needs it. See swiftlink.asm's header for why {const:}s that
; cross an {include:} boundary have to become plain `=` assignments.

; Binary SID-stream start marker -- multiplexed onto the same connection
; as the CR-terminated PETSCII text protocol. Followed by a 16-bit
; length-prefixed body, NOT an in-band end marker -- see
; handle_recv_byte's own comment for why an end marker doesn't work
; here. See sid_engine/frames.py (server) for the matching encoder.
;
; Confirmed live (not just theoretical): this is a multiplayer server --
; unsolicited text (ally/room/ambient messages) can arrive on this same
; connection independent of anything the player typed, interleaved with
; a play response. A single stray SID_STREAM_START byte inside otherwise
; ordinary text was observed causing later ordinary text to be mistaken
; for SID register data. SID_STREAM_CONFIRM is the fix: a lone
; SID_STREAM_START is no longer trusted by itself -- handle_recv_byte
; waits for this specific second byte immediately after before treating
; anything as a real stream (see handle_recv_byte_maybe_start/_confirm).
; Two specific bytes matching back-to-back by accident is astronomically
; less likely than one -- PROVIDED the second byte is chosen from a
; range ordinary PETSCII text never produces. SID_STREAM_CONFIRM used to
; be $53 ('S'), and the sibling confirms below were $42/$44/$41
; ('B'/'D'/'A') -- all in the $41-$5a range that cbmcodecs2's
; petscii_c64en_lc codec maps to ordinary lowercase letters (common in
; this project's sentence-case text). 'A' hung a live client on
; 2026-08-17: a stray SID_STREAM_START followed by an in-band lowercase
; 'a' misfired handle_recv_byte_apply_confirm, which then blocked
; forever waiting for 5 protocol bytes nobody was sending. All four
; confirm bytes below now live in the $02-$0f gap instead, which
; cbmcodecs2 never maps to a printable character and this client never
; uses as a color/cursor control code.
{const: SID_STREAM_START   $01}
{const: SID_STREAM_CONFIRM $02}   ; unused C64 control code -- see above
{const: SID_STOP           $03}   ; one-byte control signal (not a stream)
                                   ; -- play #stop sends this to silence
                                   ; playback and reset SID state immediately

; Canvas-editor stream marker -- shares CANVAS_STREAM_START's byte value
; with SID_STREAM_START (both are $01; a lone $01 is never trusted by
; itself either way, see handle_recv_byte_maybe_start), but has its own
; *confirm* byte so handle_recv_byte_confirm can tell which kind of
; stream is starting once the second byte arrives. See petscii_editor/
; canvas.py (server side) for the matching encoder/decoder and the same
; reasoning about why a second distinguishing byte is needed at all.
{const: CANVAS_STREAM_START   $01}
{const: CANVAS_STREAM_CONFIRM $04}   ; unused C64 control code --
                                       ; distinct from SID_STREAM_CONFIRM
                                       ; ($02); see its own comment for why
                                       ; not a printable letter

; Display-settings (config menu) stream marker -- same idea/reasoning as
; CANVAS_STREAM_CONFIRM above, own distinct confirm byte so
; handle_recv_byte_confirm can tell this apart from a SID or canvas
; stream. Matches commands/c64_display.py (server side) exactly.
{const: DISPLAY_STREAM_CONFIRM $06}   ; unused C64 control code -- opens
                                        ; the config_menu.asm popup
{const: APPLY_STREAM_CONFIRM   $07}   ; unused C64 control code --
                                        ; silently applies border/bg/blink
                                        ; (sent at login/reconnect, see
                                        ; commands/connect.py's
                                        ; encode_apply_for_player()),
                                        ; no popup involved

; KERNAL routines used by load_petscii_editor/load_config_menu to LOAD an
; overlay module from disk on demand (see load_petscii_editor's own
; comment for why this is a separate on-disk module rather than resident
; code).
{const: KERNAL_SETNAM $ffbd}
{const: KERNAL_SETLFS $ffba}
{const: KERNAL_LOAD    $ffd5}

; KERNAL_PLOT is X=row, Y=column (carry set = read current position into
; X/Y, carry clear = set position from X/Y) -- NOT the commonly-cited
; opposite. Verified empirically 2026-08-20 by poking a stub into free
; RAM ($c000) via the VICE remote monitor and reading back $d3 (PNTR,
; column) / $d6 (TBLX, row) afterward: X came back holding the row value,
; Y the column value, for both directions. Used by term_scroll_advance to
; reposition the cursor after a dialogue-window scroll. Plain `=`, not
; {const:} -- {const:} is a per-file macro_preprocessor.py text
; substitution, invisible to screen-handler.asm's own separate
; preprocessing pass (async_step_back/async_blank need this too); plain
; `=` is a real c64list symbol, resolved globally across {include:}s.
KERNAL_PLOT = $fff0

; Where the petscii_editor overlay module loads and runs. Chosen well
; clear of both this resident program's own growth (currently topping
; out well under $1000 -- see tada-client-vice-labels after a build for
; the exact current top) and the screen/color RAM/KERNAL-adjacent low
; page usage below -- leaves the module ~32K of contiguous RAM up to
; $9fff (BASIC ROM, banked in throughout per this client's design, starts
; at $a000) to work with, far more than a 2000-byte canvas buffer plus
; editor code needs.
{const: OVERLAY_BUF $2000}

; Fixed low-page jump table the petscii_editor overlay (and any future
; loadable module) calls through instead of depending on this resident
; program's own routine addresses staying fixed release to release --
; those addresses shift every time resident code is edited, which would
; otherwise force every overlay module to be reassembled in lockstep.
; JT_SL_SEND (jmp sl_send), JT_SL_RECV (jmp sl_recv), JT_RESUME (jmp
; prompt_loop -- hands control back to the resident request/response loop
; once the overlay is done, saved or cancelled), JT_SAVE_SCREEN/
; JT_RESTORE_SCREEN (jmp save_screen/restore_screen -- SCREEN_RAM/
; COLOR_RAM <-> BACKUP_CHARS/BACKUP_COLORS, shared so petscii_editor.asm's
; help overlay and config_menu.asm's popup don't each need their own
; private 2000-byte backup buffer -- Ryan's ask; only one module is ever
; resident at OVERLAY_BUF at a time, so no concurrent-use concern), and
; JT_SET_BLINK_MASK (jmp set_blink_mask -- .a = new cursor_blink_mask
; value; a setter routine rather than a raw poke since cursor_blink_mask
; is an ordinary resident variable whose address shifts on every resident
; edit, same reason a module can't just `sta` a resident label directly;
; used by config_menu.asm's Video Settings popup to apply a blink speed
; live as the player picks it) -- populated at boot by init_jump_table
; (copied up from jump_table_template, since a PRG's own bytes can only
; occupy one contiguous block starting at its own load address, which is
; well above this page).
;
; Cancel markers (CANVAS_STREAM_CANCEL/DISPLAY_STREAM_CANCEL) for the two
; overlay modules' upload/reply direction -- client -> server only (each
; module sends STREAM_START+this to tell the server the player backed
; out), so they don't carry the same in-band-text collision risk as the
; CONFIRM bytes.
;
; --- Shared jump table + protocol-byte block ---
; JT_BASE/PROTO_TABLE are the single point of truth for the routine
; addresses and framed-stream confirm/cancel bytes tada-client.asm,
; config_menu.asm, and petscii_editor.asm all rely on (see sid_engine/
; frames.py's docstring for the full protocol design). Before 2026-08-17
; each overlay module kept its own private `{const: ... $xx}` copy of
; these -- harmless as long as every copy stayed in sync by hand, until
; it didn't: fixing a collision bug (moving the confirm bytes out of
; printable-letter range, see SID_STREAM_CONFIRM's own comment) updated
; this file and the server but missed both modules' private copies,
; breaking Video Settings' save/cancel round trip live. Both blocks are
; copied up into fixed memory at boot by init_jump_table -- an overlay
; module's `jsr`/`lda` targets can't be this resident program's own
; labels, since those shift on every resident edit -- and every module
; reaches them via a shared `{include:constants.asm}` (a real c64list
; include, resolved at assembly time, unlike this project's own
; `{const:}` macro-preprocessor directive -- see constants.asm's own
; comment) instead of embedding its own literal addresses. Change a value
; once, here, and every module picks it up automatically on its next
; build -- no more hand-sync-and-hope.
;
; JT_BASE/PROTO_TABLE themselves moved here, to $c000, from $0340 (the
; KERNAL "datasette buffer") the same evening -- see constants.asm's own
; comment for why (a live CPU-JAM crash, confirmed via the VICE remote
; monitor, that reproduced under a JiffyDOS KERNAL but not a stock one,
; pointing at JiffyDOS's own documented use of part of that buffer).
{const: CANVAS_STREAM_CANCEL  $43}   ; 'C' -- distinct from CANVAS_STREAM_CONFIRM
{const: DISPLAY_STREAM_CANCEL $58}   ; 'X' -- unrelated to CANVAS_STREAM_CANCEL,
                                       ; different stream, no need to match
{include:constants.asm}

; Zero page pointers
        scr_ptr_lo  = $fb       ; screen write pointer low byte
        scr_ptr_hi  = $fc       ; screen write pointer high byte

        MAX_LINE    = 80        ; keyboard input line buffer size

        RX_HIGH_WATER = 200     ; rx_buf bytes-buffered count that triggers RTS-off
        RX_LOW_WATER  = 32      ; count that triggers RTS back on (hysteresis)

        APPLY_RECV_TIMEOUT_JIFFIES = 60  ; ~1 second at the jiffy clock's
                                          ; ~60Hz tick rate -- see
                                          ; apply_recv_byte's own comment

        SID_RECV_TIMEOUT_JIFFIES = 180   ; ~3 seconds -- see
                                          ; sid_service_background_recv's
                                          ; own comment. Kept well under
                                          ; 256 so the single-byte $a2
                                          ; delta this is compared against
                                          ; can't wrap around and mask a
                                          ; real timeout.

        rx_head     = $f9       ; NMI receive ring buffer: next write index
        rx_tail     = $fa       ; NMI receive ring buffer: next read index

        QTSW        = $d4       ; KERNAL quote-mode switch (212 decimal)

; sid_wr/sid_rd/sid_mode/sid_active/sid_remaining_lo/sid_remaining_hi are
; deliberately NOT zero page (see their `byte 0` definitions in the Data
; section below, near sid_byte_count). They started out at $f5-$f8 and
; $e8/$e9 respectively, but zero page on this machine is KERNAL/BASIC
; territory, not a free scratch area just because nothing *in this file*
; happened to claim a given byte -- confirmed the hard way: $f3/$f4
; turned out to be the KERNAL IRQ handler's own keyboard-decode-table
; pointer (`LDA ($f3),Y` at $ea52, in the stock $ea31 handler
; irq_handler chains into every tick via `jmp (irq_orig)`), and $f5/$f6
; turned out to be ANOTHER pointer the same routine uses (`STA $f5`/
; `LDA ($f5),Y` around $ea9d-$eae2). Both silently corrupted whichever
; of our variables happened to be sitting there, every single IRQ tick.
; None of these six actually need zero page -- they're never used as
; `(zp),Y`/`(zp,X)` indirect pointers, only plain loads/stores/compares
; and `SID_BUF,x`/`SID_BASE,y` indexed addressing -- so moving them to
; ordinary memory sidesteps this entire class of bug for good instead of
; hunting for the next byte the KERNAL doesn't happen to touch.
; rx_head/rx_tail above stay in zero page -- proven reliable across this
; whole project (Milestone 1 onward), no reason to touch what isn't
; broken.

; --- Program start ---

        orig $0801

; BASIC stub: 10 SYS2061
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00

start:
        jsr switch_to_bank3_with_charset  ; MUST run before init_screen
                                            ; (needs HIBASE/the VIC bank
                                            ; already correct) and before
                                            ; init_nmi/init_swiftlink (see
                                            ; its own comment -- SwiftLink's
                                            ; NMI isn't SEI-maskable, and
                                            ; this briefly banks KERNAL's
                                            ; NMI vector out to uninitialized
                                            ; RAM while it runs)
        jsr init_screen
        jsr init_jump_table      ; populate JT_SL_SEND/JT_SL_RECV/JT_RESUME
                                  ; before anything could need them
        jsr init_nmi             ; install our receive handler before the
        jsr init_swiftlink       ; ACIA is told to start raising NMIs on it
        jsr init_sid             ; silence the SID chip, clear playback state
        jsr init_irq             ; install the IRQ dispatcher (sid_play +
                                  ; round-robin task table)

        ; delay to let ACIA settle
        ldx #$ff
@:      ldy #$ff
@:      dey
        bne <@
        dex
        bne <@

        ; wait for server to send negotiation menu, display it.
        ; prompt_relocate_enabled stays 0 through this specific call --
        ; the raw SwiftLink negotiation exchange isn't a real interactive
        ; game prompt (nothing here waits for player input the way a
        ; genuine ctx.prompt() does), but confirmed live 2026-08-20 its
        ; own content can coincidentally end in "> ", false-matching
        ; relocate_prompt_to_row24's heuristic -- and since more
        ; negotiation bytes keep arriving regardless (nothing here is
        ; actually waiting on anything relocate parked at PROMPT_ROW),
        ; ordinary text continues printing from wherever the false
        ; relocate left the cursor: PROMPT_ROW itself, the one row
        ; term_chrout does not protect against overflowing (only
        ; STATUS_ROW triggers its fixup) -- letting KERNAL's own real
        ; whole-screen scroll fire and corrupt STATUS_ROW.
        jsr wait_for_data

        ; respond: 40 columns (C64)
        lda #'4'
        jsr sl_send
        lda #$0d                ; CR
        jsr sl_send

        lda #1
        sta prompt_relocate_enabled ; real game prompts start here on out

        ; fall into prompt loop
        jmp prompt_loop

; --- Prompt loop ---
; Request/response cycle matching the server's ctx.prompt() model: block
; for server output, display it, then block for a full line of keyboard
; input and send it, CR-terminated. Replaces the old free-running
; main_loop (recv-only -- never sent anything past the initial '4', which
; is why login input like '4' at the login menu never reached the server).
prompt_loop:
        jsr wait_for_data        ; block for server output, display it
        jsr read_line            ; block for a line of keyboard input
        jsr send_line            ; ship it, CR-terminated
        jmp prompt_loop

; --- Wait for data from server ---
; Blocks until at least one byte arrives, displays every byte as it
; comes in, then keeps draining until a 16-bit idle-poll countdown
; (X:Y, ~8192 iterations, ~160ms of margin) elapses with no further
; byte, instead of returning on the very first gap -- UNLESS a SID
; stream is confirmed starting (sid_mode reaches 1, just past
; SID_STREAM_CONFIRM), in which case this returns to the prompt
; immediately instead of blocking for however much longer the tune
; takes to finish arriving. Nothing textual is left to show at that
; point (the server always sends its status text before the raw stream),
; and sid_service_background (polled from read_line) keeps draining the
; rest of the transfer -- and feeding sid_play -- while the player types
; their next command, instead of playback stalling until they submit it.
;
; A large margin matters here for a reason beyond ACIA baud timing:
; the server sends the login banner, the "Type 'connect...'" menu text,
; and the "login > " prompt as three *separate* writer.write()/drain()
; calls (network_context.py's send()/prompt()), each of which yields to
; asyncio and can leave a several-millisecond gap before the next chunk
; is actually written to the socket. A short countdown returns between
; chunks; since read_line never polls the ACIA while waiting on the
; keyboard, whatever arrives after that point is silently lost (the
; 6551 has a single-byte receive register, no FIFO), which showed up as
; the first few characters of each chunk going missing.
wait_for_data:
        lda #0
        sta sid_background        ; foreground context -- diagnostics may print
wait_for_data_first:
        jsr sl_recv
        bcc wait_for_data_first   ; keep waiting for the very first byte
        jsr handle_recv_byte
        lda sid_mode
        cmp #1
        beq wait_for_data_backgrounding
wait_for_data_drain:
        ldx #$20                 ; settle countdown high byte
        ldy #$00                 ; settle countdown low byte
wait_for_data_poll:
        jsr sl_recv
        bcs wait_for_data_got_byte
        dey
        bne wait_for_data_poll
        dex
        bne wait_for_data_poll
        jsr sync_prompt_buf       ; settled -- snapshot the current line as
        jsr relocate_prompt_to_row24 ; the prompt, pin it to PROMPT_ROW
        rts                       ; if it looks like a real prompt
wait_for_data_got_byte:
        jsr handle_recv_byte
        lda sid_mode
        cmp #1
        beq wait_for_data_backgrounding
        jmp wait_for_data_drain
wait_for_data_backgrounding:
        jsr sync_prompt_buf
        rts

; --- Init screen ---
; Clear screen, draw the status line, set up screen pointer
init_screen:
        ; VIC_MEMORY_CONTROL is NOT touched here -- switch_to_bank3_with_
        ; charset (called first, in start:) already set it correctly for
        ; gothic_charset's char-ptr slot; re-poking CHARSET_UPPER_LOWER's
        ; old value here would silently point the char generator at $d800
        ; (COLOR_RAM's own fixed address, not usable as glyph bitmap data)
        ; instead of $d000 where gothic_charset actually landed.
        lda #VIC_BLACK
        sta VIC_BORDER
        sta VIC_BACKGROUND
        lda #$93                ; PETSCII clear screen
        jsr CHROUT
        jsr update_status_line
        jsr redraw_status_row     ; blank reverse bar, queue empty so far
        jsr status_push_reset     ; build-date/time message, its own
        ldx #<build_msg           ; batch -- shows immediately (status_
        ldy #>build_msg           ; push_buf's "first message of a fresh
        jsr build_status_line     ; batch" behavior), until the first
                                   ; real SID event replaces it
        ; set screen pointer to row 2 col 0 (front buffer -- see set_
        ; screen_line's own comment on why no low-byte carry is needed)
        lda #<80
        sta scr_ptr_lo
        lda front_hi
        clc
        adc #>80
        sta scr_ptr_hi
        rts

; --- set_screen_line: scr_ptr_lo/hi = CURRENT FRONT BUFFER + row*40 ---
; Input: .a = row number (0-24). Reuses scr_ptr_lo/hi -- this file's own
; zero-page pointer for indirect screen access (see calc_screen_ptr-style
; usage in petscii_editor.asm for the same convention: whichever routine
; needs an indirect pointer right now temporarily owns scr_ptr_lo/hi,
; rather than every routine claiming its own zero-page pair). Uses
; front_hi (not a fixed SCREEN_RAM constant) since the screen buffer is
; now double-buffered -- see the "Double-buffered screen + custom
; charset" section. No low-byte carry needed: both screen buffers are
; 1K-aligned ($xx00), so front_hi's own low byte is always 0.
set_screen_line:
        asl                       ; row*2 -- row_offsets is a word table
        tax
        lda row_offsets,x
        sta scr_ptr_lo
        lda row_offsets+1,x
        clc
        adc front_hi
        sta scr_ptr_hi
        rts

row_offsets:
        word 0,   40,  80,  120, 160, 200, 240, 280, 320, 360
        word 400, 440, 480, 520, 560, 600, 640, 680, 720, 760
        word 800, 840, 880, 920, 960

; --- update_status_line: poke status_msg into row 0, reversed-space-
; padded out to column 39 ---
; Direct SCREEN_RAM pokes, not CHROUT -- 40 bytes via CHROUT means 40
; KERNAL calls plus cursor/scroll bookkeeping this fixed single-line
; status doesn't need. Loops on status_msg's null terminator rather than
; a compile-time byte count (c64list's area/align pseudo-ops can't take
; a *-derived length as their size argument -- confirmed empirically,
; not just a syntax issue -- so there's no compile-time constant to pad
; against here even if we wanted one), so this stays correct however
; long __BuildDate's expansion turns out to be.
update_status_line:
        lda #0                    ; row 0 -- top status line
        jsr set_screen_line
        ldy #0
usl_copy:
        lda status_msg,y
        beq usl_pad
        sta (scr_ptr_lo),y
        iny
        cpy #40
        bne usl_copy
        rts
usl_pad:
        lda #$a0                  ; reverse-video space (same trick as
        sta (scr_ptr_lo),y        ; petscii_editor.asm's progress bar)
        iny
        cpy #40
        bne usl_pad
        rts

{include:swiftlink.asm}

; --- Init jump table ---
; Copies jump_table_template's 25 bytes up into the fixed JT_BASE page
; ($0340) -- see JT_BASE's own comment for why this can't just be
; assembled directly at $0340 (a PRG only occupies one contiguous block
; starting at its own load address, well above this page). The last 7 of
; those 25 bytes are PROTO_TABLE's raw protocol-byte values (not more
; jmp instructions) -- JT_BASE and PROTO_TABLE are contiguous ($0340-
; $0351 and $0352-$0358) precisely so one copy loop populates both; see
; PROTO_TABLE's own comment.
init_jump_table:
        ldx #24
init_jump_table_loop:
        lda jump_table_template,x
        sta JT_BASE,x
        dex
        bpl init_jump_table_loop
        rts

; --- Shared screen save/restore ---
; Backs the whole physical screen (SCREEN_RAM/COLOR_RAM, all 1000 cells
; including the status row) up into BACKUP_CHARS/BACKUP_COLORS and back,
; called through JT_SAVE_SCREEN/JT_RESTORE_SCREEN so any popup-window
; overlay module can save what's on screen, paint its own window over it,
; then restore exactly what was there before -- moved resident (and out
; of petscii_editor.asm, which used to keep a private copy of this exact
; mechanism for its own help overlay) so a second popup-style module
; (e.g. a config menu) doesn't need to duplicate the 2000-byte buffer
; pair and copy routine. petscii_editor.asm's key_help now calls through
; the jump table instead of using its own local copy.
SCREEN_CELLS = 1000

; save_screen/restore_screen always operate against front_hi (the
; CURRENT front buffer, not a fixed SCREEN_RAM constant) -- callers are
; expected to have already run ensure_buffer_a_front first (see that
; routine's own comment), so in practice this always means buffer A, but
; reading front_hi directly here rather than assuming that keeps this
; routine correct on its own terms rather than relying on a caller
; convention it can't verify.
save_screen:
        lda #0
        sta copy_src_lo
        lda front_hi
        sta copy_src_hi
        lda #<BACKUP_CHARS
        sta copy_dst_lo
        lda #>BACKUP_CHARS
        sta copy_dst_hi
        jsr copy_1000
        lda #<COLOR_RAM
        sta copy_src_lo
        lda #>COLOR_RAM
        sta copy_src_hi
        lda #<BACKUP_COLORS
        sta copy_dst_lo
        lda #>BACKUP_COLORS
        sta copy_dst_hi
        jmp copy_1000

restore_screen:
        lda #<BACKUP_CHARS
        sta copy_src_lo
        lda #>BACKUP_CHARS
        sta copy_src_hi
        lda #0
        sta copy_dst_lo
        lda front_hi
        sta copy_dst_hi
        jsr copy_1000
        lda #<BACKUP_COLORS
        sta copy_src_lo
        lda #>BACKUP_COLORS
        sta copy_src_hi
        lda #<COLOR_RAM
        sta copy_dst_lo
        lda #>COLOR_RAM
        sta copy_dst_hi
        jmp copy_1000

; Generic length-parameterized copy. Input: copy_src_lo/hi = source base
; address, copy_dst_lo/hi = dest base address, copy_remaining_lo/hi =
; length (already set by the caller). Self-modified lda/sta operands,
; incrementing the operand bytes directly rather than X/Y indexed
; addressing, since a buffer can exceed 256 bytes -- ported verbatim
; from petscii_editor.asm's own copy_1000 (same "no ds directive, no
; macro parameters" pattern documented in CLIENT_MECHANICS.md).
; Factored out of copy_1000 (now a 2-line wrapper below) 2026-08-20 so
; term_scroll_advance's dialogue-window shift (see [[project_async_
; prompt_status_line]] phase 2 in project memory) could reuse the same
; self-modified-address technique for an 880-byte copy instead of
; hand-rolling a second near-identical loop.
copy_block:
        lda copy_src_lo
        sta copy_src_load+1
        lda copy_src_hi
        sta copy_src_load+2
        lda copy_dst_lo
        sta copy_dst_store+1
        lda copy_dst_hi
        sta copy_dst_store+2
copy_block_loop:
copy_src_load:
        lda $ffff
copy_dst_store:
        sta $ffff
        inc copy_src_load+1
        bne copy_block_src_ok
        inc copy_src_load+2
copy_block_src_ok:
        inc copy_dst_store+1
        bne copy_block_dst_ok
        inc copy_dst_store+2
copy_block_dst_ok:
        lda copy_remaining_lo
        bne copy_block_dec_lo
        dec copy_remaining_hi
copy_block_dec_lo:
        dec copy_remaining_lo
        lda copy_remaining_lo
        ora copy_remaining_hi
        bne copy_block_loop
        rts

; copy_1000 is just copy_block with the length fixed at SCREEN_CELLS --
; save_screen/restore_screen's own copy_src_lo/hi/copy_dst_lo/hi setup
; is unchanged, they just fall into this instead of the old inline loop.
copy_1000:
        lda #<SCREEN_CELLS
        sta copy_remaining_lo
        lda #>SCREEN_CELLS
        sta copy_remaining_hi
        jmp copy_block

; term_scroll_advance's 880-byte dialogue-window shift (rows 1-22 into
; rows 0-21). Screen (glyph) data is now double-buffered (see the "Fixed
; status row + custom scroll" section below) -- shifted straight into the
; invisible back buffer with a plain, unchunked copy_block call, since
; nobody's watching it. COLOR_RAM has no such second copy on real
; hardware (single fixed 1K chip, always live on whichever buffer is
; CURRENTLY front) -- copy_color_chunked below is what that still needs.
DIALOGUE_SHIFT_BYTES = 880

copy_src_lo:
        byte 0
copy_src_hi:
        byte 0
copy_dst_lo:
        byte 0
copy_dst_hi:
        byte 0
copy_remaining_lo:
        byte 0
copy_remaining_hi:
        byte 0

; --- copy_color_chunked ---
; COLOR_RAM's rows 1-22 -> rows 0-21 shift, split into COLOR_CHUNK_BYTES-
; sized pieces, each preceded by its own wait_vblank -- the complete fix
; wait_vblank's own comment used to flag but not implement: an 880-byte
; copy (~1.75ms) runs longer than one vblank window and can spill into
; active drawing time. Only color needs this now -- the screen-glyph half
; moved entirely off-screen into the back buffer (see term_scroll_advance
; below), so color isn't sharing its vblank budget with a screen copy the
; way the original chunked-copy fix (2026-08-22, superseded same day by
; double buffering) had it do. Self-contained (own inline loop, own
; ccc_chunk_remaining countdown) rather than built from copy_block, same
; reasoning as that routine's own single-range design.
; Caller sets copy_src_lo/hi + copy_dst_lo/hi before calling.
COLOR_CHUNK_BYTES = 220           ; 880 / 4
copy_color_chunked:
        lda copy_src_lo
        sta ccc_load+1
        lda copy_src_hi
        sta ccc_load+2
        lda copy_dst_lo
        sta ccc_store+1
        lda copy_dst_hi
        sta ccc_store+2
        lda #<DIALOGUE_SHIFT_BYTES
        sta copy_remaining_lo
        lda #>DIALOGUE_SHIFT_BYTES
        sta copy_remaining_hi
ccc_next_chunk:
        jsr wait_vblank
        lda #COLOR_CHUNK_BYTES
        sta ccc_chunk_remaining
ccc_loop:
ccc_load:
        lda $ffff
ccc_store:
        sta $ffff
        inc ccc_load+1
        bne ccc_src_ok
        inc ccc_load+2
ccc_src_ok:
        inc ccc_store+1
        bne ccc_dst_ok
        inc ccc_store+2
ccc_dst_ok:
        lda copy_remaining_lo
        bne ccc_dec_lo
        dec copy_remaining_hi
ccc_dec_lo:
        dec copy_remaining_lo
        lda copy_remaining_lo
        ora copy_remaining_hi
        beq ccc_done               ; whole 880-byte copy finished
        dec ccc_chunk_remaining
        bne ccc_loop                ; more bytes left in this chunk
        jmp ccc_next_chunk          ; chunk done -- wait for the next vblank
ccc_done:
        rts

ccc_chunk_remaining:
        byte 0

; ============================================================
; --- Fixed status row (row 23) + custom scroll ---
; ============================================================
; Reserves the bottom two screen rows -- row 23 (STATUS_ROW, reverse-
; video, rotating diagnostic messages) and row 24 (input/prompt, left to
; land wherever it naturally does) -- from KERNAL's own whole-screen
; scroll, which only ever triggers once the cursor would need to reach
; row 25 (past physical row 24). term_chrout corrects the cursor back
; down to row 22 (DIALOGUE_LAST_ROW) every time it would otherwise reach
; row 23, so that trigger condition never occurs and KERNAL's real
; scroll never fires at all -- rows 23/24 are structurally protected,
; not just redrawn after the fact.
;
; Validated first in a standalone harness (test_screen_routines.asm,
; same directory) before landing here -- see that file's own history/
; comments and project memory (async-prompt/status-line project, phase
; 2) for the two wrong designs that were tried and rejected along the
; way: relocating "new" content out of STATUS_ROW on every scroll
; (wrong for both the CR and column-wrap triggers -- neither ever
; writes anything real there; a column wrap writes its character into
; the *old* row's last column, not the new row, which the shift below
; already carries forward correctly since that row is within its normal
; source range) and the initially-assumed-backwards KERNAL_PLOT X/Y
; convention (see its own {const:} comment).
STATUS_ROW           = 23
DIALOGUE_LAST_ROW    = 22
PROMPT_ROW           = 24       ; fixed row the player types on, right
                                  ; below STATUS_ROW -- see relocate_
                                  ; prompt_to_row24 (screen-handler.asm)
ROW_BYTES            = 40
STATUS_ROW_OFFSET    = 920      ; STATUS_ROW * ROW_BYTES
PROMPT_ROW_OFFSET    = 960      ; PROMPT_ROW * ROW_BYTES

; ============================================================
; --- Double-buffered screen + custom charset (VIC bank 3) ---
; ============================================================
; 2026-08-22: term_scroll_advance's dialogue-window shift no longer
; copies live, currently-displayed SCREEN_RAM in chunks -- it shifts into
; a completely invisible second screen buffer, at total leisure, then
; flips which one the VIC displays via VIC_MEMORY_CONTROL's screen-
; pointer bits. This is atomic (a handful of cycles) and structurally
; eliminates glyph tearing, rather than just keeping each write burst
; inside a vblank window and hoping. Prototyped first in the standalone
; tada_screen_blit_test.asm harness (same directory) -- see that file and
; project memory (async-prompt/status-line project) for the full
; reasoning trail. COLOR_RAM has no such second copy on real hardware
; (see copy_color_chunked above), so color tearing is mitigated the same
; vblank-chunked way as before, just running alone now.
;
; Both screen buffers live in VIC bank 3 ($c000-$ffff), selected once at
; boot and never switched again -- picked over bank 0 to avoid TWO
; existing reservations: $2000 (OVERLAY_BUF, where petscii_editor.asm/
; config_menu.asm load and run) and $c000-$c018 (JT_BASE/PROTO_TABLE,
; constants.asm -- confirmed via grep before picking SCREEN_BUF_A/B's
; addresses, same discipline constants.asm's own comment used when IT
; claimed $c000). Character ROM is only VIC-visible in banks 0/2, which
; would normally force a ROM-image-copy dance to keep the stock font
; working in bank 3 -- moot here: gothic_charset ({include:}'d below)
; supplies a complete custom 256-glyph charset of its own, an ordinary
; assembled label always visible to the CPU, so switch_to_bank3_with_
; charset only needs one $01=$30 "all RAM" banking window (to make the
; WRITE side -- the real RAM behind $d000-$dfff -- visible) around one
; copy_block call, not a ROM-read step first.
SCREEN_BUF_A    = $c400        ; bank-3-relative slot 1 -- clear of
                                 ; JT_BASE/PROTO_TABLE (slot 0, $c000)
SCREEN_BUF_B    = $c800        ; bank-3-relative slot 2
VIC_BANK_SELECT = $dd00        ; CIA2 port A, bits 0-1 -- INVERTED bank
                                 ; encoding: 00=bank3, 01=bank2, 10=bank1,
                                 ; 11=bank0 (KERNAL boot default). Bits
                                 ; 2-7 drive the serial/IEC bus --
                                 ; preserved, never touched here.
VIC_BANK_BASE   = $c000        ; bank 3's absolute base -- flip_screen_
                                 ; buffer subtracts this out to get the
                                 ; bank-relative value VIC_MEMORY_CONTROL
                                 ; actually wants
HIBASE          = $0288        ; KERNAL's screen-high-byte shadow --
                                 ; CHROUT/PLOT compute addresses from
                                 ; this, not from VIC_MEMORY_CONTROL
                                 ; directly, so a buffer flip has to
                                 ; update both. Purely a CPU-side
                                 ; absolute address, unrelated to
                                 ; VIC_BANK_SELECT.
CHARGEN_DEST    = $d000        ; bank-3-relative slot 4 (char-ptr value 2,
                                 ; 2*$800) -- where the VIC will look for
                                 ; gothic_charset once bank 3 is selected;
                                 ; real RAM behind $d000-$d7ff, not
                                 ; visible to the CPU without the $01
                                 ; trick below
CHARGEN_SIZE    = 2048
CHARGEN_RAM_CONFIG = $30       ; LORAM=0, HIRAM=0, CHAREN=0 -- all RAM,
                                 ; including the cells behind $d000-$dfff
                                 ; (needed to WRITE there -- the CPU can't
                                 ; write through the KERNAL/IO view $01
                                 ; normally leaves mapped)
VIC_D018_INIT   = $14          ; screen-ptr nibble 1 (buffer A, $c400 --
                                 ; ($c400-$c000)>>2<<4 = $10) | char-ptr
                                 ; value 2 ($d000, 2<<1=$04) -- boot value

; --- switch_to_bank3_with_charset ---
; One-time boot setup, called FIRST in start: (before init_screen even --
; init_screen's own screen-clear needs HIBASE/the VIC bank already
; correct). Copies gothic_charset into the RAM VIC bank 3 will read,
; switches the VIC there, and leaves front_hi/HIBASE/VIC_MEMORY_CONTROL
; pointing at SCREEN_BUF_A. Runs under SEI -- MUST happen before init_nmi/
; init_swiftlink (see start:'s own comment): SwiftLink's byte-arrival NMI
; is not maskable by SEI, and $01=$30 banks KERNAL's own NMI vector
; ($fffa) out to uninitialized RAM for the duration of the write window --
; a byte arriving mid-dance, if the cartridge's RxD IRQ were already
; enabled, would jump through garbage. No such risk this early: nothing
; has enabled SwiftLink's interrupt yet.
switch_to_bank3_with_charset:
        sei

        ; --- 1. Select VIC bank 3 ---
        lda VIC_BANK_SELECT
        and #%11111100              ; bits 0-1 = 00 -> bank 3 (inverted
        sta VIC_BANK_SELECT          ; encoding -- see this const's comment)

        ; --- 2. Write gothic_charset into the RAM behind $d000-$dfff that
        ; VIC-in-bank-3 will see at its own bank-relative $1000-$17ff ---
        lda $01
        pha
        lda #CHARGEN_RAM_CONFIG
        sta $01
        lda #<gothic_charset
        sta copy_src_lo
        lda #>gothic_charset
        sta copy_src_hi
        lda #<CHARGEN_DEST
        sta copy_dst_lo
        lda #>CHARGEN_DEST
        sta copy_dst_hi
        lda #<CHARGEN_SIZE
        sta copy_remaining_lo
        lda #>CHARGEN_SIZE
        sta copy_remaining_hi
        jsr copy_block
        pla
        sta $01                     ; restore -- must happen before the
                                      ; very next jsr CHROUT et al, which
                                      ; need KERNAL ROM mapped

        ; --- 3. Point the VIC and KERNAL at SCREEN_BUF_A, char-ptr 2 ---
        lda #VIC_D018_INIT
        sta VIC_MEMORY_CONTROL
        lda #>SCREEN_BUF_A
        sta front_hi
        sta HIBASE

        cli
        rts

; --- flip_screen_buffer: atomically swap which 1K page the VIC displays ---
; Input: .A = the buffer's ABSOLUTE high byte to make the new front
; (SCREEN_BUF_A's or SCREEN_BUF_B's >, i.e. $c4 or $c8).
; Updates both:
;   - VIC_MEMORY_CONTROL bits 4-7, the HARDWARE screen pointer (unit
;     $0400, VALUE RELATIVE TO THE CURRENT VIC BANK -- both buffers are
;     bank-3 slots, so the absolute high byte first gets VIC_BANK_BASE
;     subtracted back out before the shift). new_nibble = relative_hi>>2,
;     since relative_hi is always a multiple of 4 for a page that's also
;     1K-aligned; computed via two LSRs then four ASLs (net: clear the
;     bottom 2 bits, then shift into the top nibble) rather than a lookup
;     table, since it's a pure bit-shuffle with no data-dependent
;     branching.
;   - HIBASE, the KERNAL shadow byte CHROUT/PLOT actually consult to
;     compute where to poke -- without this, term_chrout's own `jsr
;     CHROUT` calls would keep printing into the now-hidden buffer instead
;     of the newly-visible one, invisibly diverging from what's on screen.
;     Set from the ABSOLUTE high byte (a plain CPU-side address, unrelated
;     to VIC bank selection), before the relative subtraction below.
; Existing charset-pointer bits (bits 0-3) are preserved by ANDing them
; back in from the register's current value, not just overwritten.
flip_screen_buffer:
        sta front_hi
        sta HIBASE
        sec
        sbc #>VIC_BANK_BASE
        lsr
        lsr
        asl
        asl
        asl
        asl                         ; .A = (relative_hi >> 2) << 4
        sta flip_d018_val
        lda VIC_MEMORY_CONTROL
        and #$0f                    ; keep charset-pointer bits untouched
        ora flip_d018_val
        sta VIC_MEMORY_CONTROL
        rts

flip_d018_val:
        byte 0
front_hi:
        byte >SCREEN_BUF_A
back_hi:
        byte 0

; --- ensure_buffer_a_front ---
; Called before handing off to any overlay module (load_petscii_editor/
; load_config_menu) -- those are separately-assembled .prg files with
; SCREEN_RAM baked in as a compile-time constant matching SCREEN_BUF_A,
; so they can't know or care which buffer is currently front. Guarantees
; buffer A both IS front (flips if it wasn't) AND actually holds the true
; current dialogue content, not stale leftovers from whenever it was last
; shown -- a bare flip alone would just reveal whatever old screen data
; happened to still be sitting in buffer A's memory from its last turn as
; front. COLOR_RAM needs no copy here (unlike the screen/glyph half) --
; it's a single shared chip, already correct on whichever buffer is
; live, unaffected by which one that is.
ensure_buffer_a_front:
        lda front_hi
        cmp #>SCREEN_BUF_A
        beq ensure_buffer_a_front_rts   ; already front -- nothing to do
        lda #0
        sta copy_src_lo
        lda front_hi
        sta copy_src_hi
        lda #0
        sta copy_dst_lo
        lda #>SCREEN_BUF_A
        sta copy_dst_hi
        jsr copy_1000               ; mirror current front's full 1000
                                      ; cells into buffer A first
        lda #>SCREEN_BUF_A
        jsr flip_screen_buffer
ensure_buffer_a_front_rts:
        rts

; --- term_chrout: drop-in CHROUT replacement for dialogue text ---
; Use instead of a bare `jsr CHROUT` for anything that can legitimately
; advance the cursor a row at a time -- display_char (incoming server
; text) and read_line_store's typed-char echo. Preserves the caller's
; X/Y across the entire call, restored right before every exit --
; confirmed live this matters, not just defensive box-checking:
; term_scroll_advance uses Y freely as its own loop counter, and CHROUT
; itself is already documented elsewhere in this file as not reliably
; preserving X (see read_line's own comment). A caller that uses X/Y as
; its own loop index across a run of term_chrout calls (e.g. printing a
; string char-by-char) would otherwise get that index silently
; clobbered by whichever branch fires here.
; PROMPT_ROW (24) is the TRUE last physical row -- unlike STATUS_ROW
; (23), a character that needs a new row while sitting there triggers
; KERNAL's OWN real whole-screen scroll DURING the CHROUT call itself,
; not after. That can't be caught post-hoc the way STATUS_ROW is: by
; the time term_chrout reads $d6 back, KERNAL's scroll already ran and
; already reset the cursor to a perfectly normal-looking row 24 (same
; as it always leaves it after any scroll) -- nothing about that read
; distinguishes "a real KERNAL scroll just corrupted STATUS_ROW" from
; "ordinary printing, still on row 24, nothing happened". Confirmed live
; 2026-08-20: ordinary text continuing to print after relocate_prompt_
; to_row24 parked the cursor there (an unanswered/still-arriving
; response following what looked like, but wasn't reliably, a genuine
; prompt) corrupted STATUS_ROW exactly this way, and the post-hoc check
; alone never caught it.
;
; So this checks BEFORE calling CHROUT: if already on PROMPT_ROW and
; this character would need a new row (a CR, or filling the last
; column), redirect through term_scroll_advance FIRST -- landing safely
; at DIALOGUE_LAST_ROW instead of letting KERNAL scroll from row 24 at
; all. Ordinary text that overflows PROMPT_ROW genuinely belongs back
; in the normal scrolling dialogue area above STATUS_ROW anyway; only
; the player's own current input belongs pinned at PROMPT_ROW itself.
term_chrout:
        stx term_saved_x
        sty term_saved_y
        pha
        ldx $d6
        cpx #PROMPT_ROW
        bne term_chrout_plain
        cmp #$0d
        beq term_chrout_prevent_cr
        ldx $d3
        cpx #39                     ; about to fill the last column?
        bne term_chrout_plain
        ; wrap case: this character would fill PROMPT_ROW's last column,
        ; and KERNAL's own advance-in-preparation-for-the-next-character
        ; would need row 25 -- shift first, THEN print this character at
        ; the now-current (DIALOGUE_LAST_ROW) position, which has a
        ; full fresh 40 columns to receive it safely.
        jsr term_scroll_advance
        jmp term_chrout_plain
term_chrout_prevent_cr:
        ; CR has no glyph of its own -- term_scroll_advance's shift +
        ; reposition-to-DIALOGUE_LAST_ROW-col0 already IS everything a
        ; CR should do; nothing left to hand to CHROUT.
        jsr term_scroll_advance
        pla
        jmp term_chrout_rts
term_chrout_plain:
        pla
        jsr CHROUT
        ldx $d6                    ; TBLX -- physical cursor row
        cpx #STATUS_ROW
        bne term_chrout_rts        ; exact match only -- NOT bcc/"< 23".
                                     ; Safe to be this precise now that
                                     ; PROMPT_ROW (24) is a real,
                                     ; deliberately-PLOTted-to position
                                     ; text can legitimately sit at and
                                     ; keep printing from (relocate_
                                     ; prompt_to_row24) -- bcc would
                                     ; wrongly fire term_scroll_advance
                                     ; on every character printed there.
                                     ; Behaviorally identical to the old
                                     ; bcc for rows 0-22 (X was never >23
                                     ; under the old model, so "< 23" and
                                     ; "== 23" only ever differed for a
                                     ; row that couldn't occur yet).
        jsr term_scroll_advance
term_chrout_rts:
        ldx term_saved_x
        ldy term_saved_y
        rts

term_saved_x:
        byte 0
term_saved_y:
        byte 0

; --- term_cursor_left / term_cursor_right: single-step relative cursor
; move ($9d/$1d) that skips over STATUS_ROW instead of landing on it,
; without triggering a scroll -- there's no new content here, just
; navigation within already-displayed text (arrow-key movement, the
; single step-back after a DEL, redraw_tail's own step-back). Same
; principle as screen-handler.asm's async_step_back/async_blank (see
; their own comment for the full reasoning); those two loop internally
; and stay as their own inline copies since they were already verified
; working, but any OTHER single-step $9d/$1d call site should use these
; instead of a bare CHROUT -- confirmed live 2026-08-20 that missing
; this class of call site is exactly what let a single stray character
; land in STATUS_ROW with no correction at all.
term_cursor_left:
        lda #$9d
        jsr CHROUT
        ldx $d6
        cpx #STATUS_ROW
        bne term_cursor_left_rts
        ldx #DIALOGUE_LAST_ROW
        ldy #39
        clc
        jsr KERNAL_PLOT
term_cursor_left_rts:
        rts

term_cursor_right:
        lda #$1d
        jsr CHROUT
        ldx $d6
        cpx #STATUS_ROW
        bne term_cursor_right_rts
        ldx #24
        ldy #0
        clc
        jsr KERNAL_PLOT
term_cursor_right_rts:
        rts

; --- wait_vblank: busy-wait until the raster beam reaches line 250 ---
; Comfortably past the visible area on both PAL (312 lines/frame) and
; NTSC (262 lines/frame) -- moves the START of each copied chunk's
; screen-memory writes to an off-screen moment, rather than however
; mid-frame the triggering character happened to land. Originally called
; once before an 880-byte-times-two atomic copy, which (checking real
; frames extracted from a screen recording, see project memory) showed
; no visible tearing in practice despite the copy's ~3.5ms runtime
; exceeding one vblank window -- but copy_dialogue_block_chunked (2026-08-
; 22) now calls this once per DIALOGUE_CHUNK_BYTES chunk instead, the
; complete fix this comment used to defer: every actual write burst stays
; comfortably inside its own blanking window, full stop, rather than
; relying on empirically-clean-so-far timing margins. $d012 alone
; (without checking $d011 bit 7) is sufficient for line 250 since that's
; well under 256.
wait_vblank:
        lda $d012
        cmp #250
        bne wait_vblank
        rts

; --- term_scroll_advance: double-buffered dialogue-window shift ---
; Rows 1-22 up into rows 0-21, discarding old row 0, then blank the fresh
; row 22 and reposition the cursor there. Both of term_chrout's triggers
; (a bare CR, or a column wrap) reduce to exactly this -- neither ever
; leaves real new content in STATUS_ROW to preserve (see this section's
; own header comment).
;
; Prepares the BACK buffer completely off-screen, at leisure, then flips:
;   1. Shift glyphs: front rows 1-22 -> back rows 0-21 (one atomic
;      copy_block call -- back buffer is invisible, no vblank pressure).
;   2. Blank back buffer's fresh row 22.
;   3. Mirror PROMPT_ROW (24) from front into back too -- NOT part of the
;      row 1-22 shift, so without this the back buffer's prompt row would
;      still hold whatever was there the LAST time it was front (stale,
;      possibly several scrolls old) until the next explicit reprint_
;      input_line/relocate_prompt_to_row24 call caught up -- a real,
;      if transient, visible-glitch class this closes outright rather
;      than relying on "probably gets overwritten before anyone notices".
;   4. Stamp back buffer's STATUS_ROW with the current queued message
;      (redraw_status_row_to) -- same "unconditional self-healing repaint
;      every scroll" reasoning the single-buffer version used, still
;      valid: whichever buffer is about to become front must be correct
;      BEFORE it's shown, not patched up after.
;   5. Chunk-shift COLOR_RAM in place (still live/visible the whole
;      time -- see copy_color_chunked's own comment).
;   6. One final wait_vblank, then flip: back becomes front, atomically.
term_scroll_advance:
        lda front_hi
        cmp #>SCREEN_BUF_A
        beq tsa_back_is_b
        lda #>SCREEN_BUF_A
        jmp tsa_back_known
tsa_back_is_b:
        lda #>SCREEN_BUF_B
tsa_back_known:
        sta back_hi

        ; --- 1. Shift glyphs: front rows 1-22 -> back rows 0-21 ---
        lda #<ROW_BYTES
        sta copy_src_lo
        lda front_hi
        sta copy_src_hi
        lda #0
        sta copy_dst_lo
        lda back_hi
        sta copy_dst_hi
        lda #<DIALOGUE_SHIFT_BYTES
        sta copy_remaining_lo
        lda #>DIALOGUE_SHIFT_BYTES
        sta copy_remaining_hi
        jsr copy_block

        ; --- 2. Blank back buffer's fresh row 22 ---
        ; scr_ptr = back_hi:00 + 880 ($0370) -- direct arithmetic since
        ; DIALOGUE_LAST_ROW is a fixed compile-time row here.
        lda #<880
        sta scr_ptr_lo
        lda back_hi
        clc
        adc #>880
        sta scr_ptr_hi
        ldy #0
        lda #$20
tsa_blank:
        sta (scr_ptr_lo),y
        iny
        cpy #40
        bne tsa_blank

        ; --- 3. Mirror PROMPT_ROW, front -> back (via copy_block -- reads
        ; and writes two DIFFERENT buffers at once, so a single scr_ptr_
        ; lo/hi indirect pointer can't do this, unlike step 2's blank) ---
        lda #<PROMPT_ROW_OFFSET
        sta copy_src_lo
        lda front_hi
        clc
        adc #>PROMPT_ROW_OFFSET
        sta copy_src_hi
        lda #<PROMPT_ROW_OFFSET
        sta copy_dst_lo
        lda back_hi
        clc
        adc #>PROMPT_ROW_OFFSET
        sta copy_dst_hi
        lda #<ROW_BYTES
        sta copy_remaining_lo
        lda #>ROW_BYTES
        sta copy_remaining_hi
        jsr copy_block

        ; --- 4. Stamp back buffer's STATUS_ROW before it's ever shown ---
        lda back_hi
        jsr redraw_status_row_to

        ; --- 5. Chunk-shift COLOR_RAM (still live the whole time) ---
        lda #<(COLOR_RAM+ROW_BYTES)
        sta copy_src_lo
        lda #>(COLOR_RAM+ROW_BYTES)
        sta copy_src_hi
        lda #<COLOR_RAM
        sta copy_dst_lo
        lda #>COLOR_RAM
        sta copy_dst_hi
        jsr copy_color_chunked

        ; --- 6. Flip: back becomes front, atomically ---
        jsr wait_vblank
        lda back_hi
        jsr flip_screen_buffer
        ldx #DIALOGUE_LAST_ROW      ; KERNAL_PLOT: X=row, Y=col
        ldy #0
        clc
        jsr KERNAL_PLOT
        rts


; ============================================================
; --- Status queue (reverse-video, rotating, fixed row 23) ---
; ============================================================
; Up to STATUS_QUEUE_MAX null-terminated messages, each built up via
; status_putc (or status_build_from_table for a whole pre-encoded
; literal at once) into status_build_buf, then handed to status_push_buf
; to land in the queue. redraw_status_row paints whichever one
; status_queue_read currently points at, reverse video, padded to 40
; columns; status_service (polled from sid_service_background --
; deliberately mainline-only, NOT the IRQ round-robin task table, to
; avoid a CHROUT/PLOT-vs-KERNAL-zero-page reentrancy hazard) rotates to
; the next one every STATUS_ROTATE_JIFFIES.
;
; Queue slot content is real, pre-encoded SCREEN CODES, not PETSCII/
; ASCII -- redraw_status_row pokes it straight into SCREEN_RAM rather
; than routing it through CHROUT. Static label text must be declared
; under {alpha:pokealt} (see build_msg/status label tables below); any
; caller building dynamic content (hex digits, decimal numbers) must
; likewise emit screen-code bytes, not ASCII -- digits 0-9 happen to
; already match ASCII byte-for-byte in this charset, but letters don't
; (screen code 'A' is $01, not ASCII $41).
STATUS_QUEUE_MAX     = 4
STATUS_SLOT_LEN      = 40       ; 39 visible chars max + null terminator
STATUS_ROTATE_JIFFIES_LO = $2c  ; 300 jiffies (~5s @ ~60Hz), low byte
STATUS_ROTATE_JIFFIES_HI = $01  ; 300 jiffies, high byte

status_build_from_table:
        stx scr_ptr_lo
        sty scr_ptr_hi
        ldy #0
status_build_from_table_loop:
        lda (scr_ptr_lo),y
        beq status_build_from_table_done
        jsr status_putc
        iny
        jmp status_build_from_table_loop
status_build_from_table_done:
        rts

; Preserves the caller's Y across the call -- status_build_from_table's
; own string-index loop uses Y, and this routine also uses Y internally
; (status_build_idx bookkeeping); without saving/restoring it, the
; caller's index silently gets reset to whatever value this routine's
; own use of Y last left it at, skipping every other source character.
status_putc:
        sty status_putc_saved_y
        ldy status_build_idx
        cpy #STATUS_SLOT_LEN-1
        bcs status_putc_rts
        sta status_build_buf,y
        iny
        sty status_build_idx
status_putc_rts:
        ldy status_putc_saved_y
        rts

status_putc_saved_y:
        byte 0

status_push_reset:
        lda #0
        sta status_queue_count
        sta status_queue_write
        sta status_queue_read
        rts

status_push_buf:
        ldy status_build_idx
        lda #0
        sta status_build_buf,y
        lda status_queue_write
        jsr status_slot_addr
        ldy #0
status_push_buf_copy:
        lda status_build_buf,y
        sta (scr_ptr_lo),y
        beq status_push_buf_copied
        iny
        cpy #STATUS_SLOT_LEN
        bcc status_push_buf_copy
status_push_buf_copied:
        lda #0
        sta status_build_idx
        inc status_queue_write
        lda status_queue_write
        cmp #STATUS_QUEUE_MAX
        bcc status_push_buf_no_wrap
        lda #0
        sta status_queue_write
status_push_buf_no_wrap:
        lda status_queue_count
        cmp #STATUS_QUEUE_MAX
        bcs status_push_buf_count_done
        inc status_queue_count
status_push_buf_count_done:
        lda status_queue_count
        cmp #1
        bne status_push_buf_rts
        lda #0
        sta status_queue_read
        jsr redraw_status_row
        lda $a2
        sta status_rotate_last_lo
        lda $a1
        sta status_rotate_last_hi
status_push_buf_rts:
        rts

; .a = slot index 0..3 -> scr_ptr_lo/hi
status_slot_addr:
        tay
        lda status_slot_lo,y
        sta scr_ptr_lo
        lda status_slot_hi,y
        sta scr_ptr_hi
        rts

; Called from sid_service_background every read_line poll iteration.
status_service:
        lda status_queue_count
        cmp #2
        bcc status_service_rts    ; 0 or 1 messages queued -- nothing to
                                    ; rotate to
        lda $a2
        sec
        sbc status_rotate_last_lo
        sta status_elapsed_lo
        lda $a1
        sbc status_rotate_last_hi
        sta status_elapsed_hi
        lda status_elapsed_hi
        cmp #STATUS_ROTATE_JIFFIES_HI
        bcc status_service_rts
        bne status_service_due
        lda status_elapsed_lo
        cmp #STATUS_ROTATE_JIFFIES_LO
        bcc status_service_rts
status_service_due:
        jsr status_rotate
status_service_rts:
        rts

status_elapsed_lo:
        byte 0
status_elapsed_hi:
        byte 0

status_rotate:
        inc status_queue_read
        lda status_queue_read
        cmp status_queue_count
        bcc status_rotate_redraw
        lda #0
        sta status_queue_read
status_rotate_redraw:
        jsr redraw_status_row
        lda $a2
        sta status_rotate_last_lo
        lda $a1
        sta status_rotate_last_hi
        rts

; --- redraw_status_row: repaint the CURRENT FRONT buffer's STATUS_ROW ---
; Thin wrapper over redraw_status_row_to for the common case (every call
; site except term_scroll_advance's own back-buffer pre-paint doesn't
; care which buffer is front, it just wants "whatever's on screen now").
redraw_status_row:
        lda front_hi
        ; falls through

; --- redraw_status_row_to: repaint an EXPLICIT buffer's STATUS_ROW ---
; Input: .A = target buffer's high byte.
; Needed because term_scroll_advance must paint the BACK buffer's status
; row (the one about to become front) BEFORE flipping, not whichever
; buffer happens to be front at the moment it's called. Self-modifies
; only the high byte of each STA operand's absolute address
; (STATUS_ROW_OFFSET's low byte, $98, is identical in both buffers since
; both are 1K-aligned; only the page differs) -- target_hi = buffer_hi +
; 3, since STATUS_ROW_OFFSET (920, $0398) contributes high byte $03.
; Otherwise unchanged from the single-buffer version: reverse video,
; padded to 40 columns, pure raw pokes (queue content is pre-encoded
; real screen codes already, same convention update_status_line uses for
; row 0's banner). Destination addressing (not set_screen_line) frees
; scr_ptr_lo/hi to be used solely for the source (queue slot) pointer --
; a raw copy-with-OR needs two concurrent pointers, and this file's
; convention is one shared transient pointer, not a second dedicated
; zero-page pair for something this narrow.
redraw_status_row_to:
        clc
        adc #>STATUS_ROW_OFFSET
        sta rsrt_store+2
        sta rsrt_pad_store+2
        sta rsrt_blank_store+2
        lda status_queue_count
        beq rsrt_blank
        lda status_queue_read
        jsr status_slot_addr        ; scr_ptr_lo/hi = &status_queue[read]
        ldy #0
rsrt_copy:
        cpy #39
        bcs rsrt_pad
        lda (scr_ptr_lo),y
        beq rsrt_pad
        ora #$80                    ; reverse video -- same $80-bit trick
rsrt_store:
        sta STATUS_ROW_OFFSET,y     ; high byte self-modified above
        iny
        jmp rsrt_copy
rsrt_pad:
        lda #$a0                    ; reverse-video space
rsrt_pad_loop:
        cpy #40
        bcs rsrt_rts
rsrt_pad_store:
        sta STATUS_ROW_OFFSET,y
        iny
        jmp rsrt_pad_loop
rsrt_rts:
        rts
rsrt_blank:
        ldy #0
        lda #$a0
rsrt_blank_loop:
rsrt_blank_store:
        sta STATUS_ROW_OFFSET,y
        iny
        cpy #40
        bne rsrt_blank_loop
        rts

status_build_buf:
        area STATUS_SLOT_LEN, 0
status_build_idx:
        byte 0

status_queue0:
        area STATUS_SLOT_LEN, 0
status_queue1:
        area STATUS_SLOT_LEN, 0
status_queue2:
        area STATUS_SLOT_LEN, 0
status_queue3:
        area STATUS_SLOT_LEN, 0

status_slot_lo:
        byte <status_queue0, <status_queue1, <status_queue2, <status_queue3
status_slot_hi:
        byte >status_queue0, >status_queue1, >status_queue2, >status_queue3

status_queue_count:
        byte 0
status_queue_write:
        byte 0
status_queue_read:
        byte 0
status_rotate_last_lo:
        byte 0
status_rotate_last_hi:
        byte 0

; --- Build-date/time status message -- shown at boot as its own batch
; (status_push_buf's "first message of a fresh batch" behavior displays
; it immediately) until the first real event (e.g. a SID stream) pushes
; its own batch and replaces it. {alpha:pokealt} makes this `ascii`
; literal emit real screen codes at assembly time -- required since
; redraw_status_row pokes queue content straight into SCREEN_RAM rather
; than going through CHROUT's own PETSCII->screencode conversion. Reset
; to {alpha:normal} right after so this doesn't leak into anything below
; that uses plain `ascii`.
{alpha:pokealt}
build_msg:
        ascii "build "
        ascii {usedef:__BuildDate}
        ascii " "
        ascii {usedef:__BuildTime}
        byte 0
{alpha:normal}

; .a = new cursor_blink_mask value -- see JT_SET_BLINK_MASK's own comment.
set_blink_mask:
        sta cursor_blink_mask
        rts

jump_table_template:
        jmp sl_send
        jmp sl_recv
        jmp prompt_loop
        jmp save_screen
        jmp restore_screen
        jmp set_blink_mask
        byte SID_STREAM_START, SID_STREAM_CONFIRM, CANVAS_STREAM_CONFIRM
        byte CANVAS_STREAM_CANCEL, DISPLAY_STREAM_CONFIRM
        byte DISPLAY_STREAM_CANCEL, APPLY_STREAM_CONFIRM

; --- Load the petscii_editor overlay module and hand control to it ---
; Called from handle_recv_byte_canvas_confirm once a real canvas stream
; is confirmed starting (CANVAS_STREAM_START+CANVAS_STREAM_CONFIRM seen
; back-to-back). The module is a separate .prg (petscii_editor.asm,
; assembled with its own `orig OVERLAY_BUF`) rather than resident code,
; so ordinary play/talk/movement sessions don't pay for a screen editor's
; code+buffers sitting in memory the whole time -- it's only loaded when
; a "banner edit" session actually starts.
;
; Uses LOAD "...",8,1 (secondary address 1: use the address embedded in
; the file's own 2-byte header, i.e. OVERLAY_BUF, same convention as a
; normal `LOAD"program",8,1`) rather than passing an explicit target
; address, so the module's own assembly is the single source of truth
; for where it lives.
;
; The rest of this stream (the 16-bit length prefix + 2000-byte canvas
; body) is still arriving over SwiftLink while the disk LOAD runs --
; nmi_handler keeps draining it into rx_buf regardless of what mainline
; is doing (same reason sid_engine's background streaming works), so
; nothing is lost during the load's real wall-clock time. The module
; picks up that data itself via JT_SL_RECV once it's running.
load_petscii_editor:
        lda #10                  ; length of "PETSCII.ED" below
        ldx #<petscii_editor_filename
        ldy #>petscii_editor_filename
        jsr KERNAL_SETNAM
        lda #1                   ; file number (arbitrary, unused after LOAD)
        ldx #8                   ; device 8
        ldy #1                   ; secondary address 1 -- use the file's
                                  ; own embedded load address
        jsr KERNAL_SETLFS
        lda #0                   ; ignored when SA=1, but LOAD still wants A=0
        jsr KERNAL_LOAD
        bcs load_overlay_error   ; carry set -- .a holds the KERNAL
                                  ; error number (Ryan caught this: an
                                  ; earlier version jumped to OVERLAY_BUF
                                  ; unconditionally, which on any real LOAD
                                  ; failure -- wrong device, file not found,
                                  ; disk error -- executes whatever garbage
                                  ; happened to already be sitting at $2000
                                  ; instead of failing cleanly)
        jsr ensure_buffer_a_front ; overlay modules hardcode SCREEN_RAM as
                                  ; a compile-time constant matching
                                  ; buffer A -- they have no way to know
                                  ; which buffer is currently front, so
                                  ; this guarantees it's always A before
                                  ; handing off (see that routine's own
                                  ; comment)
        jmp OVERLAY_BUF           ; hand off -- the module returns control
                                  ; via JT_RESUME when it's done, not rts

; --- Load the config_menu overlay module and hand control to it ---
; Called from handle_recv_byte_display_confirm once a real display-
; settings stream is confirmed starting. Same LOAD "...",8,1 (secondary
; address 1) convention as load_petscii_editor above -- see that
; routine's own comment for the full reasoning (shared here rather than
; repeated).
load_config_menu:
        lda #10                  ; length of "CONFIG.MNU" below
        ldx #<config_menu_filename
        ldy #>config_menu_filename
        jsr KERNAL_SETNAM
        lda #1
        ldx #8
        ldy #1
        jsr KERNAL_SETLFS
        lda #0
        jsr KERNAL_LOAD
        bcs load_overlay_error
        jsr ensure_buffer_a_front ; see load_petscii_editor's own comment
        jmp OVERLAY_BUF

; LOAD failed (either overlay module) -- report the KERNAL error number
; and hand control back to the ordinary prompt loop instead of jumping
; into unloaded memory.
load_overlay_error:
        pha
        lda #'?'
        jsr term_chrout
        lda #'L'
        jsr term_chrout
        lda #'O'
        jsr term_chrout
        lda #'A'
        jsr term_chrout
        lda #'D'
        jsr term_chrout
        lda #' '
        jsr term_chrout
        lda #'E'
        jsr term_chrout
        lda #'R'
        jsr term_chrout
        lda #'R'
        jsr term_chrout
        lda #' '
        jsr term_chrout
        lda #'$'
        jsr term_chrout
        pla
        jsr sid_print_hex_byte
        lda #$0d
        jsr term_chrout
        jmp prompt_loop

; {alpha:alt} makes the `ascii` line below emit $C1-$DA range bytes for
; the uppercase letters instead of plain $41-$5A ASCII -- required, not
; cosmetic: verified live (VICE monitor: LOAD against a real c1541-
; written disk) that plain ASCII bytes get KERNAL error $04 (FILE NOT
; FOUND) even though they display identically to a human. A real C64
; disk directory stores uppercase letters in the $C1-$DA range (the
; "shifted" PETSCII codes for those keys) -- c1541 -write's own ASCII-
; input case inversion (lowercase in -> uppercase $C1-$DA out) produces
; this same range, and LOAD only succeeds once SETNAM's filename bytes
; match it exactly, byte for byte. Reset to {alpha:normal} (this file's
; true default -- see c64list's own manual) immediately after so this
; doesn't leak into hex_digits/status_msg/sid_hex_digits further down,
; which are plain CHROUT display text, not filenames, and must stay in
; ordinary ASCII-range encoding.
{alpha:alt}
petscii_editor_filename:
        ascii "PETSCII.ED"
config_menu_filename:
        ascii "CONFIG.MNU"
{alpha:normal}

{include:sid_streaming.asm}

{include:screen-handler_pp.asm}

; gothic_charset -- no macro-preprocessor directives, so (like
; constants.asm) included directly, not via a _pp.asm preprocessed copy.
{include:gothic-charset.asm}

; --- Blinking input cursor ---
; GETIN-driven input (unlike CHRIN) never engages the KERNAL's own
; line-editor cursor blink, so read_line draws its own, blinked via one
; bit of $a2 (fastest-changing byte of the KERNAL's free-running jiffy
; clock, ticks ~60/sec) -- which bit is configurable via cursor_blink_
; mask (config_menu.asm's Video Settings popup), rather than the fixed
; bit 4 (~2-3 Hz) this used to hardcode.
;
; This used to print a literal reverse-video space and step back onto
; it, which only worked while the cursor was always parked past the end
; of the buffer (nothing real underneath to clobber). Once CRSR
; LEFT/RIGHT could park the cursor mid-line, that same space-print
; overwrote whatever real character was already sitting there -- the
; cursor was destroying buffer contents just by blinking over them.
; Instead, cursor_toggle flips the reverse-video bit (bit 7) of
; whatever screen code is actually under the cursor right now, read via
; the KERNAL's own PNT/PNTR zero-page vars ($d1/$d2 = pointer to the
; start of the current screen line, $d3 = cursor column within it) --
; the same pair the KERNAL's own cursor blink IRQ routine uses. These
; stay in sync via CHROUT's normal screen-editor bookkeeping regardless
; of this client's custom IRQ handler, since IRQ only affects blink
; timing/STOP-key scanning here, not CHROUT's own screen writes. EOR
; #$80 (not a plain ORA) so a show/hide pair is always a clean round
; trip no matter what the underlying character was, including if it
; already happened to be a reverse-video glyph.
cursor_phase:
        byte 0                   ; 0 = currently erased, 1 = currently drawn

; Which single bit of $a2 update_cursor tests -- one bit set picks a
; blink speed (higher bit = slower, since it takes longer for a
; higher/slower-changing bit to flip): $08 fast, $10 normal (the
; original hardcoded default), $20 slow, $40 very slow. $00 is a
; reserved sentinel meaning "solid, no blink" (speed 5) -- see
; update_cursor's own comment. Must match commands/c64_display.py's
; BLINK_SPEED_MASKS (speed# 1-5 -> mask) and config_menu.asm's own copy
; of that table exactly. Set by config_menu.asm's Video Settings popup
; when the player picks a speed and applies it live; stays at the
; default otherwise.
cursor_blink_mask:
        byte $10

rts_state:
        byte 1                   ; 1 = RTS currently asserted (ready), 0 = deasserted

x_save:
        byte 0                   ; TEMP: scratch for the read_line_loop hex-dump diagnostic
y_save:
        byte 0                   ; scratch for preserving .Y across update_cursor/CHROUT calls

; Call once per read_line poll iteration. Only touches the screen on a
; phase transition, so it doesn't flicker while sitting in one state.
; cursor_blink_mask == $00 is a reserved sentinel meaning "solid, no
; blink at all" (blink speed 5 -- Ryan's ask: some screen-reader/
; accessibility software, e.g. Gadget, doesn't get along with a
; blinking cursor). AND-ing against a real speed's mask (`$08`/`$10`/
; `$20`/`$40`, each a single bit) is what makes a 0 mask meaningless as
; "always show" on its own -- `$a2 AND $00` is always 0, which without
; this special case would read as "always erased", the opposite of
; solid. So: mask 0 skips the AND/blink logic entirely and just leaves
; the cursor drawn once it's on, never toggling it back off.
update_cursor:
        lda cursor_blink_mask
        bne update_cursor_blink
        lda cursor_phase
        bne update_cursor_done   ; already drawn -- solid, leave it
        jsr cursor_toggle
        lda #1
        sta cursor_phase
        rts
update_cursor_blink:
        lda $a2
        and cursor_blink_mask
        beq cursor_want_off
        lda cursor_phase
        bne update_cursor_done   ; already on
        jsr cursor_toggle
        lda #1
        sta cursor_phase
        rts
cursor_want_off:
        lda cursor_phase
        beq update_cursor_done   ; already off
        jsr cursor_toggle
        lda #0
        sta cursor_phase
update_cursor_done:
        rts

; Flip the reverse-video bit of the screen code currently under the
; cursor, in place. Doesn't move the screen cursor or call CHROUT at
; all, so the real character underneath survives regardless of how many
; times this fires.
cursor_toggle:
        ldy $d3                  ; PNTR -- cursor column within current line
        lda ($d1),y               ; PNT -- on-screen char code under cursor
        eor #$80
        sta ($d1),y
        rts

; Force the cursor to the "erased" state right before a real keystroke
; is handled, whatever phase update_cursor last left it in. Safe to
; call unconditionally -- a no-op if it's already erased.
cursor_hide:
        lda cursor_phase
        beq cursor_hide_done
        jsr cursor_toggle
        lda #0
        sta cursor_phase
cursor_hide_done:
        rts

; --- Read a line of keyboard input into linebuf, echo to screen ---
; Blocks until RETURN is pressed. Handles DEL as backspace.
; Terminates linebuf with $00 on return.
; Uses plain named labels rather than the file's usual @/<@/>@ anonymous
; locals -- those only resolve to the single nearest previous/next @:,
; which isn't enough for this routine's three-way dispatch.
read_line:
        ldx #0                   ; buffer index
        stx linelen
        stx cursor_pos
        lda #1
        sta sid_background       ; background context -- diagnostics stay
                                  ; quiet here, see sid_service_background
read_line_loop:
        ; .a = ?
        ; .x = index into linebuf (also stored in linelen)
        ; .y = length of input

;       stx x_save
        sty y_save
        jsr update_cursor        ; blink the cursor while waiting for a key
        jsr sid_service_background ; keep draining an in-progress SID stream
                                    ; while the player types -- see its own
                                    ; comment
        jsr GETIN                ; get char from keyboard buffer, 0 = none waiting
        cmp #0
        beq read_line_loop       ; nothing typed yet, keep polling

        ; CHROUT does not reliably preserve X in this environment (it was
        ; empirically observed leaving X at a fixed small value on
        ; return, despite common KERNAL folklore that it preserves
        ; registers) -- every CHROUT call below that happens after X has
        ; a meaningful value must save/restore X around it via x_save,
        ; or the buffer index silently corrupts and every character
        ; after the first overwrites the same slot. This was the actual
        ; cause of read_line always ending up with a 1-character buffer
        ; regardless of how much was typed, confirmed via a raw GETIN
        ; byte trace showing every keystroke WAS being read correctly.
        pha                      ; stash the typed char while tidying the cursor
        jsr cursor_hide          ; erase any visible cursor block first
        pla

        ; TEMP diagnostic: print every raw byte GETIN returns as <XX>,
        ; and the current buffer length as [XX], right before dispatch.
{ifdef: debug}
        pha
        lda #'<'
        jsr term_chrout
        pla
        pha
        jsr print_hex_byte
        lda #'>'
        jsr term_chrout
        lda #'['
        jsr term_chrout
        lda linelen
        jsr print_hex_byte
        lda #']'
        jsr term_chrout
        pla
{endif}

        ; beq straight to read_line_done from here is out of branch range
        ; (read_line_done sits well past +127 bytes down, after all the
        ; insert/cursor-move routines added since) -- same out-of-range
        ; gotcha as read_line_left/right above. c64list assembles it
        ; clean with no warning but it computes a garbage jump target at
        ; runtime: dispatch fell through to the default "store as a
        ; typed character" case, which happened to still echo a visible
        ; CR via CHROUT -- looking like RETURN worked -- while actually
        ; looping forever waiting for more keys, so read_line never
        ; returned and send_line never ran. Invert the test and reach
        ; read_line_done via jmp instead.
        cmp #$0d                 ; RETURN?
        bne read_line_not_return
        jmp read_line_done
read_line_not_return:

        cmp #$14                 ; DEL (PETSCII backspace)?
        beq read_line_del
        cmp #$94                 ; INST (shift+DEL) -- insert a blank at cursor?
        beq read_line_inst
        cmp #$9d                 ; CRSR LEFT (shift+CRSR key)?
        beq read_line_left
        cmp #$1d                 ; CRSR RIGHT (unshifted CRSR key)?
        beq read_line_right
        jmp read_line_store

read_line_del:
        lda cursor_pos            ; nothing to the left of the cursor?
        beq read_line_loop
        ldx cursor_pos             ; shift linebuf[cursor_pos..linelen-1] left
        ; by one, closing the gap left by the deleted char at cursor_pos-1
read_line_del_shift:
        cpx linelen
        bcs read_line_del_shift_done
        lda linebuf,x
        sta linebuf-1,x
        inx
        jmp read_line_del_shift
read_line_del_shift_done:
        dec linelen
        dec cursor_pos
        jsr term_cursor_left     ; step the screen cursor back onto the
                                  ; now-deleted column
        lda #1                   ; redraw the tail plus one trailing blank
        jsr redraw_tail          ; to erase the old last character on screen
        jmp read_line_loop

read_line_inst:
        lda linelen
        cmp #MAX_LINE-1
        bcs read_line_loop       ; buffer full, ignore
        ldx linelen               ; shift linebuf[cursor_pos..linelen-1] right
        ; by one (from the top down) to open a gap at cursor_pos
read_line_inst_shift:
        cpx cursor_pos
        beq read_line_inst_shift_done
        lda linebuf-1,x
        sta linebuf,x
        dex
        jmp read_line_inst_shift
read_line_inst_shift_done:
        lda #$20                 ; blank goes in the newly-opened gap
        ldx cursor_pos
        sta linebuf,x
        inc linelen
        lda #0                   ; no extra trailing blank needed -- the
        jsr redraw_tail          ; buffer grew, nothing stale beyond it
        jmp read_line_loop

read_line_left:
        ; beq/bcs straight to read_line_loop from here is out of branch
        ; range (confirmed via the .sym addresses: ~132-148 bytes, over
        ; the 6502's +/-127 signed-branch limit) -- c64list assembles an
        ; out-of-range branch clean with no warning but it jumps to
        ; garbage at runtime (see this repo's own known gotcha on this).
        ; Invert the test and reach read_line_loop via jmp instead.
        lda cursor_pos
        bne read_line_left_move  ; not at start of line
        jmp read_line_loop
read_line_left_move:
        dec cursor_pos
        jsr term_cursor_left
        jmp read_line_loop

read_line_right:
        lda cursor_pos            ; same out-of-range concern as
        cmp linelen               ; read_line_left above
        bcc read_line_right_move ; not at end of line
        jmp read_line_loop
read_line_right_move:
        inc cursor_pos
        jsr term_cursor_right
        jmp read_line_loop

read_line_store:
        pha                       ; stash the typed char across the shift below
        lda linelen
        cmp #MAX_LINE-1
        bcc read_line_store_room
        pla
        jmp read_line_loop       ; buffer full, ignore further chars
read_line_store_room:
        ldx linelen               ; shift linebuf[cursor_pos..linelen-1] right
        ; by one (from the top down) to open a gap at cursor_pos -- same
        ; shift as read_line_inst, but the gap gets the typed char instead
        ; of a blank. When cursor_pos == linelen (the common case: typing
        ; at the end of the line) this loop does nothing, so append is
        ; just the cursor-at-end special case of insert.
read_line_store_shift:
        cpx cursor_pos
        beq read_line_store_shift_done
        lda linebuf-1,x
        sta linebuf,x
        dex
        jmp read_line_store_shift
read_line_store_shift_done:
        pla                       ; recover the typed char
        ldx cursor_pos
        sta linebuf,x             ; 0-based: store first, then advance --
        inc linelen               ; matches send_line, which still starts
        inc cursor_pos            ; at index 0 and reads until the null
        jsr term_chrout           ; echo the typed char locally -- through
                                   ; term_chrout, not a bare CHROUT, so a
                                   ; long line wrapping near the bottom of
                                   ; the screen can't scroll past STATUS_ROW

        ; Echoing a literal '"' through CHROUT toggles the KERNAL's quote
        ; mode (same as typing one in a normal BASIC line) -- once on, it
        ; makes subsequent CHROUT control codes (our cursor blink's
        ; reverse-on/off/cursor-left) display as literal reverse-video
        ; glyphs instead of being interpreted, showing up as garbage
        ; around the blinking cursor. Force it back off unconditionally
        ; after every echoed character rather than only after a '"'.
        lda #0
        sta QTSW

        lda linelen               ; was this an insert (tail follows the
        cmp cursor_pos            ; cursor) rather than a plain append?
        beq read_line_store_done
        lda #0
        jsr redraw_tail          ; reprint the shifted tail, reposition cursor
read_line_store_done:
        jmp read_line_loop

; --- Reprint linebuf[cursor_pos..linelen-1] and reposition the screen
; cursor back onto cursor_pos ---
; Used whenever a mid-line insert/delete shifts the tail of the buffer,
; so the screen catches up with the new buffer contents. Input: .A =
; number of extra trailing blanks to print after the real tail (0, or 1
; to erase the stale last character left behind by a delete). Only ever
; called with 0 or 1, so a single conditional print suffices instead of
; a loop.
; Uses redraw_idx/redraw_count (plain memory, not X/Y) as loop counters
; since CHROUT is called from inside these loops and does not reliably
; preserve registers here -- see read_line_loop's own comment on this.
redraw_tail:
        sta redraw_extra
        lda cursor_pos
        sta redraw_idx
redraw_print_loop:
        lda redraw_idx
        cmp linelen
        bcs redraw_print_done
        tax
        lda linebuf,x
        jsr term_chrout
        inc redraw_idx
        jmp redraw_print_loop
redraw_print_done:
        lda redraw_extra
        beq redraw_back_setup
        lda #$20
        jsr term_chrout
redraw_back_setup:
        lda linelen               ; total columns to step back = tail length
        sec                       ; printed (linelen - cursor_pos) plus the
        sbc cursor_pos            ; extra trailing blank, if any
        clc
        adc redraw_extra
        sta redraw_count
redraw_back_loop:
        lda redraw_count
        beq redraw_done
        dec redraw_count
        jsr term_cursor_left
        jmp redraw_back_loop
redraw_done:
        rts

read_line_done:
        ldx linelen
        lda #0
        sta linebuf,x            ; null-terminate right at the real length
        lda #$0d
        jsr term_chrout          ; echo the newline locally
        ; TEMP diagnostic: show how many characters read_line actually
        ; captured. Remove once the character-loss bug is confirmed fixed.
{ifdef: debug}
        lda #'['
        jsr term_chrout
        lda #'L'
        jsr term_chrout
        lda linelen             ; was x_save
        jsr print_hex_byte
        lda #']'
        jsr term_chrout
        lda #$0d
        jsr term_chrout
{endif}
        rts

; --- TEMP diagnostic: print .A as two hex digits ---
{ifdef: debug}
hex_digits:
        ascii "0123456789ABCDEF"

print_hex_nibble:                ; .A = nibble (0-15)
        tax
        lda hex_digits,x
        jsr term_chrout
        rts

print_hex_byte:                  ; .A = byte to print in hex
        pha
        lsr
        lsr
        lsr
        lsr
        jsr print_hex_nibble
        pla
        and #$0f
        jsr print_hex_nibble
        rts
{endif}

; --- Send linebuf over SwiftLink, CR-terminated ---
; Server reads with readuntil(b'\r') (network_context.py) -- a bare CR,
; not CRLF, so only $0d goes out after the line, matching the negotiation
; response above ("lda #'4'" / "lda #$0d").
send_line:
        ldx #0
send_line_loop:
        lda linebuf,x
        beq send_line_term       ; hit the null terminator
        jsr sl_send
        inx
        jmp send_line_loop
send_line_term:
        lda #$0d
        jsr sl_send
        rts

; --- Display character on screen ---
; Input: .A = byte received from server
; Writes directly to screen RAM via pointer, handles CR
; Routes through term_chrout, not a bare CHROUT, so incoming server text
; can't scroll past STATUS_ROW -- see that section's own header comment.
;
; Resets QTSW (KERNAL quote-mode switch) after every character, same
; reasoning as read_line_store/reprint_input_line/service_async_idle's
; own QTSW resets (a literal '"' toggles quote mode, which makes
; subsequent CHROUT control codes print as literal reverse-video glyphs
; instead of being interpreted) -- but this is the one call site that
; was missing it: those three all reset QTSW when RE-displaying already-
; buffered content, but nothing reset it for incoming server text's
; *original* display pass. Confirmed live 2026-08-20 this was a real,
; not just theoretical, gap: ordinary server text (chat messages
; routinely contain literal quotes) could leave quote mode stuck on
; indefinitely, silently breaking every control code sent afterward --
; including async_step_back's own $9d CRSR-LEFT stepping, which stopped
; actually moving the cursor and instead printed $9d's literal glyph
; forward, corrupting STATUS_ROW with garbage in a way that looked like
; a completely different bug (a stray character landing there) until
; traced back to this.
display_char:
        cmp #$0d                ; carriage return?
        bne >@
        lda #$0d
        jsr term_chrout
        jmp display_char_qtsw_reset
@:      jsr term_chrout          ; let KERNAL handle PETSCII->screen code
                                  ; conversion (term_chrout wraps CHROUT)
display_char_qtsw_reset:
        pha
        lda #0
        sta QTSW
        pla
        rts

; --- Dispatch a byte received from the server: text or SID stream ---
; Called from wait_for_data for every byte sl_recv hands back, in place of
; the old unconditional display_char call. sid_mode is a 5-state machine:
;   0 = text (scan for SID_STREAM_START)
;   4 = saw SID_STREAM_START, awaiting SID_STREAM_CONFIRM (see that
;       const's own comment -- a lone start byte isn't trusted alone)
;   1 = reading the 16-bit body-length prefix, low byte
;   2 = reading the 16-bit body-length prefix, high byte
;   3 = storing frame bytes into SID_BUF, counting sid_remaining down
; States 1-3 replace what used to be a single in-band SID_STREAM_END
; ($02) marker. That was ambiguous: a SID register *value* is an
; arbitrary 0-255 byte, so real tune data eventually contains a literal
; $02 and gets mistaken for end-of-stream partway through (confirmed
; live: sid_engine's canned stub arpeggio happened to dodge this by
; luck -- no note in it produced a literal $02 anywhere -- but a real
; .sid-derived tune did not). Counting down a length the server sent up
; front has no such ambiguity. See sid_engine/frames.py's module
; docstring for the matching server-side encoder.
; cpy #1/#2's targets (handle_recv_byte_len_lo/_len_hi) sit ~210-220
; bytes below this dispatcher -- well past a 6502 branch's +/-127 byte
; range. c64list doesn't validate branch range and assembles an
; out-of-range beq/bne clean anyway (confirmed live 2026-08-18: it
; produced offset $FF, so the "branch" landed one byte into its own
; operand and ran off into garbage, eventually stray-writing into
; $0314 and JAMing at $ff09 -- a known c64list gotcha, not a bug in
; the branch logic itself).
; bne-over-jmp keeps the same dispatch logic with an unconditional jmp,
; which has no range limit.
handle_recv_byte:
        ldy sid_mode
        beq handle_recv_byte_text
        ; sid_mode != 0 -- a byte just advanced the SID receive state
        ; machine, so this stream is still genuinely alive. Restamp the
        ; idle clock sid_service_background_recv checks, so a truncated/
        ; dropped stream (no further bytes ever) times out from its own
        ; last real progress rather than from whenever reception happened
        ; to start. .a holds the just-received byte, still needed by every
        ; branch below (len_lo/len_hi/store/confirm all read it) -- pha/pla
        ; around the $a2 read/store so this is transparent to them.
        pha
        lda $a2
        sta sid_recv_last_jiffy
        pla
        cpy #1
        bne handle_recv_byte_not_len_lo
        jmp handle_recv_byte_len_lo
handle_recv_byte_not_len_lo:
        cpy #2
        bne handle_recv_byte_not_len_hi
        jmp handle_recv_byte_len_hi
handle_recv_byte_not_len_hi:
        cpy #4
        beq handle_recv_byte_confirm
        jmp handle_recv_byte_store        ; sid_mode == 3

handle_recv_byte_text:
        cmp #SID_STREAM_START
        beq handle_recv_byte_maybe_start
        cmp #SID_STOP
        beq handle_recv_byte_stop
        jsr capture_line_byte
        jmp display_char

handle_recv_byte_stop:
        jsr status_push_reset        ; fresh status-row batch -- see each
        jsr status_print_frames_played ; routine's own comment
        jsr status_print_elapsed
        jsr status_print_pointers
        jsr status_print_stream_starts
        jmp sid_stop                 ; silence + reset -- see sid_stop's own
                                      ; comment (shared with init_sid at boot)

; A lone SID_STREAM_START byte isn't trusted on its own anymore -- see
; SID_STREAM_CONFIRM's own comment (near the {const:} block) for why.
; sid_mode 4 = "saw the first byte, waiting to see if the very next byte
; confirms it's a real stream" -- confirmed live to matter: unsolicited
; game text (ally/room/ambient messages, independent of anything the
; player typed) can arrive interleaved with a play response, and a
; single stray $01 byte in ordinary text was observed mistaking later
; ordinary text for bogus SID register data.
handle_recv_byte_maybe_start:
        lda #4
        sta sid_mode
        lda $a2
        sta sid_recv_last_jiffy   ; starts the idle clock for this mode-4
                                   ; wait too -- see sid_recv_last_jiffy's
                                   ; own comment
        rts

handle_recv_byte_confirm:
        cmp #SID_STREAM_CONFIRM
        beq handle_recv_byte_start
        cmp #CANVAS_STREAM_CONFIRM
        beq handle_recv_byte_canvas_confirm
        cmp #DISPLAY_STREAM_CONFIRM
        beq handle_recv_byte_display_confirm
        cmp #APPLY_STREAM_CONFIRM
        beq handle_recv_byte_apply_confirm
        ; False alarm: the earlier $01 wasn't really a stream start.
        ; Display both the swallowed $01 and this byte as ordinary text
        ; instead of silently treating either as SID framing.
        lda #0
        sta sid_mode
        pha
        lda #SID_STREAM_START
        jsr display_char
        pla
        jmp display_char

; A real canvas stream is confirmed -- hand off to the petscii_editor
; overlay module entirely rather than reusing the SID mode-1/2/3 states
; (sid_mode goes back to 0 first: we're diverting control away from this
; dispatcher altogether, not starting a SID-shaped receive here). The
; module reads the length prefix and 2000-byte body itself once it's
; loaded and running -- see load_petscii_editor's own comment for why
; nothing arriving in the meantime is lost.
handle_recv_byte_canvas_confirm:
        lda #0
        sta sid_mode
        jmp load_petscii_editor

; A real display-settings stream is confirmed -- same reasoning as
; handle_recv_byte_canvas_confirm just above, hands off to config_menu.asm
; entirely. That module reads the length prefix + 3-byte body itself once
; it's loaded and running.
handle_recv_byte_display_confirm:
        lda #0
        sta sid_mode
        jmp load_config_menu

; A silent-apply stream is confirmed (sent at login/reconnect -- see
; commands/connect.py's encode_apply_for_player()). Unlike the canvas/
; display-popup confirms above, this doesn't hand off to an overlay
; module at all -- it consumes its own length prefix (discarded, always
; 3) + 3-byte body (border, bg, blink) right here inline, applies them
; directly (VIC-II POKEs + cursor_blink_mask), then rts's straight back
; into the ordinary receive flow. Blocking on sl_recv like this is safe
; and already-proven (petscii_editor.asm/config_menu.asm do the same for
; their own short payloads) -- nmi_handler keeps draining SwiftLink into
; rx_buf regardless of what mainline is doing, so nothing arriving
; during the short wait is lost.
;
; Each of the 5 byte-waits below goes through apply_recv_byte rather than
; a bare sl_recv/bcc spin, so a misfired confirm (this handler entered
; when nobody actually sent an apply stream -- the exact 2026-08-17
; incident that motivated moving all the confirm bytes out of printable-
; letter range, see APPLY_STREAM_CONFIRM's own comment) times out into
; garbled text instead of hanging the client forever with no way back to
; the prompt.
handle_recv_byte_apply_confirm:
        lda #0
        sta sid_mode
apply_recv_len_lo:
        jsr apply_recv_byte
        bcc handle_recv_byte_apply_timeout
apply_recv_len_hi:
        jsr apply_recv_byte
        bcc handle_recv_byte_apply_timeout
apply_recv_border:
        jsr apply_recv_byte
        bcc handle_recv_byte_apply_timeout
        sta VIC_BORDER
apply_recv_bg:
        jsr apply_recv_byte
        bcc handle_recv_byte_apply_timeout
        sta VIC_BACKGROUND
apply_recv_blink:
        jsr apply_recv_byte
        bcc handle_recv_byte_apply_timeout
        tax
        lda apply_blink_masks-1,x  ; .x is 1-5 -- -1 makes it a plain
                                     ; 0-based index, same convention as
                                     ; config_menu.asm's own blink_masks
        sta cursor_blink_mask
        rts

; Gives up on a timed-out apply-confirm byte wait: sid_mode is already 0
; (set at handle_recv_byte_apply_confirm's own entry), so this just
; drops straight back into ordinary text scanning. Whatever bytes were
; actually in flight get displayed as garbled text -- not ideal, but
; recoverable, unlike a permanent hang.
handle_recv_byte_apply_timeout:
        rts

; Polls sl_recv for one byte, giving up after APPLY_RECV_TIMEOUT_JIFFIES
; jiffies (~1 second) rather than spinning forever. Returns with carry
; set and the byte in .a on success, carry clear on timeout. $a2 is the
; KERNAL jiffy clock's fastest-changing byte (see sid_jiffy_start2's own
; comment) -- the stock KERNAL IRQ keeps incrementing it regardless of
; what mainline is doing, so this doesn't depend on anything SID-related
; still running.
apply_recv_byte:
        lda $a2
        sta apply_recv_timeout_start
apply_recv_byte_poll:
        jsr sl_recv
        bcs apply_recv_byte_rts
        lda $a2
        sec
        sbc apply_recv_timeout_start
        cmp #APPLY_RECV_TIMEOUT_JIFFIES
        bcc apply_recv_byte_poll
        clc
apply_recv_byte_rts:
        rts

; Resident copy of config_menu.asm's own blink_masks table -- can't share
; it directly (overlay modules and resident code don't share plain data
; labels, only jump-table routines -- see JT_SET_BLINK_MASK's own
; comment). Must be kept in sync with that table and commands/
; c64_display.py's BLINK_SPEED_MASKS by hand.
apply_blink_masks:
        byte $08, $10, $20, $40, $00

apply_recv_timeout_start:
        byte 0                   ; apply_recv_byte's own jiffy-clock ($a2)
                                  ; snapshot, taken fresh each call

; sid_active is already 1 throughout a multi-chunk transfer (frames.py's
; encode_stream() can split one tune into several back-to-back STREAM_
; START+CONFIRM chunks -- see its own comment), only cleared by sid_stop,
; so it's already 0 exactly when this is a genuinely fresh play command
; and already 1 exactly when this is a later chunk of a transfer already
; in progress. That distinction matters: SID_BUF is small and playback
; always lags reception, so a still-active transfer's sid_rd/sid_wr
; almost always have unplayed backlog sitting between them (rd < wr)
; the instant a new chunk's header arrives. Resetting both to 0
; unconditionally on every chunk -- what this used to do -- silently
; discarded that backlog and restarted the ring buffer from scratch,
; audible as a dropped/skipped beat at every chunk boundary; confirmed
; live 2026-08-19 (a diagnostic dump mid-transfer showed rd=$45 wr=$d2,
; i.e. 141 real unplayed bytes, moments before the next chunk's start
; would have wiped them). Same reasoning for sid_frames_played/
; sid_byte_count/the jiffy-clock snapshot: resetting those every chunk
; made #stop's diagnostics only ever reflect the most recent chunk
; instead of the whole tune. None of that applies to sid_rd/sid_wr in
; the ordinary path handle_recv_byte_stop is also used for -- because
; that stop is only ever entered from *text* mode, sid_active would
; already be 0 by the time it re-triggers via a genuinely new play.
handle_recv_byte_start:
        inc sid_stream_starts     ; TEMP diagnostic -- see its own comment
        lda sid_active
        bne handle_recv_byte_start_mode
        lda #0
        sta sid_rd
        sta sid_wr
        sta sid_byte_count+0
        sta sid_byte_count+1
        sta sid_frames_played+0
        sta sid_frames_played+1
        ; Snapshot the KERNAL jiffy clock ($a0/$a1/$a2, hi/mid/lo -- $a2
        ; is the fastest-changing byte, same one update_cursor already
        ; reads) so #stop can print real elapsed time alongside
        ; sid_frames_played, no stopwatch needed.
        lda $a0
        sta sid_jiffy_start0
        lda $a1
        sta sid_jiffy_start1
        lda $a2
        sta sid_jiffy_start2
handle_recv_byte_start_mode:
        lda #1
        sta sid_mode
        sta sid_active
        rts

handle_recv_byte_len_lo:
        sta sid_remaining_lo
        lda #2
        sta sid_mode
        rts

handle_recv_byte_len_hi:
        sta sid_remaining_hi
        lda #3
        sta sid_mode
        rts

handle_recv_byte_store:
        ; Wait for room before storing -- SID_BUF has no flow control of
        ; its own (unlike rx_buf's RTS-based backpressure), and bytes can
        ; arrive off the wire far faster than sid_play (throttled to one
        ; frame per IRQ tick, i.e. the tune's real playback rate) drains
        ; them: a real tune's burst can fill this 256-byte buffer in
        ; well under 100ms while still taking the better part of a
        ; second to finish arriving. Without this wait, the producer
        ; (this routine) laps the consumer (sid_play) and overwrites
        ; frame data before it's ever read -- confirmed live: a real
        ; tune's first frame (and most of what follows) got clobbered by
        ; later frames wrapping around, audible as "plays a moment, then
        ; stuck." "Full" is defined as sid_wr+1 == sid_rd (one slot
        ; always left empty, so full and empty stay distinguishable via
        ; wr==rd alone). Spinning here is safe: interrupts stay enabled,
        ; so sid_play keeps draining and sid_rd keeps advancing while we
        ; wait -- same pattern sl_send already uses spinning on TDRE.
        ; This also means mainline stops draining rx_buf for the
        ; duration of the wait, so backpressure cascades naturally into
        ; rx_buf's own existing RTS-deassert flow control if the stall
        ; runs long enough -- genuine end-to-end pressure, not just
        ; local buffer swapping, matching nmi_handler's own philosophy.
        pha
sid_buf_wait_room:
        lda sid_wr
        clc
        adc #1
        cmp sid_rd
        beq sid_buf_wait_room
        pla
        ldx sid_wr
        sta SID_BUF,x
        inc sid_wr                ; wraps at 256, matching rx_buf's ring buffer
        inc sid_byte_count+0
        bne handle_recv_byte_count_done
        inc sid_byte_count+1
handle_recv_byte_count_done:
        ; standard 16-bit decrement-with-borrow: sid_remaining -= 1
        lda sid_remaining_lo
        bne handle_recv_byte_dec_lo
        dec sid_remaining_hi
handle_recv_byte_dec_lo:
        dec sid_remaining_lo
        lda sid_remaining_lo
        ora sid_remaining_hi
        bne handle_recv_byte_store_done   ; still bytes left, stay in mode 3
        lda #0
        sta sid_mode                      ; countdown hit zero -- back to text mode
        lda sid_background        ; skip the diagnostics if this transfer's
        bne handle_recv_byte_store_done   ; tail landed while backgrounded
                                   ; -- kept out of caution, though the
                                   ; original reason no longer strictly
                                   ; applies now that these build into the
                                   ; status queue (redraw_status_row is
                                   ; pure raw SCREEN_RAM pokes to
                                   ; STATUS_ROW, never touches CHROUT/the
                                   ; input line the way the old CHROUT-
                                   ; based sid_print_* did)
        jsr status_push_reset      ; fresh status-row batch
        jsr status_print_byte_count
        jsr status_print_pointers ; rd/wr right *now*, before any further
                                   ; idle time, to tell whether SID_BUF is
                                   ; already wrapped by the time reception
                                   ; itself finishes
        jsr status_print_bufdump
handle_recv_byte_store_done:
        rts


; --- IRQ dispatcher init ---
; Hooks $0314/$0315 the same way init_nmi hooks $0318/$0319: save the
; current vector, install our handler, cli. Unlike NMI, the hardware IRQ
; vector already runs through the KERNAL's entry stub first ($FF48), which
; pushes A/X/Y before jumping to $0314 -- so irq_handler doesn't need to
; save/restore registers itself, and chaining to irq_orig at the end (the
; stock KERNAL IRQ, still doing keyboard scan / jiffy clock) performs the
; final pla/tax/pla/tay/pla/rti.
init_irq:
        sei
        lda $0314
        sta irq_orig+0
        lda $0315
        sta irq_orig+1
        lda #<irq_handler
        sta $0314
        lda #>irq_handler
        sta $0315
        cli
        rts

; --- IRQ handler ---
; Two tiers, matching ImageBBS's irqhn.asm shape (irq9/irq10 unconditional
; + irqtbl/irq0 round-robin), repurposed for this client's own jobs:
;   1. sid_play runs every single tick, unconditionally -- playback tempo
;      must never depend on how many other jobs are registered.
;   2. irq_dispatch_next services one round-robin job per tick, for
;      latency-tolerant background work (currently just a placeholder
;      heartbeat; future candidates: a SwiftLink TX queue pump, since
;      sl_send today busy-waits on TDRE rather than being interrupt-driven).
irq_handler:
        jsr sid_play
        jsr irq_dispatch_next
        jmp (irq_orig)

; --- Round-robin task dispatcher ---
; Advances a self-modified table index by 2 (one word entry) each tick,
; wrapping at IRQ_TASK_TABLE_LEN, and jumps into the selected job via a
; self-modified indirect target. The job ends with rts, which returns to
; whoever called irq_dispatch_next (irq_handler) -- not to code inside
; this routine -- since irq_dispatch_jmp is a jmp, not a jsr, exactly like
; irqhn.asm's irq0/irqjmp.
irq_dispatch_next:
        ldy irq_task_ptr
        lda irq_task_table,y
        sta irq_dispatch_jmp+1
        iny
        lda irq_task_table,y
        sta irq_dispatch_jmp+2
        iny
        cpy #IRQ_TASK_TABLE_LEN
        bcc irq_dispatch_next_store
        ldy #0
irq_dispatch_next_store:
        sty irq_task_ptr
irq_dispatch_jmp:
        jmp $ffff

; Placeholder round-robin job -- proves the dispatch mechanism works.
; Replace/extend irq_task_table as real jobs (SwiftLink TX pump, etc.)
; show up; bump IRQ_TASK_TABLE_LEN to match (byte length = entries * 2).
irq_task_heartbeat:
        inc irq_heartbeat
        rts

; --- Data ---

; {alpha:poke} -- update_status_line pokes this straight into SCREEN_RAM,
; not through CHROUT, so it needs to already be screen codes at assembly
; time (same reasoning as petscii_editor.asm's LOAD_LABEL/SAVE_LABEL/
; help_line1-6). Null-terminated, not fixed-width: c64list's area/align
; can't take a *-derived length as a size argument (confirmed -- not
; just a syntax issue, see update_status_line's own comment), so there's
; no compile-time way to pad this to exactly 40 bytes here; padding
; happens at runtime in update_status_line instead. Reset to
; {alpha:normal} right after so this doesn't leak into anything below
; that uses plain `ascii` (hex_digits, sid_hex_digits, etc).
{alpha:pokealt}
status_msg:
        ascii " TADA client "
        ascii {usedef:__BuildDate}
        ascii " - Connecting..."
        byte 0
{alpha:normal}

linelen:
        byte 0
cursor_pos:
        byte 0                   ; index into linebuf where the next inserted/typed
                                  ; char goes; 0 <= cursor_pos <= linelen. Distinct
                                  ; from linelen so CRSR LEFT/RIGHT can park it
                                  ; mid-buffer for INST/DEL/typed-char insertion.
redraw_extra:
        byte 0                   ; scratch for redraw_tail -- see its own comment
redraw_idx:
        byte 0
redraw_count:
        byte 0
linebuf:
        area 80,$00

nmi_orig:
        byte 0,0                ; saved KERNAL NMI vector, set by init_nmi

irq_orig:
        byte 0,0                ; saved KERNAL IRQ vector, set by init_irq

irq_task_ptr:
        byte 0                   ; byte offset into irq_task_table, self-modified

irq_heartbeat:
        byte 0                   ; placeholder round-robin job's counter

; Not zero page -- see the comment above rx_head/rx_tail's definitions
; for why. Same roles as before the move: sid_wr/sid_rd index SID_BUF
; (mainline-owned write index / IRQ-owned read index), sid_mode drives
; handle_recv_byte's state machine, sid_active gates sid_play,
; sid_remaining_lo/hi is the mode-3 byte countdown.
sid_wr:
        byte 0
sid_rd:
        byte 0
sid_mode:
        byte 0
sid_active:
        byte 0
sid_remaining_lo:
        byte 0
sid_remaining_hi:
        byte 0

sid_background:
        byte 0                   ; 0 = foreground (wait_for_data) context,
                                  ; 1 = background (read_line) context --
                                  ; gates the TEMP diagnostic prints, see
                                  ; handle_recv_byte_store

prompt_relocate_enabled:
        byte 0                   ; 0 until the SwiftLink negotiation
                                  ; exchange finishes -- see start:'s own
                                  ; comment for why that first wait_for_
                                  ; data call must not run relocate_
                                  ; prompt_to_row24

sid_recv_last_jiffy:
        byte 0                   ; $a2 snapshot taken every time a byte
                                  ; actually advances the sid_mode 1-4
                                  ; receive state machine -- see
                                  ; handle_recv_byte's and
                                  ; handle_recv_byte_maybe_start's own
                                  ; comments, checked against
                                  ; SID_RECV_TIMEOUT_JIFFIES by
                                  ; sid_service_background_recv

sid_byte_count:
        byte 0,0                 ; lo,hi -- bytes redirected into SID_BUF this
                                  ; stream, reset on SID_STREAM_START, printed
                                  ; by status_print_byte_count once the mode-3
                                  ; countdown (sid_remaining_lo/hi) hits zero

sid_dump_idx:
        byte 0                   ; status_print_bufdump's loop counter

sid_frames_played:
        byte 0,0                 ; lo,hi -- frames sid_play has applied
                                  ; since the current stream started

sid_jiffy_start0:
        byte 0                   ; $a0 (hi) snapshot at stream start
sid_jiffy_start1:
        byte 0                   ; $a1 (mid) snapshot at stream start
sid_jiffy_start2:
        byte 0                   ; $a2 (lo, fastest-changing) snapshot

sid_jiffy_elapsed0:
        byte 0                   ; hi/mid/lo of (now - start), computed
sid_jiffy_elapsed1:                ; by status_print_elapsed
        byte 0
sid_jiffy_elapsed2:
        byte 0

sid_stream_starts:
        byte 0                   ; count of handle_recv_byte_start firings
                                  ; since the last #stop (or boot)

irq_task_table:
        word irq_task_heartbeat
IRQ_TASK_TABLE_LEN = 2          ; entries * 2 -- keep in sync with the table above

align $100      ; align buffers on page boundaries -- c64list wants "$" for
                ; hex, not "0x" (confirmed against the manual and by
                ; testing: "0x100" fails with "Unresolved argument")

; 256-byte NMI receive ring buffer -- deliberately sized so rx_head/
; rx_tail (plain bytes) wrap around for free on overflow, no masking
; needed.
rx_buf:
        area 256, 0

; 256-byte SID-stream receive ring buffer -- same wrap-for-free sizing as
; rx_buf, but the roles are reversed: mainline (handle_recv_byte) is the
; producer here, sid_play (IRQ context) is the consumer.
SID_BUF:
        area 256, 0

; save_screen/restore_screen's whole-physical-screen backup (see their
; own comments, near init_jump_table) -- shared by every popup-window
; overlay module via JT_SAVE_SCREEN/JT_RESTORE_SCREEN, so only one
; resident copy of these 2000 bytes exists rather than each module
; (petscii_editor.asm's help screen, a future config menu, ...)
; allocating its own.
BACKUP_CHARS:
        area 1000, 0

BACKUP_COLORS:
        area 1000, 0
