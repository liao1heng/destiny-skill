param(
    [ValidateSet('dev', 'test')]
    [string]$Mode = 'dev',

    [string]$Repo,
    [string]$Branch,
    [string]$Path,

    [string]$Workdir,
    [string]$Prompt,
    [string]$Name,

    [ValidateSet('read-only', 'workspace-write', 'danger-full-access')]
    [string]$Sandbox,

    [string]$Model = 'mimo-v2.5-pro',

    [switch]$Wait,
    [switch]$Healthcheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Healthcheck) {
    & (Join-Path $PSScriptRoot 'test-mimo-health.ps1') -Model $Model
    exit $LASTEXITCODE
}

if ($Repo -or $Branch -or $Path) {
    if (-not ($Repo -and $Branch -and $Path)) {
        throw 'When using worktree mode, provide -Repo, -Branch, and -Path together.'
    }

    & (Join-Path $PSScriptRoot 'new-git-worktree.ps1') -Repo $Repo -Branch $Branch -Path $Path
    exit $LASTEXITCODE
}

if (-not $Workdir) {
    throw 'Provide -Workdir and -Prompt, use -Repo -Branch -Path to create a worktree, or pass -Healthcheck.'
}

if (-not $Prompt) {
    throw 'Provide -Prompt for the Claude MiMo worker.'
}

if (-not $PSBoundParameters.ContainsKey('Sandbox')) {
    $Sandbox = if ($Mode -eq 'test') { 'read-only' } else { 'workspace-write' }
}

& (Join-Path $PSScriptRoot 'run-claude-mimo.ps1') `
    -Workdir $Workdir `
    -Prompt $Prompt `
    -Mode $Mode `
    -Name $Name `
    -Sandbox $Sandbox `
    -Model $Model `
    -Wait:$Wait

exit $LASTEXITCODE
