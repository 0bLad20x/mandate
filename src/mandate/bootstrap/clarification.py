"""Decision-delta mission clarification before organization design."""

from __future__ import annotations

from mandate.persistence import StreamRef

from .contract import (
    CLARIFICATION_ID,
    ROOT_ID,
    AuthoritativeInput,
    authoritative_context,
    clarification_prompt,
    clarification_request,
    escalation_candidate,
)
from .judgment import Judgments
from .organization_store import OrganizationStore
from .runtime import ResponsibilityTurns
from .work import WorkCoordinator


CLARIFICATION_OBJECTIVE = (
    "Resolve only mission-defining Human decision deltas required before organization "
    "can be finalized, then return a compact authoritative Mission Manifest."
)


class ClarificationError(RuntimeError):
    pass


class ClarificationFlow:
    def __init__(
        self,
        organization: OrganizationStore,
        turns: ResponsibilityTurns,
        work: WorkCoordinator,
        judgments: Judgments,
    ) -> None:
        self.organization = organization
        self.turns = turns
        self.work = work
        self.judgments = judgments

    def manifest(self, stream: StreamRef) -> str | None:
        work = self.work.latest_work_to(
            stream,
            issuer=ROOT_ID,
            target=CLARIFICATION_ID,
            objective=CLARIFICATION_OBJECTIVE,
            open_only=False,
        )
        if work is None:
            return None
        projection = self.work.ledger(stream).projection()
        if work.ref not in projection.closed_work_refs():
            return None
        results = self.work.work_results(projection, work.ref)
        if not results:
            return None
        body = results[-1].value.body
        return body if body.rstrip().endswith("MISSION_MANIFEST_READY") else None

    def run(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        mission: str,
        provider: str,
        external_inputs: tuple[AuthoritativeInput, ...],
        force_new: bool = False,
    ) -> tuple[str | None, str | None]:
        self.organization.ensure_coordination(
            stream,
            run_id=run_id,
            responsibility_id=CLARIFICATION_ID,
        )

        if not force_new:
            manifest = self.manifest(stream)
            if manifest is not None:
                self.organization.retire_coordination(stream, {CLARIFICATION_ID})
                return manifest, None

        work = self.work.latest_work_to(
            stream,
            issuer=ROOT_ID,
            target=CLARIFICATION_ID,
            objective=CLARIFICATION_OBJECTIVE,
            open_only=True,
        )
        if work is None:
            work = self.work.issue(
                stream,
                issuer=ROOT_ID,
                target=CLARIFICATION_ID,
                objective=CLARIFICATION_OBJECTIVE,
                acceptance=(
                    "Only Human-owned decision deltas capable of materially changing mission or organization are escalated; ordinary solution choices and lower-impact unknowns remain delegated/deferred.",
                    "No Human-owned answer is invented, inferred from silence, or supplied by the clarifier.",
                    "When no blocking decision delta remains, a compact Mission Manifest preserves authoritative intent, Human provenance, delegated choices, and deferred unknowns without substantive mission execution.",
                ),
                reuse_open=False,
            )

        while True:
            projection = self.work.ledger(stream).projection()
            prior_results = self.work.work_results(projection, work.ref)
            prior_decisions = self.work.work_decisions(projection, work.ref)
            body = self.turns.run(
                stream,
                run_id=run_id,
                provider=provider,
                responsibility_id=CLARIFICATION_ID,
                prompt=clarification_prompt(
                    mission,
                    external_inputs,
                    prior_results[-1].value.body if prior_results else None,
                    prior_decisions[-1].value.judgment if prior_decisions else None,
                ),
            )
            result_ref = self.work.append_result(
                stream,
                actor=CLARIFICATION_ID,
                work_ref=work.ref,
                body=body,
            )
            decision_value, judgment = self.judgments.child(
                stream,
                run_id=run_id,
                provider=provider,
                parent_id=ROOT_ID,
                child_id=CLARIFICATION_ID,
                work_value=work.value,
                result_ref=result_ref,
                result_body=body,
                context=(
                    f"ORIGINAL MISSION:\n{mission}\n\nAUTHORITATIVE INPUT:\n"
                    f"{authoritative_context(external_inputs)}"
                ),
                clarification=True,
            )
            candidate = escalation_candidate(judgment)
            child_request = clarification_request(body)

            if decision_value == "ACCEPT":
                if child_request is not None:
                    raise ClarificationError(
                        "CLARIFICATION_REQUEST_CANNOT_BE_ACCEPTED"
                    )
                if not body.rstrip().endswith("MISSION_MANIFEST_READY"):
                    raise ClarificationError("MISSION_MANIFEST_READY_REQUIRED")
                self.organization.retire_coordination(stream, {CLARIFICATION_ID})
                return body, None

            if decision_value != "CONTINUE":
                raise ClarificationError("ROOT_CLARIFICATION_DECISION_INVALID")
            if candidate is not None:
                return None, candidate
            if child_request is not None:
                # The Result is only a candidate for escalation; RUN-AUTHORITY still
                # decides whether external Human authority is actually required.
                return None, child_request
            # Quality defect that can be reconsidered autonomously in the same Work.
