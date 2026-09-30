; --- screen-output.asm ---
; The client's own character output: cursor, PETSCII -> screen code
; conversion, colors, reverse video and the handful of control codes the
; server (or this client) actually sends -- replacing KERNAL CHROUT/PLOT
; for everything that lands on the screen. Ryan's call, 2026-09-28, after
; the "lost lines" bug: CHROUT's screen editor keeps its own bookkeeping
; (the LDTB1 line-link table, PNT/PNTR/TBLX/LNMX, quote mode) that this
; client's raw double-buffered scroll never updated, and every desync
; between the two showed up as a different-looking screen bug (lost
; lines after a wrapped line, CRSR LEFT jumping rows, quote mode turning
; control codes into glyphs). Owning the cursor outright removes that
; whole class instead of patching each symptom.
;
; Pulled into tada-client.asm via {include:screen-output_pp.asm}, same
; mechanism as screen-handler.asm. Labels resolve globally across the
; include, so this uses tada-client.asm's front_hi, row_offsets,
; COLOR_RAM, copy_block, the STATUS_ROW/DIALOGUE_LAST_ROW/PROMPT_ROW
; layout constants, term_scroll_advance and redraw_status_row directly.
;
; Screen model:
;   rows 0..dlg_last_row         dialogue area, scrolled by
;                                term_scroll_advance
;   sbar_row                   the status bar -- the cursor never sits
;                                here
;   rows sbar_row+1..24        the input area: the prompt and the
;                                player's typing (relocate_prompt_to_row24)
; Normally sbar_row = STATUS_ROW (23), dlg_last_row = DIALOGUE_LAST_
; ROW (22) and the input area is just PROMPT_ROW (24). When the typed
; line wraps off row 24 the input area grows a row -- the status bar
; moves up one, taking the dialogue area's bottom row with it (Ryan's
; ask, 2026-09-28: two input lines instead of the line splitting around
; the status bar) -- and it shrinks back when the line is submitted or a
; new prompt is pinned (input_area_collapse). STATUS_ROW_FLOOR bounds
; the growth: three input rows always hold a prompt plus MAX_LINE.
;
; A CR (or cursor-down) on the dialogue area's last row scrolls the
; dialogue area and lands on a fresh last row. Wrapping past column 39
; happens immediately, like the KERNAL's, so a line of exactly 40
; characters followed by a CR still leaves one blank row.
;
; No zero page: every indirect store uses self-modified absolute,Y
; operands instead (scr_ptr_lo/hi is shared and keymap_dispatch already
; has to save/restore it around its own use).
;
; Plain `=` constants only -- macro_preprocessor.py's {const:} values
; from tada-client.asm aren't visible to this file's own pass.

SO_TEXT_COLOR = $0286           ; KERNAL's current-text-color byte, kept
                                  ; as ours too -- start: already saves/
                                  ; restores it around stop_hint_msg
STATUS_ROW_FLOOR = 21           ; highest the status bar ever moves (a
                                  ; 3-row input area, rows 22-24)

; --- Cursor and layout state ---
crsr_row:
        byte 0
crsr_col:
        byte 0
so_rvs:
        byte 0                   ; $80 while RVS ON, else 0 (ORed into
                                  ; each screen code)
sbar_row:
        byte STATUS_ROW
dlg_last_row:
        byte DIALOGUE_LAST_ROW

; Where dialogue text continues while the cursor is off in the input
; area (dlg_cursor_save/_restore). input_in_area is 1 while the prompt
; and the player's typing live in the input area rather than inline in
; the dialogue (set by relocate_prompt_to_row24, cleared by
; commit_input_line).
dlg_row:
        byte 0
dlg_col:
        byte 0
input_in_area:
        byte 0

