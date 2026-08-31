"""Backend-neutral durable stream contract.

Persistence owns storage/acquisition only. Payload meaning belongs to the semantic
package that encoded it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class StreamRef:
    backend: str
    value: str


@dataclass(frozen=True)
class PersistedEntry:
    backend_id: str
    body: str


class Persistence(Protocol):
    def create_stream(
        self,
        run_id: str,
        metadata: Mapping[str, str],
    ) -> StreamRef: ...

    def resolve_stream(self, run_id: str) -> StreamRef: ...

    def metadata(self, stream: StreamRef) -> Mapping[str, str]: ...

    def append(self, stream: StreamRef, body: str) -> PersistedEntry: ...

    def read(self, stream: StreamRef) -> tuple[PersistedEntry, ...]: ...
