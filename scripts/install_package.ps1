<#
.SYNOPSIS
    Install the Cinema Camera Rig override package into Houdini's packages dir.

.DESCRIPTION
    Symlinks (preferred) or copies packages/cinema_camera_rig.json and
    packages/cinema_camera_rig.local.json into one or more Houdini packages
    folders so Houdini auto-loads the repo at startup, prepending the repo's
    otls/, vex/, and scripts/python/ to HOUDINI_PATH.

    Before installing, the CINEMA_CAMERA_REPO value inside the package json
    is pinned to THIS clone's absolute path (rewritten in place if it
    differs), so the repo works from any clone location while keeping
    symlink hot-reload semantics.

    Targets (auto-detected):
      $env:USERPROFILE\houdini21.0\packages\
      $env:USERPROFILE\OneDrive\Documents\houdini21.0\packages\
      $env:HOUDINI_USER_PREF_DIR\packages\  (if set)

    Existing files at the target are backed up to .bak.<timestamp>.

.PARAMETER Targets
    One or more explicit target packages directories. Skips auto-detection.

.PARAMETER ForceCopy
    Always copy files instead of symlinking. Use if symlinks fail (no Developer
    Mode + non-admin shell). Trade-off: edits to repo won't hot-reload in Houdini.

.PARAMETER Uninstall
    Remove installed package files (and restore the most recent .bak if found).

.EXAMPLE
    .\scripts\install_package.ps1
    .\scripts\install_package.ps1 -ForceCopy
    .\scripts\install_package.ps1 -Targets "C:\Custom\houdini21.0\packages"
    .\scripts\install_package.ps1 -Uninstall
#>

[CmdletBinding()]
param(
    [string[]]$Targets,
    [switch]$ForceCopy,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

$RepoRoot      = Split-Path -Parent $PSScriptRoot
$PackagesDir   = Join-Path $RepoRoot 'packages'
$MainPackage   = Join-Path $PackagesDir 'cinema_camera_rig.json'
$LocalPackage  = Join-Path $PackagesDir 'cinema_camera_rig.local.json'

function Sync-RepoPathInPackage {
    # The tracked package json pins CINEMA_CAMERA_REPO to an absolute path.
    # Rewrite it to THIS clone's root if it differs (surgical regex keeps
    # the file's formatting and comment keys intact).
    $content = Get-Content $MainPackage -Raw
    $repoFwd = $RepoRoot -replace '\\', '/'
    $pattern = '("CINEMA_CAMERA_REPO":\s*")[^"]*(")'
    $updated = $content -replace $pattern, "`${1}$repoFwd`${2}"
    if ($updated -ne $content) {
        Set-Content -Path $MainPackage -Value $updated -Encoding utf8 -NoNewline
        Write-Host "  [pin]  CINEMA_CAMERA_REPO -> $repoFwd" -ForegroundColor Green
    } else {
        Write-Host "  [pin]  CINEMA_CAMERA_REPO already points at this clone" -ForegroundColor DarkGray
    }
}

function Get-DefaultTargets {
    $candidates = @(
        Join-Path $env:USERPROFILE 'houdini21.0\packages'
        Join-Path $env:USERPROFILE 'OneDrive\Documents\houdini21.0\packages'
    )
    if ($env:HOUDINI_USER_PREF_DIR) {
        $candidates += Join-Path $env:HOUDINI_USER_PREF_DIR 'packages'
    }
    $existing = $candidates | Where-Object {
        Test-Path (Split-Path $_ -Parent)
    } | Select-Object -Unique
    return $existing
}

function Install-PackageFile {
    param(
        [string]$Source,
        [string]$TargetDir,
        [switch]$UseCopy
    )
    if (-not (Test-Path $Source)) {
        Write-Host "  [skip] source missing: $Source" -ForegroundColor DarkYellow
        return
    }

    $fileName = Split-Path $Source -Leaf
    $target   = Join-Path $TargetDir $fileName

    if (Test-Path $target) {
        $stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
        $backup = "$target.bak.$stamp"
        Move-Item $target $backup
        Write-Host "  [back] $fileName -> $($backup | Split-Path -Leaf)" -ForegroundColor DarkGray
    }

    if ($UseCopy) {
        Copy-Item $Source $target
        Write-Host "  [copy] $fileName" -ForegroundColor Green
    } else {
        try {
            New-Item -ItemType SymbolicLink -Path $target -Value $Source -ErrorAction Stop | Out-Null
            Write-Host "  [link] $fileName -> $Source" -ForegroundColor Green
        } catch {
            Write-Host "  [warn] symlink failed ($($_.Exception.Message.Trim())); falling back to copy" -ForegroundColor Yellow
            Copy-Item $Source $target
            Write-Host "  [copy] $fileName" -ForegroundColor Green
        }
    }
}

function Remove-PackageFile {
    param(
        [string]$FileName,
        [string]$TargetDir
    )
    $target = Join-Path $TargetDir $FileName
    if (Test-Path $target) {
        Remove-Item $target -Force
        Write-Host "  [del]  $FileName" -ForegroundColor DarkGreen

        # Try to restore most recent backup
        $latestBak = Get-ChildItem -Path $TargetDir -Filter "$FileName.bak.*" -ErrorAction SilentlyContinue |
                     Sort-Object Name -Descending |
                     Select-Object -First 1
        if ($latestBak) {
            Move-Item $latestBak.FullName $target
            Write-Host "  [rest] $FileName <- $($latestBak.Name)" -ForegroundColor DarkCyan
        }
    } else {
        Write-Host "  [skip] $FileName not present" -ForegroundColor DarkGray
    }
}

# --- main ----------------------------------------------------------------

Write-Host ""
Write-Host "Cinema Camera Rig override package installer" -ForegroundColor Cyan
Write-Host "  Repo:     $RepoRoot"
Write-Host ""

if (-not $Uninstall) { Sync-RepoPathInPackage }

if (-not $Targets) { $Targets = Get-DefaultTargets }

if (-not $Targets) {
    Write-Host "ERROR: no Houdini packages directories found." -ForegroundColor Red
    Write-Host "       Pass -Targets <path> or set `$env:HOUDINI_USER_PREF_DIR." -ForegroundColor Red
    exit 1
}

foreach ($targetDir in $Targets) {
    Write-Host "Target: $targetDir"
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        Write-Host "  [mkdir] created"
    }

    if ($Uninstall) {
        Remove-PackageFile -FileName 'cinema_camera_rig.json'       -TargetDir $targetDir
        Remove-PackageFile -FileName 'cinema_camera_rig.local.json' -TargetDir $targetDir
    } else {
        Install-PackageFile -Source $MainPackage  -TargetDir $targetDir -UseCopy:$ForceCopy
        Install-PackageFile -Source $LocalPackage -TargetDir $targetDir -UseCopy:$ForceCopy
    }
    Write-Host ""
}

if (-not $Uninstall) {
    Write-Host "Done. Restart Houdini to load the override package." -ForegroundColor Cyan
    Write-Host "Verify in Houdini Python shell:" -ForegroundColor Cyan
    Write-Host "  import os; print(os.environ.get('CINEMA_CAMERA_REPO'))" -ForegroundColor DarkGray
    Write-Host "  import hou; print(hou.hda.loadedFiles())" -ForegroundColor DarkGray
} else {
    Write-Host "Uninstalled. Restart Houdini." -ForegroundColor Cyan
}
