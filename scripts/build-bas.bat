setlocal

rem build-bas.bat
rem a quick hack for your disgust
rem last modified 23/Jan/2015 11:59

rem this batch file compiles "sub-modules" for TADA
rem (anything other than t.main)

echo [%0]:

set prefix=..
set scripts=..\scripts
set text_listings=..\text-listings
set filename=%1

rem strip out path:
rem and extension:
rem set base_filename=%base_filename:~0,-5%.prg

rem (cuz add2d64.bat won't take a full path to .prg file)

rem set new_filename=%filename:~0,-4%.prg

rem 1st parameter should be a .lbl file or we're in trouble
rem base_filename=%1:~0,-4% <- not allowed

rem compile using c64list...
rem the lbl file should {include:build-date_basic.lbl}
%c64list% %filename% -alpha:alt -crunch -prg -verbose -ovr
rem > %base_filename%.log

:ADD2D64
rem if exist %scripts%\add2d64.bat 
rem echo  base_filename: %base_filename%
rem in variable expansion below: ~dpnF.prg = d: drive, p: path, n: filename (no extension), .prg

for %%F in (%filename%) do (
call %scripts%\add2d64.bat %text_listings%\%OUTPUT_DISK% "%%~dpnF.prg"
if not errorlevel 0 echo [%0]: %errorlevel% >&2
)

REM set prefix=
REM set filename=
REM set base_filename=

endlocal
