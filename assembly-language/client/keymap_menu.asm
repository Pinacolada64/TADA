; keymap_menu.asm — loadable "Keymap Editor (C64)" popup overlay.
;
; Not resident: LOADed on demand by tada-client.asm's load_keymap_menu
; (KERNAL LOAD "KEYMAP.ED",8,1), reached via a local F7 keypress in
; read_line_not_return -- NOT a server-sent trigger the way config_
; menu.asm/help_menu.asm are, since neither the keymap nor macro text
; mean anything to the server (see keymap.asm's own header for the
; full reasoning). Discarded once this returns control via
; JT_RESUME_LOCAL -- NOT JT_RESUME, unlike every other overlay module:
; JT_RESUME's target (prompt_loop) unconditionally blocks waiting for
; a server byte before it'll even look at the keyboard again, which is
; fine when a server-sent trigger opened the popup (the server's
; usually already sent, or about to send, something else) but hangs
; forever here, since nothing server-side has any reason to react to a
; purely local popup closing. See constants.asm's own JT_RESUME_LOCAL
; comment for the live 2026-09-14 repro that found this.
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
                             ; explains the 5 nav functions (word-left,
                             ; word-right, home via CRSR-UP, home via
                             ; the real CLR/HOME key, end) + the
                             ; built-in "open the editor" binding + up
                             ; to 9 macros
MACRO_TEXT_LEN = 24
BINDING_SIZE   = 3 + MACRO_TEXT_LEN

