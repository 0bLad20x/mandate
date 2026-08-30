"""Canonical Mandate responsibility/organization semantics.

This module is the executable counterpart of ``mandate.responsibility@0.3``.
It deliberately does not prescribe professions, domain counts, hierarchy depth,
role catalogues, or execution methods. It owns only responsibility identity,
parent accountability, explicit authority, ownership boundaries, and organization
integrity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from mandate.accountable_work import ActorAuthority


class OrganizationError(ValueError):
    """A responsibility organization violates the accepted Mandate contract."""


@dataclass(frozen=True)
class Authority:
    delegate: bool
    accept_child_results: bool
    run_control: bool = False


@dataclass(frozen=True)
class Responsibility:
    responsibility_id: str
    run_id: str
    title: str
    kind: str
    parent_responsibility_id: str | None
    authority: Authority
    mandate: str
    prohibited_scope: tuple[str, ...] = ()
    conversation_id: str | None = None
    conduct_refs: tuple[str, ...] = ("C_CORE",)
    status: str = "ACTIVE"


@dataclass(frozen=True)
class Organization:
    run_id: str
    responsibilities: tuple[Responsibility, ...]

    def by_id(self) -> dict[str, Responsibility]:
        return {item.responsibility_id: item for item in self.responsibilities}

    def responsibility(self, responsibility_id: str) -> Responsibility:
        try:
            return self.by_id()[responsibility_id]
        except KeyError as exc:
            raise OrganizationError("RESPONSIBILITY_NOT_FOUND") from exc

    def children(self, responsibility_id: str) -> tuple[Responsibility, ...]:
        return tuple(
            item
            for item in self.responsibilities
            if item.parent_responsibility_id == responsibility_id
            and item.status == "ACTIVE"
        )

    def run_authority(self) -> Responsibility:
        values = [
            item
            for item in self.responsibilities
            if item.kind == "RUN_AUTHORITY" and item.status == "ACTIVE"
        ]
        if len(values) != 1:
            raise OrganizationError("EXACTLY_ONE_RUN_AUTHORITY_REQUIRED")
        return values[0]

    def root(self) -> Responsibility:
        run_authority = self.run_authority()
        roots = self.children(run_authority.responsibility_id)
        if len(roots) != 1:
            raise OrganizationError("EXACTLY_ONE_ACCOUNTABLE_ROOT_REQUIRED")
        return roots[0]

    def actor_authorities(self) -> Mapping[str, ActorAuthority]:
        # Ledger reconstruction needs historical actors even after a responsibility
        # is retired from the current organization. Status controls current
        # organizational membership, not whether past canonical Work/Result/Decision
        # records remain valid.
        return {
            item.responsibility_id: ActorAuthority(
                may_issue_work=item.authority.delegate
            )
            for item in self.responsibilities
        }


_KIND_VALUES = {"RUN_AUTHORITY", "RESPONSIBILITY"}
_STATUS_VALUES = {"ACTIVE", "RETIRED"}


def _text(value: str, code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OrganizationError(code)


def _authority_subset(child: Authority, parent: Authority) -> bool:
    return (
        (not child.delegate or parent.delegate)
        and (not child.accept_child_results or parent.accept_child_results)
        and not child.run_control
    )


def validate_organization(
    organization: Organization,
    *,
    require_single_root: bool = True,
    require_delegating_nodes_have_children: bool = False,
) -> None:
    _text(organization.run_id, "RUN_ID_REQUIRED")
    if not organization.responsibilities:
        raise OrganizationError("RESPONSIBILITIES_REQUIRED")

    by_id: dict[str, Responsibility] = {}
    conversations: dict[str, str] = {}
    for item in organization.responsibilities:
        _text(item.responsibility_id, "RESPONSIBILITY_ID_REQUIRED")
        if item.responsibility_id in by_id:
            raise OrganizationError("RESPONSIBILITY_ID_DUPLICATE")
        by_id[item.responsibility_id] = item
        if item.run_id != organization.run_id:
            raise OrganizationError("RESPONSIBILITY_RUN_MISMATCH")
        _text(item.title, "RESPONSIBILITY_TITLE_REQUIRED")
        _text(item.mandate, "RESPONSIBILITY_MANDATE_REQUIRED")
        if item.kind not in _KIND_VALUES:
            raise OrganizationError("RESPONSIBILITY_KIND_INVALID")
        if item.status not in _STATUS_VALUES:
            raise OrganizationError("RESPONSIBILITY_STATUS_INVALID")
        if item.conversation_id is not None:
            _text(item.conversation_id, "CONVERSATION_ID_INVALID")
            other = conversations.get(item.conversation_id)
            if other is not None and other != item.responsibility_id:
                raise OrganizationError("CONVERSATION_BINDING_DUPLICATE")
            conversations[item.conversation_id] = item.responsibility_id
        for scope in item.prohibited_scope:
            _text(scope, "PROHIBITED_SCOPE_INVALID")
        for ref in item.conduct_refs:
            _text(ref, "CONDUCT_REF_INVALID")

    active = [item for item in by_id.values() if item.status == "ACTIVE"]
    run_authorities = [item for item in active if item.kind == "RUN_AUTHORITY"]
    if len(run_authorities) != 1:
        raise OrganizationError("EXACTLY_ONE_RUN_AUTHORITY_REQUIRED")
    run_authority = run_authorities[0]
    if run_authority.parent_responsibility_id is not None:
        raise OrganizationError("RUN_AUTHORITY_PARENT_MUST_BE_NULL")
    if not run_authority.authority.run_control:
        raise OrganizationError("RUN_AUTHORITY_RUN_CONTROL_REQUIRED")

    for item in active:
        if item.kind == "RUN_AUTHORITY":
            continue
        if item.authority.run_control:
            raise OrganizationError("RUN_CONTROL_RESERVED_FOR_RUN_AUTHORITY")
        parent_id = item.parent_responsibility_id
        if parent_id is None:
            raise OrganizationError("RESPONSIBILITY_PARENT_REQUIRED")
        parent = by_id.get(parent_id)
        if parent is None or parent.status != "ACTIVE":
            raise OrganizationError("RESPONSIBILITY_PARENT_NOT_ACTIVE")
        if not parent.authority.delegate:
            raise OrganizationError("PARENT_DELEGATE_AUTHORITY_REQUIRED")
        if not _authority_subset(item.authority, parent.authority):
            raise OrganizationError("CHILD_AUTHORITY_EXCEEDS_PARENT")

    # Detect parent cycles independently of topology depth.
    for item in active:
        seen: set[str] = set()
        current: Responsibility | None = item
        while current is not None and current.parent_responsibility_id is not None:
            if current.responsibility_id in seen:
                raise OrganizationError("RESPONSIBILITY_PARENT_CYCLE")
            seen.add(current.responsibility_id)
            current = by_id.get(current.parent_responsibility_id)

    if require_single_root:
        children = [
            item
            for item in active
            if item.parent_responsibility_id == run_authority.responsibility_id
        ]
        if len(children) != 1:
            raise OrganizationError("EXACTLY_ONE_ACCOUNTABLE_ROOT_REQUIRED")

    if require_delegating_nodes_have_children:
        active_children: dict[str, list[Responsibility]] = {}
        for item in active:
            if item.parent_responsibility_id is not None:
                active_children.setdefault(item.parent_responsibility_id, []).append(item)
        for item in active:
            if item.kind == "RUN_AUTHORITY":
                continue
            if item.authority.delegate and not active_children.get(item.responsibility_id):
                raise OrganizationError("DELEGATING_RESPONSIBILITY_WITHOUT_CHILDREN")


def _validate_identity_update(
    existing: Responsibility,
    replacement: Responsibility,
) -> None:
    """Keep stable responsibility identity compatible with durable Work history.

    Parent ownership, kind and authority define the accountable actor identity used
    by historical Work/Result/Decision validation. Changing one of them under the
    same ID would reinterpret old records using new authority. Such a reorganization
    must retire the old ID and create a new responsibility ID instead.
    """

    if existing.run_id != replacement.run_id:
        raise OrganizationError("RESPONSIBILITY_ID_RUN_REDEFINITION")
    if existing.kind != replacement.kind:
        raise OrganizationError("RESPONSIBILITY_ID_KIND_REDEFINITION")
    if existing.parent_responsibility_id != replacement.parent_responsibility_id:
        raise OrganizationError("RESPONSIBILITY_ID_PARENT_REDEFINITION")
    if existing.authority != replacement.authority:
        raise OrganizationError("RESPONSIBILITY_ID_AUTHORITY_REDEFINITION")
    if (
        existing.conversation_id is not None
        and replacement.conversation_id is not None
        and existing.conversation_id != replacement.conversation_id
    ):
        raise OrganizationError("RESPONSIBILITY_CONVERSATION_REBIND_FORBIDDEN")


def with_responsibilities(
    organization: Organization,
    values: Iterable[Responsibility],
) -> Organization:
    by_id = organization.by_id()
    for item in values:
        existing = by_id.get(item.responsibility_id)
        if existing is not None:
            _validate_identity_update(existing, item)
        by_id[item.responsibility_id] = item
    candidate = Organization(
        run_id=organization.run_id,
        responsibilities=tuple(by_id.values()),
    )
    validate_organization(candidate, require_single_root=True)
    return candidate
