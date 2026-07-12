param(
    [switch]$DryRun,
    [int]$LockMinutes = 120,
    [string]$Sandbox = "workspace-write",
    [string]$CodexBin = $env:CODEX_BIN,
    [switch]$SkipQualityChecks
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($CodexBin)) {
    $CodexBin = "codex"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$stateDir = Join-Path $repoRoot ".codex\state"
$runsDir = Join-Path $repoRoot ".codex\runs"
$backlogPath = Join-Path $stateDir "backlog.json"
$runLogPath = Join-Path $stateDir "run_log.md"
$blockedPath = Join-Path $stateDir "blocked.md"
$lockPath = Join-Path $stateDir "run.lock"
$templatePath = Join-Path $repoRoot ".codex\prompts\next_task.md"
$qualityScript = Join-Path $repoRoot "scripts\run_quality_checks.ps1"
$guardScript = Join-Path $repoRoot "scripts\codex_guard.ps1"

& $guardScript -LockMinutes $LockMinutes
if ($LASTEXITCODE -eq 10) {
    exit 0
}

$backlog = Get-Content -LiteralPath $backlogPath -Raw | ConvertFrom-Json
$tasks = @($backlog.tasks)
$doneIds = @($tasks | Where-Object { $_.status -eq "done" } | ForEach-Object { $_.id })

$priorityMap = @{
    "P0" = 0
    "P1" = 1
    "P2" = 2
    "P3" = 3
}

$candidate = $tasks |
    Where-Object {
        $_.status -ne "done" -and
        -not $_.blocked -and
        (@($_.dependencies) | Where-Object { $_ -notin $doneIds }).Count -eq 0
    } |
    Sort-Object @{ Expression = { $_.priority_order } }, @{ Expression = { $priorityMap[$_.priority] } }, @{ Expression = { $_.id } } |
    Select-Object -First 1

if (-not $candidate) {
    Write-Host "Nessun task candidabile nel backlog."
    exit 0
}

$previewPrompt = Get-Content -LiteralPath $templatePath -Raw
$previewReplacements = @{
    "{{TASK_ID}}" = [string]$candidate.id
    "{{TASK_TITLE}}" = [string]$candidate.title
    "{{TASK_AREA}}" = [string]$candidate.area
    "{{TASK_PRIORITY}}" = [string]$candidate.priority
    "{{TASK_DESCRIPTION}}" = [string]$candidate.description
    "{{TASK_TESTS}}" = (@($candidate.tests_to_add) -join "; ")
    "{{TASK_ACCEPTANCE}}" = (@($candidate.acceptance_criteria) -join "; ")
}
foreach ($key in $previewReplacements.Keys) {
    $previewPrompt = $previewPrompt.Replace($key, $previewReplacements[$key])
}

if ($DryRun) {
    Write-Host "Dry-run: task selezionato $($candidate.id) - $($candidate.title)"
    Write-Host "Sandbox prevista: $Sandbox"
    Write-Host "Codex bin previsto: $CodexBin"
    exit 0
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $runsDir $timestamp
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$lock = @{
    started_at = [datetimeoffset]::UtcNow.ToString("o")
    task_id = $candidate.id
    run_dir = $runDir
} | ConvertTo-Json
Set-Content -LiteralPath $lockPath -Value $lock -Encoding UTF8

try {
    $effectivePrompt = Join-Path $runDir "effective_prompt.md"
    Set-Content -LiteralPath $effectivePrompt -Value $previewPrompt -Encoding UTF8

    $stdoutPath = Join-Path $runDir "codex.stdout.log"
    $stderrPath = Join-Path $runDir "codex.stderr.log"
    $qualityPath = Join-Path $runDir "quality.log"
    $summaryPath = Join-Path $runDir "summary.json"

    $args = @("exec", "--sandbox", $Sandbox, "--prompt-file", $effectivePrompt)
    $process = Start-Process -FilePath $CodexBin -ArgumentList $args -WorkingDirectory $repoRoot -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

    if ($process.ExitCode -ne 0) {
        Add-Content -LiteralPath $blockedPath -Value "`n## $(Get-Date -Format s)`n- Task: $($candidate.id)`n- Sintomo: codex exec exit code $($process.ExitCode)`n- Impatto: ciclo interrotto prima dei quality checks`n- Prossima mossa sicura: verificare binario Codex e prompt generato in $runDir`n"
        throw "Codex fallito con exit code $($process.ExitCode)"
    }

    if (-not $SkipQualityChecks) {
        & $qualityScript *>&1 | Tee-Object -FilePath $qualityPath
    }

    foreach ($task in $tasks) {
        if ($task.id -eq $candidate.id -and $task.status -eq "pending") {
            $task.status = "in_progress"
            $task.last_cycle_note = "Selezionato automaticamente il $(Get-Date -Format s). Verifica esito nei log di .codex/runs/$timestamp."
        }
    }
    $backlog | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $backlogPath -Encoding UTF8

    $summary = @{
        run_at = [datetimeoffset]::UtcNow.ToString("o")
        task_id = $candidate.id
        task_title = $candidate.title
        run_dir = $runDir
        dry_run = $false
        quality_checks = (-not $SkipQualityChecks)
    } | ConvertTo-Json
    Set-Content -LiteralPath $summaryPath -Value $summary -Encoding UTF8

    Add-Content -LiteralPath $runLogPath -Value "`n## $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - autonomous cycle`n`n- Task: ``$($candidate.id)`` - $($candidate.title)`n- Esito: executed`n- Run dir: ``.codex/runs/$timestamp`` `n- Note: completata esecuzione non interattiva; controllare diff e quality log.`n"
}
finally {
    if (Test-Path -LiteralPath $lockPath) {
        Remove-Item -LiteralPath $lockPath -Force
    }
}
