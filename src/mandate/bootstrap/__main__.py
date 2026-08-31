"""CLI for the vertically integrated Mandate Bootstrap package."""

from __future__ import annotations

import argparse
import json
import os
import secrets
from pathlib import Path

from modelrail.conversation.turn import TurnAPI

from mandate.persistence import GitHubPersistence

from .api import BootstrapAPI


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _token(env_file: Path) -> str:
    _load_env_file(env_file)
    value = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not value:
        raise SystemExit("GITHUB_TOKEN_OR_GH_TOKEN_REQUIRED")
    return value


def _print(value) -> None:
    print(json.dumps(value.__dict__, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Mandate Bootstrap")
    parser.add_argument("--repository", default="0bLad20x/llm-browser-modelrail")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--modelrail-root",
        type=Path,
        default=Path("workflow_runs/modelrail-conversations"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--provider", default="chatgpt")
    start.add_argument("--mission", required=True)
    start.add_argument("--run-id")

    resume = sub.add_parser("resume")
    resume.add_argument("--run-id", required=True)
    resume.add_argument("--external-input-file", type=Path)

    args = parser.parse_args()
    api = BootstrapAPI(
        GitHubPersistence(args.repository, _token(args.env_file)),
        TurnAPI(args.modelrail_root),
    )

    if args.command == "start":
        outcome = api.start(
            run_id=args.run_id or f"MANDATE-{secrets.token_hex(4).upper()}",
            mission=args.mission,
            provider=args.provider,
        )
    else:
        body = None
        if args.external_input_file is not None:
            body = args.external_input_file.read_text(encoding="utf-8").strip()
            if not body:
                raise SystemExit("EXTERNAL_INPUT_EMPTY")
        outcome = api.resume(
            run_id=args.run_id,
            authoritative_input=body,
        )
    _print(outcome)


if __name__ == "__main__":
    main()
