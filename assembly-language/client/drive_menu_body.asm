; drive_menu_body.asm -- the "Select Drive" popup (C64 and 128).
;
; Lists the drives on the serial bus with their model, one per row, and
; lets the player pick one with a highlight bar:
;
;     [  8   1541   (current) ]
;        9   1571
;       10   1581
;
; CRSR up/down moves the bar, RETURN uses the highlighted drive, R
; scans the bus again, RUN/STOP cancels. Ryan's ask, 2026-10-01: pick
; the drive the client loads/saves its settings (and, later, session
; logs) on.
;
; Same loadable-overlay shape as config_menu.asm/keymap_menu.asm --
; LOADed at OVERLAY_BUF, reaches the resident program only through
; constants.asm's jump table, and hands back with JT_RESUME_LOCAL like
; keymap_menu.asm (purely local: nothing here involves the server).
; Carries its own copies of disk.asm (bus scan) and drive_id.asm (M-R
; model lookup), as a separate standalone .prg has to -- see disk.asm's
; header comment.
;
; This file is the popup itself; drive_menu.asm wraps it into the C64's
; DRIVE.MNU (constants.asm, orig OVERLAY_BUF, disk.asm + drive_id.asm),
; and the 128 client {include:}s it straight in (client-128.asm defines
; c128), like keymap_menu_128.asm: no orig, no constants.asm (its JT_*
; jump table is ROM on the 128 --
; keymap_host_128.asm's JT_* labels stand in, and keymap_128.asm's
; KEYMAP_TABLE_PTR/CONFIG_SETTINGS_PTR labels), disk.asm/drive_id.asm
; come from client-128.asm, the popup goes to the VIC screen at $0400
; (keymap_host_128.asm presents it on the VDC in 80 columns) and the
; file is TADA128.CFG.
;
; What it picks is the DATA drive (Ryan, 2026-10-01): where session logs
; and other data files go. The client's own files -- the overlays and
; TADA64.CFG itself -- stay on the drive it was loaded from, so a data
; disk without them in another drive can't break F7/F5/the menus. RETURN
; stores the choice in config_settings' CFG_DATA_DRIVE (keymap.asm, found
; through CONFIG_SETTINGS_PTR) and saves TADA64.CFG -- keymap_table plus
; that block -- the same way keymap_menu.asm's key_save does. "(current)"
; marks the data drive: the saved one, or the client's drive while none
; has been chosen.
{ifdef: c128}
POPUP_SCREEN = $0400            ; the VIC screen (keymap_host_128.asm)
{endif}

; Popup box position. Plain `=` constants, defined before any address
; arithmetic uses them (see config_menu.asm's BOX_TOP_ROW comment).
DM_TOP_ROW   = 4
DM_LIST_ROWS = 10           ; drives shown at once -- real setups have
                            ; far fewer; any past 10 are left off
DM_BOX_ROWS  = 18           ; top, title, blank, 10 list rows, blank,
                            ; 3 help rows, bottom -- by hand, see
                            ; keymap.asm's KEYMAP_TABLE_SIZE comment
DM_LIST_TOP  = DM_TOP_ROW + 3
DM_INNER     = 30           ; box interior width (screen columns 5-34)
DM_BAR_FIRST = 1            ; highlight bar spans interior columns 1-28,
DM_BAR_LAST  = 28           ; one blank column inside each border
DM_MODEL_COL = 8            ; interior column of the model text
DM_TAG_COL   = 15           ; interior column of "(current)"
DM_MODEL_SIZE = 5           ; drive_model's 4 characters + NUL
DM_SAVE_PTR   = $fb         ; KERNAL SAVE's zero-page start pointer
DM_KERNAL_SAVE = $ffd8

; COLOR_RAM/GETIN are macro_preprocessor.py built-ins (C64_CONSTANTS);
; the popup goes to POPUP_SCREEN (constants.asm), the client's
; displayed buffer -- not the built-in SCREEN_RAM ($0400).

dm_module_start:                  ; first byte of DRIVE.MNU (OVERLAY_BUF)
        tsx                       ; real stack depth at entry -- dm_loop's
        stx dm_entry_sp           ; `jsr dm_dispatch` leaves a return
                                  ; address pushed while the popup is
                                  ; open (handlers exit with a tail jmp);
                                  ; the exits restore this rather than
                                  ; leak it -- see config_menu.asm's
                                  ; module_start comment
        jsr JT_SAVE_SCREEN        ; put back exactly as-is on exit
        lda CONFIG_SETTINGS_PTR   ; aim dm_cfg_get/dm_cfg_put at the
        clc                       ; resident CFG_DATA_DRIVE byte (self-
        adc #CFG_DATA_DRIVE       ; modified operands rather than a
        sta dm_cfg_get+1          ; zero-page pointer)
        sta dm_cfg_put+1
        lda CONFIG_SETTINGS_PTR+1
        adc #0
        sta dm_cfg_get+2
        sta dm_cfg_put+2
        jsr dm_draw_frame
        jsr dm_scan
        jsr dm_draw_list

dm_loop:
        jsr GETIN
        cmp #0
        beq dm_loop
        jsr dm_dispatch           ; jmp's into a handler on a hit;
        jmp dm_loop               ; returns here on a miss

; code, handler-address -- 3 bytes/entry, same table-driven dispatch
; as config_menu.asm's dispatch_config_key (same GETIN codes, already
; confirmed live there).
dm_dispatch:
        sta dm_key
        ldx #0
