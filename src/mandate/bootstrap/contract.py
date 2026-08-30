"""Pre-execution Bootstrap contract preserving accepted Mandate WP1 semantics.

Bootstrap is accountable pre-execution coordination, not a chat-style prose
assessment: clarify Human-owned mission deltas when they materially affect the
organization, persist and challenge an explicit responsibility organization,
recursively organize broad delegated domains, reintegrate the whole topology, and
obtain Human approval of the current organization before acceptance.

The accountable-work core remains Work / Result / Decision(ACCEPT|CONTINUE).
Bootstrap-specific prompts and evidence live here rather than enlarging that core.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from mandate.accountable_work import Work
from mandate.organization import Authority, Organization, Responsibility
from mandate.persistence import Persistence, StreamRef


BOOTSTRAP_PROTOCOL = "mandate.bootstrap:v1"
RUN_AUTHORITY_ID = "RUN-AUTHORITY"
ROOT_ID = "ROOT"
CLARIFICATION_ID = "MISSION-CLARIFICATION"
ORGANIZATION_DESIGN_ID = "ORGANIZATION-DESIGN"
ORGANIZATION_REVIEW_ID = "ORGANIZATION-REVIEW"
RESERVED_RESPONSIBILITY_IDS = {
    RUN_AUTHORITY_ID,
    ROOT_ID,
    CLARIFICATION_ID,
    ORGANIZATION_DESIGN_ID,
    ORGANIZATION_REVIEW_ID,
}

_REQUEST = re.compile(r"(?:^|\n)BOOTSTRAP_REQUEST:\s*(?P<request>.+?)\s*$", re.S)
_CLARIFICATION_REQUEST = re.compile(
    r"(?:^|\n)CLARIFICATION_REQUEST:\s*(?P<request>.+?)\s*$", re.S
)
_ESCALATION = re.compile(
    r"(?:^|\n)EXTERNAL_AUTHORITY_CANDIDATE:\s*(?P<request>.+?)\s*$", re.S
)


@dataclass(frozen=True)
class AuthoritativeInput:
    decision_ref: str
    actor: str
    body: str


@dataclass(frozen=True)
class TurnEvidence:
    responsibility_id: str
    conversation_id: str
    turn_id: str

    @property
    def perspective(self) -> str:
        """Compatibility alias for package-foundation evidence."""
        return self.responsibility_id


def initial_organization(run_id: str) -> Organization:
    """Persist the authority spine before delegated Bootstrap work."""
    return Organization(
        run_id=run_id,
        responsibilities=(
            Responsibility(
                responsibility_id=RUN_AUTHORITY_ID,
                run_id=run_id,
                title="Run Authority",
                kind="RUN_AUTHORITY",
                parent_responsibility_id=None,
                authority=Authority(True, True, True),
                mandate=(
                    "Own run control, Human-authority escalation, and final independent "
                    "acceptance of the complete pre-execution package. Do not perform "
                    "mission clarification, organization design, or domain execution."
                ),
                prohibited_scope=(
                    "Substantive mission execution",
                    "Authoring the domain organization in place of ROOT",
                ),
            ),
            Responsibility(
                responsibility_id=ROOT_ID,
                run_id=run_id,
                title="Accountable Root",
                kind="RESPONSIBILITY",
                parent_responsibility_id=RUN_AUTHORITY_ID,
                authority=Authority(True, True, False),
                mandate=(
                    "Own the complete Human mission below Run Authority: obtain legitimate "
                    "mission clarification, derive and challenge the initial organization, "
                    "ensure justified recursive organization, and reintegrate the whole "
                    "pre-execution package without performing substantive mission work."
                ),
                prohibited_scope=(
                    "Run control",
                    "Inventing Human commitments",
                    "Substantive mission execution",
                ),
            ),
        ),
    )


def coordination_responsibilities(run_id: str) -> tuple[Responsibility, ...]:
    """Fresh run responsibilities, not permanent privileged role classes."""
    return (
        Responsibility(
            responsibility_id=CLARIFICATION_ID,
            run_id=run_id,
            title="Mission Clarification",
            kind="RESPONSIBILITY",
            parent_responsibility_id=ROOT_ID,
            authority=Authority(False, False, False),
            mandate=(
                "Own only decision-delta clarification of Human intent before organization: "
                "identify unresolved Human-owned choices whose materially different answers "
                "could change mission meaning, scope, product direction, organization/domain "
                "weighting, authority boundaries, or acceptance; preserve lower-impact "
                "unknowns without manufacturing questions."
            ),
            prohibited_scope=(
                "Organization design",
                "Substantive mission execution",
                "Answering Human-owned questions",
            ),
        ),
        Responsibility(
            responsibility_id=ORGANIZATION_DESIGN_ID,
            run_id=run_id,
            title="Organization Design",
            kind="RESPONSIBILITY",
            parent_responsibility_id=ROOT_ID,
            authority=Authority(False, False, False),
            mandate=(
                "Derive the mission-specific initial responsibility organization from the "
                "accepted mission context. Boundaries follow material obligation, uncertainty, "
                "risk, deliverable, evidence, judgment, failure, or accountability surfaces, "
                "not profession lists or output decomposition."
            ),
            prohibited_scope=(
                "Independent acceptance of its own organization",
                "Substantive mission execution",
                "Inventing Human commitments",
            ),
        ),
        Responsibility(
            responsibility_id=ORGANIZATION_REVIEW_ID,
            run_id=run_id,
            title="Independent Organization Review",
            kind="RESPONSIBILITY",
            parent_responsibility_id=ROOT_ID,
            authority=Authority(False, False, False),
            mandate=(
                "Independently challenge the proposed/current organization for missing, "
                "collapsed, overlapping, duplicated, unsupported, authority-expanding, "
                "execution-collapsing, or over-fragmented responsibility boundaries and "
                "require bounded revision when material defects exist."
            ),
            prohibited_scope=(
                "Authoring the candidate it reviews",
                "Substantive mission execution",
                "Run control",
            ),
        ),
    )


def bootstrap_work() -> Work:
    return Work(
        to=ROOT_ID,
        objective=(
            "Produce a complete, independently challenged, Human-approved pre-execution "
            "responsibility organization for the Human mission. Clarify only material "
            "Human-owned decision deltas, preserve legitimate uncertainty, recursively "
            "organize broad delegated domains before substantive execution, and perform no "
            "substantive mission work."
        ),
        acceptance=(
            "Authoritative Human intent is separated from inference, convention, and unresolved uncertainty; no plausible interpretation is silently promoted to a Human commitment.",
            "Before organization is finalized, materially different plausible Human answers that could change mission meaning, scope, product direction, organization/domain weighting, authority boundaries, non-negotiable commitments, terminal success, or acceptance are obtained through a bounded Human clarification request; no fixed questionnaire or fixed clarification-round count is used.",
            "Exactly one accountable ROOT owns the whole mission below RUN-AUTHORITY; RUN-AUTHORITY owns run control and final independent acceptance rather than substantive organization or domain work.",
            "An explicit initial organization is persisted before ordinary substantive domain execution and every responsibility boundary is justified by inherited mission relevance plus a materially distinct obligation, uncertainty, risk, deliverable, evidence, judgment, failure, or accountability surface.",
            "Organization is not fragmented merely because task decomposition is possible, but independent epistemic depth is not collapsed into one generic Work when distinct evidence or judgment surfaces are necessary for reliable whole-mission synthesis.",
            "The organization is challenged by a responsibility independent of the candidate author and material defects cause revision rather than cosmetic acceptance.",
            "Every broad active responsibility that retains delegation authority recursively derives the child execution organization actually required by its delegated domain before substantive work begins; non-leaf authority does not substitute for its own substantive execution organization.",
            "The complete topology is reintegrated against the original Human mission and all authoritative later input; missing, duplicated, contradictory, overlapping, unsupported, or silently transformed ownership is rejected.",
            "No fixed domain count, branch count, role catalogue, profession list, symmetry, hierarchy depth, or amount of detail is preferred in advance.",
            "No substantive researching, designing of mission solutions, implementing, procuring, operating, or otherwise executing the Human mission occurs during this pre-execution Bootstrap.",
            "The Human explicitly approves the current organization before this Bootstrap Work can be accepted; Human feedback continues the same Work for reconsideration/revision.",
            "Acceptance ends pre-execution Bootstrap only and does not itself release substantive domain execution.",
        ),
    )


def encode_input(value: AuthoritativeInput) -> str:
    return json.dumps(
        {
            "protocol": BOOTSTRAP_PROTOCOL,
            "kind": "authoritative_input",
            "decision_ref": value.decision_ref,
            "actor": value.actor,
            "body": value.body,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def decode_input(body: str) -> AuthoritativeInput | None:
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(raw, dict)
        or raw.get("protocol") != BOOTSTRAP_PROTOCOL
        or raw.get("kind") != "authoritative_input"
    ):
        return None
    if set(raw) != {"protocol", "kind", "decision_ref", "actor", "body"}:
        raise ValueError("BOOTSTRAP_INPUT_SHAPE_INVALID")
    return AuthoritativeInput(
        decision_ref=str(raw["decision_ref"]),
        actor=str(raw["actor"]),
        body=str(raw["body"]),
    )


def encode_turn_evidence(value: TurnEvidence) -> str:
    return json.dumps(
        {
            "protocol": BOOTSTRAP_PROTOCOL,
            "kind": "turn_evidence",
            "responsibility_id": value.responsibility_id,
            "conversation_id": value.conversation_id,
            "turn_id": value.turn_id,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def decode_turn_evidence(body: str) -> TurnEvidence | None:
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict) or raw.get("protocol") != BOOTSTRAP_PROTOCOL:
        return None
    if raw.get("kind") != "turn_evidence":
        return None
    if set(raw) == {"protocol", "kind", "perspective", "conversation_id", "turn_id"}:
        responsibility_id = str(raw["perspective"])
    elif set(raw) == {
        "protocol", "kind", "responsibility_id", "conversation_id", "turn_id"
    }:
        responsibility_id = str(raw["responsibility_id"])
    else:
        raise ValueError("BOOTSTRAP_TURN_EVIDENCE_SHAPE_INVALID")
    return TurnEvidence(
        responsibility_id=responsibility_id,
        conversation_id=str(raw["conversation_id"]),
        turn_id=str(raw["turn_id"]),
    )


def inputs(persistence: Persistence, stream: StreamRef) -> tuple[AuthoritativeInput, ...]:
    out: list[AuthoritativeInput] = []
    for entry in persistence.read(stream):
        value = decode_input(entry.body)
        if value is not None:
            out.append(value)
    return tuple(out)


def turn_evidence(persistence: Persistence, stream: StreamRef) -> tuple[TurnEvidence, ...]:
    out: list[TurnEvidence] = []
    for entry in persistence.read(stream):
        value = decode_turn_evidence(entry.body)
        if value is not None:
            out.append(value)
    return tuple(out)


def request_from_judgment(judgment: str) -> str | None:
    match = _REQUEST.search(judgment)
    if match is None:
        return None
    value = match.group("request").strip()
    if not value:
        raise ValueError("BOOTSTRAP_REQUEST_EMPTY")
    return value


def clarification_request(body: str) -> str | None:
    match = _CLARIFICATION_REQUEST.search(body)
    return match.group("request").strip() if match is not None else None


def escalation_candidate(judgment: str) -> str | None:
    match = _ESCALATION.search(judgment)
    return match.group("request").strip() if match is not None else None


def authoritative_context(values: Iterable[AuthoritativeInput]) -> str:
    rows = list(values)
    if not rows:
        return "No later authoritative Human input has been supplied."
    return "\n\n".join(
        f"AUTHORITATIVE INPUT {i + 1} FROM {value.actor} (correlated to {value.decision_ref}):\n{value.body}"
        for i, value in enumerate(rows)
    )


def clarification_prompt(
    mission: str,
    external_inputs: Iterable[AuthoritativeInput],
    previous_result: str | None,
    previous_judgment: str | None,
) -> str:
    return f"""You are the run-specific MISSION-CLARIFICATION responsibility. You do not solve the Human mission and you do not design the organization.

