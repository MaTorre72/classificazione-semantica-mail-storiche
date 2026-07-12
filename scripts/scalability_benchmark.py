from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
import tracemalloc
from pathlib import Path

from email_cluster.atlas.smoke import _message
from email_cluster.atlas.workspace_study import run_study


def _csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def _generate_archive(root: Path, count: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        thread = index // 2
        reply = index % 2 == 1
        message_id = f"scale-{index}@example.invalid"
        parent = f"scale-{index - 1}@example.invalid" if reply else ""
        content = _message(
            "sender@example.invalid" if not reply else "atlas@example.invalid",
            "atlas@example.invalid" if not reply else "sender@example.invalid",
            f"{'Re: ' if reply else ''}Pratica sintetica {thread}",
            message_id,
            f"Messaggio sintetico locale {index}; pratica {thread}.",
            reply_to=parent,
        )
        (root / f"{index:05d}.eml").write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark locale ripetibile Email Atlas")
    parser.add_argument("--messages", type=int, default=10_000)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.messages < 10_000:
        parser.error("--messages deve essere almeno 10000 per il benchmark di accettazione")

    run_dir = args.run_dir.resolve()
    if run_dir.exists():
        shutil.rmtree(run_dir)
    archive = run_dir / "synthetic_archive"
    workspace = run_dir / "workspace"
    _generate_archive(archive, args.messages)

    tracemalloc.start()
    started = time.perf_counter()
    result = run_study(archive, workspace, attachments_text=False, resume=False)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    output_bytes = sum(path.stat().st_size for path in workspace.rglob("*") if path.is_file())
    metrics = {
        "messages_requested": args.messages,
        "messages_exported": _csv_rows(workspace / "messages.csv"),
        "conversations_exported": _csv_rows(workspace / "conversations.csv"),
        "elapsed_seconds": round(elapsed, 3),
        "python_peak_memory_mib": round(peak / 1024 / 1024, 3),
        "workspace_output_mib": round(output_bytes / 1024 / 1024, 3),
        "completed_stages": result.get("completed_stages", []),
    }
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
