param(
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$atlas = Join-Path $repoRoot ".venv\Scripts\email-atlas.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python venv non trovato: $python"
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Host "==> $Name"
    & $Action
}

Invoke-Step -Name "ruff" -Action {
    & $python -m ruff check src tests
}

Invoke-Step -Name "pytest" -Action {
    & $python -m pytest
}

Invoke-Step -Name "email-atlas-help" -Action {
    & $atlas --help | Out-Null
}

if (-not $SkipSmoke) {
    Invoke-Step -Name "email-atlas-smoke-test" -Action {
        & $atlas smoke-test | Out-Null
    }
}

Invoke-Step -Name "forbidden-large-files" -Action {
    $changed = git status --porcelain | ForEach-Object {
        if ($_.Length -ge 4) { $_.Substring(3).Trim() }
    } | Where-Object { $_ }
    foreach ($path in $changed) {
        $full = Join-Path $repoRoot $path
        if (Test-Path -LiteralPath $full -PathType Leaf) {
            $sizeMb = (Get-Item -LiteralPath $full).Length / 1MB
            if ($sizeMb -gt 10) {
                throw "File modificato troppo grande (>10MB): $path"
            }
        }
    }
}

Invoke-Step -Name "secret-check" -Action {
    $changed = git status --porcelain | ForEach-Object {
        if ($_.Length -ge 4) { $_.Substring(3).Trim() }
    } | Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $repoRoot $_) -PathType Leaf) }
    if (-not $changed) {
        return
    }
    $patterns = @(
        "BEGIN PRIVATE KEY",
        "OPENAI_API_KEY",
        "password\\s*=",
        "api[_-]?key\\s*="
    )
    foreach ($path in $changed) {
        if ($path -like "workspace_studio_email/*" -or $path -like "mail/*" -or $path -like "data/*" -or $path -like "outputs/*" -or $path -like "reports/*") {
            continue
        }
        foreach ($pattern in $patterns) {
            rg -n $pattern -- $path | Out-Null
            if ($LASTEXITCODE -eq 0) {
                throw "Possibile segreto rilevato con pattern: $pattern in $path"
            }
        }
    }
}

Invoke-Step -Name "forbidden-surfaces" -Action {
    $changed = git diff --name-only
    if ($changed) {
        $content = git diff -- . ':!workspace_studio_email' ':!mail' ':!data'
        $patterns = @("streamlit", "gradio", "gmail live", "openai api", "imaplib")
        foreach ($pattern in $patterns) {
            if ($content -match $pattern) {
                throw "Rilevata possibile superficie non desiderata nel diff: $pattern"
            }
        }
    }
}

Write-Host "Quality checks OK"
