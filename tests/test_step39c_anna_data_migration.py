from __future__ import annotations

import csv
import json
from pathlib import Path

import localization
from data_storage import ensure_data_directory, preferences_path, users_path
from users_manager import UsersManager


USER_HEADER = [
    "id",
    "name",
    "notes",
    "group",
    "date_created",
    "last_session_date",
    "last_session_end",
    "total_sessions",
    "active",
]


def _write_users(path: Path, name: str = "Legacy") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=USER_HEADER)
        writer.writeheader()
        writer.writerow({"id": "1", "name": name, "active": "1"})


def test_new_install_creates_anna_data_and_persists_preferences_and_users(tmp_path: Path) -> None:
    data_dir = ensure_data_directory(tmp_path)

    assert data_dir == tmp_path / "anna_data"
    assert data_dir.is_dir()
    assert not (tmp_path / "lola_data").exists()

    localization.save_language(tmp_path, "es")
    assert preferences_path(tmp_path) == data_dir / "preferences.json"
    assert json.loads(preferences_path(tmp_path).read_text(encoding="utf-8")) == {"language": "es"}
    assert localization.load_language(tmp_path) == "es"

    manager = UsersManager(users_path(tmp_path))
    manager.create_user("P001")
    assert manager.csv_path == data_dir / "users.csv"
    assert UsersManager(users_path(tmp_path)).users["1"]["name"] == "P001"


def test_valid_legacy_data_is_copied_safely_without_deleting_lola_data(tmp_path: Path) -> None:
    legacy = tmp_path / "lola_data"
    legacy.mkdir()
    (legacy / "preferences.json").write_text('{"language": "es"}\n', encoding="utf-8")
    _write_users(legacy / "users.csv", "Legacy participant")

    data_dir = ensure_data_directory(tmp_path)

    assert json.loads((data_dir / "preferences.json").read_text(encoding="utf-8"))["language"] == "es"
    assert UsersManager(data_dir / "users.csv").users["1"]["name"] == "Legacy participant"
    assert (legacy / "preferences.json").is_file()
    assert (legacy / "users.csv").is_file()


def test_emma_data_is_migrated_to_anna_data_without_deleting_legacy(tmp_path: Path) -> None:
    legacy = tmp_path / "emma_data"
    legacy.mkdir()
    (legacy / "preferences.json").write_text('{"language": "es"}\n', encoding="utf-8")
    _write_users(legacy / "users.csv", "Emma legacy participant")

    data_dir = ensure_data_directory(tmp_path)

    assert data_dir == tmp_path / "anna_data"
    assert json.loads((data_dir / "preferences.json").read_text(encoding="utf-8"))["language"] == "es"
    assert UsersManager(data_dir / "users.csv").users["1"]["name"] == "Emma legacy participant"
    assert legacy.is_dir()


def test_repeated_migration_is_idempotent_and_does_not_overwrite(tmp_path: Path) -> None:
    legacy = tmp_path / "lola_data"
    legacy.mkdir()
    (legacy / "preferences.json").write_text('{"language": "es"}\n', encoding="utf-8")
    _write_users(legacy / "users.csv")

    first = ensure_data_directory(tmp_path)
    first_preferences = (first / "preferences.json").read_bytes()
    first_users = (first / "users.csv").read_bytes()
    warnings: list[str] = []
    second = ensure_data_directory(tmp_path, warn=warnings.append)

    assert second == first
    assert (second / "preferences.json").read_bytes() == first_preferences
    assert (second / "users.csv").read_bytes() == first_users
    assert warnings == []


def test_existing_anna_data_wins_without_merge_and_warns_on_conflict(tmp_path: Path) -> None:
    anna = tmp_path / "anna_data"
    legacy = tmp_path / "lola_data"
    anna.mkdir()
    legacy.mkdir()
    (anna / "preferences.json").write_text('{"language": "en-US"}\n', encoding="utf-8")
    (legacy / "preferences.json").write_text('{"language": "es"}\n', encoding="utf-8")
    _write_users(legacy / "users.csv")
    warnings: list[str] = []

    ensure_data_directory(tmp_path, warn=warnings.append)

    assert json.loads((anna / "preferences.json").read_text(encoding="utf-8"))["language"] == "en-US"
    assert not (anna / "users.csv").exists()
    assert len(warnings) == 2
    assert all("not merged" in message for message in warnings)


def test_invalid_legacy_files_are_ignored_and_never_replace_valid_anna_data(tmp_path: Path) -> None:
    anna = tmp_path / "anna_data"
    legacy = tmp_path / "lola_data"
    anna.mkdir()
    legacy.mkdir()
    (anna / "preferences.json").write_text('{"language": "en-US"}\n', encoding="utf-8")
    _write_users(anna / "users.csv", "Canonical")
    (legacy / "preferences.json").write_text('{"language": "unsupported"}\n', encoding="utf-8")
    (legacy / "users.csv").write_text("wrong,header\n1,Legacy\n", encoding="utf-8")
    warnings: list[str] = []

    ensure_data_directory(tmp_path, warn=warnings.append)

    assert json.loads((anna / "preferences.json").read_text(encoding="utf-8"))["language"] == "en-US"
    assert UsersManager(anna / "users.csv").users["1"]["name"] == "Canonical"
    assert len(warnings) == 2
    assert all("invalid" in message for message in warnings)
