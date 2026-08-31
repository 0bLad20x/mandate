"""Bootstrap contract over the frozen accountable-work core.

Bootstrap is ordinary Work. Its package-local continuation meaning is carried inside
Decision.judgment so the accountable-work record shape stays unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from mandate.accountable_work import ActorAuthority, Decision, Result, Work
from mandate.persistence import Persistence, StreamRef

BOOTSTRAP_PROTOCOL = "mandate.bootstrap:v1"
BOOTSTRAP_ACTORS = {
    "RUN-AUTHORITY": ActorAuthority(may_issue_work=True),
    "BOOTSTRAP": ActorAuthority(may_issue_work=False),
}

_CONTINUATION = re.compile(
    r"(?:^|\n)BOOTSTRAP_CONTINUATION: "
    r"(?P<mode>AUTONOMOUS|EXTERNAL_INPUT|COMPLETE)\s*$",
    re.M,
)
_REQUEST = re.compile(
    r"(?:^|\n)BOOTSTRAP_REQUEST: (?P<request>.+?)"
    r"(?=\nBOOTSTRAP_CONTINUATION:|\Z)",
    re.S,
)


@dataclass(frozen=True)
class AuthoritativeInput:
    decision_ref: str
    actor: str
    body: str


@dataclass(frozen=True)
class TurnEvidence:
    perspective: str
    conversation_id: str
    turn_id: str


@dataclass(frozen=True)
class Continuation:
    mode: str
    request: str | None = None


def bootstrap_work() -> Work:
    return Work(
        to="BOOTSTRAP",
        objective=(
            "Represent the Human mission faithfully enough to determine whether later "
            "accountable execution should begin as one bounded Work or through an "
            "ownership organization, while preserving material uncertainty that cannot "
            "yet be resolved legitimately. Perform no substantive mission execution."
        ),
        acceptance=(
            "The result preserves authoritative Human intent and distinguishes stated or otherwise authoritative facts from inference, convention, and unresolved uncertainty; no unstated interpretation is silently promoted to a Human commitment or mission fact.",
            "The result examines materially plausible intended outcomes, abstraction and scope boundaries, non-negotiable commitments, and terminal success definitions where the authoritative wording genuinely permits materially different meanings; it does not manufacture ambiguity merely because alternatives are imaginable.",
            "For each material unresolved dimension that affects the mission or later ownership, the result does not infer either Human ownership or system delegation merely from the absence of specification; it justifies whether the matter must be externally resolved now, can remain unresolved while this Work continues, or can later be evaluated without changing the Human mission.",
            "External input is required only when this same Work cannot continue truthfully while the relevant matter remains unresolved, or when an external approval is explicitly required by this Work; importance, cost, difficulty, uncertainty, or downstream impact alone do not establish that requirement.",
            "If the mission can be handed to one bounded later Work without collapsing materially independent accountability, the result proposes one bounded Work and does not create organization merely because decomposition is possible.",
            "If organization is required, ownership boundaries are created, split, combined, or retained only where the mission and materially distinct failure, evidence, judgment, or accountability justify those boundaries; no number of owners, topology size, hierarchy depth, symmetry, or amount of detail is preferred in advance.",
            "Material unresolved downstream questions remain explicit and remain connected to ownership able to evaluate them later when such ownership can be established; a material concern that cannot yet be owned is preserved rather than silently solved, discarded, or assigned arbitrarily.",
            "After deeper analysis or organization, the complete interpretation is re-derived against the original Human mission and all authoritative later input; a matter previously treated as unresolved is not silently converted into a fixed fact, delegated commitment, success boundary, or ownership assumption without new authority or explicit justification.",
            "The organization or bounded Work is challenged for missing, misplaced, duplicated, overlapping, collapsed, or unsupported ownership, and recursion stops wherever another split would change only task detail rather than responsibility, evidence, judgment, failure surface, or accountability.",
            "No substantive work toward executing, researching, designing, implementing, procuring, operating, or otherwise solving the Human mission is performed during Bootstrap.",
            "For an organization case, explicit Human review approves the current organization before Bootstrap can be accepted; Human feedback may continue the same Work for revision.",
            "The final result is a complete standalone pre-execution assessment. Acceptance ends the initial Bootstrap and does not start domain execution.",
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
            "perspective": value.perspective,
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
    if (
        not isinstance(raw, dict)
        or raw.get("protocol") != BOOTSTRAP_PROTOCOL
        or raw.get("kind") != "turn_evidence"
    ):
        return None
    if set(raw) != {
        "protocol", "kind", "perspective", "conversation_id", "turn_id"
    }:
        raise ValueError("BOOTSTRAP_TURN_EVIDENCE_SHAPE_INVALID")
    return TurnEvidence(
        perspective=str(raw["perspective"]),
        conversation_id=str(raw["conversation_id"]),
        turn_id=str(raw["turn_id"]),
    )


def inputs(
    persistence: Persistence,
    stream: StreamRef,
) -> tuple[AuthoritativeInput, ...]:
    out = []
    for entry in persistence.read(stream):
        value = decode_input(entry.body)
        if value is not None:
            out.append(value)
    return tuple(out)


def turn_evidence(
    persistence: Persistence,
    stream: StreamRef,
) -> tuple[TurnEvidence, ...]:
    out = []
    for entry in persistence.read(stream):
        value = decode_turn_evidence(entry.body)
        if value is not None:
            out.append(value)
    return tuple(out)


def continuation_from_judgment(judgment: str) -> Continuation:
    match = _CONTINUATION.search(judgment)
    if match is None:
        raise ValueError("BOOTSTRAP_CONTINUATION_MISSING")
    mode = match.group("mode")
    request_match = _REQUEST.search(judgment)
    request = (
        request_match.group("request").strip()
        if request_match is not None
        else None
    )
    if mode == "EXTERNAL_INPUT" and not request:
        raise ValueError("BOOTSTRAP_REQUEST_REQUIRED")
    if mode != "EXTERNAL_INPUT" and request is not None:
        raise ValueError("BOOTSTRAP_REQUEST_FORBIDDEN")
    return Continuation(mode=mode, request=request)


def authoritative_context(values: Iterable[AuthoritativeInput]) -> str:
    rows = list(values)
    if not rows:
        return "No later external input has been supplied."
    return "\n\n".join(
        f"EXTERNAL INPUT {i + 1} FROM {value.actor}:\n{value.body}"
        for i, value in enumerate(rows)
    )


def bootstrap_prompt(
    mission: str,
    previous_result: str | None,
    previous_judgment: str | None,
    external_inputs: Iterable[AuthoritativeInput],
) -> str:
    previous = previous_result or "No previous candidate."
    judgment = previous_judgment or "No previous accountable judgment."
    return f"""You are BOOTSTRAP. Execute the addressed Work semantically without performing the Human mission itself.

