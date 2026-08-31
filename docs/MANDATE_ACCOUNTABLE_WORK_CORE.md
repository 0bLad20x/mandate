# Mandate Accountable Work Core

Status: **PROVISIONAL_CONTRACT**

Umbrella: #139  
Contract discovery: #142  
Freeze decision: #142 decision-gate comment `5443949152`

This document freezes the smallest accountable-work semantics currently supported by the fresh live V2-V4, minimality, and measurement-corrected reference-minimality evidence.

It is intentionally narrower than the historical Mandate contract family. It is not a production API, persisted schema, GitHub format, Modelrail execution format, organization/bootstrap model, SIGNAL contract, or run-control contract.

## Objective

A coordination implementation must be able to represent and reconstruct:

- who issued bounded work to whom;
- what objective and acceptance statements govern that work;
- what one closed execution returned for that work;
- which accountable actor may judge that returned result;
- whether the same work remains open or has been accepted;
- how accepted child work may inform an assignee's distinct result upward without self-acceptance.

## Frozen semantic facts

### Canonical record

Every canonical semantic fact has:

```text
reference
actor provenance
semantic value
```

`reference` means a stable unique address within the canonical record stream. Its physical representation is not frozen. `R0001` was experiment notation only.

`actor provenance` identifies the actor that asserted/issued the canonical fact. It is semantic provenance, not provider conversation identity or GitHub authorship.

### Work

```text
Work
  to
  objective
  acceptance[]
```

Meaning:

- the canonical record actor is the work issuer;
- `to` is the assignee;
- `objective` states the requested outcome;
- `acceptance` contains the statements against which returned Results are judged.

A valid Work creates a derived obligation relation from issuer to assignee. No separate obligation record or OPEN/CLOSED field is required by the current evidence.

### Result

```text
Result
  work_ref
  body
```

Meaning:

- `work_ref` identifies the exact Work being answered;
- `body` is the returned content of one closed execution against that Work;
- producing a Result does not accept, close, or otherwise dispose the Work.

The canonical record actor must be the Work assignee.

### Decision

```text
Decision
  result_ref
  decision
  judgment
```

where:

```text
decision = ACCEPT | CONTINUE
```

Meaning:

- `result_ref` identifies the exact Result being judged;
- the governing Work is derived through `Decision.result_ref -> Result.work_ref`;
- the canonical record actor must be the issuer of that Work;
- an actor may not judge its own Result;
- `judgment` is non-empty contract-grounded reasoning against the governing Work acceptance statements.

`CONTINUE` leaves the same Work open. It does not create a continuation contract or a replacement Work.

`ACCEPT` closes only the governing Work. Accepting child Work does not discharge a different parent Work owed by the issuer.

## Authority context

Fresh live evidence supports one minimal authority distinction for this core:

```text
actor may issue Work
```

The experiments represented this as `can_delegate`. The capability is provisional contract semantics; the final storage/API representation of actor authority remains OPEN.

No separate `accept_child_results` capability is required for the tested core: the Work issuer is the accountable Decision actor for Results returned against that Work.

## Derived projection

From the canonical records an implementation must be able to derive at least:

```text
work issuer
work assignee
Result -> Work
Decision -> Result -> Work
open Work
closed Work
same-Work continuation after CONTINUE
```

For the current core:

```text
open Work = issued Work without a canonical ACCEPT Decision for one of its Results
closed Work = issued Work with a canonical ACCEPT Decision for one of its Results
```

These are projections, not separately persisted coordination facts.

## Earned invariants

The provisional core must preserve:

1. **Result is return-only** — Result production does not imply acceptance.
2. **No self-acceptance** — the Result actor cannot issue its accountable Decision.
3. **Issuer accountability** — only the Work issuer may issue the accountable Decision for a Result against that Work.
4. **Assignee return** — only the Work assignee may return a Result against that Work.
5. **Delegation authority** — an actor without the work-issuing capability cannot create canonical Work.
6. **Same-work continuation** — CONTINUE leaves the original Work identity and acceptance statements in force.
7. **Recursive accountability** — accepting child Work closes only that child Work; the issuer's own parent Work remains independent.
8. **Upward result separation** — an actor that owes parent Work returns its own Result upward; its parent separately judges that Result.
9. **Stable traceability** — Results and Decisions must resolve unambiguously through stable canonical references.

## Explicitly not frozen

The following are not part of this provisional accountable-work core:

- type-specific `work_id`, `result_id`, or `decision_id` namespaces;
- explicit `from_actor_id` inside Work when canonical actor provenance supplies issuer identity;
- criterion IDs such as C1/P1;
- separate Obligation records;
- persisted OPEN/CLOSED/phase/status/continuation state;
- Result outcome enums such as PRODUCED/INCOMPLETE/FAILED;
- `accept_child_results` authority flags;
- Responsibility parent links as the routing mechanism for concrete Work accountability;
- provider or Modelrail conversation identity;
- GitHub issue/comment fields;
- reporting/package semantics;
- retry/provider-fallback semantics;
- result-after-closure policy;
- bootstrap/organization semantics;
- SIGNAL semantics;
- run-control/termination semantics.

These exclusions do not assert that every item is universally useless. They assert only that current live evidence does not require them in this core.

## State and execution boundaries

The semantic contract does not own persistence or LLM mechanics.

```text
coordination semantics
  -> canonical records and their meaning

state implementation
  -> durable storage/readback of canonical records

Modelrail
  -> Turn and Conversation execution mechanics
```

GitHub and JSONL both carried the same reduced record stream in the live minimality probes; neither backend defines this contract.

## Revisit conditions

Reopen this freeze if evidence shows that:

- the frozen facts cannot represent or validate a semantically meaningful real task;
- an independent interpreter needs experiment-only assumptions not stated here;
- a required accountability relation is ambiguous without additional semantics;
- actor authority cannot be represented truthfully with the currently earned distinction;
- state or execution substitution forces backend/provider mechanics into the semantic contract;
- a later SIGNAL, run-control, bootstrap, or organization experiment proves a necessary interaction with this core.

Until one of these conditions occurs, additions are hypotheses rather than contract extensions.
