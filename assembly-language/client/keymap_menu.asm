; keymap_menu.asm — loadable "Keymap Editor (C64)" popup overlay.
;
; Not resident: LOADed on demand by tada-client.asm's load_keymap_menu
; (KERNAL LOAD "KEYMAP.ED",8,1), reached via a local F7 keypress in
; read_line_not_return -- NOT a server-sent trigger the way config_
; menu.asm/help_menu.asm are, since neither the keymap nor macro text
; mean anything to the server (see keymap.asm's own header for the
; full reasoning). Discarded once this returns control via JT_RESUME,
; same as every other overlay module.
;
; This slice: view the current keymap (all MAX_BINDINGS slots, built
; live from keymap_table -- read via KEYMAP_TABLE_PTR, see that
; constant's own comment in constants.asm for why an indirect pointer
; instead of a fixed address), navigate with CRSR UP/DOWN, capture a
; new combo for a nav slot with RETURN (key_capture_combo -- rejects a
; combo already bound elsewhere), and either Save (KERNAL SAVE
; keymap_table back to KEYMAP.CFG) or Cancel. A macro-text sub-editor
; (RETURN on a macro slot), clearing a slot (DEL), and preset loading
; (P) are follow-up work, not yet in this file.
{include:constants.asm}

; Popup box position -- must be defined before draw_popup/etc use them
; in address arithmetic below, same forward-reference caveat config_
; menu.asm's own BOX_TOP_ROW/BOX_ROWS comment explains.
BOX_TOP_ROW = 2
BOX_ROWS    = 21               ; rows 2-22 -- clear of STATUS_ROW(23)/
                                 ; the prompt row(24), same conservative
                                 ; choice config_menu.asm makes (help_
                                 ; menu.asm's full-screen BOX_ROWS=25
                                 ; doesn't apply here, this isn't a
                                 ; server-pushed announcement popup)

; --- Keymap data model -- this file's own copy, NOT {include:}'d from
; keymap.asm (a separate standalone .prg, same reasoning as config_
; menu.asm/petscii_editor.asm not sharing code with each other -- see
; keymap.asm's own file-header comment). Must be kept in sync by hand
; if either changes; confirmed no simpler option exists the same way
; OVERLAY_BUF's own comment documents for that constant.
MAX_BINDINGS   = 15        ; keymap.asm's own MAX_BINDINGS comment
                             ; explains the 4 nav functions + the
                             ; built-in "open the editor" binding + up
                             ; to 10 macros
MACRO_TEXT_LEN = 24
BINDING_SIZE   = 3 + MACRO_TEXT_LEN

MOD_SHIFT = 1
MOD_CMDRE = 2
MOD_CTRL  = 4

ACTION_EMPTY       = 0
ACTION_WORD_LEFT   = 1
ACTION_WORD_RIGHT  = 2
ACTION_HOME        = 3
ACTION_END         = 4
ACTION_OPEN_EDITOR = 5
ACTION_MACRO       = 255

; $2900 -- see tada-client.asm's OVERLAY_BUF comment (moved here
; 2026-09-02 after this module's own first live test re-triggered the
; BACKUP_CHARS/BACKUP_COLORS collision that comment documents).
        orig $2900

module_start:
        jsr JT_SAVE_SCREEN

        ; keymap_table_end_lo/hi = KEYMAP_TABLE_PTR + KEYMAP_TABLE_SIZE
        ; -- key_save's own comment explains why this is computed once,
        ; here, rather than inline at the SAVE call site.
        lda KEYMAP_TABLE_PTR
        clc
        adc #<KEYMAP_TABLE_SIZE
        sta keymap_table_end_lo
        lda KEYMAP_TABLE_PTR+1
        adc #>KEYMAP_TABLE_SIZE
        sta keymap_table_end_hi

        lda #0
        sta selected_row
        jsr draw_popup
        jsr draw_list

; --- Main input loop ---
keymap_menu_loop:
        jsr GETIN
        cmp #0
        beq keymap_menu_loop
        jsr dispatch_keymap_key
        jmp keymap_menu_loop

; Same table-driven dispatch shape as config_menu.asm's dispatch_
; config_key -- see that routine's own comment.
dispatch_keymap_key:
        sta dispatch_key
        ldx #0
dispatch_keymap_key_loop:
        cpx #KEYMAP_KEYS_END
        beq dispatch_keymap_key_miss
        lda keymap_keys,x
        cmp dispatch_key
        beq dispatch_keymap_key_hit
        txa
        clc
        adc #3
        tax
        jmp dispatch_keymap_key_loop
