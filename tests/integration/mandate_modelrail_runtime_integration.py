"""Executable proof of the declared Mandate -> Modelrail runtime composition."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

import mandate
import modelrail


ROOT = Path(__file__).resolve().parents[2]
MODELRAIL_COMMIT = "9452d6b51b179fb0f5d0a3d34b0ddd740dc71c72"
MODELRAIL_REPOSITORY = "github.com/0bLad20x/llm-browser-modelrail"


def self_test() -> None:
    mandate_path = Path(mandate.__file__).resolve()
    modelrail_path = Path(modelrail.__file__).resolve()
    source_root = (ROOT / "src").resolve()

    assert mandate_path.is_relative_to((source_root / "mandate").resolve()), mandate_path
    assert not (source_root / "modelrail").exists()
    assert not modelrail_path.is_relative_to(source_root), modelrail_path
    print("MANDATE_IMPORT_OWNED_BY_STANDALONE_REPOSITORY_OK")
    print("MODELRAIL_IMPORT_NOT_FROM_MANDATE_SOURCE_TREE_OK")

    lock_path = ROOT / "uv.lock"
    assert lock_path.is_file(), "UV_LOCK_REQUIRED_FOR_REPRODUCIBLE_RUNTIME"
    lock_text = lock_path.read_text(encoding="utf-8")
    assert MODELRAIL_REPOSITORY in lock_text
    assert MODELRAIL_COMMIT in lock_text
    print("MANDATE_UV_LOCK_PINS_MODELRAIL_COMMIT_OK")

    distribution = importlib.metadata.distribution("llm-browser-modelrail")
    direct_url_raw = distribution.read_text("direct_url.json")
    assert direct_url_raw is not None, "MODELRAIL_DIRECT_URL_METADATA_REQUIRED"
    direct_url = json.loads(direct_url_raw)

    url = str(direct_url.get("url", ""))
    vcs_info = direct_url.get("vcs_info")
    assert MODELRAIL_REPOSITORY in url, url
    assert isinstance(vcs_info, dict), vcs_info
    assert vcs_info.get("vcs") == "git", vcs_info
    assert vcs_info.get("commit_id") == MODELRAIL_COMMIT, vcs_info
    print("MANDATE_INSTALLED_MODELRAIL_PROVENANCE_OK")

    files = tuple(distribution.files or ())
    assert any(str(path).replace("\\", "/").startswith("modelrail/") for path in files)
    assert not any(str(path).replace("\\", "/").startswith("mandate/") for path in files)
    print("MANDATE_INSTALLED_MODELRAIL_NAMESPACE_ONLY_OK")

    print("MANDATE_MODELRAIL_RUNTIME_INTEGRATION_OK")


if __name__ == "__main__":
    self_test()
