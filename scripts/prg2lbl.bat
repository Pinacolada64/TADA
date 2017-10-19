@echo off
rem this batch file enumerates through the current directory,
rem converting each {filename}.prg file to a corresponding *.lbl file,
rem logging results to {filename}.log file
rem using Jeff Hoag's C64LIST.EXE utility

rem written by pinacolada, 2016-03-03, q&d v.0001

set C64LIST=\opt\C64List3_03.exe

if exist %C64LIST% goto WORK
rem was DELETE_TEMP_FILES

echo C64LIST was not found. It was expected to be in >&2
echo %C64LIST% >&2
goto :FINISH

:DELETE_TEMP_FILES
echo Working...
echo Deleting all *.prg and *.log files...
del %PREFIX%\*.prg
del %PREFIX%\*.log

:WORK
for %%F in (*.prg) do (
REM which file are we on?
	echo.
	echo %%F

REM call c64list for all *.prg files, output to separate *.log file
rem ("~nF" expands to base filename, minus extension)
rem -prg     create BASIC program file from .lbl file
rem -crunch  remove spaces between BASIC tokens
rem -ovr     overwrite existing file
rem -sym     output symbols for assembly programs (we already have
rem				BASIC labels from \text-listings\includes)
rem -verbose show errors/status, :list - show which line it's working on 

rem		%C64LIST% %%F -lbl -crunch -ovr -sym -verbose:list > %%~nF.log
		%C64LIST% %%F -alpha:upper -lbl -crunch -ovr

rem	if not %errorlevel%==0 echo %errorlevel%
	echo Finished with %%f
	)

:finish
set C64LIST=

echo Done.