dispatch_keymap_key_hit:
        lda keymap_keys+1,x
        sta dispatch_keymap_key_jmp+1
        lda keymap_keys+2,x
        sta dispatch_keymap_key_jmp+2
dispatch_keymap_key_jmp:
        jmp $ffff
dispatch_keymap_key_miss:
        rts

dispatch_key:
        byte 0

keymap_keys:
        byte $91                  ; cursor up -- previous row
        word key_row_up
        byte $11                  ; cursor down -- next row
        word key_row_down
        byte $53                  ; 'S' -- save and exit
        word key_save
        byte $03                  ; RUN/STOP -- cancel and exit
        word key_cancel
        byte $0d                  ; RETURN -- capture a new combo for
        word key_capture_combo    ; the selected row (nav slots only)
KEYMAP_KEYS_END = * - keymap_keys

key_row_up:
        lda selected_row
        beq kru_wrap
        dec selected_row
        jmp key_row_done
kru_wrap:
        lda #MAX_BINDINGS-1
        sta selected_row
        jmp key_row_done

key_row_down:
        inc selected_row
        lda selected_row
        cmp #MAX_BINDINGS
        bne key_row_done
        lda #0
        sta selected_row
key_row_done:
        jsr draw_list
        rts

; --- selected_slot_addr: scr_ptr_lo/hi = KEYMAP_TABLE_PTR +
; selected_row*BINDING_SIZE --- same moving-pointer walk describe_
; binding_row uses, factored out here since key_capture_combo and its
; own duplicate check both need a slot's address and this file only
; has one zero-page pointer (scr_ptr_lo/hi) to compute it into --
; recomputed fresh each use rather than cached, cheap at MAX_BINDINGS-1
; iterations of a short loop.
selected_slot_addr:
        lda KEYMAP_TABLE_PTR
        sta scr_ptr_lo
        lda KEYMAP_TABLE_PTR+1
        sta scr_ptr_hi
        ldx selected_row
        beq ssa_done
ssa_loop:
        lda scr_ptr_lo
        clc
        adc #BINDING_SIZE
        sta scr_ptr_lo
        bcc ssa_no_carry
        inc scr_ptr_hi
ssa_no_carry:
        dex
        bne ssa_loop
ssa_done:
        rts

; --- key_capture_combo: RETURN on the selected row -> wait for the
; next real keypress (plus whatever SHIFT/C=/CTRL is held per $028d,
; same modifier-read keymap.asm's own keymap_dispatch uses) and store
; it as that row's new modifier+key, leaving its action byte (and any
; macro text) untouched. No-op on an empty slot (ACTION_EMPTY --
; nothing to rebind) or a macro slot (ACTION_MACRO -- RETURN there is
; reserved for the not-yet-built macro-text sub-editor, see this
; file's own header comment); only the four nav actions (WORD_LEFT/
; WORD_RIGHT/HOME/END) actually capture. RUN/STOP during the wait
; cancels (matches the prompt's own "Stop to cancel" text) without
; changing anything. A captured combo already bound to some OTHER slot
; is rejected with an inline message and the wait resumes, rather than
; silently creating a duplicate -- the original plan's "editor-time
; only" duplicate check.
key_capture_combo:
        jsr selected_slot_addr
        ldy #2                     ; action byte
        lda (scr_ptr_lo),y
        cmp #ACTION_EMPTY
        beq kcc_rts
        cmp #ACTION_MACRO
        beq kcc_rts

        ldx #<capture_prompt_msg
        ldy #>capture_prompt_msg
        jsr draw_message_row
kcc_wait:
        jsr GETIN
        cmp #0
        beq kcc_wait
        cmp #$03                   ; RUN/STOP -- cancel, no change
        beq kcc_done
        sta capture_key
        lda $028d
        and #(MOD_SHIFT|MOD_CMDRE|MOD_CTRL)
        sta capture_mod
        jsr capture_check_duplicate
        bcs kcc_wait                ; duplicate -- message shown, retry

        jsr selected_slot_addr      ; recompute -- the duplicate scan
                                     ; above reused scr_ptr_lo/hi itself
        ldy #0
        lda capture_mod
        sta (scr_ptr_lo),y
        ldy #1
        lda capture_key
        sta (scr_ptr_lo),y
kcc_done:
        ldx #<row_help1
        ldy #>row_help1
        jsr draw_message_row        ; restore the normal help line
        jsr draw_list
kcc_rts:
        rts

capture_key:
        byte 0
capture_mod:
        byte 0

; --- capture_check_duplicate: is capture_mod/capture_key already
; bound to some OTHER (non-empty) slot? Sets carry and shows an inline
; conflict message if so; clears carry silently otherwise.
capture_check_duplicate:
        lda KEYMAP_TABLE_PTR
        sta scr_ptr_lo
        lda KEYMAP_TABLE_PTR+1
        sta scr_ptr_hi
        ldx #0
ccd_loop:
        cpx selected_row
        beq ccd_next               ; skip the slot being edited itself
        ldy #2
        lda (scr_ptr_lo),y
        cmp #ACTION_EMPTY
        beq ccd_next
        ldy #0
        lda (scr_ptr_lo),y
        cmp capture_mod
        bne ccd_next
        ldy #1
        lda (scr_ptr_lo),y
        cmp capture_key
        bne ccd_next
        ldx #<capture_conflict_msg
        ldy #>capture_conflict_msg
        jsr draw_message_row
        sec
        rts
ccd_next:
        lda scr_ptr_lo
        clc
        adc #BINDING_SIZE
        sta scr_ptr_lo
        bcc ccd_no_carry
        inc scr_ptr_hi
ccd_no_carry:
        inx
        cpx #MAX_BINDINGS
        bne ccd_loop
        clc
        rts

; --- draw_message_row: poke a full 40-byte pre-formatted row (X/Y =
; lo/hi, same shape as row_help1/row_help2 -- 4 border bytes, $5d, 30
; chars, $5d, 4 border bytes) over row_help1's screen position. Reuses
; poke_line's own plain copy rather than a bespoke routine, since
; every caller here already has a full 40-byte source ready (capture_
; prompt_msg/capture_conflict_msg, or row_help1 itself to restore it).
draw_message_row:
        stx poke_src_lo
        sty poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+18)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+18)*40)
        sta poke_dst_hi
        jmp poke_line

