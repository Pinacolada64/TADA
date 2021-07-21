rem by agentfriday
rem @echo off
goto :MAIN

:INITERRLVL
exit /b 0


:MAIN
REM -- read / increment current build number --
call :INITERRLVL
if exist buildnum.bat call buildnum.bat

set curbuild_tmp=%errorlevel%
set /a curbuild_tmp=curbuild_tmp +1

REM -- write new build# 
echo exit /b %curbuild_tmp% > buildnum.bat

REM -- Generate C64list source file for current build number **ASM VERSION** --
echo {asm}                             > build_num.asm
echo build_nr: ASCII "%curbuild_tmp%" >> build_num.asm
echo {endasm}                         >> build_num.asm

REM -- and BASIC version
echo BN%%= %curbuild_tmp%               > build_num.lbl

echo  %curbuild_tmp%
set curbuild_tmp=

set filename=build-date_basic.lbl
rem pina added this:
rem output c64list comment describing {uses:} path:
echo ' {uses:..\TADA\scripts\%filename%} > %filename%
echo print "%date% %time%"	>> %filename%
set filename=
echo Done.
