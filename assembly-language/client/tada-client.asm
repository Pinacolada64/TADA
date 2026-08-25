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

; SwiftLink ACIA registers
{const: SL_DATA     $de00}      ; data register
{const: SL_STATUS   $de01}      ; status register
{const: SL_COMMAND  $de02}      ; command register
{const: SL_CONTROL  $de03}      ; control register

; ACIA status bits
{const: SL_RDRF     $08}        ; bit 3: receive data register full
{const: SL_TDRE     $10}        ; bit 4: transmit data register empty

; ACIA command register values
{const: SL_CMD_INIT    $09}     ; DTR low, RTS low, RxD IRQ on
{const: SL_CMD_OFF     $0b}     ; RxD/TxD IRQs off, DTR low
{const: SL_CMD_RTS_OFF $01}     ; DTR low, RTS *high* (deasserted) -- see
                                 ; nmi_handler's flow-control comment: this
                                 ; is what makes VICE's ACIA core disable
                                 ; its RX alarm and genuinely stop draining
                                 ; the TCP socket, per aciacore.c.

; ACIA control register: 8-bit, 1 stop, internal clock, baud rate in the
; low nibble. SwiftLink's crystal (not the stock C64 clock) makes these
; nibble values map differently than a plain 6551 datasheet's own table
; -- $0e=19200, $0f=38400 here, per Craig Bruce's swiftlib.s slNormBauds
; table (https://csbruce.com/cbm/swiftlib/swiftlib.s, already the
; reference for this cartridge elsewhere in this file -- see init_nmi).
; 38400 is the fastest a *plain* SwiftLink (this cartridge, not the
; Turbo232 variant) supports without needing its external clock generator
; register (slRegClock), which values >= $10 require and a plain
; SwiftLink doesn't have.
{const: SL_CTRL_38K $1f}

; SID chip base address (25 registers, $D400-$D418)
{const: SID_BASE $d400}

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
{const: SID_FRAME_END    $ff}   ; terminates one tick's (reg,val) pairs --
                                 ; safe as a sentinel since SID only has
                                 ; registers 0-24

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

        ; wait for server to send negotiation menu, display it
        jsr wait_for_data

        ; respond: 40 columns (C64)
        lda #'4'
        jsr sl_send
        lda #$0d                ; CR
        jsr sl_send

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
        rts                       ; the prompt read_line will redraw around
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
        lda #CHARSET_UPPER_LOWER
        sta VIC_MEMORY_CONTROL
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
        ; set screen pointer to row 2 col 0
        lda #<(SCREEN_RAM + 80)
        sta scr_ptr_lo
        lda #>(SCREEN_RAM + 80)
        sta scr_ptr_hi
        rts

; --- set_screen_line: scr_ptr_lo/hi = SCREEN_RAM + row*40 ---
; Input: .a = row number (0-24). Reuses scr_ptr_lo/hi -- this file's own
; zero-page pointer for indirect screen access (see calc_screen_ptr-style
; usage in petscii_editor.asm for the same convention: whichever routine
; needs an indirect pointer right now temporarily owns scr_ptr_lo/hi,
; rather than every routine claiming its own zero-page pair).
set_screen_line:
        asl                       ; row*2 -- row_offsets is a word table
        tax
        lda row_offsets,x
        clc
        adc #<SCREEN_RAM
        sta scr_ptr_lo
        lda row_offsets+1,x
        adc #>SCREEN_RAM
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

; --- Init SwiftLink ---
; Reset ACIA and configure for 38400 baud 8N1
init_swiftlink:
        lda #SL_CMD_OFF         ; disable interrupts
        sta SL_COMMAND
        lda #SL_CTRL_38K        ; 38400 baud, 8N1, internal clock
        sta SL_CONTROL
        lda #SL_CMD_INIT        ; DTR low, RTS low, RxD IRQ on
        sta SL_COMMAND
        rts

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

