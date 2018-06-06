{asm}
; casm v4.0 beta syntax:
orig $c000

; open2,9,1,"0:bugsc.52300"
; sys700
;
; *=52300
;
; .opt o2
;
ptr    = $22
channl = $13
curlin = $39
linnum = $14
txtptr = $7a
temp   = $02
temp1  = $49
err    = $02a7
row    = $02a8
col    = $02a9
print  = $ab47
errtab = $a326
linkprg = $a533
clear  = $a659
init   = $a67a
error  = $a36a
strout = $ab1e
fndlin = $a613
stop   = $a82c
linprt = $bdcd
reslst = $a09e
warm1  = $e38b
list   = $a6c9
ready1 = $a47b
nrmerr = $a43a
ierror = $0300
clrchn = $ffcc
plot   = $fff0
;
jsr linkprg ;re-set program pntrs
clc	    ; so user doesn't have
lda ptr	    ; to type new
adc #2
sta $2d
lda ptr+1
adc #0
sta $2e
jsr clear
lda #12	   ;set border color
sta $d020  ;
lda #0	   ;set background color
sta $d021  ;
;
lda 646 ;
pha ;
;
jsr title	;display title
lda ierror+1	;set/reset
cmp #$e3	; debug wedge - compare to normal 58251 ($E38B)
beq e1
;
ldx #7
.byte $2c	; skip next instruction
e1:
ldx #3
lda mtab,x
sta ierror+1
dex
lda mtab,x
sta mtab,x
sta ierror
stx $02
lda #<ms6
ldy #>ms6
jsr strout
ldx $02
dex
ldy mtab,x
dex
lda mtab,x
jsr strout
;
pla
sta 646
;
jmp $a474
;
start:
cpx #$30 ;error code?
bcc entry      ;yes, continue
jmp warm1      ;no, exit
;
entry:
lda curlin+1
cmp #$ff	    ;"direct mode?
bne entry1	    ;no, continue
jmp nrmerr	   ;yes, exit
;
entry1:
stx err	     ;save error
lda #0		    ;reset basic
sta channl
jsr init
;
lda 646 ;save char color
pha	;
;
lda #<ms1    ;display error
ldy #>ms1    ; message
jsr strout
lda err
asl
tax
lda errtab,x
sta ptr
lda errtab+1,x
sta ptr+1
ldy #0
eloop:
lda (ptr),y
pha
and #$7f
jsr print
iny
pla
bpl eloop
lda #<ms2
ldy #>ms2
jsr strout
;
lda $d021 ;
and #15	  ;
cmp #1	  ;
beq floyd ;
lda #5	  ;
.byte $2c
floyd:
lda #144
jsr $ffd2 ;
;
lda curlin    ;get basic
ldx curlin+1  ; line number.
sta linnum    ;find address
stx linnum+1  ; of basic line
jsr fndlin
sec	      ;calculate position
lda txtptr    ; of error in
sbc $5f	      ; basic line
sta temp
jsr l1	  ;list to crt.
;
pla	  ;restore char color
sta 646	  ;
;
ldx row	  ;set cursor
ldy col	  ; position on
clc	  ; basic line
jsr plot
ldx #3	       ;reset screen
l0:
lda btab,x  ; editor pointers
sta $0277,x
dex
bpl l0
lda #4
sta $c6
jmp ready1 ;exit to basic
;
l1:
ldy #1 ;list routine
sty $0f
lda ($5f),y
beq l7
iny
lda ($5f),y
tax
iny
lda ($5f),y
l3:
sty temp1
jsr linprt
lda #$20
l4:
ldy temp1
and #$7f
l5:
jsr print
cmp #34
bne l6
lda $0f
eor #$ff
sta $0f
l6:
iny
beq l7
cpy temp
bne l12
tya
pha
sec
jsr plot ;save screen
stx row	 ;position at
sty col	 ;error location
pla
tay
l12:
lda ($5f),y
bne l8
l7:
rts
l8:
bpl l5
cmp #$ff
beq l5
bit $0f
bmi l5
sec
sbc #$7f
tax
sty temp1
ldy #$ff
l9:
dex
beq l11
l10:
iny
lda reslst,y
bpl l10
bmi l9
l11:
iny
lda reslst,y
bmi l4
jsr print
bne l11
fil:
lda #13
jsr $ffd2
ldy #7
fil2:
lda #$20
jsr $ffd2
dey
bne fil2
lda #$12
jsr $ffd2
lda #$1f
jmp $ffd2
;
title:
lda #0
sta $2
lp1:
ldy $2
lda ms3,y
bne lp4
jsr fil
jmp lp8
lp4:
cmp #255
bne lp6
rts
lp6:
jsr $ffd2
lp8:
inc $2
jmp lp1
;
;
;
ms1:
.byte $93,$1c,$5b,0
ms2:
ascii " error]"
.byte 13,13,0
ms3:
.byte $93,9,142,0
.byte $c2,$a9	;ascii "©"
.byte $9a
ascii "			       "
.byte 0,$20,$9a
ascii "	  loadstar presents    "
.byte 0,$20,$9a
ascii "	      bug scout	       "
.byte 0,$20,$9a
ascii "	    by rick nash       "
.byte 0,$20,$9a
ascii " (c) softdisk publishing "
.byte 0,$20,$9a
ascii "			       "
.byte 0
ascii "			       "
.byte 146
.byte $c2,$a9	;ascii "©"
.byte 13,13,13,255
ms4:
ascii "installed"
.byte 13,13,0
ms5:
ascii "removed"
.byte 13,13,0
ms6:
.byte 159
ascii "	     bug scout is now "
.byte 0
mtab:
.word ms4,start,ms5,$e38b
btab:
.byte $11,$11,$91,$91
{endasm}