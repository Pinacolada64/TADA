; help_menu.asm — loadable "Help / Keyboard Shortcuts / Credits" popup
; overlay.
;
; Not resident: LOADed on demand by tada-client.asm's load_help_menu
; (KERNAL LOAD "HELP.MNU",8,1) once a help stream is confirmed starting
; (the player typed HELP, KEYS, or CREDITS at the game prompt -- see
; commands/help_menu.py), and discarded once this returns control via
; JT_RESUME. Same "loadable sub-module, not grown into tada-client.asm"
; rationale as petscii_editor.asm/config_menu.asm -- see either file's
; own header comment and CLIENT_MECHANICS.md's "Loadable overlay
; modules" section.
;
; Unlike config_menu.asm, this popup never sends anything back to the
; server -- there's nothing to save, just three pages of static text the
; player flips between locally (CRSR LEFT/RIGHT) and closes (RETURN or
; RUN/STOP) whenever they're done. So there's no HELP_STREAM_CANCEL byte
; and no upload/reply round trip: module_start reads the 1-byte body
; (which page to open on) and that's the only data this module ever
; receives.
;
; Talks to the same resident SwiftLink plumbing (sl_recv) plus the
; shared screen-save buffer via the fixed jump table tada-client.asm's
; init_jump_table populates at boot -- same shared {include:constants.asm}
; as every other overlay module, so neither the addresses nor the
; protocol-byte values can drift out of sync between the files that need
; them (see constants.asm's own comment for the 2026-08-17 incident that
; mechanism exists to prevent).
{include:constants.asm}

