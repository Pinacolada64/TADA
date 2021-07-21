rem @echo off
rem this batch file converts *.lbl files into *.prg files
rem and imports them into %OUTPUT_DISK%

set ASM_DIR=..\assembly-language
set PRG_DIR=..\text-listings
set SCRIPT_DIR=..\scripts

set C1541="\Documents\C64\GTK3VICE-3.4-win64-r38417\bin\c1541.exe"
set C64LIST="\Documents\C64\C64List4_03.exe"
set C64LISTFLAGS=-ovr -verbose -crunch

pushd %SCRIPT_DIR%

rem iso-8601 format build date (e.g. 2020-09-18)
rem 'date /t' outputs e.g. "Fri 09/18/2020"
rem source: 'help set': %PATH:~10,5%

rem 2nd iteration picks up on CR output by `date` command
set BuildDate=
for /f "skip=1" %%x in ('wmic os get localdatetime') do if not defined BuildDate set BuildDate=%%x
rem output looks like "2020-09-25"
set BuildDate=%BuildDate:~0,4%-%BuildDate:~4,2%-%BuildDate:~6,2%

set OUTPUT_DISK="%prg_dir%\tada %BuildDate%.d81"

echo      ASM_DIR = %ASM_DIR%
echo     BASE_DIR = %BASE_DIR%
echo    BuildDate = %BuildDate%
echo        C1541 = %c1541%
echo      C64LIST = %C64LIST%
echo C64LISTFLAGS = %C64LISTFLAGS%
echo  OUTPUT_DISK = %OUTPUT_DISK%
echo      PRG_DIR = %PRG_DIR%
echo   SCRIPT_DIR = %SCRIPT_DIR%

cd %PRG_DIR%

rem create blank .d81:
rem format <diskname,id> <type> <imagename>
%c1541% -format "tada %BuildDate%,01" d81 %OUTPUT_DISK% -dir

cd %SCRIPT_DIR%

if exist build-ml-c500.bat call build-ml-c500.bat
if exist build-main.bat call build-main.bat

cd %PRG_DIR%

rem convert .lbl files to .prg files:
for %%A in (boot.lbl) do (
	echo ^>^>^> %%A

rem	call :add_to_1581 %a -- if this ever gets subroutined
	
	rem change "_" to "." in c64 filenames:
	set c64_filename=%A:_=.%
	rem substitute .prg for .lbl file extension 
	set prg_filename=%%A:.prg=.lbl%
	echo %%prg_filename%% = %prg_filename%
	echo %%c64_filename%% = %c64_filename%
	pause
	
	rem convert .lbl file to .prg file:
	%C64LIST% "%%A" %C64LISTFLAGS% -prg:"%prg_filename%"

	rem in variable expansion below: ~dpnA.prg = d: drive, p: path, n: filename (no extension), A: variable, .prg
	rem %c1541% -attach %OUTPUT_DISK% -write "%%~dpnA.prg" "%c64_filename%"
	call %SCRIPT_DIR%\add2d64.bat %OUTPUT_DISK% %prg_filename%
	)

goto :end

rem now add misc. support files:

for %%A in ("trace 033c.prg" "si 9900.prg" "modbasic c000 v2.prg" "ml c500.prg" "sas c900.prg" "wrap.reloc.prg") do (
	echo ^>^>^> %%A

	rem strip .prg suffix:
	set c64_filename=%%A:~0,-4%
	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
rem	%c1541% -attach %OUTPUT_DISK% -write "%%~dpnA.prg" "%c64_filename%"
	call %SCRIPT_DIR%\add2d64.bat %OUTPUT_DISK% %%A
	)

rem TODO: add make-* PRG files
rem TODO: add SEQ files

cd %PRG_DIR%\installers

for %%A in ("make*.prg") do (
	echo ^>^>^> %%A

	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
	%C64LIST% %OUTPUT_DISK% "%%~dpnA.prg"
	%c1541% -attach %OUTPUT_DISK% -del "%c64_filename%" -write %%A "%c64_filename%"
	)

	goto :end

:add_to_1581
	echo :add_to_1581 -- %1
	pause

:end
popd

set ASM_DIR=
set BASE_DIR=
set BuildDate=
set C1541=
set c64_filename=
set C64LIST=
set C64LISTFLAGS=
set OUTPUT_DISK=
set PRG_DIR=
set SCRIPT_DIR=

echo [%0]: Done.