dm_dispatch_loop:
        cpx #DM_KEYS_END
        beq dm_dispatch_miss
        lda dm_keys,x
        cmp dm_key
        beq dm_dispatch_hit
        inx
        inx
        inx
        jmp dm_dispatch_loop
dm_dispatch_hit:
        lda dm_keys+1,x
        sta dm_dispatch_jmp+1
        lda dm_keys+2,x
        sta dm_dispatch_jmp+2
dm_dispatch_jmp:
        jmp $ffff
dm_dispatch_miss:
        rts

dm_keys:
        byte $91                  ; cursor up
        word dm_key_up
        byte $11                  ; cursor down
        word dm_key_down
        byte $0d                  ; RETURN -- use the highlighted drive
        word dm_key_choose
        byte $03                  ; RUN/STOP -- cancel
        word dm_key_cancel
        byte $52                  ; R -- scan again
        word dm_key_rescan
        byte $d2                  ; SHIFT+R (unshifted byte + $80)
        word dm_key_rescan
DM_KEYS_END = * - dm_keys

dm_key_up:
        lda dm_count
        beq dm_key_done
        lda dm_selected
        bne dm_key_up_dec
        lda dm_count              ; wrap to the last drive
dm_key_up_dec:
        sec
        sbc #1
        sta dm_selected
        jmp dm_key_redraw

dm_key_down:
        lda dm_count
        beq dm_key_done
        ldx dm_selected
        inx
        cpx dm_count
        bne dm_key_down_store
        ldx #0                    ; wrap to the first drive
dm_key_down_store:
        stx dm_selected
dm_key_redraw:
        jsr dm_draw_list
dm_key_done:
        rts                       ; back to dm_loop via dm_dispatch's caller

dm_key_rescan:
        jsr dm_scan
        jmp dm_key_redraw

; --- RETURN: make the highlighted drive the data drive, save
; TADA64.CFG, say how that went, hand back ---
dm_key_choose:
        lda dm_count
        beq dm_key_cancel         ; nothing listed: same as cancel
        ldx dm_selected
        lda drive_list,x
        sta dm_number
dm_cfg_put:
        sta $ffff                 ; CFG_DATA_DRIVE (dm_module_start aims it)
        jsr dm_save_config        ; -> X/Y = the status message
        stx dm_msg_ptr            ; JT_RESTORE_SCREEN doesn't promise to
        sty dm_msg_ptr+1          ; keep X/Y
        jsr JT_RESTORE_SCREEN     ; BEFORE the status message -- it
                                  ; repaints the status row from the
                                  ; snapshot (see keymap_menu.asm's
                                  ; key_save comment)
        ldx dm_msg_ptr
        ldy dm_msg_ptr+1
        jmp dm_exit

dm_key_cancel:
        jsr JT_RESTORE_SCREEN
        ldx #<dm_cancel_msg
        ldy #>dm_cancel_msg
