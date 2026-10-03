; keymap_128.asm -- client-128.asm's resident keymap: the table, its
; defaults, TADA128.CFG loading, and the per-key dispatch into
; input_editor.asm. The 128 counterpart of the C64 client's keymap.asm;
; the popup that edits the table is keymap_menu_128.asm (see
; keymap_host_128.asm). Its own file since 2026-09-29 -- the C64 client
; keeps TADA64.CFG.
;
; Table format: keymap.asm's 27-byte slots (modifier, key, action, 24
; bytes of macro text), 17 of them: 0-5 the nav functions, 6-14 macros,
; 15-16 Page Up/Page Down for the 80-column scrollback. Modifier bits:
; SHIFT 1, C= 2, CTRL 4, ALT 8 ($d3). Nav keys are GETIN bytes; macro
; triggers and the page keys are matrix key numbers ($d4), which is what
; tells the grey top-row arrows (83/84) from the main CRSR key.
;
; The format constants (MAX_BINDINGS, BINDING_SIZE, MOD_*, ACTION_*,
; KEYMAP_TABLE_SIZE, PAGE_SLOT_FIRST) come from keymap_menu_128.asm,
; which client-128.asm includes ahead of this file.

KM_SETNAM          = $ffbd       ; KERNAL (keymap_menu.asm's own {const:}s
KM_SETLFS          = $ffba       ; for these don't reach this file)
KM_LOAD            = $ffd5
KM_BINDING_MACRO   = 3           ; macro text's offset in a binding
KM_SUBMIT_CHAR     = $5f         ; back-arrow in macro text = press RETURN

; The table keymap_menu.asm edits and key_save writes out. Zero fill is
; ACTION_EMPTY.
keymap_table:
        area KEYMAP_TABLE_SIZE, $00

; Client settings, saved in TADA128.CFG right after keymap_table -- see
; keymap.asm's config_settings (same layout, constants_128.asm's CFG_*
; offsets). key_save (keymap_menu_128.asm) writes through the end of it.
config_settings:
        byte CONFIG_VERSION          ; CFG_VERSION
        byte 0                       ; CFG_DATA_DRIVE: none chosen yet
        area (CONFIG_SETTINGS_SIZE-2), 0

; keymap_menu.asm reads the table's address from here (on the C64 it's a
; pointer at $c032 the resident client fills in, since the overlay can't
; see keymap.asm's symbols; built in here, it can -- this just keeps the
; popup source unchanged).
KEYMAP_TABLE_PTR:
        word keymap_table

; Same for the settings block, for drive_menu.asm (built in here too;
; on the C64 a pointer at $c034 that init_keymap fills in).
CONFIG_SETTINGS_PTR:
        word config_settings

; Slots 0-6: copied from keymap.asm's keymap_default -- see its comments
; for each entry's history. On the 128, plain CRSR UP/DOWN (Home/End)
; only reach the keymap in 40 columns; in 80 they scroll back through
; the dialogue a line at a time (editor_key_hook). CLR/HOME still gives
; Home there.
KEYMAP_DEFAULT_BINDINGS = 7
KEYMAP_DEFAULT_SIZE     = 189    ; BINDING_SIZE(27) * 7, by hand (see
                                 ; keymap.asm on c64list truncating
                                 ; computed products)
