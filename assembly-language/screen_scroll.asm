{include:basic_stub.asm}
; --- CONSTANTS ---
SCREEN_RAM = $0400
LAST_LINE  = SCREEN_RAM + (24 * 40)
PTR_LO     = $D1        ; KERNAL Row Pointer Low
PTR_HI     = $D2        ; KERNAL Row Pointer High
COL_IDX    = $D3        ; KERNAL Column Index
SRC_LO     = $FB        ; Temporary ZP pointers for Scroll
SRC_HI     = $FC
DST_LO     = $FD
DST_HI     = $FE

MAIN:
    ; 1. Clear Screen
    ldx #0
    stx COL_IDX
CLEAR_SCREEN_LOOP:
    jsr clear_to_eol
    INX
    CPX #25
    BNE CLEAR_SCREEN_LOOP

    ; 2. Init Pointer to Bottom Row
    LDX #24
    jsr set_screen_line
    LDA #0
    STA COL_IDX

{def:debug}
{ifdef:debug}
    ; --- DEBUG MODE: Fill screen with A-Y and scroll ---
    LDA #1              ; Screen code for 'A'
    STA CHAR_VAL
DEBUG_ROW_LOOP:
    LDA #0
    STA COL_IDX
DEBUG_CHAR_LOOP:
    LDA CHAR_VAL        ; Get current screen code
    JSR STORE_CHAR      ; Write it
    LDA COL_IDX
    CMP #40
    BNE DEBUG_CHAR_LOOP ; Fill one full line

    ; Line is done (and scrolled). Next char.
    INC CHAR_VAL
    LDA CHAR_VAL
    CMP #26             ; Go through 'Z'
    BNE DEBUG_ROW_LOOP
    RTS

CHAR_VAL: byte 0
{else:}
    ; --- NORMAL MODE: Print Strings ---
    LDA #0
    STA $02             ; Using $02 as string counter
STR_LOOP:
    LDA $02
    ASL
    TAX
    LDA fake_input_pointers,x
    STA $FC
    LDA fake_input_pointers+1,x
    STA $FD

    LDY #0
CHAR_INNER:
    LDA ($FC),y
    BEQ STR_DONE
    JSR PRINT_CHAR
    INY
    BNE CHAR_INNER
STR_DONE:
    LDA #13
    JSR PRINT_CHAR

    LDX #15
    JSR DELAY           ; Wait approx 0.25s

    INC $02
    LDA $02
    CMP #10
    BNE STR_LOOP
    RTS
{endif}

; --- PRINT ROUTINE ---
PRINT_CHAR:
    CMP #$0D            ; CR?
    BEQ FORCE_SCROLL

    ; Simple PETSCII to Screen Code (Upper Case)
    PHA
    CMP #$40
    BCC SKIP_MAP
    AND #$3F
SKIP_MAP:
    JSR STORE_CHAR
    PLA
    RTS

FORCE_SCROLL:
    jsr clear_to_eol
    JSR SCROLL_UP
    LDA #0
    STA COL_IDX
    RTS

; --- LOW LEVEL STORAGE ---
STORE_CHAR:
    LDY COL_IDX
    STA (PTR_LO),y      ; Write to screen
    INY
    STY COL_IDX
    CPY #40
    BNE STORE_EXIT

    JSR SCROLL_UP       ; Scroll when line ends
    LDA #0
    STA COL_IDX
STORE_EXIT:
    RTS

; --- SCROLL LOGIC ---
SCROLL_UP:
    LDY #0              ; Start with Row 0 as Destination
S_LOOP:
    LDA ROW_LO,y        ; Set DST
    STA DST_LO
    LDA ROW_HI,y
    STA DST_HI

    INY                 ; Y is now Source Row
    LDA ROW_LO,y
    STA SRC_LO
    LDA ROW_HI,y
    STA SRC_HI

    ; Copy line
    LDX #0
