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
; less likely than one.
{const: SID_STREAM_START   $01}
{const: SID_STREAM_CONFIRM $53}   ; 'S' -- arbitrary, just distinctive
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
{const: CANVAS_STREAM_CONFIRM $42}   ; 'B' for "banner" -- distinct from
                                       ; SID_STREAM_CONFIRM ('S')

; Display-settings (config menu) stream marker -- same idea/reasoning as
; CANVAS_STREAM_CONFIRM above, own distinct confirm byte so
; handle_recv_byte_confirm can tell this apart from a SID or canvas
; stream. Matches commands/c64_display.py (server side) exactly.
{const: DISPLAY_STREAM_CONFIRM $44}   ; 'D' for "display"

; KERNAL routines used by load_petscii_editor/load_config_menu to LOAD an
; overlay module from disk on demand (see load_petscii_editor's own
; comment for why this is a separate on-disk module rather than resident
; code).
{const: KERNAL_SETNAM $ffbd}
{const: KERNAL_SETLFS $ffba}
{const: KERNAL_LOAD    $ffd5}

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
; Lives in the datasette buffer ($033c-$03fb), unused since this client
; never touches the tape -- populated at boot by init_jump_table (copied
; up from jump_table_template, since a PRG's own bytes can only occupy
; one contiguous block starting at its own load address, which is well
; above this page).
{const: JT_BASE    $0340}
{const: JT_SL_SEND  $0340}     ; jmp sl_send
{const: JT_SL_RECV  $0343}     ; jmp sl_recv
{const: JT_RESUME   $0346}     ; jmp prompt_loop -- hands control back to
                                 ; the resident request/response loop once
                                 ; the overlay is done (saved or cancelled)
{const: JT_SAVE_SCREEN    $0349}  ; jmp save_screen -- SCREEN_RAM/COLOR_RAM
                                    ; -> BACKUP_CHARS/BACKUP_COLORS
{const: JT_RESTORE_SCREEN $034c}  ; jmp restore_screen -- reverse of the above.
                                    ; Both added so petscii_editor.asm's help
                                    ; overlay (previously its own private
                                    ; 2000-byte BACKUP_CHARS/BACKUP_COLORS +
                                    ; copy_1000) and any future popup-window
                                    ; module (e.g. a config menu) share one
                                    ; resident save/restore buffer instead of
                                    ; each module allocating its own -- Ryan's
                                    ; ask. Only one module is ever resident at
                                    ; OVERLAY_BUF at a time, so there's no
                                    ; concurrent-use concern.
{const: JT_SET_BLINK_MASK $034f}  ; jmp set_blink_mask -- .a = new
                                    ; cursor_blink_mask value. A setter
                                    ; routine, not a raw fixed-address poke,
                                    ; because cursor_blink_mask is an
                                    ; ordinary resident variable whose real
                                    ; address shifts on every resident edit
                                    ; -- same reason overlay modules can't
                                    ; just `sta` a resident label directly.
                                    ; Used by config_menu.asm's Video
                                    ; Settings popup to apply a blink speed
                                    ; live as the player picks it.

; Zero page pointers
        scr_ptr_lo  = $fb       ; screen write pointer low byte
        scr_ptr_hi  = $fc       ; screen write pointer high byte

        MAX_LINE    = 80        ; keyboard input line buffer size

        RX_HIGH_WATER = 200     ; rx_buf bytes-buffered count that triggers RTS-off
        RX_LOW_WATER  = 32      ; count that triggers RTS back on (hysteresis)

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
        rts                       ; settled -- no bytes for a while, done
wait_for_data_got_byte:
        jsr handle_recv_byte
        lda sid_mode
        cmp #1
        beq wait_for_data_backgrounding
        jmp wait_for_data_drain
wait_for_data_backgrounding:
        rts

; --- Init screen ---
; Clear screen, draw the status line, set up screen pointer
init_screen:
        lda #VIC_BLACK
        sta VIC_BORDER
        sta VIC_BACKGROUND
        lda #$93                ; PETSCII clear screen
        jsr CHROUT
        jsr update_status_line
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
; Copies jump_table_template's 18 bytes up into the fixed JT_BASE page
; ($0340) -- see JT_BASE's own comment for why this can't just be
; assembled directly at $0340 (a PRG only occupies one contiguous block
; starting at its own load address, well above this page).
init_jump_table:
        ldx #17
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

