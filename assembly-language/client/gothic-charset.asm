; gothic-charset.asm
; Custom C64 character set: blackletter/Olde English style, uppercase +
; lowercase, sourced from "f.antic1" (assembly-language/client/Fonts.d81),
; a font disk found in Ryan's local C64 archive -- see project memory
; (async-prompt/status-line project) for the fuller search/selection story.
;
; Layout matches the standard C64 charset convention: codes 0-31 = lowercase
; + control/graphics, 32-63 = punctuation/digits, 64-95 = uppercase, 96-127 =
; PETSCII graphics (mostly preserved from f.antic1 as-is), 128-255 = reverse-
; video range (genuinely distinct glyphs in this font, NOT auto-mirrored copies
; of 0-127 -- confirmed by diffing every byte, so don't assume ORA #$80 alone
; gives a clean reverse-video look here the way it does with the stock ROM font).
;
; Two glyphs hand-patched in by Claude, 2026-08-22, per Ryan's request: codes
; 96 ($60, down-arrow) and 97 ($61, right-arrow), replacing two of f.antic1's
; own PETSCII graphics-range fillers -- up-arrow (30/$1e) and left-arrow
; (31/$1f) were already present in the font, so only the missing two directions
; needed adding, for the planned #overview map screen. Not freehand-drawn --
; down is a vertical mirror of the font's own up-arrow, right is a horizontal
; bit-mirror of its own left-arrow, so weight/style match exactly.
;
; Uses C64List's `bits` pseudo op (C64List Users Guide.pdf, monochrome form:
; '.' = 0 bit, '*' = 1 bit, one row of 8 per line) instead of raw byte/hex --
; Ryan's ask, so each glyph's pixels are directly visible/editable right in
; source rather than needing a hex-to-pixel mental conversion.
;
; Raw dot data only, no PRG load address (2048 bytes, 256 glyphs x 8 bytes) --
; pull in via {include:gothic-charset.asm} and poke/copy gothic_charset,X to
; wherever the char generator needs to live (see tada_screen_blit_test.asm's
; switch_to_bank3_with_charset for the VIC-bank-3 charset relocation this was
; built to eventually feed).

gothic_charset:
;   0 ($00)
        bits ..****..
        bits .**..**.
        bits .**.***.
        bits .**.***.
        bits .**.....
        bits .**...*.
        bits ..****..
        bits ........

;   1 ($01) 'a'
        bits ........
        bits ........
        bits .****...
        bits ...***..
        bits .*****..
        bits ***.**..
        bits .******.
        bits ........

;   2 ($02) 'b'
        bits **......
        bits .**.....
        bits .**.....
        bits .*****..
        bits .**..**.
        bits .**..**.
        bits .*****..
        bits ........

;   3 ($03) 'c'
        bits ........
        bits ........
        bits ..****..
        bits .**..**.
        bits .**.....
        bits .**..**.
        bits ..****..
        bits ........

;   4 ($04) 'd'
        bits .....**.
        bits ....**..
        bits ....**..
        bits .*****..
        bits **..**..
        bits **..**..
        bits .*****..
        bits ........

;   5 ($05) 'e'
        bits ........
        bits ........
        bits ..****..
        bits .**..**.
        bits .******.
        bits .**.....
        bits ..****..
        bits ........

;   6 ($06) 'f'
        bits ........
        bits ....***.
        bits ...**...
        bits ..*****.
        bits ...**...
        bits ...**...
        bits ..**....
        bits ........

;   7 ($07) 'g'
        bits ........
        bits ........
        bits .******.
        bits **..**..
        bits **..**..
        bits .*****..
        bits ....**..
        bits ..***...

;   8 ($08) 'h'
        bits **......
        bits .**.....
        bits .**.....
        bits .*****..
        bits .**..**.
        bits .**..**.
        bits **...**.
        bits ........

;   9 ($09) 'i'
        bits ........
        bits ...**...
        bits ........
        bits ...**...
        bits ...**...
        bits .*.**.*.
        bits .******.
        bits ........

;  10 ($0a) 'j'
        bits ........
        bits .....**.
        bits ........
        bits ....***.
        bits .....**.
        bits ..**.**.
        bits .**..**.
        bits ..****..

;  11 ($0b) 'k'
        bits **......
        bits .**.....
        bits .**..**.
        bits .**.**..
        bits .****...
        bits .**.**..
        bits **...**.
        bits ........

;  12 ($0c) 'l'
        bits ..**....
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ....**..
        bits ........

;  13 ($0d) 'm'
        bits ........
        bits ........
        bits **...**.
        bits ***.***.
        bits *******.
        bits **.*.**.
        bits **...**.
        bits ........

;  14 ($0e) 'n'
        bits ........
        bits ........
        bits ******..
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits **...**.
        bits ........

;  15 ($0f) 'o'
        bits ........
        bits ........
        bits ..****..
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits ..****..
        bits ........

;  16 ($10) 'p'
        bits ........
        bits ........
        bits .*****..
        bits .**..**.
        bits .**..**.
        bits .*****..
        bits .**.....
        bits **......

