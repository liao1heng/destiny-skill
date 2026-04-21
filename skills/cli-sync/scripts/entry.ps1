param(
    [ValidateSet('status', 'pull', 'push')]
    [string]$Mode = 'status',

    [string]$Message = 'Sync local Codex skills'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'sync-skills.ps1') -Mode $Mode -Message $Message
exit $LASTEXITCODE
