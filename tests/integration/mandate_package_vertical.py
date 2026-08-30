from __future__ import annotations

from dataclasses import dataclass

from mandate.bootstrap import AuthoritativeInput, BootstrapAPI, encode_input
from mandate.organization import current_organization
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


def _append_human(
    persistence: MemoryPersistence,
    run_id: str,
    decision_ref: str,
    body: str,
) -> None:
    persistence.append(
        persistence.resolve_stream(run_id),
        encode_input(
            AuthoritativeInput(
                decision_ref=decision_ref,
                actor="HUMAN",
                body=body,
            )
        ),
    )


def self_test() -> None:
    persistence = MemoryPersistence()

    # First process: vague mission must stop at a real Human decision-delta boundary.
    first_turns = FakeTurnAPI(
        [
            (
                "The word organize still permits materially different mission and "
                "organization boundaries.\n"
                "CLARIFICATION_REQUEST: What kind of festival is intended, at roughly "
                "what scale, and does organize mean a plan or actual delivery?"
            ),
            (
                '{"decision":"CONTINUE","judgment":'
                '"The child correctly identified mission-defining deltas.\\n'
                'EXTERNAL_AUTHORITY_CANDIDATE: What kind of festival is intended, at '
                'roughly what scale, and does organize mean a plan or actual delivery?"}'
            ),
            (
                "ROOT preserves the unresolved Human-owned mission delta and cannot "
                "legitimately finalize the organization.\n"
                "EXTERNAL_AUTHORITY_CANDIDATE: What kind of festival is intended, at "
                "roughly what scale, and does organize mean a plan or actual delivery?"
            ),
            (
                '{"decision":"CONTINUE","judgment":'
                '"Human authority is required before organization can be finalized.\\n'
                'BOOTSTRAP_REQUEST: What kind of festival is intended, at roughly what '
                'scale, and does organize mean a plan or actual delivery?"}'
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
    stream = persistence.resolve_stream("RUN-1")
    org = current_organization(persistence, stream)
    assert org.root().responsibility_id == "ROOT"
    assert org.responsibility("MISSION-CLARIFICATION").conversation_id is not None
    clarifier_conversation = org.responsibility("MISSION-CLARIFICATION").conversation_id
    root_conversation = org.responsibility("ROOT").conversation_id

    _append_human(
        persistence,
        "RUN-1",
        outcome.decision_ref,
        (
            "Es soll ein kommerzielles öffentliches Musik- und Tanzfestival für bis zu "
            "etwa 1.000 Personen werden. Gewünschtes Endergebnis ist ein belastbarer "
            "Festivalplan; Durchführung ist nicht Teil dieser Mission."
        ),
    )

    # Fresh process: same clarification ownership resumes, then organization is designed,
    # independently reviewed, recursively expanded, reintegrated, and stopped for Human
    # approval of the current organization.
    second_turns = FakeTurnAPI(
        [
            (
                "MISSION MANIFEST\n"
                "Authoritative intent: commercial public music and dance festival, up to "
                "about 1,000 people; terminal outcome is a robust festival plan, not actual "
                "delivery. Audience details and solution choices remain delegated where "
                "mission-neutral.\nMISSION_MANIFEST_READY"
            ),
            '{"decision":"ACCEPT","judgment":"The Mission Manifest now preserves the authoritative decision deltas and deferred unknowns."}',
            (
                '{"rationale":"Distinct market, commercial, realizability, and legitimacy '
                'judgment surfaces require separate accountable depth.","responsibilities":['
                '{"responsibility_id":"PROPOSITION","title":"Festival Proposition & Audience",'
                '"parent_responsibility_id":"ROOT","authority":{"delegate":false,"accept_child_results":false},'
                '"mandate":"Own proposition and audience-fit judgment without fixing deferred audience details as Human commitments.",'
                '"prohibited_scope":["Market-demand primary evidence"]},'
                '{"responsibility_id":"MARKET","title":"Market Demand & Reach",'
                '"parent_responsibility_id":"ROOT","authority":{"delegate":true,"accept_child_results":true},'
                '"mandate":"Own independent market-demand and audience-reach evidence and judgment.",'
                '"prohibited_scope":["Commercial viability policy","Festival operations"]},'
                '{"responsibility_id":"COMMERCIAL","title":"Commercial Viability",'
                '"parent_responsibility_id":"ROOT","authority":{"delegate":false,"accept_child_results":false},'
                '"mandate":"Own economic viability evidence and integrated commercial judgment.",'
                '"prohibited_scope":["Market-demand primary evidence"]},'
                '{"responsibility_id":"REALIZABILITY","title":"Festival Realizability & Operations",'
                '"parent_responsibility_id":"ROOT","authority":{"delegate":false,"accept_child_results":false},'
                '"mandate":"Own operational realizability of the planned festival.",'
                '"prohibited_scope":["External permission authority"]},'
                '{"responsibility_id":"LEGITIMACY","title":"Safety, Permissions & External Constraints",'
                '"parent_responsibility_id":"ROOT","authority":{"delegate":false,"accept_child_results":false},'
                '"mandate":"Own independent safety, permission, and external-constraint judgment.",'
                '"prohibited_scope":["Commercial strategy"]}'
                ']}'
            ),
            '{"disposition":"ACCEPTABLE","judgment":"The broad boundaries are mission-derived and non-collapsed.","findings":[]}',
            '{"decision":"ACCEPT","judgment":"The independent review completed its assigned review contract."}',
            '{"decision":"ACCEPT","judgment":"The broad candidate passed independent review without authority expansion or collapse."}',
            (
                '{"rationale":"Market-demand authority needs separate discovery and reach '
                'evidence children before substantive work.","children":['
                '{"responsibility_id":"MARKET-DISCOVERY","title":"Demand Discovery",'
                '"authority":{"delegate":false,"accept_child_results":false},'
                '"mandate":"Own primary demand evidence discovery and provenance.",'
                '"prohibited_scope":["Audience reach execution"]},'
                '{"responsibility_id":"AUDIENCE-REACH","title":"Audience Reach Evidence",'
                '"authority":{"delegate":false,"accept_child_results":false},'
                '"mandate":"Own reach/channel evidence needed for market judgment.",'
                '"prohibited_scope":["Primary proposition ownership"]}'
                ']}'
            ),
            '{"decision":"ACCEPT","judgment":"The proposed children preserve Market parent accountability and create justified evidence boundaries."}',
            '{"disposition":"ACCEPTABLE","judgment":"The recursively expanded whole topology is coherent and retains independent evidence surfaces.","findings":[]}',
            '{"decision":"ACCEPT","judgment":"The independent final review completed its contract and is acceptable."}',
            (
                "ROOT reintegrates the approved Mission Manifest with the independently "
                "challenged recursive topology. No substantive festival work has begun. "
                "The current organization now requires explicit Human approval."
            ),
            (
                '{"decision":"CONTINUE","judgment":'
                '"All pre-execution structure checks are satisfied, but Human approval of '
                'the current organization is reserved.\\nBOOTSTRAP_REQUEST: Review the '
                'current organization and either approve it explicitly or provide the '
                'changes you require."}'
            ),
        ]
    )
    second = BootstrapAPI(persistence, second_turns)
    approval_gate = second.resume(run_id="RUN-1")
    assert approval_gate.accepted is False
    assert approval_gate.decision == "CONTINUE"
    assert approval_gate.external_request is not None
    assert approval_gate.decision_ref is not None
    assert approval_gate.mission_manifest is not None

    org = current_organization(persistence, stream)
    assert org.responsibility("MISSION-CLARIFICATION").conversation_id == clarifier_conversation
    assert org.responsibility("ROOT").conversation_id == root_conversation
    assert org.responsibility("MISSION-CLARIFICATION").status == "RETIRED"
    assert org.responsibility("ORGANIZATION-DESIGN").status == "RETIRED"
    assert org.responsibility("ORGANIZATION-REVIEW").status == "RETIRED"
    assert org.children("MARKET")
    assert {child.responsibility_id for child in org.children("MARKET")} == {
        "MARKET-DISCOVERY",
        "AUDIENCE-REACH",
    }

    _append_human(
        persistence,
        "RUN-1",
        approval_gate.decision_ref,
        "Ich genehmige die aktuelle Organisation ausdrücklich so, wie sie vorliegt.",
    )

    # Another fresh process reconstructs everything from Persistence and can accept only
    # after the Human approval correlated to the current organization gate.
    third_turns = FakeTurnAPI(
        [
            (
                "ROOT confirms that the authoritative Human input explicitly approves the "
                "current, unchanged organization. The pre-execution package remains complete; "
                "substantive execution is still not released by this Result."
            ),
            '{"decision":"ACCEPT","judgment":"The current organization has explicit Human approval and every pre-execution acceptance statement is satisfied. Acceptance ends Bootstrap only."}',
        ]
    )
    third = BootstrapAPI(persistence, third_turns)
    accepted = third.resume(run_id="RUN-1")
    assert accepted.accepted is True
    assert accepted.external_request is None
    assert accepted.decision == "ACCEPT"

    # Cold resume reuses durable responsibility conversations instead of creating fresh
    # semantic actors after process loss.
    assert third_turns.calls[0].conversation_id == root_conversation
    run_authority_conversation = current_organization(
        persistence, stream
    ).responsibility("RUN-AUTHORITY").conversation_id
    assert third_turns.calls[1].conversation_id == run_authority_conversation

    print("MANDATE_PACKAGE_VERTICAL_SELF_TEST_OK")


if __name__ == "__main__":
    self_test()