dm_exit:
        jsr JT_STATUS_PUSH_RESET  ; X/Y pass through (keymap_menu.asm's
        jsr JT_BUILD_STATUS_LINE  ; push_keymap_status_msg relies on it)
        ldx dm_entry_sp           ; drop this visit's dm_loop/dm_dispatch
        txs                       ; depth -- see dm_module_start
        jmp JT_RESUME_LOCAL

; --- dm_scan: find the drives and their models ---
; drive_list/drive_count from scan_serial_bus (disk.asm); dm_models gets
; each one's drive_model (drive_id.asm), 5 bytes apiece, "" if it wasn't
; recognized. The bar starts on the current drive (dm_current) if it's
; listed, else the first. M-R is a few milliseconds per drive, so this
; runs every time the popup opens rather than caching anything.
dm_scan:
        jsr dm_clear_list
        ldx #<dm_scanning_text    ; "Scanning..." on the first list row
        ldy #>dm_scanning_text    ; while the bus is probed
        lda #0
        jsr dm_text_row
        jsr dm_data_drive
        sta dm_current
        jsr scan_serial_bus
        cmp #(DM_LIST_ROWS+1)
        bcc dm_scan_count_ok
        lda #DM_LIST_ROWS
dm_scan_count_ok:
        sta dm_count
        lda #0
        sta dm_index
        sta dm_selected
        sta dm_out
dm_scan_loop:
        lda dm_index
        cmp dm_count
        beq dm_scan_done
        tax
        lda drive_list,x
        cmp dm_current
        bne dm_scan_identify
        stx dm_selected
dm_scan_identify:
        tax
        jsr identify_drive        ; clobbers X/Y -- the loop keeps its
        ldx dm_out                ; place in dm_index/dm_out instead
        ldy #0
dm_scan_copy:
        lda drive_model,y
        sta dm_models,x
        inx
        iny
        cpy #DM_MODEL_SIZE
        bne dm_scan_copy
        stx dm_out
        inc dm_index
        jmp dm_scan_loop
dm_scan_done:
        rts

; --- dm_draw_list: repaint every list row from dm_* ---
dm_draw_list:
        lda #0
        sta dm_index
dm_draw_list_loop:
        jsr dm_build_row
        lda dm_index
        cmp dm_selected
        bne dm_draw_list_poke
        lda dm_count
        beq dm_draw_list_poke     ; no bar on an empty list
        ldx #DM_BAR_FIRST
dm_draw_list_bar:
        lda dm_row_buf,x
        ora #$80                  ; reverse video
        sta dm_row_buf,x
        inx
        cpx #(DM_BAR_LAST+1)
        bne dm_draw_list_bar
dm_draw_list_poke:
        lda dm_index
        jsr dm_poke_row
        inc dm_index
        lda dm_index
        cmp #DM_LIST_ROWS
        bne dm_draw_list_loop
        rts

; --- dm_build_row: dm_row_buf = list row dm_index, plain (no bar) ---
; "    8   1541   (current)" -- number right-aligned in interior columns
; 3-4, model from column DM_MODEL_COL, the tag from DM_TAG_COL. A row
; past the last drive is blank, except the first row of an empty list.
dm_build_row:
        jsr dm_blank_row_buf
        lda dm_index
        cmp dm_count
        bcc dm_build_row_drive
        ora dm_count              ; row 0 of an empty list?
        bne dm_build_row_done
        ldx #<dm_no_drives_text
        ldy #>dm_no_drives_text
        lda #3
        jmp dm_copy_text          ; tail call
dm_build_row_drive:
        tax
        lda drive_list,x
        sta dm_number
        jsr dm_number_digits      ; -> dm_tens/dm_ones screen codes
        lda dm_tens
        sta dm_row_buf+3
        lda dm_ones
        sta dm_row_buf+4
        lda dm_index              ; model text: dm_models + index*5
        asl
        asl
        adc dm_index              ; carry clear: index < 10
        tax
        lda dm_models,x
        bne dm_build_row_model
        ldx #<dm_unknown_text     ; not recognized
        ldy #>dm_unknown_text
        lda #DM_MODEL_COL
        jsr dm_copy_text
        jmp dm_build_row_tag
