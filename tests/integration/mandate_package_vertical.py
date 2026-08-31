"""Deterministic vertical for the Mandate package boundaries."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from inspect import signature
from tempfile import TemporaryDirectory

from mandate.bootstrap import BootstrapAPI
from mandate.bootstrap.contract import TurnEvidence, encode_turn_evidence, turn_evidence
from mandate.persistence import PersistedEntry, StreamRef
from modelrail.conversation.turn import TurnAPI, TurnRef


class MemoryPersistence:
    backend = "memory"

    def __init__(self) -> None:
        self.streams: dict[str, list[PersistedEntry]] = {}
        self.meta: dict[str, dict[str, str]] = {}

    def create_stream(self, run_id: str, metadata):
        self.streams[run_id] = []
        self.meta[run_id] = {"run_id": run_id, **dict(metadata)}
        return StreamRef(self.backend, run_id)

    def resolve_stream(self, run_id: str) -> StreamRef:
        if run_id not in self.streams:
            raise KeyError(run_id)
        return StreamRef(self.backend, run_id)

    def metadata(self, stream: StreamRef):
        return dict(self.meta[stream.value])

    def append(self, stream: StreamRef, body: str) -> PersistedEntry:
        rows = self.streams[stream.value]
        entry = PersistedEntry(str(len(rows) + 1), body)
        rows.append(entry)
        return entry

    def read(self, stream: StreamRef) -> tuple[PersistedEntry, ...]:
        return tuple(self.streams[stream.value])


@dataclass
class FakeResult:
    ref: TurnRef
    _text: str

    @property
    def text(self) -> str:
        return self._text


class FakeTurnAPI:
    def __init__(
        self,
        outputs: list[str],
        *,
        label: str,
        recovered: dict[str, TurnRef] | None = None,
    ) -> None:
        self.outputs = list(outputs)
        self.label = label
        self.recovered = dict(recovered or {})
        self.recover_calls: list[tuple[str, str]] = []
        self.submit_calls = []
        self.wait_calls: list[TurnRef] = []
        self.latest_refs: dict[str, TurnRef] = dict(self.recovered)

    def recover(self, conversation_id: str, *, provider: str):
        self.recover_calls.append((conversation_id, provider))
        return self.recovered.get(conversation_id)

    def submit(self, request):
        self.submit_calls.append(request)
        cid = request.conversation_id or request.new_conversation_id
        assert cid is not None
        ref = TurnRef(
            conversation_id=cid,
            provider=request.provider,
            turn_id=f"{self.label}-{len(self.submit_calls):04d}",
        )
        self.latest_refs[cid] = ref
        return ref

    def wait(self, ref: TurnRef, *, poll: float):
        self.wait_calls.append(ref)
        if not self.outputs:
            raise RuntimeError("NO_FAKE_OUTPUT")
        return FakeResult(ref=ref, _text=self.outputs.pop(0))


def self_test() -> None:
    assert signature(TurnAPI.wait).parameters["timeout"].default is None
    assert signature(TurnAPI.run).parameters["timeout"].default is None
    assert signature(TurnAPI.wait_any).parameters["timeout"].default is None
    assert signature(TurnAPI.wait_all).parameters["timeout"].default is None
    assert "timeout" not in signature(BootstrapAPI).parameters
    with TemporaryDirectory() as td:
        assert TurnAPI(td).recover("missing", provider="chatgpt") is None

    persistence = MemoryPersistence()
    first_turns = FakeTurnAPI(
        [
            "Candidate requiring Human authority.",
            (
                '{"decision":"CONTINUE","judgment":'
                '"Mission-defining Human authority is required now.\\n\\n'
                'BOOTSTRAP_REQUEST: Specify the intended festival end state and '
                'the terminal meaning of organize.\\n'
                'BOOTSTRAP_CONTINUATION: EXTERNAL_INPUT"}'
            ),
        ],
        label="FIRST",
    )
    first = BootstrapAPI(persistence, first_turns)
    outcome = first.start(
        run_id="RUN-1",
        mission="Ich möchte ein Festival organisieren.",
        provider="chatgpt",
    )
    assert outcome.accepted is False
    assert outcome.external_request is not None
    assert outcome.decision == "CONTINUE"
    assert outcome.decision_ref is not None
    assert len(first_turns.submit_calls) == 2

    # Fresh API instance: mission/provider remain reconstructed from Persistence.
    # The historical package still accepts authoritative input through resume().
    second_turns = FakeTurnAPI(
        [
            "Reconsidered candidate after authoritative Human input.",
            (
                '{"decision":"ACCEPT","judgment":'
                '"All Bootstrap acceptance statements are satisfied.\\n'
                'BOOTSTRAP_CONTINUATION: COMPLETE"}'
            ),
        ],
        label="SECOND",
        recovered=first_turns.latest_refs,
    )
    second = BootstrapAPI(persistence, second_turns)
    accepted = second.resume(
        run_id="RUN-1",
        authoritative_input=(
            "Es soll ein kommerzielles öffentliches Musik- und Tanzfestival "
            "für bis zu etwa 1.000 Personen werden. Endergebnis ist ein "
            "belastbarer Festivalplan; Durchführung ist nicht Teil der Mission."
        ),
    )
    assert accepted.accepted is True
    assert accepted.external_request is None

    # Completed refs are already recorded as Mandate TurnEvidence, so the next
    # semantic pass submits follow-ups in the same durable Conversations.
    assert len(second_turns.submit_calls) == 2
    assert second_turns.submit_calls[0].conversation_id is not None
    assert second_turns.submit_calls[0].new_conversation_id is None
    assert second_turns.submit_calls[1].conversation_id is not None
    assert second_turns.submit_calls[1].new_conversation_id is None

    # An active Modelrail Turn with no matching Mandate TurnEvidence is resumed
    # directly. The Bootstrap prompt is not replayed into a second logical Turn.
    recovery_persistence = MemoryPersistence()
    active_bootstrap_ref = TurnRef(
        conversation_id="mandate-RUN-RECOVERY-bootstrap",
        provider="chatgpt",
        turn_id="ACTIVE-BOOTSTRAP",
    )
    recovering_turns = FakeTurnAPI(
        [
            "Recovered Bootstrap result.",
            (
                '{"decision":"ACCEPT","judgment":'
                '"Recovered execution is sufficient.\\n'
                'BOOTSTRAP_CONTINUATION: COMPLETE"}'
            ),
        ],
        label="RECOVERY",
        recovered={active_bootstrap_ref.conversation_id: active_bootstrap_ref},
    )
    recovered_outcome = BootstrapAPI(
        recovery_persistence,
        recovering_turns,
    ).start(
        run_id="RUN-RECOVERY",
        mission="Bounded recovery proof.",
        provider="chatgpt",
    )
    assert recovered_outcome.accepted is True
    assert recovering_turns.wait_calls[0] == active_bootstrap_ref
    assert all(
        (request.conversation_id or request.new_conversation_id)
        != active_bootstrap_ref.conversation_id
        for request in recovering_turns.submit_calls
    )

    # If TurnEvidence was persisted but the corresponding semantic Result was not,
    # the same completed Turn is re-read instead of being mistaken for consumed
    # history and replaced by a follow-up.
    evidence_persistence = MemoryPersistence()
    evidence_stream = evidence_persistence.create_stream("RUN-EVIDENCE", {})
    evidence_ref = TurnRef(
        conversation_id="mandate-RUN-EVIDENCE-bootstrap",
        provider="chatgpt",
        turn_id="EVIDENCE-NOT-CONSUMED",
    )
    evidence_persistence.append(
        evidence_stream,
        encode_turn_evidence(
            TurnEvidence(
                perspective="BOOTSTRAP",
                conversation_id=evidence_ref.conversation_id,
                turn_id=evidence_ref.turn_id,
            )
        ),
    )
    evidence_turns = FakeTurnAPI(
        ["Recovered result after evidence-only crash."],
        label="EVIDENCE",
        recovered={evidence_ref.conversation_id: evidence_ref},
    )
    recovered_body = BootstrapAPI(evidence_persistence, evidence_turns)._turn(
        evidence_stream,
        "RUN-EVIDENCE",
        "chatgpt",
        "BOOTSTRAP",
        "same logical prompt",
        consumed_turns=0,
    )
    assert recovered_body == "Recovered result after evidence-only crash."
    assert evidence_turns.submit_calls == []
    assert evidence_turns.wait_calls == [evidence_ref]
    assert len(turn_evidence(evidence_persistence, evidence_stream)) == 1

    print("MANDATE_PACKAGE_VERTICAL_SELF_TEST_OK")
    print("MANDATE_ACTIVE_TURN_RECOVERY_OK")
    print("MANDATE_UNCONSUMED_TURN_EVIDENCE_RECOVERY_OK")
    print("MODELRAIL_UNBOUNDED_WAIT_DEFAULT_OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        raise SystemExit("Use --self-test")


if __name__ == "__main__":
    main()
