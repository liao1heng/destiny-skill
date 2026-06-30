param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
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
    throw 'Python 3 is required for cli-vpn-install but was not found in PATH.'
}

$scriptPath = Join-Path $PSScriptRoot 'cli_vpn_install.py'
if ($pythonCommand -eq 'py') {
    & py -3 $scriptPath @Args
}
else {
    & $pythonCommand $scriptPath @Args
}
exit $LASTEXITCODE
