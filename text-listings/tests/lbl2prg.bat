@echo off
rem this batch file should enumerate through the current directory,
rem converting each {filename}.lbl file to a corresponding *.prg file,
rem logging results to {filename}.log file
rem using Jeff Hoag's C64LIST.EXE utility
rem
rem written by pinacolada, 2014-04-09, q&d v.0001

set C64LIST=c:\opt\C64List3_03.exe

if exist %C64LIST% goto START

echo C64LIST was not found. It was expected to be in
echo %C64LIST%
goto :FINISH

:START
echo Working...

for %%F in (*.lbl) do (
REM which file are we on?
	echo %%F
REM call c64list for all *.lbl files, output to separate *.log file
rem ("~nF" expands to base filename, minus extension)
rem -prg     create BASIC program file from .lbl file
rem -crunch  remove spaces between BASIC tokens
rem -ovr     overwrite existing file
rem -sym     output symbols for assembly programs (we already have
rem				BASIC labels from \text-listings\includes)
rem -verbose show errors/status, :list - show which line it's working on 
		%C64LIST% %%F -prg -crunch -ovr -sym -verbose:list > %%~nF.log
	if not %errorlevel%==0 echo %errorlevel%
	)

REM hairy example from http://www.robvanderwoude.com/unixports.php#WHICH

REM FOR %%A IN (.;%PathExt%) DO (
REM 	IF "!Found!"=="-None-" (
REM 		FOR %%B IN ("%~1%%~A") DO (
REM 			IF NOT "%%~$SRCH_PATH:B"=="" (
REM 				FOR %%C IN ("%%~$SRCH_PATH:B") DO SET Test=%%~xC
REM 				IF NOT "!Test!"=="" IF NOT "!Test!"=="." (
REM 					ECHO.%%~$SRCH_PATH:B
REM 					IF /I NOT "%~2"=="/A" (
REM 						ENDLOCAL
REM 						GOTO:EOF
REM 					)
REM 				)
REM 			)
REM 		)
REM 	)
REM )
REM 
REM FOR /F "tokens=2 delims=[]" %%A IN ('VER') DO
REM  FOR /F "tokens=2" %%B IN ("%%~A") DO
REM  IF %%B LSS 5.1 GOTO Syntax
REM 
REM FOR /F "tokens=2 delims=[]" %%A IN ('VER') DO FOR /F "tokens=2" %%B IN ("%%~A") DO IF %%B LSS 5.1 GOTO Syntax

echo Done.
:finish
set C64LIST=
