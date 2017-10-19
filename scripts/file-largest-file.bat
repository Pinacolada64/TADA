rem find largest size .prg file (excluding t_main.prg itself)

rem https://stackoverflow.com/questions/12792706/windows-batch-script-to-copy-largest-file-and-by-pattern

rem capture only filenames (/bare), sort largest to smallest (/o-s)
rem dir /b /o-s

setlocal enabledelayedexpansion enableextensions

@echo off

rem file size:
set largest=

rem filename:
set largestname=
set /a largestsize=0

rem first, find largest file size (should be t_main.prg):
for %%a in (*.prg) do (
  if %%~za gtr !largestsize! (
    set largest=%%a
    set largestname=%%~na
    set /a largestsize=%%~za
  )
)
goto :largest

rem skip this
set match=
for %%a in (*.log) do (
  if %%~na==!largestname! (
    set match=%%a
  )
)

:largest
echo "!largest!" %destfolder%
echo "!match!" %destfolder%
endlocal