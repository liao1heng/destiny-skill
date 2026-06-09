param(
    [Parameter(Mandatory = $true)]
    [string]$Workdir,

    [Parameter(Mandatory = $true)]
    [string]$Prompt,

    [ValidateSet('dev', 'test')]
    [string]$Mode = 'dev',

    [string]$Name,

    [ValidateSet('read-only', 'workspace-write', 'danger-full-access')]
    [string]$Sandbox = 'workspace-write',

    [string]$Model = 'mimo-v2.5-pro',

    [switch]$Wait
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function New-JobName {
    param(
        [string]$Prefix,
        [string]$RawName
    )

    $baseName = if ($RawName) { $RawName } else { "$Prefix-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
    $clean = ($baseName -replace '[^a-zA-Z0-9._-]', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($clean)) {
        $clean = "$Prefix-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    }
    return $clean
}

function Escape-SingleQuoted {
    param([AllowNull()][string]$Value)
    if ($null -eq $Value) {
        return ''
    }
    return $Value.Replace("'", "''")
}

$claudePath = (Get-Command claude -ErrorAction Stop).Source
$pwshPath = (Get-Command pwsh -ErrorAction Stop).Source
$resolvedWorkdir = (Resolve-Path -LiteralPath $Workdir).Path
$jobName = New-JobName -Prefix "mimo-$Mode" -RawName $Name
$jobDir = Join-Path $HOME ".codex\jobs\$jobName"

New-Item -ItemType Directory -Force -Path $jobDir | Out-Null

$promptFile = Join-Path $jobDir 'prompt.txt'
$runnerFile = Join-Path $jobDir 'runner.ps1'
$stderrFile = Join-Path $jobDir 'stderr.log'
$lastMessageFile = Join-Path $jobDir 'last-message.txt'
$beforeStatusFile = Join-Path $jobDir 'before-status.txt'
$afterStatusFile = Join-Path $jobDir 'after-status.txt'
$statusWarningFile = Join-Path $jobDir 'status-warning.txt'

$instructions = if ($Mode -eq 'test') {
@"
You are an external Claude Code verification worker running through Xiaomi MiMo.

Rules:
- Do not modify repository files unless the user explicitly asked for a fix.
- Focus on review, tests, regression checks, and concise findings.
- Run the smallest useful command set.
- Treat the requested sandbox level as a hard intent even though this wrapper does not enforce it at the process level.
- End with findings first, then commands executed, then residual risks.
"@
}
else {
@"
You are an external Claude Code development worker running through Xiaomi MiMo.

Rules:
- Work only inside the provided workdir.
- Make the requested code changes directly in that worktree.
- Reuse existing code and keep the diff as small as possible.
- Run focused verification when practical.
- Treat the requested sandbox level as a hard intent even though this wrapper does not enforce it at the process level.
- End with a concise summary that lists changed files and verification.
"@
}

$workerPrompt = @"
$instructions

Execution context:
- Workdir: $resolvedWorkdir
- Mode: $Mode
- Sandbox intent: $Sandbox
- Model: $Model

User task:
$Prompt
"@

Set-Content -LiteralPath $promptFile -Value $workerPrompt -Encoding utf8

$escapedClaudePath = Escape-SingleQuoted -Value $claudePath
$escapedWorkdir = Escape-SingleQuoted -Value $resolvedWorkdir
$escapedPromptFile = Escape-SingleQuoted -Value $promptFile
$escapedStderrFile = Escape-SingleQuoted -Value $stderrFile
$escapedLastMessageFile = Escape-SingleQuoted -Value $lastMessageFile
$escapedBeforeStatusFile = Escape-SingleQuoted -Value $beforeStatusFile
$escapedAfterStatusFile = Escape-SingleQuoted -Value $afterStatusFile
$escapedStatusWarningFile = Escape-SingleQuoted -Value $statusWarningFile
$escapedModel = Escape-SingleQuoted -Value $Model

$runner = @"
`$ErrorActionPreference = 'Stop'
`$claudePath = '$escapedClaudePath'
`$workdir = '$escapedWorkdir'
`$promptFile = '$escapedPromptFile'
`$stderrFile = '$escapedStderrFile'
`$lastMessageFile = '$escapedLastMessageFile'
`$beforeStatusFile = '$escapedBeforeStatusFile'
`$afterStatusFile = '$escapedAfterStatusFile'
`$statusWarningFile = '$escapedStatusWarningFile'
`$model = '$escapedModel'

`$env:ANTHROPIC_API_KEY = `$null
`$env:ANTHROPIC_AUTH_TOKEN = [Environment]::GetEnvironmentVariable('ANTHROPIC_AUTH_TOKEN', 'User')
`$env:ANTHROPIC_BASE_URL = [Environment]::GetEnvironmentVariable('ANTHROPIC_BASE_URL', 'User')
if (-not `$env:ANTHROPIC_AUTH_TOKEN) {
    throw 'ANTHROPIC_AUTH_TOKEN is not set in the user environment.'
}
if (-not `$env:ANTHROPIC_BASE_URL) {
    throw 'ANTHROPIC_BASE_URL is not set in the user environment.'
}
`$env:ANTHROPIC_MODEL = `$model
`$env:ANTHROPIC_DEFAULT_SONNET_MODEL = `$model
`$env:ANTHROPIC_DEFAULT_OPUS_MODEL = `$model
`$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = `$model

Set-Location -LiteralPath `$workdir
`$hasGitRepo = `$false
if (Get-Command git -ErrorAction SilentlyContinue) {
    & git rev-parse --is-inside-work-tree 1>`$null 2>`$null
    if (`$LASTEXITCODE -eq 0) {
        `$hasGitRepo = `$true
    }
}

if (`$hasGitRepo) {
    & git status --porcelain=v1 1>`$beforeStatusFile 2>>`$stderrFile
}

`$prompt = Get-Content -LiteralPath `$promptFile -Raw
`$args = @(
    '-p',
    '--output-format',
    'text',
    '--no-session-persistence',
    '--permission-mode',
    'bypassPermissions',
    '--model',
    `$model
)

`$prompt | & `$claudePath @args 1>`$lastMessageFile 2>`$stderrFile
`$exitCode = `$LASTEXITCODE

if (`$hasGitRepo) {
    Set-Location -LiteralPath `$workdir
    & git status --porcelain=v1 1>`$afterStatusFile 2>>`$stderrFile

    if ((Test-Path -LiteralPath `$beforeStatusFile) -and (Test-Path -LiteralPath `$afterStatusFile)) {
        `$before = Get-Content -LiteralPath `$beforeStatusFile -Raw
        `$after = Get-Content -LiteralPath `$afterStatusFile -Raw
        if (`$before -ne `$after) {
            Set-Content -LiteralPath `$statusWarningFile -Value 'Repository status changed during the MiMo worker run. Inspect the worktree before trusting the result.' -Encoding utf8
        }
    }
}

exit `$exitCode
"@

Set-Content -LiteralPath $runnerFile -Value $runner -Encoding utf8

$result = [ordered]@{
    mode = if ($Wait) { 'wait' } else { 'background' }
    worker_mode = $Mode
    job_name = $jobName
    job_dir = $jobDir
    workdir = $resolvedWorkdir
    sandbox = $Sandbox
    model = $Model
    prompt_file = $promptFile
    before_status_file = $beforeStatusFile
    after_status_file = $afterStatusFile
    status_warning_file = $statusWarningFile
    stderr_file = $stderrFile
    last_message_file = $lastMessageFile
}

if ($Wait) {
    & $pwshPath -NoLogo -NoProfile -File $runnerFile
    $result.exit_code = $LASTEXITCODE
}
else {
    $process = Start-Process -FilePath $pwshPath -ArgumentList @('-NoLogo', '-NoProfile', '-File', $runnerFile) -WindowStyle Hidden -PassThru
    $result.pid = $process.Id
}

$result | ConvertTo-Json -Depth 4
