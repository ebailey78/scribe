param()

# Get staged files
$changedFiles = git diff --cached --name-only
if (-not $changedFiles) {
    exit 0
}

$needsLog = $false
foreach ($file in $changedFiles) {
    switch -Wildcard ($file) {
        'src/*'         { $needsLog = $true }
        'config/*'      { $needsLog = $true }
        'pyproject.toml' { $needsLog = $true }
        'AGENTS.md'     { $needsLog = $true }
        'README.md'     { $needsLog = $true }
    }
}

if (-not $needsLog) {
    exit 0
}

if (-not ($changedFiles -contains 'AGENT_LOG.md')) {
    Write-Error 'Code/config/docs changes detected but AGENT_LOG.md is not updated.'
    Write-Error 'Please add an entry at the top of AGENT_LOG.md describing this change.'
    exit 1
}