; Popup box position -- must be defined before draw_static/draw_page use
; them in address arithmetic below (same forward-reference gotcha
; config_menu.asm's own BOX_TOP_ROW/BOX_ROWS comment documents -- a plain
; `=` constant isn't safe to forward-reference the way a label is).
; Full 25-row screen (not a smaller inset band like config_menu.asm's
; own popup) -- confirmed live 2026-08-25 that a smaller band left
; whatever game text was on screen before the popup opened (STATS
; output, mid-fight text, ...) visibly bleeding through above/below the
; box, since JT_SAVE_SCREEN/JT_RESTORE_SCREEN back up and restore the
; WHOLE screen regardless of how much of it draw_static/draw_page
; actually overwrite. Unlike config_menu.asm (only ever opened from
; PREFS' own mostly-blank submenu background), guide/keys/credits can
; be typed from literally any game screen, so there's no safe smaller
; band to assume is already blank.
BOX_TOP_ROW = 0
BOX_ROWS    = 25

; SCREEN_RAM/COLOR_RAM/CHROUT/GETIN are macro_preprocessor.py built-ins
; (C64_CONSTANTS) -- no {const:} needed for those here.

; Load/run address moved $2000 -> $4000 2026-08-25 -- see tada-client.
; asm's own OVERLAY_BUF comment for the full story (this module's own
; loaded code was getting overwritten by save_screen's screen/color
; backup, which had grown to occupy part of the old $2000 range).
        orig $4000

module_start:
        jsr JT_SAVE_SCREEN        ; back up whatever's on screen right now
                                    ; (the caller's own game text) so it
                                    ; can be put back exactly as-is on exit

        jsr recv_length_prefix    ; discarded -- always exactly 1 for this
                                    ; stream (starting page number)

        jsr JT_SL_RECV
recv_page_wait:
        bcc recv_page_wait
        sta cur_page               ; 0 = help, 1 = keys, 2 = credits --
                                    ; see commands/help_menu.py's PAGE_*
                                    ; constants, must match exactly

        jsr draw_static
        jsr draw_page

; --- Main input loop ---
help_loop:
        jsr GETIN
        cmp #0
        beq help_loop
        jsr dispatch_help_key      ; never returns on a hit (jmp's into a
                                     ; handler); falls through here on a miss
        jmp help_loop

; code, handler-address-lo, handler-address-hi -- 3 bytes/entry. Same
; table-driven dispatch shape as config_menu.asm's own dispatch_config_
; key -- these GETIN codes ($9d/$1d/$0d/$03) are the same ones already
; confirmed live for that module's cursor keys/RETURN/RUN-STOP.
dispatch_help_key:
        sta dispatch_key
        ldx #0
dispatch_help_key_loop:
        cpx #HELP_KEYS_END
        beq dispatch_help_key_miss
        lda help_keys,x
        cmp dispatch_key
        beq dispatch_help_key_hit
        txa
        clc
        adc #3
        tax
        jmp dispatch_help_key_loop
dispatch_help_key_hit:
        lda help_keys+1,x
        sta dispatch_help_key_jmp+1
        lda help_keys+2,x
        sta dispatch_help_key_jmp+2
dispatch_help_key_jmp:
        jmp $ffff
dispatch_help_key_miss:
        rts

dispatch_key:
        byte 0

help_keys:
        byte $9d                  ; cursor left -- previous page
        word key_prev_page
        byte $1d                  ; cursor right -- next page
        word key_next_page
        byte $0d                  ; RETURN -- close
        word key_close
        byte $03                  ; RUN/STOP -- close
        word key_close
HELP_KEYS_END = * - help_keys

key_prev_page:
        lda cur_page
        bne kpp_dec
        lda #2
        sta cur_page
        jmp kpp_done
kpp_dec:
        dec cur_page
kpp_done:
        jsr draw_page
        jmp help_loop

key_next_page:
        inc cur_page
        lda cur_page
        cmp #3
        bne knp_done
        lda #0
        sta cur_page
knp_done:
        jsr draw_page
        jmp help_loop

; --- Close: restore the screen, hand back -- no reply sent, nothing to
; save (see this file's own header comment for why).
key_close:
        jsr JT_RESTORE_SCREEN
        jmp JT_RESUME

; --- Draw the static popup box (border/blank rows/nav help text) ---
; Fills the whole screen's COLOR_RAM to white first (one fill_bytes
; call), then pokes each 40-char row's text over SCREEN_RAM -- same
; "poke_line" shape as config_menu.asm's own draw_popup (a separate
; copy: this module has no way to share code with that one, they're
; never resident at the same time). Title (row 2) and content (rows
; 4-13) are drawn by draw_page, not here -- this only draws what's the
; same on every page. Full BOX_TOP_ROW/BOX_ROWS=0/25 (see that comment)
; means every one of the screen's 25 rows is accounted for between this
; routine and draw_page -- nothing is left showing whatever was on
; screen before the popup opened.
draw_static:
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

        lda #1                     ; row 1 -- blank, above the title
        ldx #1
        jsr draw_blank_run

        lda #3                     ; row 3 -- blank, above the content
        ldx #1
        jsr draw_blank_run

        lda #14                    ; rows 14-15 -- blank, below the content
        ldx #2
        jsr draw_blank_run

        lda #<row_help1
        sta poke_src_lo
        lda #>row_help1
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+16)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+16)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_help2
        sta poke_src_lo
        lda #>row_help2
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+17)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+17)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #18                    ; rows 18-23 -- blank, filling down to
        ldx #6                     ; the bottom border
        jsr draw_blank_run

        lda #<bottom_border
        sta poke_src_lo
        lda #>bottom_border
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+24)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+24)*40)
        sta poke_dst_hi
        jmp poke_line

; --- draw_blank_run: pokes row_blank into .x consecutive rows starting
; at absolute row .a (e.g. .a=18, .x=6 fills rows 18-23) -- used above
; for the wide blank bands a fixed-position poke_line call per row
; would otherwise need many near-identical copies of. Recomputes the
; destination address from scratch each row (same technique as
; dp_content below) rather than just adding 40 to a running pointer --
; simpler to read, and cheap enough for a one-off modal-popup draw.
draw_blank_run:
        sta dbr_row
        stx dbr_count
        lda #<row_blank
        sta poke_src_lo
        lda #>row_blank
        sta poke_src_hi
dbr_loop:
        lda #<(SCREEN_RAM+BOX_TOP_ROW*40)
        sta dbr_dst_lo
        lda #>(SCREEN_RAM+BOX_TOP_ROW*40)
        sta dbr_dst_hi
        ldx dbr_row