save_screen:
        lda #<SCREEN_RAM
        sta copy_src_lo
        lda #>SCREEN_RAM
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
        lda #<SCREEN_RAM
        sta copy_dst_lo
        lda #>SCREEN_RAM
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
; rows 0-21, screen + color) -- see its own comment.
DIALOGUE_SHIFT_BYTES = 880
copy_dialogue_block:
        lda #<DIALOGUE_SHIFT_BYTES
        sta copy_remaining_lo
        lda #>DIALOGUE_SHIFT_BYTES
        sta copy_remaining_hi
        jmp copy_block

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
ROW_BYTES            = 40
STATUS_ROW_OFFSET    = 920      ; STATUS_ROW * ROW_BYTES

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
term_chrout:
        stx term_saved_x
        sty term_saved_y
        jsr CHROUT
        ldx $d6                    ; TBLX -- physical cursor row
        cpx #STATUS_ROW
        bcc term_chrout_rts
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
; NTSC (262 lines/frame) -- moves the START of the scroll's screen-
; memory writes to an off-screen moment, rather than however mid-frame
; the triggering character happened to land. Does NOT fully eliminate
; tearing on its own: the shift itself (two 880-byte copies, screen +
; color, ~3.5ms of CPU time) runs longer than a single vblank window
; (well under 1ms) and can spill back into active drawing time
; regardless. A complete fix would chunk the copy across several frames
; instead of doing it atomically; not pursued since checking real frames
; extracted from a screen recording (see project memory) found no
; visible tearing with just this cheap version. $d012 alone (without
; checking $d011 bit 7) is sufficient for line 250 since that's well
; under 256.
wait_vblank:
        lda $d012
        cmp #250
        bne wait_vblank
        rts

