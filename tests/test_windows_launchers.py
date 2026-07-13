from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_LAUNCHERS = {
    "EMAIL_ATLAS.bat",
    "CREA_STUDIO.bat",
    "CONTROLLO_WORKSPACE.bat",
    "RIPARA_WORKSPACE.bat",
    "COSTRUISCI_ATLANTE.bat",
    "ESPORTA_ORANGE.bat",
    "AVVIA_CONSOLE.bat",
}


def test_only_current_windows_launchers_remain_at_repository_root() -> None:
    assert {path.name for path in REPO_ROOT.glob("*.bat")} == CURRENT_LAUNCHERS
    assert (REPO_ROOT / "archive" / "windows-launchers" / "start_gui.bat").is_file()


def test_main_menu_routes_to_every_specialized_launcher() -> None:
    menu = (REPO_ROOT / "EMAIL_ATLAS.bat").read_text(encoding="utf-8")

    for name in CURRENT_LAUNCHERS - {"EMAIL_ATLAS.bat"}:
        assert f"call {name}" in menu


def test_current_launchers_use_installed_cli_and_support_non_opening_smoke() -> None:
    for name in CURRENT_LAUNCHERS:
        content = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert content.startswith("@echo off")
        assert ".venv\\Scripts\\" in content

    for name in {
        "EMAIL_ATLAS.bat",
        "CREA_STUDIO.bat",
        "COSTRUISCI_ATLANTE.bat",
        "ESPORTA_ORANGE.bat",
        "AVVIA_CONSOLE.bat",
    }:
        content = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert "EMAIL_ATLAS_NO_OPEN" in content


def test_create_study_launcher_exposes_safe_conversation_rebuild() -> None:
    content = (REPO_ROOT / "CREA_STUDIO.bat").read_text(encoding="utf-8")

    assert "Ricostruire conversazioni con backup?" in content
    assert "--rebuild-stage build_conversations" in content
