; drive_menu_test.asm -- stand-in for the resident client, so
; vice_drive_menu_test.py can run the drive_menu.prg overlay on its
; own: fills constants.asm's jump table with stubs, selects the
; lowercase charset, clears the screen and jumps to OVERLAY_BUF ($3800,
; where the monitor loaded drive_menu.prg). JT_BUILD_STATUS_LINE keeps
; the status message pointer; JT_RESUME_LOCAL marks t_done and parks.
; KEYMAP_TABLE_PTR/CONFIG_SETTINGS_PTR point at t_config, a stand-in for
; keymap.asm's keymap_table + config_settings (what drive_menu.asm saves
; as TADA64.CFG). Running start again reopens the popup with t_config
; as the last run left it.
{include:constants.asm}

        orig $0801
        byte $0a,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00   ; 10 SYS2061

start:
        ldx #0
t_jt_copy:
        lda t_jt,x
        sta JT_BASE,x
        inx
        cpx #(T_JT_END)
        bne t_jt_copy
        ; The client's screen: VIC bank 3, screen at $c400 (POPUP_SCREEN),
        ; charset at $d000 -- here the ROM's lowercase set copied into
        ; the RAM under $d000 (the client copies its gothic one there)
        sei
        lda #$33                  ; character ROM in at $d000 for reads;
        sta $01                   ; writes land in the RAM underneath
        ldx #0
t_font:
        lda $d800,x               ; ROM's second (upper/lowercase) set
        sta $d000,x
        lda $d900,x
        sta $d100,x
        lda $da00,x
        sta $d200,x
        lda $db00,x
        sta $d300,x
        lda $dc00,x
        sta $d400,x
        lda $dd00,x
        sta $d500,x
        lda $de00,x
        sta $d600,x
        lda $df00,x
        sta $d700,x
        inx
        bne t_font
        lda #$37
        sta $01
        cli
        lda $dd00
        and #%11111100            ; VIC bank 3
        sta $dd00
        lda #$14                  ; screen $c400, charset $d000
        sta $d018
        lda #$c4                  ; KERNAL screen (HIBASE) there too
        sta $0288
        lda #$93                  ; CLR
        jsr $ffd2
        lda #<t_config
        sta KEYMAP_TABLE_PTR
        lda #>t_config
        sta KEYMAP_TABLE_PTR+1
        lda #<(t_config+432)      ; config_settings follows the table
        sta CONFIG_SETTINGS_PTR
        lda #>(t_config+432)
        sta CONFIG_SETTINGS_PTR+1
        lda #0
        sta t_done
        lda #8                    ; booted from drive 8
        sta $ba
        jmp $3800

t_rts:
        rts
t_status:
        stx t_msg
        sty t_msg+1
        rts
t_resume:
        lda #$ff
        sta t_done
t_park:
        jmp t_park

; $c000-$c022: every jump-table slot up to JT_BUILD_STATUS_LINE, as
; `jmp` entries (PROTO_TABLE's bytes in the middle are filler here)
t_jt:
        jmp t_rts                 ; $c000 JT_SL_SEND
        jmp t_rts                 ; $c003 JT_SL_RECV
        jmp t_resume              ; $c006 JT_RESUME
        jmp t_rts                 ; $c009 JT_SAVE_SCREEN
        jmp t_rts                 ; $c00c JT_RESTORE_SCREEN
        jmp t_rts                 ; $c00f JT_SET_BLINK_MASK
        byte 0,0,0,0,0,0,0,0      ; $c012-$c019 PROTO_TABLE
        jmp t_resume              ; $c01a JT_RESUME_LOCAL
        jmp t_rts                 ; $c01d JT_STATUS_PUSH_RESET
        jmp t_status              ; $c020 JT_BUILD_STATUS_LINE
T_JT_END = * - t_jt

t_done:         byte 0
t_msg:          word 0
t_config:       area 432, $5a     ; "keymap_table" -- recognizable fill
                byte CONFIG_VERSION, 0
                area 6, 0