;  17 ($11) 'q'
        bits ........
        bits ........
        bits .*****..
        bits **..**..
        bits **..**..
        bits .*****..
        bits ....**..
        bits .....**.

;  18 ($12) 'r'
        bits ........
        bits ........
        bits .**.**..
        bits .****...
        bits .**.....
        bits .**.....
        bits **......
        bits ........

;  19 ($13) 's'
        bits ........
        bits ........
        bits ..****..
        bits .***....
        bits ..****..
        bits ....***.
        bits ..****..
        bits ........

;  20 ($14) 't'
        bits ..**....
        bits ...**...
        bits .******.
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ....**..

;  21 ($15) 'u'
        bits ........
        bits ........
        bits **...**.
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits ..*****.
        bits ........

;  22 ($16) 'v'
        bits ........
        bits ........
        bits **...**.
        bits .**.**..
        bits .**.**..
        bits ..***...
        bits ...*....
        bits ........

;  23 ($17) 'w'
        bits ........
        bits ........
        bits *.....*.
        bits **.*.**.
        bits .*****..
        bits .*****..
        bits .**.**..
        bits ........

;  24 ($18) 'x'
        bits ........
        bits ........
        bits .**..**.
        bits .******.
        bits ...**...
        bits .******.
        bits .**..**.
        bits ........

;  25 ($19) 'y'
        bits ........
        bits ........
        bits **...**.
        bits .**..**.
        bits .**..**.
        bits ..*****.
        bits ....**..
        bits ..***...

;  26 ($1a) 'z'
        bits ........
        bits ........
        bits .******.
        bits .**.**..
        bits ...**...
        bits ..**.**.
        bits .******.
        bits ........

;  27 ($1b)
        bits ..****..
        bits ..**....
        bits ..**....
        bits ..**....
        bits ..**....
        bits ..**....
        bits ..****..
        bits ........

;  28 ($1c)
        bits ...***..
        bits ..*..**.
        bits ..*.....
        bits .****...
        bits ..*...*.
        bits .*....*.
        bits ******..
        bits ........

;  29 ($1d)
        bits ..****..
        bits ....**..
        bits ....**..
        bits ....**..
        bits ....**..
        bits ....**..
        bits ..****..
        bits ........

;  30 ($1e) up-arrow
        bits ........
        bits ...**...
        bits ..****..
        bits .******.
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...

;  31 ($1f) left-arrow
        bits ........
        bits ...*....
        bits ..**....
        bits .*******
        bits .*******
        bits ..**....
        bits ...*....
        bits ........

;  32 ($20) space
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........

;  33 ($21)
        bits ********
        bits ..****..
        bits ...**...
        bits ...**...
        bits ........
        bits ...**...
        bits ...**...
        bits ........

;  34 ($22)
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........

;  35 ($23)
        bits .**..**.
        bits .**..**.
        bits ********
        bits .**..**.
        bits ********
        bits .**..**.
        bits .**..**.
        bits ........

;  36 ($24)
        bits ...**...
        bits ..*****.
        bits .**.....
        bits ..****..
        bits .....**.
        bits .*****..
        bits ...**...
        bits ........

;  37 ($25)
        bits .**...*.
        bits .**..**.
        bits ....**..
        bits ...**...
        bits ..**....
        bits .**..**.
        bits .*...**.
        bits ........

;  38 ($26)
        bits ..****..
        bits .**..**.
        bits ..****..
        bits ..***...
        bits .**..***
        bits .**..**.
        bits ..******
        bits ........

;  39 ($27)
        bits .....**.
        bits ....**..
        bits ...**...
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........

;  40 ($28)
        bits ....**..
        bits ...**...
        bits ..**....
        bits ..**....
        bits ..**....
        bits ...**...
        bits ....**..
        bits ........

;  41 ($29)
        bits ..**....
        bits ...**...
        bits ....**..
        bits ....**..
        bits ....**..
        bits ...**...
        bits ..**....
        bits ........

;  42 ($2a)
        bits ........
        bits .**..**.
        bits ..****..
        bits ********
        bits ..****..
        bits .**..**.
        bits ........
        bits ........

;  43 ($2b)
        bits ........
        bits ...**...
        bits ...**...
        bits .******.
        bits ...**...
        bits ...**...
        bits ........
        bits ........

;  44 ($2c)
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ...**...
        bits ...**...
        bits ..**....

;  45 ($2d)
        bits ........
        bits ........
        bits ........
        bits .******.
        bits ........
        bits ........
        bits ........
        bits ........

;  46 ($2e)
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ...**...
        bits ...**...
        bits ........

;  47 ($2f)
        bits ........
        bits ......**
        bits .....**.
        bits ....**..
        bits ...**...
        bits ..**....
        bits .**.....
        bits ........

;  48 ($30) '0'
        bits ..***...
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits ..***...
        bits ........

;  49 ($31) '1'
        bits ...**...
        bits ..***...
        bits *****...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ..****..
        bits ........

;  50 ($32) '2'
        bits .****...
        bits **..**..
        bits **..**..
        bits ..***...
        bits .**.....
        bits **..**..
        bits ******..
        bits ........

