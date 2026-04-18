param(
    [Parameter(Mandatory = $true)]
    [string]$Workdir,

    [Parameter(Mandatory = $true)]
    [string]$Prompt,

    [string]$Name,

    [ValidateSet('read-only', 'workspace-write', 'danger-full-access')]
    [string]$Sandbox = 'read-only',

    [string]$Model,

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

$localBin = Join-Path $HOME '.local\bin'
if (Test-Path -LiteralPath $localBin) {
    $env:PATH = "$localBin;$env:PATH"
}

$kimiPath = (Get-Command kimi -ErrorAction Stop).Source
$pwshPath = (Get-Command pwsh -ErrorAction Stop).Source
$resolvedWorkdir = (Resolve-Path -LiteralPath $Workdir).Path
$jobName = New-JobName -Prefix 'test' -RawName $Name
$jobDir = Join-Path $HOME ".codex\jobs\$jobName"

New-Item -ItemType Directory -Force -Path $jobDir | Out-Null

$promptFile = Join-Path $jobDir 'prompt.txt'
$runnerFile = Join-Path $jobDir 'runner.ps1'
$eventsFile = Join-Path $jobDir 'events.jsonl'
$stderrFile = Join-Path $jobDir 'stderr.log'
$lastMessageFile = Join-Path $jobDir 'last-message.txt'
$beforeStatusFile = Join-Path $jobDir 'before-status.txt'
$afterStatusFile = Join-Path $jobDir 'after-status.txt'
$statusWarningFile = Join-Path $jobDir 'status-warning.txt'
$mcpConfigFile = Join-Path $jobDir 'mcp.json'

$workerPrompt = @"
You are an external Kimi CLI verification worker.

Rules:
- Do not modify repository files unless the user explicitly asked for a fix.
- Focus on review, tests, regression checks, and concise findings.
- Run the smallest useful command set.
- Prefer browser-based validation over blind reasoning for UI or web flows.
- Treat the requested sandbox level as a hard intent even though the wrapper does not enforce it at the process level.
- If browser interaction is relevant, prefer the configured browser tools first:
  1. Playwright MCP for scripted browser validation.
  2. Chrome DevTools MCP for direct inspection.
- If MCP is not enough and shell access is needed, use the installed Playwright CLI.
- If the user asks for screenshots, save them to explicit file paths and mention those paths in the final answer.
- End with findings first, then commands executed, then residual risks.

User task:
$Prompt
"@

Set-Content -LiteralPath $promptFile -Value $workerPrompt -Encoding utf8

$mcpConfig = [ordered]@{
    mcpServers = [ordered]@{
        'chrome-devtools' = [ordered]@{
            command = 'C:\Users\nvm\v20.19.0\node.exe'
            args = @(
                'C:\Users\the5010_566029155562\.codex\mcp\chrome-devtools\node_modules\chrome-devtools-mcp\build\src\index.js',
                '--logFile',
                'C:\Users\the5010_566029155562\AppData\Local\Temp\chrome-devtools-mcp.log',
                '--channel',
                'stable'
            )
            env = [ordered]@{
                PROGRAMFILES = 'C:\Program Files'
                SystemRoot = 'C:\Windows'
            }
        }
        'playwright' = [ordered]@{
            command = 'C:\nvm4w\nodejs\playwright-mcp.cmd'
            args = @('--headless', '--isolated')
        }
    }
}
Set-Content -LiteralPath $mcpConfigFile -Value ($mcpConfig | ConvertTo-Json -Depth 8) -Encoding utf8

$escapedWorkdir = Escape-SingleQuoted -Value $resolvedWorkdir
$escapedPromptFile = Escape-SingleQuoted -Value $promptFile
$escapedEventsFile = Escape-SingleQuoted -Value $eventsFile
$escapedStderrFile = Escape-SingleQuoted -Value $stderrFile
$escapedLastMessageFile = Escape-SingleQuoted -Value $lastMessageFile
$escapedBeforeStatusFile = Escape-SingleQuoted -Value $beforeStatusFile
$escapedAfterStatusFile = Escape-SingleQuoted -Value $afterStatusFile
$escapedStatusWarningFile = Escape-SingleQuoted -Value $statusWarningFile
$escapedMcpConfigFile = Escape-SingleQuoted -Value $mcpConfigFile
$escapedKimiPath = Escape-SingleQuoted -Value $kimiPath
$escapedModel = Escape-SingleQuoted -Value $Model
$escapedSandbox = Escape-SingleQuoted -Value $Sandbox

$runner = @"
`$ErrorActionPreference = 'Stop'
`$localBin = Join-Path `$HOME '.local\bin'
if (Test-Path -LiteralPath `$localBin) {
    `$env:PATH = "`$localBin;`$env:PATH"
}
`$env:KIMI_API_KEY = [Environment]::GetEnvironmentVariable('KIMI_API_KEY', 'User')
if (-not `$env:KIMI_API_KEY) {
    throw 'KIMI_API_KEY is not set in the user environment.'
}
`$kimiPath = '$escapedKimiPath'
`$workdir = '$escapedWorkdir'
`$promptFile = '$escapedPromptFile'
`$eventsFile = '$escapedEventsFile'
`$stderrFile = '$escapedStderrFile'
`$lastMessageFile = '$escapedLastMessageFile'
`$beforeStatusFile = '$escapedBeforeStatusFile'
`$afterStatusFile = '$escapedAfterStatusFile'
`$statusWarningFile = '$escapedStatusWarningFile'
`$mcpConfigFile = '$escapedMcpConfigFile'
`$model = '$escapedModel'
`$sandbox = '$escapedSandbox'

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
`$args = @('--print', '--output-format', 'stream-json', '-w', `$workdir, '--mcp-config-file', `$mcpConfigFile, '-p', `$prompt)
if (`$model) {
    `$args += @('-m', `$model)
}

& `$kimiPath @args 1>`$eventsFile 2>`$stderrFile
`$exitCode = `$LASTEXITCODE

if (Test-Path -LiteralPath `$eventsFile) {
    `$assistantTexts = [System.Collections.Generic.List[string]]::new()
    foreach (`$line in Get-Content -LiteralPath `$eventsFile) {
        if ([string]::IsNullOrWhiteSpace(`$line)) {
            continue
        }
        try {
            `$event = `$line | ConvertFrom-Json -Depth 32
        }
        catch {
            continue
        }

        if (`$event.role -ne 'assistant' -or -not `$event.content) {
            continue
        }

        foreach (`$part in `$event.content) {
            if (`$part.type -eq 'text' -and `$part.text) {
                [void]`$assistantTexts.Add([string]`$part.text)
            }
        }
    }

    if (`$assistantTexts.Count -gt 0) {
        Set-Content -LiteralPath `$lastMessageFile -Value (`$assistantTexts -join "`r`n") -Encoding utf8
    }
    elseif (-not (Test-Path -LiteralPath `$lastMessageFile)) {
        Set-Content -LiteralPath `$lastMessageFile -Value (Get-Content -LiteralPath `$eventsFile -Raw) -Encoding utf8
    }
}

if (`$hasGitRepo) {
    Set-Location -LiteralPath `$workdir
    & git status --porcelain=v1 1>`$afterStatusFile 2>>`$stderrFile

    if ((Test-Path -LiteralPath `$beforeStatusFile) -and (Test-Path -LiteralPath `$afterStatusFile)) {
        `$before = Get-Content -LiteralPath `$beforeStatusFile -Raw
        `$after = Get-Content -LiteralPath `$afterStatusFile -Raw
        if (`$before -ne `$after) {
            Set-Content -LiteralPath `$statusWarningFile -Value 'Repository status changed during verification. Inspect the worktree before trusting the result.' -Encoding utf8
        }
    }
}

exit `$exitCode
"@

Set-Content -LiteralPath $runnerFile -Value $runner -Encoding utf8

$result = [ordered]@{
    mode = if ($Wait) { 'wait' } else { 'background' }
    job_name = $jobName
    job_dir = $jobDir
    workdir = $resolvedWorkdir
    sandbox = $Sandbox
    prompt_file = $promptFile
    before_status_file = $beforeStatusFile
    after_status_file = $afterStatusFile
    status_warning_file = $statusWarningFile
    mcp_config_file = $mcpConfigFile
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
