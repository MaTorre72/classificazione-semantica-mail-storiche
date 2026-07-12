from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_codex_prompts_exist_for_native_and_scripted_runs() -> None:
    assert (REPO_ROOT / ".codex" / "prompts" / "automation_cycle.md").exists()
    assert (REPO_ROOT / ".codex" / "prompts" / "next_task.md").exists()


def test_non_interactive_doc_keeps_manual_integration_contract() -> None:
    content = (REPO_ROOT / "docs" / "non_interactive_codex.md").read_text(encoding="utf-8")

    assert ".codex/prompts/automation_cycle.md" in content
    assert ".codex/prompts/next_task.md" in content
    assert "manual integration required" in content


def test_codex_runners_point_to_expected_prompt_template() -> None:
    ps1 = (REPO_ROOT / "scripts" / "codex_next_task.ps1").read_text(encoding="utf-8")
    sh = (REPO_ROOT / "scripts" / "codex_next_task.sh").read_text(encoding="utf-8")

    assert '.codex\\prompts\\next_task.md' in ps1
    assert '.codex/prompts/next_task.md' in sh