;  51 ($33) '3'
        bits ..****..
        bits .**..**.
        bits .**..**.
        bits ....**..
        bits .**..**.
        bits .**..**.
        bits ..****..
        bits ........

;  52 ($34) '4'
        bits ....**..
        bits ...***..
        bits .*****..
        bits **..**..
        bits *******.
        bits ....**..
        bits ...****.
        bits ........

;  53 ($35) '5'
        bits .******.
        bits .**.....
        bits .*****..
        bits .....**.
        bits ..**.**.
        bits .**..**.
        bits ..****..
        bits ........

;  54 ($36) '6'
        bits ..****..
        bits .**..**.
        bits **......
        bits ******..
        bits ***..**.
        bits .**..**.
        bits ..****..
        bits ........

;  55 ($37) '7'
        bits .******.
        bits **...**.
        bits ....**..
        bits ...**...
        bits ...**...
        bits ...**...
        bits ....**..
        bits ........

;  56 ($38) '8'
        bits ..***...
        bits .**.**..
        bits .**.**..
        bits ..***...
        bits .**.**..
        bits .**.**..
        bits ..***...
        bits ........

;  57 ($39) '9'
        bits .****...
        bits **..**..
        bits **..**..
        bits .*****..
        bits ....**..
        bits **..**..
        bits .****...
        bits ........

;  58 ($3a)
        bits ........
        bits ........
        bits ...**...
        bits ........
        bits ........
        bits ...**...
        bits ........
        bits ........

;  59 ($3b)
        bits ........
        bits ........
        bits ...**...
        bits ........
        bits ........
        bits ...**...
        bits ...**...
        bits ..**....

;  60 ($3c)
        bits ....***.
        bits ...**...
        bits ..**....
        bits .**.....
        bits ..**....
        bits ...**...
        bits ....***.
        bits ........

;  61 ($3d)
        bits ........
        bits ........
        bits .******.
        bits ........
        bits .******.
        bits ........
        bits ........
        bits ........

;  62 ($3e)
        bits .***....
        bits ...**...
        bits ....**..
        bits .....**.
        bits ....**..
        bits ...**...
        bits .***....
        bits ........

;  63 ($3f)
        bits ..****..
        bits .**..**.
        bits ..**.**.
        bits ....**..
        bits ...**...
        bits ........
        bits ...**...
        bits ........

;  64 ($40) '-' (h-line, box top/bottom)
        bits ........
        bits ........
        bits ........
        bits ********
        bits ********
        bits ........
        bits ........
        bits ........

;  65 ($41) 'A'
        bits ...**...
        bits ..****..
        bits .**..**.
        bits .**..**.
        bits .******.
        bits .**..**.
        bits **....**
        bits ........

;  66 ($42) 'B'
        bits ******..
        bits ***..**.
        bits .**..**.
        bits .*****..
        bits .**..**.
        bits ***..**.
        bits ******..
        bits ........

;  67 ($43) 'C'
        bits ..****..
        bits .**..**.
        bits **...**.
        bits **......
        bits **...**.
        bits .**..**.
        bits ..****..
        bits ........

;  68 ($44) 'D'
        bits *****...
        bits .**.**..
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits .**.**..
        bits *****...
        bits ........

;  69 ($45) 'E'
        bits ******..
        bits .**..**.
        bits .**.....
        bits .****...
        bits .**.....
        bits .**..**.
        bits ******..
        bits ........

;  70 ($46) 'F'
        bits ******..
        bits .**..**.
        bits .**.....
        bits .****...
        bits .**.....
        bits .**.....
        bits ****....
        bits ........

;  71 ($47) 'G'
        bits ..****..
        bits .**..**.
        bits .**.....
        bits .**.***.
        bits .**..**.
        bits .**..**.
        bits ..*****.
        bits ........

;  72 ($48) 'H'
        bits **....**
        bits .**..**.
        bits .**..**.
        bits .******.
        bits .**..**.
        bits .**..**.
        bits **....**
        bits ........

;  73 ($49) 'I'
        bits ..****..
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ..****..
        bits ........

;  74 ($4a) 'J'
        bits ...****.
        bits ....**..
        bits ....**..
        bits ....**..
        bits .**.**..
        bits .**.**..
        bits ..***...
        bits ........

;  75 ($4b) 'K'
        bits **...**.
        bits ***.**..
        bits .****...
        bits .***....
        bits .****...
        bits ***.**..
        bits **...**.
        bits ........

;  76 ($4c) 'L'
        bits **......
        bits .**.....
        bits .**.....
        bits .**.....
        bits .**.**..
        bits .**..**.
        bits .******.
        bits ........

;  77 ($4d) 'M'
        bits *.....*.
        bits **...**.
        bits ***.***.
        bits *******.
        bits **.*.**.
        bits **...**.
        bits **...**.
        bits ........

;  78 ($4e) 'N'
        bits .**..**.
        bits .***.**.
        bits .******.
        bits .******.
        bits .**.***.
        bits .**..**.
        bits .**..**.
        bits ........

;  79 ($4f) 'O'
        bits ..****..
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits ..****..
        bits ........

