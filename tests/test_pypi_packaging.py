from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import hotspot_editor
from anna import resource_root


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_version_dependency_modules_and_entry_point() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    setuptools = metadata["tool"]["setuptools"]

    assert project["version"] == "1.0.0"
    assert project["dependencies"] == ["PySide6==6.11.0"]
    assert project["gui-scripts"]["anna"] == "hotspot_editor:main"
    assert "hotspot_editor" in setuptools["py-modules"]
    assert setuptools["packages"] == ["anna"]


def test_packaged_resource_root_contains_complete_sample() -> None:
    root = resource_root()
    assert (root / "assets" / "app" / "ANNA.ico").is_file()
    assert (root / "assets" / "app" / "ANNA.png").is_file()
    assert (root / "demo_project" / "washing_hands.json").is_file()
    assert (root / "demo_project" / "videos" / "VID_20260906_121554.mp4").is_file()
    assert (root / "demo_project" / "videos" / "VID_20260906_121715.mp4").is_file()


def test_pip_install_uses_local_app_data_without_changing_source_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hotspot_editor, "SOURCE_CHECKOUT", False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    installed_root = hotspot_editor.application_data_root()

    assert installed_root == tmp_path / "ANNA"
    assert installed_root.is_dir()

    monkeypatch.setattr(hotspot_editor, "SOURCE_CHECKOUT", True)
    assert hotspot_editor.application_data_root() == hotspot_editor.ROOT
