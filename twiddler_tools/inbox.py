"""Persistent inbox of chords the user wants to add to the Twiddler.

Stored as JSON under the platform user-data directory so it survives between
runs and OS reinstalls of the app itself.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_data_dir

from .model import PendingChord


def default_inbox_path() -> Path:
    return Path(user_data_dir("twiddler-tools")) / "inbox.json"


def _migrate_status(status: str) -> str:
    """Map legacy statuses to the current vocabulary.

    Older inboxes used "added" for items the user had (manually) put on the
    device; that concept is now "exported", which is only set automatically
    when a .cfg export includes the item. Previously "added" items are treated
    as still pending so they are not silently dropped from future exports.
    """
    return "pending" if status == "added" else status


class Inbox:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path) if path is not None else default_inbox_path()
        self._items: list[PendingChord] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._items = [
            PendingChord(
                text=item["text"],
                status=_migrate_status(item.get("status", "pending")),
                chord_id=item.get("chord_id"),
                created_at=item.get("created_at", ""),
                notes=item.get("notes", ""),
            )
            for item in data.get("items", [])
        ]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "items": [
                {
                    "text": item.text,
                    "status": item.status,
                    "chord_id": item.chord_id,
                    "created_at": item.created_at,
                    "notes": item.notes,
                }
                for item in self._items
            ],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add(
        self, text: str, notes: str = "", chord_id: str | None = None
    ) -> PendingChord:
        if not text:
            raise ValueError("pair text cannot be empty")
        existing = self.find(text)
        if existing is not None:
            return existing
        item = PendingChord(
            text=text,
            notes=notes,
            chord_id=chord_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._items.append(item)
        self.save()
        return item

    def find(self, text: str) -> PendingChord | None:
        needle = text.lower()
        for item in self._items:
            if item.text.lower() == needle:
                return item
        return None

    def mark_exported(self, text: str, chord_id: str | None = None) -> PendingChord | None:
        item = self.find(text)
        if item is None:
            return None
        item.status = "exported"
        if chord_id:
            item.chord_id = chord_id
        self.save()
        return item

    def update(
        self,
        text: str,
        new_text: str | None = None,
        chord_id: str | None = None,
    ) -> PendingChord | None:
        """Update an existing item's text and/or chord.

        Any change resets the item to "pending", since the exported .cfg no
        longer matches it.
        """
        item = self.find(text)
        if item is None:
            return None
        changed = False
        if new_text is not None and new_text != item.text:
            item.text = new_text
            changed = True
        if chord_id is not None and chord_id != item.chord_id:
            item.chord_id = chord_id
            changed = True
        if changed:
            item.status = "pending"
            self.save()
        return item

    def remove(self, text: str) -> bool:
        item = self.find(text)
        if item is None:
            return False
        self._items.remove(item)
        self.save()
        return True

    def items(self) -> list[PendingChord]:
        return list(self._items)

    def pending(self) -> list[PendingChord]:
        return [item for item in self._items if item.status == "pending"]