Re-derive authoritative Human intent from the original mission plus authoritative later input. Separate authority from inference and convention.

Use the accepted decision-delta rule: ask the Human only for unresolved choices where materially different plausible answers could change mission meaning, binding scope, product direction, organization/domain weighting, authority boundaries, non-negotiable commitments, terminal success definition, or acceptance. Do not maximize question count, use a fixed questionnaire, ask ordinary implementation preferences, or ask merely because something is important or uncertain.

For each candidate ambiguity, test both errors: asking unnecessarily when organization can remain mission-faithful across plausible answers; and failing to ask when choosing one interpretation would materially alter the mission or organization that must own it.

If authoritative Human input is still required before organization can be legitimately finalized, explain the decision delta and end exactly:
CLARIFICATION_REQUEST: <the smallest bounded Human question or tightly related question set>

If no such Human-owned decision delta remains, produce a compact Mission Manifest in prose containing authoritative intent, binding scope/commitments actually supplied, materially deferred unknowns, and the boundary between delegated solution choices and choices that later require renewed Human authority. End exactly:
MISSION_MANIFEST_READY

Do not create domains, responsibilities, plans, research findings, product ideas, solutions, or substantive mission output.

ORIGINAL HUMAN MISSION
{mission}

AUTHORITATIVE LATER INPUT
{authoritative_context(external_inputs)}

