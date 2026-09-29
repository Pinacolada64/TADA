; keymap_128.asm -- client-128.asm's resident keymap: the table, its
; defaults, KEYMAP.CFG loading, and the per-key dispatch into
; input_editor.asm. The 128 counterpart of the C64 client's keymap.asm
; (which is tied to tada-client.asm's read_line, so it isn't shared);
; the popup that edits the table, keymap_menu.asm, IS shared -- see
; keymap_host_128.asm.
;
; Same table format as keymap.asm, byte for byte (15 slots of modifier,
; key, action, 24 bytes of macro text), and the same file: a KEYMAP.CFG
; saved by either client loads in the other. Modifier bits are the same
; on both machines (SHIFT 1, C= 2, CTRL 4 -- the 128's ALT, bit 3, is
; masked off); nav keys are GETIN bytes and macro triggers are matrix key
; numbers, and both line up across the two keyboards for every key the
; C64 has.
;
; The format constants (MAX_BINDINGS, BINDING_SIZE, MOD_*, ACTION_*,
; KEYMAP_TABLE_SIZE) come from keymap_menu.asm, which client-128.asm
; includes ahead of this file.

KM_SETNAM          = $ffbd       ; KERNAL (keymap_menu.asm's own {const:}s
KM_SETLFS          = $ffba       ; for these don't reach this file)
KM_LOAD            = $ffd5
KM_BINDING_MACRO   = 3           ; macro text's offset in a binding
KM_SUBMIT_CHAR     = $5f         ; back-arrow in macro text = press RETURN

; The table keymap_menu.asm edits and key_save writes out. Zero fill is
; ACTION_EMPTY.
keymap_table:
        area KEYMAP_TABLE_SIZE, $00

; keymap_menu.asm reads the table's address from here (on the C64 it's a
; pointer at $c032 the resident client fills in, since the overlay can't
; see keymap.asm's symbols; built in here, it can -- this just keeps the
; popup source unchanged).
KEYMAP_TABLE_PTR:
        word keymap_table

; Copied from keymap.asm's keymap_default -- see its comments for each
; entry's history. On the 128, plain CRSR UP/DOWN (Home/End) only reach
; the keymap in 40 columns; in 80 they scroll back through the dialogue
; (editor_key_hook). CLR/HOME still gives Home there.
KEYMAP_DEFAULT_BINDINGS = 6
KEYMAP_DEFAULT_SIZE     = 162    ; BINDING_SIZE(27) * 6, by hand (see
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

; --- init_keymap: LOAD "KEYMAP.CFG" from the drive the client came from
; (secondary address 0: into keymap_table, whatever the file's header
; says -- see keymap.asm's init_keymap), or copy the defaults in. ---
init_keymap:
        lda #10
        ldx #<km_cfg_filename
        ldy #>km_cfg_filename
        jsr KM_SETNAM
        lda #0                      ; 128: data and filename both in bank 0
        ldx #0                      ; (SETBNK -- the C64 has no banks)
        jsr SETBNK
        jsr km_drive_to_x
        lda #2
        ldy #0
        jsr KM_SETLFS
        lda #0                      ; load, not verify
        ldx #<keymap_table
        ldy #>keymap_table
        jsr KM_LOAD
        bcc init_keymap_loaded
        sta km_load_error
        ldx #0
init_keymap_default:
        lda keymap_default,x
        sta keymap_table,x
        inx
        cpx #KEYMAP_DEFAULT_SIZE
        bne init_keymap_default
        lda km_load_error
        cmp #5                      ; DEVICE NOT PRESENT: no error channel
        beq init_keymap_rts         ; to read either
init_keymap_loaded:
        jmp read_error_channel      ; keymap_menu.asm's -- turns the drive's
                                    ; error LED off (see keymap.asm)
init_keymap_rts:
        rts

km_drive_to_x:
        lda $ba                     ; last device used (the client's drive)
        cmp #8
        bcs km_drive_ok
        lda #8
km_drive_ok:
        tax
        rts

{alpha:alt}
km_cfg_filename:
        ascii "KEYMAP.CFG"
{alpha:normal}

; --- km_dispatch: .A = a key from input_editor.asm (via editor_key_hook).
; Carry set: handled (the editor redraws its line). Carry clear: .A is
; the key the editor should handle itself -- the key unchanged, or $0d
; when a macro ends in the back-arrow submit marker. Same matching rules
; as keymap.asm's keymap_dispatch: nav slots match the GETIN byte (SHIFT
; ignored for $91/$9d, which are SHIFT+CRSR already), macro slots match
; the matrix key number (SFDX); the modifier must match exactly. ---
km_dispatch:
        sta km_key
        lda KM_SHFLAG
        and #(MOD_SHIFT|MOD_CMDRE|MOD_CTRL)
        sta km_mods                 ; for macro triggers
        sta km_nav_mods             ; for nav keys, SHIFT-masked below
        lda km_key
        cmp #$91
        beq km_mask_shift
        cmp #$9d
        bne km_scan
km_mask_shift:
        lda km_nav_mods
        and #(MOD_CMDRE|MOD_CTRL)
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
        cmp #ACTION_MACRO
        beq km_scan_macro
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
        bne km_run_6
        jmp module_start            ; keymap_menu.asm; leaves through
                                    ; JT_RESUME_LOCAL, never returns here
km_run_6:
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
