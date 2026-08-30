"""Mission-specific organization design, review, recursion, and reintegration gate."""

from __future__ import annotations

import json
from typing import Any

from mandate.organization import Organization, Responsibility, validate_organization
from mandate.persistence import StreamRef

from .contract import (
    CLARIFICATION_ID,
    ORGANIZATION_DESIGN_ID,
    ORGANIZATION_REVIEW_ID,
    RESERVED_RESPONSIBILITY_IDS,
    ROOT_ID,
    AuthoritativeInput,
    organization_design_prompt,
    organization_review_prompt,
    recursive_organization_prompt,
)
from .judgment import Judgments
from .organization_store import OrganizationStore
from .parsing import (
    BootstrapParseError,
    authority,
    json_object,
    required_text,
    review,
    text_list,
)
from .runtime import ResponsibilityTurns
from .work import WorkCoordinator


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


class OrganizationFlowError(RuntimeError):
    pass


class OrganizationFlow:
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

    def run(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
        external_inputs: tuple[AuthoritativeInput, ...],
        force_rebuild: bool = False,
    ) -> tuple[Organization, str]:
        if not force_rebuild and self.final_ready(stream):
            result = self.latest_review_result(
                stream,
                objective=FINAL_REVIEW_OBJECTIVE,
            )
            if result is None:
                raise OrganizationFlowError("FINAL_REVIEW_RESULT_REQUIRED")
            parsed = review(result.value.body)
            return self.organization.current(stream), str(parsed["judgment"])

        self.organization.ensure_coordination(
            stream,
            run_id=run_id,
            responsibility_id=ORGANIZATION_DESIGN_ID,
        )
        self.organization.ensure_coordination(
            stream,
            run_id=run_id,
            responsibility_id=ORGANIZATION_REVIEW_ID,
        )

        global_revision = self.latest_revision_findings(stream)
        while True:
            candidate, _ = self._design_until_initial_review_accepts(
                stream,
                run_id=run_id,
                mission=mission,
                provider=provider,
                manifest=manifest,
                external_inputs=external_inputs,
                global_revision=global_revision,
            )
            candidate = self._recursively_organize(
                stream,
                run_id=run_id,
                mission=mission,
                provider=provider,
                manifest=manifest,
            )
            validate_organization(
                candidate,
                require_single_root=True,
                require_delegating_nodes_have_children=True,
            )

            final_review = self._review_candidate(
                stream,
                run_id=run_id,
                mission=mission,
                provider=provider,
                manifest=manifest,
                candidate=candidate,
                objective=FINAL_REVIEW_OBJECTIVE,
                recursive=True,
            )
            parsed = review(final_review.value.body)
            if parsed["disposition"] == "REVISION_REQUIRED":
                global_revision = final_review.value.body
                continue

            self.organization.retire_coordination(
                stream,
                {
                    CLARIFICATION_ID,
                    ORGANIZATION_DESIGN_ID,
                    ORGANIZATION_REVIEW_ID,
                },
            )
            final = self.organization.current(stream)
            validate_organization(
                final,
                require_single_root=True,
                require_delegating_nodes_have_children=True,
            )
            return final, str(parsed["judgment"])

    def final_ready(self, stream: StreamRef) -> bool:
        final_review = self.latest_review_result(
            stream,
            objective=FINAL_REVIEW_OBJECTIVE,
        )
        if final_review is None:
            return False
        if review(final_review.value.body)["disposition"] != "ACCEPTABLE":
            return False
        organization = self.organization.current(stream)
        if any(
            item.status == "ACTIVE"
            and item.responsibility_id
            in {CLARIFICATION_ID, ORGANIZATION_DESIGN_ID, ORGANIZATION_REVIEW_ID}
            for item in organization.responsibilities
        ):
            return False
        validate_organization(
            organization,
            require_single_root=True,
            require_delegating_nodes_have_children=True,
        )
        return True

    def latest_review_result(
        self,
        stream: StreamRef,
        *,
        objective: str,
    ) -> Any | None:
        work = self.work.latest_work_to(
            stream,
            issuer=ROOT_ID,
            target=ORGANIZATION_REVIEW_ID,
            objective=objective,
            open_only=False,
        )
        if work is None:
            return None
        projection = self.work.ledger(stream).projection()
        if work.ref not in projection.closed_work_refs():
            return None
        results = self.work.work_results(projection, work.ref)
        return results[-1] if results else None

    def latest_revision_findings(self, stream: StreamRef) -> str | None:
        for objective in (FINAL_REVIEW_OBJECTIVE, INITIAL_REVIEW_OBJECTIVE):
            result = self.latest_review_result(stream, objective=objective)
            if result is not None and review(result.value.body)["disposition"] == "REVISION_REQUIRED":
                return result.value.body
        return None

    def _design_until_initial_review_accepts(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
        external_inputs: tuple[AuthoritativeInput, ...],
        global_revision: str | None,
    ) -> tuple[Organization, str]:
        design_work = self.work.issue(
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
            projection = self.work.ledger(stream).projection()
            prior_results = self.work.work_results(projection, design_work.ref)
            prior_decisions = self.work.work_decisions(projection, design_work.ref)
            body = self.turns.run(
                stream,
                run_id=run_id,
                provider=provider,
                responsibility_id=ORGANIZATION_DESIGN_ID,
                prompt=organization_design_prompt(
                    mission=mission,
                    mission_manifest=manifest,
                    prior_candidate=(
                        prior_results[-1].value.body if prior_results else None
                    ),
                    prior_judgment=(
                        prior_decisions[-1].value.judgment
                        if prior_decisions
                        else global_revision
                    ),
                    external_inputs=external_inputs,
                ),
            )
            result_ref = self.work.append_result(
                stream,
                actor=ORGANIZATION_DESIGN_ID,
                work_ref=design_work.ref,
                body=body,
            )
            candidate = self._persist_initial_candidate(
                stream,
                run_id=run_id,
                body=body,
                source_ref=result_ref,
            )
            review_result = self._review_candidate(
                stream,
                run_id=run_id,
                mission=mission,
                provider=provider,
                manifest=manifest,
                candidate=candidate,
                objective=INITIAL_REVIEW_OBJECTIVE,
                recursive=False,
            )
            parsed_review = review(review_result.value.body)
            decision_value, judgment = self.judgments.child(
                stream,
                run_id=run_id,
                provider=provider,
                parent_id=ROOT_ID,
                child_id=ORGANIZATION_DESIGN_ID,
                work_value=design_work.value,
                result_ref=result_ref,
                result_body=body,
                context=(
                    "INDEPENDENT ORGANIZATION REVIEW:\n"
                    + review_result.value.body
                ),
                clarification=False,
            )
            if parsed_review["disposition"] == "REVISION_REQUIRED":
                if decision_value == "ACCEPT":
                    raise OrganizationFlowError(
                        "DESIGN_CANNOT_BE_ACCEPTED_AGAINST_REVISION_REQUIRED_REVIEW"
                    )
                global_revision = review_result.value.body
                continue
            if decision_value == "ACCEPT":
                return candidate, str(parsed_review["judgment"])
            if decision_value != "CONTINUE":
                raise OrganizationFlowError("ROOT_DESIGN_DECISION_INVALID")
            global_revision = judgment

    def _review_candidate(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
        candidate: Organization,
        objective: str,
        recursive: bool,
    ) -> Any:
        review_work = self.work.issue(
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
            body = self.turns.run(
                stream,
                run_id=run_id,
                provider=provider,
                responsibility_id=ORGANIZATION_REVIEW_ID,
                prompt=organization_review_prompt(
                    mission=mission,
                    mission_manifest=manifest,
                    candidate_json=self.organization.json(
                        candidate,
                        execution_only=True,
                    ),
                    recursive=recursive,
                ),
            )
            review(body)
            result_ref = self.work.append_result(
                stream,
                actor=ORGANIZATION_REVIEW_ID,
                work_ref=review_work.ref,
                body=body,
            )
            decision_value, _ = self.judgments.child(
                stream,
                run_id=run_id,
                provider=provider,
                parent_id=ROOT_ID,
                child_id=ORGANIZATION_REVIEW_ID,
                work_value=review_work.value,
                result_ref=result_ref,
                result_body=body,
                context=(
                    "CANDIDATE UNDER REVIEW:\n"
                    + self.organization.json(candidate, execution_only=True)
                ),
                clarification=False,
            )
            if decision_value == "ACCEPT":
                projection = self.work.ledger(stream).projection()
                return projection.results[result_ref]
            if decision_value != "CONTINUE":
                raise OrganizationFlowError("ROOT_REVIEW_DECISION_INVALID")

    def _recursively_organize(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        mission: str,
        provider: str,
        manifest: str,
    ) -> Organization:
        while True:
            organization = self.organization.current(stream)
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
                    raise OrganizationFlowError("RECURSIVE_PARENT_REQUIRED")
                recursive_work = self.work.issue(
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
                    projection = self.work.ledger(stream).projection()
                    prior_results = self.work.work_results(
                        projection, recursive_work.ref
                    )
                    prior_decisions = self.work.work_decisions(
                        projection, recursive_work.ref
                    )
                    body = self.turns.run(
                        stream,
                        run_id=run_id,
                        provider=provider,
                        responsibility_id=responsibility.responsibility_id,
                        prompt=recursive_organization_prompt(
                            mission=mission,
                            mission_manifest=manifest,
                            responsibility=responsibility,
                            current_organization_json=self.organization.json(
                                stream,
                                execution_only=True,
                            ),
                            previous_result=(
                                prior_results[-1].value.body
                                if prior_results
                                else None
                            ),
                            previous_judgment=(
                                prior_decisions[-1].value.judgment
                                if prior_decisions
                                else None
                            ),
                        ),
                    )
                    children = self._recursive_children(
                        stream,
                        run_id=run_id,
                        parent=responsibility,
                        body=body,
                    )
                    result_ref = self.work.append_result(
                        stream,
                        actor=responsibility.responsibility_id,
                        work_ref=recursive_work.ref,
                        body=body,
                    )
                    decision_value, _ = self.judgments.child(
                        stream,
                        run_id=run_id,
                        provider=provider,
                        parent_id=parent_id,
                        child_id=responsibility.responsibility_id,
                        work_value=recursive_work.value,
                        result_ref=result_ref,
                        result_body=body,
                        context=(
                            "PROPOSED CHILD ORGANIZATION:\n"
                            + json.dumps(
                                [
                                    self.organization.responsibility_dict(item)
                                    for item in children
                                ],
                                ensure_ascii=False,
                                indent=2,
                            )
                        ),
                        clarification=False,
                    )
                    if decision_value == "CONTINUE":
                        continue
                    if decision_value != "ACCEPT":
                        raise OrganizationFlowError(
                            "RECURSIVE_PARENT_DECISION_INVALID"
                        )
                    self.organization.merge_children(
                        stream,
                        children,
                        source_ref=result_ref,
                    )
                    break

    def _persist_initial_candidate(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        body: str,
        source_ref: str,
    ) -> Organization:
        raw = json_object(body, "ORGANIZATION_DESIGN_OUTPUT_NOT_JSON")
        if set(raw) != {"rationale", "responsibilities"}:
            raise BootstrapParseError("ORGANIZATION_DESIGN_OUTPUT_SHAPE_INVALID")
        required_text(raw["rationale"], "ORGANIZATION_DESIGN_RATIONALE_REQUIRED")
        rows = raw["responsibilities"]
        if not isinstance(rows, list) or not rows:
            raise BootstrapParseError(
                "ORGANIZATION_DESIGN_RESPONSIBILITIES_REQUIRED"
            )

        current = self.organization.current(stream)
        existing = current.by_id()
        ids: set[str] = set()
        values: list[Responsibility] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "responsibility_id",
                "title",
                "parent_responsibility_id",
                "authority",
                "mandate",
                "prohibited_scope",
            }:
                raise BootstrapParseError(
                    "ORGANIZATION_RESPONSIBILITY_SHAPE_INVALID"
                )
            responsibility_id = required_text(
                row["responsibility_id"],
                "RESPONSIBILITY_ID_REQUIRED",
            )
            if responsibility_id in RESERVED_RESPONSIBILITY_IDS or responsibility_id in ids:
                raise BootstrapParseError(
                    "ORGANIZATION_RESPONSIBILITY_ID_INVALID"
                )
            ids.add(responsibility_id)
            if required_text(
                row["parent_responsibility_id"],
                "RESPONSIBILITY_PARENT_REQUIRED",
            ) != ROOT_ID:
                raise BootstrapParseError(
                    "INITIAL_ORGANIZATION_MUST_DEFINE_BROAD_ROOT_CHILDREN_ONLY"
                )
            previous = existing.get(responsibility_id)
            values.append(
                Responsibility(
                    responsibility_id=responsibility_id,
                    run_id=run_id,
                    title=required_text(
                        row["title"],
                        "RESPONSIBILITY_TITLE_REQUIRED",
                    ),
                    kind="RESPONSIBILITY",
                    parent_responsibility_id=ROOT_ID,
                    authority=authority(row["authority"]),
                    mandate=required_text(
                        row["mandate"],
                        "RESPONSIBILITY_MANDATE_REQUIRED",
                    ),
                    prohibited_scope=text_list(
                        row["prohibited_scope"],
                        "PROHIBITED_SCOPE_INVALID",
                    ),
                    conversation_id=(
                        previous.conversation_id
                        if previous is not None
                        else None
                    ),
                )
            )
        return self.organization.replace_execution_candidate(
            stream,
            values,
            source_ref=source_ref,
        )

    def _recursive_children(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        parent: Responsibility,
        body: str,
    ) -> tuple[Responsibility, ...]:
        raw = json_object(body, "RECURSIVE_ORGANIZATION_OUTPUT_NOT_JSON")
        if set(raw) != {"rationale", "children"}:
            raise BootstrapParseError(
                "RECURSIVE_ORGANIZATION_OUTPUT_SHAPE_INVALID"
            )
        required_text(raw["rationale"], "RECURSIVE_ORGANIZATION_RATIONALE_REQUIRED")
        rows = raw["children"]
        if not isinstance(rows, list) or not rows:
            raise BootstrapParseError("RECURSIVE_CHILDREN_REQUIRED")

        existing = self.organization.current(stream).by_id()
        ids: set[str] = set()
        values: list[Responsibility] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "responsibility_id",
                "title",
                "authority",
                "mandate",
                "prohibited_scope",
            }:
                raise BootstrapParseError("RECURSIVE_CHILD_SHAPE_INVALID")
            responsibility_id = required_text(
                row["responsibility_id"],
                "RESPONSIBILITY_ID_REQUIRED",
            )
            if responsibility_id in RESERVED_RESPONSIBILITY_IDS or responsibility_id in ids:
                raise BootstrapParseError("RECURSIVE_CHILD_ID_INVALID")
            ids.add(responsibility_id)
            previous = existing.get(responsibility_id)
            values.append(
                Responsibility(
                    responsibility_id=responsibility_id,
                    run_id=run_id,
                    title=required_text(
                        row["title"],
                        "RESPONSIBILITY_TITLE_REQUIRED",
                    ),
                    kind="RESPONSIBILITY",
                    parent_responsibility_id=parent.responsibility_id,
                    authority=authority(row["authority"]),
                    mandate=required_text(
                        row["mandate"],
                        "RESPONSIBILITY_MANDATE_REQUIRED",
                    ),
                    prohibited_scope=text_list(
                        row["prohibited_scope"],
                        "PROHIBITED_SCOPE_INVALID",
                    ),
                    conversation_id=(
                        previous.conversation_id
                        if previous is not None
                        else None
                    ),
                )
            )
        return tuple(values)
