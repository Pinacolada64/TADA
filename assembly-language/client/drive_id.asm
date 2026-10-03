; --- drive_id.asm ---
; identify_drive: which model is device .X? Reads the model number
; straight out of the drive's own ROM with the DOS "M-R" (memory-read)
; command, for the drive picker (drive_menu.asm). Ryan's ask,
; 2026-10-01.
;
; Kept out of disk.asm for now (the drive-scan session still has that
; file open); depends on it for probe_device and the DSK_* KERNAL
; constants, so {include:} it after disk.asm. Raw {include:} like
; disk.asm -- no {const:}/{def:} of its own. Builds for the 128 when
; c128 is defined (client-128.asm defines it; disk_test.asm's harness
; takes -def:c128): the 128 KERNAL reads OPEN's filename bytes from
; the bank SETBNK names, and this OPEN carries the M-R command as its
; filename.
;
; Why M-R and not the 73 power-on message ("73,CBM DOS V2.6 1541,00,00")
; from a "UI"/"UJ" reset: probe_device (run before every TALK -- see its
; own comment for the hang this avoids) leaves the drive's status at
; 00, OK, so the 73 message is gone by the time anything could read it,
; and getting it back means resetting the drive -- a second or two per
; drive, open files lost, and a drive that's still mid-reset when the
; KERNAL makes it TALK can hang the KERNAL forever. M-R needs no reset,
; touches no disk and doesn't light the error LED.
;
; Where the model number lives, read straight out of the ROM images
; VICE uses (/usr/local/share/vice/DRIVES) and Ryan's JiffyDOS drive
; ROMs, 2026-10-01: it's the tail of the drive's own 73 message text,
; whose last character has bit 7 set (the DOS message table's end-of-
; string marker):
;   $E5BB  "CBM DOS V2.6 1541"        1541, 1541-II (stock), also
;          "CBM DOS V3.0 1571"        1570/1571/1571CR (V3.0/V3.1)
;          "...YDOS 5.0 1541"         JiffyDOS 1541/1541-II/1571: the
;                                     same message, 3 bytes shorter, so
;                                     its end is at $E5C7 not $E5CA
;   $A6DF  "CBM DOS V10 1581"         1581, stock and JiffyDOS 6.0
;          "IFFYDOS 6.0 1581"         (both end at $A6EE)
; So rather than a fixed address per model, identify_drive reads a
; 16-byte window ending at the stock message's last byte and takes the
; four characters ending at the first bit-7 byte (past index 2), as
; long as they're digits -- which also rejects whatever a different
; model happens to have at that address (a 1581 reads $FF at $E5BB-;
; a 1541 sees a ROM mirror at $A6DF). Not found by either window:
; JiffyDOS's SX-64 drive ROM (its $E5BB is code), anything non-CBM
; (sd2iec, CMD). CMD HD: a third window once Ryan has its boot ROM to
; read the address from.

DID_WINDOW_LEN = 16
DID_MODEL_LEN  = 4

; --- identify_drive: .X = device number ---
; Out: carry clear, drive_model = the four model digits ("1541",
; "1571", "1581", ...) NUL-terminated, PETSCII -- digits are the same
; bytes as screen codes. Carry set: device absent or not recognized,
; drive_model = "" (just the NUL).
; Probes the device first (probe_device), so it's safe on any number.
; Leaves DSK_FA as it found it: the M-R OPEN's SETLFS sets FA to the
; device being identified, and FA is how current_drive_to_x (so every
; later LOAD/SAVE) knows the client's drive -- seen in VICE 2026-10-01,
; a scan of 8-10 left FA at 10 and the next SAVE went to drive 10.
identify_drive:
        stx did_device
        lda DSK_FA
        sta did_saved_fa
        lda #0
        sta drive_model
        jsr probe_device
        bcs identify_drive_done      ; absent: carry already set
        lda #<$e5bb                  ; 1541/1570/1571, stock + JiffyDOS
        ldx #>$e5bb
        jsr did_check_window
        bcc identify_drive_done
        lda #<$a6df                  ; 1581, stock + JiffyDOS
        ldx #>$a6df
        jsr did_check_window
