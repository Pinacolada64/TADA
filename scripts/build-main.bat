rem compile t_main into t.main.prg (and save labels for use by other modules)
rem v0.3, may 16th, 2014
rem v0.4, jan 11th, 2015
rem v0.5, feb 18th, 2016
rem - changed label-assignments-header.lbl to quoter-assignments.lbl
rem v0.6, aug 21st, 2020
rem - updated paths, c64list4.03, add2d64.bat, %OUTPUT_DISK% for c1541

echo [%0]:
cd %PRG_DIR%
echo %cd%

rem by pinacolada

set T_MAIN=%prg_dir%\t_main.lbl

rem check if the file exists:
if not exist %T_MAIN% goto :FINISH
%C64LIST% %T_MAIN% -crunch -prg:t_main.prg -verbose -ovr -alpha:alt

rem error occurred:
if not ERRORLEVEL 0 goto :FINISH

rem increment build number:
if exist %SCRIPT_DIR%\incbuild.bat call %SCRIPT_DIR%\incbuild.bat

rem v0.4: this prints a line telling when the file was compiled:
rem C64List4.03 achieves this with {usedef:__BuildDate} and {usedef:__BuildTime}
rem if exist %prefix%\scripts\build-date_basic.bat call %prefix%\scripts\build-date_basic.bat

rem start fresh label assignments file:
rem 1) include label-assignments-header.lbl
rem 2) collect labels from t_main.lbl for use by other modules
rem thanks to goog for undocumented "-labels" switch for c64list

rem  /y switch: suppress "overwrite existing file?" prompt:
copy /y %PRG_DIR%\includes\quoter-assignments.lbl %PRG_DIR%\includes\label-assignments.lbl
rem append labels from t_main.lbl (which are used in most other
rem t.*.lbl programs) to label-assignments.lbl:
%C64LIST% %T_MAIN% -labels >> %PRG_DIR%\includes\label-assignments.lbl

:ADD2D64
if exist %SCRIPT_DIR%\add2d64.bat call %SCRIPT_DIR%\add2d64.bat %OUTPUT_DISK% %PRG_DIR%\t_main.prg

:FINISH
rem clean up after ourselves:
set T_MAIN=

echo Remember to delete the header, assigns between {:1} and {:999}, and footer.
