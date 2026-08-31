# Repository Integration Contract

This document defines the default contract for connecting independently owned repositories. Mandate -> Modelrail is the first proven instance, but the rules are repository-neutral.

## 1. Ownership before dependency

A repository boundary exists because one system question has one owner.

Before adding a dependency, identify:

- the capability/question owned by the provider repository;
- the capability/question owned by the consumer repository;
- the public contract crossing the boundary;
- the state that remains private to each owner.

Do not split repositories merely because technologies differ, and do not combine ownership merely because one process imports both packages.

## 2. One namespace, one owner

Each distributable namespace/package has exactly one repository owner.

A provider distribution must not export the consumer's namespace. A consumer must not vendor or copy the provider's source as a second owner.

For Mandate and Modelrail:

```text
mandate distribution  -> exports mandate/
modelrail distribution -> exports modelrail/
```

## 3. Public contracts only

Consumers depend on documented public surfaces, not provider internals.

Mandate consumes Modelrail only through the Turn boundary:

```text
TurnRequest
TurnRef
TurnResult
TurnAPI
```

Provider/browser/extraction/lifecycle mechanics remain Modelrail-private. Modelrail does not import Mandate coordination semantics.

## 4. Dependencies are declared, immutable and reproducible

Cross-repository composition must be represented in project metadata and the dependency lock, not in operator shell state.

Required properties:

- dependency declared in the consumer project;
- immutable provider identity: released version or exact commit SHA;
- lockfile committed when the project uses a lock-based resolver;
- installed provenance verifiable when supported;
- no `PYTHONPATH` composition;
- no cross-repository editable install as the accepted integration mechanism;
- no assumption that an unpinned provider branch will remain compatible.

For VCS dependencies, PEP 610 `direct_url.json` is useful runtime evidence of the installed commit.

## 5. State ownership does not cross silently

Package composition does not transfer ownership of durable state.

For Mandate / Modelrail:

- Mandate Persistence owns durable semantic coordination records;
- Modelrail owns execution-substrate Conversation/Turn state;
- Mandate may persist references required to address Modelrail Turns, but does not copy or reinterpret Modelrail's internal execution state;
- Modelrail does not treat Mandate's Work/Result/Decision records as provider runtime state.

The same rule applies to future integrations: references may cross a boundary; hidden duplicate truth must not.

## 6. Provider update protocol

When a provider repository changes a public capability consumed elsewhere:

1. **Provider branch** — implement the provider change without modifying consumers implicitly.
2. **Provider gates** — run provider-local tests and package/namespace boundary checks.
3. **Immutable provider candidate** — identify the exact tested release or commit SHA.
4. **Consumer branch** — update only the declared dependency/adapter usage required by the public-contract change.
5. **Lock resolution** — regenerate and commit the consumer lockfile where applicable.
6. **Consumer contract tests** — prove namespace ownership, import/provenance and public API compatibility.
7. **Behavioral/live gate** — when the boundary reaches an external system, run one focused live acceptance test through the consumer.
8. **Record evidence** — cross-reference provider and consumer PRs and the exact tested identities.
9. **Merge deliberately** — merge in an order that keeps every committed consumer dependency resolvable.

A provider branch name is not the contract. The immutable tested commit/release is.

## 7. Backward-compatible versus coordinated changes

A provider change is backward-compatible when the consumer's documented contract and tests continue unchanged.

A coordinated change is required when any of the following changes materially:

- public symbol or call shape;
- result semantics;
- durable reference semantics;
- error/recovery contract;
- package/namespace ownership;
- required runtime configuration;
- state reachability assumptions.

Coordinated changes require provider and consumer evidence; they must not be disguised as local implementation details.

## 8. Integration tests prove the boundary, not implementation coincidence

A useful cross-repository test should answer questions such as:

- Did the consumer import its own namespace from its own package?
- Did the provider distribution export only its owned namespace?
- Is the installed provider exactly the declared immutable version/commit?
- Does the consumer use the provider's public contract rather than source-path reach-through?
- Can the composed system complete one representative interaction?
- Can durable state be reconstructed by its rightful owner after process restart?

Tests should fail if a second namespace owner, hidden source path or wrong provider revision appears.

## 9. Rollback

Rollback is an explicit dependency decision:

```text
consumer pin: provider candidate B
        -> failure
consumer pin: previous known-good provider A
```

Do not repair a failed integration by copying provider code into the consumer, adding path precedence, or leaving two package owners installed.

## 10. Documentation and PR evidence

Every accepted cross-repository integration should record:

- provider repository and immutable version/commit;
- consumer repository and integration commit/PR;
- public contract used;
- dependency direction;
- state ownership on each side;
- deterministic gates run;
- live gate when required;
- known rollback identity.

Provider and consumer PRs should cross-reference one another when both repositories change.

## 11. Mandate -> Modelrail reference implementation

The current proven boundary is:

```text
Mandate BootstrapAPI
      |
      v
Modelrail TurnAPI
      |
      v
provider/browser runtime
```

Mandate pins verified Modelrail commit `01c09f794c15d9680dff523891cbb6a0a6a7933c`. The integration proof verifies the lockfile, installed VCS provenance and that the Modelrail distribution contains `modelrail/` but not `mandate/`.

The live proof `MANDATE-LIVE-20260831-1244` completed through ChatGPT and persisted the final Mandate Decision in the Mandate repository. This is the acceptance pattern future cross-repository integrations should emulate where equivalent live behavior exists.