param(
    [ValidateSet('status', 'pull', 'push')]
    [string]$Mode = 'status',

    [string]$Message = 'Sync local Codex skills'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-PythonRunner {
    param([Parameter(Mandatory = $true)][string]$Candidate)

    $command = Get-Command $Candidate -ErrorAction SilentlyContinue
    if (-not $command) {
        return $false
    }

    if ($Candidate -eq 'py') {
        & py -3 -c "import sys" 1>$null 2>$null
    }
    else {
        & $Candidate -c "import sys" 1>$null 2>$null
    }

    return $LASTEXITCODE -eq 0
}

function Get-UvCommand {
    $command = Get-Command uv -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

$scriptPath = Join-Path $PSScriptRoot 'sync_skills.py'

foreach ($candidate in @('python', 'py', 'python3')) {
    if (-not (Test-PythonRunner -Candidate $candidate)) {
        continue
    }

    if ($candidate -eq 'py') {
        & py -3 $scriptPath --mode $Mode --message $Message
    }
    else {
        & $candidate $scriptPath --mode $Mode --message $Message
    }
    exit $LASTEXITCODE
}

$uvCommand = Get-UvCommand
if ($uvCommand) {
    & $uvCommand run --python 3.11 $scriptPath --mode $Mode --message $Message
    exit $LASTEXITCODE
}

throw 'cli-sync requires a working Python interpreter or uv, but neither is available.'