dm_build_row_model:
        ldy #DM_MODEL_COL
dm_build_row_model_loop:
        lda dm_models,x           ; PETSCII digits = screen codes
        beq dm_build_row_tag
        sta dm_row_buf,y
        inx
        iny
        jmp dm_build_row_model_loop
dm_build_row_tag:
        lda dm_number
        cmp dm_current
        bne dm_build_row_done
        ldx #<dm_current_text
        ldy #>dm_current_text
        lda #DM_TAG_COL
        jmp dm_copy_text          ; tail call
dm_build_row_done:
        rts

; --- dm_copy_text: NUL-terminated screen-code text at X/Y (lo/hi)
; into dm_row_buf from column .A ---
dm_copy_text:
        stx dm_copy_text_load+1
        sty dm_copy_text_load+2
        tay
        ldx #0
dm_copy_text_loop:
dm_copy_text_load:
        lda $ffff,x
        beq dm_copy_text_done
        sta dm_row_buf,y
        inx
        iny
        jmp dm_copy_text_loop
dm_copy_text_done:
        rts

; --- dm_text_row: list row .A = the text at X/Y, no bar ---
dm_text_row:
        sta dm_text_row_n
        txa
        pha
        tya
        pha
        jsr dm_blank_row_buf
        pla
        tay
        pla
        tax
        lda #3
        jsr dm_copy_text
        lda dm_text_row_n
        jmp dm_poke_row           ; tail call

dm_clear_list:
        lda #0
        sta dm_index
dm_clear_list_loop:
        jsr dm_blank_row_buf
        lda dm_index
        jsr dm_poke_row
        inc dm_index
        lda dm_index
        cmp #DM_LIST_ROWS
        bne dm_clear_list_loop
        rts

dm_blank_row_buf:
        lda #$20
        ldx #(DM_INNER-1)
dm_blank_row_buf_loop:
        sta dm_row_buf,x
        dex
        bpl dm_blank_row_buf_loop
        rts

; --- dm_poke_row: dm_row_buf -> the interior of list row .A ---
dm_poke_row:
        tax
        lda dm_row_lo,x
        sta dm_poke_row_store+1
        lda dm_row_hi,x
        sta dm_poke_row_store+2
        ldx #(DM_INNER-1)
dm_poke_row_loop:
        lda dm_row_buf,x
dm_poke_row_store:
        sta $ffff,x
        dex
        bpl dm_poke_row_loop
        rts

; --- dm_number_digits: dm_number (8-30) -> dm_tens/dm_ones, screen
; codes, the tens a blank for 8 and 9 ---
dm_number_digits:
        lda dm_number
        ldx #0
dm_number_digits_tens:
        cmp #10
        bcc dm_number_digits_done
        sbc #10                   ; carry set from the cmp
        inx
        jmp dm_number_digits_tens
dm_number_digits_done:
        ora #$30
        sta dm_ones
        txa
        beq dm_number_digits_blank
        ora #$30
        sta dm_tens
        rts
dm_number_digits_blank:
        lda #$20
        sta dm_tens
        rts

; --- dm_data_drive: .A = the data drive -- CFG_DATA_DRIVE, or the
; client's own drive while that's 0 (none chosen yet) ---
dm_data_drive:
dm_cfg_get:
        lda $ffff                 ; CFG_DATA_DRIVE (dm_module_start aims it)
        bne dm_data_drive_done
        jsr current_drive_to_x
        txa
dm_data_drive_done:
        rts

; --- dm_save_config: SCRATCH + SAVE TADA64.CFG on the client's drive,
; then read the error channel -- keymap_menu.asm's key_save/scratch_
; keymap_file, minus the popup bookkeeping. Out: X/Y = the status
; message, "Data drive NN" plus how the save went. ---
dm_save_config:
        lda #0
        sta dm_save_failed
{ifdef: c128}
        ldx #0                    ; 128: filenames and the SAVE's data in
        jsr SETBNK                ; bank 0 (.A = 0 too) -- the C64 has no
{endif}                           ; banks
        jsr select_drive          ; disk.asm -- the client's drive, or
        bcc dm_save_config_drive  ; the first one on the bus
        ldx #<dm_no_drive_suffix  ; none at all: the choice still holds
        ldy #>dm_no_drive_suffix  ; for this session, just not saved
        jmp dm_build_msg          ; tail call