keymap_default:
        byte MOD_CTRL, $1d, ACTION_WORD_LEFT
        area MACRO_TEXT_LEN, $20
        byte MOD_CTRL, $11, ACTION_WORD_RIGHT
        area MACRO_TEXT_LEN, $20
        byte 0, $91, ACTION_HOME
        area MACRO_TEXT_LEN, $20
        byte 0, $13, ACTION_HOME
        area MACRO_TEXT_LEN, $20
        byte 0, $11, ACTION_END
        area MACRO_TEXT_LEN, $20
        byte 0, $88, ACTION_OPEN_EDITOR   ; F7 (km_init_keyboard makes
        area MACRO_TEXT_LEN, $20           ; the 128's F7 send $88)
        byte 0, $87, ACTION_OPEN_DRIVES   ; F5 ($87, likewise)
        area MACRO_TEXT_LEN, $20

; Slots 16-17: ALT + the grey top-row CRSR UP/DOWN keys (key numbers
; 83/84 -- the 128 KERNAL's decode tables, $FA80+83) page the scrollback.
KEYMAP_PAGE_DEFAULT_SIZE = 54    ; 2 * BINDING_SIZE, by hand
keymap_page_default:
        byte MOD_ALT, 83, ACTION_PAGE_UP
        area MACRO_TEXT_LEN, $20
        byte MOD_ALT, 84, ACTION_PAGE_DOWN
        area MACRO_TEXT_LEN, $20
KM_PAGE_SLOT_OFFSET = 432        ; PAGE_SLOT_FIRST(16) * BINDING_SIZE(27)

; --- init_keymap: LOAD "TADA128.CFG" from the drive the client came from
; (secondary address 0: into keymap_table, whatever the file's header
; says -- see keymap.asm's init_keymap), or copy the defaults in. ---
init_keymap:
        jsr select_drive            ; disk.asm -- no drive on the bus at
        bcc init_keymap_have_drive  ; all: defaults, and no LOAD or error
        lda #5                      ; channel (5 = DEVICE NOT PRESENT,
        sta km_load_error           ; what LOAD itself would have said)
        jmp init_keymap_default_start
init_keymap_have_drive:
        lda #11                     ; length of "TADA128.CFG"
        ldx #<km_cfg_filename
        ldy #>km_cfg_filename
        jsr KM_SETNAM
        lda #0                      ; 128: data and filename both in bank 0
        ldx #0                      ; (SETBNK -- the C64 has no banks)
        jsr SETBNK
        jsr current_drive_to_x      ; disk.asm; select_drive's pick
        lda #2
        ldy #0
        jsr KM_SETLFS
        lda #0                      ; load, not verify
        ldx #<keymap_table
        ldy #>keymap_table
        jsr KM_LOAD
        bcc init_keymap_loaded
        sta km_load_error
init_keymap_default_start:
        ldx #0
init_keymap_default:
        lda keymap_default,x
        sta keymap_table,x
        inx
        cpx #KEYMAP_DEFAULT_SIZE
        bne init_keymap_default
        ldx #0
init_keymap_page_default:
        lda keymap_page_default,x
        sta keymap_table+KM_PAGE_SLOT_OFFSET,x
        inx
        cpx #KEYMAP_PAGE_DEFAULT_SIZE
        bne init_keymap_page_default
        lda km_load_error
        cmp #5                      ; DEVICE NOT PRESENT: no error channel
        beq init_keymap_rts         ; to read either
init_keymap_loaded:
        jsr config_validate         ; the settings block came in too
        jmp read_error_channel      ; disk.asm's -- turns the drive's
                                    ; error LED off (see keymap.asm)
init_keymap_rts:
        rts

; --- config_validate: a data drive outside 8-30 goes back to 0 ("none
; chosen"), and the version byte is restamped -- see keymap.asm's. ---
config_validate:
        lda config_settings+CFG_DATA_DRIVE
        beq config_validate_version
        cmp #8                      ; disk.asm's DSK_FIRST_DRIVE..
        bcc config_validate_clear   ; DSK_LAST_DRIVE, as literals: disk.asm
        cmp #31                     ; is {include:}d after this file
        bcc config_validate_version
config_validate_clear:
        lda #0
        sta config_settings+CFG_DATA_DRIVE
config_validate_version:
        lda #CONFIG_VERSION
        sta config_settings+CFG_VERSION
        rts

{alpha:alt}
km_cfg_filename:
        ascii "TADA128.CFG"
{alpha:normal}

; --- km_dispatch: .A = a key from input_editor.asm (via editor_key_hook).
; Carry set: handled (the editor redraws its line). Carry clear: .A is
; the key the editor should handle itself -- the key unchanged, or $0d
; when a macro ends in the back-arrow submit marker. Same matching rules
; as keymap.asm's keymap_dispatch: nav slots match the GETIN byte (SHIFT
; ignored for $91/$9d, which are SHIFT+CRSR already), macro and page
; slots match the matrix key number (SFDX); the modifier (ALT included)
; must match exactly. ---
km_dispatch:
        sta km_key
        lda #0
        sta km_paged                ; set by the Page Up/Down actions
        lda KM_SHFLAG
        and #KM_MOD_MASK
        sta km_mods                 ; for macro/page triggers
        sta km_nav_mods             ; for nav keys, SHIFT-masked below
        lda km_key
        cmp #$91
        beq km_mask_shift
        cmp #$9d
        bne km_scan
km_mask_shift:
        lda km_nav_mods
        and #(MOD_CMDRE|MOD_CTRL|MOD_ALT)
        sta km_nav_mods
km_scan:
        lda #<keymap_table
        sta km_slot
        lda #>keymap_table
        sta km_slot+1
        lda #MAX_BINDINGS
        sta km_slots_left
km_scan_loop:
        jsr km_aim                  ; km_rd -> this slot
        ldy #2
        jsr km_rd
        beq km_scan_next            ; ACTION_EMPTY
        cmp #ACTION_PAGE_UP
        bcs km_scan_macro           ; page keys and macros: matrix number
        ldy #1
        jsr km_rd
        cmp km_key
        bne km_scan_next
        ldy #0
        jsr km_rd
        cmp km_nav_mods
        bne km_scan_next
        jmp km_run
km_scan_macro:
        ldy #1
        jsr km_rd
        cmp KM_SFDX
        bne km_scan_next
        ldy #0
        jsr km_rd
        cmp km_mods
        bne km_scan_next
        jmp km_run
km_scan_next:
        clc
        lda km_slot
        adc #BINDING_SIZE
        sta km_slot
        bcc km_scan_no_carry
        inc km_slot+1
km_scan_no_carry:
        dec km_slots_left
        bne km_scan_loop
        lda km_key                  ; no binding: the editor's key
        clc
        rts

; km_aim: point km_rd's operand at km_slot. km_rd: .Y = offset -> .A
; (Z/N from the load).
km_aim:
        lda km_slot
        sta km_rd_load+1
        lda km_slot+1
        sta km_rd_load+2
        rts
km_rd:
km_rd_load:
        lda $ffff,y
        rts

; --- km_run: the matched slot's action (km_rd still aimed at it). ---
km_run:
        ldy #2
        jsr km_rd
        cmp #ACTION_WORD_LEFT
        bne km_run_2
        jsr prev_word
        sec
        rts
km_run_2:
        cmp #ACTION_WORD_RIGHT
        bne km_run_3
        jsr next_word
        sec
        rts
km_run_3:
        cmp #ACTION_HOME
        bne km_run_4
        jsr home
        sec
        rts
km_run_4:
        cmp #ACTION_END
        bne km_run_5
        jsr km_end
        sec
        rts
km_run_5:
        cmp #ACTION_OPEN_EDITOR
        bne km_run_5b
        jmp module_start            ; keymap_menu.asm; leaves through
                                    ; JT_RESUME_LOCAL, never returns here
km_run_5b:
        cmp #ACTION_OPEN_DRIVES
        bne km_run_6
        jmp dm_module_start         ; drive_menu.asm, the same way
km_run_6:
        cmp #ACTION_PAGE_UP
        bne km_run_7
        jsr sb_page_back_any        ; either screen (40 columns since
        inc km_paged
        sec
        rts
km_run_7:
        cmp #ACTION_PAGE_DOWN
        bne km_run_8
        jsr sb_page_fwd_any         ; 2026-10-01, vic_screen.asm)
        inc km_paged
        sec
        rts
km_run_8:
        cmp #ACTION_MACRO
        bne km_run_done             ; unknown action: swallow the key,
        jsr km_insert_macro         ; same as keymap.asm
        lda km_submit
        beq km_run_done
        lda #13                     ; back-arrow: the editor gets a RETURN
        clc
        rts
km_run_done:
        sec
        rts

; --- km_end: cursor to the end of the line (input_editor.asm has no End
; of its own). cright moves one character and slides the view. ---
km_end:
        ldy cpos
        lda (strptr),y
        beq km_end_rts
        jsr cright
        jmp km_end
km_end_rts:
        rts

; --- km_insert_macro: type the slot's macro text into the input line at
; the cursor, a character at a time through the editor's own insert/
; cright (so it slides and stops at maxlen exactly like typing would).
; A back-arrow stops it and sets km_submit. ---
km_insert_macro:
        lda #0
        sta km_submit
        lda #KM_BINDING_MACRO
        sta km_macro_i
km_macro_loop:
        ldy km_macro_i
        cpy #BINDING_SIZE
        beq km_macro_done
        jsr km_rd
        beq km_macro_done           ; NUL terminator
        cmp #KM_SUBMIT_CHAR
        bne km_macro_char
        lda #1
        sta km_submit
        rts
km_macro_char:
        sta km_macro_ch
        lda strlen
        cmp maxlen
        bcs km_macro_done           ; line full: drop the rest
        jsr insert                  ; opens a space at cpos
        ldy cpos
        lda km_macro_ch
        sta (strptr),y
        jsr cright
        inc km_macro_i
        jmp km_macro_loop
km_macro_done:
        rts

km_key:         byte 0
km_mods:        byte 0
km_nav_mods:    byte 0
km_slot:        word 0
km_slots_left:  byte 0
km_submit:      byte 0
km_macro_i:     byte 0
km_macro_ch:    byte 0
km_load_error:  byte 0
km_paged:       byte 0        ; this key paged the scrollback