;  80 ($50) 'P'
        bits ******..
        bits .**..**.
        bits .**..**.
        bits .*****..
        bits .**.....
        bits .**.....
        bits ****....
        bits ........

;  81 ($51) 'Q'
        bits ..****..
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits ..****..
        bits ...****.
        bits ........

;  82 ($52) 'R'
        bits ******..
        bits .**..**.
        bits .**..**.
        bits .*****..
        bits .**.**..
        bits .**.**..
        bits ***.***.
        bits ........

;  83 ($53) 'S'
        bits ..*****.
        bits .***.**.
        bits .***....
        bits ..****..
        bits ....***.
        bits .**.***.
        bits .*****..
        bits ........

;  84 ($54) 'T'
        bits .******.
        bits .*.**.*.
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ..****..
        bits ........

;  85 ($55) 'U'
        bits **...**.
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits ..***...
        bits ........

;  86 ($56) 'V'
        bits **...**.
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits .**.**..
        bits ..***...
        bits ...*....
        bits ........

;  87 ($57) 'W'
        bits **...**.
        bits **...**.
        bits **.*.**.
        bits *******.
        bits *******.
        bits ***.***.
        bits **...**.
        bits ........

;  88 ($58) 'X'
        bits **...**.
        bits .**.**..
        bits ..***...
        bits ..***...
        bits ..***...
        bits .**.**..
        bits **...**.
        bits ........

;  89 ($59) 'Y'
        bits .**..**.
        bits .**..**.
        bits .**..**.
        bits ..****..
        bits ...**...
        bits ...**...
        bits ..****..
        bits ........

;  90 ($5a) 'Z'
        bits .******.
        bits .**..**.
        bits ....**..
        bits ...**...
        bits ..**....
        bits .**..**.
        bits .******.
        bits ........

;  91 ($5b)
        bits ...**...
        bits ...**...
        bits ...**...
        bits ********
        bits ********
        bits ...**...
        bits ...**...
        bits ...**...

;  92 ($5c)
        bits **......
        bits **......
        bits ..**....
        bits ..**....
        bits **......
        bits **......
        bits ..**....
        bits ..**....

;  93 ($5d) '|' (v-line, box sides)
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...

;  94 ($5e)
        bits ..**..**
        bits ..**..**
        bits **..**..
        bits **..**..
        bits ..**..**
        bits ..**..**
        bits **..**..
        bits **..**..

;  95 ($5f)
        bits ********
        bits .*******
        bits ..******
        bits ...*****
        bits ....****
        bits .....***
        bits ......**
        bits .......*

;  96 ($60) down-arrow (added)
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...**...
        bits .******.
        bits ..****..
        bits ...**...
        bits ........

;  97 ($61) right-arrow (added)
        bits ........
        bits ....*...
        bits ....**..
        bits *******.
        bits *******.
        bits ....**..
        bits ....*...
        bits ........

;  98 ($62)
        bits ........
        bits ........
        bits ........
        bits ........
        bits ********
        bits ********
        bits ********
        bits ********

;  99 ($63)
        bits ********
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........

; 100 ($64)
        bits ........
        bits ........
        bits ........
        bits ...**...
        bits ........
        bits ........
        bits ........
        bits ........

; 101 ($65)
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......

; 102 ($66)
        bits **..**..
        bits **..**..
        bits ..**..**
        bits ..**..**
        bits **..**..
        bits **..**..
        bits ..**..**
        bits ..**..**

; 103 ($67)
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**

; 104 ($68)
        bits ........
        bits ........
        bits ........
        bits ........
        bits **..**..
        bits **..**..
        bits ..**..**
        bits ..**..**

; 105 ($69)
        bits ********
        bits *******.
        bits ******..
        bits *****...
        bits ****....
        bits ***.....
        bits **......
        bits *.......

; 106 ($6a)
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**
        bits ......**

; 107 ($6b)
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...*****
        bits ...*****
        bits ...**...
        bits ...**...
        bits ...**...

; 108 ($6c)
        bits ........
        bits ........
        bits ........
        bits ........
        bits ....****
        bits ....****
        bits ....****
        bits ....****

; 109 ($6d) box corner
        bits ...**...
        bits ...**...
        bits ...**...
        bits ...*****
        bits ...*****
        bits ........
        bits ........
        bits ........

; 110 ($6e) box corner
        bits ........
        bits ........
        bits ........
        bits *****...
        bits *****...
        bits ...**...
        bits ...**...
        bits ...**...

; 111 ($6f)
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ********
        bits ********

; 112 ($70) box corner
        bits ........
        bits ........
        bits ........
        bits ...*****
        bits ...*****
        bits ...**...
        bits ...**...
        bits ...**...

; 113 ($71)
        bits ...**...
        bits ...**...
        bits ...**...
        bits ********
        bits ********
        bits ........
        bits ........
        bits ........

; 114 ($72)
        bits ........
        bits ........
        bits ........
        bits ********
        bits ********
        bits ...**...
        bits ...**...
        bits ...**...

; 115 ($73)
        bits ...**...
        bits ...**...
        bits ...**...
        bits *****...
        bits *****...
        bits ...**...
        bits ...**...
        bits ...**...

; 116 ($74)
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......
        bits **......

