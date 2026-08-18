; config_menu.asm — loadable "Video Settings (C64)" popup overlay.
;
; Not resident: LOADed on demand by tada-client.asm's load_config_menu
; (KERNAL LOAD "CONFIG.MNU",8,1) once a display-settings stream is
; confirmed starting (PREFS -> Terminal Settings -> 'V', PETSCII
; connections only -- see commands/c64_display.py), and discarded once
; this returns control via JT_RESUME. Same "loadable sub-module, not
; grown into tada-client.asm" rationale as petscii_editor.asm -- see
; that file's own header comment and CLIENT_MECHANICS.md's "Loadable
; overlay modules" section.
;
; Talks to the same resident SwiftLink plumbing (sl_send/sl_recv) plus
; the shared screen-save buffer and the cursor-blink-speed setter via
; the fixed low-page jump table tada-client.asm's init_jump_table
; populates at boot -- see the {const:}s below for the exact addresses.
; Must match tada-client.asm's own JT_BASE-relative constants exactly --
; there's no shared include for these today, same caveat petscii_
; editor.asm's own copy of this comment gives.
{const: JT_SL_SEND        $0340}
{const: JT_SL_RECV        $0343}
{const: JT_RESUME         $0346}
{const: JT_SAVE_SCREEN    $0349}
{const: JT_RESTORE_SCREEN $034c}
{const: JT_SET_BLINK_MASK $034f}

; Must match commands/c64_display.py's STREAM_START/DISPLAY_STREAM_
; CONFIRM/DISPLAY_STREAM_CANCEL exactly.
{const: DISPLAY_STREAM_START   $01}
{const: DISPLAY_STREAM_CONFIRM $44}   ; 'D' -- used both for the server's
                                        ; opening trigger and this
                                        ; module's own "saved" reply
{const: DISPLAY_STREAM_CANCEL  $58}   ; 'X' -- this module's "cancelled"
                                        ; reply; unrelated to petscii_
                                        ; editor/canvas.py's own (differently
                                        ; valued) cancel byte -- different
                                        ; stream, no need to match

VIC_BORDER = $d020
VIC_BG     = $d021

