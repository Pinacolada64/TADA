echo [%0]:

REM agentfriday: echo [asm]>inc.asm
REM agentfriday: type sym.txt>>inc.asm
REM agentfriday: echo [endasm]>>inc.asm

rem must combine -prg and -sym, otherwise errors occur

%C64LIST% "%ASM_DIR%\ml c500.asm" -prg -ovr -sym:"%ASM_DIR%\ml-c500.sym"

call %SCRIPT_DIR%\add2d64.bat %OUTPUT_DISK% "%ASM_DIR%\ml c500.prg"
