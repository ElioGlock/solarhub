from __future__ import annotations

from dataclasses import dataclass, field

from solarhub.kinds import BUILTIN, BUILTIN_IDS

KINDS = BUILTIN_IDS  # tipos embutidos; tipos declarados pelos repositórios: solarhub.kinds.registry(store)
KIND_LABELS = {k.id: k.label for k in BUILTIN}


@dataclass
class Document:
    source: str
    path: str  # caminho relativo (posix) dentro da fonte
    kind: str
    title: str
    body: str
    ref_id: str | None = None
    status: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    commit_sha: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.path}"

    @property
    def ref(self) -> str:
        return f"{self.kind}:{self.ref_id}" if self.ref_id else self.uid