; Popup box position -- must be defined before draw_popup/draw_values use
; them in address arithmetic below (unlike a label, a plain `=` constant
; isn't safe to forward-reference the way this file originally had it --
; see this bug's own fix commentary in project memory).
BOX_TOP_ROW = 6
BOX_ROWS    = 12

; SCREEN_RAM/COLOR_RAM/CHROUT/GETIN are macro_preprocessor.py built-ins
; (C64_CONSTANTS) -- no {const:} needed for those here.

        orig $2000

module_start:
        jsr JT_SAVE_SCREEN        ; back up whatever's on screen right now
                                    ; (the caller's own text -- PREFS, most
                                    ; likely) so it can be put back exactly
                                    ; as-is on exit

        jsr recv_length_prefix    ; discarded -- always exactly 3 for this
                                    ; stream (border, bg, blink)

        jsr JT_SL_RECV
recv_border_wait:
        bcc recv_border_wait
        sta cur_border
        sta orig_border

recv_bg:
        jsr JT_SL_RECV
        bcc recv_bg
        sta cur_bg
        sta orig_bg

recv_blink:
        jsr JT_SL_RECV
        bcc recv_blink
        sta cur_blink
        sta orig_blink

        lda #0
        sta selected_field

        jsr draw_popup
        jsr apply_live             ; POKE the received border/bg live, and
                                    ; set the received blink speed, so the
                                    ; popup opens already showing (and
                                    ; sounding, for blink) the player's
                                    ; actual current settings
        jsr draw_values

; --- Main input loop ---
config_loop:
        jsr demo_cursor_update    ; blink (or hold solid) the live-preview
                                    ; cursor next to the blink-speed value
                                    ; while waiting for a key, same as
                                    ; tada-client.asm's own update_cursor
                                    ; does for real keyboard input
        jsr GETIN
        cmp #0
        beq config_loop
        jsr dispatch_config_key    ; never returns on a hit (jmp's into a
                                    ; handler); falls through here on a miss
        jmp config_loop

; code, handler-address-lo, handler-address-hi -- 3 bytes/entry. Same
; table-driven dispatch shape as petscii_editor.asm's editor_keys/
; dispatch_editor_key (self-modified jmp, EDITOR_KEYS_END-style auto
; sizing) -- these GETIN codes ($91/$11/$9d/$1d/$0d/$03) are the same
; ones already confirmed live for that module's cursor keys/RETURN/
; RUN/STOP, so no new "best guess" values here.
dispatch_config_key:
        sta dispatch_key
        ldx #0
dispatch_config_key_loop:
        cpx #CONFIG_KEYS_END
        beq dispatch_config_key_miss
        lda config_keys,x
        cmp dispatch_key
        beq dispatch_config_key_hit
        txa
        clc
        adc #3
        tax
        jmp dispatch_config_key_loop
dispatch_config_key_hit:
        lda config_keys+1,x
        sta dispatch_config_key_jmp+1
        lda config_keys+2,x
        sta dispatch_config_key_jmp+2
dispatch_config_key_jmp:
        jmp $ffff
dispatch_config_key_miss:
        rts

dispatch_key:
        byte 0

config_keys:
        byte $91                  ; cursor up -- previous field
        word key_field_up
        byte $11                  ; cursor down -- next field
        word key_field_down
        byte $9d                  ; cursor left -- decrease value
        word key_value_down
        byte $1d                  ; cursor right -- increase value
        word key_value_up
        byte $0d                  ; RETURN -- save and exit
        word key_save
        byte $03                  ; RUN/STOP -- cancel and exit
        word key_cancel
CONFIG_KEYS_END = * - config_keys

key_field_up:
        lda selected_field
        beq kfu_wrap
        dec selected_field
        jmp key_field_done
kfu_wrap:
        lda #2
        sta selected_field
        jmp key_field_done

key_field_down:
        inc selected_field
        lda selected_field
        cmp #3
        bne key_field_done
        lda #0
        sta selected_field
key_field_done:
        jsr draw_values
        jmp config_loop

; .a already saved off by the caller's dispatch (not needed here) -- these
; just look at selected_field to know which of cur_border/cur_bg/cur_blink
; to touch.
key_value_up:
        lda selected_field
        cmp #0
        beq kvu_border
        cmp #1
        beq kvu_bg
        ; blink: 1-5 (5 = solid/no blink), wrap 5->1
        inc cur_blink
        lda cur_blink
        cmp #6
        bne kv_apply
        lda #1
        sta cur_blink
        jmp kv_apply
kvu_border:
        inc cur_border
        lda cur_border
        and #$0f                  ; 0-15 wraps for free -- 4-bit range
        sta cur_border
        jmp kv_apply
kvu_bg:
        inc cur_bg
        lda cur_bg
        and #$0f
        sta cur_bg
        jmp kv_apply

key_value_down:
        lda selected_field
        cmp #0
        beq kvd_border
        cmp #1
        beq kvd_bg
        ; blink: 1-5 (5 = solid/no blink), wrap 1->5
        lda cur_blink
        cmp #1
        bne kvd_blink_dec
        lda #5
        sta cur_blink
        jmp kv_apply
kvd_blink_dec:
        dec cur_blink
        jmp kv_apply
kvd_border:
        dec cur_border
        lda cur_border
        and #$0f
        sta cur_border
        jmp kv_apply
kvd_bg:
        dec cur_bg
        lda cur_bg
        and #$0f
        sta cur_bg

kv_apply:
        jsr apply_live
        jsr draw_values
        jmp config_loop

; --- Apply cur_border/cur_bg/cur_blink live (VIC-II POKEs + blink mask) ---
apply_live:
        lda cur_border
        sta VIC_BORDER
        lda cur_bg
        sta VIC_BG
        ldx cur_blink
        lda blink_masks-1,x        ; cur_blink is 1-5 -- -1 makes it a
                                    ; plain 0-based index into blink_masks
        jsr JT_SET_BLINK_MASK
        rts

; --- Live-preview cursor: blinks (or holds solid) at cur_blink's rate ---
; Ryan's ask: show the actual blink behavior, not just a number, while
; adjusting it. Column 30 of the blink-speed row (row+4) -- a plain space
; in row_field3's fixed text, immediately left of the "00" value -- is
; free real estate for this, untouched by anything else. Same shape as
; tada-client.asm's own update_cursor/cursor_toggle (jiffy-clock bit test
; via $a2, EOR #$80 to flip reverse-video in place, $00 mask = solid/
; never-off sentinel), just local to this popup and driven by cur_blink
; directly instead of the resident cursor_blink_mask -- this demo must
; keep working correctly even while the player is actively changing the
; value, before Save/Cancel ever applies it resident-side. Whatever
; reverse-video state this cell is left in in doesn't matter on exit --
; JT_RESTORE_SCREEN overwrites the whole screen from the pre-popup
; backup regardless, so there's no separate "hide it" step needed.
demo_cursor_phase:
        byte 0                    ; 0 = currently erased, 1 = currently drawn
