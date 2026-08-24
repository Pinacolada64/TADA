; input_editor.asm -- sliding-input.asm's proven insert/delete/cursor-
; movement/word-jump line editor, ported for client-128.asm.
;
; sliding-input.asm's own BASIC-SYS-parameter front end (sliding_input/
; si_start/param3/setup) is C64 BASIC 2.0 ROM-specific (GET_VAR=$b08b,
; assign_string=$aa2c, strout=$ab1e, REQUIRE_STRING, ALLOC_STRING,
; basic_error, get_expr, SKIP_COMMA, plus BASIC-2.0-only zero page
; VARPNT=$47/FORPNT=$49/fac_strptr=$64) -- none of that exists on the
; 128's native-mode BASIC 7.0 ROM. call_sliding_input below replaces it
; with a direct parameter preload, no BASIC dependency at all. Below
; that point (instr onward) is sliding-input.asm's real, portable core
; editor, copied over unchanged except for two fixes:
;   - the one remaining BASIC ROM call (jsr strout, in clear:'s "are you
;     sure" prompt) is replaced with print_msg, a plain CHROUT loop.
;   - putchr's "shifted space ($a0) becomes a plain space" substitution
;     is removed, and drwstr instead substitutes $a0 -> $e4 (the wire
;     byte that renders as the underline glyph) at DISPLAY time only --
;     this project's convention is Shift+Space -> underscore, not
;     space (see client-128.asm's now-removed petscii_to_screencode,
;     same reasoning), and the stored buffer byte must stay $a0
;     unmodified so a future SwiftLink send still has the real byte.
;
; strptr ($fb/$fc) is confirmed free/unused zero page on the 128 (per
; Compute's 128 Programmer's Guide, "251-254 $FB-$FE Unused"). quomod's
; C128-mode quote-flag byte ($f4) is sliding-input.asm's own pre-
; existing choice, carried over as-is -- not independently re-verified
; here, since quote-mode is a minor corner case (typing a literal ")
; and the file's dual-mode design already anticipated it.

BIT_ZP  = $24   ; bit $xx    (zeropage) skips next 1-byte instruction
BIT_ABS = $2c   ; bit $xxxx  (absolute) skips next 2-byte instruction

strptr  = $fb   ; points at client-128.asm's inputbuf; set by
                ; call_sliding_input before every jsr instr
print_msg_ptr = $fd   ; also confirmed free/unused on the 128 (see
                ; header note on $fb-$fe); NOT the same pair as strptr,
                ; since print_msg runs from inside clear0/clear, which
                ; is itself reached while strptr must stay pointed at
                ; inputbuf for the surrounding editor session

chrout  = $ffd2
getin   = $ffe4
plot    = $fff0

; ROW_BYTES/INPUT_ROW are client-128.asm's own macro_preprocessor.py
; {const:}s -- textual substitution local to that one file's own
; preprocessing pass, not real c64list symbols, so they don't resolve
; here. `=` assignments are real c64list symbols and do resolve across
; {include:}s (see tada-client.asm's own header comment on this) --
; used here instead, kept in sync with client-128.asm's ROW_BYTES(40)/
; INPUT_ROW(24) by hand.
EDITOR_MAXLEN = 40   ; must match client-128.asm's ROW_BYTES
EDITOR_ROW    = 24   ; must match client-128.asm's INPUT_ROW

; --- call_sliding_input: preload the editor's parameters to point at
; client-128.asm's inputbuf/INPUT_ROW, then run the blocking editor.
; Caller (main_loop) is responsible for widening the window to the full
; screen first (set_window_full) and narrowing it back after this
; returns (set_window_narrow) -- drwstr's PLOT-based redraw can't reach
; INPUT_ROW while the normal WIN_BOTTOM=22 dialogue window is active. ---
call_sliding_input:
        lda #<inputbuf
        sta strptr
        lda #>inputbuf
        sta strptr+1
        lda #0
        sta inputbuf            ; start from an empty string each call
        lda #EDITOR_MAXLEN
        sta maxlen
        sta strwin
        lda #EDITOR_ROW
        sta strrow
        lda #0
        sta strcol
        sta lftlim
        lda #$80
        sta mode                 ; $80 = c128 mode (quomod's quote flag)
        jsr instr
        rts

; --- print_msg: .a/.y = low/high byte of a null-terminated string,
; printed via chrout. Replaces the one BASIC ROM strout call this file
; used to make (clear:'s "are you sure" prompt). ---
print_msg:
        sta print_msg_ptr
        sty print_msg_ptr+1
        ldy #0
print_msg_loop:
        lda (print_msg_ptr),y
        beq print_msg_rts
        jsr chrout
        iny
        bne print_msg_loop
print_msg_rts:
        rts

instr:
        lda lftlim      ; enter here
        sta cpos        ; set cursor position
        lda #0          ; first char of string
        sta lcol        ; at left of input area

getstr:
        jsr drwstr      ; display string

cursor:
        jsr rvson       ; reverse on
gets10:
        lda cursor_blink_mask  ; 0 = solid (no periodic redraw/re-reverse
        beq gekey_solid ; cycle at all) -- see cursor_blink_mask's own
                        ; comment; skip straight to a plain GETIN-only
                        ; poll instead of arming the countdown below
        sta blinkctr    ; kept in memory (blinkctr), not X. The C128's
                        ; GETIN clobbers X and Y (Compute's 128
                        ; Programmer's Guide: "Registers changed: .A,
                        ; .X, .Y"), unlike the C64's GETIN (.A only) -- a
                        ; countdown kept in X across these repeated getin
                        ; calls gets silently reset every poll on a real
                        ; 128.
                        ;
                        ; blinkctr USED to be paced by this loop's own
                        ; delyms busy-wait (10ms * reload, decrementing
                        ; and re-checking each spin). Now decremented by
                        ; irq_task_cursor_blink instead (client-128.asm's
                        ; round-robin IRQ task table), so gekey below just
                        ; reads it -- no artificial per-poll delay, and
                        ; GETIN gets checked far more often (better input
                        ; latency) while blink timing runs on the IRQ's own
                        ; real ~60Hz clock instead of CIA-timer polling.
                        ; Safe to decrement from IRQ context unconditionally
                        ; (even while gekey isn't running/blinkctr is stale)
                        ; since it's a plain counter byte, never touched by
                        ; CHROUT/PLOT -- gets10 always resets it fresh
                        ; before every wait cycle anyway.
gekey:
        jsr getin       ; get keypress
        bne gk1         ; if a key pressed
        lda blinkctr    ; irq_task_cursor_blink ticks this down
        bne gekey       ; not done - loop again
        lda rvsflg      ; time to switch cursor
        beq getstr      ; if rvs off, turn it on
        jsr rvsoff      ; if rvs on, turn it off
        jmp gets10

; cursor_blink_mask == 0 (solid, no blink) -- just poll for a keypress,
; leaving the cursor reversed (rvson already ran once above) instead of
; ever re-entering the redraw/re-reverse cycle at all.
gekey_solid:
        jsr getin
        bne gk1
        jmp gekey_solid
gk1:
        pha             ; save key pressed
        jsr rvsoff      ; turn off cursor
        pla
        ldx numkeys     ; see if key needs special handling
gk2:
        cmp edkeys,x
        beq exkey       ; yes - go do it
        dex
        bpl gk2

; put character in .a at cursor
putchr:
        ldy cpos
        cpy maxlen      ; exit if cursor at end
        bcs getstr      ;       of string
        pha             ; save character
        lda (strptr),y  ; cursor at end of buffer?
        bne pc1         ; no: branch
        iny             ; yes
        sta (strptr),y  ; move terminator (0) up one
        inc strlen      ; increase string length
        dey
pc1:
        pla
        sta (strptr),y  ; put char at cursor (stored as-is -- no
                        ; shifted-space substitution here, see header)
        jsr movrt       ; move the cursor right
        jmp getstr      ; back to main loop

; execute special key routines
exkey:
        txa
        asl             ; multiply by two
        tax             ; calculate index
        lda ekaddr,x    ; get command address
        sta jmpkey+1    ; set up jsr lo addr
        lda ekaddr+1,x
        sta jmpkey+2    ; set up jsr hi addr
jmpkey:
        jsr $ffff       ; (self-modifying)
        jmp getstr      ; back to main loop

edkeys:
        byte 13  ; $0d - return
        byte 20  ; $14 - delete
        byte 148 ; $94 - insert
        byte 29  ; $1d - cursor right
        byte 157 ; $9d - cursor left
        byte 34  ; $22 - quote
        byte 19  ; $13 - home
        byte 147 ; $93 - clear
        byte 133 ; $85 - f1
        byte 136 ; $88 - f7
        byte 10  ; $0a - linefeed (ignored, see linefeed: below)
numkeys:
        byte numkeys-edkeys

ekaddr:
        word return
        word delete
        word insert
        word cright
        word cleft
        word quote
        word home
        word clear
        word next_word
        word prev_word
        word linefeed

next_word:
        ldy cpos        ; get position within string
        cpy strlen      ; reached end of string?
        beq space_rts   ; yes, exit

next_word2:
        lda (strptr),y  ; get char under cursor
        cmp #' '        ; found a space?
        beq next_space  ; yes
        jsr cright      ; cursor right if necessary
        jmp next_word   ; continue looping

next_space:
        lda (strptr),y  ; get char in front of cursor
        beq space_rts   ; end of string?
        cmp #' '        ; found a space?
        bne space_rts   ; no, exit
        jsr cright      ; move cursor right
        jmp next_space  ; continue looping

linefeed:
        ; ignore it (crashes otherwise) - upstream note

space_rts:
        rts             ; return to getting input

prev_word:
        ldy cpos        ; get cursor position in string
        cpy lftlim      ; leftmost position?
        beq prev_rts    ; yes, return
        dec cpos
        ldy cpos
        lda (strptr),y  ; get char under cursor
        cmp #' '        ; found a space?
        beq prev_space  ; yes, check for multiple spaces
        jsr cleft       ; no, move string left
        jmp prev_word   ; repeat

prev_space:
        jsr cleft       ; cleft decrements cpos & lcol if necessary
        ldy cpos        ; get cursor position within string
        cpy lftlim      ; leftmost position?
        beq prev_rts    ; yes, return
        lda (strptr),y  ; get char under cursor
        cmp #' '        ; found a space?
        bne prev_space  ; no

prev_space2:
        jsr cright      ; put cursor after space

prev_rts:
        rts             ; return to getting input

; handle carriage return
return:
        lda #0
        sta lcol        ; position string
        sta cpos        ; and cursor
        pla             ; fix up stack so we'll
        pla             ; return to calling routine
        jmp drwstr      ; display string, quit

; handle cursor right
cright:
        ldy cpos
        lda (strptr),y  ; at end of string already?
        beq ekrts       ; yes, don't do anything

movrt:
        iny
        sty cpos        ; move cursor to right
        tya
        sec
        sbc lcol        ; see if we need to slide
        cmp strwin      ; the string to the left
        bcc ekrts       ; no - exit
        inc lcol        ; yes - slide it to the left
ekrts:
        rts

quote:
        lda #34
        jsr putchr
        jmp clrquo      ; clear quote mode

clear:
        lda strlen
        bne clear0
        rts             ; nothing to clear

clear0:
        jsr clearplot
        ldy strwin
        lda #$20
clear_loop:
        jsr chrout
        dey
        bne clear_loop
        jsr clearplot

        lda #<msg_clear_prompt
        ldy #>msg_clear_prompt
        jsr print_msg

clearkey_loop:
        ldx #$00
        stx 204         ; turn system cursor on during wait
        jsr getin       ; key hit in .a
        beq clearkey_loop ; no key hit, loop back
        and #%01111111  ; knock high bit off (shift-lock)

        ldx #$01
        stx 204         ; turn system cursor off again

        cmp #78         ; lower + 14  -- 'n'
        bne clearkey_y
        rts             ; "n" entered, go back to getstr
clearkey_y:
        cmp #89         ; lower + 25  -- 'y'
        bne clearkey_loop

clear1:
        lda #$00        ; load .a with a null
        ldy maxlen      ; do this for length of string

clear2:
        sta (strptr),y  ; store null in buffer
        dey
        cpy #$ff
        bne clear2      ; until done

        ldy #$01
        sty lcol        ; display from beginning of string
        sty strlen      ; reset string length to 1 character
        jmp move_home

home:
move_home:
        ldy lftlim      ; set cursor to leftmost limit position
        sty cpos        ; update cursor position
        lda #$00        ; move to leftmost column (0-based)
        sta lcol        ; set left column to display
        jmp drwstr      ; redraw string (subroutine), rts from there

; subroutine
clearplot:
        ldx strrow
        ldy strcol
        clc
        jmp plot

; handle delete key
delete:
        ldy cpos        ; are we at the left limit
        cpy lftlim      ; of cursor movement?
        bne delchr0     ; no, decrease string length
        rts

delchr0:
        dec strlen      ; decrease string length

delchr:
        lda (strptr),y  ; move chars in string
        dey             ; to the left
        sta (strptr),y
        tax             ; end of string?
        beq cleft       ; yes - now move cursor
        iny
        iny             ; point to next character
        bne delchr      ; branch back

; handle cursor left
cleft:
        ldy cpos
        cpy lftlim      ; already at left limit?
        bne cl1         ; no, branch
        lda lcol        ; yes, see if we need to
        bne declco      ; slide string to right
        rts             ; no, already at last char

cl1:
        dey
        sty cpos        ; move cursor left
        cpy lcol        ; need to slide right?
        bcs cl2         ; no, branch
declco:
        dec lcol        ; yes, slide string right
cl2:
        rts

; handle insert key
insert:
        ldy strlen
i2:     cpy maxlen      ; see if at maximum length
        bcs insrts      ; yes, exit
        inc strlen      ; no, increase strlen

i3:     lda (strptr),y  ; move characters up one
        iny             ; position
        sta (strptr),y
        dey
        dey
        cpy #$ff        ; don't go too far
        beq i4
        cpy cpos        ; at cursor yet?
        bcs i3          ; no, move another
i4:     iny             ; done moving
        lda #$20        ; put a space under the
        sta (strptr),y  ; cursor
insrts:
        rts

; display string in input area (subroutine)
drwstr:
        ldx strrow      ; put cursor at far left
        ldy strcol      ; of input area
drwsxy:
        clc
        jsr plot        ; kernal positions cursor
; commenting this next line out results in crsr down repainting string 1 line down
        jsr quomod      ; quote mode for all chars visible
        ldx #0
        ldy lcol        ; start with leftmost char
dr1:
        lda (strptr),y  ; get character
        beq dr2         ; end of string? yes, branch
        iny             ; point to next character
        byte BIT_ABS    ; skip next 2-byte instruction
dr2:
        lda #32         ; spaces fill rest of line
dr3:
        cmp #$a0        ; shifted space? (underscore convention --
        bne dr4         ; substitute only for display, buffer keeps
        lda #$e4        ; the real $a0 byte -- see header comment)
dr4:
        jsr chrout      ; output the character
        inx
        cpx strwin      ; done yet?
        bcc dr1         ; no: branch, yes: fall through to clrquo

; subroutine
; clear (clrquo)/set (quomod) quote mode
clrquo:
        lda #0          ; value to clear flag
        byte BIT_ABS    ; skip next 2-byte instruction
quomod:
        lda #1          ; value to set flag
        bit mode        ; check computer type
        bmi q1          ; $80?
        sta $d4         ; no, c64
        rts
q1:     sta $f4         ; yes, c128
        rts

; subroutine
; set/clear reverse on/off for cursor blink
rvson:
        ldy cpos
        lda (strptr),y  ; get char under cursor
        cmp #$7f        ; > 128, and thus reversed?
        bpl rvsoff      ;  turn rvs off to get un-reversed char
        sec             ; flag for later
        byte BIT_ZP     ; skip next 1-byte instruction
rvsoff:
        clc             ; flag for later
        php             ; save flag
        lda cpos        ; cursor position within string
        sec
        sbc lcol        ; consider slide position
        clc
        adc strcol      ; left side of input area
        tay             ; move column to .y
        ldx strrow      ; get row to .x
        clc
        jsr plot        ; kernal positions cursor
        plp             ; test the flag
        bcc r1          ; branch if rvs off
        lda #18
        jsr chrout      ; output rvs on character
        byte BIT_ABS    ; skip next 2-byte instruction
r1:
        lda #0
        sta rvsflg      ; set/clear our flag
        jsr quomod      ; all chars will be displayed
        ldy cpos
        lda (strptr),y  ; get character under cursor
        bne r2          ; at end of string?
        lda #32         ; yes, output a space
r2:
        jsr chrout      ; output the character
        jsr clrquo      ; clear quote mode
        lda #146
        jmp chrout      ; output rvs off & exit

; Round-robin IRQ task (client-128.asm's irq_task_table) that paces
; the input editor's cursor blink -- see gets10/gekey's own comment on
; why this replaced the old delyms busy-wait. Only touches a plain
; counter byte, never CHROUT/PLOT, so (unlike a task that called
; rvson/rvsoff directly) it's safe to run completely unconditionally,
; whether or not the editor is even active right now.
irq_task_cursor_blink:
        lda blinkctr
        beq irq_task_cursor_blink_rts
        dec blinkctr
irq_task_cursor_blink_rts:
        rts

; variables
cpos:     byte 0  ; cursor position within string
lcol:     byte 0  ; leftmost column of the string currently displayed
lftlim:   byte 0  ; leftmost limit of cursor travel within the input area
strrow:   byte 0  ; row of the input area (0-24)
strcol:   byte 0  ; leftmost column of the input area
strwin:   byte 0  ; width of the input area (number of viewable characters)
maxlen:   byte 0  ; maximum length of the input string (1-254)
strlen:   byte 0  ; current length of string
rvsflg:   byte 0  ; blink flag for cursor
blinkctr: byte 0  ; blink-timer countdown -- kept out of X, see gets10

; Reload value for blinkctr / blink-speed selector -- same convention
; and same numeric values as tada-client.asm's cursor_blink_mask ($08
; fast/$10 normal/$20 slow/$40 very slow/$00 solid-no-blink), for parity
; across both clients and so a future config-popup port to this client
; can reuse the exact same wire values without a translation table. Not
; yet wired to any live setter (no config popup on this client yet) --
; defaults to $10, matching tada-client.asm's own hardcoded default.
cursor_blink_mask: byte $10

mode:     byte 0  ; $80: c128 mode

msg_clear_prompt:
        ascii "clear: are you sure (y/n)? "
        byte $00
