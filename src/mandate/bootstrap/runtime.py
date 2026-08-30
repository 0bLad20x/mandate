"""Modelrail Turn execution for Mandate responsibilities.

This module owns only the execution boundary between a canonical Mandate
Responsibility and Modelrail TurnAPI. Responsibility identity/conversation binding
is persisted in the Organization; Modelrail remains execution substrate only.
"""

from __future__ import annotations

import re
from dataclasses import replace

from modelrail.conversation.turn import TurnAPI, TurnRequest

from mandate.organization import (
    OrganizationSnapshot,
    append_snapshot,
    current_organization,
    with_responsibilities,
)
from mandate.persistence import Persistence, StreamRef

from .contract import TurnEvidence, encode_turn_evidence


class ResponsibilityTurnError(RuntimeError):
    pass


class ResponsibilityTurns:
    def __init__(
        self,
        persistence: Persistence,
        turn_api: TurnAPI,
        *,
        timeout: float,
        poll: float,
    ) -> None:
        self.persistence = persistence
        self.turn_api = turn_api
        self.timeout = max(10.0, timeout)
        self.poll = max(0.1, poll)

    def run(
        self,
        stream: StreamRef,
        *,
        run_id: str,
        provider: str,
        responsibility_id: str,
        prompt: str,
    ) -> str:
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
            raise ResponsibilityTurnError(
                f"MODELRAIL_TURN_FAILED:{responsibility_id}:{exc}"
            ) from exc
        text = result.text.strip()
        if not text:
            raise ResponsibilityTurnError(
                f"MODELRAIL_OUTPUT_EMPTY:{responsibility_id}"
            )
        self._bind_conversation(
            stream,
            responsibility_id=responsibility_id,
            conversation_id=result.ref.conversation_id,
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

    def _bind_conversation(
        self,
        stream: StreamRef,
        *,
        responsibility_id: str,
        conversation_id: str,
    ) -> None:
        current = current_organization(self.persistence, stream)
        item = current.responsibility(responsibility_id)
        if item.conversation_id == conversation_id:
            return
        if item.conversation_id is not None:
            raise ResponsibilityTurnError(
                "RESPONSIBILITY_CONVERSATION_REBIND_FORBIDDEN"
            )
        candidate = with_responsibilities(
            current,
            (replace(item, conversation_id=conversation_id),),
        )
        append_snapshot(
            self.persistence,
            stream,
            OrganizationSnapshot(
                organization=candidate,
                reason=(
                    f"Bind first Modelrail conversation for {responsibility_id}"
                ),
            ),
        )

    @staticmethod
    def _conversation_id(run_id: str, responsibility_id: str) -> str:
        value = f"mandate-{run_id}-{responsibility_id}"
        return re.sub(r"[^A-Za-z0-9._-]+", "-", value)