; --- Save: write keymap_table back to KEYMAP.CFG, restore, hand back ---
; SCRATCH the old file first, then a plain (no "@0:") SAVE -- Ryan's
; call, 2026-09-02: the "@0:" replace-file convention is known to
; trigger a real Commodore DOS bug on some drive/ROM combinations
; (the old file's blocks can end up not properly freed), so this
; project avoids it in favor of the slower but unambiguous
; SCRATCH-then-SAVE pair. A first-ever save (file doesn't exist yet)
; makes the SCRATCH fail harmlessly with FILE NOT FOUND -- ignored,
; same as read_error_channel ignores it elsewhere.
key_save:
        jsr scratch_keymap_file
        lda #KEYMAP_FILENAME_LEN
        ldx #<keymap_filename
        ldy #>keymap_filename
        jsr KERNAL_SETNAM
        lda #2
        ldx #8
        ldy #1
        jsr KERNAL_SETLFS
        ; KERNAL SAVE wants .A = a ZERO-PAGE address whose 2 bytes hold
        ; the real start address -- KEYMAP_TABLE_PTR itself lives at
        ; $c01a (constants.asm), not zero page, so it can't be passed
        ; directly; copy it into scr_ptr_lo/hi first (this module's own
        ; general-purpose indirect pointer, unused at this point --
        ; draw_list/describe_binding_row are long done by the time the
        ; player reaches Save).
        lda KEYMAP_TABLE_PTR
        sta scr_ptr_lo
        lda KEYMAP_TABLE_PTR+1
        sta scr_ptr_hi
        ldx keymap_table_end_lo
        ldy keymap_table_end_hi
        lda #<scr_ptr_lo
        jsr KERNAL_SAVE
        jsr read_error_channel     ; clear the drive's error LED --
                                     ; same reasoning as init_keymap's
                                     ; own LOAD-side call in keymap.asm
        jsr JT_RESTORE_SCREEN
        jmp JT_RESUME

; --- scratch_keymap_file: SCRATCH any existing KEYMAP.CFG before the
; SAVE in key_save above. Sent as a DOS command string ("S0:...") on
; the command channel (secondary address 15), same channel
; read_error_channel drains -- so this deliberately does NOT call
; read_error_channel itself; key_save's own call right after the SAVE
; picks up and clears whatever either operation (a harmless FILE NOT
; FOUND from this SCRATCH on the very first save, or the SAVE itself)
; left on the channel.
scratch_keymap_file:
        lda #KEYMAP_SCRATCH_LEN
        ldx #<keymap_scratch_command
        ldy #>keymap_scratch_command
        jsr KERNAL_SETNAM
        lda #15
        ldx #8
        ldy #15
        jsr KERNAL_SETLFS
        jsr KERNAL_OPEN
        ldx #15
        jsr KERNAL_CLOSE
        rts

; --- Cancel: hands back without touching disk -- but NOTE, a real gap
; now that key_capture_combo exists: it writes straight into the
; resident keymap_table live, not a staged copy, so Cancel only skips
; the SAVE -- any combo captured earlier in this same popup visit
; stays live in memory (and dispatching) even though the player chose
; not to save it, until the next boot's LOAD overwrites it from disk
; (or KEYMAP.CFG was never written at all, so it's simply lost then).
; A proper fix needs a snapshot of keymap_table on module_start and a
; restore-from-snapshot here; not built yet -- kept as its own key/
; routine (rather than aliasing key_save) so that logic has somewhere
; real to go.
key_cancel:
        jsr JT_RESTORE_SCREEN
        jmp JT_RESUME

; --- read_error_channel: drain the drive's command/error channel ---
; Own copy, not shared with keymap.asm (separate assembly) -- see that
; file's own read_error_channel for the full comment on why this
; matters (a real 1541's ERROR LED otherwise stays lit/blinking).
read_error_channel:
        lda #0
        jsr KERNAL_SETNAM
        lda #15
        ldx #8
        ldy #15
        jsr KERNAL_SETLFS
        jsr KERNAL_OPEN
        ldx #15
        jsr KERNAL_CHKIN
read_error_channel_loop:
        jsr KERNAL_CHRIN
        jsr KERNAL_READST
        and #$40
        beq read_error_channel_loop
        jsr KERNAL_CLRCHN
        lda #15
        jmp KERNAL_CLOSE

; KERNAL routines this file needs, local {const:} -- see keymap.asm's
; own copy of this exact block for why (a separate assembly, doesn't
; {include:} anything from that file).
{const: KERNAL_SETNAM $ffbd}
{const: KERNAL_SETLFS $ffba}
{const: KERNAL_SAVE   $ffd8}
{const: KERNAL_OPEN   $ffc0}
{const: KERNAL_CLOSE  $ffc3}
{const: KERNAL_CHKIN  $ffc6}
{const: KERNAL_CLRCHN $ffcc}
{const: KERNAL_CHRIN  $ffcf}
{const: KERNAL_READST $ffb7}

; Zero page -- own copy, not shared with tada-client.asm's scr_ptr_lo/
; hi (separate assembly, doesn't {include:} anything from that file --
; same $fb/$fc address petscii_editor.asm's own copy uses, harmless
; overlap since none of these modules are ever resident at the same
; time as each other).
scr_ptr_lo = $fb
scr_ptr_hi = $fc

; --- draw_popup: static box/title/help text ---
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

        lda #<row_blank
        sta poke_src_lo
        lda #>row_blank
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+2)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+2)*40)
        sta poke_dst_hi
        jsr poke_line

        ; rows +3..+17 (the 15 list rows) start blank -- draw_list
        ; fills them immediately after this returns, every time it's
        ; called (including once, right after this), so there's no
        ; separate per-row draw needed here the way config_menu.asm's
        ; fixed 3-field rows need. No separate blank spacer row between
        ; the list and row_help1 below (unlike the one between the
        ; title and the list, kept) -- the 15th list row now occupies
        ; exactly the row that spacer used to (BOX_TOP_ROW+17), so
        ; removing it grows the list by one row without growing the
        ; box: row_help1/help2/bottom_border keep their same row
        ; numbers either way.
        ; blank_list_row (not X) carries the row counter across the jsr
        ; poke_line below -- real bug, caught live 2026-09-02: poke_line's
        ; own inner copy loop runs X 0..39 and leaves it at 40 on return,
        ; so a bare `txa` here (after the first iteration) read poke_
        ; line's leftover 40 instead of this loop's own count, adding 40
        ; to the row number every iteration from the second one on --
        ; set_screen_line_local's `asl`/`tax` then indexed row_offsets
        ; wildly out of bounds, producing a garbage screen address
        ; (confirmed live via the VICE monitor: STA $D42D,X, nowhere
        ; near SCREEN_RAM) and only accidentally terminating the loop
        ; once X's 8-bit wraparound happened to land back on 14.
        lda #0
        sta blank_list_row
draw_popup_blank_list:
        lda #<row_blank
        sta poke_src_lo
        lda #>row_blank
        sta poke_src_hi
        lda blank_list_row
        clc
        adc #BOX_TOP_ROW+3
        jsr set_screen_line_local
        lda scr_ptr_lo
        sta poke_dst_lo
        lda scr_ptr_hi
        sta poke_dst_hi
        jsr poke_line
        inc blank_list_row
        lda blank_list_row
        cmp #MAX_BINDINGS
        bne draw_popup_blank_list

        lda #<row_help1
        sta poke_src_lo
        lda #>row_help1
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+18)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+18)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<row_help2
        sta poke_src_lo
        lda #>row_help2
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta poke_dst_hi
        jsr poke_line

        lda #<bottom_border
        sta poke_src_lo
        lda #>bottom_border
        sta poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+20)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+20)*40)
        sta poke_dst_hi
        jmp poke_line

