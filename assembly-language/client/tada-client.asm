; tada-client.asm
; TADA C64 Client - Milestone 1
; SwiftLink init, connect to server, negotiate terminal, echo to screen
;
; Build:
;   make build
;
; Requires: SwiftLink cartridge at $de00
;           TADA server listening on 127.0.0.1:34064

; Comment out to strip all {ifdef:debug}...{endif} diagnostic output
; (the <XX>/[XX] read_line trace, hex_digits/print_hex_byte helpers, etc).
{def: debug}

; SwiftLink ACIA registers
{const: SL_DATA     $de00}      ; data register
{const: SL_STATUS   $de01}      ; status register
{const: SL_COMMAND  $de02}      ; command register
{const: SL_CONTROL  $de03}      ; control register

; ACIA status bits
{const: SL_RDRF     $08}        ; bit 3: receive data register full
{const: SL_TDRE     $10}        ; bit 4: transmit data register empty

; ACIA command register values
{const: SL_CMD_INIT $09}        ; DTR low, RTS low, RxD IRQ on
{const: SL_CMD_OFF  $0b}        ; RxD/TxD IRQs off, DTR low

; ACIA control register: 19200 baud, 8-bit, 1 stop, internal clock
{const: SL_CTRL_19K $1e}

; Zero page pointers
        scr_ptr_lo  = $fb       ; screen write pointer low byte
        scr_ptr_hi  = $fc       ; screen write pointer high byte

        MAX_LINE    = 80        ; keyboard input line buffer size

        rx_head     = $f9       ; NMI receive ring buffer: next write index
        rx_tail     = $fa       ; NMI receive ring buffer: next read index

; --- Program start ---

        orig $0801

; BASIC stub: 10 SYS2061
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00

start:
        jsr init_screen
        jsr init_nmi             ; install our receive handler before the
        jsr init_swiftlink       ; ACIA is told to start raising NMIs on it

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
; byte, instead of returning on the very first gap.
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
wait_for_data_first:
        jsr sl_recv
        bcc wait_for_data_first   ; keep waiting for the very first byte
        jsr display_char
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
        jsr display_char
        jmp wait_for_data_drain

; --- Init screen ---
; Clear screen, print status message, set up screen pointer
init_screen:
        lda #$93                ; PETSCII clear screen
        jsr CHROUT
        lda #$12                ; PETSCII reverse on
        jsr CHROUT
        ldx #0
@:      lda status_msg,x
        beq >@
        jsr CHROUT
        inx
        bne <@
@:      lda #$92                ; PETSCII reverse off
        jsr CHROUT
        lda #$0d                ; carriage return
        jsr CHROUT
        lda #$0d
        jsr CHROUT
        ; set screen pointer to row 2 col 0
        lda #<(SCREEN_RAM + 80)
        sta scr_ptr_lo
        lda #>(SCREEN_RAM + 80)
        sta scr_ptr_hi
        rts

; --- Init SwiftLink ---
; Reset ACIA and configure for 19200 baud 8N1
init_swiftlink:
        lda #SL_CMD_OFF         ; disable interrupts
        sta SL_COMMAND
        lda #SL_CTRL_19K        ; 19200 baud, 8N1, internal clock
        sta SL_CONTROL
        lda #SL_CMD_INIT        ; DTR low, RTS low, RxD IRQ on
        sta SL_COMMAND
        rts

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
        inc rx_tail
        sec
        rts
sl_recv_empty:
        clc
        rts

; --- Blinking input cursor ---
; GETIN-driven input (unlike CHRIN) never engages the KERNAL's own
; line-editor cursor blink, so read_line draws its own: a reverse-video
; space, blinked via bit 4 of $a2 (fastest-changing byte of the KERNAL's
; free-running jiffy clock, ticks ~60/sec) for a roughly 2-3 Hz blink.
; Uses only CHROUT + PETSCII control codes (reverse on/off, cursor left)
; so it never needs to compute a raw screen RAM address.
cursor_phase:
        byte 0                   ; 0 = currently erased, 1 = currently drawn

x_save:
        byte 0                   ; TEMP: scratch for the read_line_loop hex-dump diagnostic
y_save:
        byte 0                   ; scratch for preserving .Y across update_cursor/CHROUT calls

; Call once per read_line poll iteration. Only touches the screen on a
; phase transition, so it doesn't flicker while sitting in one state.
update_cursor:
        lda $a2
        and #$10
        beq cursor_want_off
        lda cursor_phase
        bne update_cursor_done   ; already on
        jsr cursor_show
        rts
cursor_want_off:
        lda cursor_phase
        beq update_cursor_done   ; already off
        jsr cursor_hide
update_cursor_done:
        rts

; Draw a reverse-video block at the cursor position, then step back onto
; it (CRSR LEFT) so the next real CHROUT overwrites it cleanly.
cursor_show:
        lda #1
        sta cursor_phase
        lda #$12                 ; reverse on
        jsr CHROUT
        lda #$20                 ; space -- a solid block in reverse video
        jsr CHROUT
        lda #$92                 ; reverse off
        jsr CHROUT
        lda #$9d                 ; cursor left
        jsr CHROUT
        rts

; Overwrite the block with a plain space and step back, leaving the
; screen cursor position unchanged. Also used (unconditionally) to make
; sure no stray block is left behind right before a real keystroke is
; handled -- safe even when nothing is currently drawn, since that cell
; is otherwise blank anyway.
cursor_hide:
        lda #0
        sta cursor_phase
        lda #$20
        jsr CHROUT
        lda #$9d                 ; cursor left
        jsr CHROUT
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
read_line_loop:
        ; .a = ?
        ; .x = index into linebuf (also stored in linelen)
        ; .y = length of input

;       stx x_save
        sty y_save
        jsr update_cursor        ; blink the cursor while waiting for a key
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

        cmp #$0d                 ; RETURN?
        beq read_line_done

        cmp #$14                 ; DEL (PETSCII backspace)?
        bne read_line_store
        lda linelen              ; the dispatch path no longer relies on X
        beq read_line_loop       ; surviving CHROUT calls -- linelen (a
        dec linelen              ; plain memory byte) is the source of truth
        jsr CHROUT               ; KERNAL moves cursor back on screen
        jmp read_line_loop

read_line_store:
        ldx linelen
        cpx #MAX_LINE-1
        bcs read_line_loop       ; buffer full, ignore further chars
        sta linebuf,x            ; 0-based: store first, then advance --
        inx                      ; matches send_line, which still starts
        stx linelen              ; at index 0 and reads until the null
        jsr CHROUT               ; echo the typed char locally
        jmp read_line_loop

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

; --- Data ---

status_msg:
        ascii " TADA CLIENT {usedef:__BuildDate} - CONNECTING... "
        byte 0

linelen:
        byte 0
linebuf:
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0

nmi_orig:
        byte 0,0                ; saved KERNAL NMI vector, set by init_nmi

; 256-byte NMI receive ring buffer -- deliberately sized so rx_head/
; rx_tail (plain bytes) wrap around for free on overflow, no masking
; needed.
rx_buf:
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
