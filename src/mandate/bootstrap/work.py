"""Bootstrap helpers over the frozen accountable Work core.

No workflow phase or status is persisted here. Current openness, results and
judgments are derived from Work/Result/Decision records plus the current canonical
Organization actor set.
"""

from __future__ import annotations

from typing import Any

from mandate.accountable_work import AccountableWorkLedger, Decision, Result, Work
from mandate.organization import current_organization
from mandate.persistence import Persistence, StreamRef


class WorkCoordinator:
    def __init__(self, persistence: Persistence) -> None:
        self.persistence = persistence

    def ledger(self, stream: StreamRef) -> AccountableWorkLedger:
        organization = current_organization(self.persistence, stream)
        return AccountableWorkLedger(
            self.persistence,
            stream,
            organization.actor_authorities(),
        )

    @staticmethod
    def work_results(projection: Any, work_ref: str) -> list[Any]:
        return [
            fact
            for fact in projection.results.values()
            if fact.value.work_ref == work_ref
        ]

    @staticmethod
    def work_decisions(projection: Any, work_ref: str) -> list[Any]:
        return [fact for fact in projection.decisions if fact.work_ref == work_ref]

    def top_work(self, stream: StreamRef, *, issuer: str, target: str):
        projection = self.ledger(stream).projection()
        matches = [
            fact
            for fact in projection.work.values()
            if fact.issuer == issuer and fact.value.to == target
        ]
        if len(matches) != 1:
            raise ValueError("EXACTLY_ONE_TOP_WORK_REQUIRED")
        return projection, matches[0]

    def latest_work_to(
        self,
        stream: StreamRef,
        *,
        issuer: str,
        target: str,
        objective: str | None = None,
        open_only: bool = False,
    ):
        projection = self.ledger(stream).projection()
        rows = [
            fact
            for fact in projection.work.values()
            if fact.issuer == issuer
            and fact.value.to == target
            and (objective is None or fact.value.objective == objective)
        ]
        if open_only:
            open_refs = projection.open_work_refs()
            rows = [fact for fact in rows if fact.ref in open_refs]
        return rows[-1] if rows else None

    def issue(
        self,
        stream: StreamRef,
        *,
        issuer: str,
        target: str,
        objective: str,
        acceptance: tuple[str, ...],
        reuse_open: bool = True,
    ):
        if reuse_open:
            existing = self.latest_work_to(
                stream,
                issuer=issuer,
                target=target,
                objective=objective,
                open_only=True,
            )
            if existing is not None:
                return existing
        ledger = self.ledger(stream)
        _, ref = ledger.append(
            actor=issuer,
            value=Work(to=target, objective=objective, acceptance=acceptance),
        )
        return self.ledger(stream).projection().work[ref]

    def append_result(
        self,
        stream: StreamRef,
        *,
        actor: str,
        work_ref: str,
        body: str,
    ) -> str:
        _, ref = self.ledger(stream).append(
            actor=actor,
            value=Result(work_ref=work_ref, body=body),
        )
        return ref

    def append_decision(
        self,
        stream: StreamRef,
        *,
        actor: str,
        result_ref: str,
        decision: str,
        judgment: str,
    ) -> str:
        _, ref = self.ledger(stream).append(
            actor=actor,
            value=Decision(
                result_ref=result_ref,
                decision=decision,
                judgment=judgment,
            ),
        )
        return ref
