# CREATIVE-STUDIO-LIVE-001 runtime failure 001

## Observation 1 — missing transport message id

The first `CREATIVE-STUDIO-LIVE-001` execution reached a completed downstream research/synthesis Turn and then the local studio broker exited with:

`applications.mandate_smoke_harness.BrokerError: HANDOFF_MESSAGE_ID_REQUIRED`

The failure occurred after Modelrail had extracted the completed Assistant response. Canonical semantic work had already been persisted in GitHub, including the research results and synthesis. The failure was therefore at the transport-envelope boundary, not in the creative responsibility graph or the persisted research work.

### Root cause

The shared broker validator requires every handoff to contain a non-empty `message_id`, but the studio prompts specified only the outer terminal shape (`{"run_id":"...","handoffs":[...]}`) and did not spell out the required per-handoff transport schema. A completed Assistant Turn omitted `message_id`; the validator correctly rejected it, but the long-running studio wrapper had no transport-only normalization for this recoverable omission.

## Observation 2 — redundant sender mismatch after resume

After syncing the first correction, the persisted run was resumed without resubmitting the completed `EVIDENCE-SYNTHESIS` Turn. Modelrail successfully re-extracted the already completed response for persisted TurnRef `43b102`, after which validation stopped on:

`applications.mandate_smoke_harness.BrokerError: HANDOFF_SENDER_MISMATCH`

The local checkpoint still identified the pending source responsibility as `EVIDENCE-SYNTHESIS`, issue `#24`, conversation `mandate-CREATIVE-STUDIO-LIVE-001-EVIDENCE-SYNTHESIS`, TurnRef `43b102`. Therefore Assistant-generated `from_responsibility_id` was redundant with stronger broker-owned source identity. Trusting that redundant field as if it were authority-bearing transport truth created a second avoidable process exit.

## Observation 3 — missing semantic DISPATCH target after second resume

After syncing sender binding, the same persisted TurnRef `43b102` was resumed again. Modelrail again extracted the completed Assistant response successfully. Identity normalization passed, but strict validation then stopped on:

`applications.mandate_smoke_harness.BrokerError: DISPATCH_TARGET_REQUIRED`

This is materially different from the first two defects. `to_responsibility_id` is semantic routing, not redundant transport identity. The broker must not guess it merely because the current example appears to be a child RESULT returning to ROOT. The repeated sequence therefore falsified the field-by-field repair strategy: a long-running broker cannot rely on every completed Assistant Turn emitting a perfect machine envelope, yet it also cannot safely synthesize missing semantic routing itself.

## Observation 4 — nonterminal quiescence after successful in-band recovery

After syncing the generic in-band protocol-correction loop, the same run resumed successfully. The old `EVIDENCE-SYNTHESIS` response was extracted, a correction Turn was sent in the same durable synthesis conversation, the corrected handoff reached ROOT, and the run then continued through additional downstream responsibilities, RED-TEAM-driven follow-up work, and ROOT acceptance turns for more than twenty minutes.

The process finally exited with:

`applications.mandate_smoke_harness.BrokerError: RUN_NOT_TERMINAL_BUT_NO_EXECUTABLE_HANDOFF`

At that point there was no malformed envelope. The most recent closed Turn had produced an empty handoff list, leaving `pending=[]`, `queue=[]`, and a nonterminal run. Empty handoffs are legal for an individual closed Turn, so this state is not automatically transport corruption. The short smoke broker nevertheless treated global nonterminal quiescence as a fatal invariant violation.

Canonical creative state makes this especially important: RED-TEAM follow-up work had resolved several structural risks, but actual representative viewer laughter/performed timing remained explicitly unknown and greenlight-blocking. A responsibility can therefore honestly finish a Turn without having an immediately obvious next transport action while the parent mission remains unresolved. The broker must not choose the missing semantic work itself, but it also must not terminate the local process merely because the semantic frontier is temporarily empty.

## Correction on Modelrail experimental branch

Branch: `agent/mandate-creative-studio-4day`

