# Pawdf end-user installer for Windows.
# No Git, Python, pip, compiler, source checkout, or administrator access.
#
# Everything lives inside a function rather than a top-level [CmdletBinding()]
# / param() block. Confirmed on real Windows 11 hardware (PowerShell 5.1,
# build 26100): a script whose first statement is a top-level param() block
# throws "You cannot call a method on a null-valued expression" from inside
# Invoke-Expression itself - reproduced identically whether the content
# reaches iex through a pipe (`irm ... | iex`) or as a pre-captured variable
# (`iex $result`), and independent of TLS, proxy configuration, or Windows
# Defender (Get-MpThreatDetection showed nothing; all four were checked
# before concluding this). Running the identical text as a file
# (`.\install.ps1`) has no such problem - the incompatibility is specific to
# Invoke-Expression parsing a top-level param() block, not to this script's
# logic. A script with no top-level param() isn't affected, so the real
# parameters live on the inner function instead, forwarded via `@args`.
function Install-Pawdf {
    [CmdletBinding()]
    param(
        [string]$Version = "latest",
        [string]$SourceDirectory = "",
        [string]$InstallDirectory = "",
        [switch]$NoLaunch,
        [switch]$Uninstall
    )

    $ErrorActionPreference = "Stop"

    # Windows PowerShell 5.1 (the default powershell.exe, as opposed to pwsh)
    # does not enable TLS 1.2 by default on many real-world Windows installs,
    # and GitHub's servers require it. Without this, Invoke-WebRequest below
    # fails the TLS handshake silently in a way that surfaces as a confusing
    # downstream error rather than a clear network message. .NET has shipped
    # Tls12 since .NET Framework 4.5, so this is safe on any Windows this
    # installer otherwise supports; the try/catch is only for the
    # unsupported-and-unreachable case of an even older .NET.
    try {
        [Net.ServicePointManager]::SecurityProtocol = (
            [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        )
    }
    catch {
        Write-Warning "Could not enable TLS 1.2; the download below may fail on this system."
    }

    # Invoke-WebRequest renders a UI progress bar by default, updated on
    # every chunk received; on Windows PowerShell 5.1 that rendering is slow
    # enough to fall behind the incoming stream for a file the size of the
    # installer, and the server or an intermediate proxy closes the
    # connection on the client for reading too slowly. Confirmed on real
    # Windows 11 hardware: downloading the ~4.6 KB install.ps1 script itself
    # never failed this way: only the much larger Setup.exe download did,
    # with "The request was aborted: The connection was closed
    # unexpectedly." Suppressing the progress bar is the standard fix.
    $ProgressPreference = "SilentlyContinue"

    $Repository = "aniceswan/Pawdf"
    $Asset = "Pawdf-Windows-x86_64-Setup.exe"

    if ([string]::IsNullOrWhiteSpace($InstallDirectory)) {
        $InstallDirectory = Join-Path $env:LOCALAPPDATA "Programs\Pawdf"
    }

    if ($Uninstall) {
        $Uninstaller = Join-Path $InstallDirectory "unins000.exe"
        if (Test-Path $Uninstaller) {
            $Process = Start-Process -FilePath $Uninstaller `
                -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" `
                -Wait -PassThru
            if ($Process.ExitCode -ne 0) {
                throw "Pawdf uninstaller exited with code $($Process.ExitCode)."
            }
        }
        elseif (Test-Path $InstallDirectory) {
            Remove-Item -Recurse -Force $InstallDirectory
        }
        Write-Host "Pawdf has been removed for the current user." -ForegroundColor Green
        return
    }

    # [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture was
    # the original approach here, and confirmed on real Windows 11 hardware
    # (PowerShell 5.1, build 26100) to throw "cannot call a method on a
    # null-valued expression" from calling .ToString() on it - the exact
    # symptom this whole rewrite chased through Invoke-Expression and $args
    # before isolating it to this specific line. PROCESSOR_ARCHITECTURE is a
    # plain environment variable Windows has set since XP, with no .NET type
    # resolution involved at all, so there is nothing left for this to fail
    # on beyond the environment variable simply being unset.
    $Architecture = $env:PROCESSOR_ARCHITECTURE
    if ($env:PROCESSOR_ARCHITEW6432) {
        # A 32-bit PowerShell process on 64-bit Windows reports "x86" in
        # PROCESSOR_ARCHITECTURE; PROCESSOR_ARCHITEW6432 carries the real
        # native architecture in that case.
        $Architecture = $env:PROCESSOR_ARCHITEW6432
    }

    if ($Architecture -eq "ARM64") {
        Write-Host "Windows ARM64 detected; installing the x64 build through Windows emulation." -ForegroundColor Yellow
    }
    elseif ($Architecture -ne "AMD64") {
        throw "Unsupported Windows architecture: $Architecture"
    }

    $Temporary = Join-Path ([IO.Path]::GetTempPath()) ("pawdf-install-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $Temporary | Out-Null

    try {
        $AssetPath = Join-Path $Temporary $Asset
        $SumsPath = Join-Path $Temporary "SHA256SUMS.txt"

        if (-not [string]::IsNullOrWhiteSpace($SourceDirectory)) {
            Copy-Item (Join-Path $SourceDirectory $Asset) $AssetPath
            Copy-Item (Join-Path $SourceDirectory "SHA256SUMS.txt") $SumsPath
        }
        else {
            if ($Version -eq "latest") {
                $Base = "https://github.com/$Repository/releases/latest/download"
            }
            else {
                $Base = "https://github.com/$Repository/releases/download/$Version"
            }
            Write-Host "Downloading $Asset..."
            # Invoke-WebRequest on Windows PowerShell 5.1 uses the legacy
            # System.Net.HttpWebRequest, which is well documented to close
            # the connection mid-transfer on some GitHub release downloads
            # after following the github.com -> objects.githubusercontent.com
            # redirect - confirmed on real Windows 11 hardware, and
            # unaffected by disabling the progress bar (ruling that out).
            # System.Net.WebClient does not share this failure mode and
            # already proved reliable against this same repository during
            # earlier diagnosis.
            $WebClient = New-Object System.Net.WebClient
            try {
                $WebClient.DownloadFile("$Base/$Asset", $AssetPath)
                $WebClient.DownloadFile("$Base/SHA256SUMS.txt", $SumsPath)
            }
            finally {
                $WebClient.Dispose()
            }
        }

        $Expected = $null
        foreach ($Line in Get-Content $SumsPath) {
            if ($Line -match "^([0-9a-fA-F]{64})\s+\*?(.+)$") {
                if ((Split-Path $Matches[2] -Leaf) -eq $Asset) {
                    $Expected = $Matches[1].ToLowerInvariant()
                    break
                }
            }
        }
        if (-not $Expected) { throw "$Asset is not listed in SHA256SUMS.txt." }

        $Actual = (Get-FileHash -Algorithm SHA256 $AssetPath).Hash.ToLowerInvariant()
        if ($Actual -ne $Expected) {
            throw "SHA-256 verification failed. Expected $Expected, got $Actual."
        }
        Write-Host "SHA-256 verified." -ForegroundColor Green

        $Arguments = @(
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CURRENTUSER",
            "/DIR=$InstallDirectory"
        )
        $Process = Start-Process -FilePath $AssetPath -ArgumentList $Arguments -Wait -PassThru
        if ($Process.ExitCode -ne 0) {
            throw "Pawdf installer exited with code $($Process.ExitCode)."
        }

        $Executable = Join-Path $InstallDirectory "pawdf.exe"
        if (-not (Test-Path $Executable)) {
            throw "The installer completed but $Executable is missing."
        }

        Write-Host ""
        Write-Host "Pawdf is installed." -ForegroundColor Green
        Write-Host "Executable: $Executable"
        if (-not $NoLaunch) { Start-Process -FilePath $Executable }
    }
    finally {
        Remove-Item -Recurse -Force $Temporary -ErrorAction SilentlyContinue
    }
}

# $args is only populated when this runs as an actual file
# (`.\install.ps1 -Uninstall`); at the interactive prompt or through
# Invoke-Expression - which is what `irm ... | iex` uses, and that one-liner
# has no syntax to pass flags through it in the first place - $args is
# $null, and splatting a null variable throws the same "cannot call a
# method on a null-valued expression" this rewrite was meant to fix.
# Confirmed on real Windows 11 hardware: the error moved from
# Invoke-Expression itself to this exact line once the top-level param()
# block was removed, isolating it to this splat.
if ($args) {
    Install-Pawdf @args
}
else {
    Install-Pawdf
}
