param(
    [string]$Workdir,
    [string]$Prompt,
    [string]$Name,
    [ValidateSet('read-only', 'workspace-write', 'danger-full-access')]
    [string]$Sandbox = 'read-only',
    [string]$Model,
    [switch]$Wait
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $Workdir) {
    throw 'Provide -Workdir for the test worker.'
}

if (-not $Prompt) {
    throw 'Provide -Prompt for the test worker.'
}

& (Join-Path $PSScriptRoot 'run-codex-test.ps1') -Workdir $Workdir -Prompt $Prompt -Name $Name -Sandbox $Sandbox -Model $Model -Wait:$Wait
exit $LASTEXITCODE
