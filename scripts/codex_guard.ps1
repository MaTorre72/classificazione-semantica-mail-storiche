param(
    [int]$LockMinutes = 120
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$stateDir = Join-Path $repoRoot ".codex\state"
$lockPath = Join-Path $stateDir "run.lock"
$backlogPath = Join-Path $stateDir "backlog.json"

if (-not (Test-Path -LiteralPath $stateDir)) {
    throw "Manca la cartella stato: $stateDir"
}

if (-not (Test-Path -LiteralPath $backlogPath)) {
    throw "Manca il backlog persistente: $backlogPath"
}

if (Test-Path -LiteralPath $lockPath) {
    $raw = Get-Content -LiteralPath $lockPath -Raw
    $lock = $raw | ConvertFrom-Json
    $startedAt = [datetimeoffset]::Parse($lock.started_at)
    $ageMinutes = ([datetimeoffset]::Now - $startedAt).TotalMinutes
    if ($ageMinutes -lt $LockMinutes) {
        Write-Host "Run in corso o recente rilevata ($([math]::Round($ageMinutes, 1)) minuti). Esco senza avviare un nuovo ciclo."
        exit 10
    }
    throw "Lock stale rilevato da $([math]::Round($ageMinutes, 1)) minuti. Verifica la run precedente prima di continuare."
}

Write-Host "Guard OK: backlog presente, nessun lock attivo."
