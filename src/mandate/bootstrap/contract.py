"""Bootstrap contract over the accountable-work core.

Bootstrap remains ordinary Work. CONTINUE means only that the same Work stays open.
A concrete external request, when required, is carried inside Decision.judgment rather
than in a second persisted status or control field.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from mandate.accountable_work import ActorAuthority, Work
from mandate.persistence import Persistence, StreamRef

BOOTSTRAP_PROTOCOL = "mandate.bootstrap:v1"
BOOTSTRAP_ACTORS = {
    "RUN-AUTHORITY": ActorAuthority(may_issue_work=True),
    "BOOTSTRAP": ActorAuthority(may_issue_work=False),
}
_REQUEST = re.compile(r"(?:^|\n)BOOTSTRAP_REQUEST:\s*(?P<request>.+?)\s*$", re.S)


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
        "protocol",
        "kind",
        "perspective",
        "conversation_id",
        "turn_id",
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


def request_from_judgment(judgment: str) -> str | None:
    match = _REQUEST.search(judgment)
    if match is None:
        return None
    value = match.group("request").strip()
    if not value:
        raise ValueError("BOOTSTRAP_REQUEST_EMPTY")
    return value


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
2. Explore materially plausible meanings of desired end state, scope, non-negotiable commitments, and terminal success boundary only where the wording genuinely permits different missions.
3. For every material unknown, challenge both errors: absence of specification proves neither Human ownership nor system delegation.
4. Test whether unresolved matters can remain unresolved without corrupting this Bootstrap result. If the same Work cannot proceed truthfully, explain exactly why external authority is required now.
5. Test one bounded later Work before creating organization. Decomposition being possible is not evidence that separate accountability is required; simplicity is not evidence that independent accountability may be collapsed.
6. If organization is required, derive each boundary from materially distinct failure, evidence, judgment, or accountability. Do not aim for any count, symmetry, depth, profession list, or amount of detail.
7. Preserve material unresolved downstream questions without solving them; connect them to justified later ownership where possible.
8. Examine cross-ownership interactions without creating duplicate primary accountability. Preserve mission-wide reintegration where it has its own failure/judgment surface.
9. Globally challenge the candidate for missing, misplaced, duplicated, overlapping, collapsed, unsupported, or over-detailed ownership.
10. Re-derive the complete mission after the candidate exists and detect every transition from unresolved to fixed, delegated, excluded, or assumed without authority.
11. Re-evaluate external-input necessity only after the analysis. Do not interrupt merely for importance or uncertainty; do not avoid interruption when the current Work would otherwise choose a materially different Human mission or reserved approval.
12. Do no substantive mission execution, research, design, procurement, planning, legal conclusion, implementation, or operation.
13. If an organization candidate exists, the Work explicitly reserves approval of that current organization to the Human before ACCEPT.

If you believe external input is necessary, state the unresolved information and necessity in ordinary Result prose. The Result itself cannot pause execution; RUN-AUTHORITY decides.

Return one complete standalone Result body. Do not wrap it in Work, Result, Decision, status, phase, or protocol objects.

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

Re-derive enough of the Human mission to challenge the Result. Apply these checks without preferring more or fewer questions, owners, domains, levels, words, or detail:

1. Authority and intent: reject invented Human outcomes, scope, commitments, success definitions, or delegated authority.
2. Plausible meanings: independently test whether the wording permits materially different mission meanings or terminal success states.
3. Transition audit: detect unresolved-to-fixed/delegated/excluded transitions without new authority or mission-preserving justification.
4. External-input false positives: reject interruption when the same Work can continue truthfully unresolved or legitimate later ownership can evaluate the matter without redefining the mission.
5. External-input false negatives: require outside authority when continuation would otherwise choose a materially different Human outcome, binding scope, non-negotiable commitment, terminal success definition, or reserved approval.
6. Direct-work test: test whether one bounded later Work preserves accountability before accepting an organization.
7. Ownership test: justify every boundary and broad unsplit node by distinct failure, evidence, judgment, or accountability; reject both fragmentation and collapse.
8. Unresolved-question preservation: verify material unknowns have not disappeared or been silently solved.
9. Reintegration: challenge the whole candidate against the original mission for missing, duplicated, overlapping, or contradictory responsibility.
10. Execution boundary: reject substantive domain execution.
11. Organization approval: if an organization exists, Human approval of the current candidate is contractually required before ACCEPT.

CONTINUE means only that the same Work remains open. Do not introduce another Work-Core Decision value, phase, pause state, HITL state, or continuation status.

If authoritative outside information or approval is required before truthful continuation, end the judgment with exactly:
BOOTSTRAP_REQUEST: <the smallest concrete request justified by the Work>

If the same Work can continue autonomously, do not emit BOOTSTRAP_REQUEST. If every acceptance statement is satisfied, ACCEPT and do not emit BOOTSTRAP_REQUEST.

If anything required remains missing, CONTINUE the same Work with judgment enabling complete reconsideration rather than a cosmetic patch.

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
  "judgment": "<complete contract-grounded judgment>"
}}
"""
