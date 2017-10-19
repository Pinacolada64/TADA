@ECHO OFF
:: Check for NT4 or later
IF NOT "%OS%"=="Windows_NT" GOTO Syntax
:: Check for XP or later
FOR /F "tokens=2 delims=[]" %%A IN ('VER') DO FOR /F "tokens=2" %%B IN ("%%~A") DO IF %%B LSS 5.1 GOTO Syntax

:: Check command line argument
IF     "%~1"=="" GOTO Syntax
IF NOT "%~2"=="" IF /I NOT "%~2"=="/A" GOTO Syntax
ECHO.%1 | FINDSTR /R /C:"[:\\\*\?,;/]" >NUL && GOTO Syntax

:: If the specified command contains a dot, it is not a macro nor an internal command
ECHO.%1 | FIND "." >NUL && GOTO ExtCmd

:: Check if the command specified is a DOSKEY macro
FOR /F "tokens=1* delims==" %%A IN ('DOSKEY /MACROS 2^>NUL') DO (
	IF /I "%~1"=="%%~A" (
		ECHO.
		ECHO -DOSKEY Macro-
		IF /I NOT "%~2"=="/A" GOTO:EOF
	)
)

:: Next, check if the command specified is an internal command; to do so
:: reliably we need SysInternals' STRINGS; if it isn't available, we'll
:: just check against a list of known internal commands, risking "false
:: positives" in older CMD versions (e.g. MAKELINK does not exist in XP,
:: but without STRINGS.EXE this batch file will still return "-CMD
:: internal command-"; when STRINGS.EXE IS available, the batch file would
:: return "-None-")
FOR %%A IN (APPEND ASSOC BREAK CALL CD CHCP CHDIR CLS COLOR COPY DATE DEL DIR DPATH ECHO ENDLOCAL ERASE EXIT FOR FTYPE GOTO IF KEYS MD MKDIR MKLINK MOVE PATH PAUSE POPD PROMPT PUSHD RD REM REN RENAME RMDIR SET SETLOCAL SHIFT START TIME TITLE TRUENAME TYPE VER VERIFY VOL) DO (
	IF /I "%~1"=="%%~A" (
		STRINGS.EXE /? >NUL 2>&1
		IF ERRORLEVEL 1 (
			REM * * * NOT TESTED :: may return a false positive * * *
			ECHO.
			ECHO -CMD Internal Command-
			IF /I NOT "%~2"=="/A" GOTO:EOF
		) ELSE (
			REM * * * TESTED with STRINGS.EXE :: might still occasionally fail, though * * *
			STRINGS.EXE "%ComSpec%" | FINDSTR.EXE /R /B /I /C:"%~1$" >NUL
			IF NOT ERRORLEVEL 1 (
				ECHO.
				ECHO -CMD Internal Command-
				IF /I NOT "%~2"=="/A" GOTO:EOF
			)
		)
	)
)

:ExtCmd
SETLOCAL ENABLEDELAYEDEXPANSION

:: Search current directory first, then PATH, for the "pure"
:: file name itself or one of the extensions defined in PATHEXT.
:: Add quotes to match directory names with spaces as well.
:: This command line was partly rewritten by David Riemens.
SET SRCH_PATH=.\;%PATH%
SET Found=-None-
FOR %%A IN (.;%PathExt%) DO (
	IF "!Found!"=="-None-" (
		FOR %%B IN ("%~1%%~A") DO (
			IF NOT "%%~$SRCH_PATH:B"=="" (
				FOR %%C IN ("%%~$SRCH_PATH:B") DO SET Test=%%~xC
				IF NOT "!Test!"=="" IF NOT "!Test!"=="." (
					ECHO.%%~$SRCH_PATH:B
					IF /I NOT "%~2"=="/A" (
						ENDLOCAL
						GOTO:EOF
					)
				)
			)
		)
	)
)

:: No success so far...?
IF /I NOT "%~2"=="/A" ECHO -None-

:: Done
ENDLOCAL
GOTO:EOF


:Syntax
ECHO WHICH, Version 6.11
ECHO UNIX-like WHICH utility for Windows XP and later
ECHO.
ECHO Usage:    WHICH  progname  [ /A ]
ECHO.
ECHO Where:    progname    is the name of the program to locate
ECHO           /A          lists all occurrences, not just the first one
ECHO.
ECHO Returns:  "-DOSKEY Macro-", "-CMD Internal Command-", or the fully qualified
ECHO           path to the first matching program found in the PATH, based on the
ECHO           specified extension or the ones listed in PATHEXT; or "-None-".
ECHO.
ECHO Notes:    progname MAY include extension; wildcards, drive, path NOT allowed.
ECHO           This batch file first searches the list of DOSKEY macros, then CMD's
ECHO           internal commands, then current directory, finally PATH for progname.
ECHO           Only if SysInternals' STRINGS is available and in the PATH, CMD's
ECHO           internal commands will be verified; e.g. even though MKLINK is not
ECHO           available in XP at all, without STRINGS the command "WHICH MKLINK"
ECHO           would still return "-CMD internal command-" anyway.
ECHO           When the /A switch is used, nothing is returned when nothing is found
ECHO           (unlike without /A switch, where "-None-" would be returned).
ECHO.
ECHO Written by David Riemens and Rob van der Woude
:: The things you need to do to make the text fit in 80 columns and 25 lines...
IF NOT "%OS%"=="Windows_NT" ECHO http://www.robvanderwoude.com
IF     "%OS%"=="Windows_NT" SET /P "=http://www.robvanderwoude.com" < NUL
IF     "%OS%"=="Windows_NT" EXIT /B 1

