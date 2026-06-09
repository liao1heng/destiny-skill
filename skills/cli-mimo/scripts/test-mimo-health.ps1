param(
    [string]$Model = 'mimo-v2.5-pro'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$claudePath = (Get-Command claude -ErrorAction Stop).Source
$token = [Environment]::GetEnvironmentVariable('ANTHROPIC_AUTH_TOKEN', 'User')
$baseUrl = [Environment]::GetEnvironmentVariable('ANTHROPIC_BASE_URL', 'User')

if (-not $token) {
    throw 'ANTHROPIC_AUTH_TOKEN is not set in the user environment.'
}

if (-not $baseUrl) {
    throw 'ANTHROPIC_BASE_URL is not set in the user environment.'
}

$stderrFile = Join-Path $env:TEMP 'cli-mimo-health-stderr.log'
$env:ANTHROPIC_API_KEY = $null
$env:ANTHROPIC_AUTH_TOKEN = $token
$env:ANTHROPIC_BASE_URL = $baseUrl
$env:ANTHROPIC_MODEL = $Model
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $Model
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $Model
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $Model

$response = 'Reply with exactly OK and nothing else.' | & $claudePath -p --output-format text --no-session-persistence --model $Model 2>$stderrFile
$exitCode = $LASTEXITCODE

[ordered]@{
    ok = ($exitCode -eq 0 -and $response.Trim() -eq 'OK')
    exit_code = $exitCode
    model = $Model
    base_url = $baseUrl
    response = $response.Trim()
    stderr_file = $stderrFile
} | ConvertTo-Json -Depth 3
