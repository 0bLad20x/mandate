"""Persistence codec for canonical Mandate organization snapshots.

Snapshots are append-only durable representations of the accepted
``mandate.responsibility@0.3`` fields. The latest valid snapshot is the current
organization projection; older snapshots remain evidence/history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from mandate.persistence import Persistence, StreamRef

from .core import Authority, Organization, Responsibility, validate_organization


PROTOCOL = "mandate.organization:v1"


@dataclass(frozen=True)
class OrganizationSnapshot:
    organization: Organization
    reason: str
    source_ref: str | None = None


def _responsibility_dict(value: Responsibility) -> dict[str, object]:
    return {
        "responsibility_id": value.responsibility_id,
        "run_id": value.run_id,
        "title": value.title,
        "kind": value.kind,
        "parent_responsibility_id": value.parent_responsibility_id,
        "authority": {
            "delegate": value.authority.delegate,
            "accept_child_results": value.authority.accept_child_results,
            "run_control": value.authority.run_control,
        },
        "mandate": value.mandate,
        "prohibited_scope": list(value.prohibited_scope),
        "conversation_id": value.conversation_id,
        "conduct_refs": list(value.conduct_refs),
        "status": value.status,
    }


def encode_snapshot(value: OrganizationSnapshot) -> str:
    validate_organization(value.organization, require_single_root=True)
    if not isinstance(value.reason, str) or not value.reason.strip():
        raise ValueError("ORGANIZATION_SNAPSHOT_REASON_REQUIRED")
    return json.dumps(
        {
            "protocol": PROTOCOL,
            "kind": "organization_snapshot",
            "run_id": value.organization.run_id,
            "reason": value.reason,
            "source_ref": value.source_ref,
            "responsibilities": [
                _responsibility_dict(item)
                for item in value.organization.responsibilities
            ],
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _decode_responsibility(raw: object) -> Responsibility:
    if not isinstance(raw, dict):
        raise ValueError("RESPONSIBILITY_SHAPE_INVALID")
    required = {
        "responsibility_id",
        "run_id",
        "title",
        "kind",
        "parent_responsibility_id",
        "authority",
        "mandate",
        "prohibited_scope",
        "conversation_id",
        "conduct_refs",
        "status",
    }
    if set(raw) != required:
        raise ValueError("RESPONSIBILITY_SHAPE_INVALID")
    authority_raw = raw["authority"]
    if not isinstance(authority_raw, dict) or set(authority_raw) != {
        "delegate",
        "accept_child_results",
        "run_control",
    }:
        raise ValueError("RESPONSIBILITY_AUTHORITY_SHAPE_INVALID")
    if not all(
        isinstance(authority_raw[key], bool)
        for key in ("delegate", "accept_child_results", "run_control")
    ):
        raise ValueError("RESPONSIBILITY_AUTHORITY_BOOLEAN_REQUIRED")
    prohibited = raw["prohibited_scope"]
    conduct = raw["conduct_refs"]
    if not isinstance(prohibited, list) or not isinstance(conduct, list):
        raise ValueError("RESPONSIBILITY_LIST_FIELD_INVALID")
    return Responsibility(
        responsibility_id=str(raw["responsibility_id"]),
        run_id=str(raw["run_id"]),
        title=str(raw["title"]),
        kind=str(raw["kind"]),
        parent_responsibility_id=(
            None
            if raw["parent_responsibility_id"] is None
            else str(raw["parent_responsibility_id"])
        ),
        authority=Authority(
            delegate=authority_raw["delegate"],
            accept_child_results=authority_raw["accept_child_results"],
            run_control=authority_raw["run_control"],
        ),
        mandate=str(raw["mandate"]),
        prohibited_scope=tuple(str(item) for item in prohibited),
        conversation_id=(
            None if raw["conversation_id"] is None else str(raw["conversation_id"])
        ),
        conduct_refs=tuple(str(item) for item in conduct),
        status=str(raw["status"]),
    )


def decode_snapshot(body: str) -> OrganizationSnapshot | None:
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict) or raw.get("protocol") != PROTOCOL:
        return None
    if raw.get("kind") != "organization_snapshot":
        return None
    if set(raw) != {
        "protocol",
        "kind",
        "run_id",
        "reason",
        "source_ref",
        "responsibilities",
    }:
        raise ValueError("ORGANIZATION_SNAPSHOT_SHAPE_INVALID")
    values = raw["responsibilities"]
    if not isinstance(values, list):
        raise ValueError("ORGANIZATION_RESPONSIBILITIES_INVALID")
    if not isinstance(raw["reason"], str) or not raw["reason"].strip():
        raise ValueError("ORGANIZATION_SNAPSHOT_REASON_REQUIRED")
    if raw["source_ref"] is not None and not isinstance(raw["source_ref"], str):
        raise ValueError("ORGANIZATION_SNAPSHOT_SOURCE_REF_INVALID")
    organization = Organization(
        run_id=str(raw["run_id"]),
        responsibilities=tuple(_decode_responsibility(item) for item in values),
    )
    validate_organization(organization, require_single_root=True)
    return OrganizationSnapshot(
        organization=organization,
        reason=raw["reason"],
        source_ref=raw["source_ref"],
    )


def snapshots(
    persistence: Persistence,
    stream: StreamRef,
) -> tuple[OrganizationSnapshot, ...]:
    out: list[OrganizationSnapshot] = []
    for entry in persistence.read(stream):
        value = decode_snapshot(entry.body)
        if value is not None:
            out.append(value)
    return tuple(out)


def current_organization(
    persistence: Persistence,
    stream: StreamRef,
) -> Organization:
    values = snapshots(persistence, stream)
    if not values:
        raise ValueError("ORGANIZATION_SNAPSHOT_REQUIRED")
    return values[-1].organization


def append_snapshot(
    persistence: Persistence,
    stream: StreamRef,
    snapshot: OrganizationSnapshot,
) -> None:
    persistence.append(stream, encode_snapshot(snapshot))
