"""Deterministic checks for the standalone Mandate composition boundary."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from mandate.accountable_work import (
    ActorAuthority,
    CanonicalRecord,
    Work,
    project,
)
from mandate.persistence import GitHubPersistence, Persistence


ROOT = Path(__file__).resolve().parents[2]
MANDATE_SRC = ROOT / "src" / "mandate"
MODELRAIL_RUNTIME = (
    "llm-browser-modelrail @ "
    "git+https://github.com/0bLad20x/llm-browser-modelrail.git@"
    "01c09f794c15d9680dff523891cbb6a0a6a7933c"
)


def _modelrail_importers() -> list[str]:
    importers: list[str] = []
    for path in sorted(MANDATE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(name == "modelrail" or name.startswith("modelrail.") for name in names):
                importers.append(path.relative_to(ROOT).as_posix())
                break
    return importers


def _repository_argument_is_explicit() -> bool:
    path = MANDATE_SRC / "bootstrap" / "__main__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        if any(
            isinstance(arg, ast.Constant) and arg.value == "--repository"
            for arg in node.args
        ):
            matches.append(node)
    if len(matches) != 1:
        return False
    keywords = {keyword.arg: keyword.value for keyword in matches[0].keywords}
    required = keywords.get("required")
    return (
        isinstance(required, ast.Constant)
        and required.value is True
        and "default" not in keywords
    )


def self_test() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        package = tomllib.load(handle)

    assert package["project"]["name"] == "mandate"
    assert package["project"]["dependencies"] == [MODELRAIL_RUNTIME]
    assert package["tool"]["hatch"]["metadata"]["allow-direct-references"] is True
    assert package["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/mandate"
    ]
    assert not (ROOT / "src" / "modelrail").exists()
    print("MANDATE_STANDALONE_PACKAGE_BOUNDARY_OK")
    print("MANDATE_MODELRAIL_RUNTIME_PIN_EXPLICIT_OK")
    print("MANDATE_DIRECT_RUNTIME_REFERENCE_ALLOWED_OK")

    # The Accountable Work core remains semantically independent even though the
    # complete distribution declares the runtime needed by Bootstrap composition.
    actors = {
        "ROOT": ActorAuthority(may_issue_work=True),
        "WORKER": ActorAuthority(may_issue_work=False),
    }
    projection = project(
        (
            CanonicalRecord(
                "W-COMPOSITION",
                "ROOT",
                Work("WORKER", "Prove core isolation.", ("Work remains open.",)),
            ),
        ),
        actors,
    )
    assert projection.open_work_refs() == {"W-COMPOSITION"}
    print("MANDATE_WORK_CORE_WITHOUT_MODELRAIL_SEMANTICS_OK")

    importers = _modelrail_importers()
    assert importers
    assert all(path.startswith("src/mandate/bootstrap/") for path in importers), importers
    print("MANDATE_MODELRAIL_CONSUMPTION_BOOTSTRAP_ONLY_OK")

    all_source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(MANDATE_SRC.rglob("*.py"))
    )
    assert "0bLad20x/llm-browser-modelrail" not in all_source
    assert _repository_argument_is_explicit()
    print("MANDATE_PERSISTENCE_DESTINATION_EXPLICIT_OK")

    assert getattr(Persistence, "_is_protocol", False) is True
    for operation in ("create_stream", "resolve_stream", "metadata", "append", "read"):
        assert hasattr(Persistence, operation)
        assert hasattr(GitHubPersistence, operation)
    assert GitHubPersistence.backend == "github"
    print("MANDATE_GITHUB_PERSISTENCE_ADAPTER_BOUNDARY_OK")

    print("MANDATE_STANDALONE_COMPOSITION_BOUNDARY_OK")


if __name__ == "__main__":
    self_test()
