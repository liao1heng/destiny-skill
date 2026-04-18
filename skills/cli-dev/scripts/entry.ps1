param(
    [string]$Repo,
    [string]$Branch,
    [string]$Path,
    [string]$Workdir,
    [string]$Prompt,
    [string]$Name,
    [switch]$Wait
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot

if ($Repo -or $Branch -or $Path) {
    if (-not ($Repo -and $Branch -and $Path)) {
        throw 'When using worktree mode, provide -Repo, -Branch, and -Path together.'
    }
    & (Join-Path $PSScriptRoot 'new-git-worktree.ps1') -Repo $Repo -Branch $Branch -Path $Path
    exit $LASTEXITCODE
}

if (-not $Workdir) {
    throw 'Provide -Workdir and -Prompt, or use -Repo -Branch -Path to create a worktree.'
}

if (-not $Prompt) {
    throw 'Provide -Prompt for the development worker.'
}

& (Join-Path $PSScriptRoot 'run-codex-dev.ps1') -Workdir $Workdir -Prompt $Prompt -Name $Name -Wait:$Wait
exit $LASTEXITCODE
