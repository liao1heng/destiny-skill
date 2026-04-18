param(
    [Parameter(Mandatory = $true)]
    [string]$Workdir,

    [Parameter(Mandatory = $true)]
    [string]$Prompt,

    [string]$Name,

    [switch]$Wait
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$fixedModel = 'gpt-5.3-codex'

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

$null = Get-Command codex -ErrorAction Stop
$pwshPath = (Get-Command pwsh -ErrorAction Stop).Source
$resolvedWorkdir = (Resolve-Path -LiteralPath $Workdir).Path
$jobName = New-JobName -Prefix 'dev' -RawName $Name
$jobDir = Join-Path $HOME ".codex\jobs\$jobName"

New-Item -ItemType Directory -Force -Path $jobDir | Out-Null

$promptFile = Join-Path $jobDir 'prompt.txt'
$runnerFile = Join-Path $jobDir 'runner.ps1'
$eventsFile = Join-Path $jobDir 'events.jsonl'
$stderrFile = Join-Path $jobDir 'stderr.log'
$lastMessageFile = Join-Path $jobDir 'last-message.txt'

$workerPrompt = @"
You are an external Codex CLI implementation worker.

Rules:
- Work only inside the provided workdir.
- Make the requested code changes directly in that worktree.
- Reuse existing code and keep the diff as small as possible.
- Run focused verification when practical.
- End with a concise summary that lists changed files and verification.

User task:
$Prompt
"@

Set-Content -LiteralPath $promptFile -Value $workerPrompt -Encoding utf8

$escapedWorkdir = Escape-SingleQuoted -Value $resolvedWorkdir
$escapedPromptFile = Escape-SingleQuoted -Value $promptFile
$escapedEventsFile = Escape-SingleQuoted -Value $eventsFile
$escapedStderrFile = Escape-SingleQuoted -Value $stderrFile
$escapedLastMessageFile = Escape-SingleQuoted -Value $lastMessageFile
$escapedModel = Escape-SingleQuoted -Value $fixedModel

$runner = @"
`$ErrorActionPreference = 'Stop'
`$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY', 'User')
`$workdir = '$escapedWorkdir'
`$promptFile = '$escapedPromptFile'
`$eventsFile = '$escapedEventsFile'
`$stderrFile = '$escapedStderrFile'
`$lastMessageFile = '$escapedLastMessageFile'
`$model = '$escapedModel'

Set-Location -LiteralPath `$workdir
`$args = @('-a', 'never', 'exec', '-C', `$workdir, '-s', 'workspace-write', '-m', `$model)
`$args += @('--json', '-o', `$lastMessageFile, '-')

Get-Content -LiteralPath `$promptFile -Raw | & codex @args 1>`$eventsFile 2>`$stderrFile
exit `$LASTEXITCODE
"@

Set-Content -LiteralPath $runnerFile -Value $runner -Encoding utf8

$result = [ordered]@{
    mode = if ($Wait) { 'wait' } else { 'background' }
    job_name = $jobName
    job_dir = $jobDir
    workdir = $resolvedWorkdir
    model = $fixedModel
    prompt_file = $promptFile
    events_file = $eventsFile
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
