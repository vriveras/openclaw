<#
.SYNOPSIS
    A2UI bundler for Windows - PowerShell equivalent of bundle-a2ui.sh
#>

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $RootDir) { $RootDir = Split-Path -Parent $PSScriptRoot }
$HashFile = Join-Path $RootDir "src\canvas-host\a2ui\.bundle.hash"
$OutputFile = Join-Path $RootDir "src\canvas-host\a2ui\a2ui.bundle.js"
$A2UIRendererDir = Join-Path $RootDir "vendor\a2ui\renderers\lit"
$A2UIAppDir = Join-Path $RootDir "apps\shared\MoltbotKit\Tools\CanvasA2UI"

# Docker builds exclude vendor/apps via .dockerignore.
# In that environment we must keep the prebuilt bundle.
if (-not (Test-Path $A2UIRendererDir) -or -not (Test-Path $A2UIAppDir)) {
    Write-Host "A2UI sources missing; keeping prebuilt bundle."
    exit 0
}

$InputPaths = @(
    (Join-Path $RootDir "package.json"),
    (Join-Path $RootDir "pnpm-lock.yaml"),
    $A2UIRendererDir,
    $A2UIAppDir
)

function Get-FilesRecursive {
    param([string]$Path)
    
    if (Test-Path $Path -PathType Container) {
        Get-ChildItem -Path $Path -Recurse -File | ForEach-Object { $_.FullName }
    } else {
        $Path
    }
}

function Compute-Hash {
    $files = @()
    foreach ($input in $InputPaths) {
        $files += Get-FilesRecursive -Path $input
    }
    
    # Sort files by normalized path
    $files = $files | Sort-Object { $_.Replace("\", "/") }
    
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $stream = New-Object System.IO.MemoryStream
    
    foreach ($filePath in $files) {
        $rel = $filePath.Replace($RootDir, "").TrimStart("\", "/").Replace("\", "/")
        $relBytes = [System.Text.Encoding]::UTF8.GetBytes($rel)
        $stream.Write($relBytes, 0, $relBytes.Length)
        $stream.WriteByte(0)
        
        $content = [System.IO.File]::ReadAllBytes($filePath)
        $stream.Write($content, 0, $content.Length)
        $stream.WriteByte(0)
    }
    
    $stream.Position = 0
    $hashBytes = $sha256.ComputeHash($stream)
    $stream.Dispose()
    $sha256.Dispose()
    
    return [BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
}

$currentHash = Compute-Hash

if (Test-Path $HashFile) {
    $previousHash = Get-Content $HashFile -Raw
    $previousHash = $previousHash.Trim()
    
    if ($previousHash -eq $currentHash -and (Test-Path $OutputFile)) {
        Write-Host "A2UI bundle up to date; skipping."
        exit 0
    }
}

Write-Host "Building A2UI bundle..."

# Run tsc
$tsconfigPath = Join-Path $A2UIRendererDir "tsconfig.json"
& pnpm exec tsc -p $tsconfigPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "tsc failed"
    exit 1
}

# Run rolldown
$rolldownConfig = Join-Path $A2UIAppDir "rolldown.config.mjs"
& pnpm exec rolldown -c $rolldownConfig
if ($LASTEXITCODE -ne 0) {
    Write-Error "rolldown failed"
    exit 1
}

# Write hash
$currentHash | Out-File -FilePath $HashFile -NoNewline -Encoding utf8

Write-Host "A2UI bundle created."
