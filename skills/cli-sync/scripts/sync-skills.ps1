param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'pull', 'push')]
    [string]$Mode,

    [string]$Message = 'Sync local Codex skills'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$skillRoot = Split-Path -Parent $PSScriptRoot
$defaultConfigPath = Join-Path $HOME '.codex\cli-sync\auth.ps1'
$defaultManagedSkills = @(
    'cli-arc',
    'cli-des',
    'cli-dev',
    'cli-init',
    'cli-pm',
    'cli-sync',
    'cli-test',
    'figma'
)

function Load-Config {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing cli-sync auth config: $Path"
    }

    $config = & $Path
    if (-not ($config -is [System.Collections.IDictionary])) {
        throw "The auth config must return a hashtable: $Path"
    }

    foreach ($key in @('GitHubUsername', 'GitHubToken', 'RemoteUrl', 'RepoPath', 'LocalSkillsPath')) {
        if (-not $config.Contains($key) -or [string]::IsNullOrWhiteSpace([string]$config[$key])) {
            throw "Missing required config value '$key' in $Path"
        }
    }

    if (-not $config.Contains('Branch') -or [string]::IsNullOrWhiteSpace([string]$config['Branch'])) {
        $config['Branch'] = 'main'
    }

    if (-not $config.Contains('ManagedSkills') -or @($config['ManagedSkills']).Count -eq 0) {
        $config['ManagedSkills'] = $defaultManagedSkills
    }

    return $config
}

function Resolve-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label does not exist: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function New-BasicAuthHeader {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Username,

        [Parameter(Mandatory = $true)]
        [string]$Token
    )

    $pair = '{0}:{1}' -f $Username, $Token
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($pair)
    $encoded = [Convert]::ToBase64String($bytes)
    return "AUTHORIZATION: basic $encoded"
}

function Invoke-GitAuth {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Config,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $header = New-BasicAuthHeader -Username $Config['GitHubUsername'] -Token $Config['GitHubToken']
    & git -C $Config['RepoPath'] -c ("http.extraheader={0}" -f $header) @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $exitCode."
    }
}

function Ensure-RepoCheckout {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Config
    )

    if (Test-Path -LiteralPath (Join-Path $Config['RepoPath'] '.git')) {
        return
    }

    throw "Configured repo path is not a git checkout: $($Config['RepoPath'])"
}

function Ensure-OriginRemote {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Config
    )

    $originUrl = & git -C $Config['RepoPath'] remote get-url origin 2>$null
    if ($LASTEXITCODE -ne 0) {
        & git -C $Config['RepoPath'] remote add origin $Config['RemoteUrl']
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to add origin remote.'
        }
        return
    }

    if ($originUrl.Trim() -ne $Config['RemoteUrl']) {
        & git -C $Config['RepoPath'] remote set-url origin $Config['RemoteUrl']
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to update origin remote.'
        }
    }
}

function Invoke-Mirror {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        return $false
    }

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $args = @(
        $Source,
        $Destination,
        '/MIR',
        '/R:1',
        '/W:1',
        '/NFL',
        '/NDL',
        '/NJH',
        '/NJS',
        '/NP'
    )

    & robocopy @args | Out-Null
    $exitCode = $LASTEXITCODE
    if ($exitCode -ge 8) {
        throw "robocopy failed for $Source -> $Destination with exit code $exitCode."
    }

    return $true
}

function Sync-LocalToRepo {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Config
    )

    $synced = [System.Collections.Generic.List[string]]::new()
    foreach ($skillName in $Config['ManagedSkills']) {
        $source = Join-Path $Config['LocalSkillsPath'] $skillName
        $destination = Join-Path (Join-Path $Config['RepoPath'] 'skills') $skillName
        if (Invoke-Mirror -Source $source -Destination $destination) {
            [void]$synced.Add($skillName)
        }
    }
    return $synced
}

function Sync-RepoToLocal {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Config
    )

    $synced = [System.Collections.Generic.List[string]]::new()
    foreach ($skillName in $Config['ManagedSkills']) {
        $source = Join-Path (Join-Path $Config['RepoPath'] 'skills') $skillName
        $destination = Join-Path $Config['LocalSkillsPath'] $skillName
        if (Invoke-Mirror -Source $source -Destination $destination) {
            [void]$synced.Add($skillName)
        }
    }
    return $synced
}

function Get-GitStatusText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoPath
    )

    $lines = & git -C $RepoPath status --short --branch
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to read git status.'
    }
    return ($lines -join "`n")
}

$config = Load-Config -Path $defaultConfigPath
$config['RepoPath'] = Resolve-Directory -Path $config['RepoPath'] -Label 'Repo path'
$config['LocalSkillsPath'] = Resolve-Directory -Path $config['LocalSkillsPath'] -Label 'Local skills path'

Ensure-RepoCheckout -Config $config
Ensure-OriginRemote -Config $config

$result = [ordered]@{
    mode = $Mode
    repo_path = $config['RepoPath']
    local_skills_path = $config['LocalSkillsPath']
    remote_url = $config['RemoteUrl']
    branch = $config['Branch']
    managed_skills = @($config['ManagedSkills'])
}

switch ($Mode) {
    'status' {
        $result['git_status'] = Get-GitStatusText -RepoPath $config['RepoPath']
    }

    'pull' {
        Invoke-GitAuth -Config $config -Arguments @('pull', '--ff-only', 'origin', $config['Branch'])
        $result['synced_skills'] = @(Sync-RepoToLocal -Config $config)
        $result['git_status'] = Get-GitStatusText -RepoPath $config['RepoPath']
    }

    'push' {
        Invoke-GitAuth -Config $config -Arguments @('pull', '--ff-only', 'origin', $config['Branch'])
        $result['synced_skills'] = @(Sync-LocalToRepo -Config $config)

        & git -C $config['RepoPath'] add -A
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to stage repository changes.'
        }

        & git -C $config['RepoPath'] diff --cached --quiet
        $diffExitCode = $LASTEXITCODE

        if ($diffExitCode -eq 0) {
            $result['commit_created'] = $false
        }
        elseif ($diffExitCode -eq 1) {
            & git -C $config['RepoPath'] commit -m $Message
            if ($LASTEXITCODE -ne 0) {
                throw 'Failed to create commit.'
            }
            Invoke-GitAuth -Config $config -Arguments @('push', 'origin', $config['Branch'])
            $result['commit_created'] = $true
            $result['commit_message'] = $Message
        }
        else {
            throw 'Failed to inspect staged changes.'
        }

        $result['git_status'] = Get-GitStatusText -RepoPath $config['RepoPath']
    }
}

$result | ConvertTo-Json -Depth 6
