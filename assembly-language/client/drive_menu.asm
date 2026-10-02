; drive_menu.asm -- DRIVE.MNU, the C64's loadable "Select Drive" popup
; overlay (F5). The popup itself is drive_menu_body.asm, shared with the
; 128 client (which builds it in); this wraps it the way every C64
; overlay is built: constants.asm's jump table, LOADed at OVERLAY_BUF,
; and its own copies of disk.asm and drive_id.asm, since a standalone
; .prg can't reach the resident client's. Split this way (2026-10-01)
; because c64list can't nest {ifdef} blocks, and drive_id.asm's own
; {ifdef: c128} would otherwise sit inside a "C64 only" block here.
{include:constants.asm}

        orig $3800                ; must match OVERLAY_BUF -- see
                                  ; tada-client.asm

{include:drive_menu_body_pp.asm}  ; dm_module_start is its first byte
{include:disk.asm}
{include:drive_id.asm}