; Plain untransformed SCREEN_CELLS-byte copy. Input: copy_src_lo/hi =
; source base address, copy_dst_lo/hi = dest base address. Ported
; verbatim from petscii_editor.asm's own copy_1000 (self-modified
; lda/sta operands, incrementing the operand bytes directly rather than
; X/Y indexed addressing, since the buffer exceeds 256 bytes) -- same
; "no ds directive, no macro parameters" pattern documented in
; CLIENT_MECHANICS.md.
copy_1000:
        lda copy_src_lo
        sta copy_src_load+1
        lda copy_src_hi
        sta copy_src_load+2
        lda copy_dst_lo
        sta copy_dst_store+1
        lda copy_dst_hi
        sta copy_dst_store+2
        lda #<SCREEN_CELLS
        sta copy_remaining_lo
        lda #>SCREEN_CELLS
        sta copy_remaining_hi
copy_1000_loop:
copy_src_load:
        lda $ffff
copy_dst_store:
        sta $ffff
        inc copy_src_load+1
        bne copy_src_no_carry
        inc copy_src_load+2
copy_src_no_carry:
        inc copy_dst_store+1
        bne copy_dst_no_carry
        inc copy_dst_store+2
copy_dst_no_carry:
        lda copy_remaining_lo
        bne copy_dec_lo
        dec copy_remaining_hi
copy_dec_lo:
        dec copy_remaining_lo
        lda copy_remaining_lo
        ora copy_remaining_hi
        bne copy_1000_loop
        rts

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
        jsr CHROUT
        lda #'L'
        jsr CHROUT
        lda #'O'
        jsr CHROUT
        lda #'A'
        jsr CHROUT
        lda #'D'
        jsr CHROUT
        lda #' '
        jsr CHROUT
        lda #'E'
        jsr CHROUT
        lda #'R'
        jsr CHROUT
        lda #'R'
        jsr CHROUT
        lda #' '
        jsr CHROUT
        lda #'$'
        jsr CHROUT
        pla
        jsr sid_print_hex_byte
        lda #$0d
        jsr CHROUT
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
; Deliberately only touches rx_buf while mid-stream (sid_mode != 0): if
; sid_mode is 0, whatever's waiting is ordinary text (or a stray byte
; before a stream even starts), and calling handle_recv_byte for it here
; would call display_char and corrupt whatever the player is mid-typing.
; Left alone, it just sits safely in rx_buf for wait_for_data to display
; normally on the next round-trip, exactly like today when nothing is
; playing at all.
sid_service_background:
        lda sid_mode
        beq sid_service_background_rts
        jsr sl_recv
        bcc sid_service_background_rts
        jsr handle_recv_byte
sid_service_background_rts:
        rts

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
        jsr CHROUT
        pla
        pha
        jsr print_hex_byte
        lda #'>'
        jsr CHROUT
        lda #'['
        jsr CHROUT
        lda linelen
        jsr print_hex_byte
        lda #']'
        jsr CHROUT
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
        lda #$9d                 ; step the screen cursor back onto the
        jsr CHROUT               ; now-deleted column
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
        lda #$9d
        jsr CHROUT
        jmp read_line_loop

read_line_right:
        lda cursor_pos            ; same out-of-range concern as
        cmp linelen               ; read_line_left above
        bcc read_line_right_move ; not at end of line
        jmp read_line_loop
read_line_right_move:
        inc cursor_pos
        lda #$1d
        jsr CHROUT
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
        jsr CHROUT               ; echo the typed char locally

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
        jsr CHROUT
        inc redraw_idx
        jmp redraw_print_loop
redraw_print_done:
        lda redraw_extra
        beq redraw_back_setup
        lda #$20
        jsr CHROUT
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
        lda #$9d
        jsr CHROUT
        jmp redraw_back_loop
redraw_done:
        rts

read_line_done:
        ldx linelen
        lda #0
        sta linebuf,x            ; null-terminate right at the real length
        lda #$0d
        jsr CHROUT               ; echo the newline locally
        ; TEMP diagnostic: show how many characters read_line actually
        ; captured. Remove once the character-loss bug is confirmed fixed.
{ifdef: debug}
        lda #'['
        jsr CHROUT
        lda #'L'
        jsr CHROUT
        lda linelen             ; was x_save
        jsr print_hex_byte
        lda #']'
        jsr CHROUT
        lda #$0d
        jsr CHROUT
{endif}
        rts

; --- TEMP diagnostic: print .A as two hex digits ---
{ifdef: debug}
hex_digits:
        ascii "0123456789ABCDEF"

print_hex_nibble:                ; .A = nibble (0-15)
        tax
        lda hex_digits,x
        jsr CHROUT
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
display_char:
        cmp #$0d                ; carriage return?
        bne >@
        lda #$0d
        jsr CHROUT
        rts
@:      jsr CHROUT              ; let KERNAL handle PETSCII->screen code conversion
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
handle_recv_byte:
        ldy sid_mode
        beq handle_recv_byte_text
        cpy #1
        beq handle_recv_byte_len_lo
        cpy #2
        beq handle_recv_byte_len_hi
        cpy #4
        beq handle_recv_byte_confirm
        jmp handle_recv_byte_store        ; sid_mode == 3