; 117 ($75)
        bits ***.....
        bits ***.....
        bits ***.....
        bits ***.....
        bits ***.....
        bits ***.....
        bits ***.....
        bits ***.....

; 118 ($76)
        bits .....***
        bits .....***
        bits .....***
        bits .....***
        bits .....***
        bits .....***
        bits .....***
        bits .....***

; 119 ($77)
        bits ********
        bits ********
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........

; 120 ($78)
        bits ********
        bits ********
        bits ********
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........

; 121 ($79)
        bits ........
        bits ........
        bits ........
        bits ........
        bits ........
        bits ********
        bits ********
        bits ********

; 122 ($7a)
        bits .......*
        bits ......**
        bits .....**.
        bits .**.**..
        bits .****...
        bits .***....
        bits .**.....
        bits ........

; 123 ($7b)
        bits ........
        bits ........
        bits ........
        bits ........
        bits ****....
        bits ****....
        bits ****....
        bits ****....

; 124 ($7c)
        bits ....****
        bits ....****
        bits ....****
        bits ....****
        bits ........
        bits ........
        bits ........
        bits ........

; 125 ($7d) box corner
        bits ...**...
        bits ...**...
        bits ...**...
        bits *****...
        bits *****...
        bits ........
        bits ........
        bits ........

; 126 ($7e)
        bits ****....
        bits ****....
        bits ****....
        bits ****....
        bits ........
        bits ........
        bits ........
        bits ........

; 127 ($7f)
        bits ****....
        bits ****....
        bits ****....
        bits ****....
        bits ....****
        bits ....****
        bits ....****
        bits ....****

; 128 ($80)
        bits **....**
        bits *..**..*
        bits *..*...*
        bits *..*...*
        bits *..*****
        bits *..**..*
        bits **....**
        bits ********

; 129 ($81)
        bits ********
        bits ********
        bits *....***
        bits ***...**
        bits *.....**
        bits ...*..**
        bits *......*
        bits ********

; 130 ($82)
        bits ..******
        bits *..*****
        bits *..*****
        bits *.....**
        bits *..**..*
        bits *..**..*
        bits *.....**
        bits ********

; 131 ($83)
        bits ********
        bits ********
        bits **....**
        bits *..**..*
        bits *..*****
        bits *..**..*
        bits **....**
        bits ********

; 132 ($84)
        bits *****..*
        bits ****..**
        bits ****..**
        bits *.....**
        bits ..**..**
        bits ..**..**
        bits *.....**
        bits ********

; 133 ($85)
        bits ********
        bits ********
        bits **....**
        bits *..**..*
        bits *......*
        bits *..*****
        bits **....**
        bits ********

; 134 ($86)
        bits ********
        bits ****...*
        bits ***..***
        bits **.....*
        bits ***..***
        bits ***..***
        bits **..****
        bits ********

; 135 ($87)
        bits ********
        bits ********
        bits **.....*
        bits *..**..*
        bits *..**..*
        bits **.....*
        bits *****..*
        bits *.....**

; 136 ($88)
        bits ..******
        bits *..*****
        bits *..*****
        bits *.....**
        bits *..**..*
        bits *..**..*
        bits ..***..*
        bits ********

; 137 ($89)
        bits **..****
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ****..**
        bits ********

; 138 ($8a)
        bits ********
        bits *****..*
        bits ********
        bits ****...*
        bits *****..*
        bits **..*..*
        bits *..**..*
        bits **....**

; 139 ($8b)
        bits ..******
        bits *..*****
        bits *..**..*
        bits *..*..**
        bits *....***
        bits *..*..**
        bits ..***..*
        bits ********

; 140 ($8c)
        bits ********
        bits **...***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits **....**
        bits ********

; 141 ($8d)
        bits ********
        bits ********
        bits ..***..*
        bits ...*...*
        bits .......*
        bits ..*.*..*
        bits ..***..*
        bits ********

; 142 ($8e)
        bits ********
        bits ********
        bits ......**
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits ..***..*
        bits ********

; 143 ($8f)
        bits ********
        bits ********
        bits **....**
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits **....**
        bits ********

; 144 ($90)
        bits ********
        bits ********
        bits *.....**
        bits *..**..*
        bits *..**..*
        bits *.....**
        bits *..*****
        bits ..******

; 145 ($91)
        bits ********
        bits ********
        bits *.....**
        bits ..**..**
        bits ..**..**
        bits *.....**
        bits ****..**
        bits *****..*

; 146 ($92)
        bits ********
        bits ********
        bits *..*..**
        bits *....***
        bits *..*****
        bits *..*****
        bits ..******
        bits ********

; 147 ($93)
        bits ********
        bits ********
        bits **....**
        bits *...****
        bits **....**
        bits ****...*
        bits **....**
        bits ********

; 148 ($94)
        bits **..****
        bits ***..***
        bits *......*
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ****..**

; 149 ($95)
        bits ********
        bits ********
        bits ..***..*
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits **.....*
        bits ********

; 150 ($96)
        bits ********
        bits ********
        bits ..***..*
        bits *..*..**
        bits *..*..**
        bits **...***
        bits ***.****
        bits ********

