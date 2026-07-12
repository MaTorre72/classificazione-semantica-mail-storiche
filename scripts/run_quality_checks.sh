#!/usr/bin/env bash
set -euo pipefail

SKIP_SMOKE="${SKIP_SMOKE:-0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${REPO_ROOT}/.venv/Scripts/python.exe"
ATLAS_BIN="${REPO_ROOT}/.venv/Scripts/email-atlas.exe"

run_step() {
  local name="$1"
  shift
  echo "==> ${name}"
  "$@"
}

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python venv non trovato: ${PYTHON_BIN}" >&2
  exit 1
fi

run_step "ruff" "${PYTHON_BIN}" -m ruff check src tests
run_step "pytest" "${PYTHON_BIN}" -m pytest
run_step "email-atlas-help" "${ATLAS_BIN}" --help >/dev/null

if [[ "${SKIP_SMOKE}" != "1" ]]; then
  run_step "email-atlas-smoke-test" "${ATLAS_BIN}" smoke-test >/dev/null
fi

echo "==> forbidden-large-files"
while IFS= read -r path; do
  [[ -z "${path}" ]] && continue
  if [[ -f "${REPO_ROOT}/${path}" ]]; then
    size_bytes="$(wc -c < "${REPO_ROOT}/${path}")"
    if (( size_bytes > 10485760 )); then
      echo "File modificato troppo grande (>10MB): ${path}" >&2
      exit 1
    fi
  fi
done < <(git status --porcelain | awk '{print substr($0,4)}')

echo "==> secret-check"
while IFS= read -r path; do
  [[ -z "${path}" ]] && continue
  case "${path}" in
    workspace_studio_email/*|mail/*|data/*|outputs/*|reports/*) continue ;;
  esac
  for pattern in "BEGIN PRIVATE KEY" "OPENAI_API_KEY" "password\\s*=" "api[_-]?key\\s*="; do
    if rg -n "${pattern}" -- "${path}" >/dev/null; then
      echo "Possibile segreto rilevato con pattern: ${pattern} in ${path}" >&2
      exit 1
    fi
  done
done < <(git status --porcelain | awk '{print substr($0,4)}')

echo "==> forbidden-surfaces"
if git diff --name-only | grep -q .; then
  diff_content="$(git diff -- . ':(exclude)workspace_studio_email' ':(exclude)mail' ':(exclude)data' || true)"
  for pattern in "streamlit" "gradio" "gmail live" "openai api" "imaplib"; do
    if grep -qi "${pattern}" <<< "${diff_content}"; then
      echo "Rilevata possibile superficie non desiderata nel diff: ${pattern}" >&2
      exit 1
    fi
  done
fi

echo "Quality checks OK"
