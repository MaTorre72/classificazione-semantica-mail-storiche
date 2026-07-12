#!/usr/bin/env bash
set -euo pipefail

LOCK_MINUTES="${LOCK_MINUTES:-120}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${REPO_ROOT}/.codex/state"
LOCK_PATH="${STATE_DIR}/run.lock"
BACKLOG_PATH="${STATE_DIR}/backlog.json"

if [[ ! -d "${STATE_DIR}" ]]; then
  echo "Manca la cartella stato: ${STATE_DIR}" >&2
  exit 1
fi

if [[ ! -f "${BACKLOG_PATH}" ]]; then
  echo "Manca il backlog persistente: ${BACKLOG_PATH}" >&2
  exit 1
fi

if [[ -f "${LOCK_PATH}" ]]; then
  started_at="$(python3 - <<'PY' "${LOCK_PATH}"
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["started_at"])
PY
)"
  age_minutes="$(python3 - <<'PY' "${started_at}"
from datetime import datetime, timezone
import sys
started = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
delta = datetime.now(timezone.utc) - started
print(delta.total_seconds() / 60)
PY
)"
  age_int="${age_minutes%.*}"
  if (( age_int < LOCK_MINUTES )); then
    echo "Run in corso o recente rilevata (${age_minutes} minuti). Esco senza avviare un nuovo ciclo."
    exit 10
  fi
  echo "Lock stale rilevato da ${age_minutes} minuti. Verifica la run precedente prima di continuare." >&2
  exit 2
fi

echo "Guard OK: backlog presente, nessun lock attivo."