; 151 ($97)
        bits ********
        bits ********
        bits .*****.*
        bits ..*.*..*
        bits *.....**
        bits *.....**
        bits *..*..**
        bits ********

; 152 ($98)
        bits ********
        bits ********
        bits *..**..*
        bits *......*
        bits ***..***
        bits *......*
        bits *..**..*
        bits ********

; 153 ($99)
        bits ********
        bits ********
        bits ..***..*
        bits *..**..*
        bits *..**..*
        bits **.....*
        bits ****..**
        bits **...***

; 154 ($9a)
        bits ********
        bits ********
        bits *......*
        bits *..*..**
        bits ***..***
        bits **..*..*
        bits *......*
        bits ********

; 155 ($9b)
        bits **....**
        bits **..****
        bits **..****
        bits **..****
        bits **..****
        bits **..****
        bits **....**
        bits ********

; 156 ($9c)
        bits ***...**
        bits **.**..*
        bits **.*****
        bits *....***
        bits **.***.*
        bits *.****.*
        bits ......**
        bits ********

; 157 ($9d)
        bits **....**
        bits ****..**
        bits ****..**
        bits ****..**
        bits ****..**
        bits ****..**
        bits **....**
        bits ********

; 158 ($9e)
        bits ********
        bits ***..***
        bits **....**
        bits *......*
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***

; 159 ($9f)
        bits ********
        bits ***.****
        bits **..****
        bits *.......
        bits *.......
        bits **..****
        bits ***.****
        bits ********

; 160 ($a0)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********

; 161 ($a1)
        bits ********
        bits **....**
        bits ***..***
        bits ***..***
        bits ********
        bits ***..***
        bits ***..***
        bits ********

; 162 ($a2)
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********

; 163 ($a3)
        bits *..**..*
        bits *..**..*
        bits ........
        bits *..**..*
        bits ........
        bits *..**..*
        bits *..**..*
        bits ********

; 164 ($a4)
        bits ***..***
        bits **.....*
        bits *..*****
        bits **....**
        bits *****..*
        bits *.....**
        bits ***..***
        bits ********

; 165 ($a5)
        bits *..***.*
        bits *..**..*
        bits ****..**
        bits ***..***
        bits **..****
        bits *..**..*
        bits *.***..*
        bits ********

; 166 ($a6)
        bits **....**
        bits *..**..*
        bits **....**
        bits **...***
        bits *..**...
        bits *..**..*
        bits **......
        bits ********

; 167 ($a7)
        bits *****..*
        bits ****..**
        bits ***..***
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********

; 168 ($a8)
        bits ****..**
        bits ***..***
        bits **..****
        bits **..****
        bits **..****
        bits ***..***
        bits ****..**
        bits ********

; 169 ($a9)
        bits **..****
        bits ***..***
        bits ****..**
        bits ****..**
        bits ****..**
        bits ***..***
        bits **..****
        bits ********

; 170 ($aa)
        bits ********
        bits *..**..*
        bits **....**
        bits ........
        bits **....**
        bits *..**..*
        bits ********
        bits ********

; 171 ($ab)
        bits ********
        bits ***..***
        bits ***..***
        bits *......*
        bits ***..***
        bits ***..***
        bits ********
        bits ********

; 172 ($ac)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ***..***
        bits ***..***
        bits **..****

; 173 ($ad)
        bits ********
        bits ********
        bits ********
        bits *......*
        bits ********
        bits ********
        bits ********
        bits ********

; 174 ($ae)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ***..***
        bits ***..***
        bits ********

; 175 ($af)
        bits ********
        bits ******..
        bits *****..*
        bits ****..**
        bits ***..***
        bits **..****
        bits *..*****
        bits ********

; 176 ($b0)
        bits **...***
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits **...***
        bits ********

; 177 ($b1)
        bits ***..***
        bits **...***
        bits .....***
        bits ***..***
        bits ***..***
        bits ***..***
        bits **....**
        bits ********

; 178 ($b2)
        bits *....***
        bits ..**..**
        bits ..**..**
        bits **...***
        bits *..*****
        bits ..**..**
        bits ......**
        bits ********

; 179 ($b3)
        bits **....**
        bits *..**..*
        bits *..**..*
        bits ****..**
        bits *..**..*
        bits *..**..*
        bits **....**
        bits ********

; 180 ($b4)
        bits ****..**
        bits ***...**
        bits *.....**
        bits ..**..**
        bits .......*
        bits ****..**
        bits ***....*
        bits ********

; 181 ($b5)
        bits *......*
        bits *..*****
        bits *.....**
        bits *****..*
        bits **..*..*
        bits *..**..*
        bits **....**
        bits ********

; 182 ($b6)
        bits **....**
        bits *..**..*
        bits ..******
        bits ......**
        bits ...**..*
        bits *..**..*
        bits **....**
        bits ********

; 183 ($b7)
        bits *......*
        bits ..***..*
        bits ****..**
        bits ***..***
        bits ***..***
        bits ***..***
        bits ****..**
        bits ********