demo_mask_scratch:
        byte 0

demo_cursor_update:
        ldx cur_blink
        lda blink_masks-1,x
        bne dcu_blinking
        ; solid (mask $00): draw once, never toggle back off
        lda demo_cursor_phase
        bne dcu_rts
        jsr demo_cursor_toggle
        lda #1
        sta demo_cursor_phase
dcu_rts:
        rts
dcu_blinking:
        sta demo_mask_scratch
        lda $a2
        and demo_mask_scratch
        beq dcu_want_off
        lda demo_cursor_phase
        bne dcu_rts
        jsr demo_cursor_toggle
        lda #1
        sta demo_cursor_phase
        rts
dcu_want_off:
        lda demo_cursor_phase
        beq dcu_rts
        jsr demo_cursor_toggle
        lda #0
        sta demo_cursor_phase
        rts

demo_cursor_toggle:
        lda SCREEN_RAM+(BOX_TOP_ROW+4)*40+30
        eor #$80
        sta SCREEN_RAM+(BOX_TOP_ROW+4)*40+30
        rts

; --- Save: send the new values back, restore the screen, hand back ---
key_save:
        lda #DISPLAY_STREAM_START
        jsr JT_SL_SEND
        lda #DISPLAY_STREAM_CONFIRM
        jsr JT_SL_SEND
        lda #3                    ; len_lo -- 3-byte body
        jsr JT_SL_SEND
        lda #0                    ; len_hi
        jsr JT_SL_SEND
        lda cur_border
        jsr JT_SL_SEND
        lda cur_bg
        jsr JT_SL_SEND
        lda cur_blink
        jsr JT_SL_SEND
        jsr JT_RESTORE_SCREEN
        jmp JT_RESUME

; --- Cancel: revert the live preview, send a cancel marker, hand back ---
key_cancel:
        lda orig_border
        sta cur_border
        lda orig_bg
        sta cur_bg
        lda orig_blink
        sta cur_blink
        jsr apply_live             ; undo whatever was being live-previewed

        lda #DISPLAY_STREAM_START
        jsr JT_SL_SEND
        lda #DISPLAY_STREAM_CANCEL
        jsr JT_SL_SEND
        lda #0                    ; len_lo -- no body
        jsr JT_SL_SEND
        lda #0                    ; len_hi
        jsr JT_SL_SEND
        jsr JT_RESTORE_SCREEN
        jmp JT_RESUME

