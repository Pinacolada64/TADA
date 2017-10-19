setlocal

rem pina is to blame for this:
rem latest bungling: 11/Jan/2015 14:48

set output_path=\TADA-svn\pinacolada\TADA\text-listings\includes
set filename=build-date_basic.lbl

rem output c64list comment describing {uses:} path:
echo ' {uses:%output_path%\%filename%} > %output_path%\%filename%

rem append build date/time:
echo print "Build date: %date% %time%"	>> %output_path%\%filename%

rem "time /t" and "date /t" output:
rem Sun 01/11/2015
rem 04:12 PM

set output_path=
set filename=

echo Done.

endlocal
