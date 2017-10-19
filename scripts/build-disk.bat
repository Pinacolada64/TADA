@echo on
rem this batch file takes *.lbl files and imports them into "test.d81"

set BASE_DIR=\TADA-svn\pinacolada\TADA
set SCRIPT_DIR=%BASE_DIR%\scripts
set PRG_DIR=%BASE_DIR%\text-listings

set C1541=\opt\c1541.exe
set OUTPUT_DISK=%prg_dir%\test.d81

echo    BASE_DIR = %BASE_DIR%
echo  SCRIPT_DIR = %SCRIPT_DIR%
echo     PRG_DIR = %PRG_DIR%
echo OUTPUT_DISK = %OUTPUT_DISK%
rem goto eof

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
	rem change "_" to "." in filenames:
	set prgfile_basename="%A:_=.%"

	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
	call %SCRIPT_DIR%\add2d64-test.bat %OUTPUT_DISK% "%%~dpnA.prg"
	)

rem now add misc. support files:
cd %BASE_DIR%\assembly-language

for %%A in ("trace 033c.prg" "si 9900.prg" "modbasic c000 v2.prg" "ml c500.prg" "sas c900.prg" "wrap.reloc.prg") do (
	echo ^>^>^> %%A

	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
	call %script_dir%\add2d64-test.bat %OUTPUT_DISK% "%%~dpnA.prg"
	)

rem now add make* files:
cd %PRG_DIR%\installers

for %%A in ("make*.prg") do (
	echo ^>^>^> %%A

	rem in variable expansion below: ~nA.prg = n: filename (no extension), .prg
	call %script_dir%\add2d64-test.bat %OUTPUT_DISK% "%%~dpnA.prg"
	)

:EOF
cd %script_dir%
echo [%0]: Done.