Use substantial reasoning wherever it materially improves the judgment. Do not optimize for brevity, verbosity, number of questions, number of owners, hierarchy depth, symmetry, or agreement with any prior experiment. Do not invent protocol machinery. Your returned text is only the body of a normal Result against the governing Work and has no routing or control authority. There is no required Bootstrap payload schema, epistemic status taxonomy, Human-question field, structural-gap field, or organization runtime model.

Reason from first principles against the exact Work rather than trying to produce a familiar organization. Reconsider the whole mission on every execution; a previous candidate and accountable judgment are evidence/context, not a patch specification.

1. Re-state only the authoritative Human intent. Separate what is stated or later authoritatively supplied from inference, ordinary convention, and what remains unknown. Do not convert plausibility into authority.

2. Explore the intent at the abstraction level actually permitted by the wording. Examine materially plausible meanings of the desired end state, scope, non-negotiable commitments, and terminal success boundary. Pay particular attention to action verbs or outcome phrases whose ordinary language can denote materially different endpoints. Do not create hypothetical ambiguity when different examples would still be ordinary solution choices inside the same mission.

3. For every materially relevant unknown, challenge both opposite errors. Absence of specification does not by itself prove that the Human must decide it, and it does not by itself prove that the system may decide it. Ask whether materially different answers would change the Human mission itself or instead represent alternatives that accountable later work can evaluate while preserving the same mission.

4. Test whether unresolved matters can remain unresolved without corrupting the current Bootstrap result. A matter may remain open if a trustworthy bounded Work or ownership structure can preserve it and later evaluate it without silently choosing a different Human outcome, binding scope, non-negotiable commitment, or success definition. If the same Bootstrap Work cannot proceed truthfully without an authoritative outside answer, explain exactly why.