Commits:
- `c29c36c779dabe018cde50e6a4ac5c9e87a16784` — studio broker transport-id recovery and explicit handoff schema guidance.
- `e9850973c0b322523b38501d97c56440cd26bc95` — regression coverage for a completed synthesis Turn whose DISPATCH omits `message_id`.
- `d708953e5db64ea7db17c2924810a47acb0a58de` — bind handoff sender identity to the persisted source responsibility/TurnRef rather than trusting Assistant-reported sender metadata.
- `ae836ccf8a1d093f6a31d47fcbdb6d56246aac4b` — regression coverage for wrong-sender recovery plus proof that sender normalization cannot grant run-control authority.
- `6129e9c999e5cd1e3a273965f83b6f7b404f8577` — replace field-by-field semantic guessing with an in-band protocol-correction loop for malformed terminal envelopes.
- `6066f095e6cef09a12c310ce86af010c999974a0` — regression coverage for the observed missing-target failure and for authority-violation correction without executing the forbidden control action.
- `e22fdd3bbf3eedd58088be9ac888c34ef158706f` — replace fatal nonterminal no-work handling with accountable in-band quiescence resolution.
- `3490cb250536ed666dbbcf07f77c4b2d943c4724` — regression coverage for same-owner quiescence recovery and bounded unresolved-quiescence blocking.

## Current recovery semantics

1. Studio bootstrap and dispatch prompts show the exact DISPATCH / PAUSE / TERMINATE handoff fields.
2. `message_id` is transport identity. If missing/blank, the studio broker deterministically derives it from persisted `run_id + responsibility_id + source TurnRef.turn_id + handoff index`.
3. Handoff sender identity is bound to the responsibility that owns the persisted source TurnRef. Missing or mismatched Assistant-reported `from_responsibility_id` is normalized to that source responsibility and audit-recorded.
4. Sender normalization cannot expand authority. A non-Run-Authority Turn that claims `from_responsibility_id: RUN-AUTHORITY` is rebound to its actual source responsibility before validation.
5. Missing semantic fields such as DISPATCH target/issue/action, PAUSE reason, or TERMINATE outcome are never inferred by the broker.
6. If parsing or strict validation fails, the broker opens a correction Turn in the same durable responsibility conversation. The correction Turn is explicitly transport-only: it must not repeat already completed research/creative/acceptance work and may read the already-persisted canonical issue state only as needed to emit a valid next handoff.
7. The rejected TurnRef remains the semantic receipt. The correction TurnRef is recorded separately as transport recovery evidence.
8. Protocol recovery attempts and identity normalizations are persisted in local audit state. A bounded number of failed correction attempts leads to a durable `RECOVERY_BLOCKED` checkpoint rather than an unrecorded traceback loop; explicit later `resume` retries that checkpoint after code/config correction.
9. Completed pending Turns are checkpointed one-by-one so one malformed result cannot erase already collected peers.
10. When the whole run becomes nonterminally quiescent (`pending=[]`, `queue=[]`), the broker does not guess the next responsibility or task. It reactivates the responsibility that produced the most recent completed receipt in that responsibility's existing durable conversation with a quiescence-resolution Turn.
11. The quiescence-resolution Turn must inspect canonical state and make an explicit accountable disposition: return completed work upward, create/continue justified work within authority, persist and escalate a genuine blocker/checkpoint, or—only for RUN-AUTHORITY—use PAUSE/TERMINATE when justified. It is explicitly forbidden from manufacturing work merely to keep the process busy.
12. Repeated empty quiescence resolutions are bounded. Exhaustion produces a durable `RECOVERY_BLOCKED` checkpoint with kind `QUIESCENCE_UNRESOLVED`, not a traceback or infinite loop. Quiescence recoveries are audit-recorded.
13. Existing semantic work is never restarted merely because transport/supervisor recovery is required.

## Scope

These corrections address the observed malformed-envelope and nonterminal-quiescence failure classes without modifying Modelrail Core and without allowing the broker to invent semantic routing, authority, or creative work. The long-running studio posture is now: normalize redundant transport identity; request in-band correction for malformed semantic/protocol envelopes; return an empty global frontier to the last accountable owner for explicit semantic disposition; checkpoint bounded unresolved recovery instead of crashing.

This still does not claim that every browser, network, OS-process, or Turn-submission crash is automatically recoverable. Those remain separate supervisor concerns.