PREVIOUS CLARIFICATION RESULT
{previous_result or "None."}

PREVIOUS ROOT JUDGMENT
{previous_judgment or "None."}
"""


def child_judge_prompt(
    *, parent_id: str, child_id: str, work: Work, result_body: str,
    context: str, clarification: bool = False,
) -> str:
    rule = (
        "If the child correctly identifies a Human-owned decision delta, CONTINUE the same child Work and end judgment with `EXTERNAL_AUTHORITY_CANDIDATE: <smallest justified request>`. The parent cannot answer it. If a Mission Manifest is legitimately complete, ACCEPT."
        if clarification
        else "ACCEPT only when the assigned organization-only Work is complete and contract-faithful. CONTINUE for substantive defects with judgment enabling whole-work reconsideration."
    )
    return f"""You are responsibility {parent_id}, accountable issuer of Work assigned to {child_id}. Independently judge the CURRENT child Result. Result production is not acceptance. Return only ACCEPT or CONTINUE.

Check authority, inherited mission relevance, exact Work acceptance, unresolved uncertainty, prohibited scope, and whether substantive mission execution occurred. Reject invented Human commitments and authority expansion. {rule}

WORK
{work}

CONTEXT
{context}

CURRENT CHILD RESULT
{result_body}

Return exactly one JSON object:
{{"decision":"ACCEPT or CONTINUE","judgment":"<complete judgment>"}}
"""


def organization_design_prompt(
    *, mission: str, mission_manifest: str, prior_candidate: str | None,
    prior_judgment: str | None, external_inputs: Iterable[AuthoritativeInput],
) -> str:
    return f"""You are the run-specific ORGANIZATION-DESIGN responsibility. Design only the mission-specific accountability organization below ROOT. Do not perform the Human mission.