5. Reconsider whether the mission should proceed as one bounded later Work before creating organization. Decomposition being possible is not evidence that separate accountability is required. Conversely, apparent simplicity is not evidence that materially independent responsibility may be collapsed.

6. If organization is required, derive each ownership boundary from the mission. Create or separate ownership when a material part can fail independently, requires materially different evidence or judgment, or requires distinct accountability. Combine or retain ownership when a proposed separation would only name outputs, professions, mechanisms, implementation details, or arbitrary categories. Apply the same criteria recursively. Do not aim for any particular number of domains, levels, children, or amount of detail.

7. Preserve unresolved downstream questions without solving them. Make clear which ownership can later evaluate each material question when that can be justified. If a material concern has no justified owner yet, keep that deficiency visible rather than assigning it for convenience.

8. Examine interactions across ownership without converting interaction into duplicate accountability. Where one decision affects several judgment surfaces, distinguish the contribution each ownership makes and identify where mission-wide reintegration remains necessary.

9. Perform a global ownership challenge against the original mission. Search for missing responsibility, duplicated responsibility, collapsed independent failure/evidence/judgment surfaces, unsupported fragmentation, misplaced decisions, and broad nodes whose internal responsibilities already demonstrate a justified split. Also challenge deeper splits that merely organize detail.

10. Perform a second independent mission-interpretation check after the organization or bounded Work exists. Compare every material scope, outcome, success, commitment, and delegation assumption in the candidate with the original mission and authoritative later input. In particular, detect whether something earlier described as unknown or unresolved has become fixed, delegated, or excluded without new authority or an explicit mission-preserving justification.

11. Re-evaluate external-input necessity only after the preceding analysis. Do not seek outside input merely because a question is consequential, strategic, difficult, costly, uncertain, or changes downstream topology. Do not avoid outside input merely to keep execution autonomous. External input is justified when the governing Work cannot continue truthfully while the matter remains unresolved, or when the Work explicitly reserves an approval to an external authority.

12. Do no substantive mission execution. Do not research the domain, choose a solution, design the actual product/event/system, determine budgets, select vendors, perform legal conclusions, implement code, or otherwise advance the Human mission beyond the pre-execution interpretation and ownership task.

13. If an organization candidate exists, RUN-AUTHORITY must independently challenge it before acceptance. The Work explicitly requires Human approval of the current organization. That approval is distinct from asking the Human to solve downstream mission choices. If authoritative feedback changes the organization, the changed candidate must again satisfy the Work before acceptance.

If you believe external input is necessary, state the unresolved information or decision and the necessity in ordinary Result prose. That statement cannot pause execution by itself; RUN-AUTHORITY independently determines whether an external request is warranted.

Return one complete standalone Result body in whatever textual structure best communicates the analysis and candidate. A structured organization is appropriate when organization is justified, but no fixed serialization shape is required. Do not wrap the body in a Work, Result, Decision, status, phase, or protocol object.

ORIGINAL HUMAN MISSION
{mission}

GOVERNING BOOTSTRAP WORK
{bootstrap_work()}

AUTHORITATIVE EXTERNAL INPUT RECEIVED DURING THIS SAME WORK
{authoritative_context(external_inputs)}

PREVIOUS COMPLETE RESULT BODY
{previous}

PREVIOUS ACCOUNTABLE JUDGMENT
{judgment}
"""


def judge_prompt(
    mission: str,
    result_body: str,
    result_ref: str,
    previous_judgment: str | None,
    external_inputs: Iterable[AuthoritativeInput],
) -> str:
    return f"""You are RUN-AUTHORITY, issuer of the Bootstrap Work. Independently judge the CURRENT Result against the exact governing acceptance statements. Result production is not acceptance. The only canonical Decision values are ACCEPT and CONTINUE.

Do not judge whether the Result is persuasive-looking or resembles an earlier experiment. Re-derive the Human mission and the required pre-execution structure independently from the authoritative context far enough to challenge the Result.

Apply these checks without preferring more or fewer questions, owners, domains, levels, words, or detail:

1. Authority and intent: identify what the Human actually stated or later authoritatively supplied. Challenge every material candidate claim about intended outcome, binding scope, non-negotiable commitment, success definition, or delegated authority that does not follow from that context.

