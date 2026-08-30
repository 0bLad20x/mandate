"""Frozen accountable-work semantic core.

Owns only Work / Result / Decision semantics. It has no dependency on persistence,
Modelrail, Bootstrap, GitHub, organization, HITL, or run control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, TypeAlias


class ContractError(ValueError):
    """A canonical record violates the accountable-work contract."""


@dataclass(frozen=True)
class ActorAuthority:
    may_issue_work: bool


@dataclass(frozen=True)
class Work:
    to: str
    objective: str
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class Result:
    work_ref: str
    body: str


@dataclass(frozen=True)
class Decision:
    result_ref: str
    decision: str
    judgment: str


SemanticValue: TypeAlias = Work | Result | Decision


@dataclass(frozen=True)
class CanonicalRecord:
    ref: str
    actor: str
    value: SemanticValue


@dataclass(frozen=True)
class WorkFact:
    ref: str
    issuer: str
    value: Work


@dataclass(frozen=True)
class ResultFact:
    ref: str
    actor: str
    value: Result


@dataclass(frozen=True)
class DecisionFact:
    ref: str
    actor: str
    work_ref: str
    value: Decision


@dataclass
class Projection:
    """Derived state. OPEN/CLOSED are projections, never persisted statuses."""

    work: dict[str, WorkFact] = field(default_factory=dict)
    results: dict[str, ResultFact] = field(default_factory=dict)
    decisions: list[DecisionFact] = field(default_factory=list)

    def accepted_work_refs(self) -> set[str]:
        return {
            fact.work_ref
            for fact in self.decisions
            if fact.value.decision == "ACCEPT"
        }

    def open_work_refs(self) -> set[str]:
        return set(self.work) - self.accepted_work_refs()

    def closed_work_refs(self) -> set[str]:
        return set(self.work) & self.accepted_work_refs()


DECISION_VALUES = {"ACCEPT", "CONTINUE"}


def _required_text(value: str, error: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(error)


def _validate_shape(value: SemanticValue) -> None:
    if isinstance(value, Work):
        _required_text(value.to, "WORK_TARGET_REQUIRED")
        _required_text(value.objective, "WORK_OBJECTIVE_REQUIRED")
        if not value.acceptance:
            raise ContractError("ACCEPTANCE_REQUIRED")
        for statement in value.acceptance:
            _required_text(statement, "ACCEPTANCE_REQUIRED")
        return
    if isinstance(value, Result):
        _required_text(value.work_ref, "WORK_REF_REQUIRED")
        _required_text(value.body, "RESULT_BODY_REQUIRED")
        return
    if isinstance(value, Decision):
        _required_text(value.result_ref, "RESULT_REF_REQUIRED")
        if value.decision not in DECISION_VALUES:
            raise ContractError("DECISION_VALUE_INVALID")
        _required_text(value.judgment, "JUDGMENT_REQUIRED")
        return
    raise ContractError("UNKNOWN_SEMANTIC_VALUE")


def apply_record(
    projection: Projection,
    record: CanonicalRecord,
    actors: Mapping[str, ActorAuthority],
) -> None:
    _required_text(record.ref, "RECORD_REF_REQUIRED")
    _required_text(record.actor, "ACTOR_REQUIRED")
    if record.ref in projection.work or record.ref in projection.results or any(
        fact.ref == record.ref for fact in projection.decisions
    ):
        raise ContractError("CANONICAL_RECORD_REF_DUPLICATE")

    authority = actors.get(record.actor)
    if authority is None:
        raise ContractError("ACTOR_NOT_FOUND")

    value = record.value
    _validate_shape(value)

    if isinstance(value, Work):
        if not authority.may_issue_work:
            raise ContractError("DELEGATE_AUTHORITY_REQUIRED")
        if value.to not in actors:
            raise ContractError("WORK_TARGET_NOT_FOUND")
        projection.work[record.ref] = WorkFact(
            ref=record.ref,
            issuer=record.actor,
            value=value,
        )
        return

    if isinstance(value, Result):
        work = projection.work.get(value.work_ref)
        if work is None:
            raise ContractError("RESULT_WORK_NOT_FOUND")
        if work.value.to != record.actor:
            raise ContractError("RESULT_ACTOR_NOT_ASSIGNEE")
        projection.results[record.ref] = ResultFact(
            ref=record.ref,
            actor=record.actor,
            value=value,
        )
        return

    if isinstance(value, Decision):
        result = projection.results.get(value.result_ref)
        if result is None:
            raise ContractError("DECISION_RESULT_NOT_FOUND")
        work = projection.work.get(result.value.work_ref)
        if work is None:
            raise ContractError("DECISION_WORK_NOT_FOUND")
        if result.actor == record.actor:
            raise ContractError("SELF_ACCEPTANCE_FORBIDDEN")
        if work.issuer != record.actor:
            raise ContractError("DECISION_ACTOR_NOT_WORK_ISSUER")
        projection.decisions.append(
            DecisionFact(
                ref=record.ref,
                actor=record.actor,
                work_ref=work.ref,
                value=value,
            )
        )
        return

    raise ContractError("UNKNOWN_SEMANTIC_VALUE")


def project(
    records: list[CanonicalRecord] | tuple[CanonicalRecord, ...],
    actors: Mapping[str, ActorAuthority],
) -> Projection:
    projection = Projection()
    for record in records:
        apply_record(projection, record, actors)
    return projection
