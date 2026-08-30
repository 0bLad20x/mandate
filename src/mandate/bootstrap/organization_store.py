"""Durable Organization editing used by Bootstrap flows.

This module mutates no local semantic state. Every accepted organization change is
an append-only OrganizationSnapshot in Persistence; current organization is always
reconstructed from that stream.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Iterable

from mandate.organization import (
    Organization,
    OrganizationSnapshot,
    Responsibility,
    append_snapshot,
    current_organization,
    validate_organization,
    with_responsibilities,
)
from mandate.persistence import Persistence, StreamRef

from .contract import (
    CLARIFICATION_ID,
    ORGANIZATION_DESIGN_ID,
    ORGANIZATION_REVIEW_ID,
    RESERVED_RESPONSIBILITY_IDS,
    coordination_responsibilities,
)


class OrganizationStore:
    def __init__(self, persistence: Persistence) -> None:
        self.persistence = persistence

    def current(self, stream: StreamRef) -> Organization:
        return current_organization(self.persistence, stream)

    def ensure_coordination(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        responsibility_id: str,
    ) -> None:
        current = self.current(stream)
        wanted = {
            item.responsibility_id: item
            for item in coordination_responsibilities(run_id)
        }[responsibility_id]
        existing = current.by_id().get(responsibility_id)
        if existing is not None:
            if existing.status == "ACTIVE":
                return
            wanted = replace(
                wanted,
                conversation_id=existing.conversation_id,
                status="ACTIVE",
            )
        candidate = with_responsibilities(current, (wanted,))
        self.append(
            stream,
            candidate,
            reason=f"Activate pre-execution responsibility {responsibility_id}",
        )

    def retire_coordination(
        self,
        stream: StreamRef,
        responsibility_ids: set[str],
    ) -> None:
        current = self.current(stream)
        changed = False
        values: list[Responsibility] = []
        for item in current.responsibilities:
            if item.responsibility_id in responsibility_ids and item.status == "ACTIVE":
                values.append(replace(item, status="RETIRED"))
                changed = True
            else:
                values.append(item)
        if not changed:
            return
        candidate = Organization(current.run_id, tuple(values))
        validate_organization(candidate, require_single_root=True)
        self.append(
            stream,
            candidate,
            reason="Retire completed pre-execution coordination responsibilities",
        )

    def reactivate_coordination(
        self,
        stream: StreamRef,
        responsibility_ids: set[str],
    ) -> None:
        run_id = self.current(stream).run_id
        for responsibility_id in responsibility_ids:
            self.ensure_coordination(
                stream,
                run_id=run_id,
                responsibility_id=responsibility_id,
            )

    def replace_execution_candidate(
        self,
        stream: StreamRef,
        values: Iterable[Responsibility],
        *,
        source_ref: str,
    ) -> Organization:
        values = tuple(values)
        candidate_ids = {item.responsibility_id for item in values}
        current = self.current(stream)
        retained: list[Responsibility] = []
        for item in current.responsibilities:
            if item.responsibility_id in RESERVED_RESPONSIBILITY_IDS:
                retained.append(item)
            elif item.responsibility_id in candidate_ids:
                continue
            else:
                retained.append(replace(item, status="RETIRED"))
        candidate = Organization(
            run_id=current.run_id,
            responsibilities=tuple(retained) + values,
        )
        validate_organization(candidate, require_single_root=True)
        self.append(
            stream,
            candidate,
            reason="Initial broad organization candidate",
            source_ref=source_ref,
        )
        return candidate

    def merge_children(
        self,
        stream: StreamRef,
        children: Iterable[Responsibility],
        *,
        source_ref: str,
    ) -> Organization:
        candidate = with_responsibilities(self.current(stream), tuple(children))
        self.append(
            stream,
            candidate,
            reason="Accepted recursive child organization",
            source_ref=source_ref,
        )
        return candidate

    def append(
        self,
        stream: StreamRef,
        organization: Organization,
        *,
        reason: str,
        source_ref: str | None = None,
    ) -> None:
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=organization,
                reason=reason,
                source_ref=source_ref,
            ),
        )

    def json(
        self,
        stream_or_org: StreamRef | Organization,
        *,
        execution_only: bool = False,
    ) -> str:
        organization = (
            self.current(stream_or_org)
            if isinstance(stream_or_org, StreamRef)
            else stream_or_org
        )
        values = []
        for item in organization.responsibilities:
            if item.status != "ACTIVE":
                continue
            if execution_only and item.responsibility_id in {
                "RUN-AUTHORITY",
                CLARIFICATION_ID,
                ORGANIZATION_DESIGN_ID,
                ORGANIZATION_REVIEW_ID,
            }:
                continue
            values.append(self.responsibility_dict(item))
        return json.dumps(
            {"run_id": organization.run_id, "responsibilities": values},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    @staticmethod
    def responsibility_dict(item: Responsibility) -> dict[str, Any]:
        return {
            "responsibility_id": item.responsibility_id,
            "title": item.title,
            "kind": item.kind,
            "parent_responsibility_id": item.parent_responsibility_id,
            "authority": {
                "delegate": item.authority.delegate,
                "accept_child_results": item.authority.accept_child_results,
                "run_control": item.authority.run_control,
            },
            "mandate": item.mandate,
            "prohibited_scope": list(item.prohibited_scope),
            "conversation_id": item.conversation_id,
        }