handle_recv_byte_text:
        cmp #SID_STREAM_START
        beq handle_recv_byte_maybe_start
        cmp #SID_STOP
        beq handle_recv_byte_stop
        jmp display_char

handle_recv_byte_stop:
        jsr sid_print_frames_played  ; TEMP diagnostics -- see their own
        jsr sid_print_elapsed        ; comments
        jsr sid_print_pointers
        jsr sid_print_stream_starts
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
        rts

handle_recv_byte_confirm:
        cmp #SID_STREAM_CONFIRM
        beq handle_recv_byte_start
        cmp #CANVAS_STREAM_CONFIRM
        beq handle_recv_byte_canvas_confirm
        cmp #DISPLAY_STREAM_CONFIRM
        beq handle_recv_byte_display_confirm
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

handle_recv_byte_start:
        inc sid_stream_starts     ; TEMP diagnostic -- see its own comment
        lda #0
        sta sid_rd
        sta sid_wr
        sta sid_byte_count+0
        sta sid_byte_count+1
        sta sid_frames_played+0
        sta sid_frames_played+1
        lda #1
        sta sid_mode
        sta sid_active
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
                                   ; (read_line, player mid-typing) --
                                   ; CHROUT-ing them here would corrupt
                                   ; the input line; see
                                   ; sid_service_background's own comment
        jsr sid_print_byte_count
        jsr sid_print_pointers    ; TEMP diagnostic -- rd/wr right *now*,
                                   ; before any further idle time, to tell
                                   ; whether SID_BUF is already wrapped by
                                   ; the time reception itself finishes
        jsr sid_print_bufdump
handle_recv_byte_store_done:
        rts

; --- TEMP diagnostic: dump SID_BUF[0..23] as hex ---
; Ground truth for comparing against the server's own encoded bytes (see
; sid_engine.frames.encode_stream output) -- confirms whether stored
; frame data matches what was actually sent, independent of the byte
; *count* already being verified correct by sid_print_byte_count.
;
; Keeps its loop index in a memory byte (sid_dump_idx), not X: X is
; scratch inside sid_print_hex_byte/sid_print_hex_nibble (used for the
; hex-digit-table lookup) and CHROUT itself isn't reliable about
; preserving X either (see read_line's own linelen -- same fix, same
; underlying lesson, learned the hard way earlier in this file).
sid_print_bufdump:
        lda #0
        sta sid_dump_idx
sid_print_bufdump_loop:
        ldx sid_dump_idx
        lda SID_BUF,x
        jsr sid_print_hex_byte
        lda #' '
        jsr CHROUT
        inc sid_dump_idx
        lda sid_dump_idx
        cmp #24
        bne sid_print_bufdump_loop
        lda #$0d
        jsr CHROUT
        rts

; --- Print "GOT $xxxx BYTES" -- diagnostic for the SID stream pipe ---
; Prints sid_byte_count (hi byte first) as 4 hex digits. Unconditional
; (not gated behind {ifdef:debug}) since this answers a real end-to-end
; question -- did the bytes the server said it sent actually arrive --
; not a temporary bug hunt.
; --- TEMP diagnostic: print "PLAYED $xxxx FRAMES" ---
; sid_frames_played counts every frame sid_play has successfully applied
; since the current stream started (reset in handle_recv_byte_start).
; Printed on `play #stop` -- comparing this count against real elapsed
; (stopwatch) time gives the client's true empirical playback rate,
; cutting through any PAL/NTSC IRQ-rate guessing.
sid_print_frames_played:
        lda #'P'
        jsr CHROUT
        lda #'L'
        jsr CHROUT
        lda #'A'
        jsr CHROUT
        lda #'Y'
        jsr CHROUT
        lda #'E'
        jsr CHROUT
        lda #'D'
        jsr CHROUT
        lda #' '
        jsr CHROUT
        lda #'$'
        jsr CHROUT
        lda sid_frames_played+1
        jsr sid_print_hex_byte
        lda sid_frames_played+0
        jsr sid_print_hex_byte
        lda #' '
        jsr CHROUT
        lda #'F'
        jsr CHROUT
        lda #'R'
        jsr CHROUT
        lda #'A'
        jsr CHROUT
        lda #'M'
        jsr CHROUT
        lda #'E'
        jsr CHROUT
        lda #'S'
        jsr CHROUT
        lda #$0d
        jsr CHROUT
        rts