rem @ECHO OFF
:: Check for NT4 or later
IF NOT "%OS%"=="Windows_NT" GOTO Syntax
:: Check for XP or later
FOR /F "tokens=2 delims=[]" %%A IN ('VER') DO FOR /F "tokens=2" %%B IN ("%%~A") DO IF %%B LSS 5.1 GOTO Syntax

:: Check command line argument
IF     "%~1"=="" GOTO Syntax
IF NOT "%~2"=="" IF /I NOT "%~2"=="/A" GOTO Syntax
ECHO.%1 | FINDSTR /R /C:"[:\\\*\?,;/]" >NUL && GOTO Syntax

:: If the specified command contains a dot, it is not a macro nor an internal command
ECHO.%1 | FIND "." >NUL && GOTO ExtCmd

:: Check if the command specified is a DOSKEY macro
FOR /F "tokens=1* delims==" %%A IN ('DOSKEY /MACROS 2^>NUL') DO (
	IF /I "%~1"=="%%~A" (
		ECHO.
		ECHO -DOSKEY Macro-
		IF /I NOT "%~2"=="/A" GOTO:EOF
	)
)

:: Next, check if the command specified is an internal command; to do so
:: reliably we need SysInternals' STRINGS; if it isn't available, we'll
:: just check against a list of known internal commands, risking "false
:: positives" in older CMD versions (e.g. MAKELINK does not exist in XP,
:: but without STRINGS.EXE this batch file will still return "-CMD
:: internal command-"; when STRINGS.EXE IS available, the batch file would
:: return "-None-")
FOR %%A IN (APPEND ASSOC BREAK CALL CD CHCP CHDIR CLS COLOR COPY DATE DEL DIR DPATH ECHO ENDLOCAL ERASE EXIT FOR FTYPE GOTO IF KEYS MD MKDIR MKLINK MOVE PATH PAUSE POPD PROMPT PUSHD RD REM REN RENAME RMDIR SET SETLOCAL SHIFT START TIME TITLE TRUENAME TYPE VER VERIFY VOL) DO (
	IF /I "%~1"=="%%~A" (
		STRINGS.EXE /? >NUL 2>&1
		IF ERRORLEVEL 1 (
			REM * * * NOT TESTED :: may return a false positive * * *
			ECHO.
			ECHO -CMD Internal Command-
			IF /I NOT "%~2"=="/A" GOTO:EOF
		) ELSE (
			REM * * * TESTED with STRINGS.EXE :: might still occasionally fail, though * * *
			STRINGS.EXE "%ComSpec%" | FINDSTR.EXE /R /B /I /C:"%~1$" >NUL
			IF NOT ERRORLEVEL 1 (
				ECHO.
				ECHO -CMD Internal Command-
				IF /I NOT "%~2"=="/A" GOTO:EOF
			)
		)
	)
)

:ExtCmd
SETLOCAL ENABLEDELAYEDEXPANSION

:: Search current directory first, then PATH, for the "pure"
:: file name itself or one of the extensions defined in PATHEXT.
:: Add quotes to match directory names with spaces as well.
:: This command line was partly rewritten by David Riemens.
SET SRCH_PATH=.\;%PATH%
SET Found=-None-
FOR %%A IN (.;%PathExt%) DO (
	IF "!Found!"=="-None-" (
		FOR %%B IN ("%~1%%~A") DO (
			IF NOT "%%~$SRCH_PATH:B"=="" (
				FOR %%C IN ("%%~$SRCH_PATH:B") DO SET Test=%%~xC
				IF NOT "!Test!"=="" IF NOT "!Test!"=="." (
					ECHO.%%~$SRCH_PATH:B
					IF /I NOT "%~2"=="/A" (
						ENDLOCAL
						GOTO:EOF
					)
				)
			)
		)
	)
)

:: No success so far...?
IF /I NOT "%~2"=="/A" ECHO -None-

:: Done
ENDLOCAL
GOTO:EOF


:Syntax
ECHO WHICH, Version 6.11
ECHO UNIX-like WHICH utility for Windows XP and later
ECHO.
ECHO Usage:    WHICH  progname  [ /A ]
ECHO.
ECHO Where:    progname    is the name of the program to locate
ECHO           /A          lists all occurrences, not just the first one
ECHO.
ECHO Returns:  "-DOSKEY Macro-", "-CMD Internal Command-", or the fully qualified
ECHO           path to the first matching program found in the PATH, based on the
ECHO           specified extension or the ones listed in PATHEXT; or "-None-".
ECHO.
ECHO Notes:    progname MAY include extension; wildcards, drive, path NOT allowed.
ECHO           This batch file first searches the list of DOSKEY macros, then CMD's
ECHO           internal commands, then current directory, finally PATH for progname.
ECHO           Only if SysInternals' STRINGS is available and in the PATH, CMD's
ECHO           internal commands will be verified; e.g. even though MKLINK is not
ECHO           available in XP at all, without STRINGS the command "WHICH MKLINK"
ECHO           would still return "-CMD internal command-" anyway.
ECHO           When the /A switch is used, nothing is returned when nothing is found
ECHO           (unlike without /A switch, where "-None-" would be returned).
ECHO.
ECHO Written by David Riemens and Rob van der Woude
:: The things you need to do to make the text fit in 80 columns and 25 lines...
IF NOT "%OS%"=="Windows_NT" ECHO http://www.robvanderwoude.com
IF     "%OS%"=="Windows_NT" SET /P "=http://www.robvanderwoude.com" < NUL
IF     "%OS%"=="Windows_NT" EXIT /B 1

REM []