dbr_add_loop:
        cpx #0
        beq dbr_add_done
        lda dbr_dst_lo
        clc
        adc #40
        sta dbr_dst_lo
        bcc dbr_no_carry
        inc dbr_dst_hi
dbr_no_carry:
        dex
        jmp dbr_add_loop
dbr_add_done:
        lda dbr_dst_lo
        sta poke_dst_lo
        lda dbr_dst_hi
        sta poke_dst_hi
        jsr poke_line
        inc dbr_row
        dec dbr_count
        bne dbr_loop
        rts

dbr_row:
        byte 0
dbr_count:
        byte 0
dbr_dst_lo:
        byte 0
dbr_dst_hi:
        byte 0

; --- Draw the page-specific parts: title (row+2) + 10 content rows
; (rows+4..+13) -- picked by cur_page. Explicit per-page blocks (not a
; runtime address table) so each poke_line call's source is a plain
; label, same style as config_menu.asm's draw_popup -- easy to verify by
; eye against the row_*_N labels below, no indexed-table arithmetic to
; get wrong.
; beq dp_page1 (a straight `cmp #1 / beq dp_page1`) is out of 6502
; branch range -- dp_page1 sits ~166 bytes past this point once
; dp_page0's whole title+10-content-row block is between them, and
; c64list does NOT validate branch range (assembles clean, no warning,
; computes a garbage relative offset at runtime -- confirmed live
; 2026-08-25: a real CPU JAM at $2152, one byte into what should have
; been this branch's own operand). Same gotcha already hit and fixed
; this same way elsewhere in this project (see tada-client.asm's
; read_line_loop's own comment on this) -- invert the test and reach
; dp_page1 via an unconditional jmp instead, which has no range limit.
draw_page:
        lda cur_page
        cmp #0
        beq dp_page0
        cmp #1
        bne draw_page_page2
        jmp dp_page1
draw_page_page2:
        jmp dp_page2

dp_page0:
        lda #<row_title_0
        sta poke_src_lo
        lda #>row_title_0
        sta poke_src_hi
        jsr dp_title
        lda #<row_help_0
        sta poke_src_lo
        lda #>row_help_0
        sta poke_src_hi
        lda #4
        jsr dp_content
        lda #<row_help_1
        sta poke_src_lo
        lda #>row_help_1
        sta poke_src_hi
        lda #5
        jsr dp_content
        lda #<row_help_2
        sta poke_src_lo
        lda #>row_help_2
        sta poke_src_hi
        lda #6
        jsr dp_content
        lda #<row_help_3
        sta poke_src_lo
        lda #>row_help_3
        sta poke_src_hi
        lda #7
        jsr dp_content
        lda #<row_help_4
        sta poke_src_lo
        lda #>row_help_4
        sta poke_src_hi
        lda #8
        jsr dp_content
        lda #<row_help_5
        sta poke_src_lo
        lda #>row_help_5
        sta poke_src_hi
        lda #9
        jsr dp_content
        lda #<row_help_6
        sta poke_src_lo
        lda #>row_help_6
        sta poke_src_hi
        lda #10
        jsr dp_content
        lda #<row_help_7
        sta poke_src_lo
        lda #>row_help_7
        sta poke_src_hi
        lda #11
        jsr dp_content
        lda #<row_help_8
        sta poke_src_lo
        lda #>row_help_8
        sta poke_src_hi
        lda #12
        jsr dp_content
        lda #<row_help_9
        sta poke_src_lo
        lda #>row_help_9
        sta poke_src_hi
        lda #13
        jmp dp_content

dp_page1:
        lda #<row_title_1
        sta poke_src_lo
        lda #>row_title_1
        sta poke_src_hi
        jsr dp_title
        lda #<row_keys_0
        sta poke_src_lo
        lda #>row_keys_0
        sta poke_src_hi
        lda #4
        jsr dp_content
        lda #<row_keys_1
        sta poke_src_lo
        lda #>row_keys_1
        sta poke_src_hi
        lda #5
        jsr dp_content
        lda #<row_keys_2
        sta poke_src_lo
        lda #>row_keys_2
        sta poke_src_hi
        lda #6
        jsr dp_content
        lda #<row_keys_3
        sta poke_src_lo
        lda #>row_keys_3
        sta poke_src_hi
        lda #7
        jsr dp_content
        lda #<row_keys_4
        sta poke_src_lo
        lda #>row_keys_4
        sta poke_src_hi
        lda #8
        jsr dp_content
        lda #<row_keys_5
        sta poke_src_lo
        lda #>row_keys_5
        sta poke_src_hi
        lda #9
        jsr dp_content
        lda #<row_keys_6
        sta poke_src_lo
        lda #>row_keys_6
        sta poke_src_hi
        lda #10
        jsr dp_content
        lda #<row_keys_7
        sta poke_src_lo
        lda #>row_keys_7
        sta poke_src_hi
        lda #11
        jsr dp_content
        lda #<row_keys_8
        sta poke_src_lo
        lda #>row_keys_8
        sta poke_src_hi
        lda #12
        jsr dp_content
        lda #<row_keys_9
        sta poke_src_lo
        lda #>row_keys_9
        sta poke_src_hi
        lda #13
        jmp dp_content

dp_page2:
        lda #<row_title_2
        sta poke_src_lo
        lda #>row_title_2
        sta poke_src_hi
        jsr dp_title
        lda #<row_credits_0
        sta poke_src_lo
        lda #>row_credits_0
        sta poke_src_hi
        lda #4
        jsr dp_content
        lda #<row_credits_1
        sta poke_src_lo
        lda #>row_credits_1
        sta poke_src_hi
        lda #5
        jsr dp_content
        lda #<row_credits_2
        sta poke_src_lo
        lda #>row_credits_2
        sta poke_src_hi
        lda #6
        jsr dp_content
        lda #<row_credits_3
        sta poke_src_lo
        lda #>row_credits_3
        sta poke_src_hi
        lda #7
        jsr dp_content
        lda #<row_credits_4
        sta poke_src_lo
        lda #>row_credits_4
        sta poke_src_hi
        lda #8
        jsr dp_content
        lda #<row_credits_5
        sta poke_src_lo
        lda #>row_credits_5
        sta poke_src_hi
        lda #9
        jsr dp_content
        lda #<row_credits_6
        sta poke_src_lo
        lda #>row_credits_6
        sta poke_src_hi
        lda #10
        jsr dp_content
        lda #<row_credits_7
        sta poke_src_lo
        lda #>row_credits_7
        sta poke_src_hi
        lda #11
        jsr dp_content
        lda #<row_credits_8
        sta poke_src_lo
        lda #>row_credits_8
        sta poke_src_hi
        lda #12
        jsr dp_content
        lda #<row_credits_9
        sta poke_src_lo
        lda #>row_credits_9
        sta poke_src_hi
        lda #13
        jmp dp_content

; .a = title dest row offset is always BOX_TOP_ROW+2 -- poke_src_lo/hi
; already set by the caller.
dp_title:
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+2)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+2)*40)
        sta poke_dst_hi
        jmp poke_line