dm_save_config_drive:
        lda #DM_SCRATCH_LEN       ; SCRATCH the old file first, then a
        ldx #<dm_scratch_command  ; plain SAVE (see keymap_menu.asm's
        ldy #>dm_scratch_command  ; key_save on why not "@0:")
        jsr DSK_SETNAM
        jsr current_drive_to_x
        lda #DSK_CMD_CHANNEL
        ldy #DSK_CMD_CHANNEL
        jsr DSK_SETLFS
        jsr DSK_OPEN
        lda #DSK_CMD_CHANNEL      ; CLOSE takes the file number in .A
        jsr DSK_CLOSE
        lda #DM_FILENAME_LEN
        ldx #<dm_filename
        ldy #>dm_filename
        jsr DSK_SETNAM
        jsr current_drive_to_x
        lda #2
        ldy #1
        jsr DSK_SETLFS
        lda KEYMAP_TABLE_PTR      ; SAVE wants a zero-page pointer to the
        sta DM_SAVE_PTR           ; start (same $fb/$fc keymap_menu.asm
        lda KEYMAP_TABLE_PTR+1    ; uses -- never both loaded at once)
        sta DM_SAVE_PTR+1
        lda KEYMAP_TABLE_PTR      ; end = start + CONFIG_FILE_SIZE
        clc
        adc #<CONFIG_FILE_SIZE
        tax
        lda KEYMAP_TABLE_PTR+1
        adc #>CONFIG_FILE_SIZE
        tay
        lda #DM_SAVE_PTR
        jsr DM_KERNAL_SAVE
        rol dm_save_failed        ; KERNAL error (carry) -> bit 0
        jsr read_error_channel    ; the drive's verdict (26 WRITE PROTECT
        rol dm_save_failed        ; ON, 72 DISK FULL, ...) -- and its LED
        ldx #<dm_saved_suffix
        ldy #>dm_saved_suffix
        lda dm_save_failed
        and #$03
        beq dm_build_msg
        ldx #<dm_error_suffix
        ldy #>dm_error_suffix
        ; fall through

; --- dm_build_msg: dm_msg_buf = "Data drive " + dm_number + the
; NUL-terminated suffix at X/Y. Out: X/Y = dm_msg_buf. ---
dm_build_msg:
        stx dm_build_msg_load+1
        sty dm_build_msg_load+2
        ldy #0
dm_build_msg_prefix:
        lda dm_msg_prefix,y
        beq dm_build_msg_number
        sta dm_msg_buf,y
        iny
        jmp dm_build_msg_prefix
dm_build_msg_number:
        jsr dm_number_digits      ; clobbers .A/.X only
        lda dm_tens
        cmp #$20                  ; no blank in front of 8 or 9
        beq dm_build_msg_ones
        sta dm_msg_buf,y
        iny
dm_build_msg_ones:
        lda dm_ones
        sta dm_msg_buf,y
        iny
        ldx #0
dm_build_msg_suffix:
dm_build_msg_load:
        lda $ffff,x
        sta dm_msg_buf,y
        beq dm_build_msg_done     ; the NUL is copied too
        inx
        iny
        jmp dm_build_msg_suffix
dm_build_msg_done:
        ldx #<dm_msg_buf
        ldy #>dm_msg_buf
        rts

; --- dm_draw_frame: box, title and help rows; the list rows start
; blank (dm_scan/dm_draw_list fill them) ---
dm_draw_frame:
        ldx #0                    ; white text over the whole box band
        lda #1                    ; (18 rows * 40 = 720 bytes: two
dm_draw_frame_color:              ; 256-byte pages plus 208)
        sta COLOR_RAM+DM_TOP_ROW*40,x
        sta COLOR_RAM+DM_TOP_ROW*40+256,x
        cpx #208                  ; DM_BOX_ROWS*40 - 512, by hand (see
                                  ; keymap.asm's KEYMAP_TABLE_SIZE comment)
        bcs dm_draw_frame_color_next
        sta COLOR_RAM+DM_TOP_ROW*40+512,x