A responsibility exists only when it materially owns/can change an inherited obligation, uncertainty, risk, deliverable, evidence surface, judgment surface, failure surface, or accountability surface. Do not decompose by profession, report heading, implementation step, or because multiple tasks are imaginable. Conversely, do not collapse materially independent epistemic depth into one generic responsibility merely because one actor could discuss all topics in one conversation.

Cross-domain synthesis requires independent source-domain depth when reliable synthesis depends on distinct evidence/judgment surfaces, plus accountable integration where the combination has its own failure/judgment surface.

Authority/execution separation: a broad responsibility that must organize multiple substantive execution surfaces is non-leaf (`delegate=true`, `accept_child_results=true`) and will recursively derive children later. A responsibility that genuinely owns one indivisible execution/evidence surface may be a leaf (`delegate=false`). Do not create RUN-AUTHORITY, ROOT, clarification, design, or review responsibilities.

No fixed count, symmetry, hierarchy depth, role catalogue, or preferred topology. Preserve unresolved Human choices rather than turning them into domain assumptions.

Return exactly one JSON object and nothing else:
{{"rationale":"<whole-topology rationale>","responsibilities":[{{"responsibility_id":"<stable uppercase run-local id>","title":"<human readable>","parent_responsibility_id":"ROOT or another responsibility_id in this candidate","authority":{{"delegate":true,"accept_child_results":true}},"mandate":"<material ownership boundary>","prohibited_scope":["<material adjacent authority>"]}}]}}

