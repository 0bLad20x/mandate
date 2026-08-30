"""Persistence-reconstructible Mandate pre-execution Bootstrap.

Mandate owns semantic coordination and responsibility organization. Persistence is
the only durable Mandate truth. Modelrail executes referenced Turns only.

This restores the accepted Modelrail-era WP1 behavior without restoring its local
broker-state ownership: decision-delta clarification, organization before execution,
independent challenge, recursive organization, whole-topology reintegration, and
Human approval of the current organization.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Any, Iterable

from modelrail.conversation.turn import TurnAPI, TurnRequest

from mandate.accountable_work import AccountableWorkLedger, Decision, Result, Work
from mandate.organization import (
    Authority,
    Organization,
    OrganizationSnapshot,
    Responsibility,
    append_snapshot,
    current_organization,
    snapshots,
    validate_organization,
    with_responsibilities,
)
from mandate.persistence import Persistence, StreamRef

from .contract import (
    CLARIFICATION_ID,
    ORGANIZATION_DESIGN_ID,
    ORGANIZATION_REVIEW_ID,
    RESERVED_RESPONSIBILITY_IDS,
    ROOT_ID,
    RUN_AUTHORITY_ID,
    AuthoritativeInput,
    TurnEvidence,
    authoritative_context,
    bootstrap_work,
    child_judge_prompt,
    clarification_prompt,
    clarification_request,
    coordination_responsibilities,
    encode_turn_evidence,
    escalation_candidate,
    initial_organization,
    inputs,
    organization_design_prompt,
    organization_review_prompt,
    recursive_organization_prompt,
    request_from_judgment,
    root_progress_prompt,
    run_authority_prompt,
)


CLARIFICATION_OBJECTIVE = (
    "Resolve only mission-defining Human decision deltas required before organization "
    "can be finalized, then return a compact authoritative Mission Manifest."
)
DESIGN_OBJECTIVE = (
    "Derive the mission-specific initial broad responsibility organization below ROOT; "
    "perform no substantive mission execution and do not self-accept the candidate."
)
INITIAL_REVIEW_OBJECTIVE = (
    "Independently review the initial broad organization and return ACCEPTABLE or "
    "REVISION_REQUIRED with contract-grounded findings."
)
FINAL_REVIEW_OBJECTIVE = (
    "Independently review the complete recursively expanded organization against the "
    "Human mission and accepted Mission Manifest."
)
RECURSIVE_OBJECTIVE = (
    "Derive the child execution responsibility organization required by this delegated "
    "broad mandate before substantive domain execution."
)


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
    """Public pre-execution Bootstrap surface."""

    def __init__(
        self,
        persistence: Persistence,
        turn_api: TurnAPI,
        *,
        timeout: float = 300.0,
        poll: float = 1.0,
    ) -> None:
        self.persistence = persistence
        self.turn_api = turn_api
        self.timeout = max(10.0, timeout)
        self.poll = max(0.1, poll)

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
        initial = initial_organization(run_id)
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=initial,
                reason="Initial authority spine before delegated Bootstrap work",
            ),
        )
        ledger = self._ledger(stream)
        projection, work_ref = ledger.append(
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
        mission = self._required_metadata(metadata, "mission")
        provider = self._required_metadata(metadata, "provider")
        return self._advance(run_id, mission, provider, stream)

    @staticmethod
    def _required_metadata(metadata: Any, key: str) -> str:
        value = metadata.get(key) if hasattr(metadata, "get") else None
        if not isinstance(value, str) or not value.strip():
            raise BootstrapError(f"BOOTSTRAP_METADATA_{key.upper()}_REQUIRED")
        return value

    def _ledger(self, stream: StreamRef) -> AccountableWorkLedger:
        organization = current_organization(self.persistence, stream)
        return AccountableWorkLedger(
            self.persistence,
            stream,
            organization.actor_authorities(),
        )

    def _top_work(self, stream: StreamRef):
        projection = self._ledger(stream).projection()
        matches = [
            fact
            for fact in projection.work.values()
            if fact.issuer == RUN_AUTHORITY_ID and fact.value.to == ROOT_ID
        ]
        if len(matches) != 1:
            raise BootstrapError("EXACTLY_ONE_ROOT_BOOTSTRAP_WORK_REQUIRED")
        return projection, matches[0]

    @staticmethod
    def _work_results(projection: Any, work_ref: str) -> list[Any]:
        return [
            fact
            for fact in projection.results.values()
            if fact.value.work_ref == work_ref
        ]

    @staticmethod
    def _work_decisions(projection: Any, work_ref: str) -> list[Any]:
        return [fact for fact in projection.decisions if fact.work_ref == work_ref]

    def _latest_work_to(
        self,
        stream: StreamRef,
        *,
        issuer: str,
        target: str,
        objective: str | None = None,
        open_only: bool = False,
    ) -> Any | None:
        projection = self._ledger(stream).projection()
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

    def _issue_work(
        self,
        stream: StreamRef,
        *,
        issuer: str,
        target: str,
        objective: str,
        acceptance: tuple[str, ...],
        reuse_open: bool = True,
    ) -> Any:
        if reuse_open:
            existing = self._latest_work_to(
                stream,
                issuer=issuer,
                target=target,
                objective=objective,
                open_only=True,
            )
            if existing is not None:
                return existing
        ledger = self._ledger(stream)
        _, ref = ledger.append(
            actor=issuer,
            value=Work(to=target, objective=objective, acceptance=acceptance),
        )
        return self._ledger(stream).projection().work[ref]

    def _advance(
        self,
        run_id: str,
        mission: str,
        provider: str,
        stream: StreamRef,
    ) -> BootstrapOutcome:
        while True:
            projection, top_work = self._top_work(stream)
            if top_work.ref in projection.closed_work_refs():
                return self._outcome(run_id, stream, top_work.ref)

            top_decisions = self._work_decisions(projection, top_work.ref)
            latest_top_decision = top_decisions[-1] if top_decisions else None
            supplied_inputs = inputs(self.persistence, stream)

            if latest_top_decision is not None:
                pending_request = request_from_judgment(
                    latest_top_decision.value.judgment
                )
                if pending_request is not None and not any(
                    item.decision_ref == latest_top_decision.ref
                    for item in supplied_inputs
                ):
                    return self._outcome(
                        run_id,
                        stream,
                        top_work.ref,
                        external_request=pending_request,
                    )

            force_reconsideration = bool(
                latest_top_decision is not None
                and latest_top_decision.value.decision == "CONTINUE"
                and request_from_judgment(latest_top_decision.value.judgment) is None
            )

            manifest, clarification_external = self._clarify(
                stream,
                run_id,
                mission,
                provider,
                supplied_inputs,
                force_new=force_reconsideration,
            )

            if clarification_external is not None:
                root_body = self._turn(
                    stream,
                    run_id,
                    provider,
                    ROOT_ID,
                    root_progress_prompt(
                        mission=mission,
                        mission_manifest=manifest,
                        organization_json=None,
                        unresolved_external_request=clarification_external,
                        review_judgment=None,
                        external_inputs=supplied_inputs,
                    ),
                )
                result_ref = self._append_result(
                    stream,
                    actor=ROOT_ID,
                    work_ref=top_work.ref,
                    body=root_body,
                )
                decision_ref, decision, judgment = self._judge_root(
                    stream,
                    run_id,
                    mission,
                    provider,
                    top_work.value,
                    result_ref,
                    root_body,
                    supplied_inputs,
                    current_org=None,
                    previous_judgment=(
                        latest_top_decision.value.judgment
                        if latest_top_decision is not None
                        else None
                    ),
                )
                request = request_from_judgment(judgment)
                if decision != "CONTINUE" or request is None:
                    raise BootstrapError(
                        "HUMAN_DECISION_DELTA_MUST_ESCALATE_THROUGH_RUN_AUTHORITY"
                    )
                return self._outcome(
                    run_id,
                    stream,
                    top_work.ref,
                    external_request=request,
                )

            if manifest is None:
                raise BootstrapError("MISSION_MANIFEST_REQUIRED")

            organization, review_judgment = self._build_and_challenge_organization(
                stream,
                run_id,
                mission,
                provider,
                manifest,
                supplied_inputs,
                force_rebuild=force_reconsideration,
            )

            root_body = self._turn(
                stream,
                run_id,
                provider,
                ROOT_ID,
                root_progress_prompt(
                    mission=mission,
                    mission_manifest=manifest,
                    organization_json=self._organization_json(organization),
                    unresolved_external_request=None,
                    review_judgment=review_judgment,
                    external_inputs=supplied_inputs,
                ),
            )
            result_ref = self._append_result(
                stream,
                actor=ROOT_ID,
                work_ref=top_work.ref,
                body=root_body,
            )
            decision_ref, decision, judgment = self._judge_root(
                stream,
                run_id,
                mission,
                provider,
                top_work.value,
                result_ref,
                root_body,
                supplied_inputs,
                current_org=organization,
                previous_judgment=(
                    latest_top_decision.value.judgment
                    if latest_top_decision is not None
                    else None
                ),
            )
            request = request_from_judgment(judgment)

            if decision == "ACCEPT":
                if request is not None:
                    raise BootstrapError("ACCEPT_CANNOT_REQUEST_EXTERNAL_INPUT")
                if not self._has_prior_human_organization_response(
                    stream,
                    top_work.ref,
                    supplied_inputs,
                ):
                    raise BootstrapError("HUMAN_ORGANIZATION_APPROVAL_REQUIRED")
                return self._outcome(run_id, stream, top_work.ref)

            if decision != "CONTINUE":
                raise BootstrapError("RUN_AUTHORITY_DECISION_INVALID")
            if request is not None:
                return self._outcome(
                    run_id,
                    stream,
                    top_work.ref,
                    external_request=request,
                )
            # Independent Run Authority found a material defect after ROOT result.
            # CONTINUE keeps the same ROOT Work open. The next iteration re-derives
            # clarification/organization from Persistence with this judgment as evidence.

    def _clarify(
        self,
        stream: StreamRef,
        run_id: str,
        mission: str,
        provider: str,
        supplied_inputs: tuple[AuthoritativeInput, ...],
        *,
        force_new: bool,
    ) -> tuple[str | None, str | None]:
        self._ensure_coordination_responsibility(stream, run_id, CLARIFICATION_ID)

        if not force_new:
            closed = self._latest_work_to(
                stream,
                issuer=ROOT_ID,
                target=CLARIFICATION_ID,
                objective=CLARIFICATION_OBJECTIVE,
                open_only=False,
            )
            if closed is not None:
                projection = self._ledger(stream).projection()
                if closed.ref in projection.closed_work_refs():
                    results = self._work_results(projection, closed.ref)
                    if not results:
                        raise BootstrapError("ACCEPTED_CLARIFICATION_RESULT_REQUIRED")
                    body = results[-1].value.body
                    if not body.rstrip().endswith("MISSION_MANIFEST_READY"):
                        raise BootstrapError("ACCEPTED_MISSION_MANIFEST_MARKER_REQUIRED")
                    self._retire_coordination(stream, {CLARIFICATION_ID})
                    return body, None

        work = self._latest_work_to(
            stream,
            issuer=ROOT_ID,
            target=CLARIFICATION_ID,
            objective=CLARIFICATION_OBJECTIVE,
            open_only=True,
        )
        if work is None:
            work = self._issue_work(
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
            projection = self._ledger(stream).projection()
            previous_results = self._work_results(projection, work.ref)
            previous_decisions = self._work_decisions(projection, work.ref)
            previous_result = previous_results[-1].value.body if previous_results else None
            previous_judgment = (
                previous_decisions[-1].value.judgment if previous_decisions else None
            )
            body = self._turn(
                stream,
                run_id,
                provider,
                CLARIFICATION_ID,
                clarification_prompt(
                    mission,
                    supplied_inputs,
                    previous_result,
                    previous_judgment,
                ),
            )
            result_ref = self._append_result(
                stream,
                actor=CLARIFICATION_ID,
                work_ref=work.ref,
                body=body,
            )
            decision, judgment = self._judge_child(
                stream,
                run_id,
                provider,
                parent_id=ROOT_ID,
                child_id=CLARIFICATION_ID,
                work=work.value,
                result_ref=result_ref,
                result_body=body,
                context=(
                    f"ORIGINAL MISSION:\n{mission}\n\nAUTHORITATIVE INPUT:\n"
                    f"{authoritative_context(supplied_inputs)}"
                ),
                clarification=True,
            )
            candidate = escalation_candidate(judgment)
            child_request = clarification_request(body)
            if decision == "ACCEPT":
                if child_request is not None:
                    raise BootstrapError("CLARIFICATION_REQUEST_CANNOT_BE_ACCEPTED")
                if not body.rstrip().endswith("MISSION_MANIFEST_READY"):
                    raise BootstrapError("MISSION_MANIFEST_READY_REQUIRED")
                self._retire_coordination(stream, {CLARIFICATION_ID})
                return body, None
            if decision != "CONTINUE":
                raise BootstrapError("ROOT_CLARIFICATION_DECISION_INVALID")
            if candidate is not None:
                return None, candidate
            if child_request is not None:
                # ROOT failed to copy the candidate marker but still continued. Preserve
                # authority: use the child's bounded candidate, never answer it locally.
                return None, child_request
            # Quality defect that can be reconsidered autonomously in the same Work.

    def _build_and_challenge_organization(
        self,
        stream: StreamRef,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
        supplied_inputs: tuple[AuthoritativeInput, ...],
        *,
        force_rebuild: bool,
    ) -> tuple[Organization, str]:
        if not force_rebuild and self._final_organization_ready(stream):
            organization = current_organization(self.persistence, stream)
            review = self._latest_review_result(
                stream, objective=FINAL_REVIEW_OBJECTIVE
            )
            if review is None:
                raise BootstrapError("FINAL_REVIEW_RESULT_REQUIRED")
            parsed = self._parse_review(review.value.body)
            return organization, str(parsed["judgment"])

        self._ensure_coordination_responsibility(
            stream, run_id, ORGANIZATION_DESIGN_ID
        )
        self._ensure_coordination_responsibility(
            stream, run_id, ORGANIZATION_REVIEW_ID
        )

        global_revision = self._latest_revision_findings(stream)

        while True:
            candidate, initial_review = self._design_until_initial_review_accepts(
                stream,
                run_id,
                mission,
                provider,
                manifest,
                supplied_inputs,
                global_revision,
            )
            candidate = self._recursively_organize(
                stream,
                run_id,
                mission,
                provider,
                manifest,
                candidate,
            )
            validate_organization(
                candidate,
                require_single_root=True,
                require_delegating_nodes_have_children=True,
            )

            review_result = self._review_candidate(
                stream,
                run_id,
                mission,
                provider,
                manifest,
                candidate,
                objective=FINAL_REVIEW_OBJECTIVE,
                recursive=True,
            )
            parsed_review = self._parse_review(review_result.value.body)
            if parsed_review["disposition"] == "REVISION_REQUIRED":
                global_revision = review_result.value.body
                # Preserve the rejected topology as history. A new design Work will
                # reconsider the whole organization instead of patching it silently.
                self._reactivate_coordination(
                    stream, {ORGANIZATION_DESIGN_ID, ORGANIZATION_REVIEW_ID}
                )
                continue

            self._retire_coordination(
                stream,
                {ORGANIZATION_DESIGN_ID, ORGANIZATION_REVIEW_ID, CLARIFICATION_ID},
            )
            final = current_organization(self.persistence, stream)
            validate_organization(
                final,
                require_single_root=True,
                require_delegating_nodes_have_children=True,
            )
            return final, str(parsed_review["judgment"])

    def _design_until_initial_review_accepts(
        self,
        stream: StreamRef,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
        supplied_inputs: tuple[AuthoritativeInput, ...],
        global_revision: str | None,
    ) -> tuple[Organization, str]:
        work = self._issue_work(
            stream,
            issuer=ROOT_ID,
            target=ORGANIZATION_DESIGN_ID,
            objective=DESIGN_OBJECTIVE,
            acceptance=(
                "Candidate contains mission-relevant broad responsibility boundaries below ROOT and no fixed topology/role catalogue assumptions.",
                "Distinct evidence, judgment, failure, and accountability surfaces are neither collapsed nor fragmented merely by task decomposition.",
                "Broad non-leaf authorities retain only inherited delegation/acceptance authority and perform no substantive domain execution during organization design.",
                "The candidate is independently reviewed and this Work is accepted only when the review is ACCEPTABLE.",
            ),
            reuse_open=True,
        )

        while True:
            projection = self._ledger(stream).projection()
            prior_results = self._work_results(projection, work.ref)
            prior_decisions = self._work_decisions(projection, work.ref)
            prior_candidate = prior_results[-1].value.body if prior_results else None
            prior_judgment = (
                prior_decisions[-1].value.judgment if prior_decisions else global_revision
            )
            body = self._turn(
                stream,
                run_id,
                provider,
                ORGANIZATION_DESIGN_ID,
                organization_design_prompt(
                    mission=mission,
                    mission_manifest=manifest,
                    prior_candidate=prior_candidate,
                    prior_judgment=prior_judgment or global_revision,
                    external_inputs=supplied_inputs,
                ),
            )
            design_result_ref = self._append_result(
                stream,
                actor=ORGANIZATION_DESIGN_ID,
                work_ref=work.ref,
                body=body,
            )
            candidate = self._replace_execution_candidate(
                stream,
                run_id,
                body,
                source_ref=design_result_ref,
            )

            review_result = self._review_candidate(
                stream,
                run_id,
                mission,
                provider,
                manifest,
                candidate,
                objective=INITIAL_REVIEW_OBJECTIVE,
                recursive=False,
            )
            parsed_review = self._parse_review(review_result.value.body)
            decision, judgment = self._judge_child(
                stream,
                run_id,
                provider,
                parent_id=ROOT_ID,
                child_id=ORGANIZATION_DESIGN_ID,
                work=work.value,
                result_ref=design_result_ref,
                result_body=body,
                context=(
                    "INDEPENDENT ORGANIZATION REVIEW:\n"
                    + review_result.value.body
                ),
                clarification=False,
            )
            disposition = parsed_review["disposition"]
            if disposition == "REVISION_REQUIRED":
                if decision == "ACCEPT":
                    raise BootstrapError(
                        "DESIGN_CANNOT_BE_ACCEPTED_AGAINST_REVISION_REQUIRED_REVIEW"
                    )
                global_revision = review_result.value.body
                continue
            if disposition != "ACCEPTABLE":
                raise BootstrapError("ORGANIZATION_REVIEW_DISPOSITION_INVALID")
            if decision == "ACCEPT":
                return candidate, str(parsed_review["judgment"])
            if decision != "CONTINUE":
                raise BootstrapError("ROOT_DESIGN_DECISION_INVALID")
            global_revision = judgment

    def _review_candidate(
        self,
        stream: StreamRef,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
        candidate: Organization,
        *,
        objective: str,
        recursive: bool,
    ) -> Any:
        work = self._issue_work(
            stream,
            issuer=ROOT_ID,
            target=ORGANIZATION_REVIEW_ID,
            objective=objective,
            acceptance=(
                "Review is independent from the candidate author and challenges both fragmentation and collapsed accountability.",
                "Every material finding states candidate evidence, governing boundary, material consequence, and bounded revision.",
                "Nonstandard topology is preserved when no contract-grounded material defect exists.",
                "No substantive mission execution occurs during review.",
            ),
            reuse_open=False,
        )
        while True:
            body = self._turn(
                stream,
                run_id,
                provider,
                ORGANIZATION_REVIEW_ID,
                organization_review_prompt(
                    mission=mission,
                    mission_manifest=manifest,
                    candidate_json=self._organization_json(candidate, execution_only=True),
                    recursive=recursive,
                ),
            )
            self._parse_review(body)
            result_ref = self._append_result(
                stream,
                actor=ORGANIZATION_REVIEW_ID,
                work_ref=work.ref,
                body=body,
            )
            decision, _ = self._judge_child(
                stream,
                run_id,
                provider,
                parent_id=ROOT_ID,
                child_id=ORGANIZATION_REVIEW_ID,
                work=work.value,
                result_ref=result_ref,
                result_body=body,
                context=(
                    "CANDIDATE UNDER REVIEW:\n"
                    + self._organization_json(candidate, execution_only=True)
                ),
                clarification=False,
            )
            if decision == "ACCEPT":
                projection = self._ledger(stream).projection()
                return projection.results[result_ref]
            if decision != "CONTINUE":
                raise BootstrapError("ROOT_REVIEW_DECISION_INVALID")

    def _recursively_organize(
        self,
        stream: StreamRef,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
        candidate: Organization,
    ) -> Organization:
        while True:
            organization = current_organization(self.persistence, stream)
            gaps = [
                item
                for item in organization.responsibilities
                if item.status == "ACTIVE"
                and item.kind == "RESPONSIBILITY"
                and item.responsibility_id not in RESERVED_RESPONSIBILITY_IDS
                and item.authority.delegate
                and not organization.children(item.responsibility_id)
            ]
            if not gaps:
                validate_organization(
                    organization,
                    require_single_root=True,
                    require_delegating_nodes_have_children=True,
                )
                return organization

            for responsibility in gaps:
                parent_id = responsibility.parent_responsibility_id
                if parent_id is None:
                    raise BootstrapError("RECURSIVE_PARENT_REQUIRED")
                work = self._issue_work(
                    stream,
                    issuer=parent_id,
                    target=responsibility.responsibility_id,
                    objective=RECURSIVE_OBJECTIVE,
                    acceptance=(
                        "Child boundaries are derived only from materially distinct inherited ownership/evidence/judgment/failure/accountability surfaces.",
                        "Parent accountability and authority bounds are preserved; no child gains run control or authority beyond the parent.",
                        "Broad non-leaf children are explicitly identified for further recursive organization and leaf children represent genuinely bounded execution/evidence surfaces.",
                        "No substantive domain execution occurs while deriving child organization.",
                    ),
                    reuse_open=True,
                )
                while True:
                    projection = self._ledger(stream).projection()
                    prior_results = self._work_results(projection, work.ref)
                    prior_decisions = self._work_decisions(projection, work.ref)
                    body = self._turn(
                        stream,
                        run_id,
                        provider,
                        responsibility.responsibility_id,
                        recursive_organization_prompt(
                            mission=mission,
                            mission_manifest=manifest,
                            responsibility=responsibility,
                            current_organization_json=self._organization_json(
                                current_organization(self.persistence, stream),
                                execution_only=True,
                            ),
                            previous_result=(
                                prior_results[-1].value.body if prior_results else None
                            ),
                            previous_judgment=(
                                prior_decisions[-1].value.judgment
                                if prior_decisions
                                else None
                            ),
                        ),
                    )
                    children = self._parse_recursive_children(
                        body,
                        run_id=run_id,
                        parent=responsibility,
                    )
                    result_ref = self._append_result(
                        stream,
                        actor=responsibility.responsibility_id,
                        work_ref=work.ref,
                        body=body,
                    )
                    decision, _ = self._judge_child(
                        stream,
                        run_id,
                        provider,
                        parent_id=parent_id,
                        child_id=responsibility.responsibility_id,
                        work=work.value,
                        result_ref=result_ref,
                        result_body=body,
                        context=(
                            "PROPOSED CHILD ORGANIZATION:\n"
                            + json.dumps(
                                [self._responsibility_dict(item) for item in children],
                                ensure_ascii=False,
                                indent=2,
                            )
                        ),
                        clarification=False,
                    )
                    if decision == "CONTINUE":
                        continue
                    if decision != "ACCEPT":
                        raise BootstrapError("RECURSIVE_PARENT_DECISION_INVALID")
                    self._merge_children(
                        stream,
                        children,
                        source_ref=result_ref,
                    )
                    break

    def _judge_child(
        self,
        stream: StreamRef,
        run_id: str,
        provider: str,
        *,
        parent_id: str,
        child_id: str,
        work: Work,
        result_ref: str,
        result_body: str,
        context: str,
        clarification: bool,
    ) -> tuple[str, str]:
        raw = self._turn(
            stream,
            run_id,
            provider,
            parent_id,
            child_judge_prompt(
                parent_id=parent_id,
                child_id=child_id,
                work=work,
                result_body=result_body,
                context=context,
                clarification=clarification,
            ),
        )
        value = self._decision_json(raw, "PARENT_DECISION")
        ledger = self._ledger(stream)
        ledger.append(
            actor=parent_id,
            value=Decision(
                result_ref=result_ref,
                decision=value["decision"],
                judgment=value["judgment"],
            ),
        )
        return value["decision"], value["judgment"]

    def _judge_root(
        self,
        stream: StreamRef,
        run_id: str,
        mission: str,
        provider: str,
        work: Work,
        result_ref: str,
        root_body: str,
        supplied_inputs: tuple[AuthoritativeInput, ...],
        *,
        current_org: Organization | None,
        previous_judgment: str | None,
    ) -> tuple[str, str, str]:
        raw = self._turn(
            stream,
            run_id,
            provider,
            RUN_AUTHORITY_ID,
            run_authority_prompt(
                mission=mission,
                work=work,
                root_result=root_body,
                root_result_ref=result_ref,
                current_organization_json=(
                    self._organization_json(current_org)
                    if current_org is not None
                    else None
                ),
                external_inputs=supplied_inputs,
                previous_judgment=previous_judgment,
            ),
        )
        value = self._decision_json(raw, "RUN_AUTHORITY")
        if value["decision"] == "ACCEPT" and request_from_judgment(
            value["judgment"]
        ) is not None:
            raise BootstrapError("ACCEPT_CANNOT_REQUEST_EXTERNAL_INPUT")
        ledger = self._ledger(stream)
        _, decision_ref = ledger.append(
            actor=RUN_AUTHORITY_ID,
            value=Decision(
                result_ref=result_ref,
                decision=value["decision"],
                judgment=value["judgment"],
            ),
        )
        return decision_ref, value["decision"], value["judgment"]

    def _append_result(
        self,
        stream: StreamRef,
        *,
        actor: str,
        work_ref: str,
        body: str,
    ) -> str:
        ledger = self._ledger(stream)
        _, result_ref = ledger.append(
            actor=actor,
            value=Result(work_ref=work_ref, body=body),
        )
        return result_ref

    @staticmethod
    def _decision_json(raw: str, label: str) -> dict[str, str]:
        value = BootstrapAPI._json_object(raw, f"{label}_OUTPUT_NOT_JSON")
        if set(value) != {"decision", "judgment"}:
            raise BootstrapError(f"{label}_OUTPUT_SHAPE_INVALID")
        decision = value["decision"]
        judgment = value["judgment"]
        if decision not in {"ACCEPT", "CONTINUE"}:
            raise BootstrapError(f"{label}_DECISION_INVALID")
        if not isinstance(judgment, str) or not judgment.strip():
            raise BootstrapError(f"{label}_JUDGMENT_REQUIRED")
        return {"decision": decision, "judgment": judgment}

    @staticmethod
    def _json_object(raw: str, error: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BootstrapError(error) from exc
        if not isinstance(value, dict):
            raise BootstrapError(error)
        return value

    def _parse_review(self, body: str) -> dict[str, Any]:
        value = self._json_object(body, "ORGANIZATION_REVIEW_OUTPUT_NOT_JSON")
        if set(value) != {"disposition", "judgment", "findings"}:
            raise BootstrapError("ORGANIZATION_REVIEW_OUTPUT_SHAPE_INVALID")
        if value["disposition"] not in {"ACCEPTABLE", "REVISION_REQUIRED"}:
            raise BootstrapError("ORGANIZATION_REVIEW_DISPOSITION_INVALID")
        if not isinstance(value["judgment"], str) or not value["judgment"].strip():
            raise BootstrapError("ORGANIZATION_REVIEW_JUDGMENT_REQUIRED")
        if not isinstance(value["findings"], list):
            raise BootstrapError("ORGANIZATION_REVIEW_FINDINGS_INVALID")
        required = {"evidence", "boundary", "consequence", "revision"}
        for finding in value["findings"]:
            if not isinstance(finding, dict) or set(finding) != required:
                raise BootstrapError("ORGANIZATION_REVIEW_FINDING_SHAPE_INVALID")
            if not all(isinstance(finding[key], str) and finding[key].strip() for key in required):
                raise BootstrapError("ORGANIZATION_REVIEW_FINDING_TEXT_REQUIRED")
        if value["disposition"] == "ACCEPTABLE" and value["findings"]:
            raise BootstrapError("ACCEPTABLE_REVIEW_MUST_HAVE_NO_FINDINGS")
        if value["disposition"] == "REVISION_REQUIRED" and not value["findings"]:
            raise BootstrapError("REVISION_REQUIRED_NEEDS_FINDINGS")
        return value

    def _replace_execution_candidate(
        self,
        stream: StreamRef,
        run_id: str,
        body: str,
        *,
        source_ref: str,
    ) -> Organization:
        raw = self._json_object(body, "ORGANIZATION_DESIGN_OUTPUT_NOT_JSON")
        if set(raw) != {"rationale", "responsibilities"}:
            raise BootstrapError("ORGANIZATION_DESIGN_OUTPUT_SHAPE_INVALID")
        if not isinstance(raw["rationale"], str) or not raw["rationale"].strip():
            raise BootstrapError("ORGANIZATION_DESIGN_RATIONALE_REQUIRED")
        rows = raw["responsibilities"]
        if not isinstance(rows, list) or not rows:
            raise BootstrapError("ORGANIZATION_DESIGN_RESPONSIBILITIES_REQUIRED")

        candidate_ids: set[str] = set()
        values: list[Responsibility] = []
        current = current_organization(self.persistence, stream)
        existing = current.by_id()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "responsibility_id", "title", "parent_responsibility_id",
                "authority", "mandate", "prohibited_scope"
            }:
                raise BootstrapError("ORGANIZATION_RESPONSIBILITY_SHAPE_INVALID")
            rid = self._required_text(row["responsibility_id"], "RESPONSIBILITY_ID_REQUIRED")
            if rid in RESERVED_RESPONSIBILITY_IDS or rid in candidate_ids:
                raise BootstrapError("ORGANIZATION_RESPONSIBILITY_ID_INVALID")
            candidate_ids.add(rid)
            parent = self._required_text(
                row["parent_responsibility_id"], "RESPONSIBILITY_PARENT_REQUIRED"
            )
            if parent != ROOT_ID:
                raise BootstrapError(
                    "INITIAL_ORGANIZATION_MUST_DEFINE_BROAD_ROOT_CHILDREN_ONLY"
                )
            authority = self._parse_authority(row["authority"])
            prior = existing.get(rid)
            values.append(
                Responsibility(
                    responsibility_id=rid,
                    run_id=run_id,
                    title=self._required_text(row["title"], "RESPONSIBILITY_TITLE_REQUIRED"),
                    kind="RESPONSIBILITY",
                    parent_responsibility_id=ROOT_ID,
                    authority=authority,
                    mandate=self._required_text(row["mandate"], "RESPONSIBILITY_MANDATE_REQUIRED"),
                    prohibited_scope=self._text_list(row["prohibited_scope"], "PROHIBITED_SCOPE_INVALID"),
                    conversation_id=prior.conversation_id if prior is not None else None,
                )
            )

        retained: list[Responsibility] = []
        for item in current.responsibilities:
            if item.responsibility_id in RESERVED_RESPONSIBILITY_IDS:
                retained.append(item)
            elif item.responsibility_id in candidate_ids:
                continue
            else:
                retained.append(replace(item, status="RETIRED"))
        candidate = Organization(run_id=run_id, responsibilities=tuple(retained + values))
        validate_organization(candidate, require_single_root=True)
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=candidate,
                reason="Initial broad organization candidate",
                source_ref=source_ref,
            ),
        )
        return candidate

    def _parse_recursive_children(
        self,
        body: str,
        *,
        run_id: str,
        parent: Responsibility,
    ) -> tuple[Responsibility, ...]:
        raw = self._json_object(body, "RECURSIVE_ORGANIZATION_OUTPUT_NOT_JSON")
        if set(raw) != {"rationale", "children"}:
            raise BootstrapError("RECURSIVE_ORGANIZATION_OUTPUT_SHAPE_INVALID")
        if not isinstance(raw["rationale"], str) or not raw["rationale"].strip():
            raise BootstrapError("RECURSIVE_ORGANIZATION_RATIONALE_REQUIRED")
        rows = raw["children"]
        if not isinstance(rows, list) or not rows:
            raise BootstrapError("RECURSIVE_CHILDREN_REQUIRED")
        current = current_organization(self.persistence, self._current_stream)
        existing = current.by_id()
        ids: set[str] = set()
        values: list[Responsibility] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "responsibility_id", "title", "authority", "mandate", "prohibited_scope"
            }:
                raise BootstrapError("RECURSIVE_CHILD_SHAPE_INVALID")
            rid = self._required_text(row["responsibility_id"], "RESPONSIBILITY_ID_REQUIRED")
            if rid in RESERVED_RESPONSIBILITY_IDS or rid in ids:
                raise BootstrapError("RECURSIVE_CHILD_ID_INVALID")
            ids.add(rid)
            authority = self._parse_authority(row["authority"])
            prior = existing.get(rid)
            values.append(
                Responsibility(
                    responsibility_id=rid,
                    run_id=run_id,
                    title=self._required_text(row["title"], "RESPONSIBILITY_TITLE_REQUIRED"),
                    kind="RESPONSIBILITY",
                    parent_responsibility_id=parent.responsibility_id,
                    authority=authority,
                    mandate=self._required_text(row["mandate"], "RESPONSIBILITY_MANDATE_REQUIRED"),
                    prohibited_scope=self._text_list(row["prohibited_scope"], "PROHIBITED_SCOPE_INVALID"),
                    conversation_id=prior.conversation_id if prior is not None else None,
                )
            )
        return tuple(values)

    def _merge_children(
        self,
        stream: StreamRef,
        children: tuple[Responsibility, ...],
        *,
        source_ref: str,
    ) -> None:
        current = current_organization(self.persistence, stream)
        candidate = with_responsibilities(current, children)
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=candidate,
                reason="Accepted recursive child organization",
                source_ref=source_ref,
            ),
        )

    @staticmethod
    def _parse_authority(raw: object) -> Authority:
        if not isinstance(raw, dict) or set(raw) != {"delegate", "accept_child_results"}:
            raise BootstrapError("RESPONSIBILITY_AUTHORITY_SHAPE_INVALID")
        delegate = raw["delegate"]
        accept = raw["accept_child_results"]
        if not isinstance(delegate, bool) or not isinstance(accept, bool):
            raise BootstrapError("RESPONSIBILITY_AUTHORITY_BOOLEAN_REQUIRED")
        if delegate != accept:
            raise BootstrapError(
                "NON_LEAF_AUTHORITY_MUST_DELEGATE_AND_ACCEPT_CHILD_RESULTS"
            )
        return Authority(delegate=delegate, accept_child_results=accept, run_control=False)

    @staticmethod
    def _required_text(value: object, code: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise BootstrapError(code)
        return value.strip()

    @classmethod
    def _text_list(cls, value: object, code: str) -> tuple[str, ...]:
        if not isinstance(value, list):
            raise BootstrapError(code)
        return tuple(cls._required_text(item, code) for item in value)

    def _ensure_coordination_responsibility(
        self,
        stream: StreamRef,
        run_id: str,
        responsibility_id: str,
    ) -> None:
        current = current_organization(self.persistence, stream)
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
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=candidate,
                reason=f"Activate pre-execution responsibility {responsibility_id}",
            ),
        )

    def _retire_coordination(
        self,
        stream: StreamRef,
        responsibility_ids: set[str],
    ) -> None:
        current = current_organization(self.persistence, stream)
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
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=candidate,
                reason="Retire completed pre-execution coordination responsibilities",
            ),
        )

    def _reactivate_coordination(
        self,
        stream: StreamRef,
        responsibility_ids: set[str],
    ) -> None:
        current = current_organization(self.persistence, stream)
        for rid in responsibility_ids:
            self._ensure_coordination_responsibility(stream, current.run_id, rid)

    def _latest_review_result(self, stream: StreamRef, *, objective: str) -> Any | None:
        work = self._latest_work_to(
            stream,
            issuer=ROOT_ID,
            target=ORGANIZATION_REVIEW_ID,
            objective=objective,
            open_only=False,
        )
        if work is None:
            return None
        projection = self._ledger(stream).projection()
        if work.ref not in projection.closed_work_refs():
            return None
        results = self._work_results(projection, work.ref)
        return results[-1] if results else None

    def _latest_revision_findings(self, stream: StreamRef) -> str | None:
        for objective in (FINAL_REVIEW_OBJECTIVE, INITIAL_REVIEW_OBJECTIVE):
            result = self._latest_review_result(stream, objective=objective)
            if result is None:
                continue
            parsed = self._parse_review(result.value.body)
            if parsed["disposition"] == "REVISION_REQUIRED":
                return result.value.body
        return None

    def _final_organization_ready(self, stream: StreamRef) -> bool:
        review = self._latest_review_result(stream, objective=FINAL_REVIEW_OBJECTIVE)
        if review is None:
            return False
        if self._parse_review(review.value.body)["disposition"] != "ACCEPTABLE":
            return False
        organization = current_organization(self.persistence, stream)
        if any(
            item.status == "ACTIVE"
            for item in organization.responsibilities
            if item.responsibility_id in {
                CLARIFICATION_ID, ORGANIZATION_DESIGN_ID, ORGANIZATION_REVIEW_ID
            }
        ):
            return False
        validate_organization(
            organization,
            require_single_root=True,
            require_delegating_nodes_have_children=True,
        )
        return True

    def _manifest(self, stream: StreamRef) -> str | None:
        work = self._latest_work_to(
            stream,
            issuer=ROOT_ID,
            target=CLARIFICATION_ID,
            objective=CLARIFICATION_OBJECTIVE,
            open_only=False,
        )
        if work is None:
            return None
        projection = self._ledger(stream).projection()
        if work.ref not in projection.closed_work_refs():
            return None
        results = self._work_results(projection, work.ref)
        if not results:
            return None
        body = results[-1].value.body
        return body if body.rstrip().endswith("MISSION_MANIFEST_READY") else None

    def _has_prior_human_organization_response(
        self,
        stream: StreamRef,
        top_work_ref: str,
        supplied_inputs: tuple[AuthoritativeInput, ...],
    ) -> bool:
        projection = self._ledger(stream).projection()
        input_refs = {item.decision_ref for item in supplied_inputs}
        for decision in self._work_decisions(projection, top_work_ref):
            request = request_from_judgment(decision.value.judgment)
            if request is None:
                continue
            if "Review the current organization" in request and decision.ref in input_refs:
                return True
        return False

    def _organization_json(
        self,
        organization: Organization,
        *,
        execution_only: bool = False,
    ) -> str:
        values = []
        for item in organization.responsibilities:
            if item.status != "ACTIVE":
                continue
            if execution_only and item.responsibility_id in {
                RUN_AUTHORITY_ID,
                CLARIFICATION_ID,
                ORGANIZATION_DESIGN_ID,
                ORGANIZATION_REVIEW_ID,
            }:
                continue
            values.append(self._responsibility_dict(item))
        return json.dumps(
            {"run_id": organization.run_id, "responsibilities": values},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    @staticmethod
    def _responsibility_dict(item: Responsibility) -> dict[str, Any]:
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

    def _bind_conversation(
        self,
        stream: StreamRef,
        responsibility_id: str,
        conversation_id: str,
    ) -> None:
        current = current_organization(self.persistence, stream)
        item = current.responsibility(responsibility_id)
        if item.conversation_id == conversation_id:
            return
        if item.conversation_id is not None and item.conversation_id != conversation_id:
            raise BootstrapError("RESPONSIBILITY_CONVERSATION_REBIND_FORBIDDEN")
        candidate = with_responsibilities(
            current,
            (replace(item, conversation_id=conversation_id),),
        )
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=candidate,
                reason=f"Bind first Modelrail conversation for {responsibility_id}",
            ),
        )

    def _turn(
        self,
        stream: StreamRef,
        run_id: str,
        provider: str,
        responsibility_id: str,
        prompt: str,
    ) -> str:
        # Expose the current stream to pure parsing helpers invoked during this closed
        # synchronous transaction; it is never durable or authoritative state.
        self._current_stream = stream
        organization = current_organization(self.persistence, stream)
        responsibility = organization.responsibility(responsibility_id)
        conversation_id = responsibility.conversation_id
        fresh_id = self._conversation_id(run_id, responsibility_id)
        request = TurnRequest(
            provider=provider,
            prompt=prompt,
            conversation_id=conversation_id,
            new_conversation_id=None if conversation_id else fresh_id,
        )
        try:
            result = self.turn_api.run(
                request,
                timeout=self.timeout,
                poll=self.poll,
            )
        except Exception as exc:
            raise BootstrapError(
                f"MODELRAIL_TURN_FAILED:{responsibility_id}:{exc}"
            ) from exc
        text = result.text.strip()
        if not text:
            raise BootstrapError(f"MODELRAIL_OUTPUT_EMPTY:{responsibility_id}")
        self._bind_conversation(
            stream,
            responsibility_id,
            result.ref.conversation_id,
        )
        self.persistence.append(
            stream,
            encode_turn_evidence(
                TurnEvidence(
                    responsibility_id=responsibility_id,
                    conversation_id=result.ref.conversation_id,
                    turn_id=result.ref.turn_id,
                )
            ),
        )
        return text

    @staticmethod
    def _conversation_id(run_id: str, responsibility_id: str) -> str:
        value = f"mandate-{run_id}-{responsibility_id}"
        return re.sub(r"[^A-Za-z0-9._-]+", "-", value)

    def _outcome(
        self,
        run_id: str,
        stream: StreamRef,
        top_work_ref: str,
        external_request: str | None = None,
    ) -> BootstrapOutcome:
        projection = self._ledger(stream).projection()
        decisions = self._work_decisions(projection, top_work_ref)
        results = self._work_results(projection, top_work_ref)
        latest_decision = decisions[-1] if decisions else None
        latest_result = results[-1] if results else None
        organization = current_organization(self.persistence, stream)
        return BootstrapOutcome(
            run_id=run_id,
            work_ref=top_work_ref,
            decision_ref=latest_decision.ref if latest_decision else None,
            decision=latest_decision.value.decision if latest_decision else None,
            judgment=latest_decision.value.judgment if latest_decision else None,
            result_body=latest_result.value.body if latest_result else None,
            accepted=top_work_ref in projection.closed_work_refs(),
            external_request=external_request,
            mission_manifest=self._manifest(stream),
            organization=json.loads(self._organization_json(organization)),
        )
