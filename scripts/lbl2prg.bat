@echo off
rem this batch file should enumerate through the %text_listings% directory,
rem converting each {filename}.lbl file to a corresponding *.prg file,
rem logging results to {filename}.log file
rem using Jeff Hoag's C64LIST.EXE utility
rem
rem written by pinacolada, 2014-04-09, q&d v.0001

set C64LIST=\opt\C64List4_03.exe
set C1541=\Program Files\VICE\GTK3VICE-3.4-win64-r37296\c1541.exe
set PREFIX=..
set SCRIPTS=%PREFIX%\scripts

if exist %C64LIST% goto FIND_C1541
rem was DELETE_TEMP_FILES

echo C64LIST was not found. It was expected to be in >&2
echo %C64LIST% >&2
goto :FINISH

:DELETE_TEMP_FILES
echo Deleting all *.prg and *.log files...
del %PREFIX%\*.prg
del %PREFIX%\*.log

:FIND_C1541
if exist %C1541% goto WORK
echo C1541.EXE was not found. It was expected to be in >&2
echo %C1541% >&2
goto :QUIT

:WORK
rem attach disk image, delete existing file, write new prg file
%c1541% -format "module test disk,01" d81 %diskimage%
rem syntax: -format <diskname,id> [<type> <imagename>] [<unit>]
%c1541% -attach "%output_disk%"
rem \ -delete "%prgfile%" -write "%prgfile%" -dir
rem if errorlevel echo %errorlevel%
rem pause
rem goto :QUIT

rem FIXME: i can see a problem here - need to exclude t_main.lbl
rem was (*.lbl)

for %%F in (t_startup.lbl t_ma_bank.lbl) do (
REM which file are we on?
	echo.
	echo %%F

REM call c64list for all *.lbl files, output to separate *.log file
rem ("~nF" expands to base filename, minus extension)
rem -prg     create BASIC program file from .lbl file
rem -crunch  remove spaces between BASIC tokens
rem -ovr     overwrite existing file
rem -sym     output symbols for assembly programs (we already have
rem				BASIC labels from \text-listings\includes)
rem -verbose show errors/status, :list - show which line it's working on 

rem		%C64LIST% %%F -prg -crunch -ovr -sym -verbose:list > %%~nF.log
		%C64LIST% %%F -prg -crunch -ovr

rem	if not %errorlevel%==0 echo %errorlevel%
	rem	if exist %%~nF.prg call %scripts%\add2d64.bat %diskimage% %%~nF.prg
	echo Finished with %%f
	)

:finish
set C64LIST=
set C1541=
set DISKIMAGE=
echo Done.