For a leaf set both authority booleans false. Do not include run_control or conversation_id.

ORIGINAL HUMAN MISSION
{mission}

ACCEPTED MISSION MANIFEST
{mission_manifest}

AUTHORITATIVE LATER INPUT
{authoritative_context(external_inputs)}

PRIOR CANDIDATE
{prior_candidate or "None."}

PRIOR ACCOUNTABLE JUDGMENT / REVIEW FINDINGS
{prior_judgment or "None."}
"""


def organization_review_prompt(
    *, mission: str, mission_manifest: str, candidate_json: str, recursive: bool,
) -> str:
    scope = "complete recursively expanded topology" if recursive else "initial broad organization"
    return f"""You are the run-specific independent ORGANIZATION-REVIEW responsibility. You did not author this candidate. Review the {scope}.

Find material defects, not stylistic preferences. Test both over-organization and collapse: missing independent evidence/judgment/failure surfaces; duplicate or overlapping primary accountability; unsupported relevance; authority expansion; a broad authority acting as its own substantive executor; silent promotion of unresolved Human choices; missing cross-domain integration; topology justified only by symmetry/convention. A nonstandard one-child authority or uneven depth is not a defect by itself.

Return exactly one JSON object and nothing else:
{{"disposition":"ACCEPTABLE or REVISION_REQUIRED","judgment":"<whole-candidate judgment>","findings":[{{"evidence":"<candidate fact>","boundary":"<governing principle>","consequence":"<material consequence>","revision":"<bounded required correction>"}}]}}

Use an empty findings list only when ACCEPTABLE.

ORIGINAL HUMAN MISSION
{mission}

MISSION MANIFEST
{mission_manifest}

CANDIDATE ORGANIZATION
{candidate_json}
"""


def recursive_organization_prompt(
    *, mission: str, mission_manifest: str, responsibility: Responsibility,
    current_organization_json: str, previous_result: str | None,
    previous_judgment: str | None,
) -> str:
    return f"""You are responsibility {responsibility.responsibility_id}. Derive the child execution responsibility organization actually required by your delegated mandate before substantive domain work begins.

You are a non-leaf authority. Do not perform substantive research/design/implementation. Decompose only where child ownership has materially distinct obligation, uncertainty, risk, deliverable, evidence, judgment, failure, or accountability surfaces. Preserve parent accountability and do not expand authority. Do not force symmetry or a preferred number of children.

Return exactly one JSON object and nothing else:
{{"rationale":"<why these boundaries are required and sufficient>","children":[{{"responsibility_id":"<stable uppercase run-local id>","title":"<human readable>","authority":{{"delegate":true_or_false,"accept_child_results":true_or_false}},"mandate":"<child material ownership boundary>","prohibited_scope":["<material adjacent authority>"]}}]}}

