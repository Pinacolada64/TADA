; constants_128.asm -- keymap_menu.asm's view of its host when it's built
; into client-128.asm instead of loaded as the C64 client's KEYMAP.ED
; overlay. The Makefile's keymap_menu_128.asm rule swaps this in for
; constants.asm (the only other change it makes is dropping the overlay's
; `orig`), so the popup's source stays shared with the C64 client.
;
; The JT_* names are NOT defined here: on the C64 they're fixed jump-
; table addresses at $c000, which is ROM on the 128. keymap_host_128.asm
; defines each one as a real label (JT_SAVE_SCREEN: ...) instead, and
; KEYMAP_TABLE_PTR likewise lives in keymap_128.asm as a label -- labels
; can be referenced before they're defined, `=` constants can't, and
; these are only ever referenced.

; Live keyboard state the popup reads (see constants.asm's copies for the
; C64 values). $d3/$d4 per Compute's 128 Programmer's Guide's zero-page
; map, and the editor ROM's own SCNKEY ($C636: ldx $d4 / $C651: ldy $d4).
; Key numbers 0-63 are the same physical keys as the C64's; 64-87 are the
; 128's extra keys (keypad, HELP, ESC, TAB, ALT, LINE FEED, the top-row
; arrows, NO SCROLL), and 88 means nothing is held.
KM_SHFLAG                    = $d3
KM_SFDX                      = $d4
KM_KEY_NONE                  = 88
