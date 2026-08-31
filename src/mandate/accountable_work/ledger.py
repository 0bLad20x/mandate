"""Persistence-backed codec and ledger for the frozen accountable-work core.

The core owns semantic validity. This module only serializes canonical records and
reconstructs them through the backend-neutral Persistence boundary.
"""

from __future__ import annotations

import json
import secrets
from typing import Mapping

from mandate.persistence import Persistence, StreamRef

from .core import (
    ActorAuthority,
    CanonicalRecord,
    Decision,
    Projection,
    Result,
    SemanticValue,
    Work,
    apply_record,
    project,
)

_PROTOCOL = "mandate.accountable_work:v1"


def _encode_value(value: SemanticValue) -> dict[str, object]:
    if isinstance(value, Work):
        return {
            "work": {
                "to": value.to,
                "objective": value.objective,
                "acceptance": list(value.acceptance),
            }
        }
    if isinstance(value, Result):
        return {
            "result": {
                "work_ref": value.work_ref,
                "body": value.body,
            }
        }
    if isinstance(value, Decision):
        return {
            "decision": {
                "result_ref": value.result_ref,
                "decision": value.decision,
                "judgment": value.judgment,
            }
        }
    raise TypeError("UNKNOWN_SEMANTIC_VALUE")


def _decode_value(raw: object) -> SemanticValue:
    if not isinstance(raw, dict) or len(raw) != 1:
        raise ValueError("SEMANTIC_VALUE_SHAPE_INVALID")
    kind, value = next(iter(raw.items()))
    if not isinstance(value, dict):
        raise ValueError("SEMANTIC_VALUE_PAYLOAD_INVALID")

    if kind == "work":
        if (
            set(value) != {"to", "objective", "acceptance"}
            or not isinstance(value["acceptance"], list)
        ):
            raise ValueError("WORK_SHAPE_INVALID")
        return Work(
            to=str(value["to"]),
            objective=str(value["objective"]),
            acceptance=tuple(str(item) for item in value["acceptance"]),
        )

    if kind == "result":
        if set(value) != {"work_ref", "body"}:
            raise ValueError("RESULT_SHAPE_INVALID")
        return Result(
            work_ref=str(value["work_ref"]),
            body=str(value["body"]),
        )

    if kind == "decision":
        if set(value) != {"result_ref", "decision", "judgment"}:
            raise ValueError("DECISION_SHAPE_INVALID")
        return Decision(
            result_ref=str(value["result_ref"]),
            decision=str(value["decision"]),
            judgment=str(value["judgment"]),
        )

    raise ValueError("SEMANTIC_VALUE_KIND_UNKNOWN")


def encode_record(record: CanonicalRecord) -> str:
    return json.dumps(
        {
            "protocol": _PROTOCOL,
            "ref": record.ref,
            "actor": record.actor,
            "value": _encode_value(record.value),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def decode_record(body: str) -> CanonicalRecord | None:
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict) or raw.get("protocol") != _PROTOCOL:
        return None
    if set(raw) != {"protocol", "ref", "actor", "value"}:
        raise ValueError("ACCOUNTABLE_WORK_RECORD_SHAPE_INVALID")
    return CanonicalRecord(
        ref=str(raw["ref"]),
        actor=str(raw["actor"]),
        value=_decode_value(raw["value"]),
    )


def new_record_ref() -> str:
    """Create a stable semantic identity without stream-local numbering."""

    return f"R-{secrets.token_hex(12)}"


class AccountableWorkLedger:
    """One persistence stream projected through the frozen Work Core."""

    def __init__(
        self,
        persistence: Persistence,
        stream: StreamRef,
        actors: Mapping[str, ActorAuthority],
    ) -> None:
        self.persistence = persistence
        self.stream = stream
        self.actors = actors

    def records(self) -> tuple[CanonicalRecord, ...]:
        out: list[CanonicalRecord] = []
        for entry in self.persistence.read(self.stream):
            record = decode_record(entry.body)
            if record is not None:
                out.append(record)
        return tuple(out)

    def projection(self) -> Projection:
        return project(self.records(), self.actors)

    def append(
        self,
        *,
        actor: str,
        value: SemanticValue,
    ) -> tuple[Projection, str]:
        records = list(self.records())
        ref = new_record_ref()
        record = CanonicalRecord(ref=ref, actor=actor, value=value)

        # Validate the candidate against the semantic core before durable append.
        candidate = project(records, self.actors)
        apply_record(candidate, record, self.actors)

        self.persistence.append(self.stream, encode_record(record))
        return project(tuple(records + [record]), self.actors), ref