; --- so_row_addr: row .A -> so_row_lo/so_row_hi (front screen buffer) and
; so_color_hi (COLOR_RAM, same low byte -- both are page-aligned) ---
; Clobbers .A/.X.
so_row_addr:
        asl
        tax
        lda row_offsets,x
        sta so_row_lo
        lda row_offsets+1,x
        tax
        clc
        adc front_hi
        sta so_row_hi
        txa
        clc
        adc #>COLOR_RAM
        sta so_color_hi
        rts

so_row_lo:
        byte 0
so_row_hi:
        byte 0
so_color_hi:
        byte 0

; --- term_chrout: print .A at the cursor ---
; Preserves .A/.X/.Y (callers index strings with X or Y across a run of
; these, e.g. print_msg, and read back .A afterward -- display_char via
; capture_line_byte).
term_chrout:
        stx term_saved_x
        sty term_saved_y
        pha
        jsr so_chrout
        pla
        ldx term_saved_x
        ldy term_saved_y
        rts

term_saved_x:
        byte 0
term_saved_y:
        byte 0

so_chrout:
        cmp #$20
        bcc so_control           ; $00-$1f
        cmp #$80
        bcc so_printable         ; $20-$7f
        cmp #$a0
        bcc so_control           ; $80-$9f
so_printable:
        jsr so_petscii_to_screen
        ora so_rvs
        jsr so_poke
        jmp so_advance

; Control codes: the 16 color codes set SO_TEXT_COLOR, a small table of
; others dispatch to handlers, and everything else is ignored -- including
; $0e/$8e (lower/upper case), which CHROUT used to act on by flipping
; $d018 bit 1 and pointing the VIC at COLOR_RAM instead of gothic_charset
; (the 2026-09-28 striped-screen bug; this client is always in the one
; charset it has).
so_control:
        ldx #15
so_color_scan:
        cmp so_color_codes,x
        beq so_color_found
        dex
        bpl so_color_scan
        ldx #SO_CTL_COUNT-1
so_ctl_scan:
        cmp so_ctl_codes,x
        beq so_ctl_found
        dex
        bpl so_ctl_scan
        rts
so_color_found:
        stx SO_TEXT_COLOR        ; table index == VIC color number
        rts
so_ctl_found:
        lda so_ctl_lo,x          ; table + jmp rather than a cmp/beq chain:
        sta so_ctl_jmp+1         ; c64list doesn't range-check branches
        lda so_ctl_hi,x          ; (see project memory), and the handlers
        sta so_ctl_jmp+2         ; are spread well past +/-127 bytes
so_ctl_jmp:
        jmp $ffff

; PETSCII color codes, indexed by the VIC color number they select.
so_color_codes:
        byte $90, $05, $1c, $9f, $9c, $1e, $1f, $9e
        byte $81, $95, $96, $97, $98, $99, $9a, $9b

SO_CTL_COUNT = 11
so_ctl_codes:
        byte $0d, $8d, $93, $13, $12, $92, $1d, $9d, $11, $91, $14
so_ctl_lo:
        byte <so_ctl_cr, <so_ctl_cr, <so_ctl_clear, <so_ctl_home
        byte <so_ctl_rvs_on, <so_ctl_rvs_off, <term_cursor_right
        byte <term_cursor_left, <so_ctl_down, <so_ctl_up, <so_ctl_del
so_ctl_hi:
        byte >so_ctl_cr, >so_ctl_cr, >so_ctl_clear, >so_ctl_home
        byte >so_ctl_rvs_on, >so_ctl_rvs_off, >term_cursor_right
        byte >term_cursor_left, >so_ctl_down, >so_ctl_up, >so_ctl_del

; --- so_petscii_to_screen: .A (a printable PETSCII code, $20-$7f or
; $a0-$ff) -> screen code, the same mapping CHROUT uses ---
so_petscii_to_screen:
        cmp #$40
        bcc so_p2s_rts           ; $20-$3f: unchanged
        cmp #$60
        bcc so_p2s_sub40         ; $40-$5f -> $00-$1f
        cmp #$80
        bcc so_p2s_sub20         ; $60-$7f -> $40-$5f
        cmp #$c0
        bcc so_p2s_sub40         ; $a0-$bf -> $60-$7f
        cmp #$ff
        beq so_p2s_pi
        and #$7f                 ; $c0-$fe -> $40-$7e
