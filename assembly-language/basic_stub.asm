; BASIC stub to start assembly program
        orig $0801
; basic "sys" line:
        word line_link
        word 10		; line number
        byte $9e        ; sys token
        ascii "2061"
        byte $00	; end of line
line_link:
        word $00
