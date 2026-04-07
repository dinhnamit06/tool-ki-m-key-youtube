from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from core.rpm_service import RPMFilterState
from core.rpm_templates import RPMFilterTemplate


class RPMTemplateStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path(__file__).resolve().parents[1] / "custom_filter_templates.json")

    def load_custom_templates(self) -> list[RPMFilterTemplate]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        templates: list[RPMFilterTemplate] = []
        for item in raw if isinstance(raw, list) else []:
            template = self._deserialize_template(item)
            if template is not None:
                templates.append(template)
        return templates

    def save_custom_templates(self, templates: list[RPMFilterTemplate]):
        payload = [self._serialize_template(template) for template in templates if not template.built_in]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def upsert_custom_template(self, template: RPMFilterTemplate):
        templates = self.load_custom_templates()
        kept = [item for item in templates if item.name != template.name]
        kept.append(template)
        kept.sort(key=lambda item: item.name.lower())
        self.save_custom_templates(kept)

    @staticmethod
    def _serialize_template(template: RPMFilterTemplate) -> dict:
        state_dict = asdict(template.state)
        for key in ("first_upload_after", "first_upload_before", "last_upload_after", "last_upload_before"):
            value = state_dict.get(key)
            if isinstance(value, date):
                state_dict[key] = value.isoformat()
        return {
            "name": template.name,
            "description": template.description,
            "built_in": False,
            "state": state_dict,
        }

    @staticmethod
    def _deserialize_template(payload: object) -> RPMFilterTemplate | None:
        if not isinstance(payload, dict):
            return None
        name = str(payload.get("name", "")).strip()
        if not name:
            return None
        description = str(payload.get("description", "")).strip() or "Custom template"
        state_payload = payload.get("state", {})
        if not isinstance(state_payload, dict):
            state_payload = {}
        normalized = dict(state_payload)
        for key in ("first_upload_after", "first_upload_before", "last_upload_after", "last_upload_before"):
            value = normalized.get(key)
            if isinstance(value, str) and value:
                try:
                    normalized[key] = date.fromisoformat(value)
                except ValueError:
                    normalized[key] = None
        try:
            state = RPMFilterState(**normalized)
        except TypeError:
            return None
        return RPMFilterTemplate(name=name, description=description, state=state, built_in=False)