; --- Draw the static popup box (border/title/labels/help text) ---
; Fills the whole 9-row band's COLOR_RAM to white first (one fill_bytes
; call), then pokes each 40-char row's text over SCREEN_RAM -- same
; "poke_line" shape as petscii_editor.asm's own (a separate copy: this
; module has no way to share code with that one, they're never resident
; at the same time).
draw_popup:
        lda #<(COLOR_RAM+BOX_TOP_ROW*40)
        sta fill_dst_lo
        lda #>(COLOR_RAM+BOX_TOP_ROW*40)
        sta fill_dst_hi
        lda #1                     ; white
        sta fill_value
        lda #<(BOX_ROWS*40)
        sta fill_remaining_lo
        lda #>(BOX_ROWS*40)
        sta fill_remaining_hi
        jsr fill_bytes

        lda #<top_border
        sta poke_src_lo
        lda #>top_border
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+0)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+0)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_title
        sta poke_src_lo
        lda #>row_title
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+1)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+1)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_field1
        sta poke_src_lo
        lda #>row_field1
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+2)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+2)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_field2
        sta poke_src_lo
        lda #>row_field2
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+3)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+3)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_field3
        sta poke_src_lo
        lda #>row_field3
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+4)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+4)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_blank
        sta poke_src_lo
        lda #>row_blank
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+5)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+5)*40)
        sta poke_dst_hi
        jsr poke_line

        ; row+6 is the dynamic per-field help line -- draw_values (via
        ; poke_help_line) overwrites its interior immediately after this,
        ; and again on every field/value change, so blank is just its
        ; initial state before that first happens.
        lda #<row_blank
        sta poke_src_lo
        lda #>row_blank
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+6)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+6)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_blank
        sta poke_src_lo
        lda #>row_blank
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+7)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+7)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_help1
        sta poke_src_lo
        lda #>row_help1
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+8)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+8)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_help2
        sta poke_src_lo
        lda #>row_help2
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+9)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+9)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_help3
        sta poke_src_lo
        lda #>row_help3
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+10)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+10)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<bottom_border
        sta poke_src_lo
        lda #>bottom_border
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+11)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+11)*40)
        sta poke_dst_hi
        jmp poke_line

