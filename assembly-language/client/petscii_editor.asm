; petscii_editor.asm — loadable PETSCII banner/screen editor overlay.
;
; Not resident: LOADed on demand by tada-client.asm's load_petscii_editor
; (KERNAL LOAD "PETSCII.ED",8,1) once a canvas stream is confirmed
; starting, and discarded (just overwritten by whatever loads at
; OVERLAY_BUF next) once this returns control via JT_RESUME. Keeps this
; screen editor's code+buffers out of memory during ordinary play/talk/
; movement sessions, where they're dead weight -- see tada-client.asm's
; own comment on load_petscii_editor for the fuller rationale, and
; Ryan's call to split the client into loadable sub-modules rather than
; grow tada-client.asm itself indefinitely.
;
; Talks to the same resident SwiftLink plumbing (sl_send/sl_recv) via
; the fixed low-page jump table tada-client.asm's init_jump_table
; populates at boot ($0340 = JT_SL_SEND, $0343 = JT_SL_RECV, $0346 =
; JT_RESUME) rather than depending on this resident program's own
; routine addresses, which shift every time tada-client.asm is edited.
;
; Wire format on entry: the caller has already consumed CANVAS_STREAM_
; START+CANVAS_STREAM_CONFIRM (that's what triggered this module to
; load in the first place) -- what's left arriving is the 16-bit
; length prefix, then 960 PETSCII char bytes, then 960 color bytes
; (0-15), matching petscii_editor/canvas.py's encode_download() on the
; server -- the canvas itself is 40x24 (row 24 of the physical screen
; is reserved for the status line, see CELLS' own comment), not the
; full 40x25 physical screen. Saving re-sends the same shape (fresh
; START+CONFIRM+length header, since this is a new, separate stream
; back the other way) -- see upload_canvas.
;
; Local editing keeps two parallel copies of the grid: CHAR_BUF/COLOR_BUF
; (this module's own buffers, the ones actually uploaded) and the C64's
; real SCREEN_RAM/COLOR_RAM (what's visibly drawn) -- kept in sync on
; every edit rather than re-deriving one from the other, since SCREEN_RAM
; needs PETSCII->screen-code converted glyphs (petscii_to_screen) plus a
; reverse-video cursor overlay, neither of which belong in the buffers
; that actually get uploaded.

; SCREEN_RAM/COLOR_RAM/CHROUT/GETIN are macro_preprocessor.py built-ins
; (C64_CONSTANTS) -- no {const:} needed for those here.

; Must match tada-client.asm's own JT_BASE-relative constants exactly --
; there's no shared include for these today, so a change to one side's
; jump table layout has to be mirrored here by hand.
{const: JT_SL_SEND $0340}
{const: JT_SL_RECV $0343}
{const: JT_RESUME  $0346}

; Must match petscii_editor/canvas.py's STREAM_START/STREAM_CONFIRM --
; used here only for the upload (save) direction; the download header
; was already consumed by tada-client.asm before this module loaded.
{const: CANVAS_STREAM_START   $01}
{const: CANVAS_STREAM_CONFIRM $42}
{const: CANVAS_STREAM_CANCEL  $43}

; GETIN codes for the help overlay -- BEST GUESS, NOT YET VERIFIED LIVE
; (this session's own experience with F1 says don't trust a remembered
; key code without checking: real hardware/VICE keymaps can differ from
; the "standard" PETSCII table). $08 matches the common ASCII/ANSI-
; terminal CTRL-H convention, which some VICE keymaps also extend to
; C64 CTRL+letter combos even though the stock KERNAL keyboard decode
; table doesn't define anything for CTRL+regular-letter keys on real
; hardware. $5f is back-arrow (←) unshifted, standard PETSCII.
; Adjust these two constants once confirmed against a real session --
; that's the only thing that needs to change, since both are used only
; here and in the editor_keys table entry below.
{const: HELP_KEY       $08}
{const: HELP_EXIT_KEY  $5f}

; Progress-bar sizing: row 24 (the last screen row) is an 8-char label
; ("LOADING "/"SAVING  ") followed by a 32-cell bar, one cell per
; PROGRESS_BYTES_PER_DOT bytes actually transferred. 1920 total bytes
; (960 chars + 960 colors) / 32 cells = 60 exactly, so the bar always
; reaches exactly full right as the real transfer finishes.
{const: PROGRESS_BYTES_PER_DOT $3c}

; Canvas cells: 40x24, not the full 40x25 physical screen -- row 24 is
; carved out and reserved for draw_status_line's persistent display
; (current color, cursor row/col), Ryan's ask after noticing the editor
; drew no status line at all. copy_1000/fill_1000 (key_help's full-
; screen backup/restore) still need the whole physical screen including
; the status row, so they use SCREEN_CELLS, not CELLS, for their own
; byte count.
CELLS = 960
SCREEN_CELLS = 1000

; Reuses tada-client.asm's own scr_ptr_lo/scr_ptr_hi zero-page bytes
; ($fb/$fc) -- already proven safe under this exact "interrupts enabled,
; chained into the stock KERNAL IRQ" execution environment by the
; resident program's own init_screen/display_char use of them. Safe to
; reuse here too: this module runs to completion before control ever
; returns to resident code, never concurrently with it.
scr_ptr_lo = $fb
scr_ptr_hi = $fc

        orig $2000

module_start:
        jsr recv_length_prefix   ; discarded -- always exactly 1920 for a
                                   ; 40x24 canvas; nothing to branch on

        ; Show a progress bar on the still-visible leftover screen (from
        ; before this module loaded) while the 1920-byte body streams in
        ; -- recv_chars/recv_colors fill CHAR_BUF/COLOR_BUF only, not
        ; SCREEN_RAM, so nothing real is on screen yet to protect; the
        ; whole screen gets cleared and repainted from the buffers right
        ; after anyway, which naturally erases the bar too.
        lda #<LOAD_LABEL
        sta scr_ptr_lo
        lda #>LOAD_LABEL
        sta scr_ptr_hi
        jsr progress_init

        jsr recv_chars
        jsr recv_colors

        lda #$93                 ; PETSCII clear screen
        jsr CHROUT

        jsr paint_chars
        jsr paint_colors

        lda #0
        sta cur_row
        sta cur_col
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_startup_status_line  ; version/help banner -- the first
                                        ; real edit action (any handler in
                                        ; editor_keys) overwrites this with
                                        ; draw_status_line's live color/
                                        ; position display, same handoff
                                        ; tada-client.asm's own status line
                                        ; doesn't need since it's never
                                        ; replaced by anything dynamic

edit_loop:
        jsr GETIN
        cmp #0
        beq edit_loop            ; nothing typed yet

        jsr dispatch_editor_key  ; jumps straight into the matching
                                  ; handler and never returns if found;
                                  ; carry clear on return means no match
        bcs edit_loop            ; unreachable (see above) -- kept only
                                  ; so a future edit can't accidentally
                                  ; fall through past a real match

        ; The same +/-127-byte branch-range bug the F1/dispatch_editor_key
        ; comment above describes just recurred here (Ryan caught it live:
        ; CTRL-4 for cyan crashed straight back to READY) -- this file has
        ; grown enough since that fix (the progress bar, help screen, etc)
        ; that a plain `bcs key_color` (348 bytes away, confirmed via the
        ; .sym file) silently assembled to a wrong branch target again,
        ; same as edit_save/edit_cancel/key_delete did before. Fixed the
        ; same way: a short/local branch (guaranteed in range -- it only
        ; needs to skip the 3-byte jmp right below it) plus a real `jmp`
        ; (no range limit) for the actual far target.
        jsr lookup_color_code    ; carry set + .a = color# (0-15) if this
        bcc edit_loop_not_color  ; short/local branch -- safe
        jmp key_color            ; jmp, not a branch -- no range limit
edit_loop_not_color:
        jmp key_type             ; anything else: place it as a character

; --- Table-driven special-key dispatch ---
; Was a chain of `cmp #code / beq handler` -- broke because several
; handlers (edit_save, edit_cancel, key_delete) landed more than the
; 6502's +/-127-byte branch range away from here once the file grew
; (confirmed live: c64list assembled it with 0 errors/warnings anyway,
; silently producing a wrong branch target instead of erroring on the
; out-of-range offset -- F1 was landing on essentially a random nearby
; address instead of edit_save). A table + indirect `jmp` (same idiom
; tada-client.asm's irq_dispatch_next already uses for its round-robin
; task table) has no range limit at all, so this can't recur as the file
; keeps growing.
;
; Input: .a = key code (already confirmed nonzero by edit_loop)
; Output: carry set (jumped to the matching handler -- never actually
; returns) or carry clear + .a preserved (no match, fall through to
; color-code lookup then key_type).
dispatch_editor_key:
        sta dispatch_key
        ldx #0
dispatch_editor_key_loop:
        cpx #EDITOR_KEYS_END
        beq dispatch_editor_key_miss    ; short/local branch -- safe
        lda editor_keys,x
        cmp dispatch_key
        beq dispatch_editor_key_hit     ; short/local branch -- safe
        txa
        clc
        adc #3
        tax
        jmp dispatch_editor_key_loop    ; jmp, not a branch -- no range limit
dispatch_editor_key_hit:
        lda editor_keys+1,x
        sta dispatch_editor_key_jmp+1
        lda editor_keys+2,x
        sta dispatch_editor_key_jmp+2
dispatch_editor_key_jmp:
        jmp $ffff                        ; self-modified -- see above
dispatch_editor_key_miss:
        lda dispatch_key
        clc
        rts

dispatch_key:
        byte 0

; code, handler-address-lo, handler-address-hi -- 3 bytes/entry.
editor_keys:
        byte $85                  ; F1 -- save
        word edit_save
        byte $03                  ; RUN/STOP -- ask "cancel edit? (y/n)"
        word edit_cancel_confirm  ; first, not edit_cancel directly
        byte $91                  ; cursor up
        word key_up
        byte $11                  ; cursor down
        word key_down
        byte $9d                  ; cursor left
        word key_left
        byte $1d                  ; cursor right
        word key_right
        byte $0d                  ; RETURN -- next line
        word key_return
        byte $14                  ; DEL -- backspace-erase
        word key_delete
        byte HELP_KEY              ; CTRL-H -- help screen
        word key_help
EDITOR_KEYS_END = * - editor_keys ; auto-sized -- current PC minus the
                                   ; table's own start address, so adding/
                                   ; removing an entry can't desync this
                                   ; from a hand-maintained count

key_up:
        jsr undraw_cursor
        lda cur_row
        beq key_up_done           ; already at row 0, clamp
        dec cur_row
key_up_done:
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_status_line
        jmp edit_loop

key_down:
        jsr undraw_cursor
        lda cur_row
        cmp #23                   ; last canvas row -- row 24 is the
                                    ; reserved status line, not editable
        beq key_down_done         ; already at row 23, clamp
        inc cur_row
key_down_done:
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_status_line
        jmp edit_loop

key_left:
        jsr undraw_cursor
        lda cur_col
        beq key_left_done         ; already at col 0, clamp
        dec cur_col
key_left_done:
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_status_line
        jmp edit_loop

key_right:
        jsr undraw_cursor
        lda cur_col
        cmp #39
        beq key_right_done        ; already at col 39, clamp
        inc cur_col
key_right_done:
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_status_line
        jmp edit_loop

key_return:
        jsr undraw_cursor
        lda #0
        sta cur_col
        lda cur_row
        cmp #23                   ; last canvas row, see key_down
        beq key_return_done
        inc cur_row
key_return_done:
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_status_line
        jmp edit_loop

key_delete:
        jsr undraw_cursor
        lda cur_col
        bne key_delete_left
        lda cur_row
        beq key_delete_done       ; already at 0,0 -- nowhere to go
        dec cur_row
        lda #39
        sta cur_col
        jmp key_delete_erase
key_delete_left:
        dec cur_col
key_delete_erase:
        jsr recompute_offset
        lda #$20                  ; PETSCII space
        jsr store_char_at_cursor
key_delete_done:
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_status_line
        jmp edit_loop

; --- Help overlay ---
; Backs up the real SCREEN_RAM/COLOR_RAM (not CHAR_BUF/COLOR_BUF -- the
; canvas being edited is untouched by any of this), paints a static
; help screen over it, waits for HELP_EXIT_KEY, then restores exactly
; what was there before and falls back into the ordinary edit loop.
; undraw_cursor first so the backup doesn't capture the reverse-video
; cursor glyph as if it were real canvas content.
key_help:
        jsr undraw_cursor

        lda #<SCREEN_RAM
        sta copy_src_lo
        lda #>SCREEN_RAM
        sta copy_src_hi
        lda #<BACKUP_CHARS
        sta copy_dst_lo
        lda #>BACKUP_CHARS
        sta copy_dst_hi
        jsr copy_1000
        lda #<COLOR_RAM
        sta copy_src_lo
        lda #>COLOR_RAM
        sta copy_src_hi
        lda #<BACKUP_COLORS
        sta copy_dst_lo
        lda #>BACKUP_COLORS
        sta copy_dst_hi
        jsr copy_1000

        jsr draw_help_screen

key_help_wait:
        jsr GETIN
        cmp #0
        beq key_help_wait
        cmp #HELP_EXIT_KEY
        bne key_help_wait

        lda #<BACKUP_CHARS
        sta copy_src_lo
        lda #>BACKUP_CHARS
        sta copy_src_hi
        lda #<SCREEN_RAM
        sta copy_dst_lo
        lda #>SCREEN_RAM
        sta copy_dst_hi
        jsr copy_1000
        lda #<BACKUP_COLORS
        sta copy_src_lo
        lda #>BACKUP_COLORS
        sta copy_src_hi
        lda #<COLOR_RAM
        sta copy_dst_lo
        lda #>COLOR_RAM
        sta copy_dst_hi
        jsr copy_1000

        jsr draw_cursor
        jmp edit_loop

; .a = color# (0-15) from lookup_color_code -- applies to the cell under
; the cursor without moving it or touching the character glyph, and
; also becomes current_color: the color newly typed/erased cells get
; from here on (see store_char_at_cursor) and what draw_status_line
; displays -- Ryan's ask, so the cursor "draws" in whatever color was
; last selected instead of leaving color memory untouched by typing.
key_color:
        sta color_temp            ; calc_color_buf_ptr/calc_color_ram_ptr
                                    ; both clobber .a internally
        sta current_color
        jsr calc_color_buf_ptr
        ldy #0
        lda color_temp
        sta (scr_ptr_lo),y
        jsr calc_color_ram_ptr
        ldy #0
        lda color_temp
        sta (scr_ptr_lo),y
        jsr draw_status_line
        jmp edit_loop

; .a = the typed PETSCII byte -- store it at the cursor, advance, redraw.
key_type:
        jsr store_char_at_cursor
        lda cur_col
        cmp #39
        beq key_type_next_row
        inc cur_col
        jmp key_type_done
key_type_next_row:
        lda cur_row
        cmp #23                   ; last canvas row, see key_down
        beq key_type_done          ; already at the last cell -- stay put
        inc cur_row
        lda #0
        sta cur_col
key_type_done:
        jsr recompute_offset
        jsr draw_cursor
        jsr draw_status_line
        jmp edit_loop

; --- Save/cancel: the real "oddity with saving" bug ---
; This module draws the canvas straight into SCREEN_RAM via its own
; scr_ptr_lo/hi pointer (calc_screen_ptr) and never once touches the
; KERNAL's own text-cursor tracking ($d1-$d6 etc) that CHROUT/display_char
; rely on -- that cursor has sat frozen wherever it was the instant
; before this module loaded (typically mid-way through the "banner edit
; <name>" command line the player typed). Returning to JT_RESUME without
; resetting it meant the server's "Banner saved." text (sent via ordinary
; CHROUT/display_char) landed at that frozen position -- usually
; somewhere in the middle of the just-edited canvas -- instead of
; anywhere sensible. Fix: clear the screen (PETSCII $93 also homes the
; KERNAL cursor) right before handing control back, on both the save and
; cancel paths, so the prompt loop always resumes on a clean, correctly-
; tracked screen.
edit_save:
        lda #<SAVE_LABEL
        sta scr_ptr_lo
        lda #>SAVE_LABEL
        sta scr_ptr_hi
        jsr progress_init         ; safe to draw straight onto SCREEN_RAM --
                                    ; upload_canvas reads from CHAR_BUF/
                                    ; COLOR_BUF, never back from SCREEN_RAM,
                                    ; and the screen gets cleared below the
                                    ; moment the upload finishes regardless
        jsr upload_canvas
        lda #$93                  ; clear screen + home KERNAL cursor
        jsr CHROUT
        jmp JT_RESUME

; --- RUN/STOP confirmation: "CANCEL EDIT? (Y/N)" on row 24 ---
; Ryan's call: RUN/STOP shouldn't discard an edit in progress with no
; chance to back out (a single stray RUN/STOP keypress previously threw
; away everything unconditionally). Row 24 is draw_status_line's real,
; currently-displayed status content during ordinary editing (not canvas
; content -- row 24 is reserved and never part of CHAR_BUF/COLOR_BUF,
; see CELLS' own comment) -- so unlike progress_init, this backs the row
; up first and restores it on anything but Y, the same undraw/backup/
; restore shape key_help already uses for the whole screen, just scoped
; to one row. No need to re-run draw_status_line on the restore path --
; the backed-up bytes already are the status line, byte for byte.
edit_cancel_confirm:
        jsr undraw_cursor
        ldx #0
ecc_backup_loop:
        lda SCREEN_RAM+960,x
        sta cancel_backup_chars,x
        lda COLOR_RAM+960,x
        sta cancel_backup_colors,x
        inx
        cpx #40
        bne ecc_backup_loop

        ldy #0
ecc_prompt_loop:
        lda cancel_prompt_msg,y
        sta SCREEN_RAM+960,y
        lda #2                    ; red -- attention-grabbing, distinct
        sta COLOR_RAM+960,y        ; from the progress bar's cyan/white
        iny
        cpy #40
        bne ecc_prompt_loop

ecc_wait:
        jsr GETIN
        cmp #0
        beq ecc_wait
        and #$7f                  ; shifted letters are unshifted+$80 (Y
                                    ; unshifted=$59, shifted=$d9) -- clearing
                                    ; bit 7 folds either case to $59 in one
                                    ; compare, catching both with a single
                                    ; branch (Ryan's fix: the original two-
                                    ; branch version compared against $79,
                                    ; which isn't shifted-Y at all -- PETSCII
                                    ; shift doesn't move letters into the
                                    ; $61-$7a range, only $c1-$da)
        cmp #$59                  ; 'Y', either case
        beq edit_cancel

        ; anything else: restore row 24 exactly and resume editing
        ldx #0
ecc_restore_loop:
        lda cancel_backup_chars,x
        sta SCREEN_RAM+960,x
        lda cancel_backup_colors,x
        sta COLOR_RAM+960,x
        inx
        cpx #40
        bne ecc_restore_loop
        jsr draw_cursor
        jmp edit_loop

; edit_cancel used to send nothing at all -- confirmed live (border-tick
; diagnostic showed RUN/STOP genuinely dispatching here) that the real
; problem was the server side: banner_edit.py sat in its
; readexactly(HEADER_LEN) for the full UPLOAD_TIMEOUT_SECONDS (15
; minutes) waiting for an upload that was never coming, so the client's
; own prompt_loop -> wait_for_data correctly went back to waiting for
; the next server message, which didn't arrive for 15 minutes -- looked
; identical to a hang. Fix: send a real cancel marker, the same 4-byte
; shape as a genuine save header (START+CANCEL+00+00) so banner_edit.py's
; existing single readexactly(HEADER_LEN) call completes immediately
; either way -- see petscii_editor/canvas.py's STREAM_CANCEL comment.
edit_cancel:
        lda #CANVAS_STREAM_START
        jsr JT_SL_SEND
        lda #CANVAS_STREAM_CANCEL
        jsr JT_SL_SEND
        lda #0
        jsr JT_SL_SEND
        jsr JT_SL_SEND
        lda #$93                  ; same cursor-desync fix as edit_save --
        jsr CHROUT                 ; see that routine's comment
        jmp JT_RESUME

; --- Cursor position bookkeeping ---
; cur_row/cur_col are the source of truth; cur_offset_lo/hi (0-999) is
; derived from them via row_offsets (a lookup table, not a multiply --
; avoids needing a real 16-bit multiply routine for cur_row*40) plus
; cur_col.
recompute_offset:
        lda cur_row
        asl                       ; row*2 -- row_offsets is a word table
        tax
        lda row_offsets,x
        clc
        adc cur_col
        sta cur_offset_lo
        lda row_offsets+1,x
        adc #0
        sta cur_offset_hi
        rts

; --- Store .a (a PETSCII byte) into CHAR_BUF at the cursor and paint it
; (plain, not reversed) onto the real screen -- also paints current_color
; into COLOR_BUF/COLOR_RAM at the same cell (Ryan's ask: typing/erasing
; should draw in whatever color was last selected via key_color, not
; leave color memory untouched). Used by both key_type (typed characters)
; and key_delete (erasing with a space), so both draw in current_color. ---
store_char_at_cursor:
        pha
        jsr calc_char_buf_ptr
        ldy #0
        pla
        sta (scr_ptr_lo),y
        pha
        jsr petscii_to_screen
        jsr calc_screen_ptr
        ldy #0
        sta (scr_ptr_lo),y

        lda current_color
        sta color_temp             ; calc_color_buf_ptr/calc_color_ram_ptr
                                     ; both clobber .a internally
        jsr calc_color_buf_ptr
        ldy #0
        lda color_temp
        sta (scr_ptr_lo),y
        jsr calc_color_ram_ptr
        ldy #0
        lda color_temp
        sta (scr_ptr_lo),y

        pla
        rts

; --- Draw/undraw the cursor at the CURRENT cur_offset ---
; Screen codes $00-$7f have a pre-inverted twin at +$80 in the character
; ROM, so "reverse video" is just ORA #$80 on the already-converted
; screen code -- no color-RAM changes needed, matching how the real C64
; screen editor's own cursor works.
draw_cursor:
        jsr calc_char_ptr_and_load  ; .a = raw PETSCII byte under cursor
        jsr petscii_to_screen
        ora #$80
        jsr calc_screen_ptr
        ldy #0
        sta (scr_ptr_lo),y
        rts

undraw_cursor:
        jsr calc_char_ptr_and_load
        jsr petscii_to_screen
        jsr calc_screen_ptr
        ldy #0
        sta (scr_ptr_lo),y
        rts

; .a = CHAR_BUF[cur_offset] on return
calc_char_ptr_and_load:
        jsr calc_char_buf_ptr
        ldy #0
        lda (scr_ptr_lo),y
        rts

; --- Pointer calculators: scr_ptr_lo/hi = BASE + cur_offset ---
calc_char_buf_ptr:
        lda cur_offset_lo
        clc
        adc #<CHAR_BUF
        sta scr_ptr_lo
        lda cur_offset_hi
        adc #>CHAR_BUF
        sta scr_ptr_hi
        rts

calc_color_buf_ptr:
        lda cur_offset_lo
        clc
        adc #<COLOR_BUF
        sta scr_ptr_lo
        lda cur_offset_hi
        adc #>COLOR_BUF
        sta scr_ptr_hi
        rts

calc_screen_ptr:
        pha
        lda cur_offset_lo
        clc
        adc #<SCREEN_RAM
        sta scr_ptr_lo
        lda cur_offset_hi
        adc #>SCREEN_RAM
        sta scr_ptr_hi
        pla
        rts

calc_color_ram_ptr:
        lda cur_offset_lo
        clc
        adc #<COLOR_RAM
        sta scr_ptr_lo
        lda cur_offset_hi
        adc #>COLOR_RAM
        sta scr_ptr_hi
        rts

; --- PETSCII byte -> screen code (C64 character-ROM index) ---
; Standard piecewise mapping (c64-wiki's PETSCII/screen-code tables) --
; unverified against real hardware/VICE by this session (flagged in the
; feature's plan notes); a wrong range here only affects how a glyph
; *looks* while editing, not the raw PETSCII byte round-tripped to the
; server, so it's safe to fix later without touching the wire format.
petscii_to_screen:
        cmp #$20
        bcc pts_add80             ; < $20: control codes -> +$80
        cmp #$40
        bcc pts_same              ; $20-$3f: unchanged
        cmp #$60
        bcc pts_sub40             ; $40-$5f: -$40
        cmp #$80
        bcc pts_sub20             ; $60-$7f: -$20
        cmp #$a0
        bcc pts_sub80             ; $80-$9f: -$80 (mirrors $00-$1f glyphs)
        cmp #$c0
        bcc pts_sub40             ; $a0-$bf: -$40 (mirrors $60-$7f glyphs)
        cmp #$ff
        beq pts_pi
        jmp pts_sub80             ; $c0-$fe (except $ff, handled above): -$80
pts_pi:
        lda #$5e
        rts
pts_same:
        rts
pts_add80:
        clc
        adc #$80
        rts
pts_sub20:
        sec
        sbc #$20
        rts
pts_sub40:
        sec
        sbc #$40
        rts
pts_sub80:
        sec
        sbc #$80
        rts

; --- Recognise a PETSCII color-select control byte ---
; Input: .a = byte from GETIN. Output: carry set + .a = color# (0-15)
; if it matched one of the 16 known color codes (same raw values as
; formatting.py's PETSCII_CONTROL_CODES, in the same order as
; petscii_editor/canvas.py's COLOR_NUMBER_TO_TOKEN); carry clear
; (.a unchanged) otherwise.
lookup_color_code:
        ldy #0
lcc_loop:
        cpy #16
        beq lcc_not_found
        cmp color_codes,y
        beq lcc_found
        iny
        jmp lcc_loop
lcc_found:
        tya
        sec
        rts
lcc_not_found:
        clc
        rts

; --- General-purpose 1000-byte memory copy ---
; Unlike the bulk-transfer helpers below (each doing a byte-by-byte
; *transform* -- PETSCII<->screen-code conversion, or a wire read/write
; -- which is why those are written out individually rather than
; shared), this is a plain, untransformed copy: one real reusable
; subroutine, not a macro (c64list has no macro parameters, but an
; ordinary JSR with input variables works fine here). Used by the help
; overlay to back up/restore SCREEN_RAM+COLOR_RAM.
;
; Input: copy_src_lo/hi = source base address, copy_dst_lo/hi = dest
; base address. Copies exactly SCREEN_CELLS (1000) bytes -- the whole
; physical screen including the status row, not just CELLS (960)
; canvas cells; key_help's backup/restore needs the status line
; preserved too.
copy_1000:
        lda copy_src_lo
        sta copy_src_load+1
        lda copy_src_hi
        sta copy_src_load+2
        lda copy_dst_lo
        sta copy_dst_store+1
        lda copy_dst_hi
        sta copy_dst_store+2
        lda #<SCREEN_CELLS
        sta copy_remaining_lo
        lda #>SCREEN_CELLS
        sta copy_remaining_hi
copy_1000_loop:
copy_src_load:
        lda $ffff
copy_dst_store:
        sta $ffff
        inc copy_src_load+1
        bne copy_src_no_carry
        inc copy_src_load+2
copy_src_no_carry:
        inc copy_dst_store+1
        bne copy_dst_no_carry
        inc copy_dst_store+2
copy_dst_no_carry:
        lda copy_remaining_lo
        bne copy_dec_lo
        dec copy_remaining_hi
copy_dec_lo:
        dec copy_remaining_lo
        lda copy_remaining_lo
        ora copy_remaining_hi
        bne copy_1000_loop
        rts

; --- General-purpose 1000-byte fill ---
; Input: fill_dst_lo/hi = dest base address, fill_value = byte to write
; to every one of SCREEN_CELLS (1000) bytes -- see copy_1000's own
; comment on why this is SCREEN_CELLS, not CELLS: draw_help_screen fills
; the whole physical screen (status row included), which key_help then
; fully restores from its own SCREEN_CELLS-sized backup afterward.
fill_1000:
        lda fill_dst_lo
        sta fill_1000_store+1
        lda fill_dst_hi
        sta fill_1000_store+2
        lda #<SCREEN_CELLS
        sta fill_remaining_lo
        lda #>SCREEN_CELLS
        sta fill_remaining_hi
fill_1000_loop:
        lda fill_value
fill_1000_store:
        sta $ffff
        inc fill_1000_store+1
        bne fill_1000_no_carry
        inc fill_1000_store+2
fill_1000_no_carry:
        lda fill_remaining_lo
        bne fill_dec_lo
        dec fill_remaining_hi
fill_dec_lo:
        dec fill_remaining_lo
        lda fill_remaining_lo
        ora fill_remaining_hi
        bne fill_1000_loop
        rts

; --- Progress bar (row 24, the last screen row) ---
; Shown while a canvas download/upload streams in/out (module_start,
; edit_save) -- 2000 bytes at 38400 baud takes long enough that showing
; nothing at all looked like a hang (Ryan's report: "some oddity with
; saving"). Pokes straight into SCREEN_RAM/COLOR_RAM: safe during a
; download (nothing real is on screen yet -- recv_chars/recv_colors fill
; CHAR_BUF/COLOR_BUF only, and the whole screen is cleared+repainted from
; them right after) and safe during a save (upload_canvas reads from
; CHAR_BUF/COLOR_BUF, never back from SCREEN_RAM, and edit_save clears
; the screen the moment the upload finishes regardless -- see its own
; comment on the cursor-desync fix).
;
; progress_init: input scr_ptr_lo/hi (caller-set, same zero-page pointer
; calc_char_buf_ptr etc. use -- (zp),y indirect addressing needs a real
; zero-page pointer, and this file's convention is to reuse scr_ptr_lo/hi
; for whatever the current operation needs rather than claim a second
; zero-page pair for it) = address of an 8-byte {alpha:poke} label
; (LOAD_LABEL or SAVE_LABEL). Pokes the label into columns 0-7, blanks
; columns 8-39 (the bar), resets progress_col/progress_counter.
;
; Label uses white (1) rather than the bar's cyan (3) -- a first guess
; at fixing an earlier live report that the label never showed up,
; before the real cause (progress_col initialized to 0 instead of 8,
; below) was found: the bar's own first dots were landing on top of the
; label and eating through it before it was ever visible, nothing to do
; with color/contrast at all. Left as white anyway since it's a fine
; choice regardless, just not the fix.
progress_init:
        ldy #0
progress_init_label_loop:
        lda (scr_ptr_lo),y
        sta SCREEN_RAM+960,y
        lda #1                     ; white -- see comment above
        sta COLOR_RAM+960,y
        iny
        cpy #8
        bne progress_init_label_loop
        ldx #8
progress_init_bar_loop:
        lda #$20                   ; PETSCII/screen-code space (blank cell)
        sta SCREEN_RAM+960,x
        lda #3
        sta COLOR_RAM+960,x
        inx
        cpx #40
        bne progress_init_bar_loop
        lda #8                     ; bar starts at column 8, past the label
                                     ; -- real bug, not a contrast issue:
                                     ; this was 0 before, so progress_tick's
                                     ; very first dots landed on top of the
                                     ; label (columns 0-7) and ate through
                                     ; it before it was ever visible, which
                                     ; is why only the bar ever seemed to
                                     ; show up
        sta progress_col
        lda #0
        sta progress_counter
        rts

; progress_tick: call once per byte actually transferred. Every
; PROGRESS_BYTES_PER_DOT bytes, lights the next bar cell (columns
; 8-39) with a solid reverse-space block, until the bar is full --
; cpx #40 stops it from writing past column 39 if more bytes arrive
; than the bar has cells for (rounding slop, see PROGRESS_BYTES_PER_DOT's
; own comment).
progress_tick:
        inc progress_counter
        lda progress_counter
        cmp #PROGRESS_BYTES_PER_DOT
        bne progress_tick_done
        lda #0
        sta progress_counter
        ldx progress_col
        cpx #40
        beq progress_tick_done
        lda #$a0                   ; reverse-video space -- solid block
        sta SCREEN_RAM+960,x
        inc progress_col
progress_tick_done:
        rts

; --- Startup status-line banner ---
; Shown once, right when the editor first draws the canvas -- a version/
; help hint instead of the color/position display draw_status_line
; normally shows, since there's nothing to report yet (cursor is at
; 0,0, no color chosen beyond the default). Overwritten by the first
; real draw_status_line call once the player does anything (see
; module_start's own comment on the handoff).
;
; Null-terminated + runtime-padded rather than a fixed 40-byte string,
; same reasoning as tada-client.asm's update_status_line/status_msg:
; {usedef:__BuildDate}'s expansion length isn't known at the point this
; comment is written, so there's no compile-time constant to size
; against. cpy #40 bounds both the copy and the pad loop, so a longer-
; than-expected build-date string degrades to a truncated line instead
; of overrunning past column 39 into row 25 (which doesn't exist).
; Padded with plain spaces (not update_status_line's reverse-video
; space) to match this status line's own plain-white convention.
draw_startup_status_line:
        ldy #0
dssl_copy:
        lda startup_status_msg,y
        beq dssl_pad
        sta SCREEN_RAM+960,y
        lda #1                     ; white
        sta COLOR_RAM+960,y
        iny
        cpy #40
        bne dssl_copy
        rts
dssl_pad:
        lda #$20
        sta SCREEN_RAM+960,y
        lda #1
        sta COLOR_RAM+960,y
        iny
        cpy #40
        bne dssl_pad
        rts

; --- Status line (row 24, reserved -- see CELLS' own comment) ---
; Shows the current draw color (as a hex digit whose own on-screen color
; matches current_color, doubling as a swatch) plus the cursor's row/
; column. Redrawn after every cursor move, type/erase, and color change
; -- see edit_loop's various handlers. Pokes straight into SCREEN_RAM/
; COLOR_RAM, never touches CHAR_BUF/COLOR_BUF -- row 24 was carved out
; of the canvas specifically so this can own it outright, the same way
; the progress bar/cancel-prompt already borrow it for their own
; on-screen-only content (and don't need to call this afterward: the
; help overlay restores row 24 byte-for-byte via its whole-screen
; backup, and the cancel prompt restores its own row-24-only backup the
; same way -- see those routines' own comments).
;
; Layout (40 columns): "COLOR:" + 1 hex digit + " ROW:" + 2 digits +
; " COL:" + 2 digits, then blank-padded to column 39.
draw_status_line:
        ldy #0
dsl_label_loop:
        lda status_color_label,y
        sta SCREEN_RAM+960,y
        lda #1                     ; white
        sta COLOR_RAM+960,y
        iny
        cpy #6                     ; "COLOR:"
        bne dsl_label_loop

        ldx current_color
        lda hex_chars,x
        sta SCREEN_RAM+966
        lda current_color          ; the digit's own color IS the swatch
        sta COLOR_RAM+966

        lda #$20
        sta SCREEN_RAM+967
        lda #1
        sta COLOR_RAM+967

        ldy #0
dsl_row_label_loop:
        lda status_row_label,y
        sta SCREEN_RAM+968,y
        lda #1
        sta COLOR_RAM+968,y
        iny
        cpy #4                     ; "ROW:"
        bne dsl_row_label_loop

        lda cur_row
        jsr byte_to_decimal2
        stx SCREEN_RAM+972
        sty SCREEN_RAM+973
        lda #1
        sta COLOR_RAM+972
        sta COLOR_RAM+973

        lda #$20
        sta SCREEN_RAM+974
        lda #1
        sta COLOR_RAM+974

        ldy #0
dsl_col_label_loop:
        lda status_col_label,y
        sta SCREEN_RAM+975,y
        lda #1
        sta COLOR_RAM+975,y
        iny
        cpy #4                     ; "COL:"
        bne dsl_col_label_loop

        lda cur_col
        jsr byte_to_decimal2
        stx SCREEN_RAM+979
        sty SCREEN_RAM+980
        lda #1
        sta COLOR_RAM+979
        sta COLOR_RAM+980

        ldx #0                     ; blank the remaining columns 21-39
dsl_blank_loop:
        lda #$20
        sta SCREEN_RAM+981,x
        lda #1
        sta COLOR_RAM+981,x
        inx
        cpx #19
        bne dsl_blank_loop
        rts

; --- .a (0-39) -> two decimal-digit screen codes ---
; Small values only (cur_row max 23, cur_col max 39) -- a plain
; repeated-subtraction loop against 10 is plenty, no need for a general
; divide routine.
; Output: .x = tens digit screen code, .y = ones digit screen code.
byte_to_decimal2:
        ldx #0
btd_tens_loop:
        cmp #10
        bcc btd_tens_done
        sec
        sbc #10
        inx
        jmp btd_tens_loop
btd_tens_done:
        tay                        ; .y = ones value (0-9), raw not char yet
        lda decimal_chars,x
        tax                        ; .x = tens digit screen code (final)
        lda decimal_chars,y
        tay                        ; .y = ones digit screen code (final)
        rts

; --- Fixed-width (40-byte) line poke ---
; Copies exactly 40 bytes from poke_src_lo/hi to poke_dst_lo/hi -- one
; screen row's worth. Unlike copy_1000/fill_1000, a plain X-indexed loop
; is enough here (0-39 never crosses a page boundary in a way that needs
; the self-modified-high-byte trick those two need for 1000 bytes).
; Input: poke_src_lo/hi = source (a 40-byte help_* line, space-padded),
; poke_dst_lo/hi = dest (SCREEN_RAM + row*40).
poke_line:
        lda poke_src_lo
        sta poke_line_load+1
        lda poke_src_hi
        sta poke_line_load+2
        lda poke_dst_lo
        sta poke_line_store+1
        lda poke_dst_hi
        sta poke_line_store+2
        ldx #0
poke_line_loop:
poke_line_load:
        lda $ffff,x
poke_line_store:
        sta $ffff,x
        inx
        cpx #40
        bne poke_line_loop
        rts

; --- Draw the static help screen ---
; Clears to blank/white first (fill_1000 x2), then pokes each 40-char
; help_line_N over SCREEN_RAM (COLOR_RAM is left at the white fill --
; no per-line color needed for a plain help screen).
draw_help_screen:
        lda #<SCREEN_RAM
        sta fill_dst_lo
        lda #>SCREEN_RAM
        sta fill_dst_hi
        lda #$20                  ; PETSCII space
        sta fill_value
        jsr fill_1000
        lda #<COLOR_RAM
        sta fill_dst_lo
        lda #>COLOR_RAM
        sta fill_dst_hi
        lda #1                    ; white
        sta fill_value
        jsr fill_1000

        lda #<help_line1
        sta poke_src_lo
        lda #>help_line1
        sta poke_src_hi
        lda #<(SCREEN_RAM+40*1)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+40*1)
        sta poke_dst_hi
        jsr poke_line

        lda #<help_line2
        sta poke_src_lo
        lda #>help_line2
        sta poke_src_hi
        lda #<(SCREEN_RAM+40*3)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+40*3)
        sta poke_dst_hi
        jsr poke_line

        lda #<help_line3
        sta poke_src_lo
        lda #>help_line3
        sta poke_src_hi
        lda #<(SCREEN_RAM+40*4)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+40*4)
        sta poke_dst_hi
        jsr poke_line

        lda #<help_line4
        sta poke_src_lo
        lda #>help_line4
        sta poke_src_hi
        lda #<(SCREEN_RAM+40*5)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+40*5)
        sta poke_dst_hi
        jsr poke_line

        lda #<help_line5
        sta poke_src_lo
        lda #>help_line5
        sta poke_src_hi
        lda #<(SCREEN_RAM+40*6)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+40*6)
        sta poke_dst_hi
        jsr poke_line

        lda #<help_line6
        sta poke_src_lo
        lda #>help_line6
        sta poke_src_hi
        lda #<(SCREEN_RAM+40*8)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+40*8)
        sta poke_dst_hi
        jsr poke_line
        rts

; --- Bulk transfer helpers ---
; Each does a straight-line 1000-byte copy via a self-modified store (or
; load) operand -- c64list has no macro parameters, so these are written
; out individually rather than shared
; via a generic parameterised routine (matches this file's and tada-
; client.asm's existing preference for explicit code).

recv_length_prefix:
        jsr JT_SL_RECV
        bcc recv_length_prefix    ; len_lo -- discarded, always 1000+1000
recv_length_prefix_hi:
        jsr JT_SL_RECV
        bcc recv_length_prefix_hi
        rts

recv_chars:
        lda #<CHAR_BUF
        sta rc_store+1
        lda #>CHAR_BUF
        sta rc_store+2
        lda #<CELLS
        sta rc_remaining_lo
        lda #>CELLS
        sta rc_remaining_hi
rc_loop:
        jsr JT_SL_RECV
        bcc rc_loop
rc_store:
        sta $ffff
        jsr progress_tick
        inc rc_store+1
        bne rc_no_carry
        inc rc_store+2
rc_no_carry:
        lda rc_remaining_lo
        bne rc_dec_lo
        dec rc_remaining_hi
rc_dec_lo:
        dec rc_remaining_lo
        lda rc_remaining_lo
        ora rc_remaining_hi
        bne rc_loop
        rts

recv_colors:
        lda #<COLOR_BUF
        sta rl_store+1
        lda #>COLOR_BUF
        sta rl_store+2
        lda #<CELLS
        sta rl_remaining_lo
        lda #>CELLS
        sta rl_remaining_hi
rl_loop:
        jsr JT_SL_RECV
        bcc rl_loop
rl_store:
        sta $ffff
        jsr progress_tick
        inc rl_store+1
        bne rl_no_carry
        inc rl_store+2
rl_no_carry:
        lda rl_remaining_lo
        bne rl_dec_lo
        dec rl_remaining_hi
rl_dec_lo:
        dec rl_remaining_lo
        lda rl_remaining_lo
        ora rl_remaining_hi
        bne rl_loop
        rts

; Copies CHAR_BUF -> SCREEN_RAM, converting each byte via
; petscii_to_screen on the way (plain, not reversed -- the cursor
; overlay is applied separately by draw_cursor once painting is done).
paint_chars:
        lda #<CHAR_BUF
        sta pc_load+1
        lda #>CHAR_BUF
        sta pc_load+2
        lda #<SCREEN_RAM
        sta pc_store+1
        lda #>SCREEN_RAM
        sta pc_store+2
        lda #<CELLS
        sta pc_remaining_lo
        lda #>CELLS
        sta pc_remaining_hi
pc_loop:
pc_load:
        lda $ffff
        jsr petscii_to_screen
pc_store:
        sta $ffff
        inc pc_load+1
        bne pc_load_no_carry
        inc pc_load+2
pc_load_no_carry:
        inc pc_store+1
        bne pc_store_no_carry
        inc pc_store+2
pc_store_no_carry:
        lda pc_remaining_lo
        bne pc_dec_lo
        dec pc_remaining_hi
pc_dec_lo:
        dec pc_remaining_lo
        lda pc_remaining_lo
        ora pc_remaining_hi
        bne pc_loop
        rts

; Copies COLOR_BUF -> COLOR_RAM directly (color# 0-15 values are already
; real color-RAM values, no conversion needed).
paint_colors:
        lda #<COLOR_BUF
        sta pl_load+1
        lda #>COLOR_BUF
        sta pl_load+2
        lda #<COLOR_RAM
        sta pl_store+1
        lda #>COLOR_RAM
        sta pl_store+2
        lda #<CELLS
        sta pl_remaining_lo
        lda #>CELLS
        sta pl_remaining_hi
pl_loop:
pl_load:
        lda $ffff
pl_store:
        sta $ffff
        inc pl_load+1
        bne pl_load_no_carry
        inc pl_load+2
pl_load_no_carry:
        inc pl_store+1
        bne pl_store_no_carry
        inc pl_store+2
pl_store_no_carry:
        lda pl_remaining_lo
        bne pl_dec_lo
        dec pl_remaining_hi
pl_dec_lo:
        dec pl_remaining_lo
        lda pl_remaining_lo
        ora pl_remaining_hi
        bne pl_loop
        rts

; --- Save: send a fresh STREAM_START+CONFIRM+length header, then
; CHAR_BUF then COLOR_BUF, straight over JT_SL_SEND. ---
upload_canvas:
        lda #CANVAS_STREAM_START
        jsr JT_SL_SEND
        lda #CANVAS_STREAM_CONFIRM
        jsr JT_SL_SEND
        lda #<(CELLS*2)
        jsr JT_SL_SEND
        lda #>(CELLS*2)
        jsr JT_SL_SEND

        lda #<CHAR_BUF
        sta uc_load+1
        lda #>CHAR_BUF
        sta uc_load+2
        lda #<CELLS
        sta uc_remaining_lo
        lda #>CELLS
        sta uc_remaining_hi
uc_char_loop:
uc_load:
        lda $ffff
        jsr JT_SL_SEND
        jsr progress_tick
        inc uc_load+1
        bne uc_char_no_carry
        inc uc_load+2
uc_char_no_carry:
        lda uc_remaining_lo
        bne uc_char_dec_lo
        dec uc_remaining_hi
uc_char_dec_lo:
        dec uc_remaining_lo
        lda uc_remaining_lo
        ora uc_remaining_hi
        bne uc_char_loop

        lda #<COLOR_BUF
        sta uc_load2+1
        lda #>COLOR_BUF
        sta uc_load2+2
        lda #<CELLS
        sta uc_remaining_lo
        lda #>CELLS
        sta uc_remaining_hi
uc_color_loop:
uc_load2:
        lda $ffff
        jsr JT_SL_SEND
        jsr progress_tick
        inc uc_load2+1
        bne uc_color_no_carry
        inc uc_load2+2
uc_color_no_carry:
        lda uc_remaining_lo
        bne uc_color_dec_lo
        dec uc_remaining_hi
uc_color_dec_lo:
        dec uc_remaining_lo
        lda uc_remaining_lo
        ora uc_remaining_hi
        bne uc_color_loop
        rts

; --- Data ---

cur_row:
        byte 0
cur_col:
        byte 0
cur_offset_lo:
        byte 0
cur_offset_hi:
        byte 0
color_temp:
        byte 0

; The color# (0-15) applied to newly typed/erased cells and shown by
; draw_status_line -- set by key_color, read by store_char_at_cursor.
; Defaults to white (1), same default as a freshly-cleared C64 screen
; (BLANK_COLOR in petscii_editor/canvas.py) -- this module is freshly
; LOADed from disk each time the editor opens, so this static default
; is a real runtime reset, not just an assembly-time value.
current_color:
        byte 1

rc_remaining_lo:
        byte 0
rc_remaining_hi:
        byte 0
rl_remaining_lo:
        byte 0
rl_remaining_hi:
        byte 0
pc_remaining_lo:
        byte 0
pc_remaining_hi:
        byte 0
pl_remaining_lo:
        byte 0
pl_remaining_hi:
        byte 0
uc_remaining_lo:
        byte 0
uc_remaining_hi:
        byte 0

; progress_init/progress_tick's own state -- see those routines' comments.
progress_col:
        byte 0
progress_counter:
        byte 0

; copy_1000/fill_1000/poke_line's own input/scratch variables -- see
; those routines' own comments.
copy_src_lo:
        byte 0
copy_src_hi:
        byte 0
copy_dst_lo:
        byte 0
copy_dst_hi:
        byte 0
copy_remaining_lo:
        byte 0
copy_remaining_hi:
        byte 0
fill_dst_lo:
        byte 0
fill_dst_hi:
        byte 0
fill_value:
        byte 0
fill_remaining_lo:
        byte 0
fill_remaining_hi:
        byte 0
poke_src_lo:
        byte 0
poke_src_hi:
        byte 0
poke_dst_lo:
        byte 0
poke_dst_hi:
        byte 0

; Same raw byte values as formatting.py's PETSCII_CONTROL_CODES 16-color
; palette, in the same order as petscii_editor/canvas.py's
; COLOR_NUMBER_TO_TOKEN (index into this table == C64 color# 0-15).
color_codes:
        byte 144, 5, 28, 159, 156, 30, 31, 158
        byte 129, 149, 150, 151, 152, 153, 154, 155

; row_offsets[row] = row*40, as 16-bit words -- avoids needing a real
; multiply routine for recompute_offset. Only 24 entries (rows 0-23) --
; row 24 is the reserved status line, never a valid cur_row value (see
; CELLS' own comment and key_down/key_return's #23 clamp).
row_offsets:
        word 0
        word 40
        word 80
        word 120
        word 160
        word 200
        word 240
        word 280
        word 320
        word 360
        word 400
        word 440
        word 480
        word 520
        word 560
        word 600
        word 640
        word 680
        word 720
        word 760
        word 800
        word 840
        word 880
        word 920

; 960-byte buffers -- the master copy of the canvas actually uploaded
; on save (40x24; row 24 is the status line, not part of these). Initial
; content here is irrelevant (recv_chars/recv_colors overwrite both in
; full before anything reads them) -- reserved via c64list's `area`
; pseudo-op rather than literal zero bytes.
CHAR_BUF:
        area 960, 0

COLOR_BUF:
        area 960, 0

; Backs up the real SCREEN_RAM/COLOR_RAM while the help overlay is shown
; (see key_help) -- unrelated to CHAR_BUF/COLOR_BUF above, which hold
; the actual canvas being edited and are never touched by the help
; screen at all.
BACKUP_CHARS:
        area 1000, 0

BACKUP_COLORS:
        area 1000, 0

; edit_cancel_confirm's row-24 backup -- just the one row (40 bytes each),
; unlike BACKUP_CHARS/COLORS above which back up the whole screen for the
; help overlay.
cancel_backup_chars:
        area 40, 0
cancel_backup_colors:
        area 40, 0

; edit_cancel_confirm's prompt, 40 chars exactly (fixed-width row-24
; poke, same {alpha:poke} reasoning as LOAD_LABEL/SAVE_LABEL/help_line1-6
; below -- needs to already be screen codes at assembly time).
{alpha:poke}
cancel_prompt_msg:
        ascii "CANCEL EDIT? (Y/N)                      "
{alpha:normal}

; Help screen text, 40 chars each (poke_line copies a fixed 40 bytes,
; so every line must be space-padded to exactly that width). {alpha:poke}
; converts standard-case ASCII straight into screen POKE codes -- these
; are poked directly into SCREEN_RAM, not sent through petscii_to_screen
; at display time like CHAR_BUF's contents are, so they need to already
; be screen codes at assembly time. Reset to {alpha:normal} right after,
; same reason petscii_editor_filename's own {alpha:alt} block in tada-
; client.asm resets afterward -- this must not leak into anything else
; that uses `ascii` later in the file.
; progress_init's two labels -- 8 chars exactly (poked straight into
; SCREEN_RAM columns 0-7, same {alpha:poke} reasoning as help_line1-6
; below: these need to already be screen codes at assembly time, not run
; through petscii_to_screen at display time).
{alpha:poke}
LOAD_LABEL:
        ascii "LOADING "
SAVE_LABEL:
        ascii "SAVING  "
{alpha:normal}

; draw_status_line's labels/digit tables -- same {alpha:poke} reasoning
; as LOAD_LABEL/SAVE_LABEL above (poked straight into SCREEN_RAM, not
; run through petscii_to_screen). hex_chars/decimal_chars are indexed
; by value (0-15 / 0-9), not copied as fixed-width strings like the
; three labels.
{alpha:poke}
status_color_label:
        ascii "COLOR:"
status_row_label:
        ascii "ROW:"
status_col_label:
        ascii "COL:"
hex_chars:
        ascii "0123456789ABCDEF"
decimal_chars:
        ascii "0123456789"
{alpha:normal}

; draw_startup_status_line's one-time banner. Ryan asked for "PetSCII
; editor version {usedef:__BuildDate}. Ctrl-H for help" verbatim, but
; that's 52+ characters against a 40-column row (__BuildDate alone
; currently expands to a 10-character date) -- shortened to fit while
; keeping the actual version/help content, in the same ALL-CAPS
; poke-mode convention as every other on-screen label in this file
; (status_msg in tada-client.asm does the same for its own __BuildDate
; use). Null-terminated -- see draw_startup_status_line's own comment.
{alpha:poke}
startup_status_msg:
        ascii "PETSCII v"
        ascii {usedef:__BuildDate}
        ascii " CTRL-H FOR HELP"
        byte 0
{alpha:normal}

{alpha:poke}
help_line1:
        ascii "PETSCII EDITOR HELP                     "
help_line2:
        ascii "CURSOR KEYS: MOVE   DEL: BACKSPACE      "
help_line3:
        ascii "RETURN: NEXT LINE                       "
help_line4:
        ascii "CTRL/CMDRE + 1-8: SET COLOR             "
help_line5:
        ascii "F1: SAVE   RUN/STOP: CANCEL             "
help_line6:
        ascii "PRESS <- (BACK ARROW) TO RETURN         "
{alpha:normal}
