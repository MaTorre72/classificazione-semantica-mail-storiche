#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
LOCK_MINUTES="${LOCK_MINUTES:-120}"
SANDBOX="${SANDBOX:-workspace-write}"
CODEX_BIN="${CODEX_BIN:-codex}"
SKIP_QUALITY_CHECKS="${SKIP_QUALITY_CHECKS:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --lock-minutes) shift; LOCK_MINUTES="$1" ;;
    --sandbox) shift; SANDBOX="$1" ;;
    --codex-bin) shift; CODEX_BIN="$1" ;;
    --skip-quality-checks) SKIP_QUALITY_CHECKS=1 ;;
    *) echo "Argomento sconosciuto: $1" >&2; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${REPO_ROOT}/.codex/state"
RUNS_DIR="${REPO_ROOT}/.codex/runs"
BACKLOG_PATH="${STATE_DIR}/backlog.json"
RUN_LOG_PATH="${STATE_DIR}/run_log.md"
BLOCKED_PATH="${STATE_DIR}/blocked.md"
LOCK_PATH="${STATE_DIR}/run.lock"
TEMPLATE_PATH="${REPO_ROOT}/.codex/prompts/next_task.md"
QUALITY_SCRIPT="${REPO_ROOT}/scripts/run_quality_checks.sh"
GUARD_SCRIPT="${REPO_ROOT}/scripts/codex_guard.sh"

"${GUARD_SCRIPT}" || rc=$?
if [[ "${rc:-0}" == "10" ]]; then
  exit 0
elif [[ "${rc:-0}" != "0" ]]; then
  exit "${rc:-1}"
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
run_dir="${RUNS_DIR}/${timestamp}"
mkdir -p "${run_dir}"

candidate_json="$(python3 - <<'PY' "${BACKLOG_PATH}"
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
tasks = data["tasks"]
done_ids = {t["id"] for t in tasks if t["status"] == "done"}
candidates = []
for task in tasks:
    if task["status"] == "done" or task.get("blocked"):
        continue
    deps = task.get("dependencies", [])
    if any(dep not in done_ids for dep in deps):
        continue
    candidates.append(task)
candidates.sort(key=lambda t: (t.get("priority_order", 9999), t["id"]))
print(json.dumps(candidates[0] if candidates else {}))
PY
)"

if [[ "${candidate_json}" == "{}" ]]; then
  echo "Nessun task candidabile nel backlog."
  exit 0
fi

task_id="$(python3 - <<'PY' "${candidate_json}"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "Dry-run: task selezionato ${task_id}"
  echo "Sandbox prevista: ${SANDBOX}"
  echo "Codex bin previsto: ${CODEX_BIN}"
  exit 0
fi

python3 - <<'PY' "${LOCK_PATH}" "${task_id}" "${run_dir}"
import json, sys
from datetime import datetime, timezone
from pathlib import Path
payload = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "task_id": sys.argv[2],
    "run_dir": sys.argv[3],
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

cleanup() {
  rm -f "${LOCK_PATH}"
}
trap cleanup EXIT

python3 - <<'PY' "${TEMPLATE_PATH}" "${candidate_json}" "${run_dir}/effective_prompt.md"
import json, sys
from pathlib import Path
template = Path(sys.argv[1]).read_text(encoding="utf-8")
task = json.loads(sys.argv[2])
mapping = {
    "{{TASK_ID}}": task["id"],
    "{{TASK_TITLE}}": task["title"],
    "{{TASK_AREA}}": task["area"],
    "{{TASK_PRIORITY}}": task["priority"],
    "{{TASK_DESCRIPTION}}": task["description"],
    "{{TASK_TESTS}}": "; ".join(task.get("tests_to_add", [])),
    "{{TASK_ACCEPTANCE}}": "; ".join(task.get("acceptance_criteria", [])),
}
for key, value in mapping.items():
    template = template.replace(key, value)
Path(sys.argv[3]).write_text(template, encoding="utf-8")
PY

stdout_path="${run_dir}/codex.stdout.log"
stderr_path="${run_dir}/codex.stderr.log"
quality_path="${run_dir}/quality.log"
summary_path="${run_dir}/summary.json"

if ! "${CODEX_BIN}" exec --sandbox "${SANDBOX}" --prompt-file "${run_dir}/effective_prompt.md" >"${stdout_path}" 2>"${stderr_path}"; then
  {
    echo
    echo "## $(date -Iseconds)"
    echo "- Task: ${task_id}"
    echo "- Sintomo: codex exec fallito"
    echo "- Impatto: ciclo interrotto prima dei quality checks"
    echo "- Prossima mossa sicura: verificare binario Codex e prompt generato in ${run_dir}"
  } >> "${BLOCKED_PATH}"
  exit 1
fi

if [[ "${SKIP_QUALITY_CHECKS}" != "1" ]]; then
  "${QUALITY_SCRIPT}" | tee "${quality_path}"
fi

python3 - <<'PY' "${BACKLOG_PATH}" "${task_id}" "${timestamp}"
import json, sys
from datetime import datetime
from pathlib import Path
path = Path(sys.argv[1])
task_id = sys.argv[2]
timestamp = sys.argv[3]
data = json.loads(path.read_text(encoding="utf-8"))
for task in data["tasks"]:
    if task["id"] == task_id and task["status"] == "pending":
        task["status"] = "in_progress"
        task["last_cycle_note"] = f"Selezionato automaticamente il {datetime.now().isoformat(timespec='seconds')}. Verifica esito nei log di .codex/runs/{timestamp}."
path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
PY

python3 - <<'PY' "${summary_path}" "${candidate_json}" "${run_dir}"
import json, sys
from datetime import datetime, timezone
from pathlib import Path
task = json.loads(sys.argv[2])
payload = {
    "run_at": datetime.now(timezone.utc).isoformat(),
    "task_id": task["id"],
    "task_title": task["title"],
    "run_dir": sys.argv[3],
    "dry_run": False,
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
PY

{
  echo
  echo "## $(date '+%Y-%m-%d %H:%M:%S') - autonomous cycle"
  echo
  echo "- Task: \`${task_id}\`"
  echo "- Esito: executed"
  echo "- Run dir: \`.codex/runs/${timestamp}\`"
  echo "- Note: completata esecuzione non interattiva; controllare diff e quality log."
} >> "${RUN_LOG_PATH}"
