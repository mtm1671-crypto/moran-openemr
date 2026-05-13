"""Load source-backed scanner knowledge base entries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


KNOWLEDGE_BASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "site_vulnerability_knowledge_base.json"
)


def load_site_vulnerability_knowledge_base(path: Path = KNOWLEDGE_BASE_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("site vulnerability knowledge base must be a JSON object")
    return cast(dict[str, Any], payload)


def vulnerability_class_ids(path: Path = KNOWLEDGE_BASE_PATH) -> set[str]:
    payload = load_site_vulnerability_knowledge_base(path)
    classes = payload.get("vulnerability_classes", [])
    if not isinstance(classes, list):
        raise ValueError("vulnerability_classes must be a list")
    ids: set[str] = set()
    for entry in classes:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("each vulnerability class must contain a string id")
        ids.add(entry["id"])
    return ids
