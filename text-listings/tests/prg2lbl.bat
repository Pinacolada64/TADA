@echo off
rem this batch file should enumerate through the current directory,
rem converting each *.prg file to a corresponding *.lbl file, using
rem Jeff Hoag's C64LIST.EXE utility
rem
rem written by pinacolada, 2014-02-01, q&d v.0001

set C64LIST=c:\opt\C64List3_03.exe

if exist %C64LIST% goto START

echo C64LIST was not found. It was expected to be in
echo %C64LIST%

goto :FINISH

:START
echo Working...
for %%f in (*.prg) do %C64LIST% %%f -lbl -crunch -ovr

echo Done.
:finish
set C64LIST=
