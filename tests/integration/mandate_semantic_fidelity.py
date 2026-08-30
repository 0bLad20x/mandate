from __future__ import annotations

from dataclasses import dataclass

from mandate.bootstrap import BootstrapAPI
from mandate.bootstrap.contract import (
    bootstrap_work,
    clarification_prompt,
    organization_design_prompt,
    organization_review_prompt,
)
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
        return StreamRef(self.backend, run_id)

    def metadata(self, stream: StreamRef):
        return dict(self.meta[stream.value])

    def append(self, stream: StreamRef, body: str) -> PersistedEntry:
        entry = PersistedEntry(str(len(self.streams[stream.value]) + 1), body)
        self.streams[stream.value].append(entry)
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
        assert cid
        return FakeResult(
            TurnRef(
                conversation_id=cid,
                provider=request.provider,
                turn_id=f"T{len(self.calls):04d}",
            ),
            self.outputs.pop(0),
        )


def _decision(value: str, judgment: str) -> str:
    import json

    return json.dumps({"decision": value, "judgment": judgment})


def _review(disposition: str, judgment: str, findings: list[dict] | None = None) -> str:
    import json

    return json.dumps(
        {
            "disposition": disposition,
            "judgment": judgment,
            "findings": findings or [],
        }
    )


def _cross_domain() -> None:
    persistence = MemoryPersistence()
    outputs = [
        (
            "MISSION MANIFEST\nThe Human explicitly wants deep independent exploration "
            "of motorsport and gardening followed by novel cross-domain synthesis. The "
            "specific resulting concepts remain delegated creative choices.\n"
            "MISSION_MANIFEST_READY"
        ),
        _decision("ACCEPT", "The manifest preserves the clear cross-domain intent."),
        (
            '{"rationale":"One general creative owner can cover the request.",'
            '"responsibilities":[{"responsibility_id":"GENERIC-CREATIVE",'
            '"title":"Creative Exploration","parent_responsibility_id":"ROOT",'
            '"authority":{"delegate":false,"accept_child_results":false},'
            '"mandate":"Explore motorsport and gardening together and generate ideas.",'
            '"prohibited_scope":[]}]}'
        ),
        _review(
            "REVISION_REQUIRED",
            "The candidate collapses independent source-domain evidence and synthesis judgment.",
            [
                {
                    "evidence": "GENERIC-CREATIVE owns both source domains and their synthesis.",
                    "boundary": "Distinct epistemic depth needed for reliable cross-domain synthesis must not be collapsed merely because one actor can discuss both topics.",
                    "consequence": "Shallow shared-context ideation can replace independent motorsport and gardening models, eliminating contradictory findings and accountable synthesis.",
                    "revision": "Create independently accountable motorsport and gardening knowledge/evidence surfaces plus a synthesis responsibility that owns cross-domain transfer and reintegration.",
                }
            ],
        ),
        _decision("ACCEPT", "The independent review completed its contract."),
        _decision("CONTINUE", "The design collapses materially distinct epistemic surfaces and must be reconsidered as a whole."),
        (
            '{"rationale":"Reliable creative transfer requires independent source-domain depth '
            'and a separate synthesis judgment surface.","responsibilities":['
            '{"responsibility_id":"MOTORSPORT","title":"Motorsport Deep Model",'
            '"parent_responsibility_id":"ROOT","authority":{"delegate":false,"accept_child_results":false},'
            '"mandate":"Own motorsport mechanisms, evidence, constraints, and transferable principles independently.",'
            '"prohibited_scope":["Gardening primary evidence","Cross-domain synthesis"]},'
            '{"responsibility_id":"GARDENING","title":"Gardening Deep Model",'
            '"parent_responsibility_id":"ROOT","authority":{"delegate":false,"accept_child_results":false},'
            '"mandate":"Own gardening mechanisms, evidence, constraints, and transferable principles independently.",'
            '"prohibited_scope":["Motorsport primary evidence","Cross-domain synthesis"]},'
            '{"responsibility_id":"SYNTHESIS","title":"Cross-Domain Synthesis",'
            '"parent_responsibility_id":"ROOT","authority":{"delegate":false,"accept_child_results":false},'
            '"mandate":"Own accountable comparison, transfer, contradiction handling, and novel synthesis across the independently derived source-domain findings.",'
            '"prohibited_scope":["Replacing source-domain primary evidence"]}'
            ']}'
        ),
        _review("ACCEPTABLE", "The revised candidate preserves independent source depth and accountable synthesis."),
        _decision("ACCEPT", "The independent review result is complete."),
        _decision("ACCEPT", "The revised broad design passes independent review."),
        _review("ACCEPTABLE", "The complete topology remains coherent; all three responsibilities are justified leaves."),
        _decision("ACCEPT", "The final independent review completed its contract."),
        "ROOT reintegrates independent motorsport depth, independent gardening depth, and accountable synthesis. Human organization approval remains reserved.",
        _decision(
            "CONTINUE",
            "The pre-execution topology is coherent but Human approval is reserved.\n"
            "BOOTSTRAP_REQUEST: Review the current organization and either approve it explicitly or provide the changes you require.",
        ),
    ]
    api = BootstrapAPI(persistence, FakeTurnAPI(outputs))
    outcome = api.start(
        run_id="CROSS-DOMAIN",
        mission=(
            "Explore motorsport and gardening deeply and combine their mechanisms to "
            "create genuinely new cross-domain concepts."
        ),
        provider="chatgpt",
    )
    assert outcome.accepted is False
    assert outcome.external_request is not None
    org = current_organization(persistence, persistence.resolve_stream("CROSS-DOMAIN"))
    active = {
        item.responsibility_id
        for item in org.responsibilities
        if item.status == "ACTIVE"
    }
    assert "GENERIC-CREATIVE" not in active
    assert {"MOTORSPORT", "GARDENING", "SYNTHESIS"} <= active


