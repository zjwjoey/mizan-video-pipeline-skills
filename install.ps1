[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$SkillRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $SkillRoot) {
    if ($env:CODEX_HOME) {
        $SkillRoot = Join-Path $env:CODEX_HOME 'skills'
    } else {
        $profilePath = [Environment]::GetFolderPath('UserProfile')
        $SkillRoot = Join-Path $profilePath '.codex\skills'
    }
}

$sourceRoot = Join-Path $PSScriptRoot 'skills'
$SkillRoot = [IO.Path]::GetFullPath($SkillRoot)
if ($SkillRoot.TrimEnd('\', '/') -eq [IO.Path]::GetFullPath($sourceRoot).TrimEnd('\', '/')) {
    throw 'Installation target must not be the repository source directory.'
}
$skillNames = @(
    'video-storyboard-compiler',
    'gpt-image-ext-material-generation',
    'dreamina-canvas-bootstrap',
    'dreamina-cli',
    'capcut-mate-video-pipeline'
)
$missing = @($skillNames | Where-Object { -not (Test-Path -LiteralPath (Join-Path $sourceRoot $_)) })
if ($missing.Count -gt 0) {
    throw "Repository package is incomplete. Missing: $($missing -join ', ')"
}

$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$backupRoot = Join-Path (Split-Path -Parent $SkillRoot) "skill-backups\$stamp"
$createRoot = $PSCmdlet.ShouldProcess($SkillRoot, 'Create skill root directory')
if (-not $createRoot) {
    return
}
New-Item -ItemType Directory -Force -Path $SkillRoot | Out-Null
$installed = [System.Collections.Generic.List[string]]::new()

foreach ($name in $skillNames) {
    $source = Join-Path $sourceRoot $name
    $destination = Join-Path $SkillRoot $name
    $backup = Join-Path $backupRoot $name
    if ([IO.Path]::GetFullPath((Split-Path -Parent $destination)) -ne $SkillRoot) {
        throw 'Resolved skill destination is outside the intended installation root.'
    }

    if ($PSCmdlet.ShouldProcess($destination, 'Install pipeline skill')) {
        if (Test-Path -LiteralPath $destination) {
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            Move-Item -LiteralPath $destination -Destination $backup
        }
        try {
            Copy-Item -LiteralPath $source -Destination $destination -Recurse
            $installed.Add($destination)
        } catch {
            if (Test-Path -LiteralPath $destination) {
                New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
                Move-Item -LiteralPath $destination -Destination (Join-Path $backupRoot ($name + '.partial'))
            }
            if (Test-Path -LiteralPath $backup) {
                Move-Item -LiteralPath $backup -Destination $destination
            }
            throw
        }
    }
}

[pscustomobject]@{
    skill_root = $SkillRoot
    installed = @($installed)
    backup_root = if (Test-Path -LiteralPath $backupRoot) { $backupRoot } else { $null }
} | ConvertTo-Json -Depth 4
