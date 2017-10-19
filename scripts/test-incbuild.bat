rem test-incbuild.bat
set SCRIPTS=C:\TADA-svn\pinacolada\TADA\scripts
if exist %SCRIPTS%\incbuild.bat call %SCRIPTS%\incbuild.bat
echo %errorlevel%
set SCRIPTS=
