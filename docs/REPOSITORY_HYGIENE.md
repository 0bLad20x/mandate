# Repository Hygiene

This document defines how Mandate distinguishes active development, historical evidence and persisted runtime streams. The goal is a clean current repository without destroying evidence.

## Branch classes

### `main`

Only current accepted standalone Mandate source, package metadata, tests and documentation.

### `agent/*`

Temporary implementation/review branches. Delete after their work is merged or abandoned and any evidence worth retaining is recorded elsewhere.

### `migration/*`

Temporary transition refs. They exist only while a migration is being proven. Once the proof is documented, either delete the ref or replace it with an explicit `archive/*` ref when the commit itself remains important evidence.

### `archive/*`

Historical evidence. Archive refs are not active configuration and must not be used as dependency targets. They may preserve pre-migration repositories, failed fidelity attempts or other historically important snapshots.

## Current branch disposition snapshot — 2026-08-31

| Branch | Disposition |
| --- | --- |
| `main` | keep |
| `agent/modelrail-runtime-integration` | keep until the verified integration is accepted into main |
| `agent/mandate-repository-hygiene` | temporary; delete after its documentation is integrated |
| `agent/standalone-package-boundary` | delete after final Mandate integration; already represented in main/history |
| `agent/standalone-composition-boundary` | delete after final Mandate integration; already represented in main/history |
| `migration/modelrail-current-exact` | replace with a permanent archive ref to exact transfer commit `b126e21a9027dc7198db6de2c3cb9a3e0fab356b`, then delete the temporary migration name |
| `archive/legacy-main-pre-modelrail-transfer` | keep |
| `archive/legacy-modelrail-fidelity-attempt` | keep as migration evidence unless a later explicit archive-pruning decision removes it |
| `archive/legacy-smoke-foundation` | keep as historical evidence |

Branch deletion is repository hygiene, not evidence deletion, when the same commit remains reachable from accepted history or an archive ref.

## Issue classes

GitHub issues in this repository are not all backlog items. They may be one of four different things.

### 1. Current development/backlog issue

Represents work still being considered or implemented against the current standalone architecture.

Use normal open/closed lifecycle.

### 2. Durable Mandate run stream

`GitHubPersistence` uses issues titled `[mandate-run] <run_id>` as storage containers. Their bodies/Comments contain encoded protocol records.

The GitHub issue state is backend/UI metadata only. Mandate semantic Work state is reconstructed from canonical Work/Result/Decision records. `GitHubPersistence.resolve_stream()` searches `state=all`, so closing a completed stream does not erase semantic state.

Recommended labels:

- `run-evidence`
- optional `run-complete`
- optional `run-aborted`

Never delete a run stream that is part of accepted evidence.

### 3. Historical experiment/governance evidence

Older issues based on `mandate.coordination@0.1`, `PROJECT_STATE.yaml`, `governance/*`, `contracts/*`, `experiments/*`, Responsibility/Organization/SIGNAL/PAUSE/TERMINATE experiments belong to the pre-standalone evidence corpus unless explicitly promoted into the current package.

They are not active package contracts merely because they remain open.

Recommended treatment:

- preserve the issue and comments;
- label `legacy-evidence` or an equivalent archive label;
- close finished experiments as completed;
- close abandoned/superseded proposals as not planned/superseded;
- do not delete historical evidence solely to make the issue counter smaller.

### 4. Migration issue

Tracks repository extraction/package-boundary work. Close as completed once its acceptance gates and durable migration documentation are satisfied.

## Current run-stream disposition snapshot — 2026-08-31

| Issue | Semantic evidence | Recommended UI disposition |
| --- | --- | --- |
| `#122` `MANDATE-DFA4167A` | initial Work only; no completed Turn/Decision | preserve, close as aborted/not planned, label `run-evidence` + `run-aborted` |
| `#123` `MANDATE-5DA168EF` | complete Bootstrap trace ending in `ACCEPT` | preserve, close completed, label `run-evidence` + `run-complete` |
| `#124` `MANDATE-6D8E0B40` | complete Bootstrap trace ending in `ACCEPT` | preserve, close completed, label `run-evidence` + `run-complete` |
| `#129` `MANDATE-LIVE-20260831-1244` | accepted cross-repository live-separation proof | preserve permanently, close completed, label `run-evidence` + `run-complete` |

Issue `#121` is the package-foundation migration umbrella. Its deterministic-package and focused-live-run gates are now satisfied. It should be closed as completed after the migration/integration/hygiene documentation is accepted into `main`.

## Cleanup procedure

Repository cleanup should follow this order:

1. classify evidence before changing UI state;
2. commit durable migration/integration documentation;
3. merge accepted current implementation into `main`;
4. convert temporary migration evidence to `archive/*` where needed;
5. delete merged `agent/*` branches;
6. label and close current run streams according to semantic evidence;
7. classify and close historical experiment issues without deleting their evidence;
8. leave only real current work open.

Do not use GitHub open/closed state as a substitute for Mandate semantic state.