A child with delegate=true is a justified broad non-leaf authority and will recursively organize later. Leaf children use both booleans false. Return at least one child. If the parent mandate is actually indivisible and should have been a leaf, explain that instead of inventing children so the accountable parent can revise the organization.

ORIGINAL HUMAN MISSION
{mission}

MISSION MANIFEST
{mission_manifest}

YOUR RESPONSIBILITY
{responsibility}

CURRENT WHOLE ORGANIZATION
{current_organization_json}

PREVIOUS RESULT
{previous_result or "None."}

PREVIOUS PARENT JUDGMENT
{previous_judgment or "None."}
"""


def root_progress_prompt(
    *, mission: str, mission_manifest: str | None, organization_json: str | None,
    unresolved_external_request: str | None, review_judgment: str | None,
    external_inputs: Iterable[AuthoritativeInput],
) -> str:
    return f"""You are ROOT, accountable for the complete Human mission below RUN-AUTHORITY. Produce a Result for your still-open pre-execution Bootstrap Work. Do not execute the Human mission.

Reintegrate the complete current state against the original mission and authoritative later input. You have no run-control authority and cannot answer Human-owned choices.

If clarification has produced a legitimate unresolved Human-owned decision delta that prevents organization finalization, return a bounded escalation candidate and end exactly:
EXTERNAL_AUTHORITY_CANDIDATE: <smallest justified Human request>

If a complete independently challenged, recursively organized topology exists, explain why it preserves accountability and uncertainty. The current organization still requires explicit Human approval before your Work can be accepted; state that clearly. Do not claim Bootstrap acceptance releases substantive execution.

ORIGINAL HUMAN MISSION
{mission}

MISSION MANIFEST
{mission_manifest or "Not yet accepted."}

CURRENT ORGANIZATION
{organization_json or "Not yet finalized."}

UNRESOLVED EXTERNAL REQUEST
{unresolved_external_request or "None."}

LATEST INDEPENDENT REVIEW
{review_judgment or "None."}

AUTHORITATIVE LATER INPUT
{authoritative_context(external_inputs)}
"""


def run_authority_prompt(
    *, mission: str, work: Work, root_result: str, root_result_ref: str,
    current_organization_json: str | None,
    external_inputs: Iterable[AuthoritativeInput], previous_judgment: str | None,
) -> str:
    return f"""You are RUN-AUTHORITY, issuer of ROOT's pre-execution Bootstrap Work. Independently judge the CURRENT ROOT Result. Result production is not acceptance. The only Decision values are ACCEPT and CONTINUE.

Reject invented Human outcomes/commitments, missing decision-delta clarification, chat-like collapse of independent epistemic surfaces, artificial fragmentation, missing independent organization challenge, broad non-leaf authority substituting for execution children, missing reintegration, substantive domain execution, or authority expansion.

If ROOT escalates a legitimate Human-owned decision delta required before organization finalization, CONTINUE and end exactly:
BOOTSTRAP_REQUEST: <smallest justified clarification request>

If a complete organization exists but authoritative Human input does not explicitly approve that current organization, CONTINUE and end exactly:
BOOTSTRAP_REQUEST: Review the current organization and either approve it explicitly or provide the changes you require.

Human feedback continues the same ROOT Work. Human approval must refer to the current organization, not a superseded candidate.

ACCEPT only when every acceptance statement is satisfied and authoritative Human input explicitly approves the current organization. ACCEPT ends Bootstrap only; it does not release substantive execution.

WORK
{work}

ORIGINAL HUMAN MISSION
{mission}

AUTHORITATIVE LATER INPUT
{authoritative_context(external_inputs)}

CURRENT ORGANIZATION
{current_organization_json or "Not yet finalized."}

PREVIOUS RUN-AUTHORITY JUDGMENT
{previous_judgment or "None."}

CURRENT ROOT RESULT REF
{root_result_ref}

CURRENT ROOT RESULT
{root_result}

Return exactly one JSON object and nothing else:
{{"decision":"ACCEPT or CONTINUE","judgment":"<complete contract-grounded judgment>"}}
"""
