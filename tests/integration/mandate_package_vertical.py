from __future__ import annotations

from dataclasses import dataclass

from mandate.bootstrap import AuthoritativeInput, BootstrapAPI, encode_input
from mandate.persistence import PersistedEntry, StreamRef
from modelrail.conversation.turn import TurnRef


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
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls = []

    def run(self, request, *, timeout: float, poll: float):
        self.calls.append(request)
        if not self.outputs:
            raise RuntimeError("NO_FAKE_OUTPUT")
        cid = request.conversation_id or request.new_conversation_id
        assert cid is not None
        return FakeResult(
            ref=TurnRef(
                conversation_id=cid,
                provider=request.provider,
                turn_id=f"T{len(self.calls):04d}",
            ),
            _text=self.outputs.pop(0),
        )


def self_test() -> None:
    persistence = MemoryPersistence()
    first_turns = FakeTurnAPI(
        [
            "Candidate requiring Human authority.",
            (
                '{"decision":"CONTINUE","judgment":'
                '"Mission-defining Human authority is required now.\\n\\n'
                'BOOTSTRAP_REQUEST: Specify the intended festival end state and '
                'the terminal meaning of organize."}'
            ),
        ]
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

    # Human input already exists in the one durable truth before a fresh API resumes.
    stream = persistence.resolve_stream("RUN-1")
    persistence.append(
        stream,
        encode_input(
            AuthoritativeInput(
                decision_ref=outcome.decision_ref,
                actor="HUMAN",
                body=(
                    "Es soll ein kommerzielles öffentliches Musik- und Tanzfestival "
                    "für bis zu etwa 1.000 Personen werden. Endergebnis ist ein "
                    "belastbarer Festivalplan; Durchführung ist nicht Teil der Mission."
                ),
            )
        ),
    )

    second_turns = FakeTurnAPI(
        [
            "Reconsidered candidate after authoritative Human input.",
            '{"decision":"ACCEPT","judgment":"All Bootstrap acceptance statements are satisfied."}',
        ]
    )
    second = BootstrapAPI(persistence, second_turns)
    accepted = second.resume(run_id="RUN-1")
    assert accepted.accepted is True
    assert accepted.external_request is None

    # Both semantic perspectives resume their persisted Modelrail conversation identity.
    assert second_turns.calls[0].conversation_id is not None
    assert second_turns.calls[0].new_conversation_id is None
    assert second_turns.calls[1].conversation_id is not None
    assert second_turns.calls[1].new_conversation_id is None

    print("MANDATE_PACKAGE_VERTICAL_SELF_TEST_OK")


if __name__ == "__main__":
    self_test()
