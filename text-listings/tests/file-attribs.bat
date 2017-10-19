rem @echo off
rem test what %~a1 expands to -- file attributes property

rem shorten prompt to > (restored after script ends)
set OLD_PROMPT=%PROMPT%
set PROMPT=$G

set STDERR=2

if not %1. == . goto check_exist
:usage
echo %0 - Check %%~a1 tilde expansion functionality.
echo Supply an existing filename as a parameter.
goto :finish

:check_exist
if exist %1 goto start
echo Missing file %1. Aborted.
goto finish

:start
set FILE_INFO=%~a1
echo %FILE_INFO%
rem goto :finish

:finish
rem clean up after ourselves:

rem set STDERR=
rem set FILE_INFO=

rem restore original prompt:
set PROMPT=%OLD_PROMPT%
set OLD_PROMPT=

rem we'll do it the hard way, directory (o)rdered by (-)largest (s)ize
rem (b)are is used to prevent date/time from being displayed
rem listing JUST the largest file would be cool

dir *.prg /b /o-s
