"""Vertically integrated Bootstrap API.

Mandate owns semantic coordination. Persistence owns durable storage. Modelrail owns
referenced Turn execution. No authoritative Mandate run-state file exists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from modelrail.conversation.turn import TurnAPI, TurnRequest

from mandate.accountable_work import AccountableWorkLedger, Decision, Result
from mandate.persistence import Persistence, StreamRef

from .contract import (
    BOOTSTRAP_ACTORS,
    AuthoritativeInput,
    TurnEvidence,
    bootstrap_prompt,
    bootstrap_work,
    encode_turn_evidence,
    inputs,
    judge_prompt,
    request_from_judgment,
    turn_evidence,
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


class BootstrapAPI:
    """Public Bootstrap surface; prompts and execution mechanics remain internal."""

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
        ledger = AccountableWorkLedger(
            self.persistence,
            stream,
            BOOTSTRAP_ACTORS,
        )
        projection, _ = ledger.append(
            actor="RUN-AUTHORITY",
            value=bootstrap_work(),
        )
        if len(projection.open_work_refs()) != 1:
            raise BootstrapError("BOOTSTRAP_INITIAL_WORK_INVALID")
        return self._advance(run_id, mission, provider, stream)

    def resume(self, *, run_id: str) -> BootstrapOutcome:
        """Resume only from durable Mandate state already present in Persistence."""

        stream = self.persistence.resolve_stream(run_id)
        metadata = self.persistence.metadata(stream)
        if metadata.get("application") != "mandate.bootstrap":
            raise BootstrapError("BOOTSTRAP_STREAM_APPLICATION_MISMATCH")
        mission = self._required_metadata(metadata, "mission")
        provider = self._required_metadata(metadata, "provider")
        return self._advance(run_id, mission, provider, stream)

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
        ledger = AccountableWorkLedger(
            self.persistence,
            stream,
            BOOTSTRAP_ACTORS,
        )
        while True:
            projection = ledger.projection()
            works = list(projection.work.values())
            if len(works) != 1:
                raise BootstrapError("EXACTLY_ONE_BOOTSTRAP_WORK_REQUIRED")
            work_ref = works[0].ref

            latest_decision = projection.decisions[-1] if projection.decisions else None
            if work_ref in projection.closed_work_refs():
                return self._outcome(run_id, work_ref, projection)

            supplied_inputs = inputs(self.persistence, stream)
            if latest_decision is not None:
                request = request_from_judgment(latest_decision.value.judgment)
                if request is not None:
                    supplied = any(
                        value.decision_ref == latest_decision.ref
                        for value in supplied_inputs
                    )
                    if not supplied:
                        return self._outcome(
                            run_id,
                            work_ref,
                            projection,
                            external_request=request,
                        )

            previous_result = (
                list(projection.results.values())[-1].value.body
                if projection.results
                else None
            )
            previous_judgment = (
                latest_decision.value.judgment
                if latest_decision is not None
                else None
            )

            body = self._turn(
                stream,
                run_id,
                provider,
                "BOOTSTRAP",
                bootstrap_prompt(
                    mission,
                    previous_result,
                    previous_judgment,
                    supplied_inputs,
                ),
            )
            _, result_ref = ledger.append(
                actor="BOOTSTRAP",
                value=Result(work_ref=work_ref, body=body),
            )

            raw = self._turn(
                stream,
                run_id,
                provider,
                "RUN-AUTHORITY",
                judge_prompt(
                    mission,
                    body,
                    result_ref,
                    previous_judgment,
                    supplied_inputs,
                ),
            )
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise BootstrapError("RUN_AUTHORITY_OUTPUT_NOT_JSON") from exc
            if not isinstance(value, dict) or set(value) != {"decision", "judgment"}:
                raise BootstrapError("RUN_AUTHORITY_OUTPUT_SHAPE_INVALID")

            decision = str(value["decision"])
            judgment = str(value["judgment"])
            if decision not in {"ACCEPT", "CONTINUE"}:
                raise BootstrapError("RUN_AUTHORITY_DECISION_INVALID")
            request = request_from_judgment(judgment)
            if decision == "ACCEPT" and request is not None:
                raise BootstrapError("ACCEPT_CANNOT_REQUEST_EXTERNAL_INPUT")

            ledger.append(
                actor="RUN-AUTHORITY",
                value=Decision(
                    result_ref=result_ref,
                    decision=decision,
                    judgment=judgment,
                ),
            )
            # The next loop re-reads Persistence. No Mandate-local mutable state decides
            # what Work, Result, Decision, Human input, or conversation binding exists.

    def _turn(
        self,
        stream: StreamRef,
        run_id: str,
        provider: str,
        perspective: str,
        prompt: str,
    ) -> str:
        evidence = [
            value
            for value in turn_evidence(self.persistence, stream)
            if value.perspective == perspective
        ]
        conversation_id = (
            evidence[-1].conversation_id
            if evidence
            else f"mandate-{run_id}-{perspective.lower()}"
        )
        request = TurnRequest(
            provider=provider,
            prompt=prompt,
            conversation_id=conversation_id if evidence else None,
            new_conversation_id=None if evidence else conversation_id,
        )
        try:
            result = self.turn_api.run(
                request,
                timeout=self.timeout,
                poll=self.poll,
            )
        except Exception as exc:
            raise BootstrapError(
                f"MODELRAIL_TURN_FAILED:{perspective}:{exc}"
            ) from exc
        text = result.text.strip()
        if not text:
            raise BootstrapError(f"MODELRAIL_OUTPUT_EMPTY:{perspective}")
        self.persistence.append(
            stream,
            encode_turn_evidence(
                TurnEvidence(
                    perspective=perspective,
                    conversation_id=result.ref.conversation_id,
                    turn_id=result.ref.turn_id,
                )
            ),
        )
        return text

    @staticmethod
    def _outcome(
        run_id: str,
        work_ref: str,
        projection: Any,
        external_request: str | None = None,
    ) -> BootstrapOutcome:
        latest_decision = projection.decisions[-1] if projection.decisions else None
        latest_result = (
            list(projection.results.values())[-1]
            if projection.results
            else None
        )
        return BootstrapOutcome(
            run_id=run_id,
            work_ref=work_ref,
            decision_ref=latest_decision.ref if latest_decision else None,
            decision=latest_decision.value.decision if latest_decision else None,
            judgment=latest_decision.value.judgment if latest_decision else None,
            result_body=latest_result.value.body if latest_result else None,
            accepted=work_ref in projection.closed_work_refs(),
            external_request=external_request,
        )
