; client-128.asm
; TADA Commodore 128 client -- early skeleton, NOT functional yet.
;
; See assembly-language/client/128_CLIENT_MECHANICS.md for the feature
; wishlist this is starting to work through. Runs in 128 native mode
; (not the C64-compatibility "GO 64" mode tada-client.asm targets) --
; separate binary, separate memory map, separate KERNAL. Does not share
; code with tada-client.asm; anything genuinely reusable (SwiftLink
; init, the receive-buffer protocol) gets pulled over deliberately once
; this has enough of its own scaffolding to need it, not blindly copied
; up front.
;
; Today this does the first two items on that wishlist: read the 40/80
; column switch at startup, and (VIC/40-column path) set up a
; scrolling dialogue window via ESC-T/ESC-B, a static status row, and a
; static input row below it, mirroring tada-client.asm's STATUS_ROW/
; PROMPT_ROW layout for a familiar player experience across both
; clients. Still no SwiftLink, no server connection, no tab-stop sync
; client code (that part already landed server-side only, see
; terminal.c128_tab_sync_bytes()).
;
; The 80-column (VDC) path (2026-09-29) keeps the same row layout but
; draws dialogue itself -- vdc.asm (8563 register/block-copy/fill
; primitives, modeled on the editor ROM's own $CDCC/$C40D/$C4A5) and
; vdc_screen.asm (dialogue output with block-copy scrolling, a 140-row
; scrollback history in bank 0 RAM under BASIC, CRSR UP/DOWN to view
; it). The input row still goes through input_editor.asm's KERNAL
; PLOT/CHROUT, which the editor points at the VDC in 80 columns.
;
; The Keymap Editor (same day) is the C64 client's own keymap_menu.asm,
; built in (keymap_host_128.asm hosts it, keymap_128.asm holds the table
; and dispatch); F7 opens it in either mode. It saves to its own
; TADA128.CFG (the C64 client's is TADA64.CFG). See
; 128_CLIENT_MECHANICS.md's Keymap Editor section, and
; MMU_CLIENT_CONFIG below for why the program may now extend past
; $4000.
;
; SwiftLink (also 2026-09-29): the C64 client's own swiftlink.asm, built
; with {def: c128} for the 128 KERNAL's different NMI entry/exit (see
; its nmi_handler comment). At boot the client waits for the server's
; first byte -- or RUN/STOP, which goes offline into the local demo
; (the old echo loop, "fill" and "clock" test commands, the Keymap
; Editor) -- answers the 40/80-column negotiation menu with whichever
; screen it's on, then runs the line editor with an idle hook
; (editor_idle_hook) that shows server text as it arrives, even mid-
; line. recv_byte parses the server's framed streams (STREAM_START +
; confirm + 16-bit length + body): the Hourglass clock and the login-
; time color/blink apply are handled, Video Settings opens this
; client's own popup (video_menu_128.asm, 2026-10-05), the other popup
; streams (Help, the canvas editor) and SID music are skipped, with a
; cancel reply where the server waits for one. So the "Still no
; SwiftLink" below is history now.
;
; Verified against Compute's 128 Programmer's Guide (pdftotext -layout;
; see 128_CLIENT_MECHANICS.md's own citation note about why a naive
; extract of this book's tables can't be trusted) rather than guessed:
;   - Native-mode BASIC program text starts at $1C01 (7169), not the
;     C64's $0801 -- different memory map, so the BASIC-stub loader
;     bytes below are recomputed for this load address, not copied from
;     tada-client.asm's C64 stub.
;   - $D505 (54533 decimal), the MMU mode configuration register: bit 7
;     reads the 40/80-column switch (1 = up = 40 columns/VIC-II, 0 =
;     down = 80 columns/VDC). "Read and acted upon only at power on or
;     reset" -- not a live togglable interrupt source (that's RESTORE,
;     a completely separate key wired to CIA 2's NMI line), so this is
;     safe to read exactly once at startup with no interrupt-handler
;     interaction to worry about.
;   - ESC-T sets a window's top-left corner, ESC-B its bottom-right --
;     both "at current cursor position" (a prior PLOT positions the
;     cursor, then the escape locks that corner in), same underlying
;     mechanism as the BASIC-level `WINDOW x1,y1,x2,y2[,clear]`
;     statement ($FE $1A, "Not available in BASIC 2.0" -- 128-only).
;   - Critically, PLOT's own KERNAL doc says: "the position is relative
;     to the current window, not the screen" once a window is active,
;     and errors ("Position outside window if carry set") if asked to
;     move outside it. That means the status/input rows below the
;     dialogue window can't be reached via ordinary PLOT/CHROUT once the
;     window is set up -- they need raw SCREEN_RAM pokes instead, same
;     as tada-client.asm's own redraw_status_row already does for the
;     C64's STATUS_ROW (bypassing CHROUT/PLOT there for exactly this
;     kind of reason, if for a different underlying cause).

; Build revision tracker, same as tada-client.asm's (Ryan's ask,
; 2026-10-01): c64list stamps the number in client-128.buildrev into
; __BuildRev and writes it back incremented after every error-free
; assemble -- this client's own counter, separate from the C64 client's.
; Digits only in the file, no newline. Shown via build_rev.asm's
; build_msg (see show_build_msg).
{buildrev:client-128.buildrev}

; MMU mode configuration register -- bit 7 is the 40/80 switch.
{const: MMU_MODE_CONFIG $d505}
{const: SWITCH_40_COL_MASK $80}

; Editor zero page: bit 7 set = the editor is driving the 80-column
; (VDC) screen. See start's comment on why this, not the switch.
{const: EDITOR_MODE_80 $d7}

; Widest screen (VDC) -- sizes inputbuf and status_line; scr_cols holds
; the live width (40 or 80).
{const: MAX_COLS 80}

; MMU configuration for the whole run: bank 0 RAM at $4000-$bfff (BASIC
; ROM out), I/O and the KERNAL in -- Compute's 128 Programmer's Guide
; figure 7-5. The Keymap Editor (keymap_menu.asm, built in) pushes the
; program past $4000, and the scrollback history lives in $6800-$bfbf.
; Checked against the ROMs 2026-09-29 before relying on it: the editor
; ($C000-$CFFF) never writes $FF00, and the KERNAL only does so in
; save/restore pairs (INDFET/INDSTA for LOAD/SAVE, DMA, the IRQ/NMI/BRK
; stubs) or in JSRFAR/JMPFAR, which this client never calls. The one
; catch: the KERNAL IRQ runs irq_handler with $FF00 = $00, so everything
; an interrupt reaches must stay below $4000 -- see check_128_layout.py.
{const: MMU_CONFIG_REG    $ff00}
{const: MMU_CLIENT_CONFIG $0e}

; KERNAL
{const: KERNAL_CHROUT $ffd2}
{const: KERNAL_PLOT   $fff0}
{const: KERNAL_GETIN  $ffe4}

