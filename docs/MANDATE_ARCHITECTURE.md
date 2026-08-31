# Mandate Architecture

This document describes the current package-level Mandate foundation derived from the
frozen provisional Accountable Work Core and the V9 Bootstrap semantics.

V10 reconstruction code is evidence about persistence pressure only; its changed
cognitive execution conditions are **not** promoted into this architecture.

## Purpose

Mandate owns semantic coordination. Modelrail owns LLM Turn execution. Persistence
owns durable storage/acquisition only.

The architecture follows one rule:

> One system question has one owner and one durable truth.

Cross-repository dependency and update rules are defined in
[Repository Integration Contract](REPOSITORY_INTEGRATION_CONTRACT.md).

## Public boundaries

```text
Application / composition root
   |
   v
BootstrapAPI
   |
   +--> AccountableWorkLedger --> accountable_work.core
   |
   +--> Persistence -----------> GitHubPersistence today
   |
   +--> Modelrail TurnAPI -----> provider/runtime mechanics
```

The standalone `mandate` distribution packages only `src/mandate`. Modelrail is an
external execution dependency at the Bootstrap integration boundary; Modelrail does not
own or import Mandate coordination semantics.

The verified Modelrail integration commit
`01c09f794c15d9680dff523891cbb6a0a6a7933c` packages only `src/modelrail` while
preserving the frozen Mandate source snapshot in the Modelrail repository for rollback
and migration evidence. Mandate declares that exact commit as its external runtime
dependency. `uv.lock` resolves the same commit. This makes the runtime composition
reproducible without `PYTHONPATH`, editable cross-repository source paths, or an implicit
dependency on Modelrail `main`.

The standalone live proof `MANDATE-LIVE-20260831-1244` executed this exact composition
through ChatGPT and ended in a persisted `ACCEPT` Decision. The provider repository may
therefore advance its own packaging branch separately; Mandate's accepted dependency
identity is the immutable tested commit, not a branch name.

## 0. Composition root

Owner question:

> Which concrete infrastructure adapters and execution runtime are selected for one Mandate process?

The Bootstrap CLI is the current composition root. It wires:

```text
GitHubPersistence(repository, token)
TurnAPI(modelrail_root)
BootstrapAPI(persistence, turn_api)
```

Composition configuration is deployment input, not semantic truth. In particular, the
Persistence repository is required explicitly; Mandate has no hidden default that points
to the Modelrail repository or any other coordination stream destination.

The composition root may select a different Persistence adapter or execution runtime in
the future without changing Accountable Work semantics.

## 1. Accountable Work

Owner question:

> What Work exists, what Result answered it, and what accountable Decision governs it?

`mandate.accountable_work.core` owns only:

```text
Work
Result
Decision = ACCEPT | CONTINUE
actor provenance
issuer / assignee / decision authority
derived open / closed projection
```

It has no dependency on Bootstrap, Persistence, GitHub, Modelrail, HITL, providers,
workflow phases, or run control.

`mandate.accountable_work.ledger` owns only serialization/reconstruction of those
semantic records through the Persistence contract. It does not change their meaning.

Stable canonical references are writer-independent. Sequential `R0001` notation was
experiment notation, not a Work-Core requirement.

The clean main-based foundation contains one Accountable Work implementation under
`src/mandate/accountable_work`; historical experiment implementations are not copied
into this branch.

## 2. Persistence

Owner question:

> How are opaque durable entries stored, reacquired, and located independently of the backend?

Public operations:

```text
create_stream(run_id, metadata) -> StreamRef
resolve_stream(run_id) -> StreamRef
metadata(stream) -> Mapping[str, str]
append(stream, opaque_body) -> PersistedEntry
read(stream) -> ordered PersistedEntry[]
```

Persistence does not interpret Work, Result, Decision, Bootstrap, Human input, or
provider mechanics.

`GitHubPersistence` is the current adapter behind the Mandate-owned `Persistence` port.
Its GitHub Issue/Comment shape is private backend mechanics. A SQL, MongoDB, JSONL, or
other implementation may replace it by implementing the same boundary without changing
semantic packages. The adapter remains inside Mandate because it implements Mandate's
persistence boundary; the use of GitHub technology alone does not create an independent
system ownership boundary.

Mission, provider, authoritative Human input, Work records, and Bootstrap execution
references required to reconstruct Mandate coordination flow through this same
Persistence boundary. They are not authoritative Mandate-local files.

## 3. Bootstrap

Owner question:

> Given the Human mission and authoritative context, what faithful pre-execution handoff is justified?

