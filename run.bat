@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
title Tetris

rem =====================================================================
rem  Tetris launcher (Windows)
rem  1) find a Python interpreter that already has pygame
rem  2) otherwise find any Python and install pygame for it
rem  3) run the game, passing through any extra arguments
rem =====================================================================

set "PY="

rem --- 1) prefer an interpreter that already has pygame ---
python -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto run

py -3 -c "import pygame" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto run

rem --- 2) none has pygame: pick any working interpreter, then install ---
python -c "pass" >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto install_deps

py -3 -c "pass" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto install_deps

goto no_python

:install_deps
echo.
echo  pygame is not installed for this Python. Installing it now...
echo.
%PY% -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
if not errorlevel 1 goto run

echo  No official pygame wheel for this Python, trying pygame-ce...
%PY% -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pygame-ce
if not errorlevel 1 goto run

goto install_failed

:run
%PY% tetris.py %*
if errorlevel 1 pause
exit /b 0

:no_python
echo.
echo  [ERROR] Python was not found.
echo.
echo   Install Python 3.9 or newer from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" during setup.
echo.
pause
exit /b 1

:install_failed
echo.
echo  [ERROR] Could not install a pygame package.
echo.
echo   Try it manually:
echo     %PY% -m pip install pygame
echo     %PY% -m pip install pygame-ce
echo.
pause
exit /b 1
