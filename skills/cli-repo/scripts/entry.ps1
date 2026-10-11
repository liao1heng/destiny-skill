param(
 [ValidateSet('clone','add','status')][string]$Mode='clone',
 [string]$Project=(Get-Location).Path,
 [string]$Url
)
$ErrorActionPreference='Stop'
$arguments=@('--mode',$Mode,'--project',$Project)
if ($Url) { $arguments+=@('--url',$Url) }
$script=Join-Path $PSScriptRoot 'repo.py'
foreach ($candidate in @('python','py','python3')) {
 if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
 $prefix=@(); if ($candidate -eq 'py') { $prefix=@('-3') }
 & $candidate @prefix -c 'import sys; assert sys.version_info >= (3, 10)' 1>$null 2>$null
 if ($LASTEXITCODE -eq 0) { & $candidate @prefix $script @arguments; exit $LASTEXITCODE }
}
if (Get-Command uv -ErrorAction SilentlyContinue) { & uv run --python 3.11 $script @arguments; exit $LASTEXITCODE }
throw 'cli-repo需要Python 3.10+或uv'