dm_draw_frame_color_next:
        inx
        bne dm_draw_frame_color
        lda #0
        sta dm_index
dm_draw_frame_row:
        ldx dm_index              ; which row image goes on this row
        lda dm_frame_rows,x
        asl
        tax
        lda dm_frame_images,x
        sta dm_draw_frame_load+1
        lda dm_frame_images+1,x
        sta dm_draw_frame_load+2
        ldx dm_index
        lda dm_screen_lo,x
        sta dm_draw_frame_store+1
        lda dm_screen_hi,x
        sta dm_draw_frame_store+2
        ldx #39
dm_draw_frame_copy:
dm_draw_frame_load:
        lda $ffff,x
dm_draw_frame_store:
        sta $ffff,x
        dex
        bpl dm_draw_frame_copy
        inc dm_index
        lda dm_index
        cmp #DM_BOX_ROWS
        bne dm_draw_frame_row
        rts

; Which 40-byte image each of the box's 18 rows gets: 0 top border,
; 1 title, 2 blank interior, 3/4/5 help, 6 bottom border.
dm_frame_rows:
        byte 0, 1, 2, 2,2,2,2,2,2,2,2,2,2, 2, 3, 4, 5, 6
dm_frame_images:
        word dm_top_border, dm_row_title, dm_row_blank
        word dm_row_help1, dm_row_help2, dm_row_help3, dm_bottom_border

; Start of each box row on screen (column 0), and of each list row's
; interior (column 5).
dm_screen_lo:
        byte <(POPUP_SCREEN+(DM_TOP_ROW+0)*40), <(POPUP_SCREEN+(DM_TOP_ROW+1)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+2)*40), <(POPUP_SCREEN+(DM_TOP_ROW+3)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+4)*40), <(POPUP_SCREEN+(DM_TOP_ROW+5)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+6)*40), <(POPUP_SCREEN+(DM_TOP_ROW+7)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+8)*40), <(POPUP_SCREEN+(DM_TOP_ROW+9)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+10)*40), <(POPUP_SCREEN+(DM_TOP_ROW+11)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+12)*40), <(POPUP_SCREEN+(DM_TOP_ROW+13)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+14)*40), <(POPUP_SCREEN+(DM_TOP_ROW+15)*40)
        byte <(POPUP_SCREEN+(DM_TOP_ROW+16)*40), <(POPUP_SCREEN+(DM_TOP_ROW+17)*40)
dm_screen_hi:
        byte >(POPUP_SCREEN+(DM_TOP_ROW+0)*40), >(POPUP_SCREEN+(DM_TOP_ROW+1)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+2)*40), >(POPUP_SCREEN+(DM_TOP_ROW+3)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+4)*40), >(POPUP_SCREEN+(DM_TOP_ROW+5)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+6)*40), >(POPUP_SCREEN+(DM_TOP_ROW+7)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+8)*40), >(POPUP_SCREEN+(DM_TOP_ROW+9)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+10)*40), >(POPUP_SCREEN+(DM_TOP_ROW+11)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+12)*40), >(POPUP_SCREEN+(DM_TOP_ROW+13)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+14)*40), >(POPUP_SCREEN+(DM_TOP_ROW+15)*40)
        byte >(POPUP_SCREEN+(DM_TOP_ROW+16)*40), >(POPUP_SCREEN+(DM_TOP_ROW+17)*40)
dm_row_lo:
        byte <(POPUP_SCREEN+(DM_LIST_TOP+0)*40+5), <(POPUP_SCREEN+(DM_LIST_TOP+1)*40+5)
        byte <(POPUP_SCREEN+(DM_LIST_TOP+2)*40+5), <(POPUP_SCREEN+(DM_LIST_TOP+3)*40+5)
        byte <(POPUP_SCREEN+(DM_LIST_TOP+4)*40+5), <(POPUP_SCREEN+(DM_LIST_TOP+5)*40+5)
        byte <(POPUP_SCREEN+(DM_LIST_TOP+6)*40+5), <(POPUP_SCREEN+(DM_LIST_TOP+7)*40+5)
        byte <(POPUP_SCREEN+(DM_LIST_TOP+8)*40+5), <(POPUP_SCREEN+(DM_LIST_TOP+9)*40+5)