; --- draw_list: (re)draw all MAX_BINDINGS rows from keymap_table ---
; Called once at startup and again after every CRSR UP/DOWN -- redraws
; every row rather than just the marker column, simplest correct thing
; for a list this small (15 rows * 40 bytes = 600 bytes, negligible).
draw_list:
        ldx #0
draw_list_loop:
        stx draw_list_row
        jsr describe_binding_row  ; fills row_scratch (30 bytes)

        ldx draw_list_row
        txa
        clc
        adc #BOX_TOP_ROW+3
        jsr set_screen_line_local  ; scr_ptr_lo/hi = this row's base --
                                     ; already zero page (unlike poke_
                                     ; dst_lo/hi below, which are plain
                                     ; variables poke_line's own self-
                                     ; modified-absolute-address copy
                                     ; uses, not usable with (zp),y
                                     ; indirect addressing the way this
                                     ; routine needs), so no separate
                                     ; copy is needed here at all

        ; Assemble the full 40-byte row: 5 border bytes + row_scratch's
        ; 30 + 5 border bytes, written directly (not via poke_line,
        ; which copies a single fixed 40-byte source) since the middle
        ; third is this call's own dynamic content.
        ldy #0
dl_left_border:
        lda row_blank,y
        sta (scr_ptr_lo),y
        iny
        cpy #5
        bne dl_left_border
