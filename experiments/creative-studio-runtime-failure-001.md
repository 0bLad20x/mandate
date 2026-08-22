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

## Correction on Modelrail experimental branch

Branch: `agent/mandate-creative-studio-4day`

Commits:
- `c29c36c779dabe018cde50e6a4ac5c9e87a16784` — studio broker transport-id recovery and explicit handoff schema guidance.
- `e9850973c0b322523b38501d97c56440cd26bc95` — regression coverage for a completed synthesis Turn whose DISPATCH omits `message_id`.
- `d708953e5db64ea7db17c2924810a47acb0a58de` — bind handoff sender identity to the persisted source responsibility/TurnRef rather than trusting Assistant-reported sender metadata.
- `ae836ccf8a1d093f6a31d47fcbdb6d56246aac4b` — regression coverage for wrong-sender recovery plus proof that sender normalization cannot grant run-control authority.

Correction semantics:

1. Studio bootstrap and dispatch prompts show the exact DISPATCH / PAUSE / TERMINATE handoff fields.
2. `message_id` is transport identity. If and only if it is missing/blank, the studio broker deterministically derives it from persisted `run_id + responsibility_id + source TurnRef.turn_id + handoff index`.
3. Handoff sender identity is bound to the responsibility that owns the persisted source TurnRef. Missing or mismatched Assistant-reported `from_responsibility_id` is normalized to that source responsibility and audit-recorded.
4. Sender normalization cannot expand authority. A non-Run-Authority Turn that claims `from_responsibility_id: RUN-AUTHORITY` is rebound to its actual source responsibility before validation, so PAUSE/TERMINATE remains rejected.
5. No semantic target, issue number, action, PAUSE reason, or TERMINATE outcome is inferred. Those fields remain strict validator failures.
6. Transport repairs are recorded in local `transport_repairs` audit state.
7. Completed pending Turns are checkpointed one-by-one during collection so a later malformed result cannot discard earlier collection progress.
8. Because both observed failures exited before the collector removed the offending pending Turn, persisted TurnRef `43b102` should remain resumable after syncing the latest correction; semantic research should not be restarted.

## Scope

This corrects the two observed recoverable transport-identity failures without modifying Modelrail Core and without weakening authority validation. It does not claim that every possible long-duration browser/network/process failure is automatically recoverable; broader crash-gap/restart guarantees remain a separate runtime concern.
