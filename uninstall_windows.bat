@echo off
setlocal

set "PAWDF_ROOT=%~dp0"
set "PAWDF_UNINSTALLER=%PAWDF_ROOT%packaging\windows\uninstall_windows.ps1"

if not exist "%PAWDF_UNINSTALLER%" (
  echo.
  echo ERROR: Pawdf Windows uninstaller was not found:
  echo   %PAWDF_UNINSTALLER%
  exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%PAWDF_UNINSTALLER%"
set "PAWDF_EXIT_CODE=%ERRORLEVEL%"

if not "%PAWDF_EXIT_CODE%"=="0" (
  echo.
  echo Pawdf removal failed with exit code %PAWDF_EXIT_CODE%.
)

exit /b %PAWDF_EXIT_CODE%
