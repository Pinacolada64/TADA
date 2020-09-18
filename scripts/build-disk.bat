rem @echo off
rem this batch file converts *.lbl files into *.prg files
rem and imports them into $OUTPUT_DISK

set BASE_DIR=..
set SCRIPT_DIR=%BASE_DIR%\scripts
set PRG_DIR=%BASE_DIR%\text-listings

set C1541=..\..\GTK3VICE-3.4-win64-r38417\bin\c1541.exe

rem iso-8601 format build date (2020-09-18)
rem 'date /t' outputs "Fri 09/18/2020"
rem source: 'help set': %PATH:~10,5%

rem 2nd iteration picks up on CR output by `date` command
set BuildDate=
for /f "skip=1" %%x in ('wmic os get localdatetime') do if not defined BuildDate set BuildDate=%%x
echo BuildDate=%BuildDate:~0,4%-%BuildDate:~4,2%-%BuildDate:~6,2%
goto :EOF

set OUTPUT_DISK=%prg_dir%\"tada %BuildDate%.d81"

echo    BASE_DIR = %BASE_DIR%
echo  SCRIPT_DIR = %SCRIPT_DIR%
echo     PRG_DIR = %PRG_DIR%
echo OUTPUT_DISK = %OUTPUT_DISK%
rem  goto eof

cd %script_dir%
if exist build-ml-c500.bat call build-ml-c500.bat
if exist build-main.bat call build-main.bat

cd %PRG_DIR%

rem create blank .d81:
rem format <diskname,id> [<type> <imagename>] [<unit>]
%c1541% -format test,01 d81 %OUTPUT_DISK%

rem TODO: add make-* PRG files
rem TODO: add SEQ files

for %%A in (*.lbl) do (
	echo ^>^>^> %%A
	rem convert .lbl file to .prg file:
	call %SCRIPT_DIR%\build-bas.bat "%%A.lbl"
	rem change "_" to "." in c64 filenames:
	rem set c64file_basename="%A:_=.%"

	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
	call %SCRIPT_DIR%\add2d64.bat %OUTPUT_DISK% "%%~dpnA.prg"
	)

rem now add misc. support files:
cd %BASE_DIR%\assembly-language

for %%A in ("trace 033c.prg" "si 9900.prg" "modbasic c000 v2.prg" "ml c500.prg" "sas c900.prg" "wrap.reloc.prg") do (
	echo ^>^>^> %%A

	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
	call %script_dir%\add2d64.bat %OUTPUT_DISK% "%%~dpnA.prg"
	)

rem now add make* files:
cd %PRG_DIR%\installers

for %%A in ("make*.prg") do (
	echo ^>^>^> %%A

	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
	call %script_dir%\add2d64.bat %OUTPUT_DISK% "%%~dpnA.prg"
	)

:EOF
cd %script_dir%
echo [%0]: Done.