identify_drive_done:
        lda did_saved_fa             ; lda/sta leave the carry alone
        sta DSK_FA
        rts

; --- did_check_window: .A/.X = drive address (lo/hi) of a 16-byte
; window to read. Carry clear and drive_model filled in if a model
; number ends inside it; carry set if not. ---
did_check_window:
        jsr did_memory_read
        bcs did_check_window_no      ; didn't get all 16 bytes
        ldx #3                       ; need three characters before it
did_check_window_find:
        lda did_window,x
        bmi did_check_window_found
        inx
        cpx #DID_WINDOW_LEN
        bne did_check_window_find
did_check_window_no:
        lda #0
        sta drive_model
        sec
        rts
did_check_window_found:
        and #$7f                     ; the end-of-message marker bit
        sta drive_model+3
        lda did_window-1,x
        sta drive_model+2
        lda did_window-2,x
        sta drive_model+1
        lda did_window-3,x
        sta drive_model
        lda #0
        sta drive_model+DID_MODEL_LEN
        ldx #(DID_MODEL_LEN-1)
did_check_window_digits:
        lda drive_model,x
        jsr dsk_digit                ; disk.asm: carry set if not 0-9
        bcs did_check_window_no
        dex
        bpl did_check_window_digits
        clc
        rts

; --- did_memory_read: OPEN 15,<did_device>,15,"M-R"<lo><hi><16> and
; read the 16 bytes back into did_window. .A/.X = the address (lo/hi).
; Carry clear if all 16 arrived, set if not (OPEN/CHKIN failed, or the
; drive ended early -- older DOSes that ignore M-R's count byte send
; just one). The caller has already probed did_device, so the TALK
; that CHKIN starts has a talker. ---
did_memory_read:
        sta did_command+3
        stx did_command+4
        lda #0
        sta did_count
{ifdef: c128}
        lda #0                       ; 128: filename (and data) in bank 0
        ldx #0
        jsr $ff68                    ; SETBNK -- the C64 has no banks
{endif}
        lda #6                       ; "M-R" + lo + hi + count
        ldx #<did_command
        ldy #>did_command
        jsr DSK_SETNAM
        lda #DSK_CMD_CHANNEL
        ldx did_device
        ldy #DSK_CMD_CHANNEL
        jsr DSK_SETLFS
        jsr DSK_OPEN
        bcs did_memory_read_fail     ; e.g. file 15 already open
        ldx #DSK_CMD_CHANNEL
        jsr DSK_CHKIN
        bcs did_memory_read_close
        lda #0
        sta DSK_STATUS
did_memory_read_loop:
        jsr DSK_CHRIN
        ldx did_count
        sta did_window,x
        inc did_count
        jsr DSK_READST
        bne did_memory_read_close    ; EOI (or a timeout) ends it
        lda did_count
        cmp #DID_WINDOW_LEN
        bne did_memory_read_loop
did_memory_read_close:
        jsr DSK_CLRCHN
        lda #DSK_CMD_CHANNEL
        jsr DSK_CLOSE
        lda #0                       ; leave ST clean, as probe_device does
        sta DSK_STATUS
        lda did_count
        cmp #DID_WINDOW_LEN          ; carry set here if all 16 arrived --
        bcs did_memory_read_ok       ; the opposite of what we return
did_memory_read_fail:
        sec
        rts
did_memory_read_ok:
        clc
        rts

; "M-R" as the DOS reads it: unshifted PETSCII $4D,$2D,$52 (plain
; bytes rather than `ascii`, so no {alpha:} mode can change them),
; then the address and the byte count.
did_command:        byte $4d, $2d, $52, 0, 0, DID_WINDOW_LEN
did_window:         area DID_WINDOW_LEN, 0
drive_model:        area (DID_MODEL_LEN+1), 0
did_device:         byte 0
did_count:          byte 0
did_saved_fa:       byte 0
