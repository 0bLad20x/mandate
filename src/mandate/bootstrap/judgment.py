"""Accountable Decision execution for Bootstrap Work.

A child Result is judged by its Work issuer. ROOT Results are judged by
RUN-AUTHORITY. This module does not choose workflow progression; it only executes
and persists the accountable Decision boundary.
"""

from __future__ import annotations

from mandate.accountable_work import Work
from mandate.organization import Organization
from mandate.persistence import StreamRef

from .contract import (
    AuthoritativeInput,
    child_judge_prompt,
    request_from_judgment,
    run_authority_prompt,
)
from .parsing import decision
from .runtime import ResponsibilityTurns
from .work import WorkCoordinator


class JudgmentError(RuntimeError):
    pass


class Judgments:
    def __init__(
        self,
        turns: ResponsibilityTurns,
        work: WorkCoordinator,
    ) -> None:
        self.turns = turns
        self.work = work

    def child(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        provider: str,
        parent_id: str,
        child_id: str,
        work_value: Work,
        result_ref: str,
        result_body: str,
        context: str,
        clarification: bool = False,
    ) -> tuple[str, str]:
        raw = self.turns.run(
            stream,
            run_id=run_id,
            provider=provider,
            responsibility_id=parent_id,
            prompt=child_judge_prompt(
                parent_id=parent_id,
                child_id=child_id,
                work=work_value,
                result_body=result_body,
                context=context,
                clarification=clarification,
            ),
        )
        value = decision(raw, "PARENT_DECISION")
        self.work.append_decision(
            stream,
            actor=parent_id,
            result_ref=result_ref,
            decision=value["decision"],
            judgment=value["judgment"],
        )
        return value["decision"], value["judgment"]

    def root(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        mission: str,
        provider: str,
        work_value: Work,
        result_ref: str,
        root_body: str,
        external_inputs: tuple[AuthoritativeInput, ...],
        current_organization_json: str | None,
        previous_judgment: str | None,
    ) -> tuple[str, str, str]:
        raw = self.turns.run(
            stream,
            run_id=run_id,
            provider=provider,
            responsibility_id="RUN-AUTHORITY",
            prompt=run_authority_prompt(
                mission=mission,
                work=work_value,
                root_result=root_body,
                root_result_ref=result_ref,
                current_organization_json=current_organization_json,
                external_inputs=external_inputs,
                previous_judgment=previous_judgment,
            ),
        )
        value = decision(raw, "RUN_AUTHORITY")
        if value["decision"] == "ACCEPT" and request_from_judgment(
            value["judgment"]
        ) is not None:
            raise JudgmentError("ACCEPT_CANNOT_REQUEST_EXTERNAL_INPUT")
        decision_ref = self.work.append_decision(
            stream,
            actor="RUN-AUTHORITY",
            result_ref=result_ref,
            decision=value["decision"],
            judgment=value["judgment"],
        )
        return decision_ref, value["decision"], value["judgment"]