; --- TEMP diagnostic: print "ELAPSED $xxxxxx JIFFIES" ---
; current jiffy clock ($a0/$a1/$a2) minus the snapshot handle_recv_byte_
; start took when the stream began -- standard 3-byte subtract-with-
; borrow, low byte first. No BCD involved; the jiffy clock is a plain
; binary counter.
sid_print_elapsed:
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

        lda #'E'
        jsr CHROUT
        lda #'L'
        jsr CHROUT
        lda #'A'
        jsr CHROUT
        lda #'P'
        jsr CHROUT
        lda #'S'
        jsr CHROUT
        lda #'E'
        jsr CHROUT
        lda #'D'
        jsr CHROUT
        lda #' '
        jsr CHROUT
        lda #'$'
        jsr CHROUT
        lda sid_jiffy_elapsed0
        jsr sid_print_hex_byte
        lda sid_jiffy_elapsed1
        jsr sid_print_hex_byte
        lda sid_jiffy_elapsed2
        jsr sid_print_hex_byte
        lda #' '
        jsr CHROUT
        lda #'J'
        jsr CHROUT
        lda #'I'
        jsr CHROUT
        lda #'F'
        jsr CHROUT
        lda #'F'
        jsr CHROUT
        lda #'I'
        jsr CHROUT
        lda #'E'
        jsr CHROUT
        lda #'S'
        jsr CHROUT
        lda #$0d
        jsr CHROUT
        rts

; --- TEMP diagnostic: print "RD=$xx WR=$xx" ---
; Raw current values of sid_rd/sid_wr at the moment #stop was processed.
; Ground truth for whether SID_BUF's producer/consumer indices are where
; they should be (matching sid_byte_count/sid_frames_played) or have
; drifted -- e.g. sid_wr still growing after "GOT" already printed would
; mean more bytes are landing in SID_BUF than accounted for.
sid_print_pointers:
        lda #'R'
        jsr CHROUT
        lda #'D'
        jsr CHROUT
        lda #'='
        jsr CHROUT
        lda #'$'
        jsr CHROUT
        lda sid_rd
        jsr sid_print_hex_byte
        lda #' '
        jsr CHROUT
        lda #'W'
        jsr CHROUT
        lda #'R'
        jsr CHROUT
        lda #'='
        jsr CHROUT
        lda #'$'
        jsr CHROUT
        lda sid_wr
        jsr sid_print_hex_byte
        lda #$0d
        jsr CHROUT
        rts

; --- TEMP diagnostic: print "STARTS=$xx" ---
; sid_stream_starts counts every time handle_recv_byte_start fired (a
; real SID_STREAM_START+SID_STREAM_CONFIRM pair was seen) since the last
; #stop. A count > 1 when the player only issued one `play` command
; means something else on this connection is triggering stream starts --
; ambient/ally/room broadcasts most likely, given this is a live
; multiplayer server. Ground truth for whether the confirm-byte fix
; actually stopped spurious triggers or just made them rarer.
sid_print_stream_starts:
        lda #'S'
        jsr CHROUT
        lda #'T'
        jsr CHROUT
        lda #'A'
        jsr CHROUT
        lda #'R'
        jsr CHROUT
        lda #'T'
        jsr CHROUT
        lda #'S'
        jsr CHROUT
        lda #'='
        jsr CHROUT
        lda #'$'
        jsr CHROUT
        lda sid_stream_starts
        jsr sid_print_hex_byte
        lda #$0d
        jsr CHROUT
        rts

sid_print_byte_count:
        lda #'G'
        jsr CHROUT
        lda #'O'
        jsr CHROUT
        lda #'T'
        jsr CHROUT
        lda #' '
        jsr CHROUT
        lda #'$'
        jsr CHROUT
        lda sid_byte_count+1
        jsr sid_print_hex_byte
        lda sid_byte_count+0
        jsr sid_print_hex_byte
        lda #' '
        jsr CHROUT
        lda #'B'
        jsr CHROUT
        lda #'Y'
        jsr CHROUT
        lda #'T'
        jsr CHROUT
        lda #'E'
        jsr CHROUT
        lda #'S'
        jsr CHROUT
        lda #$0d
        jsr CHROUT
        rts

sid_print_hex_nibble:             ; .A = nibble (0-15)
        pha
        and #$0f
        tax
        lda sid_hex_digits,x
        jsr CHROUT
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
        lda SID_BUF,x
        inx
        cmp #SID_FRAME_END
        bne sid_play_scan

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
{alpha:poke}
status_msg:
        ascii " TADA CLIENT "
        ascii {usedef:__BuildDate}
        ascii " - CONNECTING..."
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

sid_byte_count:
        byte 0,0                 ; lo,hi -- bytes redirected into SID_BUF this
                                  ; stream, reset on SID_STREAM_START, printed
                                  ; by sid_print_byte_count once the mode-3
                                  ; countdown (sid_remaining_lo/hi) hits zero

sid_dump_idx:
        byte 0                   ; sid_print_bufdump's loop counter

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
sid_jiffy_elapsed1:                ; by sid_print_elapsed
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
