# CREATIVE-STUDIO-LIVE-001 runtime failure 001

## Observation

The first `CREATIVE-STUDIO-LIVE-001` execution reached a completed downstream research/synthesis Turn and then the local studio broker exited with:

`applications.mandate_smoke_harness.BrokerError: HANDOFF_MESSAGE_ID_REQUIRED`

The failure occurred after Modelrail had extracted the completed Assistant response. Canonical semantic work had already been persisted in GitHub, including the research results and synthesis. The failure was therefore at the transport-envelope boundary, not in the creative responsibility graph or the persisted research work.

## Root cause

The shared broker validator requires every handoff to contain a non-empty `message_id`, but the studio prompts specified only the outer terminal shape (`{"run_id":"...","handoffs":[...]}`) and did not spell out the required per-handoff transport schema. A completed Assistant Turn omitted `message_id`; the validator correctly rejected it, but the long-running studio wrapper had no transport-only normalization for this recoverable omission.

## Correction on Modelrail experimental branch

Branch: `agent/mandate-creative-studio-4day`

Commits:
- `c29c36c779dabe018cde50e6a4ac5c9e87a16784` — studio broker transport-id recovery and explicit handoff schema guidance.
- `e9850973c0b322523b38501d97c56440cd26bc95` — regression coverage for a completed synthesis Turn whose DISPATCH omits `message_id`.

Correction semantics:

1. Studio bootstrap and dispatch prompts now show the exact DISPATCH / PAUSE / TERMINATE handoff fields.
2. `message_id` is treated as transport identity. If and only if it is missing/blank, the studio broker deterministically derives it from persisted `run_id + responsibility_id + source TurnRef.turn_id + handoff index`.
3. The repair is recorded in local `transport_repairs` audit state.
4. No semantic routing, action, sender authority, issue number, PAUSE reason, or TERMINATE outcome is inferred. Those fields remain strict validator failures.
5. Completed pending Turns are checkpointed one-by-one during collection so a later malformed result cannot discard earlier collection progress.
6. Because the failed run exited before the old collector saved removal of the offending pending Turn, the persisted TurnRef should remain resumable after syncing the correction; semantic research should not be restarted.

## Scope

This corrects the observed recoverable transport-envelope failure without modifying Modelrail Core and without weakening authority validation. It is not evidence that every possible long-duration browser/network/process failure is now automatically recoverable; broader crash-gap/restart guarantees remain a separate runtime concern.
