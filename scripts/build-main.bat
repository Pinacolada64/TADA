rem compile t_main into t.main.prg (and save labels for use by other modules)
rem v0.3, may 16th, 2014
rem v0.4, jan 11th, 2015
rem v0.5, feb 18th, 2016
rem - changed label-assignments-header.lbl to quoter-assignments.lbl

rem by pinacolada

set C64LIST=\opt\C64List3_03.exe
set PREFIX=\TADA-svn\pinacolada\TADA
set T_MAIN=%PREFIX%\text-listings\t_main.lbl

rem check if the file exists:
if not exist %T_MAIN% goto :FINISH
%C64LIST% %T_MAIN% -crunch -prg:t_main.prg -verbose -ovr

rem error occurred:
if not ERRORLEVEL 0 goto :FINISH

rem increment build number:
if exist %prefix%\scripts\incbuild.bat call %prefix%\scripts\incbuild.bat

rem v0.4: this prints a line telling when the file was compiled:
if exist %prefix%\scripts\build-date_basic.bat call %prefix%\scripts\build-date_basic.bat

rem start fresh label assignments file:
rem 1) include label-assignments-header.lbl
rem 2) collect labels from t_main.lbl for use by other modules
rem thanks to goog for undocumented "-labels" switch for c64list

rem  /y switch: suppress "overwrite existing file?" prompt:
copy /y %PREFIX%\text-listings\includes\quoter-assignments.lbl %PREFIX%\text-listings\includes\label-assignments.lbl
rem append labels from t_main.lbl (which are used in most other
rem t.*.lbl programs) to label-assignments.lbl:
%C64LIST% %T_MAIN% -labels >> %PREFIX%\text-listings\includes\label-assignments.lbl

:ADD2D64
if exist %prefix%\scripts\add2d64-test.bat call %prefix%\scripts\add2d64-test.bat %prefix%\text-listings\module-batch-disk.d81 %prefix%\text-listings\t_main.prg
echo [add2d64-test.bat]: errorlevel %errorlevel%

:FINISH
rem clean up after ourselves:
set C64LIST=
set PREFIX=
set T_MAIN=

echo Remember to delete the header, assigns between {:1} and {:999}, and footer.
