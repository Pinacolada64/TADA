; --- keymap.asm ---
; Player-customizable input-line keybindings: rebindable word-left/
; right and home/end navigation, plus a handful of macro slots that
; insert a short server command into the input line when pressed.
; Split out of tada-client.asm the same way screen-handler.asm was
; (Ryan's call, 2026-09-02) -- keeping this concern in its own file
; rather than growing tada-client.asm further.
;
; Purely client-side: neither the nav-function rebinds nor macro text
; mean anything to the server (a macro just inserts text into the input
; line exactly as if typed), so there's no protocol/round-trip the way
; Video Settings (c64_display.py) or Help (help_menu.py) have -- opened
; by a local F7 keypress (read_line_not_return's own check, in
; tada-client.asm), persisted to/from disk (KEYMAP.CFG) rather than
; sent to the server at all.
;
; Pulled into tada-client.asm via {include:keymap_pp.asm} (see the
; Makefile's own preprocessing step for this file, same SPLIT_MODULES
; mechanism screen-handler.asm uses) -- c64list resolves labels across
; the include globally, so everything here can freely reference and be
; referenced by tada-client.asm's own labels (KERNAL_SETNAM/SETLFS/
; LOAD, OVERLAY_BUF, copy_block/copy_src_lo/copy_dst_lo/copy_remaining_
; lo, load_overlay_error, term_chrout, read_line_word_left/right,
; read_line_home/end) -- those four KERNAL/OVERLAY_BUF constants are
; plain `=` there rather than {const:} specifically so this file's own,
; separate macro_preprocessor.py pass can see them (see KERNAL_PLOT's
; own comment in tada-client.asm for the general reasoning).

; KERNAL routines used only by read_error_channel below, local to this
; file (unlike KERNAL_SETNAM/SETLFS/LOAD above, nothing outside
; keymap.asm needs these, so plain {const:} is fine here).
{const: KERNAL_OPEN   $ffc0}
{const: KERNAL_CLOSE  $ffc3}
{const: KERNAL_CHKIN  $ffc6}
{const: KERNAL_CLRCHN $ffcc}
{const: KERNAL_CHRIN  $ffcf}
{const: KERNAL_READST $ffb7}

