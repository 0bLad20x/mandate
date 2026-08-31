"""GitHub issue/comment implementation of the Persistence contract."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .base import PersistedEntry, StreamRef

_VERSION = "mandate.persistence.github:v1"
_META = re.compile(
    rf"<!-- {re.escape(_VERSION)} metadata -->\n```json\n(?P<body>.*?)\n```",
    re.S,
)


class GitHubPersistenceError(RuntimeError):
    pass


class GitHubPersistence:
    backend = "github"

    def __init__(self, repository: str, token: str) -> None:
        owner, sep, name = repository.partition("/")
        if not sep or not owner or not name or "/" in name:
            raise ValueError("REPOSITORY_MUST_BE_OWNER_SLASH_REPO")
        if not token.strip():
            raise ValueError("GITHUB_TOKEN_REQUIRED")
        self.owner = owner
        self.name = name
        self.token = token

    def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        raw_body = json.dumps(data).encode() if data is not None else None
        request = Request(
            "https://api.github.com" + path,
            method=method,
            data=raw_body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "modelrail-mandate",
                **({"Content-Type": "application/json"} if raw_body else {}),
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode()
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:700]
            raise GitHubPersistenceError(
                f"GITHUB_HTTP_{exc.code}:{detail}"
            ) from exc
        except URLError as exc:
            raise GitHubPersistenceError(
                f"GITHUB_CONNECTION_ERROR:{exc.reason}"
            ) from exc
        return json.loads(body) if body else None

    def create_stream(
        self,
        run_id: str,
        metadata: Mapping[str, str],
    ) -> StreamRef:
        if not run_id.strip():
            raise ValueError("RUN_ID_REQUIRED")
        payload = {"run_id": run_id, **dict(metadata)}
        value = self._request(
            "POST",
            f"/repos/{quote(self.owner)}/{quote(self.name)}/issues",
            {
                "title": f"[mandate-run] {run_id}",
                "body": (
                    "Mandate durable coordination stream. Backend representation only; "
                    "semantic meaning is owned by encoded protocol payloads.\n\n"
                    f"<!-- {_VERSION} metadata -->\n```json\n"
                    + json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n```"
                ),
            },
        )
        number = value.get("number") if isinstance(value, dict) else None
        if not isinstance(number, int):
            raise GitHubPersistenceError("STREAM_CREATION_FAILED")
        return StreamRef(self.backend, str(number))

    def resolve_stream(self, run_id: str) -> StreamRef:
        expected = f"[mandate-run] {run_id}"
        matches: list[int] = []
        page = 1
        while True:
            rows = self._request(
                "GET",
                f"/repos/{quote(self.owner)}/{quote(self.name)}/issues"
                f"?state=all&per_page=100&page={page}",
            )
            if not isinstance(rows, list):
                raise GitHubPersistenceError("STREAM_DISCOVERY_FAILED")
            for item in rows:
                if (
                    isinstance(item, dict)
                    and item.get("title") == expected
                    and isinstance(item.get("number"), int)
                    and "pull_request" not in item
                ):
                    matches.append(item["number"])
            if len(rows) < 100:
                break
            page += 1
        if len(matches) != 1:
            raise GitHubPersistenceError(
                f"STREAM_RESOLUTION_FAILED:{len(matches)}"
            )
        return StreamRef(self.backend, str(matches[0]))

    def metadata(self, stream: StreamRef) -> Mapping[str, str]:
        self._validate_stream(stream)
        issue = self._request(
            "GET",
            f"/repos/{quote(self.owner)}/{quote(self.name)}/issues/"
            f"{quote(stream.value)}",
        )
        body = issue.get("body") if isinstance(issue, dict) else None
        match = _META.search(body) if isinstance(body, str) else None
        if match is None:
            raise GitHubPersistenceError("STREAM_METADATA_NOT_FOUND")
        raw = json.loads(match.group("body"))
        if not isinstance(raw, dict):
            raise GitHubPersistenceError("STREAM_METADATA_INVALID")
        return {str(key): str(value) for key, value in raw.items()}

    def append(self, stream: StreamRef, body: str) -> PersistedEntry:
        self._validate_stream(stream)
        if not isinstance(body, str) or not body.strip():
            raise ValueError("PERSISTENCE_BODY_REQUIRED")
        value = self._request(
            "POST",
            f"/repos/{quote(self.owner)}/{quote(self.name)}/issues/"
            f"{quote(stream.value)}/comments",
            {"body": body},
        )
        identifier = value.get("id") if isinstance(value, dict) else None
        if not isinstance(identifier, int):
            raise GitHubPersistenceError("ENTRY_APPEND_FAILED")
        return PersistedEntry(str(identifier), body)

    def read(self, stream: StreamRef) -> tuple[PersistedEntry, ...]:
        self._validate_stream(stream)
        out: list[PersistedEntry] = []
        page = 1
        while True:
            rows = self._request(
                "GET",
                f"/repos/{quote(self.owner)}/{quote(self.name)}/issues/"
                f"{quote(stream.value)}/comments?per_page=100&page={page}",
            )
            if not isinstance(rows, list):
                raise GitHubPersistenceError("ENTRY_READ_FAILED")
            for item in rows:
                body = item.get("body") if isinstance(item, dict) else None
                identifier = item.get("id") if isinstance(item, dict) else None
                if isinstance(body, str) and isinstance(identifier, int):
                    out.append(PersistedEntry(str(identifier), body))
            if len(rows) < 100:
                return tuple(out)
            page += 1

    def _validate_stream(self, stream: StreamRef) -> None:
        if stream.backend != self.backend or not stream.value.strip():
            raise ValueError("GITHUB_STREAM_REF_INVALID")
