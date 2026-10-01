; --- disk.asm ---
; Serial-bus disk helpers shared by both clients: find out which drives
; are on the bus before touching one, and read a drive's command/error
; channel without hanging when nothing answers. Ryan's ask, 2026-09-30.
;
; {include:}d raw (no {const:}/{def:} of its own, so no _pp.asm pass --
; same as input_editor.asm) by tada-client.asm, by keymap_menu.asm (a
; separate standalone .prg, so it carries its own copy) and by
; client-128.asm. Constants are plain `=` with a DSK_ prefix so they
; can't collide with the KERNAL_* symbols tada-client.asm already
; defines. Every KERNAL entry used here is at the same address on the
; C64 and the 128, and nothing below keeps a value in .X/.Y across a
; KERNAL call (the 128's KERNAL is freer with them than the C64's --
; see keymap_128.asm's GETIN history), so the one source serves both.
;
; Routines:
;   current_drive_to_x -- .X = the drive the client came from ($ba)
;   probe_device       -- is device .X on the bus?
;   scan_serial_bus    -- which of devices 8-30 are on the bus?
;   select_drive       -- the drive to use next, or carry set = none
;   read_error_channel -- the drive's status: code in .A, text in
;                         drive_status_buf

DSK_STATUS  = $90       ; KERNAL ST (READST's byte) -- bit 7 = device
                        ; not present, bit 6 = EOI, bits 0-1 = timeout
DSK_FA      = $ba       ; KERNAL FA: the last device SETLFS was given --
                        ; after LOAD"TADA-CLIENT",9 still 9 once this
                        ; program is running
DSK_SECOND  = $ff93     ; secondary address after LISTEN
DSK_CIOUT   = $ffa8     ; byte to the listener (buffered one deep)
DSK_UNLSN   = $ffae
DSK_LISTEN  = $ffb1
DSK_READST  = $ffb7
DSK_SETLFS  = $ffba
DSK_SETNAM  = $ffbd
DSK_OPEN    = $ffc0
DSK_CLOSE   = $ffc3
DSK_CHKIN   = $ffc6
DSK_CLRCHN  = $ffcc
DSK_CHRIN   = $ffcf

DSK_FIRST_DRIVE = 8     ; 0-7 are keyboard/tape/RS-232/screen/printers
DSK_LAST_DRIVE  = 30    ; the highest serial device number the KERNAL
                        ; can address (31 is the "no secondary" marker)
DSK_MAX_DRIVES  = 23    ; DSK_LAST_DRIVE - DSK_FIRST_DRIVE + 1, by hand
DSK_CMD_CHANNEL = 15
DSK_PROBE_CHANNEL = 14  ; probe_device's -- never opened by either client
DSK_STATUS_MAX  = 48    ; drive_status_buf's text capacity -- the
                        ; longest stock message ("73,CBM DOS V2.6
                        ; 1541,00,00") is 26 bytes; sd2iec's power-on
                        ; message runs longer and is truncated
DOS_NO_DEVICE   = $ff   ; read_error_channel's code when nothing
                        ; answered (DOS codes themselves are 00-79)

; --- current_drive_to_x: .X = the drive to use for disk I/O ---
; DSK_FA, or 8 if that's below 8 (the client was started some way that
; never touched a drive), so nothing is ever aimed at a non-disk
; device. Clobbers .A -- call it BEFORE loading .A with a file number.
; Moved here from tada-client.asm (and keymap_menu.asm's own copy) so
; both clients and the overlay share one version.
current_drive_to_x:
        lda DSK_FA
        cmp #DSK_FIRST_DRIVE
        bcs current_drive_ok
        lda #DSK_FIRST_DRIVE
current_drive_ok:
        tax
        rts

; --- probe_device: .X = device number. Carry clear if a device with
; that number is on the serial bus, carry set if not. ---
; Nothing obvious works here, going by the KERNAL ROM itself
; (901227-03, disassembled 2026-09-30):
;   - OPEN with no filename never touches the bus, so it "succeeds"
;     for any device number.
;   - Anything that makes the device TALK (CHKIN, TKSA) waits at
;     $EDD6 -- a bare `jsr $eea9 / bmi $edd6` with interrupts off --
;     for the talker to pull CLK, forever if there is no talker. That
;     is how the old read_error_channel could hang.
;   - LISTEN/SECOND/UNLSN and checking ST (the usual recipe) only
;     catches an EMPTY bus: every device acks every byte sent under
;     ATN, addressed or not, so drive 8 happily acks "LISTEN 9".
;   - Reading the DATA line by hand after SECOND (what $ED41-$ED47 do
;     at the start of the next byte) works with the stock KERNAL but
;     not JiffyDOS's -- tried and seen failing in VICE 2026-09-30: its
;     own handshake leaves the lines differently.
; So this sends real bytes after ATN is released and lets whichever
; KERNAL is running make its own ?DEVICE NOT PRESENT call on them (the
; stock one at $ED44, JiffyDOS's and the 128's in theirs). What gets
; sent has to be something every drive listens to AND that leaves it
; quiet -- both found out the hard way in VICE, 2026-09-30:
;   - a byte on a channel that isn't open: a stock-protocol 1541 doesn't
;     listen, so the KERNAL calls it absent (and the 128's KERNAL hung
;     at $E3A9 waiting for an EOI ack from a 1571 that never came)
;   - a lone CR on the command channel: detected fine, but the drive
;     answers 31,SYNTAX ERROR and blinks its error LED
; So: OPEN 14,<dev>,14,"#" / CLOSE 14 done by hand -- allocate a
; direct-access buffer and free it again, which every CBM-DOS drive
; does in its own RAM without touching the disk (no motor, works with
; no disk in), leaving its status at 00, OK. Nothing in either client
; ever opens channel 14. The one side effect: whatever status message
; the drive was holding (a previous error, or the 73 power-on message)
; is replaced by 00 -- fine, since the clients probe right before their
; own LOAD/SAVE, which replaces it anyway. It's also why
; read_error_channel doesn't probe a drive this already found (see
; dsk_verified): probing first wiped the very error it went to read
; (a SAVE to a full disk read back as 00, OK -- x128, 2026-09-30).
; Out: carry clear = present (and dsk_verified = .X's device), carry
; set = absent.
probe_device:
        stx dsk_probe_dev
        lda #0
        sta DSK_STATUS
        txa
        jsr DSK_LISTEN
        lda #($f0|DSK_PROBE_CHANNEL) ; $Fx: OPEN channel x
        jsr DSK_SECOND
        lda DSK_STATUS
        bmi probe_device_unlisten   ; nobody on the bus at all
        lda #$23                    ; '#' (raw, so no {alpha:} mode can remap it)
        jsr DSK_CIOUT               ; buffered -- UNLSN sends it (with
                                    ; EOI), and that's where "not
                                    ; present" gets noticed
probe_device_unlisten:
        jsr DSK_UNLSN
        lda DSK_STATUS
        sta dsk_st
        bmi probe_device_done       ; absent: nothing was opened
        lda dsk_probe_dev           ; present: CLOSE 14 again
        jsr DSK_LISTEN
        lda #($e0|DSK_PROBE_CHANNEL) ; $Ex: CLOSE channel x
        jsr DSK_SECOND
        jsr DSK_UNLSN
probe_device_done:
        lda #0                      ; leave ST clean for whoever's next
        sta DSK_STATUS
        lda dsk_st
        bmi probe_device_forget
        lda dsk_probe_dev           ; answered: read_error_channel may
        sta dsk_verified            ; talk to it without probing again
        clc
        rts
probe_device_forget:
        lda dsk_probe_dev           ; absent: if it was the verified one,
        cmp dsk_verified            ; it isn't any more
        bne probe_device_absent
        lda #0
        sta dsk_verified
probe_device_absent:
        sec
        rts

; --- scan_serial_bus: probe devices 8-30 ---
; drive_list = the device numbers that answered, lowest first;
; drive_count (also returned in .A, Z set when it's 0) = how many.
; An absent device costs a millisecond or two, so the whole scan is
; well under a tenth of a second.
scan_serial_bus:
        lda #0
        sta drive_count
        lda #DSK_FIRST_DRIVE
        sta dsk_device
scan_serial_bus_loop:
        ldx dsk_device
        jsr probe_device
        bcs scan_serial_bus_next
        ldx drive_count
        lda dsk_device
        sta drive_list,x
        inc drive_count
scan_serial_bus_next:
        inc dsk_device
        lda dsk_device
        cmp #(DSK_LAST_DRIVE+1)
        bne scan_serial_bus_loop
        lda drive_count
        rts

; --- select_drive: pick the drive for the next LOAD/SAVE ---
; The drive the client came from if it's still on the bus; otherwise
; the lowest-numbered drive scan_serial_bus finds (it may have been
; switched off, or the client was started some way that never touched
; a drive). Either way the choice goes into DSK_FA too, so
; current_drive_to_x -- and everything that calls it -- agrees.
; Out: carry clear, .X = the drive. Carry set: no drive on the bus at
; all -- the caller aborts its LOAD/SAVE rather than attempt it.
select_drive:
        jsr current_drive_to_x
        stx dsk_device
        jsr probe_device
        bcc select_drive_use
        jsr scan_serial_bus
        beq select_drive_none
        lda drive_list              ; lowest-numbered drive found
        sta dsk_device
select_drive_use:
        lda dsk_device
        sta DSK_FA
        tax
        clc
        rts
select_drive_none:
        sec
        rts

; --- read_error_channel: read the current drive's status message ---
; OPEN 15,<drive>,15 / read to EOI / CLOSE 15. Reading it is also what
; turns off a real 1541's blinking error LED, which is why every
; LOAD/SAVE here calls this afterward even when it doesn't care about
; the answer.
; Out: .A = the DOS code (00 OK, 01 FILES SCRATCHED, 20-79 errors,
;      73 the power-on message), or DOS_NO_DEVICE if the drive didn't
;      answer; also in drive_status_code.
; Never TALKs to a device that isn't there (that hangs -- see
; probe_device): ST bit 7 left by the LOAD/SAVE just before means it
; wasn't, and a drive other than the one select_drive/probe_device last
; found gets probed first. The one it did find is read without a probe,
; so its status survives to be read -- call this right after the
; LOAD/SAVE it's reporting on, before anything else touches the bus.
;      Carry set if .A >= 20 (an error, or no device), clear if not.
;      drive_status_buf = the message text, e.g. "26,WRITE PROTECT
;      ON,00,00", NUL-terminated, the trailing CR dropped. The drive
;      sends PETSCII: digits, comma and space are the same bytes as
;      screen codes, and its uppercase letters poke straight in as
;      uppercase glyphs in the lowercase charset.
read_error_channel:
        lda #0
        sta drive_status_len
        sta drive_status_buf
        lda #DOS_NO_DEVICE
        sta drive_status_code
        lda DSK_STATUS              ; the LOAD/SAVE this follows found
        bpl read_error_channel_ask  ; nobody there: don't TALK to it --
        jmp read_error_channel_done ; jmp, not bmi: the done label is 135
                                    ; bytes on, out of branch range, and
                                    ; c64list assembled the bmi silently
                                    ; as a branch into its own operand
                                    ; (check_branch_targets.py, 2026-10-01)
read_error_channel_ask:
        jsr current_drive_to_x
        cpx dsk_verified            ; select_drive/probe_device just found
        beq read_error_channel_open ; it: no probe (it'd reset the status)
        jsr probe_device            ; anything else: make sure first --
        bcs read_error_channel_done ; TALKing to nobody hangs
read_error_channel_open:
        lda #0                      ; no filename -- the command channel
        jsr DSK_SETNAM              ; takes none
        jsr current_drive_to_x
        lda #DSK_CMD_CHANNEL
        ldy #DSK_CMD_CHANNEL
        jsr DSK_SETLFS
        jsr DSK_OPEN
        bcs read_error_channel_done ; e.g. file 15 already open: leave
                                    ; whoever owns it alone (that's how
                                    ; key_save's never-closed SCRATCH
                                    ; file 15 turned up, 2026-09-30)
        ldx #DSK_CMD_CHANNEL
        jsr DSK_CHKIN
        bcs read_error_channel_close
        lda #0
        sta DSK_STATUS
read_error_channel_loop:
        jsr DSK_CHRIN
        sta dsk_char
        jsr DSK_READST
        sta dsk_st
        lda dsk_char
        cmp #$0d
        beq read_error_channel_next
        ldx drive_status_len
        cpx #DSK_STATUS_MAX
        bcs read_error_channel_next ; full: keep reading to EOI anyway
        sta drive_status_buf,x
        inc drive_status_len
read_error_channel_next:
        lda dsk_st
        beq read_error_channel_loop ; EOI ends the message; so does a
                                    ; timeout (the drive went away
                                    ; mid-message) -- any bit at all
        ldx drive_status_len
        lda #0
        sta drive_status_buf,x
        ; Two leading digits -> binary. Anything else leaves
        ; DOS_NO_DEVICE: whatever answered isn't talking CBM DOS.
        cpx #2
        bcc read_error_channel_close
        lda drive_status_buf+1
        jsr dsk_digit
        bcs read_error_channel_close
        sta dsk_char                ; ones
        lda drive_status_buf
        jsr dsk_digit
        bcs read_error_channel_close
        asl                         ; tens * 10 = tens*8 + tens*2
        sta dsk_st
        asl
        asl
        adc dsk_st                  ; carry clear: tens <= 9
        adc dsk_char
        sta drive_status_code
read_error_channel_close:
        jsr DSK_CLRCHN
        lda #DSK_CMD_CHANNEL
        jsr DSK_CLOSE
read_error_channel_done:
        lda drive_status_code
        cmp #20                     ; carry set = error (or no device)
        rts

; .A = a PETSCII digit -> .A = its value, carry clear; carry set if
; .A isn't a digit.
dsk_digit:
        sec
        sbc #$30                    ; '0'
        cmp #10                     ; carry set if it wasn't '0'-'9'
        rts

drive_count:        byte 0
drive_list:         area DSK_MAX_DRIVES, 0
drive_status_code:  byte DOS_NO_DEVICE
drive_status_len:   byte 0
drive_status_buf:   area (DSK_STATUS_MAX+1), 0
dsk_device:         byte 0
dsk_char:           byte 0
dsk_st:             byte 0
dsk_probe_dev:      byte 0
dsk_verified:       byte 0    ; the device probe_device last found
                              ; (0 = none -- not a drive number)
