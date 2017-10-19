@echo off
rem test tilde expansion

rem filename is test.lbl

rem "help set" gives more info about expansion

set filename=test.lbl

rem http://stackoverflow.com/questions/636381/what-is-the-best-way-to-do-a-substring-in-a-batch-file/636391#636391
rem %var:~0,-4% would extract all characters except the last four 
rem which would also rid you of the file extension (assuming three 
rem characters after the .).

echo 1: %filename%
echo 2: %filename:~0,-4% (no extension)
echo 3: %filename:~0,-3%prg

rem create new filename with base fiename + new extension
set new_filename=%filename:~0,-3%prg

echo %new_filename%

set filename=
set new_filename=
