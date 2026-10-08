; constants_128.asm -- keymap_menu_128.asm's view of its host,
; client-128.asm; the 128 counterpart of the C64 overlay's constants.asm.
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

; Modifier bits the editor captures: SHIFT 1, C= 2, CTRL 4, ALT 8 ($d3).
KM_MOD_MASK                  = 15

; config_settings' layout (keymap_128.asm's block after keymap_table,
; saved in TADA128.CFG) -- the same offsets as constants.asm's copies
; for the C64's TADA64.CFG; see those for what each byte means.
CONFIG_VERSION       = 1
CFG_VERSION          = 0
CFG_DATA_DRIVE       = 1
; +2 is the C64's CFG_BORDER_STYLE -- kept, never read here. The two
; after it are 128-only (Video Settings in 80 columns, video_menu_128.asm;
; reserved/zero in TADA64.CFG): the input cursor, 0 = Soft (input_
; editor.asm's reverse video -- also what older TADA128.CFG files hold),
; 1 = the VDC's Block cursor, 2 = its Line; and that cursor's blink, 0 =
; Slow (the editor's own default), 1 = Fast, 2 = Solid.
CFG_VDC_SHAPE        = 3
CFG_VDC_FLASH        = 4
CONFIG_SETTINGS_SIZE = 8
