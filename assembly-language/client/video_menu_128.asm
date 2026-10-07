; video_menu_128.asm -- the 128 client's own Video Settings popup.
;
; The server's PREFS -> Terminal Settings -> 'V' sends a display-settings
; stream (commands/c64_display.py: STREAM_START, DISPLAY_STREAM_CONFIRM,
; 16-bit length, then border, background, blink speed). The C64 client
; LOADs config_menu.asm for it; this client used to answer it with a
; cancel and "(Popup not on the 128 client yet.)". Now recv_byte collects
; the body into vs_body (client-128.asm's frame_byte) and frame_finish
; jumps to vs_open with it.
;
; Not config_menu.asm built in, the way keymap_menu.asm and the drive
; picker are: what makes sense differs by screen (Ryan's ask, 2026-10-05),
; so the popup works out which one it's on and offers:
;
;   40 columns (VIC-II): Border color, Background color, Cursor blink
;     speed -- the C64 popup's fields, minus Border style (the Gothic
;     charset's box-glyph swap; this client runs the ROM charset).
;   80 columns (VDC): Background color (the VDC has no border), Cursor
;     blink speed, and two client-side settings for the 8563's own
;     hardware cursor -- Cursor (Soft = input_editor.asm's reverse-video
;     cursor, as before; Block or Line = the VDC cursor in that shape)
;     and Flash (the VDC cursor's Slow/Fast/Solid blink).
;
; Border, background and blink speed go back to the server, as on the
; C64. The server stores one set per player: the 80-column background is
; the same VIC-II color number, shown as the RGBI color the editor itself
; uses for it (dlg_vdc_colors -- the same mapping apply_settings uses at
; login). The reply echoes every body byte that came in, edited or not,
; so a longer body (the status line color, 2026-10-05) round-trips
; unchanged -- c64_display.py rejects a reply whose length differs.
;
; Background never lands on a color the text would vanish on: CRSR
; left/right step over any that shows as the dialogue's or the input
; line's text color (vs_bg_clash, Ryan's ask 2026-10-05), and client-
; 128.asm's apply_settings skips such a saved background at login. The
; box itself is drawn in the dialogue's text color rather than white, so
; it stays readable on any background allowed.
;
; Cursor and Flash are 128-only, so they live with the client:
; config_settings' CFG_VDC_SHAPE/CFG_VDC_FLASH (constants_128.asm), saved
; in TADA128.CFG on RETURN when either changed -- the same SCRATCH + SAVE
; as drive_menu_body.asm's dm_save_config.
;
; The VDC cursor's values are the editor ROM's own, read from VICE's
; kernal-318020-05.bin on 2026-10-05: the editor keeps its 80-column
; cursor mode in $0A2B, written to R10 ($CD91). It starts as $60 (blink
; at 1/32 the field rate, from scan line 0 -- $C0DE); ESC-S (block)
; clears the start line ($CAFE), ESC-U (underline) makes it 7 ($CB0A),
; ESC-E (steady) clears the blink bits ($CB1E) and ESC-F puts $60 back.
; R10 bits 6-5: 00 steady, 01 off, 10 blink 1/16, 11 blink 1/32. R11 (end
; line) is left as the editor set it, just as those escapes do.
;
; The editor only switches its VDC cursor on and off inside its own
; keyboard-wait loop ($C25x), which this client never runs (it reads keys
; through GETIN), so a cursor placed here stays put until we move it.
;
; Drawing: the box goes to the VIC screen at $0400 like the other built-in
; popups, through keymap_host_128.asm's JT_SAVE_SCREEN/JT_RESTORE_SCREEN,
; which present it on the VDC in 80 columns. While that's going on the
; IRQ owns the VDC (km_present_tick), so the live preview's own VDC
; register writes (background, the cursor) are made with interrupts off
; -- a register select from the IRQ between our select and our data write
; would send the byte somewhere else.
;
; Mainline only, so it sits above $4000 with the other popups.

VS_TOP_ROW    = 6           ; box's top screen row (config_menu.asm's)
VS_BODY_MAX   = 8           ; display-stream body bytes kept
VS_MARK_COL   = 5           ; '>' marker column
VS_VALUE_COL  = 32          ; two-digit values
VS_DEMO_COL   = 30          ; the blink row's live-preview cursor cell
VS_BAR_FIRST  = 16          ; choice rows: first screen column repainted
VS_BAR_END    = 35          ; ...and one past the last
VS_DEMO_VDC   = 770         ; 80 columns: VDC address of the demo cell --
                            ; (VS_TOP_ROW+3)*80 + KM_VDC_COL + VS_DEMO_COL,
                            ; by hand (c64list truncates products of byte
                            ; constants); +3 = the blink row, slot 1
VS_INPUT_VDC  = 1920        ; INPUT_ROW * 80, by hand
VS_TAIL_ROWS  = 6           ; box rows after the fields, before the bottom

VS_GETIN      = $ffe4       ; client-128.asm's KERNAL_GETIN is a {const:},
                            ; which doesn't reach {include:}d files

VDC_R_CURSOR_HI = $0e       ; R14/R15: cursor address
VDC_R_CURSOR_LO = $0f

; Field ids -- indexes into vs_val and the per-field tables below.
VS_F_BORDER   = 0
VS_F_BG       = 1
VS_F_BLINK    = 2
VS_F_SHAPE    = 3
VS_F_FLASH    = 4
VS_FIELD_COUNT     = 5

; --- vs_open: the whole display stream is in (vs_body, apply_idx bytes
; of it). Never returns: leaves through JT_RESUME, like the other
; popups. ---
vs_open:
        lda apply_idx
        sta vs_body_len
        jsr JT_SAVE_SCREEN
        ldx #VS_F_BLINK
vs_open_body:
        lda vs_body,x
        sta vs_val,x
        dex
        bpl vs_open_body
        lda config_settings+CFG_VDC_SHAPE
        sta vs_val+VS_F_SHAPE
        lda config_settings+CFG_VDC_FLASH
        sta vs_val+VS_F_FLASH
        ldx #VS_FIELD_COUNT-1
vs_open_orig:
        lda vs_val,x
        sta vs_orig,x
        dex
        bpl vs_open_orig

        ; Which fields this screen gets -- the 40-column list, or the
        ; 80-column one four bytes further on.
        ldy #0
        lda #3
        ldx screen_mode
        bne vs_open_fields
        ldy #4
        lda #4
vs_open_fields:
        sta vs_nfields
        clc
        adc #9                    ; top, title, the fields, VS_TAIL_ROWS,
        sta vs_box_rows           ; bottom
        ldx #0
vs_open_field_copy:
        lda vs_field_lists,y
        sta vs_fields,x
        cmp #VS_F_BLINK
        bne vs_open_field_next
        stx vs_demo_slot
vs_open_field_next:
        iny
        inx
        cpx vs_nfields
        bne vs_open_field_copy

        lda #0
        sta vs_sel
        sta vs_demo_on
        jsr vs_draw_box
        jsr vs_apply_live
        jsr vs_draw_values

; --- Main loop: blink the demo cursor, take keys. ---
vs_loop:
        jsr vs_demo_update
        jsr VS_GETIN
        cmp #0
        beq vs_loop
        cmp #$91                  ; CRSR up: previous field
        beq vs_key_up
        cmp #$11                  ; CRSR down: next field
        beq vs_key_down
        cmp #$9d                  ; CRSR left: lower value / left choice
        beq vs_key_left
        cmp #$1d                  ; CRSR right: higher value / right choice
        beq vs_key_right
        cmp #$0d                  ; RETURN: save
        beq vs_key_save
        cmp #$03                  ; RUN/STOP: cancel
        bne vs_loop
        jmp vs_cancel
vs_key_save:
        jmp vs_save

vs_key_up:
        dec vs_sel
        bpl vs_key_moved
        ldx vs_nfields
        dex
        stx vs_sel
        jmp vs_key_moved
vs_key_down:
        inc vs_sel
        lda vs_sel
        cmp vs_nfields
        bcc vs_key_moved
        lda #0
        sta vs_sel
vs_key_moved:
        jsr vs_draw_values
        jmp vs_loop

; Numbers wrap at either end (as on the C64); the choice bars stop there,
; like the C64's Border style bar. A background color the text would
; vanish on (vs_bg_clash) is stepped over in the same direction --
; vs_key_dir says which way to step again.
vs_key_right:
        lda #1
        sta vs_key_dir
vs_key_right_step:
        jsr vs_cur_field
        lda vs_val,x
        cmp vs_max,x
        bcc vs_key_inc
        lda vs_kind,x
        bne vs_key_changed        ; choice: stays on the last one
        lda vs_min,x
        jmp vs_key_store
vs_key_inc:
        adc #1                    ; carry clear from the bcc
        jmp vs_key_store
vs_key_left:
        lda #0
        sta vs_key_dir
vs_key_left_step:
        jsr vs_cur_field
        lda vs_val,x
        cmp vs_min,x
        beq vs_key_at_min
        sbc #1                    ; carry set: above the minimum
        jmp vs_key_store
vs_key_at_min:
        lda vs_kind,x
        bne vs_key_changed        ; choice: stays on the first one
        lda vs_max,x
vs_key_store:
        sta vs_val,x
        cpx #VS_F_BG
        bne vs_key_changed
        jsr vs_bg_clash
        bcc vs_key_changed
        lda vs_key_dir            ; invisible text: one more step
        bne vs_key_right_step
        jmp vs_key_left_step
vs_key_changed:
        jsr vs_apply_live
        jsr vs_draw_values
        jmp vs_loop

; --- vs_bg_clash: A = a background color (VIC-II number). Carry set =
; text would be invisible on it: it shows as the same color as the
; dialogue's current text (vic_screen.asm's vdlg_color in 40 columns,
; vdc_screen.asm's dlg_attr in 80) or the input line's ($F1, the
; editor's color -- the server's command color). In 80 columns all three
; are compared as the RGBI color the VDC shows. Ryan's ask, 2026-10-05.
; Used by the popup and by client-128.asm's apply_settings. Preserves
; A and X. Only two of the sixteen colors can ever clash, so a caller stepping
; past one always finds another. ---
vs_bg_clash:
        stx vs_clash_x
        sta vs_clash_a
        ldx screen_mode
        beq vs_bg_clash_vdc
        sta vs_clash_bg
        cmp vdlg_color
        beq vs_bg_clash_yes
        lda $f1                   ; KERNAL_COLOR: a VIC-II color here
        jmp vs_bg_clash_input
vs_bg_clash_vdc:
        tax
        lda dlg_vdc_colors,x
        sta vs_clash_bg
        lda dlg_attr
        and #$0f                  ; RGBI; the high bits are ALT etc.
        cmp vs_clash_bg
        beq vs_bg_clash_yes
        lda $f1                   ; KERNAL_COLOR: a VDC attribute here
vs_bg_clash_input:
        and #$0f
        cmp vs_clash_bg
        beq vs_bg_clash_yes
        ldx vs_clash_x
        lda vs_clash_a
        clc
        rts
vs_bg_clash_yes:
        ldx vs_clash_x
        lda vs_clash_a
        sec
        rts

; --- vs_text_color: the dialogue's text color as a VIC-II number -- the
; popup box is drawn in it rather than plain white, so a background
; vs_bg_clash allows can't hide the box either. 80 columns: the VIC-II
; color whose RGBI (dlg_vdc_colors, one-to-one) is dlg_attr's, since the
; box reaches the VDC through km_present_tick's same mapping. ---
vs_text_color:
        lda screen_mode
        beq vs_text_color_vdc
        lda vdlg_color
        rts
vs_text_color_vdc:
        lda dlg_attr
        and #$0f
        ldx #15
vs_text_color_scan:
        cmp dlg_vdc_colors,x
        beq vs_text_color_found
        dex
        bpl vs_text_color_scan
        ldx #1                    ; (can't happen: the table covers 0-15)
vs_text_color_found:
        txa
        rts

; X = the selected field's id.
vs_cur_field:
        ldx vs_sel
        lda vs_fields,x
        tax
        rts

; --- vs_apply_live: show vs_val now -- colors, the input editor's blink
; speed (which also paces the other popups' cursor), and in 80 columns
; the VDC cursor on the demo cell. ---
vs_apply_live:
        ldx vs_val+VS_F_BLINK
        lda apply_blink_masks-1,x ; 1-5 -> client-128.asm's mask table
        sta cursor_blink_mask
        lda screen_mode
        beq vs_apply_vdc
        lda vs_val+VS_F_BORDER
        sta $d020
        lda vs_val+VS_F_BG
        sta $d021
        rts
vs_apply_vdc:
        sei                       ; the IRQ is presenting the popup -- see
        ldx #VDC_R_BACKGROUND     ; this file's header
        jsr vdc_read_reg
        and #$f0                  ; R26's high nibble: keep (apply_settings)
        sta vs_tmp
        ldx vs_val+VS_F_BG
        lda dlg_vdc_colors,x
        ora vs_tmp
        ldx #VDC_R_BACKGROUND
        jsr vdc_write_reg
        lda #>VS_DEMO_VDC
        ldy #<VS_DEMO_VDC
        jsr vs_cursor_at
        lda vs_val+VS_F_SHAPE
        ldx vs_val+VS_F_FLASH
        jsr vs_cursor_mode
        cli
        rts

; --- vs_cursor_at: A/Y = VDC address (high/low) -> R14/R15. ---
vs_cursor_at:
        ldx #VDC_R_CURSOR_HI
        jsr vdc_write_reg
        tya
        ldx #VDC_R_CURSOR_LO
        jmp vdc_write_reg

; --- vs_cursor_mode: A = shape (0 Soft, 1 Block, 2 Line), X = flash (0
; Slow, 1 Fast, 2 Solid) -> R10. Soft turns the VDC cursor off. ---
vs_cursor_mode:
        tay
        beq vs_cursor_mode_off
        lda vs_flash_bits,x
        ora vs_shape_start-1,y
        jmp vs_cursor_mode_write
vs_cursor_mode_off:
        lda #VDC_CURSOR_OFF
vs_cursor_mode_write:
        ldx #VDC_R_CURSOR_MODE
        jmp vdc_write_reg

; --- vs_cursor_off: VDC cursor off, 80 columns only (mainline owns the
; VDC). keymap_host_128.asm's JT_SAVE_SCREEN calls it too, so the input
; row's cursor doesn't keep blinking under the other popups. ---
vs_cursor_off:
        lda screen_mode
        bne vs_cursor_off_rts
        lda #0
        jmp vs_cursor_mode
vs_cursor_off_rts:
        rts

; --- vs_editor_cursor: called by input_editor.asm's `cursor:` before it
; draws its own. 80 columns with Block or Line chosen: the VDC cursor goes
; on the input row's cursor cell, carry set (the editor then just polls
; for keys). Otherwise carry clear: the reverse-video cursor as before. ---
vs_editor_cursor:
        lda screen_mode
        bne vs_editor_cursor_no
        lda config_settings+CFG_VDC_SHAPE
        beq vs_editor_cursor_no
        lda cpos                  ; the same column rvson works out
        sec
        sbc lcol
        clc
        adc strcol
        clc
        adc #<VS_INPUT_VDC
        tay
        lda #>VS_INPUT_VDC
        adc #0
        jsr vs_cursor_at
        lda config_settings+CFG_VDC_SHAPE
        ldx config_settings+CFG_VDC_FLASH
        jsr vs_cursor_mode
        sec
        rts
vs_editor_cursor_no:
        clc
        rts

; --- vs_demo_update: the blink row's demo cell, C64-popup style: blinks
; (or holds) at the chosen speed, timed off the jiffy clock's low byte
; ($A2 on the 128 as on the C64). When the VDC cursor is previewing
; instead, the soft one stays off. ---
vs_demo_update:
        lda screen_mode
        bne vs_demo_soft
        lda vs_val+VS_F_SHAPE
        beq vs_demo_soft
        lda vs_demo_on            ; VDC cursor: just keep this one off
        bne vs_demo_toggle
        rts
vs_demo_soft:
        ldx vs_val+VS_F_BLINK
        lda apply_blink_masks-1,x
        beq vs_demo_want_on       ; $00: solid
        and $a2
        beq vs_demo_want_off
vs_demo_want_on:
        lda vs_demo_on
        beq vs_demo_toggle
        rts
vs_demo_want_off:
        lda vs_demo_on
        bne vs_demo_toggle
        rts
vs_demo_toggle:
        lda vs_demo_slot
        clc
        adc #2
        tax
        jsr vs_set_row
        ldy #VS_DEMO_COL
        jsr vs_peek
        eor #$80
        jsr vs_poke
        lda vs_demo_on
        eor #1
        sta vs_demo_on
        rts

; --- Save: reply with the body (border/background/blink edited), store
; and save the VDC cursor if it changed, put the screen back. ---
vs_save:
        ldx #VS_F_BLINK
vs_save_body:
        lda vs_val,x
        sta vs_body,x
        dex
        bpl vs_save_body
        lda #STREAM_START
        jsr sl_send
        lda #DISPLAY_STREAM_CONFIRM
        jsr sl_send
        lda vs_body_len
        jsr sl_send
        lda #0
        jsr sl_send
        ldx #0
vs_save_send:
        lda vs_body,x
        jsr sl_send               ; preserves X
        inx
        cpx vs_body_len
        bne vs_save_send

        lda #0
        sta vs_msg+1              ; no status message unless a save ran
        lda vs_val+VS_F_SHAPE
        cmp config_settings+CFG_VDC_SHAPE
        bne vs_save_cursor
        lda vs_val+VS_F_FLASH
        cmp config_settings+CFG_VDC_FLASH
        beq vs_save_done
vs_save_cursor:
        lda vs_val+VS_F_SHAPE     ; resident copy first: holds for the
        sta config_settings+CFG_VDC_SHAPE  ; session even if the disk
        lda vs_val+VS_F_FLASH              ; save fails
        sta config_settings+CFG_VDC_FLASH
        jsr vs_save_config        ; -> X/Y = the status message
        stx vs_msg
        sty vs_msg+1
vs_save_done:
        jsr vs_close              ; before the message -- the restore
        ldy vs_msg+1              ; repaints the status row
        beq vs_save_resume
        ldx vs_msg
        jsr JT_BUILD_STATUS_LINE
vs_save_resume:
        jmp JT_RESUME

; --- Cancel: put back what was live before, tell the server. ---
vs_cancel:
        ldx #VS_FIELD_COUNT-1
vs_cancel_copy:
        lda vs_orig,x
        sta vs_val,x
        dex
        bpl vs_cancel_copy
        jsr vs_apply_live
        lda #DISPLAY_STREAM_CANCEL
        jsr send_stream_cancel
        jsr vs_close
        jmp JT_RESUME

; vs_close: the screen back, and the VDC cursor off until the input
; editor places it again (vs_editor_cursor).
vs_close:
        jsr JT_RESTORE_SCREEN
        jmp vs_cursor_off

; --- vs_save_config: SCRATCH + SAVE TADA128.CFG on the client's drive,
; then read the error channel -- drive_menu_body.asm's dm_save_config.
; Out: X/Y = the status message.
;
; With the SwiftLink held for the duration (swiftlink.asm's sl_hold/
; sl_release): the server answers the reply vs_save just sent at once,
; and its text arriving as NMIs mid-transfer hung x128's serial bus two
; runs in five before this was added -- see sl_hold's comment. ---
vs_save_config:
        jsr sl_hold
        jsr vs_save_config_held
        jmp sl_release            ; tail call -- keeps X/Y

vs_save_config_held:
        lda #0
        sta vs_save_failed
        ldx #0                    ; filenames and the SAVE's data in bank 0
        jsr SETBNK
        jsr select_drive          ; disk.asm -- the client's drive, or
        bcc vs_save_drive         ; the first one on the bus
        ldx #<vs_no_drive_msg
        ldy #>vs_no_drive_msg
        rts
vs_save_drive:
        lda #DM_SCRATCH_LEN       ; drive_menu_body.asm's "S0:TADA128.CFG"
        ldx #<dm_scratch_command
        ldy #>dm_scratch_command
        jsr DSK_SETNAM
        jsr current_drive_to_x
        lda #DSK_CMD_CHANNEL
        ldy #DSK_CMD_CHANNEL
        jsr DSK_SETLFS
        jsr DSK_OPEN
        lda #DSK_CMD_CHANNEL
        jsr DSK_CLOSE
        lda #DM_FILENAME_LEN
        ldx #<dm_filename
        ldy #>dm_filename
        jsr DSK_SETNAM
        jsr current_drive_to_x
        lda #2
        ldy #1
        jsr DSK_SETLFS
        lda KEYMAP_TABLE_PTR      ; keymap_table, then config_settings
        sta DM_SAVE_PTR
        lda KEYMAP_TABLE_PTR+1
        sta DM_SAVE_PTR+1
        lda KEYMAP_TABLE_PTR
        clc
        adc #<CONFIG_FILE_SIZE
        tax
        lda KEYMAP_TABLE_PTR+1
        adc #>CONFIG_FILE_SIZE
        tay
        lda #DM_SAVE_PTR
        jsr DM_KERNAL_SAVE
        rol vs_save_failed        ; KERNAL error (carry) -> bit 0
        jsr read_error_channel    ; the drive's verdict
        rol vs_save_failed
        ldx #<vs_saved_msg
        ldy #>vs_saved_msg
        lda vs_save_failed
        and #$03
        beq vs_save_config_rts
        ldx #<vs_error_msg
        ldy #>vs_error_msg
vs_save_config_rts:
        rts

; --- vs_draw_box: the static box -- color RAM over its rows in the
; dialogue's text color (vs_text_color), then
; each row: the top rule, the title, one label row per field, the tail
; rows (blank, help line, blank, three key-help rows), the bottom rule. ---
vs_draw_box:
        ldx #VS_TOP_ROW
        clc
        lda km_row40_lo,x
        adc #<KM_VIC_COLORS
        sta km_fill_store+1
        lda km_row40_hi,x
        adc #>KM_VIC_COLORS
        sta km_fill_store+2
        ldx vs_box_rows
        lda km_row40_lo,x         ; rows * 40
        sta km_count
        lda km_row40_hi,x
        sta km_count+1
        jsr vs_text_color
        tax
        jsr km_fill

        lda #$70                  ; top-left corner
        sta vs_edge_l
        lda #$6e                  ; top-right
        sta vs_edge_r
        lda #<vs_rule
        ldy #>vs_rule
        ldx #0
        jsr vs_put_row

        lda #<vs_title_40
        ldy #>vs_title_40
        ldx screen_mode
        bne vs_draw_title
        lda #<vs_title_80
        ldy #>vs_title_80
vs_draw_title:
        ldx #1
        jsr vs_put_mid

        lda #0
        sta vs_i
vs_draw_field:
        ldx vs_i
        lda vs_fields,x
        tax
        lda vs_label_lo,x
        ldy vs_label_hi,x
        pha
        lda vs_i
        clc
        adc #2
        tax
        pla
        jsr vs_put_mid
        inc vs_i
        lda vs_i
        cmp vs_nfields
        bne vs_draw_field

        lda #0
        sta vs_i
vs_draw_tail:
        ldx vs_i
        lda vs_tail_lo,x
        ldy vs_tail_hi,x
        pha
        txa
        clc
        adc vs_nfields
        adc #2
        tax
        pla
        jsr vs_put_mid
        inc vs_i
        lda vs_i
        cmp #VS_TAIL_ROWS
        bne vs_draw_tail

        lda #$6d                  ; bottom-left
        sta vs_edge_l
        lda #$7d                  ; bottom-right
        sta vs_edge_r
        lda #<vs_rule
        ldy #>vs_rule
        ldx vs_box_rows
        dex
        jmp vs_put_row

; --- vs_draw_values: per field row, the '>' marker and the value -- two
; digits, or the choice text with the chosen one's bar reversed -- then
; the help line and the CRSR left/right hint for the selected field. ---
vs_draw_values:
        lda #0
        sta vs_i
vs_dv_loop:
        lda vs_i
        clc
        adc #2
        tax
        jsr vs_set_row
        ldy #VS_MARK_COL
        lda #' '
        ldx vs_i
        cpx vs_sel
        bne vs_dv_mark
        lda #'>'
vs_dv_mark:
        jsr vs_poke
        lda vs_fields,x
        tax
        lda vs_kind,x
        bne vs_dv_choice
        lda vs_val,x
        jsr vs_dec2
        ldy #VS_VALUE_COL
        lda vs_tens
        jsr vs_poke
        iny
        lda vs_ones
        jsr vs_poke
        jmp vs_dv_next
vs_dv_choice:
        sec                       ; the label from screen column 0 on:
        lda vs_label_lo,x         ; label - 5 (it starts at column 5)
        sbc #5
        sta vs_dv_plain+1
        lda vs_label_hi,x
        sbc #0
        sta vs_dv_plain+2
        ldy #VS_BAR_FIRST
vs_dv_plain:
        lda $ffff,y
        jsr vs_poke
        iny
        cpy #VS_BAR_END
        bne vs_dv_plain
        lda #0                    ; bar index: Cursor's bars from 0, Flash's
        cpx #VS_F_FLASH           ; from 3, plus the value
        bne vs_dv_bar_base
        lda #3
vs_dv_bar_base:
        clc
        adc vs_val,x
        tax
        ldy vs_bar_col,x
        lda vs_bar_width,x
        sta vs_count
vs_dv_bar:
        jsr vs_peek
        ora #$80                  ; reverse video
        jsr vs_poke
        iny
        dec vs_count
        bne vs_dv_bar
vs_dv_next:
        inc vs_i
        lda vs_i
        cmp vs_nfields
        beq vs_dv_help            ; not `bne vs_dv_loop`: out of branch
        jmp vs_dv_loop            ; range, which c64list doesn't catch
vs_dv_help:
        jsr vs_cur_field          ; help line: box row nfields+3
        lda vs_help_lo,x
        ldy vs_help_hi,x
        pha
        lda vs_kind,x
        sta vs_tmp
        lda vs_nfields
        clc
        adc #3
        tax
        pla
        jsr vs_put_mid
        lda #<vs_help2_value      ; CRSR left/right hint: box row
        ldy #>vs_help2_value      ; nfields+6
        ldx vs_tmp
        beq vs_dv_help2
        lda #<vs_help2_choice
        ldy #>vs_help2_choice
vs_dv_help2:
        pha
        lda vs_nfields
        clc
        adc #6
        tax
        pla
        ; fall through

; --- vs_put_mid / vs_put_row: one box row. A/Y = its 30-byte interior,
; X = box row (0 = top). vs_put_mid gives it vertical-line edges;
; vs_put_row uses vs_edge_l/vs_edge_r. The four columns either side of
; the box are blanked, as on the C64. ---
vs_put_mid:
        pha
        lda #$5d                  ; vertical line
        sta vs_edge_l
        sta vs_edge_r
        pla
vs_put_row:
        sta vs_pr_src+1
        sty vs_pr_src+2
        jsr vs_set_row
        ldy #39
        lda #' '
vs_pr_blank:
        jsr vs_poke
        dey
        bpl vs_pr_blank
        ldy #4
        lda vs_edge_l
        jsr vs_poke
        ldy #35
        lda vs_edge_r
        jsr vs_poke
        ldx #0
        ldy #5
vs_pr_loop:
vs_pr_src:
        lda $ffff,x
        jsr vs_poke
        iny
        inx
        cpx #30
        bne vs_pr_loop
        rts

; vs_set_row: X = box row -> vs_poke/vs_peek aimed at that screen row.
vs_set_row:
        txa
        clc
        adc #VS_TOP_ROW
        tax
        clc
        lda km_row40_lo,x
        adc #<KM_VIC_SCREEN
        sta vs_poke+1
        sta vs_peek+1
        lda km_row40_hi,x
        adc #>KM_VIC_SCREEN
        sta vs_poke+2
        sta vs_peek+2
        rts

; Column Y of the vs_set_row row. Both preserve X and Y.
vs_poke:
        sta $ffff,y
        rts
vs_peek:
        lda $ffff,y
        rts

; vs_dec2: A = 0-19 -> vs_tens/vs_ones, digit screen codes ($30-$39, the
; same as their PETSCII).
vs_dec2:
        ldx #'0'
vs_dec2_tens:
        cmp #10
        bcc vs_dec2_done
        sbc #10
        inx
        jmp vs_dec2_tens
vs_dec2_done:
        ora #'0'
        sta vs_ones
        stx vs_tens
        rts

; --- Tables ---

; Field lists: 40 columns (3), then 80 columns (4).
vs_field_lists:
        byte VS_F_BORDER, VS_F_BG, VS_F_BLINK
        byte 0                    ; (pad -- the 80-column list starts at +4)
        byte VS_F_BG, VS_F_BLINK, VS_F_SHAPE, VS_F_FLASH

; Per field id: border, background, blink speed, Cursor, Flash.
vs_min:
        byte 0, 0, 1, 0, 0
vs_max:
        byte 15, 15, 5, 2, 2
vs_kind:                          ; 0 = number, 1 = choice bar
        byte 0, 0, 0, 1, 1
vs_label_lo:
        byte <vs_lbl_border, <vs_lbl_bg, <vs_lbl_blink, <vs_lbl_shape, <vs_lbl_flash
vs_label_hi:
        byte >vs_lbl_border, >vs_lbl_bg, >vs_lbl_blink, >vs_lbl_shape, >vs_lbl_flash
vs_help_lo:
        byte <vs_help_border, <vs_help_bg, <vs_help_blink, <vs_help_shape, <vs_help_flash
vs_help_hi:
        byte >vs_help_border, >vs_help_bg, >vs_help_blink, >vs_help_shape, >vs_help_flash

; Tail rows, after the fields: blank, the help line (vs_draw_values
; fills it), blank, then the key help.
vs_tail_lo:
        byte <vs_blank, <vs_blank, <vs_blank, <vs_help1, <vs_help2_value, <vs_help3
vs_tail_hi:
        byte >vs_blank, >vs_blank, >vs_blank, >vs_help1, >vs_help2_value, >vs_help3

; Choice bars, screen columns and widths: Cursor's Soft/Block/Line, then
; Flash's Slow/Fast/Solid -- one blank either side of each word, from
; the label text below.
vs_bar_col:
        byte 16, 22, 29, 16, 22, 29
vs_bar_width:
        byte 6, 7, 6, 6, 6, 6

; R10 pieces (see this file's header): Flash's Slow/Fast/Solid blink
; bits, and Block's/Line's start scan line.
vs_flash_bits:
        byte $60, $40, $00
vs_shape_start:
        byte 0, 7

; --- State ---
vs_body:
        area VS_BODY_MAX, 0       ; the display stream's body, as received
vs_body_len:     byte 0
vs_val:          area VS_FIELD_COUNT, 0
vs_orig:         area VS_FIELD_COUNT, 0
vs_fields:       area 4, 0        ; field ids shown, top to bottom
vs_nfields:      byte 0
vs_box_rows:     byte 0
vs_sel:          byte 0           ; selected slot in vs_fields
vs_demo_slot:    byte 0           ; slot of the blink-speed field
vs_demo_on:      byte 0           ; 1 = demo cell currently reversed
vs_i:            byte 0
vs_count:        byte 0
vs_tmp:          byte 0
vs_tens:         byte 0
vs_ones:         byte 0
vs_edge_l:       byte 0
vs_edge_r:       byte 0
vs_msg:          word 0
vs_save_failed:  byte 0
vs_key_dir:      byte 0           ; 1 = the last value key was right
vs_clash_bg:     byte 0
vs_clash_x:      byte 0
vs_clash_a:      byte 0

; --- Text: 30-byte box interiors, screen codes ({alpha:pokealt}, as
; config_menu.asm's). Box glyphs as raw bytes -- see config_menu.asm on
; alpha modes mangling them inside ascii strings. ---
vs_rule:
        area 30, $40              ; horizontal line
{alpha:pokealt}
vs_title_40:
        ascii "  Video Settings: 40 columns  "
vs_title_80:
        ascii "  Video Settings: 80 columns  "
vs_lbl_border:
        ascii "  Border color:            00 "
vs_lbl_bg:
        ascii "  Background color:        00 "
vs_lbl_blink:
        ascii "  Cursor blink speed:      00 "
vs_lbl_shape:
        ascii "  Cursor:   Soft  Block  Line "
vs_lbl_flash:
        ascii "  Flash:    Slow  Fast   Solid"
vs_blank:
        ascii "                              "
vs_help_border:
        ascii "Border color, 0-15 (VIC-II)   "
vs_help_bg:
        ascii "Background color, 0-15        "
vs_help_blink:
        ascii "1=fastest .. 4=slowest, 5=off "
vs_help_shape:
        ascii "Soft, or the VDC's own cursor "
vs_help_flash:
        ascii "VDC cursor's blink (not Soft) "
vs_help1:
        ascii " Crsr Up/Down: Select option  "
vs_help2_value:
        ascii " Crsr Left/Right: Incr/Decr   "
vs_help2_choice:
        ascii " Crsr Left/Right: Choose      "
vs_help3:
        ascii " Return: save   Stop: cancel  "

; vs_save_config's status-row messages, NUL-terminated
vs_saved_msg:
        ascii "VDC cursor saved."
        byte 0
vs_no_drive_msg:
        ascii "VDC cursor not saved: no drive"
        byte 0
vs_error_msg:
        ascii "VDC cursor not saved: disk error"
        byte 0
{alpha:normal}