2. Plausible meanings: independently test whether the original wording permits materially different mission meanings or terminal success states. Do not manufacture ambiguity from ordinary solution alternatives, but do not erase ambiguity merely because a mission-neutral abstraction can be written.

3. Transition audit: compare the CURRENT Result with the authoritative context and with material uncertainties preserved in prior reasoning. Detect any transition from unknown/unresolved to fixed fact, delegated choice, excluded scope, or assumed success boundary that lacks new authoritative input or a mission-preserving justification. A coherent organization does not excuse such a transition.

4. External-input false positives: reject a proposed interruption when the matter can remain unresolved while the same Work continues truthfully, or when later accountable ownership can evaluate it without changing the Human mission. Importance, cost, difficulty, uncertainty, strategic impact, or topology impact alone are insufficient.

5. External-input false negatives: do not permit the system to choose a materially different Human outcome, binding scope, non-negotiable commitment, terminal success definition, or explicitly reserved approval merely to avoid interruption. If the Work cannot proceed without making such a choice, authoritative outside input is required.

6. Direct-work test: independently test whether one bounded later Work would preserve accountability. Do not create organization merely because decomposition is possible; do not collapse materially independent failure/evidence/judgment/accountability into one Work merely because the mission is short or underspecified.

7. Ownership test: for every proposed boundary and every broad unsplit node, ask what distinct failure, evidence, judgment, or accountability justifies the boundary or its absence. Search both for unsupported fragmentation and for collapsed responsibility. Topology size and depth are consequences, never success criteria.

8. Unresolved-question preservation: verify that material unresolved matters have not disappeared or been silently solved. Where later ownership is claimed, test whether that ownership can legitimately evaluate the matter without redefining the Human mission. Where no justified owner exists, that unresolved gap must remain visible.

9. Reintegration: test the complete bounded Work or organization against the original mission for missing, misplaced, duplicated, overlapping, or internally contradictory responsibility, including deeper findings that should change a peer or parent boundary.

10. Execution boundary: reject substantive domain execution, solution selection, research, implementation, planning, procurement, legal conclusions, or other progress on the Human mission itself.

11. Organization approval: if an organization exists, the governing Work explicitly requires Human approval of the current candidate before ACCEPT. This requirement is contractual for this Bootstrap contract; do not confuse it with evidence that every organization universally requires Human approval.

CONTINUE means only that the same Work remains open. Do not introduce another Work-Core Decision value or status. The semantic continuation condition must be preserved inside this canonical Decision.judgment.

The judgment MUST end with exactly one package-local interpretation block:

If the same Work can continue from current authoritative context:
BOOTSTRAP_CONTINUATION: AUTONOMOUS

If authoritative outside information or approval is required before truthful continuation:
BOOTSTRAP_REQUEST: <the smallest concrete request justified by the governing Work>
BOOTSTRAP_CONTINUATION: EXTERNAL_INPUT

If every acceptance statement is satisfied:
BOOTSTRAP_CONTINUATION: COMPLETE

These lines are inside Decision.judgment. They are not a second Decision field, persisted status, HITL record, phase, capability, or new Work-Core primitive.

If anything required remains missing, CONTINUE the same Work and give judgment that enables a complete reconsideration rather than a cosmetic patch. Do not invent another workflow/status taxonomy and do not perform the Human mission.

ORIGINAL HUMAN MISSION
{mission}

GOVERNING WORK
{bootstrap_work()}

AUTHORITATIVE EXTERNAL INPUT RECEIVED DURING THIS SAME WORK
{authoritative_context(external_inputs)}

PREVIOUS ACCOUNTABLE JUDGMENT
{previous_judgment or "No previous accountable judgment."}

CURRENT RESULT REF
{result_ref}

CURRENT RESULT BODY
{result_body}

Return exactly one JSON object and nothing else:
{{
  "decision": "ACCEPT or CONTINUE",
  "judgment": "<complete contract-grounded judgment including the required interpretation block>"
}}
"""


def result_value(work_ref: str, body: str) -> Result:
    return Result(work_ref=work_ref, body=body)


def decision_value(result_ref: str, decision: str, judgment: str) -> Decision:
    return Decision(
        result_ref=result_ref,
        decision=decision,
        judgment=judgment,
    )
