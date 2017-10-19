rem build-bas.bat
rem a quick hack for your disgust

set script_dir=c:\tada-svn\pinacolada\TADA\scripts

rem this includes BASIC PRINT statement to print date/time of build
rem also compiles using c64list

rem 1st parameter should be a .lbl file or we're in trouble

rem output build date/time to "build-date_basic.lbl":
if exist %script_dir%\build-date_basic.bat call %script_dir%\build-date_basic.bat

rem the lbl file should {include:build-date_basic.lbl}
C:\opt\C64List3_03.exe "%1" -alpha:invert -crunch -prg -verbose -ovr -labels > includes.lbl
rem ~nF1.txt or %filenameroot% in editpad pro

set script_dir=