dm_row_hi:
        byte >(POPUP_SCREEN+(DM_LIST_TOP+0)*40+5), >(POPUP_SCREEN+(DM_LIST_TOP+1)*40+5)
        byte >(POPUP_SCREEN+(DM_LIST_TOP+2)*40+5), >(POPUP_SCREEN+(DM_LIST_TOP+3)*40+5)
        byte >(POPUP_SCREEN+(DM_LIST_TOP+4)*40+5), >(POPUP_SCREEN+(DM_LIST_TOP+5)*40+5)
        byte >(POPUP_SCREEN+(DM_LIST_TOP+6)*40+5), >(POPUP_SCREEN+(DM_LIST_TOP+7)*40+5)
        byte >(POPUP_SCREEN+(DM_LIST_TOP+8)*40+5), >(POPUP_SCREEN+(DM_LIST_TOP+9)*40+5)

dm_entry_sp:        byte 0
dm_key:             byte 0
dm_count:           byte 0        ; drives listed (drive_count, max 10)
dm_selected:        byte 0        ; list index under the bar
dm_current:         byte 0        ; the current drive's number
dm_index:           byte 0
dm_out:             byte 0
dm_number:          byte 0
dm_tens:            byte 0
dm_ones:            byte 0
dm_text_row_n:      byte 0
dm_msg_ptr:         word 0
dm_save_failed:     byte 0
dm_msg_buf:         area 40, 0
dm_row_buf:         area DM_INNER, $20
dm_models:          area (DM_LIST_ROWS*DM_MODEL_SIZE), 0

; Box rows: real PETSCII line-drawing screen codes via `byte`/`area`
; (never inside `ascii` -- see config_menu.asm's top_border comment for
; why), label text via {alpha:pokealt}, the lowercase charset's screen
; codes. 40 bytes each.
{alpha:pokealt}
dm_top_border:
        byte $20,$20,$20,$20, $70
        area 30, $40
        byte $6e, $20,$20,$20,$20
dm_row_title:
        byte $20,$20,$20,$20, $5d
        ascii "         Select Drive         "
        byte $5d, $20,$20,$20,$20
dm_row_blank:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20
dm_row_help1:
        byte $20,$20,$20,$20, $5d
        ascii " Crsr Up/Down: select drive   "
        byte $5d, $20,$20,$20,$20
dm_row_help2:
        byte $20,$20,$20,$20, $5d
        ascii " Return: use   R: scan again  "
        byte $5d, $20,$20,$20,$20
dm_row_help3:
        byte $20,$20,$20,$20, $5d
        ascii " Stop: cancel                 "
        byte $5d, $20,$20,$20,$20
dm_bottom_border:
        byte $20,$20,$20,$20, $6d
        area 30, $40
        byte $7d, $20,$20,$20,$20

dm_scanning_text:
        ascii "Scanning..."
        byte 0
dm_no_drives_text:
        ascii "No drives found."
        byte 0
dm_unknown_text:
        ascii "Unknown"
        byte 0
dm_current_text:
        ascii "(current)"
        byte 0
dm_cancel_msg:
        ascii "Data drive unchanged."
        byte 0
dm_msg_prefix:
        ascii "Data drive "
        byte 0
dm_saved_suffix:
        ascii " saved."
        byte 0
dm_no_drive_suffix:
        ascii " (not saved: no drive)"
        byte 0
dm_error_suffix:
        ascii " (not saved: disk error)"
        byte 0
{alpha:normal}

; "S0:TADA64.CFG" and "TADA64.CFG" share the filename bytes, as in
; keymap_menu.asm. {alpha:alt}: a disk directory's uppercase letters are
; $C1-$DA (see keymap.asm's filename-block comment).
{alpha:alt}
dm_scratch_command:
        ascii "S0:"
dm_filename:
{ifndef: c128}
        ascii "TADA64.CFG"
{endif}
{ifdef: c128}
        ascii "TADA128.CFG"
{endif}
dm_filename_end:
{alpha:normal}
DM_SCRATCH_LEN  = dm_filename_end - dm_scratch_command  ; 13 (14 on the 128)
DM_FILENAME_LEN = dm_filename_end - dm_filename         ; 10 (11)
