param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [Parameter(Mandatory = $true)]
    [string]$Branch,

    [Parameter(Mandatory = $true)]
    [string]$Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$InputPath)
    return [System.IO.Path]::GetFullPath($InputPath)
}

$repoPath = (Resolve-Path -LiteralPath $Repo).Path
$worktreePath = Resolve-FullPath -InputPath $Path
$parentPath = Split-Path -Parent $worktreePath

if (-not (Test-Path -LiteralPath $parentPath)) {
    throw "Parent directory does not exist: $parentPath"
}

if (Test-Path -LiteralPath $worktreePath) {
    $existing = Get-ChildItem -Force -LiteralPath $worktreePath -ErrorAction SilentlyContinue
    if ($existing) {
        throw "Target worktree path is not empty: $worktreePath"
    }
}

Push-Location -LiteralPath $repoPath
try {
    & git rev-parse --show-toplevel 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Not a git repository: $repoPath"
    }

    & git show-ref --verify --quiet "refs/heads/$Branch"
    $branchExists = $LASTEXITCODE -eq 0

    $args = @('worktree', 'add', $worktreePath)
    if ($branchExists) {
        $args += $Branch
    }
    else {
        $args += @('-b', $Branch)
    }

    & git @args
    if ($LASTEXITCODE -ne 0) {
        throw "git worktree add failed"
    }
}
finally {
    Pop-Location
}

[ordered]@{
    repo = $repoPath
    branch = $Branch
    branch_exists = $branchExists
    worktree = $worktreePath
} | ConvertTo-Json -Depth 3