def _anti_fragmentation() -> None:
    persistence = MemoryPersistence()
    outputs = [
        "MISSION MANIFEST\nAuthoritative intent: produce one bounded factual conversion result; no mission-defining ambiguity remains.\nMISSION_MANIFEST_READY",
        _decision("ACCEPT", "No material Human decision delta remains."),
        (
            '{"rationale":"One indivisible evidence/judgment surface is sufficient.",'
            '"responsibilities":[{"responsibility_id":"CONVERSION",'
            '"title":"Conversion Result","parent_responsibility_id":"ROOT",'
            '"authority":{"delegate":false,"accept_child_results":false},'
            '"mandate":"Own the one bounded conversion evidence and result surface.",'
            '"prohibited_scope":[]}]}'
        ),
        _review("ACCEPTABLE", "Additional responsibilities would only duplicate task detail without a new accountability surface."),
        _decision("ACCEPT", "The review completed its contract."),
        _decision("ACCEPT", "The one-leaf design is justified and independently accepted."),
        _review("ACCEPTABLE", "The final one-leaf topology is sufficient and not under-organized."),
        _decision("ACCEPT", "The final review completed its contract."),
        "ROOT reintegrates the intentionally minimal organization. Human approval remains reserved.",
        _decision(
            "CONTINUE",
            "No additional domain boundary is justified; Human approval is still required.\n"
            "BOOTSTRAP_REQUEST: Review the current organization and either approve it explicitly or provide the changes you require.",
        ),
    ]
    api = BootstrapAPI(persistence, FakeTurnAPI(outputs))
    outcome = api.start(
        run_id="ANTI-FRAGMENT",
        mission="Convert a single supplied measurement into another specified unit.",
        provider="chatgpt",
    )
    assert outcome.external_request is not None
    org = current_organization(persistence, persistence.resolve_stream("ANTI-FRAGMENT"))
    execution = [
        item
        for item in org.children("ROOT")
        if item.responsibility_id not in {
            "MISSION-CLARIFICATION",
            "ORGANIZATION-DESIGN",
            "ORGANIZATION-REVIEW",
        }
    ]
    assert [item.responsibility_id for item in execution] == ["CONVERSION"]


def _contract_surfaces() -> None:
    work_text = "\n".join(bootstrap_work().acceptance)
    assert "Human explicitly approves the current organization" in work_text
    assert "independent epistemic depth" in work_text
    assert "recursively derives" in work_text

    clarification = clarification_prompt("mission", (), None, None)
    assert "decision-delta" in clarification
    assert "fixed questionnaire" in clarification
    assert "organization/domain weighting" in clarification
    assert "CLARIFICATION_REQUEST" in clarification

    design = organization_design_prompt(
        mission="mission",
        mission_manifest="manifest",
        prior_candidate=None,
        prior_judgment=None,
        external_inputs=(),
    )
    assert "Cross-domain synthesis requires independent source-domain depth" in design
    assert "do not collapse materially independent epistemic depth" in design

    review = organization_review_prompt(
        mission="mission",
        mission_manifest="manifest",
        candidate_json="{}",
        recursive=True,
    )
    assert "broad authority acting as its own substantive executor" in review
    assert "over-organization and collapse" in review


def self_test() -> None:
    _contract_surfaces()
    _cross_domain()
    _anti_fragmentation()
    print("MANDATE_SEMANTIC_FIDELITY_SELF_TEST_OK")


if __name__ == "__main__":
    self_test()
