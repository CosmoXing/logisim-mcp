@echo off
rem ---------------------------------------------------------------
rem logisim-mcp plugin - stdio launcher for Windows
rem   run-mcp.cmd             start MCP server (called by the client)
rem   run-mcp.cmd --doctor    print environment diagnostics
rem Interpreter order: LOGISIM_PYTHON > where python > where python3 > python
rem NOTE: keep this file ASCII-only. A UTF-8 Chinese comment breaks
rem       cmd.exe parsing under the default GBK console codepage.
rem ---------------------------------------------------------------
setlocal enabledelayedexpansion
set "PYEXE="

if defined LOGISIM_PYTHON (
  if exist "%LOGISIM_PYTHON%" set "PYEXE=%LOGISIM_PYTHON%"
)

if not defined PYEXE (
  for /f "delims=" %%i in ('where python.exe 2^>nul ^<nul') do (
    if not defined PYEXE set "PYEXE=%%i"
  )
)

if not defined PYEXE (
  for /f "delims=" %%i in ('where python3.exe 2^>nul ^<nul') do (
    if not defined PYEXE set "PYEXE=%%i"
  )
)

if not defined PYEXE set "PYEXE=python"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

"!PYEXE!" "%~dp0..\server\server.py" %*
exit /b %ERRORLEVEL%
