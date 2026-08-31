# Mandate

Mandate owns semantic coordination for accountable work and Bootstrap. Modelrail is an external execution runtime for referenced LLM Turns; it does not own Mandate coordination semantics.

## Ownership

```text
Application / composition root
        |
        v
   BootstrapAPI
      /     \
     v       v
Persistence  Modelrail TurnAPI
     |
     v
Accountable Work records
```

Mandate owns:

- `Work -> Result -> Decision(ACCEPT|CONTINUE)` semantics;
- Bootstrap interpretation and continuation rules;
- backend-neutral Persistence and the current GitHub adapter;
- reconstruction of Mandate coordination state.

Modelrail owns provider/browser execution, durable Conversation/Turn mechanics, lifecycle and extraction beneath its public Turn API.

## Repository status

The current standalone package was transferred exactly from the frozen Mandate snapshot that previously lived in Modelrail, then adapted only where a standalone repository requires an explicit package/composition boundary. The transfer evidence and every intentional post-transfer deviation are recorded in [Migration from Modelrail](docs/MIGRATION_FROM_MODELRAIL.md).

The verified runtime composition pins Modelrail to an immutable commit and commits `uv.lock`; cross-repository editable installs and `PYTHONPATH` composition are not part of the architecture.

## Documentation

- [Architecture](docs/MANDATE_ARCHITECTURE.md) — current semantic ownership and runtime composition.
- [Accountable Work Core](docs/MANDATE_ACCOUNTABLE_WORK_CORE.md) — transferred provisional core contract; preserved as source evidence.
- [Migration from Modelrail](docs/MIGRATION_FROM_MODELRAIL.md) — exact transfer proof and intentional standalone changes.
- [Repository Integration Contract](docs/REPOSITORY_INTEGRATION_CONTRACT.md) — standard for dependencies and communication between repositories.
- [Repository Hygiene](docs/REPOSITORY_HYGIENE.md) — branch, issue and persisted-run lifecycle rules.

## Local setup

```powershell
uv sync --locked
```

Local secrets and browser-profile configuration belong in `.env`, which is ignored by Git. Start from `.env.example`.

Core deterministic gates:

```powershell
uv run --locked python .\tests\integration\mandate_accountable_work_package.py
uv run --locked python .\tests\integration\mandate_standalone_composition_boundary.py
uv run --locked python .\tests\integration\mandate_modelrail_runtime_integration.py
uv run --locked python .\tests\integration\mandate_package_vertical.py --self-test
```

## Repository-state rule

GitHub issues may be used by `GitHubPersistence` as durable stream containers. The GitHub issue open/closed flag is backend/UI state; it is not Mandate's semantic Work open/closed truth. Semantic truth is reconstructed from the encoded persisted records.

Historical pre-standalone experiments remain evidence, not current package contracts. Archive branches and historical issues must not be treated as active runtime configuration merely because they remain accessible.