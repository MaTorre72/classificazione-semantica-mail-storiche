from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SourceCandidate:
    path: Path
    file_type: str


def scan_local_folder(source: Path) -> list[SourceCandidate]:
    if source.is_file():
        return [_candidate_for_file(source)] if _candidate_for_file(source) else []

    candidates: list[SourceCandidate] = []
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        candidate = _candidate_for_file(path)
        if candidate:
            candidates.append(candidate)
    return candidates


def _candidate_for_file(path: Path) -> SourceCandidate | None:
    suffix = path.suffix.lower()
    if suffix == ".eml":
        return SourceCandidate(path=path, file_type="eml")
    if suffix in {".mbox", ".mbx"}:
        return SourceCandidate(path=path, file_type="mbox")
    if suffix == "" and path.name not in {"Inbox.msf", "Sent.msf"}:
        # Thunderbird mbox files often have no extension.
        try:
            first = path.open("rb").read(5)
        except OSError:
            return None
        if first == b"From ":
            return SourceCandidate(path=path, file_type="mbox")
    return None


def file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