; 184 ($b8)
        bits *....***
        bits ..**..**
        bits ..**..**
        bits *.....**
        bits ****..**
        bits ..**..**
        bits *....***
        bits ********

; 185 ($b9)
        bits **....**
        bits *..**..*
        bits *..**..*
        bits **.....*
        bits *****..*
        bits *..**..*
        bits **....**
        bits ********

; 186 ($ba)
        bits ********
        bits ********
        bits ***..***
        bits ********
        bits ********
        bits ***..***
        bits ********
        bits ********

; 187 ($bb)
        bits ********
        bits ********
        bits ***..***
        bits ********
        bits ********
        bits ***..***
        bits ***..***
        bits **..****

; 188 ($bc)
        bits ****...*
        bits ***..***
        bits **..****
        bits *..*****
        bits **..****
        bits ***..***
        bits ****...*
        bits ********

; 189 ($bd)
        bits ********
        bits ********
        bits *......*
        bits ********
        bits *......*
        bits ********
        bits ********
        bits ********

; 190 ($be)
        bits *...****
        bits ***..***
        bits ****..**
        bits *****..*
        bits ****..**
        bits ***..***
        bits *...****
        bits ********

; 191 ($bf)
        bits **....**
        bits *..**..*
        bits **..*..*
        bits ****..**
        bits ***..***
        bits ********
        bits ***..***
        bits ********

; 192 ($c0)
        bits ********
        bits ********
        bits ********
        bits ........
        bits ........
        bits ********
        bits ********
        bits ********

; 193 ($c1)
        bits ***..***
        bits **....**
        bits *..**..*
        bits *..**..*
        bits *......*
        bits *..**..*
        bits ..****..
        bits ********

; 194 ($c2)
        bits ......**
        bits ...**..*
        bits *..**..*
        bits *.....**
        bits *..**..*
        bits ...**..*
        bits ......**
        bits ********

; 195 ($c3)
        bits **....**
        bits *..**..*
        bits ..***..*
        bits ..******
        bits ..***..*
        bits *..**..*
        bits **....**
        bits ********

; 196 ($c4)
        bits .....***
        bits *..*..**
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits *..*..**
        bits .....***
        bits ********

; 197 ($c5)
        bits ......**
        bits *..**..*
        bits *..*****
        bits *....***
        bits *..*****
        bits *..**..*
        bits ......**
        bits ********

; 198 ($c6)
        bits ......**
        bits *..**..*
        bits *..*****
        bits *....***
        bits *..*****
        bits *..*****
        bits ....****
        bits ********

; 199 ($c7)
        bits **....**
        bits *..**..*
        bits *..*****
        bits *..*...*
        bits *..**..*
        bits *..**..*
        bits **.....*
        bits ********

; 200 ($c8)
        bits ..****..
        bits *..**..*
        bits *..**..*
        bits *......*
        bits *..**..*
        bits *..**..*
        bits ..****..
        bits ********

; 201 ($c9)
        bits **....**
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits **....**
        bits ********

; 202 ($ca)
        bits ***....*
        bits ****..**
        bits ****..**
        bits ****..**
        bits *..*..**
        bits *..*..**
        bits **...***
        bits ********

; 203 ($cb)
        bits ..***..*
        bits ...*..**
        bits *....***
        bits *...****
        bits *....***
        bits ...*..**
        bits ..***..*
        bits ********

; 204 ($cc)
        bits ..******
        bits *..*****
        bits *..*****
        bits *..*****
        bits *..*..**
        bits *..**..*
        bits *......*
        bits ********

; 205 ($cd)
        bits .*****.*
        bits ..***..*
        bits ...*...*
        bits .......*
        bits ..*.*..*
        bits ..***..*
        bits ..***..*
        bits ********

; 206 ($ce)
        bits *..**..*
        bits *...*..*
        bits *......*
        bits *......*
        bits *..*...*
        bits *..**..*
        bits *..**..*
        bits ********

; 207 ($cf)
        bits **....**
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits **....**
        bits ********

; 208 ($d0)
        bits ......**
        bits *..**..*
        bits *..**..*
        bits *.....**
        bits *..*****
        bits *..*****
        bits ....****
        bits ********

; 209 ($d1)
        bits **....**
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits **....**
        bits ***....*
        bits ********

; 210 ($d2)
        bits ......**
        bits *..**..*
        bits *..**..*
        bits *.....**
        bits *..*..**
        bits *..*..**
        bits ...*...*
        bits ********

; 211 ($d3)
        bits **.....*
        bits *...*..*
        bits *...****
        bits **....**
        bits ****...*
        bits *..*...*
        bits *.....**
        bits ********

; 212 ($d4)
        bits *......*
        bits *.*..*.*
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits **....**
        bits ********

; 213 ($d5)
        bits ..***..*
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits **...***
        bits ********

; 214 ($d6)
        bits ..***..*
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits *..*..**
        bits **...***
        bits ***.****
        bits ********

; 215 ($d7)
        bits ..***..*
        bits ..***..*
        bits ..*.*..*
        bits .......*
        bits .......*
        bits ...*...*
        bits ..***..*
        bits ********

; 216 ($d8)
        bits ..***..*
        bits *..*..**
        bits **...***
        bits **...***
        bits **...***
        bits *..*..**
        bits ..***..*
        bits ********

