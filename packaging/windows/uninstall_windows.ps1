# The reverse of install_windows.ps1: removes the installed files and both
# shortcuts for the current user. No administrator rights needed, because
# nothing was installed outside %LOCALAPPDATA%.
#
# This leaves the cloned repository, .venv\ and dist\ alone.
#
#     powershell -ExecutionPolicy Bypass -File packaging\windows\uninstall_windows.ps1

$ErrorActionPreference = "Stop"

$InstallDir  = Join-Path $env:LOCALAPPDATA "Pawdf"
$StartMenu   = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Pawdf.lnk"
$DesktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Pawdf.lnk"

Write-Host ""
Write-Host "Removing Pawdf..."
Write-Host ""

if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
    Write-Host "  - application files" -ForegroundColor Green
}
foreach ($link in @($StartMenu, $DesktopLink)) {
    if (Test-Path $link) {
        Remove-Item -Force $link
        Write-Host "  - $(Split-Path $link -Leaf)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "  Pawdf has been uninstalled." -ForegroundColor Green
Write-Host "  The cloned repository, .venv\ and dist\ were left alone." -ForegroundColor DarkGray
Write-Host ""
