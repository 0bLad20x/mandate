"""Public persistence-reconstructible Mandate pre-execution Bootstrap API.

The API orchestrates accepted semantic owners; it does not contain provider/browser
mechanics, candidate parsers, organization storage, or a second workflow state
machine. Durable truth is reconstructed from Persistence on every advance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from modelrail.conversation.turn import TurnAPI

from mandate.organization import OrganizationSnapshot, append_snapshot, snapshots
from mandate.persistence import Persistence, StreamRef

from .clarification import ClarificationFlow
from .contract import (
    ROOT_ID,
    RUN_AUTHORITY_ID,
    AuthoritativeInput,
    bootstrap_work,
    initial_organization,
    inputs,
    request_from_judgment,
    root_progress_prompt,
)
from .judgment import Judgments
from .organization_flow import OrganizationFlow
from .organization_store import OrganizationStore
from .runtime import ResponsibilityTurns
from .work import WorkCoordinator


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapOutcome:
    run_id: str
    work_ref: str
    decision_ref: str | None
    decision: str | None
    judgment: str | None
    result_body: str | None
    accepted: bool
    external_request: str | None
    mission_manifest: str | None = None
    organization: dict[str, Any] | None = None


class BootstrapAPI:
    """Start or resume Mandate pre-execution organization from durable state."""

    def __init__(
        self,
        persistence: Persistence,
        turn_api: TurnAPI,
        *,
        timeout: float = 300.0,
        poll: float = 1.0,
    ) -> None:
        self.persistence = persistence
        self.turns = ResponsibilityTurns(
            persistence,
            turn_api,
            timeout=timeout,
            poll=poll,
        )
        self.work = WorkCoordinator(persistence)
        self.organization = OrganizationStore(persistence)
        self.judgments = Judgments(self.turns, self.work)
        self.clarification = ClarificationFlow(
            self.organization,
            self.turns,
            self.work,
            self.judgments,
        )
        self.organization_flow = OrganizationFlow(
            self.organization,
            self.turns,
            self.work,
            self.judgments,
        )

    def start(
        self,
        *,
        run_id: str,
        mission: str,
        provider: str,
    ) -> BootstrapOutcome:
        provider = provider.strip().lower()
        stream = self.persistence.create_stream(
            run_id,
            {
                "application": "mandate.bootstrap",
                "protocol": "mandate.bootstrap:v1",
                "mission": mission,
                "provider": provider,
            },
        )
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=initial_organization(run_id),
                reason="Initial authority spine before delegated Bootstrap work",
            ),
        )
        projection, work_ref = self.work.ledger(stream).append(
            actor=RUN_AUTHORITY_ID,
            value=bootstrap_work(),
        )
        if work_ref not in projection.open_work_refs():
            raise BootstrapError("BOOTSTRAP_INITIAL_WORK_INVALID")
        return self._advance(run_id, mission, provider, stream)

    def resume(self, *, run_id: str) -> BootstrapOutcome:
        stream = self.persistence.resolve_stream(run_id)
        metadata = self.persistence.metadata(stream)
        if metadata.get("application") != "mandate.bootstrap":
            raise BootstrapError("BOOTSTRAP_STREAM_APPLICATION_MISMATCH")
        if not snapshots(self.persistence, stream):
            raise BootstrapError(
                "BOOTSTRAP_FIDELITY_ORGANIZATION_STATE_REQUIRED: "
                "pre-fidelity package runs remain evidence and are not silently reinterpreted"
            )
        return self._advance(
            run_id,
            self._required_metadata(metadata, "mission"),
            self._required_metadata(metadata, "provider"),
            stream,
        )

    @staticmethod
    def _required_metadata(metadata: Any, key: str) -> str:
        value = metadata.get(key) if hasattr(metadata, "get") else None
        if not isinstance(value, str) or not value.strip():
            raise BootstrapError(f"BOOTSTRAP_METADATA_{key.upper()}_REQUIRED")
        return value

    def _advance(
        self,
        run_id: str,
        mission: str,
        provider: str,
        stream: StreamRef,
    ) -> BootstrapOutcome:
        while True:
            projection, top_work = self.work.top_work(
                stream,
                issuer=RUN_AUTHORITY_ID,
                target=ROOT_ID,
            )
            if top_work.ref in projection.closed_work_refs():
                return self._outcome(run_id, stream, top_work.ref)

            top_decisions = self.work.work_decisions(projection, top_work.ref)
            latest_decision = top_decisions[-1] if top_decisions else None
            authoritative_inputs = inputs(self.persistence, stream)

            if latest_decision is not None:
                pending = request_from_judgment(latest_decision.value.judgment)
                if pending is not None and not self._input_supplied(
                    latest_decision.ref,
                    authoritative_inputs,
                ):
                    return self._outcome(
                        run_id,
                        stream,
                        top_work.ref,
                        external_request=pending,
                    )

            force_reconsideration = bool(
                latest_decision is not None
                and latest_decision.value.decision == "CONTINUE"
                and request_from_judgment(latest_decision.value.judgment) is None
            )

            manifest, clarification_request = self.clarification.run(
                stream,
                run_id=run_id,
                mission=mission,
                provider=provider,
                external_inputs=authoritative_inputs,
                force_new=force_reconsideration,
            )
            if clarification_request is not None:
                return self._escalate_clarification(
                    stream,
                    run_id=run_id,
                    mission=mission,
                    provider=provider,
                    top_work=top_work,
                    request=clarification_request,
                    authoritative_inputs=authoritative_inputs,
                    previous_judgment=(
                        latest_decision.value.judgment
                        if latest_decision is not None
                        else None
                    ),
                )
            if manifest is None:
                raise BootstrapError("MISSION_MANIFEST_REQUIRED")

            organization, review_judgment = self.organization_flow.run(
                stream,
                run_id=run_id,
                mission=mission,
                provider=provider,
                manifest=manifest,
                external_inputs=authoritative_inputs,
                force_rebuild=force_reconsideration,
            )

            root_body = self.turns.run(
                stream,
                run_id=run_id,
                provider=provider,
                responsibility_id=ROOT_ID,
                prompt=root_progress_prompt(
                    mission=mission,
                    mission_manifest=manifest,
                    organization_json=self.organization.json(organization),
                    unresolved_external_request=None,
                    review_judgment=review_judgment,
                    external_inputs=authoritative_inputs,
                ),
            )
            result_ref = self.work.append_result(
                stream,
                actor=ROOT_ID,
                work_ref=top_work.ref,
                body=root_body,
            )
            _, decision_value, judgment = self.judgments.root(
                stream,
                run_id=run_id,
                mission=mission,
                provider=provider,
                work_value=top_work.value,
                result_ref=result_ref,
                root_body=root_body,
                external_inputs=authoritative_inputs,
                current_organization_json=self.organization.json(organization),
                previous_judgment=(
                    latest_decision.value.judgment
                    if latest_decision is not None
                    else None
                ),
            )
            request = request_from_judgment(judgment)

            if decision_value == "ACCEPT":
                if not self._has_human_organization_response(
                    stream,
                    top_work.ref,
                    authoritative_inputs,
                ):
                    raise BootstrapError("HUMAN_ORGANIZATION_APPROVAL_REQUIRED")
                return self._outcome(run_id, stream, top_work.ref)

            if decision_value != "CONTINUE":
                raise BootstrapError("RUN_AUTHORITY_DECISION_INVALID")
            if request is not None:
                return self._outcome(
                    run_id,
                    stream,
                    top_work.ref,
                    external_request=request,
                )
            # Same ROOT Work remains open. A contract-grounded autonomous CONTINUE
            # triggers whole pre-execution reconsideration on the next iteration.

    def _escalate_clarification(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        mission: str,
        provider: str,
        top_work: Any,
        request: str,
        authoritative_inputs: tuple[AuthoritativeInput, ...],
        previous_judgment: str | None,
    ) -> BootstrapOutcome:
        root_body = self.turns.run(
            stream,
            run_id=run_id,
            provider=provider,
            responsibility_id=ROOT_ID,
            prompt=root_progress_prompt(
                mission=mission,
                mission_manifest=None,
                organization_json=None,
                unresolved_external_request=request,
                review_judgment=None,
                external_inputs=authoritative_inputs,
            ),
        )
        result_ref = self.work.append_result(
            stream,
            actor=ROOT_ID,
            work_ref=top_work.ref,
            body=root_body,
        )
        _, decision_value, judgment = self.judgments.root(
            stream,
            run_id=run_id,
            mission=mission,
            provider=provider,
            work_value=top_work.value,
            result_ref=result_ref,
            root_body=root_body,
            external_inputs=authoritative_inputs,
            current_organization_json=None,
            previous_judgment=previous_judgment,
        )
        external_request = request_from_judgment(judgment)
        if decision_value != "CONTINUE" or external_request is None:
            raise BootstrapError(
                "HUMAN_DECISION_DELTA_MUST_ESCALATE_THROUGH_RUN_AUTHORITY"
            )
        return self._outcome(
            run_id,
            stream,
            top_work.ref,
            external_request=external_request,
        )

    @staticmethod
    def _input_supplied(
        decision_ref: str,
        authoritative_inputs: tuple[AuthoritativeInput, ...],
    ) -> bool:
        return any(
            value.decision_ref == decision_ref
            for value in authoritative_inputs
        )

    def _has_human_organization_response(
        self,
        stream: StreamRef,
        top_work_ref: str,
        authoritative_inputs: tuple[AuthoritativeInput, ...],
    ) -> bool:
        projection = self.work.ledger(stream).projection()
        input_refs = {value.decision_ref for value in authoritative_inputs}
        for decision in self.work.work_decisions(projection, top_work_ref):
            request = request_from_judgment(decision.value.judgment)
            if (
                request is not None
                and "Review the current organization" in request
                and decision.ref in input_refs
            ):
                return True
        return False

    def _outcome(
        self,
        run_id: str,
        stream: StreamRef,
        top_work_ref: str,
        external_request: str | None = None,
    ) -> BootstrapOutcome:
        projection = self.work.ledger(stream).projection()
        decisions = self.work.work_decisions(projection, top_work_ref)
        results = self.work.work_results(projection, top_work_ref)
        latest_decision = decisions[-1] if decisions else None
        latest_result = results[-1] if results else None
        return BootstrapOutcome(
            run_id=run_id,
            work_ref=top_work_ref,
            decision_ref=latest_decision.ref if latest_decision else None,
            decision=latest_decision.value.decision if latest_decision else None,
            judgment=(
                latest_decision.value.judgment if latest_decision else None
            ),
            result_body=latest_result.value.body if latest_result else None,
            accepted=top_work_ref in projection.closed_work_refs(),
            external_request=external_request,
            mission_manifest=self.clarification.manifest(stream),
            organization=json.loads(self.organization.json(stream)),
        )