; 217 ($d9)
        bits *..**..*
        bits *..**..*
        bits *..**..*
        bits **....**
        bits ***..***
        bits ***..***
        bits **....**
        bits ********

; 218 ($da)
        bits *......*
        bits *..**..*
        bits ****..**
        bits ***..***
        bits **..****
        bits *..**..*
        bits *......*
        bits ********

; 219 ($db)
        bits ***..***
        bits ***..***
        bits ***..***
        bits ........
        bits ........
        bits ***..***
        bits ***..***
        bits ***..***

; 220 ($dc)
        bits ..******
        bits ..******
        bits **..****
        bits **..****
        bits ..******
        bits ..******
        bits **..****
        bits **..****

; 221 ($dd)
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***..***

; 222 ($de)
        bits **..**..
        bits **..**..
        bits ..**..**
        bits ..**..**
        bits **..**..
        bits **..**..
        bits ..**..**
        bits ..**..**

; 223 ($df)
        bits ........
        bits *.......
        bits **......
        bits ***.....
        bits ****....
        bits *****...
        bits ******..
        bits *******.

; 224 ($e0)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits *..**..*
        bits *..**..*
        bits **....**

; 225 ($e1)
        bits ....****
        bits ....****
        bits ....****
        bits ....****
        bits ....****
        bits ....****
        bits ....****
        bits ....****

; 226 ($e2)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ........
        bits ........
        bits ........
        bits ........

; 227 ($e3)
        bits ........
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********

; 228 ($e4)
        bits ********
        bits ********
        bits ********
        bits ***..***
        bits ********
        bits ********
        bits ********
        bits ********

; 229 ($e5)
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******

; 230 ($e6)
        bits ..**..**
        bits ..**..**
        bits **..**..
        bits **..**..
        bits ..**..**
        bits ..**..**
        bits **..**..
        bits **..**..

; 231 ($e7)
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..

; 232 ($e8)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ..**..**
        bits ..**..**
        bits **..**..
        bits **..**..

; 233 ($e9)
        bits ........
        bits .......*
        bits ......**
        bits .....***
        bits ....****
        bits ...*****
        bits ..******
        bits .*******

; 234 ($ea)
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..
        bits ******..

; 235 ($eb)
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***.....
        bits ***.....
        bits ***..***
        bits ***..***
        bits ***..***

; 236 ($ec)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ****....
        bits ****....
        bits ****....
        bits ****....

; 237 ($ed)
        bits ***..***
        bits ***..***
        bits ***..***
        bits ***.....
        bits ***.....
        bits ********
        bits ********
        bits ********

; 238 ($ee)
        bits ********
        bits ********
        bits ********
        bits .....***
        bits .....***
        bits ***..***
        bits ***..***
        bits ***..***

; 239 ($ef)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ........
        bits ........

; 240 ($f0)
        bits ********
        bits ********
        bits ********
        bits ***.....
        bits ***.....
        bits ***..***
        bits ***..***
        bits ***..***

; 241 ($f1)
        bits ***..***
        bits ***..***
        bits ***..***
        bits ........
        bits ........
        bits ********
        bits ********
        bits ********

; 242 ($f2)
        bits ********
        bits ********
        bits ********
        bits ........
        bits ........
        bits ***..***
        bits ***..***
        bits ***..***

; 243 ($f3)
        bits ***..***
        bits ***..***
        bits ***..***
        bits .....***
        bits .....***
        bits ***..***
        bits ***..***
        bits ***..***

; 244 ($f4)
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******
        bits ..******

; 245 ($f5)
        bits ...*****
        bits ...*****
        bits ...*****
        bits ...*****
        bits ...*****
        bits ...*****
        bits ...*****
        bits ...*****

; 246 ($f6)
        bits *****...
        bits *****...
        bits *****...
        bits *****...
        bits *****...
        bits *****...
        bits *****...
        bits *****...

; 247 ($f7)
        bits ........
        bits ........
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********

; 248 ($f8)
        bits ........
        bits ........
        bits ........
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********

; 249 ($f9)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ********
        bits ........
        bits ........
        bits ........

; 250 ($fa)
        bits *******.
        bits ******..
        bits *****..*
        bits *..*..**
        bits *....***
        bits *...****
        bits *..*****
        bits ********

; 251 ($fb)
        bits ********
        bits ********
        bits ********
        bits ********
        bits ....****
        bits ....****
        bits ....****
        bits ....****

; 252 ($fc)
        bits ****....
        bits ****....
        bits ****....
        bits ****....
        bits ********
        bits ********
        bits ********
        bits ********

; 253 ($fd)
        bits ***..***
        bits ***..***
        bits ***..***
        bits .....***
        bits .....***
        bits ********
        bits ********
        bits ********

; 254 ($fe)
        bits ....****
        bits ....****
        bits ....****
        bits ....****
        bits ********
        bits ********
        bits ********
        bits ********

; 255 ($ff)
        bits ....****
        bits ....****
        bits ....****
        bits ....****
        bits ****....
        bits ****....
        bits ****....
        bits ****....