; .a = row offset (3-12, absolute -- BOX_TOP_ROW+.a is the dest row).
; poke_src_lo/hi already set by the caller. Computes the dest address at
; runtime (row offset varies per call, unlike dp_title's fixed one) via
; dp_content_row_lo/hi scratch -- BOX_TOP_ROW*40 is a compile-time
; constant added in, .a*40 done by repeated adds since 6502 has no
; multiply.
dp_content:
        sta dp_content_row
        lda #<(SCREEN_RAM+BOX_TOP_ROW*40)
        sta dp_content_dst_lo
        lda #>(SCREEN_RAM+BOX_TOP_ROW*40)
        sta dp_content_dst_hi
        ldx dp_content_row
dp_content_add_loop:
        cpx #0
        beq dp_content_add_done
        lda dp_content_dst_lo
        clc
        adc #40
        sta dp_content_dst_lo
        bcc dp_content_no_carry
        inc dp_content_dst_hi
dp_content_no_carry:
        dex
        jmp dp_content_add_loop
dp_content_add_done:
        lda dp_content_dst_lo
        sta poke_dst_lo
        lda dp_content_dst_hi
        sta poke_dst_hi
        jmp poke_line

dp_content_row:
        byte 0
dp_content_dst_lo:
        byte 0
dp_content_dst_hi:
        byte 0

; --- Plain untransformed byte fill ---
; Input: fill_dst_lo/hi = dest base, fill_value = byte, fill_remaining_lo/
; hi = count. Same shape as config_menu.asm's own fill_bytes -- a
; separate copy, see draw_static's comment.
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
; poke_dst_lo/hi = dest (SCREEN_RAM + row*40). Same shape as config_
; menu.asm's own poke_line -- a separate copy, see draw_static's comment.
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
        beq poke_line_skip        ; 0 = transparent -- leave the dest
                                    ; cell alone so whatever was behind
                                    ; the window (the game text
                                    ; JT_SAVE_SCREEN backed up, still on
                                    ; screen at this point) keeps showing
poke_line_store:
        sta $ffff,x
poke_line_skip:
        inx
        cpx #40
        bne poke_line_loop
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

; --- Receive helper (mirrors config_menu.asm/petscii_editor.asm's own) ---
; Reads the 16-bit length prefix -- discarded, always 1 for this stream
; (just the starting page number).
recv_length_prefix:
        jsr JT_SL_RECV
        bcc recv_length_prefix    ; len_lo -- discarded, always 1
recv_length_prefix_hi:
        jsr JT_SL_RECV
        bcc recv_length_prefix_hi
        rts

; --- State ---
cur_page:
        byte 0                    ; 0 = help, 1 = keys, 2 = credits

; Popup box text, 40 bytes each -- poke_line copies a fixed 40 bytes, so
; every row must add up to exactly that width (same convention as
; config_menu.asm's own row_field*/row_blank).
;
; Real PETSCII line-drawing screen codes (top_left/top_right/bot_left/
; bot_right/h/v below), not plain ASCII +/-/| -- same box-drawing set
; config_menu.asm's own top_border/bottom_border already uses (verified
; there via cbmcodecs2 directly against table.py's PETSCII Border: $70
; top-left, $6e top-right, $6d bottom-left, $7d bottom-right, $40
; horizontal, $5d vertical). Emitted via `byte`/`area`, NOT inside an
; `ascii "..."` string -- see config_menu.asm's own top_border comment
; for the {alpha:poke}-mangles-$xx-repeat-tokens bug that makes this
; matter.
{alpha:pokealt}
top_border:
        byte $20,$20,$20,$20, $70
        area 30, $40
        byte $6e, $20,$20,$20,$20
row_blank:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20
bottom_border:
        byte $20,$20,$20,$20, $6d
        area 30, $40
        byte $7d, $20,$20,$20,$20

; --- help page content rows ---
row_help_0:
        byte $20,$20,$20,$20, $5d
        ascii "TADA is a text adventure --   "
        byte $5d, $20,$20,$20,$20

row_help_1:
        byte $20,$20,$20,$20, $5d
        ascii "explore, fight monsters, and  "
        byte $5d, $20,$20,$20,$20

row_help_2:
        byte $20,$20,$20,$20, $5d
        ascii "level up your character.      "
        byte $5d, $20,$20,$20,$20

row_help_3:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20

row_help_4:
        byte $20,$20,$20,$20, $5d
        ascii "Common commands:              "
        byte $5d, $20,$20,$20,$20

row_help_5:
        byte $20,$20,$20,$20, $5d
        ascii "LOOK, N/S/E/W to move, GET,   "
        byte $5d, $20,$20,$20,$20

row_help_6:
        byte $20,$20,$20,$20, $5d
        ascii "DROP, INV, SAY, ATTACK.       "
        byte $5d, $20,$20,$20,$20

row_help_7:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20

row_help_8:
        byte $20,$20,$20,$20, $5d
        ascii "Type KEYS for the full list   "
        byte $5d, $20,$20,$20,$20

row_help_9:
        byte $20,$20,$20,$20, $5d
        ascii "of keyboard shortcuts.        "
        byte $5d, $20,$20,$20,$20

; --- keys page content rows ---
row_keys_0:
        byte $20,$20,$20,$20, $5d
        ascii "Editing the input line:       "
        byte $5d, $20,$20,$20,$20

row_keys_1:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20

row_keys_2:
        byte $20,$20,$20,$20, $5d
        ascii "CRSR left/right: move cursor  "
        byte $5d, $20,$20,$20,$20

row_keys_3:
        byte $20,$20,$20,$20, $5d
        ascii "SHIFT+DEL: insert a space     "
        byte $5d, $20,$20,$20,$20

row_keys_4:
        byte $20,$20,$20,$20, $5d
        ascii "DEL: delete left              "
        byte $5d, $20,$20,$20,$20

row_keys_5:
        byte $20,$20,$20,$20, $5d
        ascii "CRSR UP: jump to line start   "
        byte $5d, $20,$20,$20,$20

row_keys_6:
        byte $20,$20,$20,$20, $5d
        ascii "CRSR DOWN: jump to line end   "
        byte $5d, $20,$20,$20,$20

row_keys_7:
        byte $20,$20,$20,$20, $5d
        ascii "CTRL+CRSR LEFT: word left     "
        byte $5d, $20,$20,$20,$20

row_keys_8:
        byte $20,$20,$20,$20, $5d
        ascii "CTRL+CRSR DOWN: word right    "
        byte $5d, $20,$20,$20,$20

row_keys_9:
        byte $20,$20,$20,$20, $5d
        ascii "RETURN: send command          "
        byte $5d, $20,$20,$20,$20

; --- credits page content rows ---
row_credits_0:
        byte $20,$20,$20,$20, $5d
        ascii "TADA                          "
        byte $5d, $20,$20,$20,$20

row_credits_1:
        byte $20,$20,$20,$20, $5d
        ascii "A Commodore 64/128 MUD        "
        byte $5d, $20,$20,$20,$20

row_credits_2:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20

; A literal " inside an ascii "..." string isn't valid (it would just
; close the string early) -- c64list also doesn't treat '...' as an
; alternate string delimiter the way some assemblers do; confirmed live
; 2026-08-25, `ascii '...'` errors "Single character expected" since
; c64list parses single-quotes as a one-character literal instead. Each
; embedded " is `byte 34` ($22, same screen code as ASCII/PETSCII in
; this punctuation range -- no {alpha:pokealt} translation needed,
; `byte` bypasses that entirely regardless, same as this file's own
; box-drawing bytes above) splitting the ascii run around it.
row_credits_3:
        byte $20,$20,$20,$20, $5d
        ascii "Created by Ryan "
        byte 34
        ascii "Pinacolada"
        byte 34
        ascii "  "
        byte $5d, $20,$20,$20,$20

