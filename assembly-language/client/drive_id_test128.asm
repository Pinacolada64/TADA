; drive_id_test.asm -- standalone harness for drive_id.asm, run by
; vice_drive_id_test.py under x64sc/x128 true drive emulation (same
; shape as disk_test.asm). Builds for the C64 by default, for the 128
; with -def:c128. Runs identify_drive on devices 8-11, keeping each
; one's drive_model text and carry, then parks for the monitor.

{ifdef: c128}
        orig $1c01
        byte $0d,$1c,$0a,$00,$9e,$37,$31,$38,$31,$00,$00,$00   ; 10 SYS7181
{endif}
{ifndef: c128}
        orig $0801
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00   ; 10 SYS2061
{endif}

start:
        lda #8                       ; "the client's drive" -- identify_
        sta DSK_FA                   ; drive must leave it alone
        sta t_dev
        lda #0
        sta t_out
t_loop:
        lda t_dev
        sta t_progress
        ldx t_dev
        jsr identify_drive
        lda #0
        rol
        ldx t_dev
        sta t_carry-8,x
        ldx t_out                    ; copy drive_model (5 bytes)
        ldy #0
t_copy:
        lda drive_model,y
        sta t_models,x
        inx
        iny
        cpy #(DID_MODEL_LEN+1)
        bne t_copy
        stx t_out
        inc t_dev
        lda t_dev
        cmp #12
        bne t_loop

        lda DSK_FA
        sta t_fa
        lda #$ff
        sta t_progress
t_park:
        jmp t_park

{include:disk.asm}
{include:drive_id.asm}

t_progress:     byte 0
t_dev:          byte 0
t_out:          byte 0
t_fa:           byte $ee
t_carry:        byte $ee, $ee, $ee, $ee
t_models:       area 20, $ee
