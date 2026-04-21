param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'pull', 'push')]
    [string]$Mode,

    [string]$Message = 'Sync local Codex skills'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pythonCommand = $null
foreach ($candidate in @('python', 'py', 'python3')) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
        $pythonCommand = $candidate
        break
    }
}

if (-not $pythonCommand) {
    throw 'Python is required for cli-sync but was not found in PATH.'
}

$scriptPath = Join-Path $PSScriptRoot 'sync_skills.py'
if ($pythonCommand -eq 'py') {
    & py -3 $scriptPath --mode $Mode --message $Message
}
else {
    & $pythonCommand $scriptPath --mode $Mode --message $Message
}
exit $LASTEXITCODE