row_credits_4:
        byte $20,$20,$20,$20, $5d
        ascii "Sherwood, and Claude.ai!      "
        byte $5d, $20,$20,$20,$20

row_credits_5:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20

row_credits_6:
        byte $20,$20,$20,$20, $5d
        ascii "Inspired by "
        byte 34
        ascii "The Land of Spur"
        byte 34
        byte $5d, $20,$20,$20,$20

row_credits_7:
        byte $20,$20,$20,$20, $5d
        ascii "by Greg Davis and Skip Thomson"
        byte $5d, $20,$20,$20,$20

row_credits_8:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20

row_credits_9:
        byte $20,$20,$20,$20, $5d
        ascii " -- Thank you for playing! -- "
        byte $5d, $20,$20,$20,$20

; --- title rows ---
row_title_0:
        byte $20,$20,$20,$20, $5d
        ascii "General Help (1/3)            "
        byte $5d, $20,$20,$20,$20

row_title_1:
        byte $20,$20,$20,$20, $5d
        ascii "Keyboard Shortcuts (2/3)      "
        byte $5d, $20,$20,$20,$20

row_title_2:
        byte $20,$20,$20,$20, $5d
        ascii "Credits (3/3)                 "
        byte $5d, $20,$20,$20,$20

; --- static help/nav rows ---
row_help1:
        byte $20,$20,$20,$20, $5d
        ascii "<-/-> : change page           "
        byte $5d, $20,$20,$20,$20

row_help2:
        byte $20,$20,$20,$20, $5d
        ascii "RETURN or STOP: close         "
        byte $5d, $20,$20,$20,$20
{alpha:normal}