; VIC-II text screen -- same default location and 25x40 layout as the
; C64 (native 128 mode's 40-column path uses the same VIC-II chip).
; SCREEN_RAM itself is one of macro_preprocessor.py's own built-in
; {const:}s (already $0400 -- redefining it errors "Cannot redefine
; built-in constant"), so only ROW_BYTES needs declaring here.
{const: ROW_BYTES   40}

; Screen row layout -- mirrors tada-client.asm's STATUS_ROW (23) /
; PROMPT_ROW (24) exactly, so a player switching between the C64 and
; C128 clients sees the same layout. WIN_TOP/WIN_BOTTOM bound the
; scrolling dialogue window (rows 0-22); STATUS_ROW/INPUT_ROW sit below
; it, reached only via raw SCREEN_RAM pokes (see header comment).
{const: WIN_TOP      0}
{const: WIN_BOTTOM   22}
{const: STATUS_ROW    23}
{const: INPUT_ROW     24}
{const: STATUS_ROW_OFFSET 920}   ; STATUS_ROW * ROW_BYTES
{const: INPUT_ROW_OFFSET  960}   ; INPUT_ROW * ROW_BYTES

; Reverse-video bit -- same convention as tada-client.asm's status row
; (a screen code with bit 7 set displays reverse video on this charset,
; same as the C64's).
{const: REVERSE_BIT $80}

; swiftlink.asm's 128 variant of nmi_handler (and anything else that
; ever needs to tell the two clients apart). Defined here in the source,
; not only by the Makefile's -def:c128, so the NMI handler can't quietly
; come out as the C64 one if that command-line flag ever goes away
; (c64list rejects a second definition, hence the ifndef).
{ifndef: c128}
{def: c128}
{endif}

; KERNAL editor zero page (native 128 mode -- Compute's 128 Programmer's
; Guide's zero-page map, not the C64's addresses): COLOR is the current
; character color CHROUT uses, QTSW the quote-mode flag (input_editor.
; asm's quomod sets/clears the same byte).
{const: KERNAL_COLOR $f1}
{const: KERNAL_QTSW  $f4}

; Framed server streams -- see tada-client.asm's SID_STREAM_START/
; *_STREAM_CONFIRM block for the protocol and why the confirm bytes sit
; in $02-$0f; commands/c64_display.py and sid_engine/frames.py are the
; server side. Plain `=` because recv_byte's tables need them as data.
STREAM_START           = $01
SID_STREAM_CONFIRM     = $02
SID_STOP               = $03      ; one byte, not a stream
CANVAS_STREAM_CONFIRM  = $04
DISPLAY_STREAM_CONFIRM = $06
APPLY_STREAM_CONFIRM   = $07
HELP_STREAM_CONFIRM    = $08
CLOCK_STREAM_CONFIRM   = $0b
CANVAS_STREAM_CANCEL   = $43      ; client -> server replies, see
DISPLAY_STREAM_CANCEL  = $58      ; frame_finish

; swiftlink.asm's flow-control thresholds (rx_buf bytes buffered): RTS
; off at RX_HIGH_WATER, back on below RX_LOW_WATER -- tada-client.asm's
; values.
RX_HIGH_WATER = 200
RX_LOW_WATER  = 32

; drain_rx's settle countdown, high byte (~30 cycles a poll at 1 MHz):
; $20 is tada-client.asm's wait_for_data margin (~0.25 s), for the
; negotiation menu, which arrives in several writes; $04 (~30 ms) is
; enough to batch a burst from inside the line editor.
DRAIN_SETTLE_MENU = $20
DRAIN_SETTLE_IDLE = $04

        orig $1c01

; BASIC stub: 10 SYS7181 (native-128-mode load address is $1c01, not the
; C64's $0801 -- see header comment -- so this next-line-pointer/target
; pair is recomputed for that, not the C64 client's stub bytes).
        byte $0d,$1c,$0a,$00,$9e,$37,$31,$38,$31,$00,$00,$00

start:
        ; Select the lowercase/uppercase charset (CHR$(14)), same as
        ; tada-client.asm -- the server encodes Commodore text with
        ; petscii_c64en_lc, so e.g. the Hourglass clock's "PM" arrives
        ; as shifted $d0/$cd and only reads as letters in this charset.
        ; This used to force uppercase/graphics (CHR$(142), 2026-08-24,
        ; on the belief that status_msg/demo_msg/echo_prefix were
        ; encoded for it). Rendering x128's screen RAM through the real
        ; chargen ROM on 2026-09-29 showed otherwise: status_msg's
        ; {alpha:pokealt} codes ("C" = $43, "o" = $0f) are lowercase-
        ; charset codes, so under CHR$(142) "TADA" and "Commodore"'s "C"
        ; were drawing as graphics glyphs.
        lda #14
        jsr KERNAL_CHROUT
        ; ...and keep it: CHR$(11) disables SHIFT+C= charset switching
        ; (sets LOCKS $f7 = 128), the same lock tada-client.asm sets on
        ; the C64. 128 mode's own codes per Compute's 128 Programmer's
        ; Guide CHR$ table -- 11 disable / 12 enable; the C64's 8/9 are
        ; 64-mode only (9 is TAB here).
        lda #11
        jsr KERNAL_CHROUT

        lda #MMU_CLIENT_CONFIG
        sta MMU_CONFIG_REG
        jsr km_init_keyboard      ; F-keys -> single codes, CTRL+CRSR fix
        jsr init_keymap           ; TADA128.CFG, or the defaults -- disk I/O,
                                  ; so before SwiftLink starts raising NMIs
        jsr init_nmi              ; install our receive handler before the
        jsr init_swiftlink        ; ACIA is told to start raising NMIs on it

        ; Which screen is the editor actually driving? $D7 bit 7 (set =
        ; 80 columns) rather than the $D505 switch bit: the switch is only
        ; read at reset, and ESC-X can swap screens afterwards -- $D7 is
        ; what CHROUT/PLOT (input_editor.asm) will really draw on, and
        ; it's the flag the editor's own VDC code tests ($C161, $C6E7).
        bit EDITOR_MODE_80
        bmi eighty_col_mode
        jmp forty_col_mode

; --- 80 columns: our own VDC dialogue output (vdc_screen.asm) with block-
; copy scrolling and a scrollback history; no ESC-T/ESC-B window at all,
; since dialogue output never goes through CHROUT here. ---
eighty_col_mode:
        lda #0
        sta screen_mode          ; 0 = VDC/80-column
        lda #MAX_COLS
        sta scr_cols
        jsr init_irq
        jsr vdc_screen_init
        jmp connect

forty_col_mode:
        lda #1
        sta screen_mode          ; 1 = VIC-II/40-column

        jsr init_irq              ; install the IRQ dispatcher (just the
                                   ; blink-cursor task so far) before
                                   ; anything else touches the screen
        jsr vic_screen_init       ; history in VDC RAM, sized by
                                  ; vdc_detect_ram (vic_screen.asm)
        jsr init_window
        ; ...and fall into connect: dialogue output goes straight to
        ; vic_putc from here on, same as 80 columns' dlg_putc.

; --- connect: "Connecting..." on the status row until the server's
; first byte arrives (answer the negotiation menu, then the line editor
; takes over) or RUN/STOP gives up (go_offline). Nothing goes into the
; dialogue window while waiting, so the offline demo starts on a clean
; screen. ---
connect:
        lda #<status_msg_connecting
        ldy #>status_msg_connecting
        jsr set_status_msg
        jsr wait_for_connect
        bcs go_offline
        lda #<status_msg
        ldy #>status_msg
        jsr set_status_msg
        jsr show_build_msg
        jsr out_scroll_hint       ; which keys scroll back, ahead of the
        jsr negotiate             ; server's first text
        jsr out_end
        jmp main_loop

; --- go_offline: RUN/STOP at connect. The offline flag keeps main_loop
; on the local demo (echo, "fill", "clock") and send_line off the ACIA;
; the Keymap Editor works the same either way. ---
go_offline:
        lda #1
        sta offline
        lda #<status_msg_offline
        ldy #>status_msg_offline
        jsr set_status_msg
        jsr show_build_msg
        lda screen_mode
        bne go_offline_40
        lda #<eighty_msg
        ldy #>eighty_msg
        jsr out_string
        jmp go_offline_banner
go_offline_40:
        ; Demo: a few lines of filler dialogue text, and what
        ; vdc_detect_ram found -- how many rows of scrollback 40 columns
        ; get out of the VDC's RAM.
        lda #<demo_msg
        ldy #>demo_msg
        jsr out_string
        jsr vic_ram_msg_out
go_offline_banner:
        jsr out_scroll_hint
        lda #<eighty_msg_tail
        ldy #>eighty_msg_tail
        jsr out_string
        jsr out_end
        jmp main_loop

; --- out_scroll_hint: the scrollback keys into the dialogue
; -- "CRSR up/down: scroll back a line. Alt+Grey Up/Alt+Grey Down: a
; page." with the defaults. ---
out_scroll_hint:
        lda #<scroll_hint_msg
        ldy #>scroll_hint_msg
        jsr out_string
        jsr out_page_keys
        lda #<scroll_hint_end
        ldy #>scroll_hint_end
        jmp out_string

; --- out_page_keys: "<Page Up combo>/<Page Down combo>" into the
; dialogue, named by the Keymap Editor's own describe_combo, so the
; names match its list. The page slots (keymap_128.asm's
; KM_PAGE_SLOT_OFFSET) hold a matrix key number, turned into a name
; code by key_num_unshifted -- the same steps as the popup's
; describe_binding_row macro path, through its list_trigger_mod/_key
; scratch record. An unbound slot shows as "none". Borrows scr_ptr_lo/
; hi ($fb/$fc, the editor's strptr -- call_sliding_input resets that
; before every line). ---
out_page_keys:
        lda keymap_table+KM_PAGE_SLOT_OFFSET
        ldx keymap_table+KM_PAGE_SLOT_OFFSET+1
        jsr out_page_key
        lda #'/'
        jsr out_char
        lda keymap_table+KM_PAGE_SLOT_OFFSET+BINDING_SIZE
        ldx keymap_table+KM_PAGE_SLOT_OFFSET+BINDING_SIZE+1
; .A = modifier bits, .X = matrix key number.
out_page_key:
        sta list_trigger_mod
        cpx #KM_KEY_NONE
        bcs out_page_key_none
        txa
        ora list_trigger_mod
        beq out_page_key_none     ; mod = key = 0: nothing captured
        lda key_num_unshifted,x
        sta list_trigger_key
        lda #<list_trigger_mod
        sta scr_ptr_lo
        lda #>list_trigger_mod
        sta scr_ptr_hi
        jsr describe_combo        ; screen codes at row_scratch+15, length
        ldx #0                    ; describe_combo_col
out_page_key_loop:
        cpx describe_combo_col
        beq out_page_key_rts
        lda row_scratch+15,x
        jsr screen_to_petscii
        jsr out_char
        inx
        jmp out_page_key_loop
out_page_key_none:
        lda #<page_key_none_msg
        ldy #>page_key_none_msg
        jmp out_string
out_page_key_rts:
        rts

; .A = a screen code (lowercase charset) -> the PETSCII that prints it;
; the reverse bit is dropped. Inverse of petscii_to_screen. ---
screen_to_petscii:
        and #$7f
        cmp #$20
        bcc s2p_add40             ; $00-$1f -> $40-$5f
        cmp #$40
        bcc s2p_rts               ; $20-$3f unchanged
        cmp #$60
        bcc s2p_add80             ; $40-$5f -> $c0-$df
        clc                       ; $60-$7f -> $a0-$bf
s2p_add40:
        adc #$40                  ; carry clear on every path here
s2p_rts:
        rts
s2p_add80:
        ora #$80
        rts

{alpha:alt}
page_key_none_msg:
        ascii "none"
        byte 0
{alpha:normal}

; --- wait_for_connect: carry clear = the server's first byte is in
; rx_buf (left there for negotiate), carry set = RUN/STOP. Keys other
; than RUN/STOP are thrown away -- nothing typed before the server is
; there means anything. ---
wait_for_connect:
        lda rx_tail
        cmp rx_head
        bne wait_for_connect_data
        jsr KERNAL_GETIN
        cmp #$03                  ; RUN/STOP
        bne wait_for_connect
        sec
        rts
wait_for_connect_data:
        clc
        rts

; --- negotiate: show the server's 40/80-column menu until it goes
; quiet, then answer it with the screen we're on -- "4" for the VIC-II,
; "8" for the VDC (simple_server.py's _negotiate_terminal). Same
; settle-then-answer approach as tada-client.asm's start_connected. ---
negotiate:
        lda #DRAIN_SETTLE_MENU
        jsr drain_rx
        bcs negotiate             ; hit the byte cap, not quiet yet
        lda #'8'
        ldx screen_mode
        beq negotiate_send
        lda #'4'
negotiate_send:
        pha
        jsr sl_send
        lda #13
        jsr sl_send
        pla                       ; ...and show it after the menu's prompt,
        jsr out_char              ; so the history reads "[4/8] > 8"
        lda #13
        jsr out_char
        jmp line_cap_reset

; --- Main loop: read a line from the input row, echo it into the
; scrolling dialogue window. No server connection yet -- this just
; proves the three-region layout (scrolling window / static status row
; / static input row) works together before SwiftLink gets wired in.
;
; The line editor itself is sliding-input.asm's ported insert/delete/
; cursor-movement/word-jump core (input_editor.asm) -- its drwstr
; redraw goes through PLOT, which is window-relative once ESC-T/ESC-B
; is active (see this file's header comment), and INPUT_ROW (24) sits
; below the normal WIN_BOTTOM=22 dialogue window. So the window is
; widened to the full screen for the duration of the call and narrowed
; back after -- narrowing does NOT re-clear (see set_window_narrow),
; since that would wipe the scrolled dialogue history on every line. ---
;
; In 80 columns there's no window to widen: the editor's window is the
; whole screen and dialogue output bypasses CHROUT (vdc_screen.asm).
; Since 2026-10-01 that's true in 40 columns as well (vic_screen.asm):
; the window stays the whole screen and nothing is narrowed any more.
;
; With SwiftLink the widen/narrow pair became out_end/out_begin, which
; also keep the dialogue's own cursor and color apart from the input
; row's (see out_begin) -- server text now arrives in the middle of
; editing too (editor_idle_hook), not just between lines. The editor
; runs in out_end's state; each finished line is handled in out_begin's.
; Online, the line is echoed after whatever the dialogue cursor follows
; (normally the server's prompt, so the history reads "login > name")
; and sent; offline, it goes to the local demo commands.
main_loop:
        tsx                       ; JT_RESUME_LOCAL (the Keymap Editor
        stx main_loop_sp          ; closing) comes back to this depth
        lda screen_mode
        beq main_loop_edit
        jsr set_window_full       ; already full except straight after the
                                  ; Keymap Editor -- kept for that path
main_loop_edit:
        jsr call_sliding_input
        jsr out_begin
        lda offline
        bne main_loop_offline
        jsr echo_prompt           ; the relocated prompt, if any (see
        jsr echo_input            ; relocate_prompt), then the line
        jsr send_line
        lda #0
        sta prompt_len            ; the next line starts without one --
        sta prompt_cols           ; the server sends a fresh prompt
        jsr line_cap_reset        ; the echo ended the dialogue line
        jmp main_loop_next
main_loop_offline:
        jsr clock_test_command    ; "clock <text>" sets the status-row
        bcs main_loop_next        ; clock locally -- see its own comment
        jsr fill_test_command     ; "fill" prints FILL_TEST_LINES lines
        bcs main_loop_next        ; to scroll back through
        lda #<echo_prefix
        ldy #>echo_prefix
        jsr out_string
        jsr echo_input
main_loop_next:
        jsr out_end
        jmp main_loop

; --- echo_input: inputbuf, then CR, into the dialogue. ---
echo_input:
        ldx #0
echo_input_loop:
        lda inputbuf,x
        beq echo_input_done
        jsr out_char
        inx
        jmp echo_input_loop
echo_input_done:
        lda #13
        jmp out_char

; --- send_line: inputbuf over SwiftLink, CR-terminated (the server
; reads up to a bare CR -- see tada-client.asm's send_line). Bytes go as
; typed, Shift+Space's $a0 included, same as the C64 client. ---
send_line:
        ldx #0
send_line_loop:
        lda inputbuf,x
        beq send_line_term
        jsr sl_send
        inx
        jmp send_line_loop
send_line_term:
        lda #13
        jmp sl_send

; --- out_string: .A/.Y = a null-terminated string (any length) for the
; dialogue, through out_char. ---
out_string:
        sta out_string_read+1
        sty out_string_read+2
out_string_read:
        lda $ffff                 ; self-modified
        beq out_string_rts
        jsr out_char
        inc out_string_read+1
        bne out_string_read
        inc out_string_read+2
        jmp out_string_read
out_string_rts:
        rts

; --- out_begin / out_end: bracket dialogue output. Both are no-ops on
; both screens now -- dlg_putc (80 columns) and vic_putc (40, since
; 2026-10-01) keep their own cursor and color and never go near the
; editor's, so the input row's cursor and KERNAL_COLOR are left alone.
; They used to narrow the 40-column ESC-T/ESC-B window to rows 0-22,
; move the KERNAL cursor to the dialogue and swap its color in, then
; widen the window again afterwards -- that went when 40-column
; dialogue stopped going through CHROUT (vic_screen.asm), and the
; brackets stay as the place to hang anything output needs again. ---
out_begin:
        rts

out_end:
        rts

; --- editor_idle_hook: called by input_editor.asm's key-poll loops
; while no key is waiting. Carry clear = nothing happened; carry set =
; dialogue output happened, so the editor redraws the input line and
; cursor.
; While the view is scrolled back, received bytes stay in rx_buf --
; dlg_putc/vic_putc would snap the view back to live mid-read -- and
; swiftlink.asm's RTS flow control holds the server off once it fills;
; they show as soon as the player leaves scrollback. ---
editor_idle_hook:
        lda rx_tail
        cmp rx_head
        beq editor_idle_none
        jsr sb_any_offset
        bne editor_idle_none
        jsr out_begin
        lda #DRAIN_SETTLE_IDLE
        jsr drain_rx
        bcs editor_idle_end       ; capped mid-burst: more is coming
        jsr relocate_prompt
        bcc editor_idle_end
        inc prompt_moved
editor_idle_end:
        jsr out_end
        lda prompt_moved          ; drawn after out_end, on the input
        beq editor_idle_drew      ; row
        lda #0
        sta prompt_moved
        jsr show_prompt
editor_idle_drew:
        sec
        rts
editor_idle_none:
        clc
        rts

; --- drain_rx: hand received bytes to recv_byte until none arrives for
; a settle countdown (.A = its high byte, see DRAIN_SETTLE_MENU), or 256
; bytes have gone by. Carry clear = went quiet, carry set = hit the byte
; cap (callers that need quiet, like negotiate, call again). The cap
; keeps a long burst from starving the keyboard. Same X:Y countdown as
; tada-client.asm's wait_for_data -- sl_recv only touches X when it
; returns a byte, and the countdown restarts then anyway. ---
drain_rx:
        sta drain_settle_hi
        lda #0
        sta drain_count
drain_rx_restart:
        ldx drain_settle_hi
        ldy #0
drain_rx_poll:
        jsr sl_recv
        bcs drain_rx_got
        dey
        bne drain_rx_poll
        dex
        bne drain_rx_poll
        clc
        rts
drain_rx_got:
        jsr recv_byte
        inc drain_count
        bne drain_rx_restart
        sec
        rts

drain_settle_hi:
        byte 0
drain_count:
        byte 0

; --- recv_byte: .A = one byte from the server. rx_state:
;   0  text -- STREAM_START starts a possible frame, SID_STOP and $8e
;      (uppercase/graphics charset, which would undo start's CHR$(14))
;      are dropped, anything else goes to out_char
;   1  saw STREAM_START: a known confirm byte starts a frame, anything
;      else was ordinary text after all (tada-client.asm's SID_STREAM_
;      CONFIRM comment: a lone $01 is never trusted)
;   2  frame length, low byte
;   3  frame length, high byte -- frame_begin, or frame_finish if 0
;   4  body bytes to frame_byte, counting frame_len down to frame_finish
; Every frame has the same header (commands/c64_display.py, sid_engine/
; frames.py), so the ones this client can't use yet are skipped by
; length rather than needing a parser each. ---
recv_byte:
        ldx rx_state
        bne recv_framed
recv_text:
        cmp #STREAM_START
        beq recv_start
        cmp #SID_STOP
        beq recv_rts
        cmp #$8e
        beq recv_rts
        jsr line_capture
        jmp out_char
recv_start:
        lda #1
        sta rx_state
recv_rts:
        rts

recv_framed:
        cpx #1
        bne recv_not_confirm
        ldx #FRAME_CONFIRMS_LEN-1
recv_confirm_scan:
        cmp frame_confirms,x
        beq recv_confirmed
        dex
        bpl recv_confirm_scan
        ldx #0                    ; not a frame: back to text, and this
        stx rx_state              ; byte is text too (it may itself be
        jmp recv_text             ; another STREAM_START)
recv_confirmed:
        sta frame_type
        lda #2
        sta rx_state
        rts
recv_not_confirm:
        cpx #2
        bne recv_not_len_lo
        sta frame_len
        lda #3
        sta rx_state
        rts
recv_not_len_lo:
        cpx #3
        bne recv_body
        sta frame_len+1
        lda #4
        sta rx_state
        jsr frame_begin
        lda frame_len
        ora frame_len+1
        bne recv_rts
        jmp frame_finish          ; empty body (e.g. a clock hide)
recv_body:
        jsr frame_byte
        lda frame_len             ; 16-bit decrement
        bne recv_body_lo
        dec frame_len+1
recv_body_lo:
        dec frame_len
        lda frame_len
        ora frame_len+1
        bne recv_rts
        jmp frame_finish

frame_begin:
        lda #0
        sta apply_idx
        lda frame_type
        cmp #CLOCK_STREAM_CONFIRM
        bne frame_begin_rts
        jmp clock_reset
frame_begin_rts:
        rts

; .A = one body byte. Clock: to clock_putc. Apply: the first three bytes
; (border, background, blink speed) into apply_buf. Video Settings: the
; first VS_BODY_MAX into video_menu_128.asm's vs_body, apply_idx
; counting them. Anything else: dropped.
frame_byte:
        ldx frame_type
        cpx #CLOCK_STREAM_CONFIRM
        bne frame_byte_not_clock
        jmp clock_putc
frame_byte_not_clock:
        cpx #DISPLAY_STREAM_CONFIRM
        bne frame_byte_not_display
        ldx apply_idx
        cpx #VS_BODY_MAX
        bcs frame_byte_rts
        sta vs_body,x
        inc apply_idx
        rts
frame_byte_not_display:
        cpx #APPLY_STREAM_CONFIRM
        bne frame_byte_rts
        ldx apply_idx
        cpx #3
        bcs frame_byte_rts
        sta apply_buf,x
        inc apply_idx
frame_byte_rts:
        rts

; The whole frame is in. Video Settings opens video_menu_128.asm's popup
; (vs_open never returns -- it leaves through JT_RESUME, like the Keymap
; Editor) if the body has at least border, background and blink speed;
; a shorter one gets a cancel. The canvas editor leaves the server
; waiting for the popup's reply too (petscii_editor/canvas.py's cancel is
; STREAM_START+STREAM_CANCEL+00+00), so it gets a cancel -- and, with
; Help, a note in the dialogue, since this client has neither popup yet.
; SID music is skipped silently: the server's own status text already
; says what's playing.
frame_finish:
        lda #0
        sta rx_state
        lda frame_type
        cmp #CLOCK_STREAM_CONFIRM
        bne frame_finish_not_clock
        jmp clock_commit
frame_finish_not_clock:
        cmp #APPLY_STREAM_CONFIRM
        bne frame_finish_not_apply
        jmp apply_settings
frame_finish_not_apply:
        cmp #DISPLAY_STREAM_CONFIRM
        bne frame_finish_not_display
        lda apply_idx
        cmp #3
        bcc frame_finish_display_short
        jmp vs_open
frame_finish_display_short:
        lda #DISPLAY_STREAM_CANCEL
        jsr send_stream_cancel
        jmp frame_finish_note
frame_finish_not_display:
        cmp #CANVAS_STREAM_CONFIRM
        bne frame_finish_not_canvas
        lda #CANVAS_STREAM_CANCEL
        jsr send_stream_cancel
        jmp frame_finish_note
frame_finish_not_canvas:
        cmp #HELP_STREAM_CONFIRM
        bne frame_finish_rts
frame_finish_note:
        lda #<no_popup_msg
        ldy #>no_popup_msg
        jmp out_string
frame_finish_rts:
        rts

; .A = the cancel byte: STREAM_START, .A, a zero 16-bit length.
send_stream_cancel:
        pha
        lda #STREAM_START
        jsr sl_send
        pla
        jsr sl_send
        lda #0
        jsr sl_send
        jmp sl_send

; --- apply_settings: the player's saved Video Settings, sent at login
; (commands/connect.py's encode_apply_for_player): border and background
; as VIC-II color numbers, blink speed 1-5. 40 columns: straight into
; the VIC-II. 80 columns: the VDC has no border, and its background
; (R26's low nibble -- the high nibble is the monochrome-mode foreground,
; kept) takes the RGBI color the editor itself shows for that VIC-II
; color (vdc_screen.asm's dlg_vdc_colors). Blink speed indexes the same
; mask table as tada-client.asm's apply_recv_blink; out of range = left
; alone. A background the text would vanish on (video_menu_128.asm's
; vs_bg_clash -- the server keeps one set for both clients, so a color
; picked on a C64 with other text colors can arrive here) is left alone
; too. ---
VDC_R_BACKGROUND = $1a
apply_settings:
        lda apply_idx
        cmp #3
        bcc apply_settings_rts    ; short body -- leave everything alone
        lda screen_mode
        beq apply_settings_vdc
        lda apply_buf
        sta $d020
        lda apply_buf+1
        jsr vs_bg_clash
        bcs apply_settings_blink
        sta $d021
        jmp apply_settings_blink
apply_settings_vdc:
        lda apply_buf+1
        jsr vs_bg_clash
        bcs apply_settings_blink
        ldx #VDC_R_BACKGROUND
        jsr vdc_read_reg
        and #$f0
        sta apply_tmp
        lda apply_buf+1
        and #$0f
        tay
        lda dlg_vdc_colors,y
        ora apply_tmp
        jsr vdc_write_reg
apply_settings_blink:
        ldx apply_buf+2
        dex
        cpx #5
        bcs apply_settings_rts
        lda apply_blink_masks,x
        sta cursor_blink_mask
apply_settings_rts:
        rts

; Must match tada-client.asm's apply_blink_masks / commands/
; c64_display.py's BLINK_SPEED_MASKS.
apply_blink_masks:
        byte $08, $10, $20, $40, $00

frame_confirms:
        byte SID_STREAM_CONFIRM, CANVAS_STREAM_CONFIRM, DISPLAY_STREAM_CONFIRM
        byte APPLY_STREAM_CONFIRM, HELP_STREAM_CONFIRM, CLOCK_STREAM_CONFIRM
FRAME_CONFIRMS_LEN = 6

rx_state:
        byte 0
frame_type:
        byte 0
frame_len:
        word 0
apply_idx:
        byte 0
apply_buf:
        byte 0, 0, 0
apply_tmp:
        byte 0

;
; --- Prompt on the input row -- tada-client.asm's relocate_prompt_to_
; row24/commit_input_line, for this client's editor. The server's prompt
; ("main > ") ends a write with no CR, so it's the partial line the
; dialogue cursor sits after; left there, anything else the server sends
; while the player types would continue on the prompt's line. So once a
; drain from inside the editor settles, a partial line ending in "> "
; (after any trailing color code -- the server appends the command
; color) moves down: relocate_prompt erases it from the dialogue and
; keeps its bytes in prompt_buf, and show_prompt draws it at the start
; of the input row, with the editor's input area (strcol/strwin) starting
; right after it -- the prompt's own color codes leave KERNAL_COLOR at
; the command color for the typed text, as on the C64. On RETURN,
; main_loop echoes prompt + line into the dialogue, so the history still
; reads "main > look". Not during negotiate (the menu's prompt isn't a
; game prompt, same as the C64's prompt_relocate_enabled). The pager's
; "-- More 1/2 ?=help -- > " ends in "> " too, so it moves the same way --
; tada-client.asm's heuristic does the same, and the history still reads
; right ("-- More 1/2 ?=help -- > " followed by whatever was typed).
;
; line_capture keeps the bytes of the dialogue line in progress (since
; the last CR/CLR), for relocate_prompt to test and copy: anything that
; moves the cursor, or a line longer than LINE_CAP_MAX bytes, marks it
; unusable, and a prompt must leave 10 columns to type in. ---
LINE_CAP_MAX = 40

; .A = a text byte about to go to out_char. Preserves .A.
line_capture:
        sta line_cap_byte
        cmp #13
        beq line_capture_reset
        cmp #$93
        beq line_capture_reset
        ldx line_cap_len
        cpx #LINE_CAP_MAX
        bcs line_capture_bad
        sta line_cap_buf,x
        inc line_cap_len
        cmp #$20
        bcc line_capture_ctrl
        cmp #$80
        bcc line_capture_printable
        cmp #$a0
        bcs line_capture_printable
line_capture_ctrl:
        cmp #$12                  ; RVS on/off and the charset code don't
        beq line_capture_rts      ; move the cursor; the 16 color codes
        cmp #$92                  ; neither
        beq line_capture_rts
        cmp #$0e
        beq line_capture_rts
        ldx #15
line_capture_color:
        cmp dlg_color_codes,x
        beq line_capture_rts
        dex
        bpl line_capture_color
line_capture_bad:
        lda #1
        sta line_cap_bad
        bne line_capture_rts      ; always
line_capture_printable:
        inc line_cap_cols
        lda line_cap_last
        sta line_cap_prev
        lda line_cap_byte
        sta line_cap_last
line_capture_rts:
        lda line_cap_byte
        rts
line_capture_reset:
        jsr line_cap_reset
        lda line_cap_byte
        rts

line_cap_reset:
        lda #0
        sta line_cap_len
        sta line_cap_cols
        sta line_cap_bad
        sta line_cap_last
        sta line_cap_prev
        rts

; In out_begin's state. Carry set = the partial line was a prompt: now
; in prompt_buf, and gone from the dialogue (the dialogue cursor back at
; the start of its row).
relocate_prompt:
        lda line_cap_len
        beq relocate_no
        lda line_cap_bad
        bne relocate_no
        lda line_cap_last
        cmp #' '
        bne relocate_no
        lda line_cap_prev
        cmp #'>'
        bne relocate_no
        lda line_cap_cols
        clc
        adc #10
        cmp scr_cols
        bcs relocate_no           ; leave at least 10 columns to type in
        ldx #0
relocate_copy:
        lda line_cap_buf,x
        sta prompt_buf,x
        inx
        cpx line_cap_len
        bne relocate_copy
        stx prompt_len
        lda line_cap_cols
        sta prompt_cols
        jsr line_cap_reset
        jsr dlg_blank_cur_row     ; erase it from the dialogue, cursor back
        sec                       ; at the start of its row
        rts
relocate_no:
        clc
        rts

; In out_end's state (the line editor's). Points the editor's input area
; past the prompt and draws the prompt at the start of the input row;
; with no prompt, the input area is the whole row again. Called by
; call_sliding_input before every line too, so a prompt survives the
; Keymap Editor's JT_RESUME. The view slides if the cursor would now be
; past the narrower area.
show_prompt:
        lda prompt_cols
        sta strcol
        lda scr_cols
        sec
        sbc #1
        sec
        sbc prompt_cols
        sta strwin
        lda cpos
        sec
        sbc lcol
        cmp strwin
        bcc show_prompt_draw
        lda cpos
        sec
        sbc strwin
        clc
        adc #1
        sta lcol
show_prompt_draw:
        lda prompt_len
        beq show_prompt_rts
        clc
        ldx #INPUT_ROW
        ldy #0
        jsr KERNAL_PLOT
        lda #0
        sta show_prompt_idx
show_prompt_loop:
        ldx show_prompt_idx
        lda prompt_buf,x
        jsr KERNAL_CHROUT
        lda #0
        sta KERNAL_QTSW
        inc show_prompt_idx
        lda show_prompt_idx
        cmp prompt_len
        bne show_prompt_loop
show_prompt_rts:
        rts

; The relocated prompt's bytes into the dialogue, ahead of the echoed
; line (out_begin's state).
echo_prompt:
        ldx #0
echo_prompt_loop:
        cpx prompt_len
        beq echo_prompt_rts
        lda prompt_buf,x
        jsr out_char
        inx
        jmp echo_prompt_loop
echo_prompt_rts:
        rts

line_cap_buf:
        area LINE_CAP_MAX, 0
line_cap_len:
        byte 0
line_cap_cols:
        byte 0                    ; printable characters in line_cap_buf
line_cap_bad:
        byte 0                    ; 1 = moved the cursor or overflowed
line_cap_last:
        byte 0                    ; last printable character
line_cap_prev:
        byte 0                    ; ...and the one before it
line_cap_byte:
        byte 0
prompt_buf:
        area LINE_CAP_MAX, 0
prompt_len:
        byte 0                    ; bytes in prompt_buf, 0 = no prompt
prompt_cols:
        byte 0                    ; columns it takes on the input row
prompt_moved:
        byte 0
show_prompt_idx:
        byte 0

; --- set_status_msg: .A/.Y = the status row's message (screen codes,
; null-terminated), redrawn now. ---
set_status_msg:
        sta status_msg_ptr
        sty status_msg_ptr+1
        jmp draw_status_row

; --- show_build_msg: build_rev.asm's "build 42, 2026-Oct-01 13:02:56"
; on the status row as a status_override -- so it holds until the first
; key (editor_key_hook clears it), then status_msg shows again, like the
; C64 client's build message holding until its first real status event.
; Called once connect is over (connected or offline), not before: the
; override would hide "Connecting... RUN/STOP to go offline". ---
show_build_msg:
        jsr strip_build_rev_zeros
        lda #<build_msg
        sta status_override
        lda #>build_msg
        sta status_override+1
        jmp draw_status_row

; --- out_char: .A = PETSCII for the dialogue area, whichever screen.
; 40 columns: vic_putc. 80 columns: dlg_putc. Preserves X (and Y)
; either way -- callers index strings with X. ---
;
; The 40-column path used to CHROUT into an ESC-T/ESC-B window and clear
; quote mode after every character (a lone '"' in server text turned the
; color/cursor codes after it into reverse glyphs). vic_putc has no quote
; mode, so that reset went with it (2026-10-01).
out_char:
        pha
        lda screen_mode
        beq out_char_vdc
        pla
        jmp vic_putc
out_char_vdc:
        pla
        jmp dlg_putc

; --- editor_key_hook: called by input_editor.asm for every key. .A =
; the GETIN byte; carry set = consumed (the editor just redraws), carry
; clear = .A is what the editor should handle (normally the key itself).
;
; Order: any key first clears a status-row override ("Saved keymap."
; etc.). Plain (or SHIFTed) CRSR UP/DOWN scroll the dialogue a line
; (scroll_key_hook -- vdc_key_hook in 80 columns, vic_screen.asm's in 40);
; every other key leaves scrollback. Then the keymap (keymap_128.asm's
; km_dispatch) gets the key -- word jumps, home/end, macros, F7 for the
; editor, and Page Up/Page Down (ALT + the grey arrows by default), which
; is why CRSR with C=, CTRL or ALT held skips the line scroll. So a keymap
; binding on plain CRSR UP/DOWN (the defaults' Home/End) is shadowed by
; scrollback -- in 40 columns too since they got scrollback (2026-10-01);
; before that it worked there as on the C64. ---
editor_key_hook:
        sta editor_hook_key
        lda status_override+1
        beq editor_hook_no_msg
        lda #0
        sta status_override+1
        jsr draw_status_row
editor_hook_no_msg:
        lda editor_hook_key
        cmp #$91
        beq editor_hook_crsr
        cmp #$11
        bne editor_hook_keymap
editor_hook_crsr:
        lda $d3
        and #$0e                  ; C=, CTRL or ALT + CRSR: keymap
        bne editor_hook_keymap    ; territory (SHIFT is CRSR UP itself)
        lda editor_hook_key
        jmp scroll_key_hook
editor_hook_keymap:
        lda editor_hook_key
        jsr km_dispatch
        ; Any key but Page Up/Down leaves scrollback -- after the keymap,
        ; not before, or every Page Up would snap to the live view first
        ; and could never page more than once. Keeps .A and carry.
        php
        pha
        lda km_paged
        bne editor_hook_rts
        jsr sb_exit_any
editor_hook_rts:
        pla
        plp
        rts

editor_hook_key:
        byte 0

done:
        rts

; --- init_window: define the scrolling dialogue region (rows WIN_TOP-
; WIN_BOTTOM) via ESC-T (top-left corner)/ESC-B (bottom-right corner).
; Both escapes act on wherever the cursor currently is -- PLOT it first,
; then send the escape to lock that corner in. Once both corners are
; set, PLOT's own coordinates become window-relative (see this file's
; header comment) -- status_row/input_row below the window are reached
; via raw SCREEN_RAM pokes instead, never through PLOT/CHROUT again
; after this runs. ---
;
; Since 2026-10-01 the window is the whole screen (set_window_full)
; rather than rows WIN_TOP-WIN_BOTTOM: dialogue no longer goes through
; CHROUT at all (vic_screen.asm draws and scrolls it), so the KERNAL
; window only matters to input_editor.asm on the input row -- the
; narrow window, and the set_window_narrow that set it, went.
init_window:
        jsr set_window_full

        ; ESC-T/ESC-B set the window's bounds but do NOT clear its
        ; contents or home the cursor the way the BASIC-level
        ; WINDOW x1,y1,x2,y2[,clear] statement does -- confirmed live in
        ; VICE 2026-08-24: without this, the autostart boot text ("ready.",
        ; "load...", "searching for *", ...) was still sitting in the
        ; window area, and the demo text below started printing from
        ; wherever the cursor happened to be after boot (mid-screen), not
        ; the window's top-left.
        ;
        ; CLR_HOME (147, this project's existing PETSCII_CONTROL_CODES
        ; 'clear' value -- formatting.py) sent TWICE fixes it: the first
        ; press only homes the cursor (Ryan's call, confirmed live) --
        ; clearing a window apparently needs the cursor already at its
        ; home position first -- and the second, now genuinely at home,
        ; performs the real clear. No KERNAL routine found in Compute's
        ; 128 Programmer's Guide for "clear the current window" directly
        ; callable from assembly (only the BASIC WINDOW statement's own
        ; optional clear parameter, which isn't a bare routine call) --
        ; if one turns up later this can shrink to a single JSR.
        lda #147
        jsr KERNAL_CHROUT
        jsr KERNAL_CHROUT
        rts

; --- set_window_full: the ESC-T/ESC-B window over the whole screen,
; rows WIN_TOP-INPUT_ROW, so the editor's PLOT-based redraw can reach the
; input row. Used at boot (init_window, which also clears) and before
; each input_editor.asm call (main_loop -- the Keymap Editor can leave
; the window changed). Its bottom edge is set by poking the cursor
; position rather than PLOTting there; the comment inside says why.
; (The narrow-window helper that comment compares against,
; set_window_narrow, was removed 2026-10-01 along with the narrow
; window.) ---
set_window_full:
        clc
        ldx #WIN_TOP
        ldy #0
        jsr KERNAL_PLOT           ; row 0 is always in-bounds for any
                                   ; window, safe regardless of what's
                                   ; currently active
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'T'
        jsr KERNAL_CHROUT

        ; Can't PLOT to INPUT_ROW here the way set_window_narrow does --
        ; confirmed live 2026-08-24 (debug_plot_carry/_x/_y instrumentation,
        ; since removed): the OLD (narrow, WIN_TOP-WIN_BOTTOM) window is
        ; still the active constraint until ESC-B completes, since ESC-T
        ; alone doesn't redefine the window -- so a PLOT trying to move
        ; to INPUT_ROW (below WIN_BOTTOM) gets rejected outright (carry
        ; set, X/Y left unchanged at the requested-but-refused position,
        ; cursor doesn't actually move). This is the actual root cause
        ; of the "can't type anything" bug Ryan hit live: drwstr's own
        ; later PLOT(INPUT_ROW,...) calls were failing the exact same
        ; way, so the whole line editor was drawing wherever the cursor
        ; was stuck instead of the input row -- GETIN/putchr were
        ; working correctly the entire time (confirmed via inputbuf
        ; contents), only the on-screen feedback was broken.
        ;
        ; Fix: poke the KERNAL's own cursor-position zero page directly
        ; instead of calling PLOT, bypassing its boundary check -- ESC-B
        ; defines the window's bottom-right corner at wherever the
        ; cursor position claims to be, not specifically wherever the
        ; immediately-preceding PLOT call put it. $EB (row) / $EC (col)
        ; are the correct addresses for this on native 128 mode --
        ; confirmed via Compute's 128 Programmer's Guide's own zero-page
        ; map ("235 $EB Current cursor line", "236 $EC Current cursor
        ; column"), NOT the C64's $D6/$D3 (a real difference this file
        ; almost inherited by assumption the way tada-client.asm's own
        ; conventions were carried over elsewhere in this port).
        lda #INPUT_ROW
        sta $eb
        lda #39
        sta $ec
        lda #27                  ; ESC
        jsr KERNAL_CHROUT
        lda #'B'
        jsr KERNAL_CHROUT
        rts

; --- draw_status_row: raw SCREEN_RAM pokes, reverse video, same
; convention as tada-client.asm's redraw_status_row (bit 7 set on a
; screen code displays reverse video on this charset). Static
; placeholder message for now -- no status queue/rotation yet, that's
; tada-client.asm's status_queue machinery, not ported here yet.
; The Hourglass clock (clock_len bytes of clock_buf, 0 = none) owns the
; row's right end, same as tada-client.asm's redraw_status_row_to: the
; message stops one column short of it (a gap), so with no clock the
; message is capped at 39 columns.
;
; Both screens share this: the row is built in status_line (scr_cols
; wide) and then copied to SCREEN_RAM (40 columns) or VDC row 23 (80,
; vdc_draw_status_line). While scrolled back (80 columns only), the
; scrollback position message replaces status_msg. ---
draw_status_row:
        ldx #0
        lda #(' ' | REVERSE_BIT)
draw_status_blank_loop:
        sta status_line,x
        inx
        cpx scr_cols
        bne draw_status_blank_loop

        jsr sb_any_offset         ; scrolled back, either screen
        beq draw_status_not_sb
        jsr sb_status_any
        jmp draw_status_have_msg
draw_status_not_sb:
        lda status_override       ; a one-off message (the Keymap Editor's
        ldy status_override+1     ; "Saved keymap.") until the next key
        bne draw_status_have_msg
        lda status_msg_ptr        ; connecting / connected / offline --
        ldy status_msg_ptr+1      ; see set_status_msg
draw_status_have_msg:
        sta draw_status_read+1
        sty draw_status_read+2
        lda scr_cols
        sec
        sbc #1
        sec
        sbc clock_len
        sta draw_status_limit
        ldx #0
draw_status_msg_loop:
        cpx draw_status_limit
        bcs draw_status_key_tag
draw_status_read:
        lda $ffff,x               ; self-modified: status_msg or sb_status_buf
        beq draw_status_key_tag
        ora #REVERSE_BIT
        sta status_line,x
        inx
        jmp draw_status_msg_loop
; "[key]" at the message area's right end while a status_override is up
; (Ryan's ask, 2026-10-01) -- the next key clears every override (see
; editor_key_hook), so this tells the player to press one. Only if a
; blank column is left between it and the message (.X = the column just
; past the message); otherwise the message wins and there's no tag.
; Never over the scrollback position message.
draw_status_key_tag:
        lda sb_offset
        bne draw_status_clock
        lda status_override+1
        beq draw_status_clock
        lda draw_status_limit
        sec
        sbc #KEY_TAG_LEN
        bcc draw_status_clock     ; row too short for it at all
        sta draw_status_tag_col
        cpx draw_status_tag_col
        bcs draw_status_clock     ; no gap left -- message reaches it
        tax
        ldy #0
draw_status_key_tag_loop:
        lda key_tag,y
        beq draw_status_clock
        ora #REVERSE_BIT
        sta status_line,x
        inx
        iny
        jmp draw_status_key_tag_loop
draw_status_clock:
        lda scr_cols
        sec
        sbc clock_len
        tax                       ; first clock column
        ldy #0
draw_status_clock_loop:
        cpx scr_cols
        bcs draw_status_blit
        lda clock_buf,y
        ora #REVERSE_BIT
        sta status_line,x
        inx
        iny
        jmp draw_status_clock_loop
draw_status_blit:
        lda screen_mode           ; VIC: 40 columns, or 80 columns with the
        ora km_present_on         ; Keymap Editor open (its status row is
        bne draw_status_vic       ; VIC row 23 then, see keymap_host_128.asm)
        jmp vdc_draw_status_line
draw_status_vic:
        ldx #0
draw_status_vic_loop:
        lda status_line,x
        sta SCREEN_RAM+STATUS_ROW_OFFSET,x
        inx
        cpx #ROW_BYTES
        bne draw_status_vic_loop
        rts

draw_status_limit:
        byte 0
draw_status_tag_col:
        byte 0

; --- Hourglass clock (PlayerFlags.HOURGLASS) -- the display half of
; tada-client.asm's CLOCK_STREAM_CONFIRM ($0b) stream, ported ahead of
; SwiftLink: nothing here receives it from the server yet. Once a
; receive dispatcher exists, its clock-stream handler reads the 16-bit
; length (high byte ignored), calls clock_reset, clock_putc once per
; body byte, then clock_commit -- the same steps as tada-client.asm's
; clock_recv, split up so they don't assume a receive routine that
; doesn't exist here yet. An empty body (clock_reset + clock_commit
; with no putc) hides the clock.
;
; Body bytes are PETSCII, converted to screen codes with the standard
; mapping -- matches the server's petscii_c64en_lc codec now that this
; client runs the lowercase charset (see start's CHR$(14) comment), so
; "PM" (shifted $d0/$cd) shows as capital letters.
CLOCK_MAX = 12                    ; tada-client.asm's CLOCK_MAX / commands/
                                  ; c64_display.py's CLOCK_MAX
clock_reset:
        lda #0
        sta clock_recv_idx
        rts

; .A = one PETSCII body byte. Anything past CLOCK_MAX is dropped, so a
; caller can keep feeding a longer body without losing stream sync.
; Preserves X/Y.
clock_putc:
        stx clock_saved_x
        ldx clock_recv_idx
        cpx #CLOCK_MAX
        bcs clock_putc_rts
        jsr petscii_to_screen
        sta clock_buf,x
        inc clock_recv_idx
clock_putc_rts:
        ldx clock_saved_x
        rts

clock_commit:
        lda clock_recv_idx
        sta clock_len
        jmp draw_status_row       ; tail call

; .A (a printable PETSCII code, $20-$7f or $a0-$ff) -> screen code --
; same mapping as tada-client.asm's so_petscii_to_screen (this client's
; own old petscii_to_screencode went away with input_editor.asm).
petscii_to_screen:
        cmp #$40
        bcc p2s_rts         ; $20-$3f: unchanged
        cmp #$60
        bcc p2s_sub40       ; $40-$5f -> $00-$1f
        cmp #$80
        bcc p2s_sub20       ; $60-$7f -> $40-$5f
        cmp #$c0
        bcc p2s_sub40       ; $a0-$bf -> $60-$7f
        cmp #$ff
        beq p2s_pi
        and #$7f                  ; $c0-$fe -> $40-$7e
p2s_rts:
        rts
p2s_sub40:
        sec
        sbc #$40
        rts
p2s_sub20:
        sec
        sbc #$20
        rts
p2s_pi:
        lda #$5e                  ; $ff is pi, same glyph as $de
        rts

; --- clock_test_command: local stand-in for the server's clock stream
; until SwiftLink is wired in. If inputbuf starts with "clock", feeds
; everything after it (one separating space skipped) through clock_
; reset/putc/commit and returns carry set (main_loop skips the echo);
; a bare "clock" hides the clock. Anything else: carry clear, untouched.
; Delete once a real receive path calls clock_reset/putc/commit.
; (It does now -- frame_begin/frame_byte/frame_finish -- but this stays
; as part of the offline demo, where vice128_clock_test.py drives it.) ---
clock_test_command:
        ldx #0
clock_test_match:
        lda clock_test_word,x
        beq clock_test_matched
        cmp inputbuf,x
        bne clock_test_no
        inx
        jmp clock_test_match
clock_test_matched:
        jsr clock_reset
        lda inputbuf,x
        cmp #' '
        bne clock_test_feed
        inx
clock_test_feed:
        lda inputbuf,x
        beq clock_test_done
        jsr clock_putc
        inx
        jmp clock_test_feed
clock_test_done:
        jsr clock_commit
        sec
        rts
clock_test_no:
        clc
        rts

clock_test_word:
        ascii "clock"
        byte 0

; --- fill_test_command: another local stand-in until SwiftLink lands.
; A bare "fill" prints FILL_TEST_LINES numbered lines through out_char --
; enough to scroll the 80-column history well past one screen. Each line
; switches color twice (yellow text, white number) so scrollback can be
; checked for keeping attributes, not just characters. Carry set =
; handled. Delete along with clock_test_command. (Offline demo only
; now, same as clock_test_command.) ---
FILL_TEST_LINES = 60
fill_test_command:
        ldx #0
fill_test_match:
        lda fill_test_word,x
        beq fill_test_matched
        cmp inputbuf,x
        bne fill_test_no
        inx
        jmp fill_test_match
fill_test_matched:
        lda inputbuf,x
        bne fill_test_no          ; "fill" exactly, nothing after it
        lda #1
        sta fill_test_n
fill_test_line:
        ldx #0
fill_test_text_loop:
        lda fill_test_text,x
        beq fill_test_number
        jsr out_char
        inx
        jmp fill_test_text_loop
fill_test_number:
        lda fill_test_n
        jsr dec3
        ldx #0
fill_test_digit_loop:
        lda dec3_buf,x
        jsr out_char
        inx
        cpx #3
        bne fill_test_digit_loop
        lda #13
        jsr out_char
        inc fill_test_n
        lda fill_test_n
        cmp #FILL_TEST_LINES+1
        bcc fill_test_line
        sec
        rts
fill_test_no:
        clc
        rts

fill_test_word:
        ascii "fill"
        byte 0
fill_test_text:
        byte $9e                  ; yellow
{alpha:alt}
        ascii "Scrollback test line "
{alpha:normal}
        byte $05, 0               ; white for the number
fill_test_n:
        byte 0

; --- dec3: .A (0-255) -> dec3_buf = three ASCII/PETSCII digits, which
; are also their own screen codes ($30-$39). Preserves X and Y. ---
dec3:
        sty dec3_saved_y
        ldy #'0'
dec3_hundreds:
        cmp #100
        bcc dec3_hundreds_done
        sbc #100                  ; carry set from the cmp
        iny
        jmp dec3_hundreds
dec3_hundreds_done:
        sty dec3_buf
        ldy #'0'
dec3_tens:
        cmp #10
        bcc dec3_tens_done
        sbc #10
        iny
        jmp dec3_tens
dec3_tens_done:
        sty dec3_buf+1
        ora #'0'
        sta dec3_buf+2
        ldy dec3_saved_y
        rts

dec3_buf:
        byte 0,0,0
dec3_saved_y:
        byte 0

clock_buf:
        area CLOCK_MAX, 0
clock_len:
        byte 0                    ; 0 = no clock shown (hourglass off)
clock_recv_idx:
        byte 0
clock_saved_x:
        byte 0

; read_input_row/petscii_to_screencode used to live here -- superseded
; 2026-08-24 by input_editor.asm's ported sliding-input.asm core
; (insert/delete/cursor-movement/word-jump, not just append/backspace),
; called from main_loop as call_sliding_input. That routine draws via
; PLOT/CHROUT rather than raw SCREEN_RAM pokes, so it needs the window
; widened first (see main_loop's comment) -- and it handles the Shift+
; Space -> underscore display convention itself now (drwstr substitutes
; $a0 -> $e4 at display time only; see input_editor.asm's header).

; --- IRQ dispatcher: install, round-robin one job per tick ---
; Same shape as tada-client.asm's own init_irq/irq_handler/
; irq_dispatch_next -- ported deliberately for parity across both
; clients, not independently invented. Hooks CINV ($0314/$0315),
; confirmed the same address/purpose on the 128 as the C64 (Compute's
; 128 Programmer's Guide: "CINV vector to IRQ handler routine"). Not
; independently re-verified here: whether the 128's KERNAL IRQ entry
; stub pushes A/X/Y before jumping through CINV the same way the C64's
; $FF48 does (which is what lets irq_handler skip saving registers
; itself, relying on the eventual jmp (irq_orig) to fall through to the
; stock handler's own pla/tax/pla/tay/pla/rti) -- inherited from the
; C64 pattern on the reasonable assumption of shared KERNAL heritage,
; same as this file's other C64-inherited-but-128-plausible assumptions.
; Only one real job exists yet (irq_task_cursor_blink, from
; input_editor.asm) -- no heartbeat placeholder needed since there's no
; ambiguity to prove the dispatch mechanism against.
init_irq:
        sei
        lda $0314
        sta irq_orig+0
        lda $0315
        sta irq_orig+1
        lda #<irq_handler
        sta $0314
        lda #>irq_handler
        sta $0315
        cli
        rts

irq_handler:
        jsr irq_dispatch_next
        lda km_present_on         ; Keymap Editor open in 80 columns: copy
        beq irq_handler_chain     ; its changes to the VDC (see
        jsr km_present_tick       ; keymap_host_128.asm)
irq_handler_chain:
        jmp (irq_orig)

irq_dispatch_next:
        ldy irq_task_ptr
        lda irq_task_table,y
        sta irq_dispatch_jmp+1
        iny
        lda irq_task_table,y
        sta irq_dispatch_jmp+2
        iny
        cpy #IRQ_TASK_TABLE_LEN
        bcc irq_dispatch_next_store
        ldy #0
irq_dispatch_next_store:
        sty irq_task_ptr
irq_dispatch_jmp:
        jmp $ffff

{include:input_editor.asm}
{include:vdc.asm}
{include:vdc_screen.asm}
{include:keymap_host_128.asm}
{include:swiftlink.asm}

irq_orig:
        byte 0,0                 ; saved KERNAL IRQ vector, set by init_irq

; swiftlink.asm's state (tada-client.asm declares the same names; see
; swiftlink.asm's header). The NMI handler reaches all of it, so it stays
; up here, below $4000. rx_head/rx_tail are ordinary memory, not
; tada-client.asm's zero page $f9/$fa -- nothing indexes through them,
; and zero page is the 128 KERNAL's to check first.
nmi_orig:
        byte 0,0                 ; saved KERNAL NMI vector, set by init_nmi
rts_state:
        byte 1                   ; 1 = RTS currently asserted (ready), 0 = deasserted
rx_head:
        byte 0                   ; NMI receive ring buffer: next write index
rx_tail:
        byte 0                   ; NMI receive ring buffer: next read index
rx_buf:
        area 256, 0              ; wraps at 256 with rx_head/rx_tail

irq_task_ptr:
        byte 0                   ; byte offset into irq_task_table, self-modified

irq_task_table:
        word irq_task_cursor_blink
IRQ_TASK_TABLE_LEN = 2           ; entries * 2 -- keep in sync with the table above

; --- Data ---

; screen_mode: 0 = VDC (80-column), 1 = VIC-II (40-column). Set once at
; startup by the $D7 check above; main_loop, out_char, editor_key_hook
; and draw_status_row branch on it. scr_cols is the matching width.
screen_mode:
        byte 0
scr_cols:
        byte ROW_BYTES

forty_msg:
        ascii "40-column mode (vic-ii) detected."
        byte 13, 0

; Printed through out_char (dlg_putc) at 80-column startup. {alpha:alt}
; so capitals come out as real shifted PETSCII ($c1-$da) -- plain ascii
; folds everything to $41-$5a, i.e. lowercase in this charset (confirmed
; reading VDC RAM 2026-09-29: "VDC" showed as "vdc").
{alpha:alt}
eighty_msg:
        ascii "80-column mode (VDC) detected."
        byte 13
        ascii "Dialogue rows 0-22 scroll by VDC block copy; status row 23, input row 24."
        byte 13, 0
; ...then scroll_hint_msg + out_page_keys + scroll_hint_end (go_offline),
; then:
eighty_msg_tail:
        ascii "Type fill for 60 test lines."
        byte 13, 13, 0

; The scrollback keys, also shown on connecting (connect).
; out_page_keys fills in the page keys from the keymap, so a rebinding
; shows up here -- under 80 columns even with two 15-character combos.
scroll_hint_msg:
        ascii "CRSR up/down: scroll back a line. "
        byte 0
scroll_hint_end:
        ascii ": a page."
        byte 13, 0
{alpha:normal}

; Sent through out_char (vic_putc) into the dialogue -- plain PETSCII/
; ASCII text is fine here (not raw screen codes -- unlike status_msg
; below, vic_putc converts it). {alpha:alt} for real capitals, same as
; eighty_msg (plain ascii folds them to lowercase). Followed by
; vic_screen.asm's VDC RAM line, then the scroll hint (go_offline).
{alpha:alt}
demo_msg:
        ascii "40-column mode (vic-ii) detected."
        byte 13
        ascii "Dialogue rows 0-22; scrollback in VDC."
        byte 13
        ascii "Status row: row 23 (below). Input row: row 24."
        byte 13, 0

echo_prefix:
        ascii "You typed: "
        byte 0
{alpha:normal}

; status_msg: raw screen codes via {alpha:pokealt} (see
; sid_streaming.asm's status_lbl_* for the same convention and its own
; comment on why -- draw_status_row pokes this straight into SCREEN_RAM,
; never through CHROUT, so it needs pre-encoded screen codes rather than
; plain PETSCII/ASCII).
{alpha:pokealt}
status_msg:
        ascii "TADA -- Commodore 128 client"
        byte 0
status_msg_offline:
        ascii "TADA -- Commodore 128 client (offline)"
        byte 0
status_msg_connecting:
        ascii "Connecting... RUN/STOP to go offline"
        byte 0
; draw_status_row's "press a key" tag for a status_override message.
; The brackets are raw screen codes: {alpha:pokealt} passes "[" and "]"
; through as ASCII $5b/$5d -- graphics glyphs in screen codes, not
; brackets ($1b/$1d) -- checked in the assembled .prg.
key_tag:
        byte $1b                  ; [
        ascii "key"
        byte $1d, 0               ; ]
KEY_TAG_LEN = 5
{alpha:normal}

; build_msg/strip_build_rev_zeros -- shared with tada-client.asm. Kept up
; here with status_msg, below $4000, since draw_status_row reads it.
{include:build_rev.asm}

; Dialogue note for a server popup this client doesn't have yet (see
; frame_finish). PETSCII for out_string, {alpha:alt} for real capitals.
{alpha:alt}
no_popup_msg:
        ascii "(Popup not on the 128 client yet.)"      ; < 40 columns
        byte 13, 0
{alpha:normal}

; status_msg_ptr: the message draw_status_row shows when nothing
; overrides it -- set_status_msg picks one of the three above.
status_msg_ptr:
        word status_msg_connecting

; offline: 1 once RUN/STOP gave up on connecting (go_offline).
offline:
        byte 0

; inputbuf: input_editor.asm's line buffer, one byte per input-row
; column (scr_cols, up to MAX_COLS=80) plus a null terminator --
; call_sliding_input points strptr at this before every call.
inputbuf:
        area MAX_COLS+1, 0

; status_line: draw_status_row builds the status row here (screen codes,
; scr_cols wide) before copying it to whichever screen is live.
status_line:
        area MAX_COLS, 0

; status_override: a message draw_status_row shows instead of status_msg
; (high byte 0 = none), set by JT_BUILD_STATUS_LINE, cleared by the next
; key editor_key_hook sees.
status_override:
        word 0
main_loop_sp:
        byte 0

; --- Above this line: everything an interrupt can reach, which must stay
; below $4000 (see MMU_CLIENT_CONFIG). Below: the Keymap Editor, which
; runs only in mainline, so it can sit above $4000. keymap_menu.asm is the
; C64 client's own source, built for the 128 by the Makefile's
; keymap_menu_128.asm rule (constants_128.asm instead of constants.asm,
; no overlay `orig`). ---
{include:keymap_menu_128_pp.asm}
{include:keymap_128.asm}
; 40-column dialogue output and its VDC-RAM scrollback -- mainline only,
; so it sits up here too (vdc_detect_ram, which can't, is in vdc.asm)
{include:vic_screen.asm}
; disk.asm: bus scan, drive selection, error channel -- shared with the
; C64 client (see its header)
{include:disk.asm}
; The drive picker (F5): drive_id.asm's M-R model lookup and the popup
; the C64 loads as DRIVE.MNU, built in under c128 (see
; drive_menu_body.asm's header)
{include:drive_id.asm}
{include:drive_menu_body_pp.asm}
; Video Settings (PREFS -> Terminal Settings -> V): this client's own
; popup, VIC-II or VDC settings by screen, plus the VDC hardware cursor
{include:video_menu_128.asm}