dl_middle:
        ldx #0
dl_middle_loop:
        lda row_scratch,x
        sta (scr_ptr_lo),y
        iny
        inx
        cpx #30
        bne dl_middle_loop
dl_right_border:
        lda row_blank,y
        sta (scr_ptr_lo),y
        iny
        cpy #40
        bne dl_right_border

        ldx draw_list_row
        inx
        cpx #MAX_BINDINGS
        bne draw_list_loop
        rts

draw_list_row:
        byte 0

; --- describe_binding_row: build row_scratch (30 bytes) for slot .x ---
; Layout: marker(1) space(1) name(12) space(1) combo(15) = 30 -- combo
; starts at offset 15 (1+1+12+1), NOT 17. Real bug, caught live
; 2026-09-02: the combo field was written at row_scratch+17, 2 bytes
; past where this layout actually puts it, so the 15-byte field ran
; off the end of the 30-byte row_scratch buffer into whatever followed
; it in memory -- selected_row and blank_list_row, as it happened,
; silently overwritten with padding/text bytes (typically $20) every
; single time a row was drawn. Confirmed via the VICE monitor: row_
; scratch = $2d93, +30 = $2db1 = selected_row exactly.
describe_binding_row:
        stx describe_slot
        ; marker
        lda selected_row
        cmp describe_slot
        bne dbr_no_marker
        lda marker_char
        jmp dbr_marker_store
dbr_no_marker:
        lda blank_char
dbr_marker_store:
        sta row_scratch+0
        lda blank_char
        sta row_scratch+1

        ; keymap_slot_addr: scr_ptr_lo/hi = KEYMAP_TABLE_PTR + .x*
        ; BINDING_SIZE -- same moving-pointer technique keymap.asm's
        ; own keymap_dispatch uses (MAX_BINDINGS*BINDING_SIZE exceeds
        ; what an 8-bit Y-indexed offset can reach), just walked once
        ; per row here instead of scanned in a search loop.
        lda KEYMAP_TABLE_PTR
        sta scr_ptr_lo
        lda KEYMAP_TABLE_PTR+1
        sta scr_ptr_hi
        ldx describe_slot
        beq dbr_addr_done
dbr_addr_loop:
        lda scr_ptr_lo
        clc
        adc #BINDING_SIZE
        sta scr_ptr_lo
        bcc dbr_addr_no_carry
        inc scr_ptr_hi
dbr_addr_no_carry:
        dex
        bne dbr_addr_loop
dbr_addr_done:

        ldy #2                     ; action byte
        lda (scr_ptr_lo),y
        sta describe_action
        cmp #ACTION_EMPTY
        bne dbr_not_empty
        ldx #<name_empty
        ldy #>name_empty
        jsr copy_name12
        jmp dbr_combo_blank