so_p2s_rts:
        rts
so_p2s_sub40:
        sec
        sbc #$40
        rts
so_p2s_sub20:
        sec
        sbc #$20
        rts
so_p2s_pi:
        lda #$5e                 ; $ff is pi, same glyph as $de
        rts

; --- so_poke: store screen code .A (and SO_TEXT_COLOR) at the cursor,
; without moving it ---
so_poke:
        pha
        lda crsr_row
        jsr so_row_addr
        lda so_row_lo
        sta so_poke_scr+1
        sta so_poke_col+1
        lda so_row_hi
        sta so_poke_scr+2
        lda so_color_hi
        sta so_poke_col+2
        ldy crsr_col
        pla
so_poke_scr:
        sta $ffff,y
        lda SO_TEXT_COLOR
so_poke_col:
        sta $ffff,y
        rts

; --- so_advance: step past a just-printed character, wrapping at once
; after column 39 (like the KERNAL) ---
so_advance:
        inc crsr_col
        lda crsr_col
        cmp #40
        bcs so_wrap
        rts

; --- so_wrap: the cursor ran off the right edge ---
; In the dialogue area this is just a newline. In the input area it moves
; to the next input row, and running off row 24 grows the input area by
; a row (input_area_grow) so the line keeps reading top to bottom right
; under the status bar -- the old CHROUT version instead scrolled and
; carried on at row 22 above the first 40 characters it left on row 24,
; so stepping left off the second row walked into the dialogue history.
so_wrap:
        lda crsr_row
        cmp sbar_row
        bcc so_newline           ; dialogue area
        lda #0
        sta crsr_col
        lda crsr_row
        cmp #PROMPT_ROW
        bcs so_wrap_grow
        inc crsr_row             ; next input row
        rts
so_wrap_grow:
        lda sbar_row
        cmp #STATUS_ROW_FLOOR+1
        bcc so_wrap_full         ; already at the floor -- can't happen
                                   ; with MAX_LINE, but stay on screen
        jmp input_area_grow
so_wrap_full:
        lda #39
        sta crsr_col
        rts

; --- so_newline: column 0 of the next row, scrolling the dialogue area
; from its last row (term_scroll_advance lands on a fresh last row). A
; CR in the input area scrolls too, the same way PROMPT_ROW always has.
so_newline:
        lda #0
        sta crsr_col
so_ctl_down:
        lda crsr_row
        cmp dlg_last_row
        bcs so_newline_scroll    ; last dialogue row, or the input area
        inc crsr_row
        rts
so_newline_scroll:
        jmp term_scroll_advance

; CR (and SHIFT+CR) also turns reverse video off, as CHROUT's does.
so_ctl_cr:
        lda #0
        sta so_rvs
        jmp so_newline

so_ctl_rvs_on:
        lda #$80
        sta so_rvs
        rts

so_ctl_rvs_off:
        lda #0
        sta so_rvs
        rts

so_ctl_home:
        lda #0
        sta crsr_row
        sta crsr_col
        rts

so_ctl_up:
        lda crsr_row
        beq so_ctl_up_rts        ; already on the top row
        dec crsr_row
        lda crsr_row
        cmp sbar_row
        bne so_ctl_up_rts
        dec crsr_row             ; hop over the status bar
so_ctl_up_rts:
        rts

; DEL from the server: step back and blank that cell (no line-closing
; shift -- nothing the server sends relies on that).
so_ctl_del:
        jsr term_cursor_left
        lda #$20
        jmp so_poke