; keymap_default (keymap.asm) binds Home to two adjacent slots -- slot
; 2 (plain CRSR-UP) and slot 3 (the real CLR/HOME key) -- since both
; are legitimate physical shortcuts for the same action. Showing them
; as two separate "Home" rows here would look like a duplicate/bug
; (Ryan's own catch live 2026-09-18), so this list instead folds them
; into ONE row: HOME_MERGE_ROW is that row's index (still 2 -- rows 0/1
; are unaffected), NAV_ROWS is one less than NAV_SLOT_COUNT since slot
; 3 no longer gets its own row, and combo_subindex (declared near
; selected_row below) tracks which of the two underlying slots
; (HOME_MERGE_ROW's primary slot + combo_subindex, 0 or 1) CRSR-LEFT/
; CRSR-RIGHT and RETURN currently act on within that one row -- see
; row_to_slot's own comment for the row->slot arithmetic this implies.
; Hardcoded to this one specific row/slot rather than a general N-way
; merge table: only Home ever needs this today, and key_capture_combo
; never changes a slot's action byte, so which slots merge is fixed at
; build time, not something that needs runtime discovery.
HOME_MERGE_ROW = 2

; --- Two-screen split (Ryan's ask, 2026-09-18): the list is now one of
; two pages, "Keymap Editor" (the 5 nav rows above) and "Macro Editor"
; (the remaining macro slots), selected via a header row shown above
; row 0 -- CRSR-UP past row 0 moves focus onto the header (header_
; focused=1); CRSR-LEFT/RIGHT while there toggle active_page and
; redraw; CRSR-DOWN returns focus to the list at that page's row 0.
; NAV_SLOT_COUNT is the number of real keymap_table slots the nav page
; covers (word-left, word-right, Home's two merged slots, end, open-
; editor); every slot from there up is a macro slot. NAV_ROWS/MACRO_
; ROWS are each page's own row count (NAV_ROWS accounts for the Home
; merge, same as the old TOTAL_ROWS did); PAGE_ROWS_MAX is the larger
; of the two, used as draw_list's fixed loop bound so switching to a
; shorter page still blanks whatever the longer page left on screen
; (see draw_list's own comment).
NAV_SLOT_COUNT = 6
NAV_ROWS       = HOME_MERGE_ROW + 3   ; word-left, word-right, home
                                         ; (merged), end, open-editor = 5
MACRO_ROWS     = MAX_BINDINGS - NAV_SLOT_COUNT   ; 9
PAGE_ROWS_MAX  = MACRO_ROWS

; Column/length of each heading within row_title_base's 30-char field
; (draw_title) -- "Keymap Editor" (13 chars) at column 2, "Macro
; Editor" (12 chars) at column 18: 2+13+3+12 = 30. Must be defined here,
; before draw_title's own use of them below, same forward-reference
; caveat BOX_TOP_ROW/BOX_ROWS's own comment documents for this
; assembler's `=` constants.
KEYMAP_LABEL_COL = 2
KEYMAP_LABEL_LEN = 13
MACRO_LABEL_COL  = 18
MACRO_LABEL_LEN  = 12

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
        tsx                          ; save the real stack depth we were
        stx module_entry_sp           ; entered at -- keymap_menu_loop's
                                       ; own `jsr dispatch_keymap_key`
                                       ; leaves a return address pushed
                                       ; for as long as this popup stays
                                       ; open (dispatch reaches key_save/
                                       ; key_cancel via a tail JMP, never
                                       ; an RTS back through it), so
                                       ; every visit needs its own clean
                                       ; way to discard that -- see
                                       ; key_save/key_cancel's own exit,
                                       ; which restores this before
                                       ; jumping out. Confirmed live
                                       ; 2026-09-17: without this, every
                                       ; open/close cycle permanently
                                       ; leaked 2 bytes of stack (the
                                       ; orphaned return into keymap_
                                       ; menu_loop), and once some
                                       ; unrelated rts elsewhere finally
                                       ; unwound the real stack down to
                                       ; that leftover depth, it popped
                                       ; the leak instead of its own
                                       ; return address -- silently
                                       ; jumping back into this dead
                                       ; loop from the middle of a
                                       ; completely unrelated keystroke,
                                       ; looking like a random hang with
                                       ; no visible popup on screen.
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

        ; Snapshot keymap_table before anything in this visit can
        ; touch it (key_capture_combo writes live) -- key_cancel
        ; restores from this if the player backs out without saving.
        jsr backup_keymap_table

        lda #0
        sta selected_row
        sta combo_subindex
        sta header_focused
        sta active_page
        jsr draw_popup
        jsr draw_title
        jsr draw_list

        ; Clear keymap.asm's own "Opening keymap editor..." status-row
        ; message now that the popup is genuinely open and drawn (Ryan's
        ; ask, 2026-09-18) -- that message is useful feedback DURING the
        ; real disk LOAD time load_keymap_menu's own LOAD takes, but has
        ; nothing left to say once we're actually here. Pushing a single-
        ; NUL "message" through the same push_keymap_status_msg path
        ; key_save/key_cancel use pads the whole status row with blanks
        ; at display time (build_status_line's own contract -- see its
        ; comment in screen-handler.asm), same as if nothing had ever
        ; been pushed; there's no separate JT_CLEAR_STATUS_LINE entry
        ; needed for this.
        ldx #<keymap_status_clear_msg
        ldy #>keymap_status_clear_msg
        jsr push_keymap_status_msg

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
        byte $9d                  ; cursor left -- next sub-entry within
        word key_subselect_next    ; a merged row (Home only, for now);
                                     ; no-op on any other row -- reversed
                                     ; from LEFT=prev/RIGHT=next 2026-09-18
                                     ; (Ryan's preference, confirmed live)
        byte $1d                  ; cursor right -- previous sub-entry
        word key_subselect_prev
        byte $53                  ; 'S' -- save and exit
        word key_save
        byte $03                  ; RUN/STOP -- cancel and exit
        word key_cancel
        byte $0d                  ; RETURN -- capture a new combo for
        word key_capture_combo    ; the selected row (nav slots only)
KEYMAP_KEYS_END = * - keymap_keys

; CRSR-UP past row 0 moves focus onto the header instead of wrapping to
; the last row (Ryan's ask, 2026-09-18) -- see the two-screen-split
; comment near NAV_ROWS/MACRO_ROWS above. Already-header-focused is a
; no-op: there's nothing above the header to move to.
key_row_up:
        lda header_focused
        bne kru_rts
        lda selected_row
        bne kru_dec
        lda #1
        sta header_focused
        jsr draw_list            ; hide the row marker -- describe_
                                    ; binding_row's own marker check
                                    ; skips it entirely while header_
                                    ; focused is set
        jsr draw_title
        jmp draw_help_footer      ; picks the header-focused footer now
kru_rts:
        rts
kru_dec:
        dec selected_row
        jmp key_row_reset_sub

; CRSR-DOWN while header-focused returns to the list at the active
; page's row 0 (mirrors key_row_up's own header entry above). CRSR-DOWN
; from the list's own LAST row now also moves to the header instead of
; wrapping back to row 0 (Ryan's ask, 2026-09-19 -- symmetric with
; CRSR-UP past row 0) -- get_page_rows (not the old fixed TOTAL_ROWS)
; gives the active page's own row count, since that now depends on
; active_page.
key_row_down:
        lda header_focused
        beq krd_list
        lda #0
        sta header_focused
        sta selected_row
        sta combo_subindex
        jsr draw_title              ; header_focused just cleared -- the
                                       ; active heading's color needs to
                                       ; drop back to white (key_row_done
                                       ; below only redraws the list/
                                       ; footer, not the title)
        jmp key_row_done
krd_list:
        lda selected_row
        clc
        adc #1
        sta krd_next_row
        jsr get_page_rows
        cmp krd_next_row
        beq krd_header             ; next_row == page's row count -> past
                                     ; the last row, enter the header
        lda krd_next_row
        sta selected_row
        jmp key_row_reset_sub
krd_header:
        lda #1
        sta header_focused
        jsr draw_list              ; hide the row marker, same as
                                     ; key_row_up's own header entry
        jsr draw_title
        jmp draw_help_footer
key_row_reset_sub:
        lda #0
        sta combo_subindex        ; moving to a different row always
                                     ; re-highlights that row's FIRST
                                     ; sub-entry, same idea as any list
                                     ; UI resetting a nested selection
                                     ; when the outer selection moves
key_row_done:
        jsr draw_list
        jmp draw_help_footer        ; tail call -- selected_row just
                                     ; changed, so which footer belongs
                                     ; on rows 18/19 may have too
                                     ; (key_subselect_prev/next never
                                     ; call this: sub-selecting within a
                                     ; row can't change WHICH row is
                                     ; selected, so the footer choice
                                     ; can't change either)

; --- key_subselect_prev/next: move combo_subindex between HOME_MERGE_
; ROW's two sub-entries (Ryan's ask, 2026-09-18: comma-separate the two
; Home bindings into one row rather than showing two identical-looking
; "Home" rows, with these two keys picking which one RETURN/Save-
; conflict-checking currently targets). Bound CRSR-RIGHT->prev, CRSR-
; LEFT->next (reversed from the naive left=prev/right=next mapping,
; same day, confirmed live -- Ryan's preference) -- see keymap_keys'
; own dispatch entries above. No-op on every other row -- nothing else
; has more than one sub-entry to move between.
;
; Repurposed while header_focused (2026-09-18): CRSR-LEFT/RIGHT there
; instead toggle active_page and redraw -- both keys do the same thing
; since there are only two pages, so either direction just flips it.
; jmp (not a short branch) to toggle_active_page from here since that
; routine lives elsewhere in the file and a direct beq/bne to it risks
; the out-of-range-branch gotcha (see keymap.asm's own MAX_BINDINGS*
; BINDING_SIZE comment / project memory feedback_6502_branch_range) --
; the local beq to the fall-through label right below stays safely in
; range either way.
;
; Also gated on active_page==0: HOME_MERGE_ROW is only a meaningful row
; number on the Keymap Editor page -- on the Macro Editor page, that
; same row index is an ordinary macro slot with no sub-entries, and
; letting combo_subindex go nonzero there would silently point RETURN/
; duplicate-checking (edit_slot = row_to_slot(selected_row) +
; combo_subindex) at the WRONG macro slot, one past the intended one.
key_subselect_prev:
        lda header_focused
        beq ksp_check_row
        jmp toggle_active_page
ksp_check_row:
        lda active_page
        bne ksp_rts
        lda selected_row
        cmp #HOME_MERGE_ROW
        bne ksp_rts
        lda combo_subindex
        beq ksp_rts                ; already at the first sub-entry
        dec combo_subindex
        jsr draw_list
ksp_rts:
        rts

key_subselect_next:
        lda header_focused
        beq ksn_check_row
        jmp toggle_active_page
ksn_check_row:
        lda active_page
        bne ksn_rts
        lda selected_row
        cmp #HOME_MERGE_ROW
        bne ksn_rts
        lda combo_subindex
        bne ksn_rts                ; already at the last sub-entry (1)
        inc combo_subindex
        jsr draw_list
ksn_rts:
        rts

; --- toggle_active_page: flip active_page and redraw the title (new
; highlighted heading) and list (that page's own rows) -- reached only
; from key_subselect_prev/next above while header_focused is set.
; Resets selected_row/combo_subindex to 0 so returning to the list (via
; key_row_down) always lands on the new page's first row rather than
; whatever row number happened to be selected on the OTHER page (which
; may not even exist there -- e.g. Macro Editor's row 8 has no
; counterpart on the 5-row Keymap Editor page).
toggle_active_page:
        lda active_page
        eor #1
        sta active_page
        lda #0
        sta selected_row
        sta combo_subindex
        jsr draw_title
        jsr draw_list
        jmp draw_help_footer

; --- get_page_rows: .A = the active page's row count (NAV_ROWS or
; MACRO_ROWS) -- used by key_row_down's wraparound and draw_list's own
; loop, both of which need this rather than the old fixed TOTAL_ROWS
; now that it depends on active_page.
get_page_rows:
        lda active_page
        bne gpr_macro
        lda #NAV_ROWS
        rts
gpr_macro:
        lda #MACRO_ROWS
        rts

; --- row_to_slot: .x = a row index (0..MAX(NAV_ROWS,MACRO_ROWS)-1),
; interpreted against active_page -> .x = the real keymap_table slot
; that row's PRIMARY entry describes ---
; Keymap Editor page (active_page=0): rows before HOME_MERGE_ROW map
; 1:1 to the same-numbered slot; rows after it are shifted up by one
; (slot HOME_MERGE_ROW+1 no longer gets its own row, folded into HOME_
; MERGE_ROW's row instead -- see that constant's own comment). HOME_
; MERGE_ROW's row itself also maps to slot HOME_MERGE_ROW unchanged
; (its primary/first sub-entry) -- callers that need the SECOND sub-
; entry add combo_subindex on top of this result themselves (see
; edit_slot below), since that only ever applies to this one row.
; Macro Editor page (active_page=1): no merge -- slot = row +
; NAV_SLOT_COUNT, the first real slot number past the nav page's own.
row_to_slot:
        lda active_page
        beq rts_nav_page
        txa
        clc
        adc #NAV_SLOT_COUNT
        tax
        rts
rts_nav_page:
        cpx #HOME_MERGE_ROW+1
        bcc rts_row_to_slot        ; row <= HOME_MERGE_ROW: slot == row
        inx                         ; row > HOME_MERGE_ROW: slot = row+1
rts_row_to_slot:
        rts

; --- edit_slot: the ONE real keymap_table slot RETURN/duplicate-
; checking currently act on -- row_to_slot(selected_row) + combo_
; subindex. combo_subindex is only ever nonzero on HOME_MERGE_ROW (key_
; subselect_prev/next enforce that), so this is just row_to_slot's
; result unchanged on every other row.
edit_slot:
        ldx selected_row
        jsr row_to_slot
        txa
        clc
        adc combo_subindex
        sta edit_slot_value
        rts

edit_slot_value:
        byte 0

; --- selected_slot_addr: scr_ptr_lo/hi = KEYMAP_TABLE_PTR +
; edit_slot*BINDING_SIZE --- same moving-pointer walk describe_
; binding_row uses, factored out here since key_capture_combo and its
; own duplicate check both need a slot's address and this file only
; has one zero-page pointer (scr_ptr_lo/hi) to compute it into --
; recomputed fresh each use rather than cached, cheap at MAX_BINDINGS-1
; iterations of a short loop.
selected_slot_addr:
        jsr edit_slot
        lda KEYMAP_TABLE_PTR
        sta scr_ptr_lo
        lda KEYMAP_TABLE_PTR+1
        sta scr_ptr_hi
        ldx edit_slot_value
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
        lda header_focused         ; no row is selected while the header
        beq kcc_have_row            ; itself has focus -- nothing to bind
        rts
kcc_have_row:
        jsr selected_slot_addr
        ldy #2                     ; action byte
        lda (scr_ptr_lo),y
        cmp #ACTION_EMPTY
        beq kcc_rts
        cmp #ACTION_MACRO
        beq kcc_rts

        ; Snapshot the KERNAL's own PNT/PNTR ($d1/$d2/$d3 -- cursor_
        ; toggle's own screen-position pointer, read_line_loop's own
        ; update_cursor uses the same pair) before update_capture_
        ; display starts repositioning them at the live readout below --
        ; restored in kcc_done so this wait's own cursor blinking can't
        ; leak a stale position into read_line once this popup closes.
        ; cursor_phase itself needs no snapshot/restore: read_line_loop's
        ; own cursor_hide call (right before dispatching ANY keystroke,
        ; including the F7 that opened this popup) already guarantees
        ; it's 0 (erased) on entry here, and kcc_done's own JT_CURSOR_
        ; HIDE call puts it back to exactly that same state before
        ; restoring $d1-$d3, so the two states always match up.
        lda $d1
        sta capture_saved_pnt_lo
        lda $d2
        sta capture_saved_pnt_hi
        lda $d3
        sta capture_saved_pntr

        ldx #<capture_prompt_msg
        ldy #>capture_prompt_msg
        jsr draw_message_row
        lda #0
        sta capture_display_key
        jsr update_capture_display  ; draw the (blank) live row once
                                       ; up front, before the first key
kcc_wait:
        jsr GETIN
        cmp #0
        bne kcc_got_key
        jsr update_capture_display  ; no key this tick -- still refresh
                                       ; modifiers/blank-on-release live
        jmp kcc_wait
kcc_got_key:
        sta capture_display_key     ; cache for the live row regardless
                                       ; of accept/reject below
        pha
        jsr update_capture_display
        pla
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
        jsr JT_CURSOR_HIDE          ; erase the live-readout cursor at
                                     ; its CURRENT ($d1-$d3) position --
                                     ; must happen before restoring
                                     ; those below, while they still
                                     ; point at the real on-screen spot
                                     ; the cursor was last drawn at
        lda capture_saved_pnt_lo
        sta $d1
        lda capture_saved_pnt_hi
        sta $d2
        lda capture_saved_pntr
        sta $d3
        jsr draw_help_footer        ; restore rows 18/19 -- row 19 was
                                     ; overwritten by the live combo
                                     ; readout; picks the plain or
                                     ; HOME_MERGE_ROW-specific footer
                                     ; depending on selected_row, same
                                     ; as key_row_up/down's own call
        jsr draw_list
kcc_rts:
        rts

capture_key:
        byte 0
capture_mod:
        byte 0
capture_saved_pnt_lo:
        byte 0
capture_saved_pnt_hi:
        byte 0
capture_saved_pntr:
        byte 0

; --- Live modifier/key readout during the capture wait (Ryan's idea,
; see [[project_keymap_editor_idea]]/[[project_3_key_rollover_idea]] in
; project memory -- show C=/Ctrl/Shift + the held key live, blanking
; the key the instant it's released rather than on a timeout, now that
; keyboard_rollover.asm's SFDX gives real hold/release state). Reuses
; describe_combo as-is (same 15-char "Ctrl+D"-style field the saved
; list itself shows) rather than a bespoke renderer -- capture_live_mod/
; capture_live_key are laid out exactly like a real binding record
; (mod byte then key byte) so scr_ptr_lo/hi can point straight at them.
capture_live_mod:
        byte 0
capture_live_key:
        byte 0
; Cached from the last real GETIN event seen this wait (not necessarily
; the one that ends up accepted -- a rejected duplicate re-enters the
; wait and this keeps showing what was actually pressed). 0 = nothing
; cached yet.
capture_display_key:
        byte 0

; --- update_capture_display: refresh row 19's live readout, and blink
; a real cursor (via JT_CURSOR_HIDE/JT_UPDATE_CURSOR) right after
; whatever's currently printed there -- Ryan's ask, 2026-09-18: hide
; the cursor while (re)printing a modifier name/key name, then show it
; again once done, so it visibly "follows" the live text and the
; player can tell the client is still waiting for input rather than
; hung. Safe to call every kcc_wait iteration -- SHFLAG is live
; already (no lag); SFDX reverting to $40 blanks the key portion the
; instant the physical key releases, independent of GETIN's own
; buffered timing. Clobbers A/X/Y and scr_ptr_lo/hi (both already
; treated as call-clobbered by every other routine in this file).
update_capture_display:
        jsr JT_CURSOR_HIDE          ; erase wherever the cursor was left
                                     ; blinking last tick, BEFORE this
                                     ; tick's text overwrites that row --
                                     ; a harmless no-op on the very first
                                     ; call (cursor_phase starts at 0,
                                     ; see key_capture_combo's own
                                     ; comment on why that's guaranteed)
        lda $028d                  ; SHFLAG -- live modifier state
        and #(MOD_SHIFT|MOD_CMDRE|MOD_CTRL)
        sta capture_live_mod
        lda $cb                    ; SFDX -- live matrix coordinate of
                                     ; the key currently held, $40 = none
        cmp #$40
        bne ucd_have_key
        lda #0                     ; no key held -- key_names' $00
        sta capture_live_key        ; sentinel blanks the field for us
        jmp ucd_describe
ucd_have_key:
        lda capture_display_key
        sta capture_live_key
ucd_describe:
        lda #<capture_live_mod
        sta scr_ptr_lo
        lda #>capture_live_mod
        sta scr_ptr_hi
        jsr describe_combo         ; fills row_scratch+15..+29
        lda describe_combo_col     ; how much of the 15-byte field is
        sta ucd_text_len            ; real text, not padding -- describe_
                                     ; combo left this as a side effect;
                                     ; cache it now before anything else
                                     ; in this routine can reuse it
        ldx #0
ucd_copy_loop:
        lda row_scratch+15,x
        sta capture_live_row+11,x
        inx
        cpx #15
        bne ucd_copy_loop
        ldx #<capture_live_row
        ldy #>capture_live_row
        stx poke_src_lo
        sty poke_src_hi
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta poke_dst_hi
        jsr poke_line

        ; Point PNT/PNTR ($d1/$d2/$d3) at the cell right after the live
        ; text just printed (capture_live_row+11 is column 11 of this
        ; physical row -- see ucd_copy_loop above) -- JT_UPDATE_CURSOR
        ; toggles reverse-video on THAT cell if the blink timer calls
        ; for it this tick, giving a real cursor that visibly sits right
        ; where the next character would go, "following" the printout.
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta $d1
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta $d2
        lda #11
        clc
        adc ucd_text_len
        sta $d3
        jmp JT_UPDATE_CURSOR        ; tail call -- its own rts returns
                                     ; straight to our caller

ucd_text_len:
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
        cpx edit_slot_value        ; skip the REAL slot being edited --
        beq ccd_next                 ; NOT selected_row: on a merged row
                                       ; (HOME_MERGE_ROW) those two
                                       ; differ, and the OTHER sub-entry
                                       ; sharing that row is a distinct
                                       ; real slot that a genuine
                                       ; duplicate check must still catch
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

; --- draw_help_footer: (re)paint rows 18/19 with whichever footer
; matches the current focus/selection -- row_help1_header/row_help2_
; header while header_focused (Left/Right/Down are what matter there,
; not Up/Down: Select or RETURN: Bind); otherwise row_help1/row_help2
; normally, or row_help1_merged/row_help2_merged while HOME_MERGE_ROW
; is selected ON THE KEYMAP EDITOR PAGE specifically (active_page==0 --
; that same row number is an ordinary macro row on the other page, with
; no Left/Right sub-entry to call out). Called from key_row_up/down
; (via key_row_done) whenever selected_row/header_focused/active_page
; changes, and from kcc_done to restore rows 18/19 after the capture
; wait's own message/live-readout overwrote them.
draw_help_footer:
        lda header_focused
        beq dhf_list_focus
        ldx #<row_help1_header
        ldy #>row_help1_header
        jsr draw_message_row
        ldx #<row_help2_header
        ldy #>row_help2_header
        jmp dhf_row2
dhf_list_focus:
        lda active_page
        bne dhf_normal
        lda selected_row
        cmp #HOME_MERGE_ROW
        beq dhf_merged
dhf_normal:
        ldx #<row_help1
        ldy #>row_help1
        jsr draw_message_row
        ldx #<row_help2
        ldy #>row_help2
        jmp dhf_row2
dhf_merged:
        ldx #<row_help1_merged
        ldy #>row_help1_merged
        jsr draw_message_row
        ldx #<row_help2_merged
        ldy #>row_help2_merged
dhf_row2:
        stx poke_src_lo               ; draw_message_row only targets
        sty poke_src_hi               ; row 18 -- row 19 needs its own
                                        ; poke_line call here
        lda #<(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta poke_dst_lo
        lda #>(SCREEN_RAM+(BOX_TOP_ROW+19)*40)
        sta poke_dst_hi
        jmp poke_line               ; tail call -- its own rts returns
                                     ; straight to our caller

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
        ; $c023 (constants.asm), not zero page, so it can't be passed
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
        jsr JT_RESTORE_SCREEN      ; must happen BEFORE the status message
                                     ; below, not after -- JT_RESTORE_
                                     ; SCREEN repaints the WHOLE screen
                                     ; (status row included) from the
                                     ; snapshot module_start took when
                                     ; this popup opened, which already
                                     ; had "Opening keymap editor..." on
                                     ; it; pushing the Save message first
                                     ; and restoring after was tried and
                                     ; confirmed live 2026-09-18 to
                                     ; silently stomp the new message
                                     ; right back to the stale one
        ldx #<keymap_saved_msg
        ldy #>keymap_saved_msg
        jsr push_keymap_status_msg ; "Saved keymap." -- via JT_STATUS_
                                     ; PUSH_RESET/JT_BUILD_STATUS_LINE,
                                     ; not a direct call: this file is a
                                     ; separate standalone .prg, unlike
                                     ; keymap.asm's own init_keymap/
                                     ; load_keymap_menu, which {include:}
                                     ; into the resident program and so
                                     ; can call status_push_reset/build_
                                     ; status_line by label directly --
                                     ; see constants.asm's own comment on
                                     ; JT_STATUS_PUSH_RESET
        ldx module_entry_sp        ; discard whatever this visit's own
        txs                          ; keymap_menu_loop/dispatch call
                                       ; depth left pushed -- see module_
                                       ; start's own comment on why
        jmp JT_RESUME_LOCAL        ; NOT JT_RESUME -- see constants.asm's
                                     ; own comment on why this popup
                                     ; can't go through the normal
                                     ; wait-for-server-data resume path

; --- push_keymap_status_msg: X/Y = lo/hi of a NUL-terminated,
; {alpha:pokealt}-encoded string -- push it as a fresh, single-message
; status-row batch via the resident client's own status_push_reset/
; build_status_line, reached through JT_STATUS_PUSH_RESET/JT_BUILD_
; STATUS_LINE since this file is a standalone .prg (see constants.asm's
; own comment on those two entries). Y is preserved by JT_BUILD_STATUS_
; LINE's own contract (it's just build_status_line's X/Y-pointer
; argument), so no save/restore needed around either call here.
push_keymap_status_msg:
        jsr JT_STATUS_PUSH_RESET
        jmp JT_BUILD_STATUS_LINE  ; tail call -- its own rts returns
                                    ; straight to key_save/key_cancel

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

; --- Cancel: restore keymap_table from module_start's own snapshot,
; then hand back without touching disk. key_capture_combo writes
; straight into the resident keymap_table live, not a staged copy --
; this used to be a real gap (any combo captured earlier in this same
; popup visit stayed live even after Cancel), fixed by restore_
; keymap_table undoing whatever this visit changed. Kept as its own
; key/routine (rather than aliasing key_save) since the two now
; genuinely diverge: Save keeps the live (possibly edited) table and
; also persists it to disk; Cancel discards the edits and touches disk
; not at all.
key_cancel:
        jsr restore_keymap_table
        jsr JT_RESTORE_SCREEN      ; must happen BEFORE the status
                                     ; message below -- see key_save's own
                                     ; comment on why (repaints the WHOLE
                                     ; screen, status row included, from
                                     ; the pre-popup snapshot)
        ldx #<keymap_aborted_msg
        ldy #>keymap_aborted_msg
        jsr push_keymap_status_msg ; "Aborted." -- see key_save's own
                                     ; comment on why this goes through
                                     ; the JT_* trampolines rather than a
                                     ; direct call
        ldx module_entry_sp        ; see key_save's own comment on this
        txs
        jmp JT_RESUME_LOCAL        ; NOT JT_RESUME -- see constants.asm's
                                     ; own comment on why this popup
                                     ; can't go through the normal
                                     ; wait-for-server-data resume path

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

        ; Row +1 (the title) is left blank here -- module_start's own
        ; jsr draw_title (right after this returns) fills it with the
        ; two selectable page headings instead of a single static
        ; string; nothing renders to the physical screen in between
        ; (no vsync wait, just consecutive jsr calls), same as how the
        ; list rows below start blank until draw_list's own first call.

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

; --- draw_title: (re)draw row +1 (the header) from row_title_base,
; reverse-videoing whichever page's heading is active_page's current
; value -- same EOR #$80 technique describe_combo_merged's dcm_invert_
; range uses for the sub-entry highlight, applied here to a fixed
; screen row instead of a variable one (the header never moves), so a
; compile-time absolute address is used directly rather than set_
; screen_line_local's runtime row math. Called from module_start (once,
; at open) and from key_row_up/toggle_active_page (whenever header_
; focused or active_page changes).
draw_title:
        ldx #0
dt_copy_loop:
        lda row_title_base,x
        sta row_scratch,x
        inx
        cpx #30
        bne dt_copy_loop

        lda active_page
        bne dt_macro_active
        ldx #KEYMAP_LABEL_COL
        ldy #KEYMAP_LABEL_LEN
        jmp dt_do_invert
dt_macro_active:
        ldx #MACRO_LABEL_COL
        ldy #MACRO_LABEL_LEN
dt_do_invert:
        stx dt_pos
dt_invert_loop:
        ldx dt_pos
        lda row_scratch,x
        eor #$80
        sta row_scratch,x
        inc dt_pos
        dey
        bne dt_invert_loop

        ; Color: both headings reset to white every call, then the
        ; ACTIVE one recolored yellow if the header currently has focus
        ; (Ryan's ask, 2026-09-19) -- reverse video alone (above) marks
        ; WHICH page is active regardless of focus; this second cue
        ; marks whether the header itself is the thing CRSR-LEFT/RIGHT
        ; would act on right now, same distinction row_scratch's marker
        ; column draws between "this is the selected row" (list-
        ; focused) and no marker at all (header-focused). Resetting
        ; BOTH ranges to white unconditionally (rather than just the
        ; formerly-focused one) means toggle_active_page's own draw_
        ; title call never has to remember which heading was last
        ; colored.
        ldx #KEYMAP_LABEL_COL
        ldy #KEYMAP_LABEL_LEN
        lda #1                     ; white
        jsr dt_set_color
        ldx #MACRO_LABEL_COL
        ldy #MACRO_LABEL_LEN
        lda #1
        jsr dt_set_color
        lda header_focused
        beq dt_color_done
        lda active_page
        bne dt_focus_macro
        ldx #KEYMAP_LABEL_COL
        ldy #KEYMAP_LABEL_LEN
        jmp dt_focus_color
dt_focus_macro:
        ldx #MACRO_LABEL_COL
        ldy #MACRO_LABEL_LEN
dt_focus_color:
        lda #7                     ; yellow
        jsr dt_set_color
dt_color_done:

        ; Assemble the full 40-byte row directly at its fixed screen
        ; address (5 border bytes + row_scratch's 30 + 5 border bytes),
        ; same split draw_list's own dl_left_border/dl_middle/dl_right_
        ; border uses, but via plain abs,Y addressing since this row's
        ; address is a compile-time constant, not a per-call variable
        ; one -- no set_screen_line_local / (scr_ptr_lo),y needed.
        ldy #0
dt_left_border:
        lda row_blank,y
        sta SCREEN_RAM+(BOX_TOP_ROW+1)*40,y
        iny
        cpy #5
        bne dt_left_border
dt_middle:
        ldx #0
dt_middle_loop:
        lda row_scratch,x
        sta SCREEN_RAM+(BOX_TOP_ROW+1)*40,y
        iny
        inx
        cpx #30
        bne dt_middle_loop
dt_right_border:
        lda row_blank,y
        sta SCREEN_RAM+(BOX_TOP_ROW+1)*40,y
        iny
        cpy #40
        bne dt_right_border
        rts

; --- dt_set_color: .X = start column within row +1's 30-char field,
; .Y = length, .A = VIC-II color number -> pokes that many COLOR_RAM
; cells starting there. +5 in the address below is the same border
; offset row_scratch's own content sits at within the physical 40-byte
; row (see draw_list's dl_left_border for the SCREEN_RAM equivalent).
; Reuses dt_pos as its position counter, same as dt_invert_loop above
; -- the two never run concurrently (both only ever called from within
; draw_title itself).
dt_set_color:
        sta dt_color_val
        stx dt_pos
dt_set_color_loop:
        ldx dt_pos
        lda dt_color_val
        sta COLOR_RAM+(BOX_TOP_ROW+1)*40+5,x
        inc dt_pos
        dey
        bne dt_set_color_loop
        rts

dt_color_val:
        byte 0

dt_pos:
        byte 0

; --- draw_list: (re)draw PAGE_ROWS_MAX rows -- the active page's own
; rows (NAV_ROWS or MACRO_ROWS, from keymap_table via describe_binding_
; row) plus, if the OTHER page is longer, blank rows over whatever it
; left behind on screen (Ryan's two-screen-split ask, 2026-09-18: the
; loop always runs to PAGE_ROWS_MAX -- the longer page's count -- so
; toggling from Macro Editor's 9 rows down to Keymap Editor's 5 clears
; rows 5-8 instead of leaving stale macro rows showing underneath).
; Called once at startup and again after every CRSR UP/DOWN/LEFT/RIGHT
; -- redraws every row rather than just the marker/highlight column,
; simplest correct thing for a list this small (9 rows * 40 bytes = 360
; bytes, negligible).
draw_list:
        jsr get_page_rows
        sta page_row_count
        ldx #0
draw_list_loop:
        stx draw_list_row
        cpx page_row_count
        bcs dl_row_blank           ; past the active page's own rows --
                                     ; blank row_scratch instead of
                                     ; describing a real slot
        jsr describe_binding_row  ; fills row_scratch (30 bytes)
        jmp dl_place
dl_row_blank:
        ldy #0
dl_row_blank_loop:
        lda blank_char
        sta row_scratch,y
        iny
        cpy #30
        bne dl_row_blank_loop
dl_place:
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
        cpx #PAGE_ROWS_MAX
        bne draw_list_loop
        rts

draw_list_row:
        byte 0

; get_page_rows's result, cached once per draw_list call rather than
; re-fetched every loop iteration (cheap either way, but cpx needs a
; memory operand -- CPX has no indexed addressing mode -- so this has
; to live somewhere regardless).
page_row_count:
        byte 0

; key_row_down's own scratch -- selected_row+1, cached here so it can be
; compared against get_page_rows's result (which clobbers A) and then
; either stored (still in range) or discarded (out of range -> header).
krd_next_row:
        byte 0

; --- describe_binding_row: build row_scratch (30 bytes) for row .x ---
; Layout: marker(1) space(1) name(12) space(1) combo(15) = 30 -- combo
; starts at offset 15 (1+1+12+1), NOT 17. Real bug, caught live
; 2026-09-02: the combo field was written at row_scratch+17, 2 bytes
; past where this layout actually puts it, so the 15-byte field ran
; off the end of the 30-byte row_scratch buffer into whatever followed
; it in memory -- selected_row and blank_list_row, as it happened,
; silently overwritten with padding/text bytes (typically $20) every
; single time a row was drawn. Confirmed via the VICE monitor: row_
; scratch = $2d93, +30 = $2db1 = selected_row exactly.
;
; .x is a ROW index (0..page_row_count-1 for the CURRENT active_page --
; row_to_slot itself reads active_page too), NOT a raw keymap_table
; slot index, since 2026-09-18 -- HOME_MERGE_ROW's own comment explains
; why those can now differ (row_to_slot converts). describe_slot always
; holds the row's PRIMARY slot (both merged slots share the same
; action, so the primary slot's action/name describes the whole row
; either way); the marker and merged-combo highlight both need the ROW
; number too, so that's kept separately in describe_row.
describe_binding_row:
        stx describe_row
        jsr row_to_slot            ; .x (row) -> .x (primary slot)
        stx describe_slot
        ; marker -- suppressed entirely while header_focused (no row is
        ; "selected" in that state, focus is on the header instead)
        lda header_focused
        bne dbr_no_marker
        lda selected_row
        cmp describe_row
        bne dbr_no_marker
        lda marker_char
        jmp dbr_marker_store
dbr_no_marker:
        lda blank_char
dbr_marker_store:
        sta row_scratch+0
        lda blank_char
        sta row_scratch+1

        ; keymap_slot_addr: scr_ptr_lo/hi = KEYMAP_TABLE_PTR +
        ; describe_slot*BINDING_SIZE -- same moving-pointer technique
        ; keymap.asm's own keymap_dispatch uses (MAX_BINDINGS*
        ; BINDING_SIZE exceeds what an 8-bit Y-indexed offset can
        ; reach), just walked once per row here instead of scanned in a
        ; search loop.
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
        ; Home is the one action with two bound slots sharing a row
        ; (HOME_MERGE_ROW) -- every other action always has exactly one
        ; slot, so only this branch ever needs the merged-combo path.
        lda describe_row
        cmp #HOME_MERGE_ROW
        bne dbr_combo
        jsr describe_combo_merged
        rts
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
describe_row:
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
; Data-driven (Ryan's ask, 2026-09-02): mod_names/key_names below (own
; comment) are walked by a small generic table-scan, not a hardcoded
; cmp chain -- easy to extend (a future ALT modifier bit for a C128
; editor, more named keys) by adding a table row, not new code. Only
; shows the FIRST modifier bit found (checked in mod_names' own order
; -- CTRL, then C=, then SHIFT) rather than every one that's set --
; keymap_dispatch itself still matches on the FULL mask regardless,
; this is a display simplification only, fine since no default or
; realistic binding combines more than one modifier. A key not in
; key_names (a macro's own trigger key, which can be any key at all)
; shows as a raw "$XX" hex code rather than guessing a charset-
; dependent glyph.
describe_combo:
        ldx #0
        stx describe_combo_col
        jsr describe_combo_append
        jmp dc_pad

; --- describe_combo_merged: build row_scratch+15..+29 for HOME_MERGE_
; ROW's two underlying slots (describe_slot and describe_slot+1),
; comma-separated -- "up,home" for the built-in default. scr_ptr_lo/hi
; must already point at describe_slot's own mod/key bytes on entry
; (describe_binding_row's own address-walk already leaves them there).
; When this row is the currently selected one, the sub-entry combo_
; subindex points at is shown in reverse video (EOR #$80 on each of its
; screen codes, via dcm_invert_range below) so CRSR-LEFT/RIGHT's effect
; is visible -- same technique tada-client.asm's own cursor_toggle uses
; for the blinking input cursor, not a bracket/punctuation marker
; (Ryan's ask, 2026-09-18, replacing this routine's first cut, which
; wrapped the highlighted combo in '['/']' instead) -- otherwise both
; combos show plain, since there's nothing to highlight on a row that
; isn't selected.
describe_combo_merged:
        lda #0
        sta describe_combo_col
        lda selected_row
        cmp describe_row
        beq dcm_highlight_yes
        lda #0
        jmp dcm_highlight_store
dcm_highlight_yes:
        lda #1
dcm_highlight_store:
        sta dcm_highlight          ; 1 if this row is selected, else 0

        ; --- first sub-entry: describe_slot, combo_subindex 0 ---
        lda describe_combo_col
        sta dcm_start_col
        jsr describe_combo_append
        lda dcm_highlight
        beq dcm_skip_invert0
        lda combo_subindex
        bne dcm_skip_invert0
        jsr dcm_invert_range        ; flip reverse-video on [dcm_start_
                                     ; col, describe_combo_col) -- just
                                     ; what describe_combo_append wrote
dcm_skip_invert0:
        lda #$2c                   ; ',' -- c64list treats a literal
                                     ; comma as an addressing-mode
                                     ; separator even inside #'x', so
                                     ; this needs the raw hex value
        jsr describe_combo_putc

        ; --- advance scr_ptr_lo/hi by one BINDING_SIZE to describe_
        ; slot+1's own mod/key bytes ---
        lda scr_ptr_lo
        clc
        adc #BINDING_SIZE
        sta scr_ptr_lo
        bcc dcm_no_carry
        inc scr_ptr_hi
dcm_no_carry:

        ; --- second sub-entry: describe_slot+1, combo_subindex 1 ---
        lda describe_combo_col
        sta dcm_start_col
        jsr describe_combo_append
        lda dcm_highlight
        beq dcm_skip_invert1
        lda combo_subindex
        cmp #1
        bne dcm_skip_invert1
        jsr dcm_invert_range
dcm_skip_invert1:
        jmp dc_pad

; EOR #$80 (reverse-video bit) on row_scratch+15+dcm_start_col through
; row_scratch+15+describe_combo_col-1 -- exactly the bytes the most
; recent describe_combo_append call just wrote, nothing else (the
; comma/padding stay plain either way).
dcm_invert_range:
        ldx dcm_start_col
dcm_invert_loop:
        cpx describe_combo_col
        bcs dcm_invert_done
        lda row_scratch+15,x
        eor #$80
        sta row_scratch+15,x
        inx
        jmp dcm_invert_loop
dcm_invert_done:
        rts

dcm_start_col:
        byte 0
dcm_highlight:
        byte 0

; --- describe_combo_append: same as describe_combo above, but doesn't
; reset describe_combo_col first or pad afterward -- factored out
; 2026-09-18 so describe_combo_merged (below) can append TWO combos'
; worth of text into one field, separated by its own comma/bracket
; punctuation, then pad once at the very end instead of twice.
describe_combo_append:
        ldy #0                     ; modifier byte
        lda (scr_ptr_lo),y
        sta describe_mod
        ldx #0
dc_mod_loop:
        cpx #MOD_NAMES_END
        beq dc_key                 ; no modifier bit matched -- fine,
                                     ; plenty of bindings have none
        lda mod_names,x
        and describe_mod
        beq dc_mod_next
        lda mod_names+1,x
        sta dc_name_lo
        lda mod_names+2,x
        tay
        ldx dc_name_lo
        jsr copy_mod_prefix
        jmp dc_key
dc_mod_next:
        txa
        clc
        adc #3
        tax
        jmp dc_mod_loop

dc_key:
        ldy #1                     ; key byte
        lda (scr_ptr_lo),y
        sta describe_key
        ldx #0
dc_key_loop:
        cpx #KEY_NAMES_END
        beq dk_hex                 ; no name for this key -- fall back
        lda key_names,x
        cmp describe_key
        bne dc_key_next
        lda key_names+1,x
        sta dc_name_lo
        lda key_names+2,x
        tay
        ldx dc_name_lo
        jsr copy_key_name
        rts
dc_key_next:
        txa
        clc
        adc #3
        tax
        jmp dc_key_loop
        ; No name for this key -- show the actual letter/symbol instead
        ; of a raw hex code where possible (Ryan's ask, 2026-09-02:
        ; "ctrl+$04" doesn't read as "ctrl+D" to anyone). GETIN's
        ; unshifted-letter PETSCII codes ($41-$5A, 'A'-'Z') need NO
        ; conversion here -- confirmed against this file's own already-
        ; working {alpha:pokealt} static strings (e.g. name_word_left's
        ; assembled bytes: 'W'/'L' poke as their own plain ASCII value,
        ; $57/$4C, and display as uppercase): this popup's charset
        ; (mode 2, mixed case) maps screen codes $41-$5A straight to
        ; uppercase glyphs, same as PETSCII already has them. $20-$3F
        ; (space, digits, punctuation) is likewise identical between
        ; PETSCII and screen code in this charset. Anything outside
        ; both ranges (control codes, unnamed cursor/function keys,
        ; SHIFT/CBM-modified letter codes) still falls back to hex --
        ; there's no single glyph for those without a bigger table.
dk_hex:
        lda describe_key
        cmp #$41
        bcc dk_try_symbol
        cmp #$5b                  ; > 'Z' ($5a)?
        bcs dk_try_symbol
        jsr describe_combo_putc   ; 'A'-'Z': PETSCII == screen code already
        rts
dk_try_symbol:
        lda describe_key
        cmp #$20
        bcc dk_hex_fallback
        cmp #$40                  ; > '?' ($3f)?
        bcs dk_hex_fallback
        jsr describe_combo_putc   ; $20-$3f: PETSCII == screen code already
        rts
dk_hex_fallback:
        lda #'$'
        jsr describe_combo_putc
        lda describe_key
        jmp describe_combo_put_hex_byte ; tail call -- its own rts
                                          ; returns straight to our caller

; --- dc_pad: pad row_scratch+15..+29 with blank_char from describe_
; combo_col onward -- shared tail for describe_combo (single combo) and
; describe_combo_merged (two combos comma-separated) below, called
; explicitly by each rather than fallen into, since describe_combo_
; append (above) must be able to append a SECOND combo's text after the
; first without padding in between.
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
describe_mod:
        byte 0
dc_name_lo:
        byte 0

; --- mod_names / key_names: (byte, word) rows -- a mask/key value and
; the NUL-terminated name to show for it (copy_mod_prefix/copy_key_name
; both just append a NUL-terminated string via describe_combo_putc, so
; one shape works for both tables despite one being a mask and the
; other an exact byte match). Add a row here to name a new key or
; modifier; no code changes needed in describe_combo itself. Checked
; in this order -- see describe_combo's own comment on why only the
; first match shows for modifiers.
mod_names:
        byte MOD_CTRL
        word mod_ctrl_name
        byte MOD_CMDRE
        word mod_cmdre_name
        byte MOD_SHIFT
        word mod_shift_name
MOD_NAMES_END = * - mod_names

key_names:
        byte $9d
        word key_left_name
        byte $1d
        word key_right_name
        byte $91
        word key_up_name
        byte $11
        word key_down_name
        byte $85
        word key_f1_name
        byte $86
        word key_f3_name
        byte $87
        word key_f5_name
        byte $88
        word key_f7_name
        byte $13                  ; real CLR/HOME key, unshifted
        word key_home_name
        byte $93                  ; SHIFT+CLR/HOME (the actual CLR
        word key_clear_name        ; function) -- $93/147 decimal, NOT
                                     ; $83/131: $13 (19 decimal, HOME)
                                     ; with bit 7 set for SHIFT is
                                     ; $13+$80=$93, not $83
        byte $00                  ; sentinel: "no key held" -- GETIN
        word key_none_name         ; never returns 0 for a real press,
                                     ; so this is safe to reuse as
                                     ; update_capture_display's "blank
                                     ; the key portion" signal, an
                                     ; empty name that lets dc_pad's
                                     ; own blanking do the rest
KEY_NAMES_END = * - key_names

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

; 0 = Keymap Editor page (the 5 nav rows), 1 = Macro Editor page (the
; remaining macro slots) -- see the two-screen-split comment near NAV_
; ROWS/MACRO_ROWS above. Only CRSR-LEFT/RIGHT while header_focused
; (toggle_active_page) ever change this.
active_page:
        byte 0

; 0 = a list row has focus (selected_row is meaningful), 1 = the header
; above the list has focus (selected_row/combo_subindex are not --
; describe_binding_row's own marker check skips entirely while this is
; set, and key_capture_combo/key_subselect_prev/next's row-specific
; logic are no-ops here, repurposed instead for page-toggling). Set by
; key_row_up on row 0, cleared by key_row_down.
header_focused:
        byte 0

; Which of HOME_MERGE_ROW's two underlying slots (0 = describe_slot
; itself, 1 = describe_slot+1) CRSR-LEFT/CRSR-RIGHT and RETURN act on.
; Only ever nonzero while selected_row == HOME_MERGE_ROW -- key_row_up/
; key_row_down reset it to 0 on every row change, and key_subselect_
; prev/next (dispatch table above) are themselves no-ops on any other
; row, so nothing else needs to guard against a stale nonzero value
; leaking onto some other row's addressing.
combo_subindex:
        byte 0

; draw_popup_blank_list's own row counter -- see that routine's own
; comment for why X can't be trusted to survive its jsr poke_line.
blank_list_row:
        byte 0

; keymap_table_end_lo/hi: KERNAL SAVE wants the END address (X/Y), not
; a byte count -- module_start computes this once (KEYMAP_TABLE_PTR +
; KEYMAP_TABLE_SIZE), right after JT_SAVE_SCREEN, so key_save's own
; SETLFS/SAVE sequence just reads it straight rather than recomputing
; it inline every time. KEYMAP_TABLE_SIZE is hand-computed (405), not
; written as MAX_BINDINGS*BINDING_SIZE -- same C64List byte/word-
; inference gotcha keymap.asm's own KEYMAP_TABLE_SIZE comment documents.
keymap_table_end_lo:
        byte 0
keymap_table_end_hi:
        byte 0

; Real stack depth at module_start's own entry -- see that routine's
; own comment; key_save/key_cancel restore SP from this right before
; exiting, discarding this visit's own keymap_menu_loop/dispatch call
; depth instead of leaking it.
module_entry_sp:
        byte 0
KEYMAP_TABLE_SIZE = 405           ; MAX_BINDINGS(15) * BINDING_SIZE(27)

; --- backup_keymap_table / restore_keymap_table: bulk-copy
; KEYMAP_TABLE_SIZE (405) bytes between the resident keymap_table (via
; KEYMAP_TABLE_PTR) and this module's own keymap_table_backup below --
; module_start takes the snapshot before anything in this popup visit
; can touch the live table; key_cancel restores from it so a combo
; captured but not explicitly Saved doesn't linger live in the
; resident table (see key_cancel's own comment).
;
; Too big for an 8-bit indexed loop (poke_line's own fixed 40-byte
; copy doesn't reach), and needs two moving pointers at once (source
; and destination), so this can't reuse this module's one zero-page
; pointer (scr_ptr_lo/hi) the way most of this file's other bulk work
; does -- instead it's two self-modified ABSOLUTE addresses (no
; indexing at all) each advanced a byte at a time with the same carry-
; propagation idea fill_bytes already uses for its own single
; self-modified pointer, just load-then-store instead of a constant
; fill, and a 16-bit remaining-count down to zero instead of fill_
; bytes' own convention of counting down a fixed byte total.
backup_keymap_table:
        lda KEYMAP_TABLE_PTR
        sta kt_copy_load+1
        lda KEYMAP_TABLE_PTR+1
        sta kt_copy_load+2
        lda #<keymap_table_backup
        sta kt_copy_store+1
        lda #>keymap_table_backup
        sta kt_copy_store+2
        jmp kt_copy_run

restore_keymap_table:
        lda #<keymap_table_backup
        sta kt_copy_load+1
        lda #>keymap_table_backup
        sta kt_copy_load+2
        lda KEYMAP_TABLE_PTR
        sta kt_copy_store+1
        lda KEYMAP_TABLE_PTR+1
        sta kt_copy_store+2
kt_copy_run:
        lda #<KEYMAP_TABLE_SIZE
        sta kt_copy_remaining_lo
        lda #>KEYMAP_TABLE_SIZE
        sta kt_copy_remaining_hi
kt_copy_loop:
        lda kt_copy_remaining_lo
        ora kt_copy_remaining_hi
        beq kt_copy_done
kt_copy_load:
        lda $ffff
kt_copy_store:
        sta $ffff
        inc kt_copy_load+1
        bne kt_copy_load_no_carry
        inc kt_copy_load+2
kt_copy_load_no_carry:
        inc kt_copy_store+1
        bne kt_copy_store_no_carry
        inc kt_copy_store+2
kt_copy_store_no_carry:
        lda kt_copy_remaining_lo
        bne kt_copy_dec_lo
        dec kt_copy_remaining_hi
kt_copy_dec_lo:
        dec kt_copy_remaining_lo
        jmp kt_copy_loop
kt_copy_done:
        rts

kt_copy_remaining_lo:
        byte 0
kt_copy_remaining_hi:
        byte 0

; This module's own copy of keymap_table, taken/restored around a
; popup visit -- NOT persisted anywhere itself (only the resident
; keymap_table, via key_save, ever gets written to KEYMAP.CFG).
keymap_table_backup:
        area KEYMAP_TABLE_SIZE, $00

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
key_f1_name:
        ascii "F1"
        byte 0
key_f3_name:
        ascii "F3"
        byte 0
key_f5_name:
        ascii "F5"
        byte 0
key_f7_name:
        ascii "F7"
        byte 0
key_home_name:
        ascii "HOME"
        byte 0
key_clear_name:
        ascii "CLEAR"
        byte 0
key_none_name:
        byte 0                     ; empty string -- see key_names' own
                                     ; comment on the $00 sentinel entry
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
; row_title_base: draw_title's own plain-text source for the header --
; NOT framed with the $20x4/$5d border bytes row_blank/row_help1/etc.
; carry, since draw_title assembles those itself (same 5+30+5 technique
; draw_list uses for the list rows below, see that routine's own
; comment) rather than a single fixed poke_line source -- it needs to
; EOR #$80 whichever heading is active before the border goes on.
; "Keymap Editor" (13 chars) starts at column KEYMAP_LABEL_COL (2),
; "Macro Editor" (12 chars) at MACRO_LABEL_COL (18) -- 2+13+3+12 = 30,
; both constants declared with draw_title below.
row_title_base:
        ascii "  Keymap Editor   Macro Editor"
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

; Alternate footer shown only while HOME_MERGE_ROW is selected (Ryan's
; ask, 2026-09-18) -- Left/Right only does anything on that one row, so
; the standard "Up/Down: Select  Return: Bind" / "S: Save  Stop:
; Cancel" footer stops being the whole story there. 'S: Save' is left
; out of row_help2_merged entirely (not just blanked to spaces) --
; Save still genuinely works from this row, this is purely about
; keeping the alternate footer focused on what Left/Right/Return mean
; here rather than repeating the global Save reminder. draw_help_footer
; (below) picks between this pair and row_help1/row_help2 every time
; selected_row changes.
row_help1_merged:
        byte $20,$20,$20,$20, $5d
        ascii " Left/Right: Choose shortcut  "
        byte $5d, $20,$20,$20,$20
row_help2_merged:
        byte $20,$20,$20,$20, $5d
        ascii " Return: Edit     Stop: Cancel"
        byte $5d, $20,$20,$20,$20

; Footer shown while header_focused (Ryan's two-screen-split ask,
; 2026-09-18) -- Left/Right and Down are what matter there; 'S: Save'
; is left out same as row_help2_merged's own precedent (Save still
; works, this just keeps the alternate footer focused on this state's
; own keys rather than repeating the global reminder).
row_help1_header:
        byte $20,$20,$20,$20, $5d
        ascii " Left/Right: Choose section   "
        byte $5d, $20,$20,$20,$20
row_help2_header:
        byte $20,$20,$20,$20, $5d
        ascii " Down: Select     Stop: Cancel"
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

; --- capture_live_row: row 19's content during the capture wait --
; " Key: " (6 chars) then update_capture_display's own 15-char
; describe_combo output (offsets 11..25), then 9 trailing blanks.
; Overwrites row_help2's screen line for the duration of the wait,
; restored (like row_help1) once key_capture_combo finishes.
capture_live_row:
        byte $20,$20,$20,$20, $5d
        ascii " Key: "
        area 15, $20
        byte $20,$20,$20,$20,$20,$20,$20,$20,$20
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

; Save/Cancel status-row messages -- pushed via push_keymap_status_msg
; (JT_STATUS_PUSH_RESET/JT_BUILD_STATUS_LINE). {alpha:pokealt} for the
; same reason as keymap.asm's own keymap_loading_msg/keymap_opening_msg:
; the status row is poked with real screen codes, not routed through
; CHROUT's PETSCII->screencode conversion.
{alpha:pokealt}
keymap_saved_msg:
        ascii "Saved keymap."
        byte 0
keymap_aborted_msg:
        ascii "Aborted."
        byte 0
{alpha:normal}

; Empty status-row "message" -- module_start pushes this to blank out
; keymap.asm's own "Opening keymap editor..." once this popup is fully
; drawn (see module_start's own comment). No {alpha:} block needed for
; a single NUL byte.
keymap_status_clear_msg:
        byte 0