L_LOOP:
    LDA (SRC_LO),x
    STA (DST_LO),x
    INX
    CPX #40
    BNE L_LOOP

    CPY #24             ; Did we just move Row 24 into Row 23?
    BNE S_LOOP

    ; Clear entire last line
    lda #0
    sta COL_IDX
    jsr clear_to_eol

    ; Fix row Pointers back to bottom row
    LDX #24
    jsr set_screen_line
    RTS

clear_to_eol:
; use after carriage return received to clear to end of line
    LDA COL_IDX
clear_to_eol_loop:
    CMP #40
    BEQ clear_to_eol_done
    LDA #$20
    JSR STORE_CHAR
    JMP clear_to_eol
clear_to_eol_done:
    RTS

set_screen_line:
    ; Set KERNAL screen row pointers to line number in X
    ; Enter: .x = line number (0-24)
    cpx #25
    bcs set_screen_line_done ; out of range
    LDA ROW_LO,x
    STA PTR_LO
    LDA ROW_HI,x
    STA PTR_HI
set_screen_line_done:
    RTS

; --- DELAY ---
DELAY:
    LDA $A2
W_LOOP:
    CMP $A2
    BEQ W_LOOP
    DEX
    BNE DELAY
    RTS

; --- TABLES ---
; TODO: text could be moved to $a000-$bfff, under ROM
;              ----+----+----+----+----+----+----+----+
;              Welcome to the "Totally Awesome Dungeon
;              Adventure" client test v0.001.
fake_server_input_1:
	ascii "Welcome to the {quote}Totally Awesome Dungeon",13
	ascii "Adventure{quote} client test v0.001.",$00
fake_server_input_2:
        ascii "Pinacolada enters the room.",$00
fake_server_input_3:
        ascii "This is line 4.",$00
fake_server_input_4:
        ascii "This is line 5.",$00
fake_server_input_5:
        ascii "This is line 6.",$00
fake_server_input_6:
        ascii "This is line 7.",$00
fake_server_input_7:
        ascii "This is line 8.",$00
fake_server_input_8:
        ascii "This is line 9.",$00
fake_server_input_9:
        ascii "This is line 10.",$00
fake_server_input_10:
        ascii "This is line 11.",$00

fake_input_pointers:
        word fake_server_input_1
        word fake_server_input_2
        word fake_server_input_3
        word fake_server_input_4
        word fake_server_input_5
        word fake_server_input_6
        word fake_server_input_7
        word fake_server_input_8
        word fake_server_input_9
        word fake_server_input_10

; Low bytes of screen ram row starts
; FIXME: I think these are stored in ROM somewhere? if so, use that table instead
ROW_LO:
    byte $00, $28, $50, $78, $a0, $c8, $f0, $18
    byte $40, $68, $90, $b8, $e0, $08, $30, $58
    byte $80, $a8, $d0, $f8, $20, $48, $70, $98, $c0

; High bytes of screen ram row starts:
ROW_HI:
    byte $04, $04, $04, $04, $04, $04, $04, $05
    byte $05, $05, $05, $05, $05, $06, $06, $06
    byte $06, $06, $06, $06, $07, $07, $07, $07, $07

char_output:
    ; Placeholder for character to output
    byte ' '

; {include:screen-handler.asm}
{undef:debug}
{ifdef:debug}
    ; 2. Loop through our 10 test strings
    ; save whatever is in $fb-$fe since they are also COPY_BYTE_LOOP's
        ; work area
    jsr save_zp
    LDA #0
    STA $FB             ; Use $FB as our "string counter" (0-9)

    jsr restore_zp
    RTS                 ; Return to BASIC
{endif}

save_zp:
; don't use e.g., "lda $fb / pha" because the RTS will pop the last two
; values off the stack and crash
	lda $fb
	sta restore_zp+1
	lda $fc
	sta restore_zp+5
	lda $fd
	sta restore_zp+9
	lda $fe
	sta restore_zp+13
	rts

restore_zp:
	lda #$ff	; +1
	sta $fb
	lda #$ff	; +5
	sta $fc
	lda #$ff	; +9
	sta $fd
	lda #$ff	; +13
	sta $fe
	rts