; --- so_ctl_clear: CLR -- back to the default layout, blank every row
; except the status bar, repaint the status bar (the KERNAL's clear wiped
; it until the next scroll), and home the cursor ---
so_ctl_clear:
        lda #STATUS_ROW
        sta sbar_row
        lda #DIALOGUE_LAST_ROW
        sta dlg_last_row
        lda #0
        sta input_in_area
        sta dlg_row
        sta dlg_col
        sta so_clear_row
so_clear_loop:
        lda so_clear_row
        cmp #STATUS_ROW
        beq so_clear_next
        jsr so_blank_row
so_clear_next:
        inc so_clear_row
        lda so_clear_row
        cmp #25
        bcc so_clear_loop
        jsr redraw_status_row
        jmp so_ctl_home

so_clear_row:
        byte 0

; --- so_blank_row: fill row .A with spaces in SO_TEXT_COLOR ---
so_blank_row:
        jsr so_row_addr
        lda so_row_lo
        sta so_blank_scr+1
        sta so_blank_col+1
        lda so_row_hi
        sta so_blank_scr+2
        lda so_color_hi
        sta so_blank_col+2
        ldy #39
so_blank_loop:
        lda #$20
so_blank_scr:
        sta $ffff,y
        lda SO_TEXT_COLOR
so_blank_col:
        sta $ffff,y
        dey
        bpl so_blank_loop
        rts

; --- input_area_blank: blank every input-area row (sbar_row+1..24) ---
input_area_blank:
        ldx sbar_row
        inx
        stx so_clear_row
iab_loop:
        lda so_clear_row
        jsr so_blank_row
        inc so_clear_row
        lda so_clear_row
        cmp #25
        bcc iab_loop
        rts

; --- input_area_grow: the typed line ran off row 24 -- move the status
; bar up a row and give the input area another ---
; 1. term_scroll_advance shifts the dialogue area up a row (with its own
;    double-buffered flip), leaving a fresh blank row at dlg_last_row --
;    the row the status bar is about to move into.
; 2. sbar_row/dlg_last_row step up one, and the saved dialogue cursor
;    follows its text up (the text it pointed at just moved).
; 3. The input rows below the old status bar move up one row (screen +
;    color), overwriting the old status bar, and row 24 is blanked.
; 4. The status bar is repainted at its new row; typing continues at
;    row 24 col 0.
input_area_grow:
        jsr term_scroll_advance
        dec sbar_row
        dec dlg_last_row
        lda dlg_row
        beq iag_dlg_done
        dec dlg_row
iag_dlg_done:
        ; rows sbar_row+2..24 -> sbar_row+1..23: screen, then color.
        ; Both are copies with dest 40 bytes below source, so overlap is
        ; safe with copy_block's ascending loop.
        lda sbar_row
        clc
        adc #2
        asl
        tax
        lda row_offsets,x        ; source offset within a 1K screen
        sta iag_src_lo
        lda row_offsets+1,x
        sta iag_src_hi
        sec
        lda #<1000
        sbc iag_src_lo
        sta iag_len_lo
        lda #>1000
        sbc iag_src_hi
        sta iag_len_hi
        lda front_hi
        jsr iag_copy_rows
        lda #>COLOR_RAM
        jsr iag_copy_rows
        lda #PROMPT_ROW
        jsr so_blank_row
        jsr redraw_status_row
        ldx #PROMPT_ROW
        ldy #0
        jmp so_set_cursor

; .A = base page (front_hi or >COLOR_RAM): copy iag_len bytes from
; base+iag_src to 40 bytes lower.
iag_copy_rows:
        sta iag_base
        lda iag_src_lo
        sta copy_src_lo
        lda iag_src_hi
        clc
        adc iag_base
        sta copy_src_hi
        lda copy_src_lo
        sec
        sbc #40
        sta copy_dst_lo
        lda copy_src_hi
        sbc #0
        sta copy_dst_hi
        lda iag_len_lo
        sta copy_remaining_lo
        lda iag_len_hi
        sta copy_remaining_hi
        jmp copy_block

