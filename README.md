# Mandate

Mandate is a repository-native semantic coordination protocol for LLM work.

GitHub owns the durable semantic state: responsibilities, delegated task contracts, results, acceptance, authority, and run state. Modelrail is treated as an execution broker: it receives an addressed execution request, runs one closed Turn in a durable Conversation, and returns the completed result.

The protocol is intentionally small. Domain workflows such as research, engineering, creative work, or deterministic evaluation are configurations above the same coordination kernel.

## Current foundation

The v0.1 foundation is built around:

- explicit responsibility and accountability;
- no self-acceptance;
- contract-bound acceptance;
- downward delegation, upward results, and sideways signals;
- explicit run-control authority;
- persistent responsibility-to-conversation routing;
- closed execution transactions rather than open-ended workflow dialogue.

See `PROJECT_STATE.yaml` for the current accepted state and `governance/repo-map.yaml` for exact resource routing.

## Non-goals for v0.1

Mandate does not yet define a universal role library, a fixed organization hierarchy, a research workflow, a DAG engine, or a complete governance handbook. Those mechanisms must be earned by observed coordination failures or concrete domain needs.
