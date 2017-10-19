set PREFIX=\TADA-svn\pinacolada\TADA

set DISKIMAGE=%prefix%\text-listings\module-batch-disk.d81

cd %PREFIX%\assembly-language

REM agentfriday: echo [asm]>inc.asm
REM agentfriday: type sym.txt>>inc.asm
REM agentfriday: echo [endasm]>>inc.asm

rem must combine -prg and -sym, otherwise errors occur
casm "ml c500.lbl" -prg -sym:"ml-c500-sym.lbl" -ovr

rem wrap "ml-c500-sym.lbl" file in {asm} and {endasm} tags

echo {asm} > "ml-c500-symbols.lbl"

type "ml-c500-sym.lbl" >> "ml-c500-symbols.lbl"

echo {endasm} >> "ml-c500-symbols.lbl"

rem del ml-c500-sym.lbl

call add2d64-test.bat %DISKIMAGE% "ml c500.prg"
