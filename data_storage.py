from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Callable


DATA_DIR_NAME = "anna_data"
LEGACY_DATA_DIR_NAMES = ("emma_data", "lola_data")
PREFERENCES_FILENAME = "preferences.json"
USERS_FILENAME = "users.csv"
SUPPORTED_LANGUAGES = {"en-US", "es"}
REQUIRED_USER_FIELDS = {"id", "name"}

_LOGGER = logging.getLogger(__name__)


def _valid_preferences(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("language"), str)
        and payload["language"] in SUPPORTED_LANGUAGES
    )


def _valid_users_csv(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            fieldnames = csv.DictReader(handle).fieldnames
    except (OSError, UnicodeError, csv.Error):
        return False
    if not fieldnames or len(fieldnames) != len(set(fieldnames)):
        return False
    return REQUIRED_USER_FIELDS.issubset(fieldnames)


def _same_contents(first: Path, second: Path) -> bool:
    try:
        return first.read_bytes() == second.read_bytes()
    except OSError:
        return False


def _copy_without_overwrite(source: Path, destination: Path) -> bool:
    if destination.exists():
        return False
    temporary = destination.parent / f".{destination.name}.migration-{uuid.uuid4().hex}.tmp"
    try:
        shutil.copy2(source, temporary)
        if destination.exists():
            return False
        os.replace(temporary, destination)
        return True
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def ensure_data_directory(
    root: Path,
    *,
    warn: Callable[[str], None] | None = None,
) -> Path:
    """Return ANNA's canonical data directory and migrate safe legacy files once.

    Migration is attempted only when ``anna_data`` did not exist at entry. An
    existing canonical directory is always authoritative: missing files are not
    filled from, and existing files are never overwritten by legacy directories.
    """

    root = Path(root)
    anna_data = root / DATA_DIR_NAME
    warning = warn or _LOGGER.warning
    anna_existed = anna_data.exists()
    anna_data.mkdir(parents=True, exist_ok=True)

    validators = {
        PREFERENCES_FILENAME: _valid_preferences,
        USERS_FILENAME: _valid_users_csv,
    }
    for legacy_name in LEGACY_DATA_DIR_NAMES:
        legacy_data = root / legacy_name
        for filename, validator in validators.items():
            legacy_file = legacy_data / filename
            anna_file = anna_data / filename
            if not legacy_file.is_file():
                continue
            if not validator(legacy_file):
                warning(f"Legacy data ignored because it is invalid: {legacy_file}")
                continue
            if anna_existed or anna_file.exists():
                if anna_file.is_file() and _same_contents(legacy_file, anna_file):
                    continue
                warning(
                    f"Legacy/canonical data conflict; {DATA_DIR_NAME} is preserved and "
                    f"{legacy_name} is not merged: {filename}"
                )
                continue
            if not _copy_without_overwrite(legacy_file, anna_file):
                warning(
                    "Legacy/canonical data conflict during migration; "
                    f"{DATA_DIR_NAME} is preserved: {filename}"
                )

    return anna_data


def preferences_path(root: Path) -> Path:
    return ensure_data_directory(root) / PREFERENCES_FILENAME


def users_path(root: Path) -> Path:
    return ensure_data_directory(root) / USERS_FILENAME