dbr_not_empty:
        cmp #ACTION_MACRO
        bne dbr_nav_name
        ; macro: show the macro_text itself (truncated/padded to 12)
        ldy #3
        ldx #0
dbr_macro_copy:
        cpx #12
        beq dbr_macro_done
        lda (scr_ptr_lo),y
        beq dbr_macro_pad          ; NUL -- pad the rest with spaces
        sta row_scratch+2,x
        iny
        inx
        jmp dbr_macro_copy
dbr_macro_pad:
        lda blank_char
        sta row_scratch+2,x
        inx
        cpx #12
        bne dbr_macro_pad
dbr_macro_done:
        jmp dbr_combo_blank        ; a macro's own trigger combo still
                                     ; shows normally below -- only the
                                     ; NAME column took the early exit
dbr_nav_name:
        cmp #ACTION_WORD_LEFT
        bne dbr_try_word_right
        ldx #<name_word_left
        ldy #>name_word_left
        jsr copy_name12
        jmp dbr_combo
dbr_try_word_right:
        cmp #ACTION_WORD_RIGHT
        bne dbr_try_home
        ldx #<name_word_right
        ldy #>name_word_right
        jsr copy_name12
        jmp dbr_combo
dbr_try_home:
        cmp #ACTION_HOME
        bne dbr_try_end
        ldx #<name_home
        ldy #>name_home
        jsr copy_name12
        jmp dbr_combo
dbr_try_end:
        cmp #ACTION_END
        bne dbr_try_open_editor
        ldx #<name_end
        ldy #>name_end
        jsr copy_name12
        jmp dbr_combo
dbr_try_open_editor:
        ; whatever's left over is ACTION_OPEN_EDITOR -- nothing else is
        ; valid (ACTION_EMPTY/ACTION_MACRO both took an earlier exit,
        ; above)
        ldx #<name_open_editor
        ldy #>name_open_editor
        jsr copy_name12
dbr_combo:
        jsr describe_combo
        rts
dbr_combo_blank:
        ldx #0
dbr_combo_blank_loop:
        lda blank_char
        sta row_scratch+15,x
        inx
        cpx #15
        bne dbr_combo_blank_loop
        rts

describe_slot:
        byte 0
describe_action:
        byte 0

; .x/.y = lo/hi of a 12-byte name table entry -> row_scratch+2..+13
copy_name12:
        stx copy_name12_load+1
        sty copy_name12_load+2
        ldy #0
copy_name12_loop:
copy_name12_load:
        lda $ffff,y
        sta row_scratch+2,y
        iny
        cpy #12
        bne copy_name12_loop
        rts

