; disk_test.asm -- standalone harness for disk.asm, run by
; vice_disk_test.py under x64sc/x128 true drive emulation. Builds for
; the C64 by default, for the 128 with -def:c128 (native-mode load
; address). Runs each routine once, writing t_progress before each step
; (so a hang shows which step it stuck in) and the results into the
; t_* bytes below, then parks in a loop for the monitor to read them.

{ifdef: c128}
        orig $1c01
        byte $0d,$1c,$0a,$00,$9e,$37,$31,$38,$31,$00,$00,$00   ; 10 SYS7181
{endif}
{ifndef: c128}
        orig $0801
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00   ; 10 SYS2061
{endif}

start:
        ; 1: probe_device on 8-11 -> t_probe (carry: 1 = absent)
        lda #1
        sta t_progress
        lda #8
        sta t_dev
t_probe_loop:
        ldx t_dev
        jsr probe_device
        lda #0
        rol
        ldx t_dev
        sta t_probe-8,x
        inc t_dev
        lda t_dev
        cmp #12
        bne t_probe_loop

        ; 2: provoke an error on drive 8 -- OPEN 15,8,15,"R0:A=B" (rename
        ; a file that isn't there: 62 FILE NOT FOUND) / CLOSE 15 -- then
        ; read_error_channel must hand back THAT, not a status its own
        ; probe reset -> t_rec8 code, t_rec8_buf text. select_drive
        ; first, the way the clients do before a LOAD/SAVE (it's what
        ; marks 8 as already found). With no drive 8, just the read.
        lda #2
        sta t_progress
        lda #8
        sta DSK_FA
        jsr select_drive
        bcs t_no_drive8
{ifdef: c128}
        lda #0                      ; SETBNK: filename in bank 0
        ldx #0
        jsr $ff68
{endif}
        lda #(t_rename_end-t_rename)
        ldx #<t_rename
        ldy #>t_rename
        jsr DSK_SETNAM
        lda #15
        ldx #8
        ldy #15
        jsr DSK_SETLFS
        jsr DSK_OPEN
        lda #15
        jsr DSK_CLOSE
t_no_drive8:
        lda #8
        sta DSK_FA
        jsr read_error_channel
        sta t_rec8
        ldx #0
t_copy8:
        lda drive_status_buf,x
        sta t_rec8_buf,x
        inx
        cpx #(DSK_STATUS_MAX+1)
        bne t_copy8

        ; 3: again -- reading it cleared it: "00, OK,00,00"
        lda #3
        sta t_progress
        jsr read_error_channel
        sta t_rec8b

        ; 4: read_error_channel on absent drive 9 -- must not hang
        lda #4
        sta t_progress
        lda #9
        sta DSK_FA
        jsr read_error_channel
        sta t_rec9
        lda #0
        rol
        sta t_rec9_c

        ; 5: scan_serial_bus -> t_count (drive_list read via symbols)
        lda #5
        sta t_progress
        jsr scan_serial_bus
        sta t_count

        ; 6: select_drive with FA = 9 -> falls back to the first drive
        lda #6
        sta t_progress
        lda #9
        sta DSK_FA
        jsr select_drive
        stx t_sel_x
        lda #0
        rol
        sta t_sel_c
        lda DSK_FA
        sta t_sel_fa

        lda #$ff
        sta t_progress
t_park:
        jmp t_park

{include:disk.asm}

; "R0:A=B" -- PETSCII uppercase (plain $41-$5A), raw bytes so no
; {alpha:} mode can touch them
t_rename:       byte $52, $30, $3a, $41, $3d, $42
t_rename_end:
t_progress:     byte 0
t_dev:          byte 0
t_probe:        byte $ee, $ee, $ee, $ee
t_rec8:         byte $ee
t_rec8b:        byte $ee
t_rec9:         byte $ee
t_rec9_c:       byte $ee
t_count:        byte $ee
t_sel_x:        byte $ee
t_sel_c:        byte $ee
t_sel_fa:       byte $ee
t_rec8_buf:     area (DSK_STATUS_MAX+1), 0