iag_base:
        byte 0
iag_src_lo:
        byte 0
iag_src_hi:
        byte 0
iag_len_lo:
        byte 0
iag_len_hi:
        byte 0

; --- input_area_collapse: back to the one-row input area ---
; Blanks the input area, gives the rows between the old status bar and
; DIALOGUE_LAST_ROW back to the dialogue area (blank -- the dialogue
; cursor is still above them, so nothing is lost), and repaints the
; status bar at STATUS_ROW. A no-op when the input area is already one
; row. Leaves the cursor alone.
input_area_collapse:
        lda sbar_row
        cmp #STATUS_ROW
        bcs iac_rts
        lda sbar_row
        sta so_clear_row
iac_loop:
        lda so_clear_row
        jsr so_blank_row
        inc so_clear_row
        lda so_clear_row
        cmp #25
        bcc iac_loop
        lda #STATUS_ROW
        sta sbar_row
        lda #DIALOGUE_LAST_ROW
        sta dlg_last_row
        jmp redraw_status_row
iac_rts:
        rts

; --- dlg_cursor_save / dlg_cursor_restore: park and resume the dialogue
; area's own cursor around time spent in the input area ---
dlg_cursor_save:
        lda crsr_row
        sta dlg_row
        lda crsr_col
        sta dlg_col
        rts

dlg_cursor_restore:
        lda dlg_row
        sta crsr_row
        lda dlg_col
        sta crsr_col
        rts

; --- term_cursor_left / term_cursor_right: single-step cursor moves over
; text already on screen (line-editor navigation, DEL's step back,
; redraw_tail/async_step_back's walks) -- no scrolling, and the status
; bar is hopped over in both directions. Stop at the top-left and
; bottom-right corners rather than wrapping or scrolling. Leave .X/.Y
; alone.
term_cursor_left:
        lda crsr_col
        beq tcl_prev_row
        dec crsr_col
        rts
tcl_prev_row:
        lda crsr_row
        beq tcl_rts              ; top-left corner
        dec crsr_row
        lda crsr_row
        cmp sbar_row
        bne tcl_last_col
        dec crsr_row             ; hop over the status bar
tcl_last_col:
        lda #39
        sta crsr_col
tcl_rts:
        rts

term_cursor_right:
        lda crsr_col
        cmp #39
        bcs tcr_next_row
        inc crsr_col
        rts
tcr_next_row:
        lda crsr_row
        cmp #PROMPT_ROW
        bcs tcr_rts              ; bottom-right corner
        inc crsr_row
        lda crsr_row
        cmp sbar_row
        bne tcr_first_col
        inc crsr_row             ; hop over the status bar
tcr_first_col:
        lda #0
        sta crsr_col
tcr_rts:
        rts

; --- so_set_cursor / so_get_cursor: .X = row, .Y = column (same
; register order the KERNAL_PLOT calls these replaced used). Also
; reachable from overlays as JT_SET_CURSOR/JT_GET_CURSOR. ---
so_set_cursor:
        stx crsr_row
        sty crsr_col
        rts

so_get_cursor:
        ldx crsr_row
        ldy crsr_col
        rts

; --- cursor_toggle: flip the reverse-video bit of the screen code under
; the cursor, in place ---
; Doesn't move the cursor or print anything, so the real character
; underneath survives however many times this fires. Clobbers .A/.Y,
; preserves .X.
cursor_toggle:
        stx so_toggle_x
        lda crsr_row
        jsr so_row_addr
        lda so_row_lo
        sta so_toggle_ld+1
        sta so_toggle_st+1
        lda so_row_hi
        sta so_toggle_ld+2
        sta so_toggle_st+2
        ldy crsr_col
so_toggle_ld:
        lda $ffff,y
        eor #$80
so_toggle_st:
        sta $ffff,y
        ldx so_toggle_x
        rts

so_toggle_x:
        byte 0
