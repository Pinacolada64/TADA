rem @echo off
rem add2d64.bat

rem based on a batch file to add a .prg file to a d64 disk image
rem original by Bill Buckels 2013

rem c1541.exe that comes with winvice must be on-path
rem this disk must be used on a c64 and not on a c128
rem the program is a c64 binary with BASIC startup code

rem modified by pinacolada, 2/Apr/2014 20:49

set oldpath=%path%
rem set C1541=\Program Files\VICE\GTK3VICE-3.4-win64-r37296\c1541.exe

rem no parameters?
rem usually is 'if "%1" == "" goto USAGE' but this barfs if
rem %1 is already enclosed in quotes. thanks, stackoverflow
rem http://stackoverflow.com/questions/26551/how-to-pass-command-line-parameters-in-batch-file
rem also, %~1 may work around quoting parameters
if %~1. == . goto USAGE

:CHECK_DISK_PARAM
rem check disk image name parameter:
%diskimage%=%1
if not %diskimage%. = . goto find_disk
echo Missing ^<disk_image.d64^> parameter.
goto :QUIT

:FIND_DISK
if exist %diskimage% goto CHECK_FILE_PARAM
echo Disk image %diskimage% not found. Aborting.
goto :QUIT

:CHECK_FILE_PARAM
if exist %diskimage% goto CHECK_FILE
echo Disk image %diskimage% not found. Aborting.
goto :QUIT

:FIND_FILE
rem check if program file exists:
%prgfile%=%2
if exist %prgfile% goto FIND_C1541
echo Program %prgfile% not found. Aborting.

:FIND_C1541
if exist %C1541% goto WORK
echo C1541.EXE was not found. It was expected to be in
echo %C1541%
goto :QUIT

:WORK
rem attach disk image, delete existing file, write new prg file
%c1541% -attach "%diskimage%" -delete "%prgfile%" -write "%prgfile%" -dir
if errorlevel echo [%0]: errorlevel %errorlevel%
goto :QUIT

:USAGE
rem must escape < > | ^ symbols with ^ first.
echo.
echo %0 - adds a file to a d64 image, overwriting existing file
echo.
echo syntax: %0 ^<disk_image.d64^> ^<filename.prg^>
echo         (.d64 and .prg extensions are currently required)

:QUIT
rem clean up after ourselves
set diskimage=
set prgfile=
SET C1541= 
set path=%oldpath%
rem exit
