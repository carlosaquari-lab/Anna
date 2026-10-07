from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


class UsersManager:
    """Gestión local de participantes de ANNA."""

    FIELDNAMES = [
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

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = Path(csv_path)
        self.users: dict[str, dict[str, object]] = {}
        self.current_user_id: str | None = None
        self._next_numeric_id = 1
        self.load_users_from_csv()

    def load_users_from_csv(self) -> None:
        self.users = {}
        if not self.csv_path.exists():
            return
        with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                user_id = str(row.get("id") or "").strip()
                if not user_id:
                    continue
                self.users[user_id] = {
                    "id": user_id,
                    "name": row.get("name", ""),
                    "notes": row.get("notes", ""),
                    "group": row.get("group", ""),
                    "date_created": row.get("date_created", ""),
                    "last_session_date": row.get("last_session_date", ""),
                    "last_session_end": row.get("last_session_end", ""),
                    "total_sessions": row.get("total_sessions", "0"),
                    "active": row.get("active", "1") or "1",
                }
        numeric_ids = []
        for user_id in self.users:
            try:
                numeric_ids.append(int(user_id))
            except ValueError:
                continue
        self._next_numeric_id = max(numeric_ids) + 1 if numeric_ids else 1

    def save_users_to_csv(self) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
            writer.writeheader()
            for user_id in sorted(self.users, key=self._sort_key):
                user = self.users[user_id]
                writer.writerow({field: user.get(field, "") for field in self.FIELDNAMES})

    @staticmethod
    def _sort_key(user_id: str) -> tuple[int, object]:
        try:
            return (0, int(user_id))
        except ValueError:
            return (1, user_id)

    def generate_user_id(self) -> str:
        numeric_ids = []
        for user_id in self.users:
            try:
                numeric_ids.append(int(user_id))
            except ValueError:
                continue
        next_id = max([self._next_numeric_id, *(number + 1 for number in numeric_ids)] or [1])
        self._next_numeric_id = next_id + 1
        return str(next_id)

    @staticmethod
    def normalize_identifier(identifier: str) -> str:
        return str(identifier or "").strip()

    def participant_identifier_exists(self, identifier: str, *, exclude_user_id: str | None = None) -> bool:
        normalized = self.normalize_identifier(identifier).casefold()
        return any(
            self.normalize_identifier(str(user.get("name", ""))).casefold() == normalized
            for user_id, user in self.users.items()
            if user_id != exclude_user_id
        )

    def validate_participant_identifier(self, identifier: str, *, exclude_user_id: str | None = None) -> str:
        clean_identifier = self.normalize_identifier(identifier)
        if not clean_identifier:
            raise ValueError("participant identifier is required")
        if self.participant_identifier_exists(clean_identifier, exclude_user_id=exclude_user_id):
            raise ValueError("participant identifier already exists")
        return clean_identifier

    def create_user(self, name: str) -> str:
        clean_name = self.validate_participant_identifier(name)
        user_id = self.generate_user_id()
        self.users[user_id] = {
            "id": user_id,
            "name": clean_name,
            "notes": "",
            "group": "",
            "date_created": datetime.now().date().isoformat(),
            "last_session_date": "",
            "last_session_end": "",
            "total_sessions": 0,
            "active": "1",
        }
        self.save_users_to_csv()
        return user_id

    def rename_user(self, user_id: str, identifier: str) -> None:
        if user_id not in self.users:
            raise KeyError(user_id)
        clean_identifier = self.validate_participant_identifier(identifier, exclude_user_id=user_id)
        self.users[user_id]["name"] = clean_identifier
        self.save_users_to_csv()

    def clear_current_user(self) -> None:
        self.current_user_id = None

    def select_user(self, user_id: str) -> None:
        if user_id not in self.users:
            raise KeyError(user_id)
        if not self.is_active_user(user_id):
            raise ValueError("archived participant cannot be selected")
        self.current_user_id = user_id

    def get_current_user_name(self) -> str:
        if self.current_user_id and self.current_user_id in self.users:
            return str(self.users[self.current_user_id].get("name", ""))
        return ""

    def update_user_session_on_close(self) -> None:
        if not self.current_user_id or self.current_user_id not in self.users:
            return
        user = self.users[self.current_user_id]
        try:
            total = int(float(user.get("total_sessions", 0)))
        except (TypeError, ValueError):
            total = 0
        now = datetime.now()
        user["total_sessions"] = total + 1
        user["last_session_date"] = now.date().isoformat()
        user["last_session_end"] = now.strftime("%Y-%m-%d %H:%M:%S")
        self.save_users_to_csv()

    @staticmethod
    def participant_code(user_id: str) -> str:
        try:
            return f"P{int(user_id):04d}"
        except (TypeError, ValueError):
            return f"P{str(user_id).strip()}"

    def participant_display_name(self, user_id: str, *, include_archived: bool = True) -> str:
        user = self.users[user_id]
        label = f"{user.get('name', '')} — {self.participant_code(user_id)}"
        if include_archived and not self.is_active_user(user_id):
            label = f"{label} (archivado)"
        return label

    @staticmethod
    def _active_value(value: object) -> bool:
        return str(value if value is not None else "1").strip().casefold() not in {"0", "false", "no", "archived"}

    def is_active_user(self, user_id: str) -> bool:
        return user_id in self.users and self._active_value(self.users[user_id].get("active", "1"))

    @staticmethod
    def _last_session_sort_value(value: object) -> tuple[int, int]:
        text = str(value or "").strip()
        if not text:
            return (1, 0)
        try:
            date_value = datetime.fromisoformat(text[:10]).date()
        except ValueError:
            return (1, 0)
        return (0, -date_value.toordinal())

    def sorted_participant_ids(self, *, show_archived: bool = False) -> list[str]:
        user_ids = [
            user_id
            for user_id in self.users
            if show_archived or self.is_active_user(user_id)
        ]

        def key(user_id: str) -> tuple[int, int, str]:
            user = self.users[user_id]
            session_group, session_date = self._last_session_sort_value(user.get("last_session_date", ""))
            return (session_group, session_date, self.normalize_identifier(str(user.get("name", ""))).casefold())

        return sorted(user_ids, key=key)

    def has_recorded_sessions(self, user_id: str, sessions_root: Path | None = None) -> bool:
        user = self.users.get(user_id)
        if not user:
            return False
        try:
            if int(float(user.get("total_sessions", 0) or 0)) > 0:
                return True
        except (TypeError, ValueError):
            pass
        if sessions_root is None or not Path(sessions_root).exists():
            return False
        for session_path in Path(sessions_root).glob("*/session.json"):
            try:
                data = json.loads(session_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if str(data.get("user_id", "")) == str(user_id):
                return True
        return False

    def archive_user(self, user_id: str) -> None:
        if user_id not in self.users:
            raise KeyError(user_id)
        self.users[user_id]["active"] = "0"
        if self.current_user_id == user_id:
            self.current_user_id = None
        self.save_users_to_csv()

    def reactivate_user(self, user_id: str) -> None:
        if user_id not in self.users:
            raise KeyError(user_id)
        self.users[user_id]["active"] = "1"
        self.save_users_to_csv()

    def delete_user(self, user_id: str) -> None:
        if user_id not in self.users:
            raise KeyError(user_id)
        if self.current_user_id == user_id:
            self.current_user_id = None
        del self.users[user_id]
        self.save_users_to_csv()

    def remove_or_archive_user(self, user_id: str, sessions_root: Path | None = None) -> str:
        if self.has_recorded_sessions(user_id, sessions_root):
            self.archive_user(user_id)
            return "archived"
        self.delete_user(user_id)
        return "deleted"