; ============================================================
; --- Keymap: rebindable input-line functions + macros ---
; ============================================================
; A fixed-size table read_line_loop's read_line_not_return consults
; (currently gated behind {ifdef:debug} -- see that call site's own
; comment in tada-client.asm and keymap_dispatch's below) to decide
; what a keypress does -- replaced that call site's own hardcoded cmp
; chain outright, 2026-09-02, once confirmed correct live. Each binding
; is BINDING_SIZE bytes:
;   modifier   (1 byte) -- bitmask matching $028d's own layout (see
;                            keymap_dispatch's own comment below): bit
;                            0 SHIFT, bit 1 Commodore, bit 2 CTRL
;   key        (1 byte) -- the raw GETIN byte for that key
;   action     (1 byte) -- ACTION_EMPTY (slot unused), a built-in nav
;                            function index, or ACTION_MACRO
;   macro_text (MACRO_TEXT_LEN bytes) -- NUL-terminated (NOT space-
;                            padded: macro text may legitimately
;                            contain a literal space, e.g. "give
;                            sword", so a space can't double as the
;                            terminator the way it does for screen
;                            padding elsewhere in this file). Only
;                            meaningful when action == ACTION_MACRO;
;                            unused for nav-function slots, where it's
;                            just whatever keymap_table's own zero-fill
;                            (or a loaded file's leftover bytes) left
;                            there -- harmless, nothing ever reads it
MAX_BINDINGS   = 15        ; the 5 built-in nav functions (word-left,
                             ; word-right, home via CRSR-UP, home via
                             ; the real CLR/HOME key, end), the built-in
                             ; "open the editor" binding (F7 by
                             ; default -- Ryan's ask, 2026-09-02: make
                             ; it a real, rebindable keymap_table entry
                             ; instead of a hardcoded special case, so
                             ; it's visible/rebindable the same as
                             ; everything else) plus up to 9 macros --
                             ; still fits without a scrollable list in
                             ; the editor popup
MACRO_TEXT_LEN = 24
BINDING_SIZE   = 3 + MACRO_TEXT_LEN
; Hand-computed rather than written as MAX_BINDINGS*BINDING_SIZE --
; confirmed (again -- see tada-client.asm's DIALOGUE_SHIFT_BYTES
; comment for the first time this bit) that C64List 4.06 infers a
; computed value's storage width from its byte-sized operands rather
; than the actual product, silently truncating 405 ($0195) down to
; $95 with just a warning (no error) to catch it. If MAX_BINDINGS or
; BINDING_SIZE changes, recompute this by hand: MAX_BINDINGS*BINDING_SIZE.
KEYMAP_TABLE_SIZE   = 405         ; MAX_BINDINGS(15) * BINDING_SIZE(27)
KEYMAP_DEFAULT_BINDINGS = 6
KEYMAP_DEFAULT_SIZE = BINDING_SIZE * KEYMAP_DEFAULT_BINDINGS

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

; keymap_table is a resident buffer (not inside any overlay module) --
; read_line_loop needs it on every keypress regardless of whether the
; editor popup has ever been opened, and it must also be a stable,
; predictable LOAD/SAVE target: KERNAL LOAD/SAVE ",8,1" always uses (or
; writes) a 2-byte header matching the file's actual load address, so
; this label's own assembled address IS that header -- both init_keymap
; below and keymap_menu.asm's future Save action must target this exact
; buffer for that convention to round-trip correctly. Zero-filled --
; NOT spaces: a zero action byte IS ACTION_EMPTY, so every one of the
; MAX_BINDINGS-KEYMAP_DEFAULT_BINDINGS slots init_keymap doesn't
; overwrite (no saved keymap uses them either) already reads correctly
; as "unused" the moment this label's own fill runs, no separate pass
; needed to mark them empty.
keymap_table:
        area KEYMAP_TABLE_SIZE, $00

; --- Built-in default keymap ---
; Matches this scheme's original home before the dispatch rework
; (2026-09-02, see keymap_dispatch's own comment): CTRL+CRSR-LEFT/DOWN
; for word-left/right, plain CRSR-UP/DOWN for home/end -- the exact
; hardcoded `cmp`/$028d checks tada-client.asm's read_line_not_return
; used to have, before keymap_dispatch + this table replaced them.
; Copied into keymap_table by init_keymap whenever no KEYMAP.CFG loads
; successfully (first run, or a disk without one), so a player who's
; never opened the Keymap Editor sees no behavior change at all. Only
; these KEYMAP_DEFAULT_SIZE bytes need copying -- the remaining
; MAX_BINDINGS-KEYMAP_DEFAULT_BINDINGS slots in keymap_table are
; already correct either way
; (its own area fill above if the default copy runs, or whatever a
; real LOAD wrote if one succeeded).
;
; NOTE (2026-08-24, inherited from the removed hardcoded version):
; CTRL+CRSR-LEFT/DOWN could not be live-confirmed working end-to-end in
; that session's sandboxed VICE testing environment -- isolated via a
; pure-BASIC PEEK(653)/GET A$ test (independent of this file entirely)
; that Tab (VICE's mapped CTRL key there) reads correctly as 4 when
; held alone, and C=+cursor correctly shows a nonzero SFDX value, but
; Tab+cursor (any direction) never registers any GETIN event at all.
; Looked like a VICE/GTK-specific limitation of the Tab key specifically
; when held with another key (Tab doubles as a GTK focus-navigation
; key), not a bug in the dispatch logic. Not re-confirmed since: 2026-
; 09-02's live retest of keymap_dispatch exercised plain typed text
; (catching the real A-preservation bug that session found), not a
; CTRL+cursor combo specifically -- only a synthetic monitor call has
; verified this exact binding so far (keymap_dispatch's own commit).
; Still worth confirming CTRL+CRSR specifically via real typed input,
; on real hardware or a differently-configured VICE, before relying on
; it.
keymap_default:
        byte MOD_CTRL, $9d, ACTION_WORD_LEFT
        area MACRO_TEXT_LEN, $20
        byte MOD_CTRL, $11, ACTION_WORD_RIGHT
        area MACRO_TEXT_LEN, $20
        byte 0, $91, ACTION_HOME
        area MACRO_TEXT_LEN, $20
        byte 0, $13, ACTION_HOME  ; real CLR/HOME key -- unbound before
                                    ; this fix, so it fell through
                                    ; keymap_dispatch and tada-client.asm's
                                    ; own DEL/INST/CRSR-LEFT/CRSR-RIGHT
                                    ; fallback chain straight into
                                    ; read_line_store, which echoed the
                                    ; raw $13 byte via CHROUT -- the real
                                    ; KERNAL HOME control code -- hijacking
                                    ; the screen cursor out from under the
                                    ; line editor's own cursor_pos
                                    ; bookkeeping instead of moving it
        area MACRO_TEXT_LEN, $20
        byte 0, $11, ACTION_END
        area MACRO_TEXT_LEN, $20
        byte 0, $88, ACTION_OPEN_EDITOR   ; F7, no modifier
        area MACRO_TEXT_LEN, $20

; --- init_keymap: LOAD a saved keymap from disk, or fall back to the
; built-in default ---
; Attempts KERNAL LOAD "KEYMAP.CFG",8,1 directly into keymap_table (the
; file's own embedded header, written by keymap_menu.asm's future Save
; action, always matches this exact address -- see keymap_table's own
; comment). FILE NOT FOUND ($04) is the ordinary first-run case (or a
; disk with no saved keymap), not a real error -- any LOAD failure at
; all just copies keymap_default in instead, no attempt to distinguish
; "no file" from "no drive"/other genuine errors, since the fallback is
; correct either way and there's no player-facing prompt to show a
; KERNAL error number to this early in boot (before the screen/status
; row are even fully set up). Called from tada-client.asm's own start:
; before init_nmi/init_swiftlink -- purely local disk I/O, unrelated to
; the network setup that follows it.
init_keymap:
        ; Publish keymap_table's real runtime address via KEYMAP_TABLE_
        ; PTR (constants.asm) -- see that constant's own comment for why
        ; this indirection exists at all (no fixed hand-chosen address
        ; was available, and keymap_menu.asm can't see this file's own
        ; `keymap_table = ...` symbol regardless, being a separate
        ; standalone .prg). Written unconditionally, first thing, before
        ; either the LOAD or the default-copy below run -- both target
        ; the exact same address either way, so there's no "which one
        ; happened" branching needed here.
        lda #<keymap_table
        sta KEYMAP_TABLE_PTR
        lda #>keymap_table
        sta KEYMAP_TABLE_PTR+1

        jsr status_push_reset
        ldx #<keymap_loading_msg
        ldy #>keymap_loading_msg
        jsr build_status_line     ; "Loading KEYMAP.CFG..." -- status_
                                    ; push_reset/build_status_line are
                                    ; already live by this point (called
                                    ; from tada-client.asm's start:
                                    ; right after init_screen, which
                                    ; sets up the status row and pushes
                                    ; its own build-date message --
                                    ; this replaces that batch, same as
                                    ; any other status_push_reset call)

        lda #10                  ; length of "KEYMAP.CFG" below
        ldx #<keymap_data_filename
        ldy #>keymap_data_filename
        jsr KERNAL_SETNAM
        lda #2                   ; file number -- distinct from load_
        ldx #8                   ; help_menu/load_keymap_menu's #1,
        ldy #1                   ; unrelated but harmless either way
        jsr KERNAL_SETLFS
        lda #0
        jsr KERNAL_LOAD
        bcs init_keymap_use_default
        jmp init_keymap_clear_error ; loaded successfully -- keymap_
                                      ; table already holds the real
                                      ; saved data
init_keymap_use_default:
        lda #<keymap_default
        sta copy_src_lo
        lda #>keymap_default
        sta copy_src_hi
        lda #<keymap_table
        sta copy_dst_lo
        lda #>keymap_table
        sta copy_dst_hi
        lda #<KEYMAP_DEFAULT_SIZE
        sta copy_remaining_lo
        lda #>KEYMAP_DEFAULT_SIZE
        sta copy_remaining_hi
        jsr copy_block
init_keymap_clear_error:
        ; Read (and discard) the drive's error channel regardless of
        ; whether the LOAD above succeeded or failed -- every CBM DOS
        ; operation queues a status message there ("00, OK,00,00" on
        ; success, "04, FILE NOT FOUND,00,00" etc on failure), and a
        ; real 1541's ERROR LED stays lit/blinking red until that
        ; message is actually read back, regardless of whether the
        ; caller (this routine) already decided how to handle the
        ; failure on its own via LOAD's carry flag. Ryan's catch --
        ; skipping this would leave a normal, expected first-run "no
        ; KEYMAP.CFG yet" outcome looking like a real drive problem to
        ; anyone glancing at the drive light.
        jsr read_error_channel

        ; Restore the build-date status message init_screen originally
        ; pushed (tada-client.asm's own build_msg/start:) -- "Loading
        ; KEYMAP.CFG..." above replaced that batch via status_push_
        ; reset, and nothing else pushes a new one before the player
        ; ever sees the screen, so without this it would just sit there
        ; permanently instead of the build date, which is what every
        ; earlier build showed and what Ryan wants to see again once
        ; loading's done.
        jsr status_push_reset
        ldx #<build_msg
        ldy #>build_msg
        jsr build_status_line
        rts

; --- read_error_channel: drain the drive's command/error channel ---
; OPEN 15,8,15 / read until EOI / CLOSE 15 -- the standard KERNAL
; pattern for clearing a drive's error status after any operation
; (LOAD, SAVE, etc). Discards every byte read rather than displaying
; it: the point here is purely to clear the ERROR LED, not to surface
; the message anywhere -- init_keymap already knows success/failure
; from LOAD's own carry flag and has nothing further to say about it.
read_error_channel:
        lda #0                    ; filename length 0 -- OPEN 15,8,15
        jsr KERNAL_SETNAM          ; (the command/error channel) takes
        lda #15                    ; no filename
        ldx #8
        ldy #15
        jsr KERNAL_SETLFS
        jsr KERNAL_OPEN
        ldx #15
        jsr KERNAL_CHKIN           ; channel 15 becomes the input channel
read_error_channel_loop:
        jsr KERNAL_CHRIN
        jsr KERNAL_READST
        and #$40                   ; EOI (end of the status line)
        beq read_error_channel_loop
        jsr KERNAL_CLRCHN
        lda #15
        jmp KERNAL_CLOSE            ; tail call -- CLOSE's own rts
                                     ; returns straight to our caller

; --- Load the keymap_menu overlay module and hand control to it ---
; Reached only via tada-client.asm's read_line_not_return F7 check -- a
; purely local keystroke, not a server-sent trigger the way every other
; overlay module is reached (CANVAS_STREAM_CONFIRM/DISPLAY_STREAM_
; CONFIRM/HELP_STREAM_CONFIRM), since neither the keymap editor nor
; what it edits (see init_keymap's own comment above) means anything to
; the server. Same LOAD ",8,1" convention as the others otherwise, and
; falls through to tada-client.asm's shared load_overlay_error on
; failure just like they do.
load_keymap_menu:
        jsr status_push_reset
        ldx #<keymap_opening_msg
        ldy #>keymap_opening_msg
        jsr build_status_line     ; "Opening keymap editor..." -- same
                                    ; direct-call pattern as init_keymap's
                                    ; own message above (this file is
                                    ; {include:}'d into the resident
                                    ; program, so status_push_reset/
                                    ; build_status_line are ordinary
                                    ; labels here, not JT_* trampolines --
                                    ; those exist for keymap_menu.asm's
                                    ; own Save/Cancel messages instead,
                                    ; being a separate standalone .prg)

        lda #9                   ; length of "KEYMAP.ED" below
        ldx #<keymap_menu_filename
        ldy #>keymap_menu_filename
        jsr KERNAL_SETNAM
        lda #1
        ldx #8
        ldy #1
        jsr KERNAL_SETLFS
        lda #0
        jsr KERNAL_LOAD
        bcs load_overlay_error
        jmp OVERLAY_BUF

; {alpha:pokealt} makes the `ascii` line below emit real screen codes
; at assembly time -- required, not cosmetic, same reasoning as
; tada-client.asm's own build_msg: redraw_status_row pokes queue
; content straight into SCREEN_RAM rather than going through CHROUT's
; own PETSCII->screencode conversion.
{alpha:pokealt}
keymap_loading_msg:
        ascii "Loading KEYMAP.CFG..."
        byte 0
keymap_opening_msg:
        ascii "Opening keymap editor..."
        byte 0
{alpha:normal}

; {alpha:alt} makes the `ascii` lines below emit $C1-$DA range bytes for
; the uppercase letters instead of plain $41-$5A ASCII -- required, not
; cosmetic, same reasoning as tada-client.asm's own petscii_editor_
; filename/etc block (a real C64 disk directory stores uppercase
; letters in that range, and LOAD/SAVE only succeed once SETNAM's
; filename bytes match it exactly). Reset to {alpha:normal} immediately
; after for the same reason that file resets it too.
{alpha:alt}
keymap_menu_filename:
        ascii "KEYMAP.ED"
; KEYMAP.CFG (init_keymap's own LOAD, and keymap_menu.asm's future SAVE)
; is data, not a program -- doesn't belong beside the overlay-module
; filename above, but needs the exact same $C1-$DA alpha:alt encoding
; for the same reason, so it stays in this one block rather than
; opening a second one just for one name.
keymap_data_filename:
        ascii "KEYMAP.CFG"
{alpha:normal}

; ============================================================
; --- Keymap dispatch (debug build only for now) ---
; ============================================================
; Called from tada-client.asm's read_line_not_return, wrapped there in
; {ifdef:debug}...{endif} -- see that call site's own comment for why:
; a match here fully replaces what the hardcoded chain below it would
; otherwise have done for the SAME key, but a miss falls through to
; that unchanged chain, so this can be live-tested (make debug-d64)
; without any risk to the normal build while it's still being verified.

; --- keymap_dispatch: check keymap_table for a binding matching the
; just-typed key + current modifier state ---
; Input: .A = the byte read_line_loop's GETIN call just returned.
; Output: carry SET and the key fully handled (caller should treat it
; as consumed, typically `jmp read_line_loop`) if a binding matched;
; carry CLEAR (caller falls through to its own further dispatch) if
; nothing in the table matches this key+modifier combo at all, or
; matches on key but not modifier (see keymap_dispatch_loop's own
; comment on why every slot is still checked in that case rather than
; stopping at the first key-only match).
;
; Scans keymap_table via a moving 16-bit pointer (scr_ptr_lo/hi, this
; file's own temporary borrow of tada-client.asm's shared indirect-
; pointer pair -- see set_screen_line's comment on the convention),
; NOT simple `LDA keymap_table,Y` indexed addressing: MAX_BINDINGS(15)
; * BINDING_SIZE(27) is 405, so slot 10's own base offset (270) already
; exceeds what an 8-bit Y can reach. Same self-modified/incremented-
; pointer technique copy_block already uses elsewhere in this
; codebase, just read-only here (no destination pointer needed).
keymap_dispatch:
        sta keymap_dispatch_key
        lda scr_ptr_lo             ; save the caller's scr_ptr_lo/hi --
        sta keymap_dispatch_save_lo ; this scan borrows the pair for
        lda scr_ptr_hi              ; MAX_BINDINGS*BINDING_SIZE bytes'
        sta keymap_dispatch_save_hi ; worth of reads, and a no-match
                                      ; scan leaves it sitting just past
                                      ; the end of keymap_table -- restored
                                      ; before every return below so
                                      ; nothing after this call ever sees
                                      ; that leftover value instead of
                                      ; whatever was really there
        lda #<keymap_table
        sta scr_ptr_lo
        lda #>keymap_table
        sta scr_ptr_hi
        ldx #MAX_BINDINGS
; keymap_dispatch_loop branches on the SLOT's own action byte to pick
; which basis a MACRO slot's own key byte is matched against -- 2026-
; 09-22 fix (Ryan's ask, after the keymap editor's own T-trigger UI
; shipped without this half ever being wired up): a macro slot stores
; its trigger's PHYSICAL MATRIX POSITION (capture_macro_combo's own
; SFDX-based capture in keymap_menu.asm, not this file -- see that
; routine's own header comment for why: GETIN folds CTRL+M down to the
; same $0d byte a bare RETURN produces, so only the matrix position can
; tell them apart), but this scan used to compare EVERY slot's key byte
; against keymap_dispatch_key -- a GETIN-DECODED byte -- regardless of
; which basis that slot actually stored. The two numbering systems
; barely overlap for the same physical key (e.g. 'T' is matrix
; position 22 but decodes to $54), so a captured trigger could never
; actually match during real gameplay -- the whole feature worked in
; the editor (captured, saved, displayed) but silently never fired.
; Nav slots are UNCHANGED (still keymap_dispatch_key, still the CRSR-
; UP/LEFT shift-masking below, which exists specifically to compensate
; for GETIN's OWN decode quirk of baking Shift into a cursor key's
; byte -- SFDX has no such quirk, a physical key's matrix position
; never changes just because Shift is also held, so a macro trigger
; needs no equivalent masking at all).
keymap_dispatch_loop:
        ldy #2                    ; action byte
        lda (scr_ptr_lo),y
        cmp #ACTION_EMPTY
        beq keymap_dispatch_next  ; unused slot -- skip without even
                                    ; checking key/modifier
        cmp #ACTION_MACRO
        beq keymap_dispatch_macro_key
        ldy #1                    ; key byte -- nav slot, decoded-byte
        lda (scr_ptr_lo),y          ; basis
        cmp keymap_dispatch_key
        bne keymap_dispatch_next  ; wrong key -- try the next slot
                                    ; (deliberately not stopping here:
                                    ; two slots could share a key with
                                    ; different modifiers, e.g. plain
                                    ; CRSR-DOWN for End vs CTRL+CRSR-
                                    ; DOWN for Word Right, same as the
                                    ; built-in default already does)
        jmp keymap_dispatch_nav_mod
keymap_dispatch_macro_key:
        ldy #1                    ; key byte -- macro slot, matrix-
        lda (scr_ptr_lo),y          ; position basis (see this loop's
        cmp $cb                     ; own header comment above)
        bne keymap_dispatch_next
        lda $028d
        and #(MOD_SHIFT|MOD_CMDRE|MOD_CTRL)
        sta keymap_dispatch_temp
        jmp keymap_dispatch_mod_ready ; no shift-masking for macros --
                                        ; see this loop's own header
                                        ; comment
keymap_dispatch_nav_mod:
        lda $028d                 ; live SHIFT/Commodore/CTRL status --
        and #(MOD_SHIFT|MOD_CMDRE|MOD_CTRL) ; $028D (653 decimal, SFDX)
        sta keymap_dispatch_temp  ; is the KERNAL's live SHIFT/Commodore/
                                    ; CTRL status (0/1/2/4), the C64
                                    ; cross-reference Compute's 128
                                    ; Programmer's Guide gives for the
                                    ; 128's own $D3 -- bit 2 (value 4)
                                    ; is CTRL. Cursor keys' own GETIN
                                    ; byte doesn't change when a
                                    ; modifier is also held (unlike
                                    ; letter keys), so this is the only
                                    ; way to detect that
        lda keymap_dispatch_key   ; CRSR-UP ($91) and CRSR-LEFT ($9d) are
        cmp #$91                   ; SHIFT+the physical CRSR-DOWN/RIGHT
        beq keymap_dispatch_mask_shift ; key -- the KERNAL keyboard scan
        cmp #$9d                   ; already baked that Shift press into
        bne keymap_dispatch_mod_ready ; the byte value itself before it
                                    ; ever reached GETIN's buffer, so
                                    ; Shift is still physically down (and
                                    ; $028D still reads it live) for as
                                    ; long as the key is held/repeating --
                                    ; found live 2026-09-17 as the real
                                    ; cause of CRSR-UP intermittently
                                    ; missing this table's plain (mod=0)
                                    ; ACTION_HOME entry and falling
                                    ; through to read_line_store's raw
                                    ; CHROUT echo instead, letting the
                                    ; real KERNAL cursor-up hijack the
                                    ; screen. Masking MOD_SHIFT out of
                                    ; the live snapshot for just these
                                    ; two key bytes treats Shift as
                                    ; already consumed by producing the
                                    ; shifted byte at all, leaving
                                    ; Commodore/CTRL free to still work
                                    ; as genuine extra modifiers on top
                                    ; (e.g. CTRL+CRSR-LEFT for word-left)
keymap_dispatch_mask_shift:
        lda keymap_dispatch_temp
        and #(MOD_CMDRE|MOD_CTRL)
        sta keymap_dispatch_temp
keymap_dispatch_mod_ready:
        ldy #0                     ; modifier byte
        lda (scr_ptr_lo),y
        cmp keymap_dispatch_temp
        bne keymap_dispatch_next  ; right key, wrong modifier -- keep
                                    ; scanning (same reasoning as above)
        ldy #2                     ; MATCH -- dispatch on this slot's
        lda (scr_ptr_lo),y        ; action byte
        jmp keymap_dispatch_run
keymap_dispatch_next:
        lda scr_ptr_lo
        clc
        adc #BINDING_SIZE
        sta scr_ptr_lo
        bcc keymap_dispatch_no_carry
        inc scr_ptr_hi
keymap_dispatch_no_carry:
        dex
        bne keymap_dispatch_loop
        lda keymap_dispatch_save_lo ; restore the caller's scr_ptr_lo/hi
        sta scr_ptr_lo               ; (see keymap_dispatch's own entry
        lda keymap_dispatch_save_hi  ; comment) before this scan's own
        sta scr_ptr_hi                ; leftover pointer can leak out
        lda keymap_dispatch_key    ; scanned every slot, no match --
        clc                         ; restore .A to the original typed
        rts                         ; byte before returning: the scan
                                     ; above has been freely reloading
                                     ; .A from keymap_table this whole
                                     ; time (table data, not the typed
                                     ; key), and the caller's own
                                     ; fallthrough-to-its-hardcoded-
                                     ; chain path depends on .A still
                                     ; holding the real key on a miss --
                                     ; confirmed live 2026-09-02: every
                                     ; unmatched key was landing in
                                     ; linebuf as whatever keymap_table
                                     ; byte the scan happened to end on
                                     ; instead of what was actually
                                     ; typed. keymap_dispatch_run's own
                                     ; match path doesn't need this --
                                     ; every branch there ends in either
                                     ; a jsr (nav function, doesn't
                                     ; touch linebuf directly) or
                                     ; keymap_insert_macro (inserts the
                                     ; MACRO's text, not the triggering
                                     ; key, so .A's value past that
                                     ; point is moot either way)

; --- keymap_dispatch_run: act on a matched slot's action byte ---
; Input: .A = the action byte; scr_ptr_lo/hi still points at the start
; of the matched binding record (keymap_insert_macro needs that for
; ACTION_MACRO). Falls through to keymap_dispatch_handled (carry set)
; for every recognized action; an action byte that matches none of
; them (shouldn't happen -- nothing writes a keymap_table record with
; an action outside this set) is still treated as handled rather than
; falling through to tada-client.asm's own hardcoded chain, since a
; real key/modifier match already occurred and re-running the
; hardcoded path for it would risk double-handling the keystroke.
keymap_dispatch_run:
        cmp #ACTION_WORD_LEFT
        bne keymap_dispatch_try_word_right
        jsr read_line_word_left
        jmp keymap_dispatch_handled
keymap_dispatch_try_word_right:
        cmp #ACTION_WORD_RIGHT
        bne keymap_dispatch_try_home
        jsr read_line_word_right
        jmp keymap_dispatch_handled
keymap_dispatch_try_home:
        cmp #ACTION_HOME
        bne keymap_dispatch_try_end
        jsr read_line_home
        jmp keymap_dispatch_handled
keymap_dispatch_try_end:
        cmp #ACTION_END
        bne keymap_dispatch_try_open_editor
        jsr read_line_end
        jmp keymap_dispatch_handled
keymap_dispatch_try_open_editor:
        cmp #ACTION_OPEN_EDITOR
        bne keymap_dispatch_try_macro
        jmp load_keymap_menu      ; never returns here -- same as read_
                                     ; line_not_return's old direct `jmp
                                     ; load_keymap_menu` for F7 used to
                                     ; do, before this became a real
                                     ; table entry; JT_RESUME (called by
                                     ; the popup itself when it's done)
                                     ; is what eventually hands control
                                     ; back, not this call chain's own
                                     ; rts
keymap_dispatch_try_macro:
        cmp #ACTION_MACRO
        bne keymap_dispatch_handled
        jsr keymap_insert_macro    ; needs scr_ptr_lo/hi still pointing
                                     ; at the matched binding record --
                                     ; restore happens after, below
keymap_dispatch_handled:
        lda keymap_dispatch_save_lo ; restore the caller's scr_ptr_lo/hi,
        sta scr_ptr_lo               ; same reasoning as the no-match
        lda keymap_dispatch_save_hi  ; exit above -- every action that
        sta scr_ptr_hi                ; reaches here (all but OPEN_EDITOR,
                                        ; which never returns to this
                                        ; caller at all) leaves scr_ptr_lo/
                                        ; hi exactly as this call found it
        sec
        rts

keymap_dispatch_key:
        byte 0
keymap_dispatch_temp:
        byte 0
keymap_dispatch_save_lo:
        byte 0
keymap_dispatch_save_hi:
        byte 0

; --- keymap_insert_macro: insert a matched binding's macro_text into
; linebuf at cursor_pos ---
; Same shift-and-insert idea as tada-client.asm's read_line_store, just
; applied to a whole string at once instead of one typed char. Input:
; scr_ptr_lo/hi points at the start of the matched binding record
; (keymap_dispatch_run's own pointer, still valid here -- nothing
; between there and this call moves it). Silently stops inserting
; (rather than erroring) if linelen hits MAX_LINE-1 partway through,
; same "buffer full, ignore the rest" behavior read_line_store already
; has for a single typed character, just covering the whole remaining
; macro instead of one char.
keymap_insert_macro:
        ldy #3                     ; macro_text starts at binding
                                     ; offset 3 (past modifier/key/action)
keymap_insert_macro_scan:
        cpy #BINDING_SIZE
        beq keymap_insert_macro_done
        lda (scr_ptr_lo),y
        beq keymap_insert_macro_done  ; NUL terminator
        pha
        lda linelen
        cmp #MAX_LINE-1
        bcc keymap_insert_macro_room
        pla
        jmp keymap_insert_macro_done  ; buffer full -- stop here,
                                        ; discarding the rest of the
                                        ; macro rather than partially
                                        ; inserting a mid-word fragment
keymap_insert_macro_room:
        ldx linelen                ; shift linebuf[cursor_pos..linelen-1]
                                     ; right by one to open a gap at
                                     ; cursor_pos -- same loop shape as
                                     ; read_line_store_shift
keymap_insert_macro_shift:
        cpx cursor_pos
        beq keymap_insert_macro_shift_done
        lda linebuf-1,x
        sta linebuf,x
        dex
        jmp keymap_insert_macro_shift
keymap_insert_macro_shift_done:
        pla                         ; recover the char to insert
        ldx cursor_pos
        sta linebuf,x
        inc linelen
        inc cursor_pos
        jsr term_chrout             ; echo it -- preserves X/Y itself,
                                      ; so our Y (macro_text scan index)
                                      ; survives this call untouched
        lda #0
        sta QTSW                    ; same defensive reset read_line_
                                      ; store/reprint_input_line already
                                      ; do after every echoed char, in
                                      ; case this macro's text contains
                                      ; a literal '"'
        iny
        jmp keymap_insert_macro_scan
keymap_insert_macro_done:
        rts
