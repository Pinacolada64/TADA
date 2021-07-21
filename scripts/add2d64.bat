@echo off
echo [%0]:
setlocal

rem add2d64.bat

rem based on a batch file to add a .prg file to a d64 disk image
rem original by Bill Buckels 2013

rem c1541.exe that comes with winvice must be on-path
rem this disk must be used on a c64 and not on a c128
rem the program is a c64 binary with BASIC startup code

rem modified by pinacolada, 2/Apr/2014 20:49

rem again on 11/Jan/2015 17:51:
rem + cleaner logic
rem + errors output to stderr

rem again on 19/Jan/2015 0:01
rem agentfriday to the rescue after great pscug meeting!
rem + setlocal avoids clobbering % variables % between CALLs
rem + discovered variable expansion happens even in rem statements (!)

rem and again 2/Oct/2015 13:25
rem + handles quoted paths with spaces
rem http://stackoverflow.com/questions/5239291/batch-file-parameter-with-spaces-double-quotes-pipes
rem has a solution to this problem

rem and again 30/Nov/2015 13:07
rem + now removes *.prg extension within disk image
rem + now displays usage if no command line params
rem + now changes _ to . within filenames to be written to disk image
rem http://ss64.com/nt/syntax-replace.html
rem Use the syntax below to edit and replace the characters assigned to a string variable.
rem Syntax
rem      %variable:StrToFind=NewStr%

rem set oldpath=%path%
rem C1541=..\..\GTK3VICE-3.4-win64-r38417\bin\c1541.exe

rem no command line parameters?
rem usually is 'if "%1" == "" goto USAGE' but this barfs if
rem %1 is already enclosed in quotes. thanks, stackoverflow
rem http://stackoverflow.com/questions/26551/how-to-pass-command-line-parameters-in-batch-file
rem also, %~1 may work around quoting parameters

if "%~1" == "" goto USAGE

:FIND_C1541
if exist %C1541% goto CHECK_IMAGE_PARAM
echo C1541.EXE was not found. It was expected to be in >&2
echo %C1541%. >&2
set errorlevel=1
goto :QUIT

:CHECK_IMAGE_PARAM
rem check disk image name parameter:
set diskimage="%~1"
setlocal EnableDelayedExpansion
echo diskimage: !diskimage!

if not "!diskimage!." == "." goto CHECK_IMAGE_EXISTS
echo Missing ^<disk_image.d64^> parameter. >&2
set errorlevel=2
goto :QUIT

:CHECK_IMAGE_EXISTS
if exist !diskimage! goto CHECK_PRG_PARAM
echo Disk image !diskimage! not found. Aborting. >&2
set errorlevel=3
goto :QUIT

:CHECK_PRG_PARAM
setlocal DisableDelayedExpansion

rem ends in .prg extension
set prgfile="%~2"

rem 1) prgfile_basename: %~n2 strips path and file extension from imported .prg file:
set prgfile_basename="%~n2"

rem 2) c64_filename: change "_" to ".":
set c64_filename="%prgfile_basename:_=.%"

rem prgfile_filename_ext: filename.ext
set prgfile_filename_ext="%~nx2"

echo     prgfile_basename: %prgfile_basename%
echo prgfile_filename_ext: %prgfile_filename_ext%
echo              prgfile: %prgfile%
echo         c64_filename: %c64_filename%

setlocal EnableDelayedExpansion

if not %prgfile%. == . goto CHECK_PRG_EXISTS
echo Missing ^<program_file.prg^> parameter. >&2
set errorlevel=4
goto :QUIT

:CHECK_PRG_EXISTS
if exist %prgfile% goto WORK
echo .prg file %prgfile% not found. Aborting. >&2
set errorlevel=5
goto :QUIT

:WORK
rem 1) attach disk image
rem 2) delete existing file from disk image (c64_filename)
rem 3) write new prg file to disk image (with full path + ".prg" extension)

rem the thing to remember here is the following parameters need not be quoted twice:
rem c1541 will throw "wrong number of parameters" errors if so

setlocal EnableDelayedExpansion
echo %c1541% -attach !diskimage! -delete %c64_filename% -write %prgfile% %c64_filename% -dir
     %c1541% -attach !diskimage! -delete %c64_filename% -write %prgfile% %c64_filename% -dir
setlocal DisableDelayedExpansion
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
if not errorlevel 0 echo [%0]: %errorlevel% >&2
set diskimage=
set prgfile=
set prgfile_basename=
set C1541= 

rem 'exit' closes dos window if open
rem also returns control to lbl2prg.bat
rem exit

endlocal
