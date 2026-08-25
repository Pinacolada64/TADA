; swiftlink.asm -- SwiftLink/Turbo-232 ACIA transport: init, NMI-driven
; receive buffering, and send/recv primitives. Split out of
; tada-client.asm (2026-08-24) once that file got long enough that
; finding the transport layer amid screen/keyboard/SID code was getting
; hard -- pure code reorganization, no behavior change (verified via a
; byte-identical assembled .prg before/after the split).
;
; Depends on tada-client.asm's own declarations (referenced by name,
; resolved globally across {include:}s the same way constants.asm's
; JT_*/PROTO_* addresses are -- see that file's header comment):
; rx_head/rx_tail (zero page), rts_state, nmi_orig, RX_HIGH_WATER/
; RX_LOW_WATER, and the rx_buf data buffer. None of that moved here --
; only the routines that operate on it -- so this file has no data
; section of its own.
;
; The SL_* register/command constants below DID move here (not just
; referenced from tada-client.asm) -- they used to be {const:}s there,
; but {const:} is macro_preprocessor.py's own textual substitution,
; resolved only within the file it runs on. It doesn't carry across
; {include:}s the way a real c64list `NAME = value` symbol does (c64list
; itself resolves {include:} well after macro_preprocessor.py has
; already finished substituting {const:}s in the *including* file only),
; so a symbolic SL_COMMAND etc. referenced from this separately-included
; file would otherwise assemble as a genuinely undefined symbol. Plain
; `=` assignments, like constants.asm's, are real c64list symbols and do
; resolve globally -- confirmed via a byte-identical assembled .prg
; before/after this split, not just "it compiles now".

; SwiftLink ACIA registers
SL_DATA     = $de00      ; data register
SL_STATUS   = $de01      ; status register
SL_COMMAND  = $de02      ; command register
SL_CONTROL  = $de03      ; control register

; ACIA status bits
SL_RDRF     = $08        ; bit 3: receive data register full
SL_TDRE     = $10        ; bit 4: transmit data register empty

; ACIA command register values
SL_CMD_INIT    = $09     ; DTR low, RTS low, RxD IRQ on
SL_CMD_OFF     = $0b     ; RxD/TxD IRQs off, DTR low
SL_CMD_RTS_OFF = $01     ; DTR low, RTS *high* (deasserted) -- see
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
SL_CTRL_38K = $1f

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