Bootstrap remains ordinary Accountable Work. Its Work objective/acceptance and its
BOOTSTRAP/RUN-AUTHORITY reasoning criteria are taken from the V9 semantic reference.

Bootstrap does **not** add a Work-Core Decision value or a HITL record. The only
canonical Decision values remain:

```text
ACCEPT
CONTINUE
```

`CONTINUE` still means only that the same Work remains open.

For deterministic package reconstruction, Bootstrap requires its RUN-AUTHORITY
`Decision.judgment` to end with one Bootstrap-local interpretation block:

```text
BOOTSTRAP_CONTINUATION: AUTONOMOUS
```

or:

```text
BOOTSTRAP_REQUEST: <request justified by the Work>
BOOTSTRAP_CONTINUATION: EXTERNAL_INPUT
```

or, for ACCEPT:

```text
BOOTSTRAP_CONTINUATION: COMPLETE
```

These lines are part of the existing canonical `Decision.judgment`. They are not a
second Decision field, persisted status, phase, capability, or Work-Core primitive.
The semantic justification remains the judgment itself.

Authoritative Human input is accepted only when the latest canonical CONTINUE judgment
requires external input. The input is correlated to that Decision and persisted before
Bootstrap continues.

`BootstrapAPI.resume(run_id=...)` reconstructs mission and provider from Persistence;
the caller does not re-supply them as a second truth.

## 4. Modelrail

Owner question:

> How is one referenced LLM Turn executed and continued across provider mechanics?

Mandate consumes only Modelrail's public Turn boundary:

```text
TurnRequest
TurnRef
TurnResult
TurnAPI
```

Provider, browser, extraction, lifecycle, and Conversation progression stay inside
Modelrail. Mandate persists the relevant Conversation/Turn references needed to address
its two semantic perspectives without importing Modelrail provider internals.

Modelrail Conversation State is execution-substrate state, not a duplicate of Mandate
coordination truth. Moving Modelrail execution across machines requires the Modelrail
execution state to be reachable by that Modelrail deployment; Mandate does not copy or
reinterpret it.

The standalone Mandate package does not hide this dependency through environment-specific
source paths. Its project metadata pins the verified Modelrail packaging-boundary commit,
and the committed `uv.lock` preserves that same resolved commit. Runtime integration
acceptance verifies installed PEP 610 provenance and confirms that the installed Modelrail
distribution exports `modelrail` but not `mandate`.

## 5. Reconstruction

No Mandate `run-state.json` is authoritative.

A fresh Mandate process reconstructs from the Persistence boundary:

```text
stream metadata
   +
ordered persisted entries
   |
   +--> accountable-work records --> Work projection
   +--> authoritative Bootstrap inputs
   +--> Modelrail Turn references
   |
   v
BootstrapAPI
```

Local Human-input files are ingress only. Once accepted, their content is persisted
before semantic continuation. Local caches may be deleted without changing canonical
Mandate coordination truth.

## 6. Horizontal execution boundary

The package removes stream-local sequential ID allocation so independent writers do
not depend on a shared in-process counter for canonical identity.

This does **not** grant multiple workers authority to race the same semantic action.
Conflicting concurrent Decisions or duplicate execution of the same open Work are
run-control questions. Existing Mandate rules already require explicit Run Control
authority; that owner is not silently invented here.

The current foundation therefore supports stateless reconstruction and distribution of
independent runs/work across workers while keeping same-Work execution authority
explicit rather than hiding it inside Persistence.

## 7. Current package structure

```text
src/mandate/
├── accountable_work/
│   ├── core.py
│   ├── ledger.py
│   └── __init__.py
├── bootstrap/
│   ├── contract.py
│   ├── api.py
│   ├── __main__.py
│   └── __init__.py
├── persistence/
│   ├── base.py
│   ├── github.py
│   └── __init__.py
└── __init__.py
```

The wheel target is exactly `src/mandate`. Modelrail is not packaged inside Mandate.

## 8. Explicit non-goals of this foundation

Not introduced here:

- global scheduler or workflow engine;
- generic HITL subsystem;
- organization runtime or reorganization protocol;
- SIGNAL semantics;
- resource/capability framework;
- provider allocator;
- generic audit subsystem;
- duplicated persisted OPEN/CLOSED/phase/status state;
- GitHub-shaped semantic records;
- hidden defaults that select another repository as Mandate's persistence destination;
- environment-specific `PYTHONPATH` composition as a substitute for declared package dependencies.

Those require their own semantic ownership evidence before a package boundary is added.
