# Mandate Agent Instructions

This repository uses GitHub as canonical semantic state and Modelrail only as the execution broker.

## Read order for known work

1. Read `PROJECT_STATE.yaml` by exact path.
2. Read `governance/repo-map.yaml` by exact path.
3. Read `governance/protocol.yaml` by exact path.
4. Resolve the assigned responsibility from the run organization artifact referenced by the task/run.
5. Read the assigned GitHub issue directly by issue number.
6. Read `governance/conduct/index.yaml`, then only the conduct modules referenced by the responsibility/task or triggered by granted authority.
7. Read other resources only when explicitly authorized by the task or when discovery is itself part of the task.

## GitHub retrieval discipline

- Known file: use exact `fetch_file` with path and ref when supplied.
- Known issue: use exact `fetch_issue`; use issue comments only when the task requires the thread.
- Known directory: use a bounded exact directory read.
- Unknown resource: use constrained repository search only for discovery, then read the exact returned resource.
- Do not search for a resource whose exact identity is already known.
- Search snippets are discovery aids, not canonical evidence when an exact resource can be read.
- When reproducibility matters, resolve one repository commit and read required files at that pinned ref.

## Authority discipline

Do not infer permissions, acceptance authority, delegation authority, or run-control authority from a title or conversation history. Use only canonical organization state and the protocol.

Do not broaden the assigned task by crawling unrelated repository state. GitHub task/resource references are authorization and context boundaries unless the task explicitly grants discovery scope.

## Closed execution transaction

Each dispatched execution handles one addressed contract and returns one completed result. Further work requires a new GitHub-side contract or message, even when the same durable Modelrail conversation is continued.