; --- Draw the dynamic parts: field-selection marker + numeric values ---
; Column 5 of each field row (the space right after the box's left '|')
; carries the '>' marker for whichever field is selected, ' ' otherwise.
; Column 32 of each field row carries the value as two decimal digits.
draw_values:
        lda selected_field
        cmp #0
        bne dv_border_off
        lda marker_char
        jmp dv_border_store
dv_border_off:
        lda blank_char
dv_border_store:
        sta SCREEN_RAM+(BOX_TOP_ROW+2)*40+5

        lda selected_field
        cmp #1
        bne dv_bg_off
        lda marker_char
        jmp dv_bg_store
dv_bg_off:
        lda blank_char
dv_bg_store:
        sta SCREEN_RAM+(BOX_TOP_ROW+3)*40+5

        lda selected_field
        cmp #2
        bne dv_blink_off
        lda marker_char
        jmp dv_blink_store
dv_blink_off:
        lda blank_char
dv_blink_store:
        sta SCREEN_RAM+(BOX_TOP_ROW+4)*40+5

        lda cur_border
        jsr to_decimal2
        lda digit_tens
        sta SCREEN_RAM+(BOX_TOP_ROW+2)*40+32
        lda digit_ones
        sta SCREEN_RAM+(BOX_TOP_ROW+2)*40+33

        lda cur_bg
        jsr to_decimal2
        lda digit_tens
        sta SCREEN_RAM+(BOX_TOP_ROW+3)*40+32
        lda digit_ones
        sta SCREEN_RAM+(BOX_TOP_ROW+3)*40+33

        lda cur_blink
        jsr to_decimal2
        lda digit_tens
        sta SCREEN_RAM+(BOX_TOP_ROW+4)*40+32
        lda digit_ones
        sta SCREEN_RAM+(BOX_TOP_ROW+4)*40+33

        lda selected_field
        beq dv_help_border
        cmp #1
        beq dv_help_bg
        lda #<help_blink
        sta poke_src_lo
        lda #>help_blink
        sta poke_src_hi
        jmp dv_help_go
dv_help_border:
        lda #<help_border
        sta poke_src_lo
        lda #>help_border
        sta poke_src_hi
        jmp dv_help_go
dv_help_bg:
        lda #<help_bg
        sta poke_src_lo
        lda #>help_bg
        sta poke_src_hi
dv_help_go:
        jsr poke_help_line
        rts

; .a = value (0-19 is all this module ever needs -- border/bg are 0-15,
; blink is 1-4). Stores screen codes for the two decimal digits into
; digit_tens/digit_ones via digit_chars, rather than assuming a fixed
; digit-to-screen-code arithmetic offset -- same "verify, don't guess"
; policy as HELP_KEY/HELP_EXIT_KEY's own comment in petscii_editor.asm.
to_decimal2:
        ldx #0
td_tens_loop:
        cmp #10
        bcc td_done
        sbc #10
        inx
        jmp td_tens_loop
td_done:
        ; .x = tens digit (0 or 1), .a = ones digit (0-9)
        tay
        lda digit_chars,x
        sta digit_tens
        tya
        tax
        lda digit_chars,x
        sta digit_ones
        rts

digit_tens:
        byte 0
digit_ones:
        byte 0

; blink_speed (1-4) -> cursor_blink_mask bit, must match tada-client.asm's
; cursor_blink_mask comment and commands/c64_display.py's
; BLINK_SPEED_MASKS exactly: $08 fast, $10 normal (the original hardcoded
; default), $20 slow, $40 very slow, $00 solid/no blink (Ryan's ask --
; some screen-reader/accessibility software, e.g. Gadget, doesn't get
; along with a blinking cursor). Must live after `orig $2000` like every
; other data table in this module -- a real byte-emitting label placed
; before `orig $2000` assembles at c64list's own default origin instead,
; silently producing a .prg whose embedded load address doesn't match
; OVERLAY_BUF at all (this exact bug, live 2026-08-15: it built with 0
; errors -- just a "Large change in origin" warning -- but KERNAL LOAD
; then loaded the whole module at the wrong address and `jmp OVERLAY_BUF`
; jumped into garbage memory).
blink_masks:
        byte $08, $10, $20, $40, $00

; --- Plain untransformed byte fill ---
; Input: fill_dst_lo/hi = dest base, fill_value = byte, fill_remaining_lo/
; hi = count. Generalized (count is an input, not hardcoded) unlike
; petscii_editor.asm's own fill_1000, since this module only ever fills
; the 9-row popup band (BOX_ROWS*40 bytes), not a full screen.
fill_bytes:
        lda fill_dst_lo
        sta fb_store+1
        lda fill_dst_hi
        sta fb_store+2
fb_loop:
        lda fill_value
fb_store:
        sta $ffff
        inc fb_store+1
        bne fb_no_carry
        inc fb_store+2
fb_no_carry:
        lda fill_remaining_lo
        bne fb_dec_lo
        dec fill_remaining_hi
fb_dec_lo:
        dec fill_remaining_lo
        lda fill_remaining_lo
        ora fill_remaining_hi
        bne fb_loop
        rts

; --- Plain untransformed 40-byte copy (one screen row) ---
; Input: poke_src_lo/hi = source (a 40-byte row_* line, space-padded),
; poke_dst_lo/hi = dest (SCREEN_RAM + row*40). Same shape as petscii_
; editor.asm's own poke_line -- a separate copy, see draw_popup's comment.
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

; --- Plain untransformed 30-byte copy (dynamic per-field help text) ---
; Input: poke_src_lo/hi = source (a help_* table, 30 bytes, no box
; border bytes). Dest is always fixed (row+6's interior, columns 5-34) --
; only the source varies, picked by draw_values based on selected_field.
poke_help_line:
        lda poke_src_lo
        sta poke_help_load+1
        lda poke_src_hi
        sta poke_help_load+2
        ldx #0
poke_help_loop:
poke_help_load:
        lda $ffff,x
        sta SCREEN_RAM+(BOX_TOP_ROW+6)*40+5,x
        inx
        cpx #30
        bne poke_help_loop
        rts

; --- Bulk-transfer scratch vars ---
poke_src_lo:
        byte 0
poke_src_hi:
        byte 0
poke_dst_lo:
        byte 0
poke_dst_hi:
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

; --- Receive helper (mirrors petscii_editor.asm's own) ---
recv_length_prefix:
        jsr JT_SL_RECV
        bcc recv_length_prefix    ; len_lo -- discarded, always 3
recv_length_prefix_hi:
        jsr JT_SL_RECV
        bcc recv_length_prefix_hi
        rts

; --- State ---
; (BOX_TOP_ROW/BOX_ROWS moved up near VIC_BORDER/VIC_BG -- see that
; comment.)

selected_field:
        byte 0                    ; 0 = border, 1 = background, 2 = blink
cur_border:
        byte 0
cur_bg:
        byte 0
cur_blink:
        byte 0
orig_border:
        byte 0
orig_bg:
        byte 0
orig_blink:
        byte 0

; Single poke-able screen codes for '>' / ' ' -- built via the verified
; {alpha:poke} ASCII->screen-code conversion (same macro petscii_editor.asm's
; own poke-target text uses) rather than a hand-guessed numeric screen code.
{alpha:poke}
marker_char:
        ascii ">"
blank_char:
        ascii " "

digit_chars:
        ascii "0123456789"

; Popup box text, 40 bytes each -- poke_line copies a fixed 40 bytes, so
; every row must add up to exactly that width (same convention as
; petscii_editor.asm's help_line1-6). Value/marker columns (32 and 5
; respectively, within each row_field* line) are placeholders overwritten
; live by draw_values -- their exact characters here don't matter.
;
; Real PETSCII line-drawing screen codes (top_left/top_right/bot_left/
; bot_right/h/v below), not plain ASCII +/-/| -- same box-drawing set
; table.py's own PETSCII Border already uses server-side (Ryan's ask:
; match that, rather than a plain-ASCII box). Values verified via
; cbmcodecs2 directly, not guessed: `'┌'.encode('screencode_c64_uc')[0]`
; etc. -- $70 top-left, $6e top-right, $6d bottom-left, $7d bottom-right,
; $40 horizontal, $5d vertical (cross-checked live 2026-08-15 against
; table.py's PETSCII Border: top_left='┌', top_right='┐', bot_left='└',
; bot_right='┘', h='─', v='│').
;
; These must be emitted via `byte`/`area`, NOT inside an `ascii "..."`
; string even via a `{$xx:N}` repeat token -- confirmed live: `{alpha:
; poke}` (active for this whole block, for the plain-English label text)
; re-runs its own ASCII->screencode conversion table over whatever value
; a `{$xx:N}` token produces too, silently mangling a real screen code
; into something else entirely (e.g. `{$70:1}` -> $10, not $70, because
; poke-mode treated $70 as if it were ASCII 'p' and converted THAT).
; `byte`/`area` bypass alpha-mode conversion entirely regardless of
; which `{alpha:...}` block they're inside, confirmed the same way.

; pokealt pokes upper/lowercase characters to screen RAM, I think:
{alpha:pokealt}
top_border:
        byte $20,$20,$20,$20, $70
        area 30, $40
        byte $6e, $20,$20,$20,$20
row_title:
        byte $20,$20,$20,$20, $5d
        ascii "        Video Settings        "
        byte $5d, $20,$20,$20,$20
row_field1:
        byte $20,$20,$20,$20, $5d
        ascii "  Border color:            00 "
        byte $5d, $20,$20,$20,$20
row_field2:
        byte $20,$20,$20,$20, $5d
        ascii "  Background color:        00 "
        byte $5d, $20,$20,$20,$20
row_field3:
        byte $20,$20,$20,$20, $5d
        ascii "  Cursor blink speed:      00 "
        byte $5d, $20,$20,$20,$20
row_blank:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20

; Dynamic per-field help text, 30 bytes each (no leading/trailing box
; bytes here -- these overwrite just row_blank's interior at runtime via
; draw_values/poke_help_line, picked by selected_field). Ryan's ask,
; especially for blink speed since 1-5 isn't self-explanatory from the
; field row's bare number alone.
help_border:
        ascii "Border color, 0-15 (VIC-II)   "
help_bg:
        ascii "Background color, 0-15        "
help_blink:
        ascii "1=fastest .. 4=slowest, 5=off "

row_help1:
        byte $20,$20,$20,$20, $5d
        ascii " Crsr Up/Down: Select option  "
        byte $5d, $20,$20,$20,$20
row_help2:
        byte $20,$20,$20,$20, $5d
        ascii " Crsr Left/Right: Incr/Decr   "
        byte $5d, $20,$20,$20,$20
row_help3:
        byte $20,$20,$20,$20, $5d
        ascii " Return: save   Stop: cancel  "
        byte $5d, $20,$20,$20,$20
bottom_border:
        byte $20,$20,$20,$20, $6d
        area 30, $40
        byte $7d, $20,$20,$20,$20
{alpha:normal}