; Shift the dialogue window up, rows 1-22 -> rows 0-21 (screen + color),
; discarding old row 0, then blank the fresh row 22 and reposition the
; cursor there. Both of term_chrout's triggers (a bare CR, or a column
; wrap) reduce to exactly this -- neither ever leaves real new content
; in STATUS_ROW to preserve (see this section's own header comment).
term_scroll_advance:
        jsr wait_vblank
        lda #<(SCREEN_RAM+ROW_BYTES)
        sta copy_src_lo
        lda #>(SCREEN_RAM+ROW_BYTES)
        sta copy_src_hi
        lda #<SCREEN_RAM
        sta copy_dst_lo
        lda #>SCREEN_RAM
        sta copy_dst_hi
        jsr copy_dialogue_block

        lda #<(COLOR_RAM+ROW_BYTES)
        sta copy_src_lo
        lda #>(COLOR_RAM+ROW_BYTES)
        sta copy_src_hi
        lda #<COLOR_RAM
        sta copy_dst_lo
        lda #>COLOR_RAM
        sta copy_dst_hi
        jsr copy_dialogue_block

        lda #DIALOGUE_LAST_ROW
        jsr set_screen_line         ; scr_ptr_lo/hi = row 22 base
        ldy #0
        lda #$20
term_scroll_advance_blank:
        sta (scr_ptr_lo),y
        iny
        cpy #40
        bne term_scroll_advance_blank
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

; --- redraw_status_row: repaint STATUS_ROW with the currently-selected
; queued message (or an all-blank bar if the queue is empty), reverse
; video, padded to 40 columns. Pure raw SCREEN_RAM pokes -- no CHROUT,
; no cursor save/restore, no KERNAL_PLOT at all -- since queue content
; is pre-encoded screen codes already (same convention update_status_
; line already uses for row 0's banner). Destination is plain absolute
; indexed addressing (STATUS_ROW_OFFSET is a compile-time constant)
; rather than set_screen_line, freeing scr_ptr_lo/hi to be used solely
; for the source (queue slot) pointer -- a raw copy-with-OR needs two
; concurrent pointers, and this file's convention is one shared
; transient pointer, not a second dedicated zero-page pair for
; something this narrow.
redraw_status_row:
        lda status_queue_count
        beq redraw_status_row_blank
        lda status_queue_read
        jsr status_slot_addr        ; scr_ptr_lo/hi = &status_queue[read]
        ldy #0
redraw_status_row_copy:
        cpy #39
        bcs redraw_status_row_pad
        lda (scr_ptr_lo),y
        beq redraw_status_row_pad
        ora #$80                    ; reverse video -- same $80-bit trick
        sta SCREEN_RAM+STATUS_ROW_OFFSET,y
        iny
        jmp redraw_status_row_copy
redraw_status_row_pad:
        lda #$a0                    ; reverse-video space
redraw_status_row_pad_loop:
        cpy #40
        bcs redraw_status_row_rts
        sta SCREEN_RAM+STATUS_ROW_OFFSET,y
        iny
        jmp redraw_status_row_pad_loop
redraw_status_row_rts:
        rts
redraw_status_row_blank:
        ldy #0
        lda #$a0
redraw_status_row_blank_loop:
        sta SCREEN_RAM+STATUS_ROW_OFFSET,y
        iny
        cpy #40
        bne redraw_status_row_blank_loop
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
        lda #0
        sta cursor_blink_ticks   ; force an immediate reload/toggle at the
                                  ; new speed next update_cursor call, rather
                                  ; than finishing out the old speed's
                                  ; leftover countdown first
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

; --- Init NMI receive handler ---
; The SwiftLink cartridge raises NMI (not IRQ) when a byte arrives --
; init_swiftlink's SL_CMD_INIT already tells the ACIA to do this. Without
; a handler installed, those NMIs just go to the stock KERNAL handler,
; which ignores them: the byte sits in the ACIA's single-byte data
; register (no FIFO) until *something* reads it, and gets silently
; overwritten by the next arriving byte if nothing has. That was the
; real cause of losing the first few characters of each burst -- any
; time the main loop was off polling the keyboard (read_line) instead
; of draining the ACIA (sl_recv), bytes that arrived in that window
; were lost. Buffering every byte the instant it arrives, regardless of
; what the main loop is doing, fixes that at the root instead of just
; giving wait_for_data a bigger timing margin to reduce the odds of it.
;
; Reference: SwiftLink/Turbo-232 device driver by Craig Bruce (public
; domain) -- https://csbruce.com/cbm/swiftlib/swiftlib.s -- which does
; the same NMI-chaining + ring-buffer technique properly (with flow
; control, error counting, C128 support, etc.). This is a minimal
; receive-only version of that idea sized for this client's needs.
init_nmi:
        sei
        lda #0
        sta rx_head
        sta rx_tail
        lda $0318                ; save the current (KERNAL) NMI vector
        sta nmi_orig+0
        lda $0319
        sta nmi_orig+1
        lda #<nmi_handler
        sta $0318
        lda #>nmi_handler
        sta $0319
        cli
        rts

; --- NMI handler ---
; On entry the CPU has already pushed PC and status; A/X are ours to use
; as long as we save/restore them. If the NMI wasn't caused by a
; received byte (RDRF clear), it's not ours -- chain to whatever handler
; was previously installed (KERNAL's, which also covers the RESTORE key)
; rather than swallowing it.
nmi_handler:
        pha
        lda SL_STATUS
        and #SL_RDRF
        beq nmi_not_ours
        txa
        pha
        lda SL_DATA               ; read the byte -- also clears RDRF/NMI
        ldx rx_head
        sta rx_buf,x
        inc rx_head               ; wraps at 256, matching rx_buf's size

        ; Flow control: once rx_buf is getting full, deassert RTS so
        ; VICE's ACIA core disables its own RX alarm and genuinely stops
        ; draining the TCP socket (aciacore.c's acia_set_handshake_lines(),
        ; ACIA_CMD_BITS_TRANSMITTER_NO_RTS case, clears alarm_active_rx --
        ; that alarm is what schedules the getc()/recv() calls). Once
        ; VICE stops recv()-ing, the OS's real TCP receive window closes,
        ; and the server's own write()/drain() will eventually block --
        ; genuine end-to-end backpressure, not just an emulator-local
        ; buffer swap. sl_recv (mainline) re-asserts RTS once drained.
        lda rts_state
        beq nmi_rts_done          ; already off, nothing to do
        lda rx_head
        sec
        sbc rx_tail                ; A = bytes currently buffered (unsigned, mod 256)
        cmp #RX_HIGH_WATER
        bcc nmi_rts_done          ; still comfortably below the high water mark
        lda #SL_CMD_RTS_OFF
        sta SL_COMMAND
        lda #0
        sta rts_state
nmi_rts_done:

        pla
        tax
        pla
        rti
nmi_not_ours:
        pla
        jmp (nmi_orig)

; --- SwiftLink send byte ---
; Input: .A = byte to send
; Waits for transmit register empty, then sends
sl_send:
        pha
@:      lda SL_STATUS
        and #SL_TDRE            ; transmit register empty?
        beq <@                  ; no, keep waiting
        pla
        sta SL_DATA             ; send byte
        rts

; --- Receive byte from the NMI ring buffer ---
; Output: carry set = byte received, .A = byte
;         carry clear = no byte waiting
; The actual ACIA read happens in nmi_handler, asynchronously to
; whatever the main loop is doing -- this just drains what it buffered.
sl_recv:
        lda rx_tail
        cmp rx_head
        beq sl_recv_empty        ; head == tail: nothing buffered
        ldx rx_tail
        lda rx_buf,x
        pha                      ; stash the byte -- flow-control check below uses A
        inc rx_tail

        ; Re-assert RTS once the buffer has drained back down (hysteresis:
        ; a lower threshold than nmi_handler's pause point avoids rapid
        ; on/off toggling right at a single boundary).
        lda rts_state
        bne sl_recv_rts_done     ; already on, nothing to do
        lda rx_head
        sec
        sbc rx_tail
        cmp #RX_LOW_WATER
        bcs sl_recv_rts_done     ; still above the low water mark
        lda #SL_CMD_INIT
        sta SL_COMMAND
        lda #1
        sta rts_state
sl_recv_rts_done:
        pla
        sec
        rts
sl_recv_empty:
        clc
        rts

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

{include:screen-handler_pp.asm}

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

; Which single value cursor_blink_ticks reloads to on every toggle --
; also doubles as a blink-speed selector: $08 fast, $10 normal (the
; original hardcoded default), $20 slow, $40 very slow. $00 is a
; reserved sentinel meaning "solid, no blink" (speed 5) -- see
; update_cursor's own comment. Must match commands/c64_display.py's
; BLINK_SPEED_MASKS (speed# 1-5 -> mask) and config_menu.asm's own copy
; of that table exactly. Set by config_menu.asm's Video Settings popup
; when the player picks a speed and applies it live; stays at the
; default otherwise. Named "_mask" for history/wire-protocol reasons
; (it used to be AND-ed against a bit of the free-running jiffy clock,
; see cursor_blink_ticks's own comment for why that changed) -- the
; numeric values themselves didn't need to change, only how
; update_cursor uses them.
cursor_blink_mask:
        byte $10

; Countdown reload from cursor_blink_mask, decremented by
; irq_task_cursor_blink (the IRQ round-robin task, see irq_task_table)
; every tick. update_cursor (called from read_line_loop, mainline
; context) toggles the cursor exactly when this hits 0, then reloads it
; from cursor_blink_mask -- reusing that byte's existing numeric value
; directly as the tick count is not a coincidence: bit N of a free-
; running counter (the old design's mechanism) is 0 for 2^N ticks then
; 1 for 2^N ticks, the same square wave a decrement-to-zero-and-reload
; counter with reload=2^N produces, and $08/$10/$20/$40 are exactly
; 2^3/2^4/2^5/2^6. Kept as a lightweight IRQ-decremented counter (never
; touching CHROUT/PLOT or the PNT/PNTR pointers cursor_toggle reads)
; rather than calling update_cursor's actual toggle from IRQ context --
; the KERNAL screen editor doesn't update PNT/PNTR atomically with
; respect to interrupts, so a toggle firing mid-CHROUT elsewhere in the
; client could flip the wrong on-screen byte. Same design as
; client-128.asm's blinkctr/irq_task_cursor_blink -- ported back here
; deliberately for parity across both clients, not independently
; invented twice.
cursor_blink_ticks:
        byte 0

rts_state:
        byte 1                   ; 1 = RTS currently asserted (ready), 0 = deasserted

x_save:
        byte 0                   ; TEMP: scratch for the read_line_loop hex-dump diagnostic
y_save:
        byte 0                   ; scratch for preserving .Y across update_cursor/CHROUT calls

; Called directly from read_line_loop every poll iteration (mainline
; context, same as before this file grew an IRQ task table at all) --
; only irq_task_cursor_blink's lightweight tick-down runs from IRQ, see
; cursor_blink_ticks's own comment for why. Only touches the screen on
; a phase transition, so it doesn't flicker while sitting in one state.
; cursor_blink_mask == $00 is a reserved sentinel meaning "solid, no
; blink at all" (blink speed 5 -- Ryan's ask: some screen-reader/
; accessibility software, e.g. Gadget, doesn't get along with a
; blinking cursor) -- checked first and skips the tick-countdown
; entirely, since cursor_blink_ticks is never reloaded/consulted in
; solid mode (irq_task_cursor_blink's own beq-on-zero guard means an
; always-0 counter just never decrements either, harmless either way).
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
        lda cursor_blink_ticks
        bne update_cursor_done   ; not time yet -- irq_task_cursor_blink is
                                  ; ticking this down in the background
        lda cursor_blink_mask
        sta cursor_blink_ticks   ; reload for the next half-period
        jsr cursor_toggle
        lda cursor_phase
        eor #1
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
        jsr update_cursor         ; blink the cursor while waiting for a key
                                   ; -- irq_task_cursor_blink only ticks the
                                   ; countdown in the background, this is
                                   ; still what actually toggles it, see
                                   ; cursor_blink_ticks's own comment
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

        ; CRSR UP/DOWN were never in read_line's own dispatch chain at
        ; all before this -- unhandled, they fell through to
        ; read_line_store and got typed as literal control bytes, which
        ; is worse here than a stray on-screen glyph the way it was on
        ; the 128 client (see input_editor.asm's own cursor up/down
        ; fix): read_line_store also ECHOES the typed byte via CHROUT,
        ; and CHROUT-ing $91/$11 as OUTPUT actually executes them as
        ; cursor-up/cursor-down control codes, moving the real screen
        ; cursor around uncontrolled -- confirmed live 2026-08-24 by
        ; Ryan. Rather than just ignore them (matching the 128 side),
        ; Ryan asked for CRSR UP -> start of line, CRSR DOWN -> end of
        ; line (when CTRL isn't also held -- see below), a more useful
        ; binding than a no-op given they're otherwise unused.
        cmp #$91                 ; CRSR UP (shift+CRSR key)?
        bne read_line_check_left
        jsr read_line_home
        jmp read_line_loop
read_line_check_left:

        ; CTRL+CRSR-LEFT/CTRL+CRSR-DOWN -> word-left/word-right, checked
        ; ahead of the ordinary dispatch below since GETIN's own byte
        ; for a cursor key doesn't change when CTRL is also held (CTRL
        ; only modifies the encoding for letter keys, not cursor keys).
        ; $028D (653 decimal, SFDX) is the KERNAL's live SHIFT/
        ; Commodore/CTRL status (0/1/2/4), the C64 cross-reference
        ; Compute's 128 Programmer's Guide gives for the 128's own $D3
        ; -- bit 2 (value 4) is CTRL. IMPORTANT: use $028d, not the
        ; bare decimal literal 653 -- c64list assembles an unprefixed
        ; number as HEX by default, so `lda 653` silently assembled as
        ; LDA $0653 (a completely unrelated address), not decimal 653
        ; ($028d). This was a real bug caught live during testing 2026-
        ; 08-24 (Ryan spotted it) -- confirmed via live disassembly that
        ; every `lda 653` in an earlier draft of this dispatch compiled
        ; to `LDA $0653`, which is why the CTRL bit never appeared to
        ; be set no matter what was actually held. Same key combo the
        ; 128 client's input_editor.asm uses (see its own comment
        ; there) for cross-client consistency, chosen there because
        ; the 128's F1/F7 are unusable as plain shortcuts (KERNAL auto-
        ; expands them into whole command strings) -- the C64 doesn't
        ; have that specific problem, but read_line never had word-jump
        ; at all before this, so there's no existing F1/F7 binding
        ; being displaced either.
        ;
        ; NOTE (2026-08-24): CTRL+CRSR-LEFT/DOWN could not be live-
        ; confirmed working end-to-end in this session's sandboxed VICE
        ; testing environment -- isolated via a pure-BASIC PEEK(653)/
        ; GET A$ test (independent of this file entirely) that Tab
        ; (VICE's mapped CTRL key here) reads correctly as 4 when held
        ; alone, and C=+cursor correctly shows a nonzero SFDX value,
        ; but Tab+cursor (any direction, including CRSR DOWN, which
        ; shares neither row nor column with Tab in the keyboard
        ; matrix, ruling out real matrix ghosting) never registers any
        ; GETIN event at all. This looks like a VICE/GTK-specific
        ; limitation of the Tab key specifically when held with another
        ; key (Tab doubles as a GTK focus-navigation key), not a bug in
        ; this dispatch logic, which is verified correct via py65
        ; disassembly against source intent. Ryan's own idea for a real
        ; fix -- installing assembly-language/3-key-rollover-source.lbl
        ; (a custom IRQ-driven keyboard scan bypassing the KERNAL's own,
        ; already present in this repo, untracked/unintegrated) in
        ; place of the KERNAL's scan -- is a legitimate direction but a
        ; separate, larger undertaking than this dispatch change;
        ; parked rather than attempted in the same session. Confirm
        ; the actual key combo on real hardware or a differently-
        ; configured VICE before relying on it.
        cmp #$9d                 ; CRSR LEFT (shift+CRSR key)?
        bne read_line_check_ctrl_down
        pha
        lda $028d
        and #4
        beq read_line_left_plain ; CTRL not held -- ordinary cursor-left
        pla                      ; CTRL held -- discard stashed byte,
        jsr read_line_word_left  ; word-jump instead
        jmp read_line_loop
read_line_left_plain:
        pla
        jmp read_line_left

read_line_check_ctrl_down:
        cmp #$11                 ; CRSR DOWN -- see the header comment
        bne read_line_dispatch_rest ; above for the UP/DOWN backstory
        pha
        lda $028d
        and #4
        beq read_line_down_plain ; CTRL not held -- jump to end of line
        pla
        jsr read_line_word_right
        jmp read_line_loop
read_line_down_plain:
        pla
        jsr read_line_end
        jmp read_line_loop

read_line_dispatch_rest:
        cmp #$14                 ; DEL (PETSCII backspace)?
        beq read_line_del
        cmp #$94                 ; INST (shift+DEL) -- insert a blank at cursor?
        beq read_line_inst
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

; --- read_line_word_left / read_line_word_right: CTRL+CRSR-LEFT/CTRL+
; CRSR-DOWN word-jump (see read_line_not_return's own comment). Plain
; callable subroutines (rts-ending), called via jsr then jmp read_line_
; loop -- same safe shape exkey/jmpkey uses on the 128 client's own
; dispatch, not the trickier stack-unwind its return: handler needs
; (not needed here since these don't skip any enclosing frame, just
; move the cursor and return normally).
;
; Both peek at the character about to be stepped over BEFORE deciding
; to move, rather than moving first and checking after -- keeps the
; loop symmetric and avoids an extra out-of-bounds read at cursor_pos
; 0/linelen (the entry/top-of-loop bounds check always runs first).
read_line_word_left:
        lda cursor_pos
        beq read_line_word_left_rts     ; already at start -- nothing left
read_line_word_left_spaces:
        lda cursor_pos
        beq read_line_word_left_rts
        ldx cursor_pos
        lda linebuf-1,x                 ; char immediately before cursor_pos
        cmp #' '
        bne read_line_word_left_word    ; found real text -- skip the word now
        dec cursor_pos
        jsr term_cursor_left
        jmp read_line_word_left_spaces
read_line_word_left_word:
        lda cursor_pos
        beq read_line_word_left_rts
        ldx cursor_pos
        lda linebuf-1,x
        cmp #' '
        beq read_line_word_left_rts     ; that's the boundary -- stop here,
                                          ; cursor_pos is now at the word's
                                          ; own first character
        dec cursor_pos
        jsr term_cursor_left
        jmp read_line_word_left_word
read_line_word_left_rts:
        rts

read_line_word_right:
        lda cursor_pos
        cmp linelen
        beq read_line_word_right_rts    ; already at end
read_line_word_right_word:
        lda cursor_pos
        cmp linelen
        beq read_line_word_right_rts
        ldx cursor_pos
        lda linebuf,x                   ; char at cursor_pos, about to be
                                          ; stepped over
        cmp #' '
        beq read_line_word_right_spaces ; found the word's trailing space
        inc cursor_pos
        jsr term_cursor_right
        jmp read_line_word_right_word
read_line_word_right_spaces:
        lda cursor_pos
        cmp linelen
        beq read_line_word_right_rts
        ldx cursor_pos
        lda linebuf,x
        cmp #' '
        bne read_line_word_right_rts    ; found the next word's first char
        inc cursor_pos
        jsr term_cursor_right
        jmp read_line_word_right_spaces
read_line_word_right_rts:
        rts

; --- read_line_home / read_line_end: CRSR UP -> start of line, CRSR
; DOWN (without CTRL) -> end of line -- see read_line_not_return's own
; comment. Plain callable subroutines (rts-ending), same jsr-then-jmp-
; read_line_loop shape as read_line_word_left/right above.
read_line_home:
        lda cursor_pos
        beq read_line_home_rts
        dec cursor_pos
        jsr term_cursor_left
        jmp read_line_home
read_line_home_rts:
        rts

read_line_end:
        lda cursor_pos
        cmp linelen
        beq read_line_end_rts
        inc cursor_pos
        jsr term_cursor_right
        jmp read_line_end
read_line_end_rts:
        rts

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
        lda #0
        sta cursor_blink_ticks     ; see set_blink_mask's own comment
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
        ; Snapshot the KERNAL jiffy clock ($a0/$a1/$a2, hi/mid/lo -- $a2 is
        ; the fastest-changing byte) so #stop can print real elapsed time
        ; alongside sid_frames_played, no stopwatch needed.
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

; Round-robin job that paces the blinking input cursor -- only
; decrements a plain counter byte, never touches CHROUT/PLOT or the
; PNT/PNTR pointers cursor_toggle reads, so (unlike a task that called
; update_cursor's actual toggle directly) it's safe to run
; unconditionally, whether or not read_line is even active right now.
; See cursor_blink_ticks's own comment. Same design as
; client-128.asm's irq_task_cursor_blink/blinkctr.
irq_task_cursor_blink:
        lda cursor_blink_ticks
        beq irq_task_cursor_blink_rts
        dec cursor_blink_ticks
irq_task_cursor_blink_rts:
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
        word irq_task_cursor_blink
IRQ_TASK_TABLE_LEN = 4          ; entries * 2 -- keep in sync with the table above

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
