# Build Pawdf and install it for the current user on Windows.
#
# No administrator rights needed: everything lands under %LOCALAPPDATA%.
# Safe to re-run; it replaces a previous install in place.
#
#     powershell -ExecutionPolicy Bypass -File packaging\windows\install_windows.ps1
#
# NOTE: this script has not been run on real Windows hardware. It is written
# against documented behaviour and is exercised by CI on windows-latest, which
# builds the bundle but cannot verify the Start Menu and Desktop shortcuts.
# Treat the shortcut steps as untested. See packaging/README.md.

$ErrorActionPreference = "Stop"

$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvDir     = Join-Path $RepoRoot ".venv"
$DistDir     = Join-Path $RepoRoot "dist\pawdf"
$InstallDir  = Join-Path $env:LOCALAPPDATA "Pawdf"
$ExePath     = Join-Path $InstallDir "pawdf.exe"
$StartMenu   = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Pawdf.lnk"
$DesktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Pawdf.lnk"

$script:Step = 0
function Step($text) {
    $script:Step++
    Write-Host ""
    Write-Host "[$script:Step/5] $text" -ForegroundColor Yellow
}
function Ok($text)   { Write-Host "      + $text" -ForegroundColor Green }
function Info($text) { Write-Host "      $text" -ForegroundColor DarkGray }
function Die($text)  { Write-Host ""; Write-Host "error: $text" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "   /\_/\    Pawdf"        -ForegroundColor DarkYellow
Write-Host "  ( o.o )   offline PDF tools" -ForegroundColor DarkYellow
Write-Host "   > ^ <"                 -ForegroundColor DarkYellow

# ----------------------------------------------------------- requirements --

Step "Checking requirements"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Die "Python is not on PATH.`n  Install it from https://python.org/downloads (tick 'Add python.exe to PATH')`n  or run:  winget install Python.Python.3.12"
}

$version = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
$ok = & python -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)"
if ($ok.Trim() -ne "1") { Die "Python 3.10 or newer is required (found $version)." }
Ok "python $version"

# --------------------------------------------------------- dependencies --

Step "Setting up the Python environment"

if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    Info "creating a virtualenv at .venv"
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Die "could not create a virtualenv at $VenvDir" }
}
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

Info "installing dependencies (a few minutes on first run)"
& $VenvPython -m pip install --quiet --upgrade pip
# [dev] pulls in the [gui] extra plus PyInstaller, which the build needs.
& $VenvPython -m pip install --quiet -e "$RepoRoot[dev]"
if ($LASTEXITCODE -ne 0) { Die "dependency installation failed. Scroll up for pip's output." }
Ok "dependencies installed"

# ---------------------------------------------------------------- build --

Step "Building the application"

if ((Test-Path $DistDir) -and -not $env:PAWDF_REBUILD) {
    Info "reusing the existing build in dist\ (set PAWDF_REBUILD=1 to force)"
} else {
    Info "bundling with PyInstaller (this is the slow part)"
    $log = Join-Path $RepoRoot "build\install-build.log"
    New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
    & $VenvPython (Join-Path $RepoRoot "scripts\build_pyinstaller.py") *> $log
    if ($LASTEXITCODE -ne 0) {
        Get-Content $log -Tail 25 | ForEach-Object { Write-Host "        $_" }
        Die "the build failed. Full log: $log"
    }
}

if (-not (Test-Path (Join-Path $DistDir "pawdf.exe"))) {
    Die "the build did not produce $DistDir\pawdf.exe"
}
Ok "build ready"

# -------------------------------------------------------------- install --

Step "Installing to $InstallDir"

if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $DistDir "*") $InstallDir
Ok "application files"

# The shortcut's AppUserModelID must match the one the app sets at startup
# (gui/app.py), or Windows treats the running window as a separate taskbar
# button and pinning the shortcut appears to do nothing.
$shell = New-Object -ComObject WScript.Shell
foreach ($linkPath in @($StartMenu, $DesktopLink)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $linkPath) | Out-Null
    $link = $shell.CreateShortcut($linkPath)
    $link.TargetPath       = $ExePath
    $link.WorkingDirectory = $InstallDir
    $link.IconLocation     = $ExePath
    $link.Description      = "Split, merge, organize, compress and convert PDFs, fully offline"
    $link.Save()
}
Ok "Start Menu and Desktop shortcuts"

# --------------------------------------------------------------- verify --

Step "Verifying"

if (-not (Test-Path $ExePath)) { Die "the installed executable is missing" }
Ok "executable in place"

if (-not (Test-Path (Join-Path $InstallDir "_internal\pawdf\gui\web\index.html"))) {
    Die "the UI files did not make it into the bundle"
}
Ok "UI assets bundled"

Write-Host ""
Write-Host "  Pawdf is installed." -ForegroundColor Green
Write-Host ""
Write-Host "  Find it in the Start Menu, or on your Desktop."
Write-Host "  To pin it: open it, right-click its taskbar icon, and choose"
Write-Host "  'Pin to taskbar'."
Write-Host ""
Write-Host "  Run it directly:   $ExePath"
Write-Host "  Remove it:         powershell -ExecutionPolicy Bypass -File packaging\windows\uninstall_windows.ps1"
Write-Host ""