; --- describe_combo: build row_scratch+15..+29 (15 bytes) from the
; matched binding's modifier+key bytes ---
; Only shows the FIRST modifier bit found (CTRL, then C=, then SHIFT)
; rather than every one that's set -- keymap_dispatch itself still
; matches on the FULL mask regardless, this is a display simplification
; only, fine since no default or realistic binding combines more than
; one modifier. The four cursor keys get a short name; anything else
; (a macro's own trigger key, which can be any key at all) shows as a
; raw "$XX" hex code rather than guessing a charset-dependent glyph.
describe_combo:
        ldx #0
        stx describe_combo_col
        ldy #0                     ; modifier byte
        lda (scr_ptr_lo),y
        and #MOD_CTRL
        beq dc_try_cmdre
        ldx #<mod_ctrl_name
        ldy #>mod_ctrl_name
        jsr copy_mod_prefix
        jmp dc_key
dc_try_cmdre:
        ldy #0
        lda (scr_ptr_lo),y
        and #MOD_CMDRE
        beq dc_try_shift
        ldx #<mod_cmdre_name
        ldy #>mod_cmdre_name
        jsr copy_mod_prefix
        jmp dc_key
dc_try_shift:
        ldy #0
        lda (scr_ptr_lo),y
        and #MOD_SHIFT
        beq dc_key
        ldx #<mod_shift_name
        ldy #>mod_shift_name
        jsr copy_mod_prefix
dc_key:
        ldy #1                     ; key byte
        lda (scr_ptr_lo),y
        sta describe_key
        cmp #$9d
        bne dk_try_right
        ldx #<key_left_name
        ldy #>key_left_name
        jsr copy_key_name
        jmp dc_pad
dk_try_right:
        cmp #$1d
        bne dk_try_up
        ldx #<key_right_name
        ldy #>key_right_name
        jsr copy_key_name
        jmp dc_pad
dk_try_up:
        cmp #$91
        bne dk_try_down
        ldx #<key_up_name
        ldy #>key_up_name
        jsr copy_key_name
        jmp dc_pad
dk_try_down:
        cmp #$11
        bne dk_hex
        ldx #<key_down_name
        ldy #>key_down_name
        jsr copy_key_name
        jmp dc_pad
dk_hex:
        lda #'$'
        jsr describe_combo_putc
        lda describe_key
        jsr describe_combo_put_hex_byte
dc_pad:
        ldx describe_combo_col
dc_pad_loop:
        cpx #15
        beq dc_pad_done
        lda blank_char
        sta row_scratch+15,x
        inx
        jmp dc_pad_loop
dc_pad_done:
        rts

describe_combo_col:
        byte 0
describe_key:
        byte 0

; .a = one character -> row_scratch+15+describe_combo_col, advances
; the column. Bounds-checked against the 15-byte combo field so a
; pathological table entry (shouldn't happen -- nothing writes one)
; can't walk this off the end of row_scratch.
describe_combo_putc:
        ldx describe_combo_col
        cpx #15
        bcs dcp_rts
        sta row_scratch+15,x
        inc describe_combo_col
dcp_rts:
        rts

; .x/.y = lo/hi of a NUL-terminated name -> appended via describe_
; combo_putc, same bounds-checking that gives for free
copy_mod_prefix:
        stx copy_mod_prefix_load+1
        sty copy_mod_prefix_load+2
        ldy #0
copy_mod_prefix_loop:
copy_mod_prefix_load:
        lda $ffff,y
        beq copy_mod_prefix_done
        jsr describe_combo_putc
        iny
        jmp copy_mod_prefix_loop
copy_mod_prefix_done:
        rts

copy_key_name:
        stx copy_key_name_load+1
        sty copy_key_name_load+2
        ldy #0
copy_key_name_loop:
copy_key_name_load:
        lda $ffff,y
        beq copy_key_name_done
        jsr describe_combo_putc
        iny
        jmp copy_key_name_loop
copy_key_name_done:
        rts

; .a = byte -> two hex-digit screen codes via describe_combo_putc
describe_combo_put_hex_byte:
        pha
        lsr
        lsr
        lsr
        lsr
        jsr describe_combo_put_hex_nibble
        pla
        and #$0f
        jsr describe_combo_put_hex_nibble
        rts

describe_combo_put_hex_nibble:
        tax
        lda hex_digits,x
        jsr describe_combo_putc
        rts

hex_digits:
        {alpha:poke}
        ascii "0123456789ABCDEF"
        {alpha:normal}

; --- set_screen_line_local: scr_ptr_lo/hi = SCREEN_RAM + .a*40 ---
; Own copy of tada-client.asm's set_screen_line (not shared -- separate
; assembly). .a = row number (0-24).
set_screen_line_local:
        asl
        tax
        lda row_offsets,x
        clc
        adc #<SCREEN_RAM
        sta scr_ptr_lo
        lda row_offsets+1,x
        adc #>SCREEN_RAM
        sta scr_ptr_hi
        rts

row_offsets:
        word 0,   40,  80,  120, 160, 200, 240, 280, 320, 360
        word 400, 440, 480, 520, 560, 600, 640, 680, 720, 760
        word 800, 840, 880, 920, 960

; --- Plain untransformed byte fill (own copy -- see config_menu.asm's
; fill_bytes for the shared shape) ---
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

; --- Plain untransformed 40-byte copy (own copy) ---
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

row_scratch:
        area 30, $20

selected_row:
        byte 0

; draw_popup_blank_list's own row counter -- see that routine's own
; comment for why X can't be trusted to survive its jsr poke_line.
blank_list_row:
        byte 0

; keymap_table_end_lo/hi: KERNAL SAVE wants the END address (X/Y), not
; a byte count -- module_start computes this once (KEYMAP_TABLE_PTR +
; KEYMAP_TABLE_SIZE), right after JT_SAVE_SCREEN, so key_save's own
; SETLFS/SAVE sequence just reads it straight rather than recomputing
; it inline every time. KEYMAP_TABLE_SIZE is hand-computed (378), not
; written as MAX_BINDINGS*BINDING_SIZE -- same C64List byte/word-
; inference gotcha keymap.asm's own KEYMAP_TABLE_SIZE comment documents.
keymap_table_end_lo:
        byte 0
keymap_table_end_hi:
        byte 0
KEYMAP_TABLE_SIZE = 405           ; MAX_BINDINGS(15) * BINDING_SIZE(27)

; {alpha:poke} builds single poke-able screen codes for '>'/' ' -- same
; verified {alpha:poke} ASCII->screen-code conversion config_menu.asm's
; own marker_char/blank_char use.
{alpha:poke}
marker_char:
        ascii ">"
blank_char:
        ascii " "
{alpha:normal}

; Fixed 12-char name strings (padded with trailing spaces to exactly
; 12 -- copy_name12 always copies all 12 bytes, no length checking).
{alpha:pokealt}
name_empty:
        ascii "-- empty -- "
name_word_left:
        ascii "Word Left   "
name_word_right:
        ascii "Word Right  "
name_home:
        ascii "Home        "
name_end:
        ascii "End         "
name_open_editor:
        ascii "Open Editor "
{alpha:normal}

; NUL-terminated modifier-prefix/key-name fragments -- describe_combo
; copies these via copy_mod_prefix/copy_key_name (stops at the NUL, not
; a fixed length, since these vary in length and get concatenated).
{alpha:poke}
mod_ctrl_name:
        ascii "CTRL+"
        byte 0
mod_cmdre_name:
        ascii "C=+"
        byte 0
mod_shift_name:
        ascii "SHFT+"
        byte 0
key_left_name:
        ascii "LEFT"
        byte 0
key_right_name:
        ascii "RIGHT"
        byte 0
key_up_name:
        ascii "UP"
        byte 0
key_down_name:
        ascii "DOWN"
        byte 0
{alpha:normal}

; Popup box text -- same PETSCII line-drawing screen codes/{alpha:
; pokealt} convention as config_menu.asm's own (see that file's box-
; text comment for the full verification story: $70/$6e/$6d/$7d/$40/
; $5d, cross-checked against table.py's PETSCII Border).
{alpha:pokealt}
top_border:
        byte $20,$20,$20,$20, $70
        area 30, $40
        byte $6e, $20,$20,$20,$20
row_title:
        byte $20,$20,$20,$20, $5d
        ascii "         Keymap Editor        "
        byte $5d, $20,$20,$20,$20
row_blank:
        byte $20,$20,$20,$20, $5d
        ascii "                              "
        byte $5d, $20,$20,$20,$20
row_help1:
        byte $20,$20,$20,$20, $5d
        ascii " Up/Down: Select  Return: Bind"
        byte $5d, $20,$20,$20,$20
row_help2:
        byte $20,$20,$20,$20, $5d
        ascii " S: Save   Stop: Cancel       "
        byte $5d, $20,$20,$20,$20

; key_capture_combo swaps row_help1's screen line for one of these two
; (then restores row_help1 itself when done) via draw_message_row --
; same shape/field width, verified 30 ascii chars each the same way
; row_help1/row_help2's own strings are.
capture_prompt_msg:
        byte $20,$20,$20,$20, $5d
        ascii " Press new key, Stop to cancel"
        byte $5d, $20,$20,$20,$20
capture_conflict_msg:
        byte $20,$20,$20,$20, $5d
        ascii " That combo is already used!  "
        byte $5d, $20,$20,$20,$20
bottom_border:
        byte $20,$20,$20,$20, $6d
        area 30, $40
        byte $7d, $20,$20,$20,$20

; "S0:KEYMAP.CFG" and "KEYMAP.CFG" share one copy of the filename text
; -- keymap_filename points partway into keymap_scratch_command's own
; bytes ("S0:" + "KEYMAP.CFG" back to back), so key_save's plain SAVE
; and scratch_keymap_file's SCRATCH command both read out of the same
; "KEYMAP.CFG" bytes rather than duplicating them (Ryan's idea,
; 2026-09-02). Lengths are assemble-time label-difference constants,
; not hand-counted -- hand-counting is exactly what produced the
; off-by-one this replaced (the old "@0:KEYMAP.CFG" code had `lda #14`
; for a 13-byte string). {alpha:alt} for the $C1-$DA uppercase-letter
; range a real disk directory needs (see keymap.asm's own
; filename-block comment for the full reasoning); "S0:" is plain
; ASCII/PETSCII punctuation, unaffected by alpha:alt either way (that
; mode only remaps letters).
{alpha:alt}
keymap_scratch_command:
        ascii "S0:"
keymap_filename:
        ascii "KEYMAP.CFG"
keymap_filename_end:
{alpha:normal}
KEYMAP_SCRATCH_LEN = keymap_filename_end - keymap_scratch_command  ; 13
KEYMAP_FILENAME_LEN = keymap_filename_end - keymap_filename        ; 10
