; instr - enhanced string input routine
; commodore world issue 21, pg. 36
; string return help: agentfriday
         *= $2000
         jmp setup
; zero-page locations:

forpnt   = $49
         ; temporary pointer to index
         ; variable used by 'for'
fac_strptr = $64
strptr   = $fb

         ; kernal routines:

basic_error = $a437
         ; output error message in .a
assign_string = $aa2c
         ; string w/ descriptor address
         ; in $64/$65 stored in variable
         ; descriptor pointed to by $49/
         ; $4a

; $49: OLD descriptor pointed to by SYS
;      statement
; $64: NEW descriptor that just-input
;      line points to describng value
;      about to be assigned to var

get_var  = $b08b
     ; read variable name from basic
     ; text, look up address
skip_comma = $e20e
     ; check basic text for comma
     ; followed by something else
chrout   = $ffd2 ;kernal character outpu
getin    = $ffe4 ;kernal character input
plot     = $fff0 ;kernal cursor position

; variables
datco    = $01 ; input text color
cpos     .byte 0
lcol     .byte 0
lftlim   .byte 0; furthest left cursor
           ; can move in input area
strrow   .byte 0; input display row
strcol   .byte 0; leftmost column of
           ; input area (0-80)
strwin   .byte 0; # viewable chars in
           ; input area
rvsflg   .byte 0
mode     .byte 0; $80: c128 mode

setup    lda #18
         sta strrow

         lda #0
         sta strcol

         lda #39
         sta strwin

         lda #250
         sta strlen

         lda #0
         sta lftlim

         ldx #<inbuf
         ldy #>inbuf
         stx strptr
         sty strptr+1

         lda #0
         sta inbuf

         lda #$00   ; #$80 for c128 mode
         sta mode

         jsr skip_comma
         jsr get_var     ; addr in .a/.y
         ldx $0d         ; variable type
         bmi is_string

         lda #$16       ; ?type mismatch
         jmp basic_error

is_string
         pha    ; push string descriptor
                ; on to stack

         tya    ; until after input
         pha    ; routine is finished

;instr main loop

instr    lda lftlim
         sta cpos
         lda #0
         sta lcol
getstr   jsr drwstr
         jsr rvson
gets10   ldx $fe
gekey    jsr getin
         bne gk1
         ldy #10
         jsr delyms
         dex
         bne gekey
         lda rvsflg
         beq getstr
         jsr rvsoff
         jmp gets10
gk1      pha
         jsr rvsoff
         pla
         ldx #5
gk2      cmp edkeys,x
         beq exkey
         dex
         bpl gk2

;put character at cursor

putchr   ldy cpos
         cpy strlen
         bcs getstr
         pha
         lda (strptr),y
         bne pc1
         iny
         sta (strptr),y
         dey
pc1      pla
         sta (strptr),y
         jsr movrt
         jmp getstr

;execute special key routines

exkey    txa
         asl a
         tax
         lda ekaddr,x
         sta jmpkey+1
         lda ekaddr+1,x
         sta jmpkey+2
jmpkey   jsr jmpkey
         jmp getstr

edkeys   .byte 13,20,148,29,157,34
ekaddr   .word return,delete,insert
         .word cright,cleft,ekrts

;carriage return - finish up
return   lda #0
         sta lcol
         sta cpos
         pla  ; af: pull return address,
         pla  ; "specialkey" dispatch
         jsr drwstr

    ; p: here is new code to send
    ;    string back to basic

         ldy #$00   ; max string length
loop     lda (strptr),y
         ; load .a w/ addr of strptr + y
         beq foundzero; branch if =0
         iny          ; $01, $02, $03...
         bne loop   ; branch if not zero
foundzero sty strlen ;store back

         pla      ; pull SYS-line string
         sta forpnt+1
         pla      ; descriptor off stack
         sta forpnt
         lda #<strptr     ; $--xx
         sta fac_strptr   ; $64
         sta <strptr2     ; new string
         lda #>strptr     ; $xx--
         sta fac_strptr+1 ; $65
         sta >strptr2     ; new string

    ; assign_string = $aa2c
    ; string w/ descriptor address in
    ; $64/$65 stored in variable
    ; descriptor pointed to by $49/$4a

         jmp assign_string

;handle cursor right

cright   ldy cpos
         lda (strptr),y
         beq ekrts

movrt    iny
         sty cpos
         tya
         sec
         sbc lcol
         cmp strwin
         bcc ekrts
         inc lcol
ekrts    rts

;handle delete key

delete   ldy cpos
         cpy lftlim
         bne delchr
         lda (strptr),y
         beq ekrts
         iny

delchr   lda (strptr),y
         dey
         sta (strptr),y
         tax
         beq cleft
         iny
         iny
         bne delchr

;handle cursor left

cleft    ldy cpos
         cpy lftlim
         bne cl1
         lda lcol
         bne declco
         rts

cl1      dey
         sty cpos
         cpy lcol
         bcs cl2
declco   dec lcol
cl2      rts

;handle insert key

insert   ldy #0
i1       lda (strptr),y
         beq i2
         iny
         bne i1
i2       cpy strlen
         bcs insrts

i3       lda (strptr),y
         iny
         sta (strptr),y
         dey
         dey
         cpy #$ff
         beq i4
         cpy cpos
         bcs i3
i4       iny
         lda #$20
         sta (strptr),y
insrts   rts

;display string in input area

drwstr   ldx strrow
         ldy strcol
drwsxy   clc
         jsr plot
         lda #datco
         jsr chrout
         jsr quomod
         ldx #0
         ldy lcol
dr1      lda (strptr),y
         beq dr2
         iny
         .byte $2c
dr2      lda #32
         jsr chrout
         inx
         cpx strwin
         bcc dr1

;set/clear quote mode

clrquo   lda #0
         .byte $2c
quomod   lda #1
         bit mode
         bmi q1
         sta $d4
         rts
q1       sta $f4
         rts

         ; set/clear reverse on/off
         ; for cursor blink

rvson    sec
         .byte $24
rvsoff   clc
         php
         lda cpos
         sec
         sbc lcol
         clc
         adc strcol
         tay
         ldx strrow
         clc
         jsr plot
         lda #datco
         jsr chrout
         plp
         bcc r1
         lda #18
         jsr chrout
         .byte $2c
r1       lda #0
         sta rvsflg
         jsr quomod
         ldy cpos
         lda (strptr),y
         bne r2
         lda #32
r2       jsr chrout
         jsr clrquo
         lda #146
         jmp chrout

;delay used for cursor blink

delyms   pha
         lda #$7f
         sta $dd0d
         lda #$08
         sta $dd0e
         sta $dd0f
         lda #$ff
         sta $dd04
         lda #$04
         sta $dd05
de1      lda #$11
         sta $dd0e
de2      lda $dd05
         bne de2
         dey
         bne de2
         pla
         rts

; space for string buffer
; af: I would recommend allocating the
; string descriptor itself in your
; code (.byte/.word) and store the
; address of inbuf there as well as
; strptr.

; max string length while in routine,
; current string length upon return
; to BASIC
strlen   .byte $ff

; FIXME:
; zero-page pointer for lda (strptr),x
; but later needs to become the address
; of string after routine exits to
; basic
strptr2  .word $ffff
inbuf    .word $ffff

