"""Tipos sugeridos: o Solarhub propõe, você decide.

Junta as pistas do conteúdo (solarhub.detect) por pasta e propõe:
- "a pasta X parece <tipo existente>"  (ex.: regras-seguranca/ parece Guardrails)
- "a pasta X tem documentos sem tipo: criar uma aba?"  (tipo novo, com o nome que você escolher)

Aceitar grava uma regra só no seu Solarhub (config.toml, na fonte), nunca no repositório, e reindexa a fonte.
Ignorar não pergunta de novo. Tudo pode ser desfeito.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from solarhub import config, indexer, kinds
from solarhub.store import Store

FOLDER_MIN = 2         # documentos parecidos para sugerir a pasta inteira
FOLDER_SHARE = 0.6     # e pelo menos 60% dos documentos sem tipo da pasta
NEW_TYPE_MIN = 3       # documentos sem tipo para sugerir uma aba nova
STRONG = 2.0           # pontuação para sugerir um arquivo sozinho
GENERIC = {"docs", "doc", "documentation", "documentacao", "documentação", "src", "assets", "images", "img",
           "static", "notes", "notas", "misc", "general", "geral", "examples", "exemplos", "templates", "modelos",
           "archive", "arquivo", "old", "drafts", "rascunhos", "stacks", "shared", "common", "wiki", "pages",
           "content", "conteudo", "conteúdo", "home", "outros", "others", "tmp", "temp", "backup", "vendor"}


@dataclass
class Suggestion:
    key: str               # fonte|escopo|tipo (estável, usado para aceitar/ignorar)
    source: str
    scope: str             # pasta ("regras/") ou arquivo ("x/y.md")
    kind: str              # id de um tipo existente, ou "new"
    count: int
    total: int
    why: str
    examples: list[str] = field(default_factory=list)
    label: str = ""        # nome proposto para a aba (tipo novo)

    @property
    def is_folder(self) -> bool:
        return self.scope.endswith("/")

    @property
    def glob(self) -> str:
        return self.scope + "*" if self.is_folder else self.scope

    def text(self) -> str:
        where = f"a pasta {self.scope}" if self.is_folder else self.scope
        if self.kind == "new":
            return f"{where} tem {self.count} documentos sem tipo: criar a aba “{self.label}”?"
        k = kinds.get(self.kind)
        qty = f"{self.count} de {self.total} documentos" if self.is_folder else "o documento"
        return f"{where}: {qty} parecem {k.label} — {self.why}"


def _humanize(name: str) -> str:
    s = re.sub(r"[-_]+", " ", indexer.ORDER_PREFIX_RE.sub("", name)).strip()
    return (s[:1].upper() + s[1:])[:30] if s else name


def _known_dir(name: str) -> bool:
    return any(name in k.dirs for k in kinds.BUILTIN)


def for_source(src: config.Source, store: Store) -> list[Suggestion]:
    docs = store.list(kind="doc", source=src.name)
    by_folder: dict[str, list] = defaultdict(list)
    for d in docs:
        parent = str(PurePosixPath(d.path).parent)
        by_folder["" if parent == "." else parent].append(d)
    out: list[Suggestion] = []
    dismissed = set(src.dismissed)
    for folder, items in sorted(by_folder.items()):
        guesses = [(d, d.extra["suggest"]) for d in items if d.extra.get("suggest")]
        votes = Counter(g["kind"] for _, g in guesses)
        best = votes.most_common(1)[0] if votes else None
        covered = set()
        if folder and best and best[1] >= FOLDER_MIN and best[1] / len(items) >= FOLDER_SHARE:
            kid = best[0]
            hits = [(d, g) for d, g in guesses if g["kind"] == kid]
            why = Counter(g["why"].split(" (")[0] for _, g in hits).most_common(1)[0][0]
            out.append(Suggestion(f"{src.name}|{folder}/|{kid}", src.name, folder + "/", kid, len(hits), len(items),
                                  why, [d.title for d, _ in hits[:3]]))
            covered = {d.uid for d, _ in hits}
        for d, g in guesses:  # arquivos soltos com sinal forte
            if d.uid not in covered and g["score"] >= STRONG:
                out.append(Suggestion(f"{src.name}|{d.path}|{g['kind']}", src.name, d.path, g["kind"], 1, 1,
                                      g["why"], [d.title]))
                covered.add(d.uid)
        name = indexer.ORDER_PREFIX_RE.sub("", PurePosixPath(folder).name.lower()) if folder else ""
        rest = [d for d in items if d.uid not in covered]
        if (folder and not covered and len(rest) >= NEW_TYPE_MIN and name not in GENERIC and not _known_dir(name)
                and re.fullmatch(r"[a-zà-ú][a-zà-ú0-9 _-]{2,40}", name)):
            out.append(Suggestion(f"{src.name}|{folder}/|new", src.name, folder + "/", "new", len(rest), len(items),
                                  "pasta própria, sem um tipo reconhecido", [d.title for d in rest[:3]],
                                  label=_humanize(PurePosixPath(folder).name)))
    return [s for s in out if s.key not in dismissed]


def suggestions(cfg: config.Config, store: Store) -> list[Suggestion]:
    out = []
    for s in cfg.enabled_sources:
        out += for_source(s, store)
    # mais documentos primeiro; tipos existentes antes de abas novas
    return sorted(out, key=lambda s: (s.kind == "new", -s.count, s.source, s.scope))


def find(cfg: config.Config, store: Store, key: str) -> Suggestion:
    for s in suggestions(cfg, store):
        if s.key == key:
            return s
    raise config.ConfigError(f"sugestão não encontrada: {key}")


def _new_type_id(src: config.Source, label: str) -> str:
    base = indexer.slugify(label)[:24].strip("-") or "tipo"
    if not re.match(r"^[a-z]", base):
        base = ("t-" + base)[:24]
    taken = set(kinds.BUILTIN_IDS) | set(src.types)
    kid, i = base, 2
    while kid in taken or len(kid) < 2:
        kid = f"{base[:21]}-{i}"
        i += 1
    return kid


def accept(cfg: config.Config, s: Suggestion, label: str | None = None) -> str:
    """Grava a regra na fonte (config.toml). Retorna o id do tipo. Quem chama reindexa a fonte."""
    src = cfg.require(s.source)
    kid = s.kind
    if kid == "new":
        name = (label or s.label).strip()
        if not name:
            raise config.ConfigError("dê um nome para a aba")
        kid = _new_type_id(src, name)
        src.types[kid] = {"label": name[:30], "description": f"Criado no Solarhub a partir de {s.scope}"}
    globs = src.kinds.setdefault(kid, [])
    if s.glob not in globs:
        globs.append(s.glob)
    return kid


def dismiss(cfg: config.Config, s: Suggestion) -> None:
    src = cfg.require(s.source)
    if s.key not in src.dismissed:
        src.dismissed.append(s.key)


@dataclass
class Rule:
    source: str
    kind: str
    glob: str
    label: str

    def text(self) -> str:
        return f"{self.glob} → {self.label} ({self.source})"


def rules(cfg: config.Config, store: Store | None = None) -> list[Rule]:
    out = []
    for s in cfg.sources:
        for kid, globs in s.kinds.items():
            label = (s.types.get(kid) or {}).get("label") or kinds.get(kid, store).label
            out += [Rule(s.name, kid, g, label) for g in globs]
    return out


def undo(cfg: config.Config, source: str, kind: str, glob: str) -> None:
    src = cfg.require(source)
    globs = [g for g in src.kinds.get(kind, []) if g != glob]
    if globs:
        src.kinds[kind] = globs
    else:
        src.kinds.pop(kind, None)
        src.types.pop(kind, None)  # aba criada por você some junto com a última regra
