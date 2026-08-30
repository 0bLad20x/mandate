"""Strict parsing for Bootstrap responsibility outputs.

These shapes are local Work-result contracts, not new global Mandate status types.
They make candidate/review evidence executable while the canonical accountability
model remains Work / Result / Decision.
"""

from __future__ import annotations

import json
from typing import Any

from mandate.organization import Authority


class BootstrapParseError(ValueError):
    pass


def json_object(raw: str, error: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BootstrapParseError(error) from exc
    if not isinstance(value, dict):
        raise BootstrapParseError(error)
    return value


def decision(raw: str, label: str) -> dict[str, str]:
    value = json_object(raw, f"{label}_OUTPUT_NOT_JSON")
    if set(value) != {"decision", "judgment"}:
        raise BootstrapParseError(f"{label}_OUTPUT_SHAPE_INVALID")
    decision_value = value["decision"]
    judgment = value["judgment"]
    if decision_value not in {"ACCEPT", "CONTINUE"}:
        raise BootstrapParseError(f"{label}_DECISION_INVALID")
    if not isinstance(judgment, str) or not judgment.strip():
        raise BootstrapParseError(f"{label}_JUDGMENT_REQUIRED")
    return {"decision": decision_value, "judgment": judgment}


def review(raw: str) -> dict[str, Any]:
    value = json_object(raw, "ORGANIZATION_REVIEW_OUTPUT_NOT_JSON")
    if set(value) != {"disposition", "judgment", "findings"}:
        raise BootstrapParseError("ORGANIZATION_REVIEW_OUTPUT_SHAPE_INVALID")
    if value["disposition"] not in {"ACCEPTABLE", "REVISION_REQUIRED"}:
        raise BootstrapParseError("ORGANIZATION_REVIEW_DISPOSITION_INVALID")
    if not isinstance(value["judgment"], str) or not value["judgment"].strip():
        raise BootstrapParseError("ORGANIZATION_REVIEW_JUDGMENT_REQUIRED")
    if not isinstance(value["findings"], list):
        raise BootstrapParseError("ORGANIZATION_REVIEW_FINDINGS_INVALID")
    required = {"evidence", "boundary", "consequence", "revision"}
    for finding in value["findings"]:
        if not isinstance(finding, dict) or set(finding) != required:
            raise BootstrapParseError("ORGANIZATION_REVIEW_FINDING_SHAPE_INVALID")
        if not all(
            isinstance(finding[key], str) and finding[key].strip()
            for key in required
        ):
            raise BootstrapParseError("ORGANIZATION_REVIEW_FINDING_TEXT_REQUIRED")
    if value["disposition"] == "ACCEPTABLE" and value["findings"]:
        raise BootstrapParseError("ACCEPTABLE_REVIEW_MUST_HAVE_NO_FINDINGS")
    if value["disposition"] == "REVISION_REQUIRED" and not value["findings"]:
        raise BootstrapParseError("REVISION_REQUIRED_NEEDS_FINDINGS")
    return value


def required_text(value: object, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BootstrapParseError(code)
    return value.strip()


def text_list(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise BootstrapParseError(code)
    return tuple(required_text(item, code) for item in value)


def authority(raw: object) -> Authority:
    if not isinstance(raw, dict) or set(raw) != {
        "delegate",
        "accept_child_results",
    }:
        raise BootstrapParseError("RESPONSIBILITY_AUTHORITY_SHAPE_INVALID")
    delegate = raw["delegate"]
    accept = raw["accept_child_results"]
    if not isinstance(delegate, bool) or not isinstance(accept, bool):
        raise BootstrapParseError("RESPONSIBILITY_AUTHORITY_BOOLEAN_REQUIRED")
    if delegate != accept:
        raise BootstrapParseError(
            "NON_LEAF_AUTHORITY_MUST_DELEGATE_AND_ACCEPT_CHILD_RESULTS"
        )
    return Authority(
        delegate=delegate,
        accept_child_results=accept,
        run_control=False,
    )
