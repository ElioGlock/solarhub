"""Classifica e extrai metadados dos arquivos de uma fonte.

Tolerante por design: ADRs e guias têm formato livre; extraímos o que der
(id, status, título) e o agente lê o corpo para o resto.
"""
from __future__ import annotations

import fnmatch
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Iterator

import yaml

from solarhub.formats import RICH_EXT, html_to_markdown, pdf_to_text
from solarhub import detect
from solarhub import kinds as kinds_mod
from solarhub.models import Document

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

OVERRIDE_FILE = "solarhub.toml"
# Muda quando a classificação/extração muda: o próximo sync reindexa tudo (sem gerar "novidades").
VERSION = "5"
SKILL_FILE = "SKILL.md"
TEXT_EXT = {".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea", ".vscode", ".tox"}
MAX_BYTES = 512 * 1024

ORDER_PREFIX_RE = re.compile(r"^\d+[-_. ]+")  # "03-adrs" -> "adrs" (pastas numeradas para ordenar)
# ID de ADR, com escopo opcional: ADR-014 · ADR 14 · ADR-mobile-0001 · ADR_backend_0002 · ADR-front-end-0003
ADR_SCOPE = r"[A-Za-z][A-Za-z0-9+#]*(?:[-_][A-Za-z][A-Za-z0-9+#]*)*"
ADR_REF = rf"ADR(?:[-_](?P<scope>{ADR_SCOPE})[-_]|[-_ ]?)0*(?P<num>\d{{1,5}})"
ADR_REF_RE = re.compile(rf"\b{ADR_REF}\b", re.I)
ADR_KEY_RE = re.compile(rf"^(?:ADR[-_ ]?)?(?:(?P<scope>{ADR_SCOPE})[-_ ])?0*(?P<num>\d{{1,5}})$", re.I)
ADR_FILE_RE = re.compile(rf"^adr(?:[-_]{ADR_SCOPE}[-_]|[-_ ]?)\d+", re.I)
# Arquivos que vivem na pasta de um tipo mas não são daquele tipo: índices e modelos
INDEX_RE = re.compile(r"^(?:readme|index|_index|indice|índice|sumario|sumário|toc|summary|changelog|contributing)$", re.I)
TEMPLATE_RE = re.compile(r"templat|modelo|exemplo|example|sample", re.I)
NOT_ADR_RE = re.compile(rf"{INDEX_RE.pattern}|{TEMPLATE_RE.pattern}", re.I)
RING_LINE_RE = re.compile(r"^[ \t>*_|-]*(?:ring|anel|quadrante?|status)[*_]*[ \t]*[:：][ \t]*[*_]*[ \t]*(.+)$", re.I | re.M)
RING_ALIASES = {"adopt": "adopt", "adotar": "adopt", "adotado": "adopt", "trial": "trial", "experimentar": "trial",
                "assess": "assess", "avaliar": "assess", "hold": "hold", "evitar": "hold", "aguardar": "hold"}

FM_RE = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
H1_RE = re.compile(r"^#[ \t]+(.+?)[ \t#]*$", re.M)
LEADING_NUM_RE = re.compile(r"^0*(\d{1,5})(?=[-_ .])")
STATUS_LINE_RE = re.compile(r"^[ \t>*_|-]*(?:status|situação|situacao|estado)[*_]*[ \t]*[:：][ \t]*[*_]*[ \t]*(.+)$", re.I | re.M)
STATUS_HEADING_RE = re.compile(r"^#{1,6}[ \t]*(?:status|situação|situacao|estado)[ \t]*$\s*^[ \t>*_-]*(.+)$", re.I | re.M)
_ADR_TOKEN = rf"(ADR(?:[-_]{ADR_SCOPE}[-_]|[-_ ]?)\d+)"
SUPERSEDED_BY_RE = re.compile(rf"(?:superseded[ \t]+by|substitu[íi]d[oa][ \t]+(?:por|pelo|pela))[ \t:*_\[]*{_ADR_TOKEN}", re.I)
SUPERSEDES_RE = re.compile(rf"(?:\bsupersedes\b|\bsubstitui\b)[ \t:*_\[]*{_ADR_TOKEN}", re.I)
DATE_LINE_RE = re.compile(r"^[ \t>*_|-]*(?:data|date)[*_]*[ \t]*[:：][ \t]*[*_]*[ \t]*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})",
                          re.I | re.M)
SCOPE_LINE_RE = re.compile(r"^[ \t>*_|-]*(?:escopo|scope|stack)[*_]*[ \t]*[:：][ \t]*[*_]*[ \t]*([\w.+# -]{1,40})$",
                           re.I | re.M)

STATUS_ALIASES = {
    "accepted": "accepted", "approved": "accepted", "aceito": "accepted", "aceita": "accepted",
    "aprovado": "accepted", "aprovada": "accepted", "vigente": "accepted",
    "proposed": "proposed", "draft": "proposed", "proposto": "proposed", "proposta": "proposed",
    "rascunho": "proposed",
    "superseded": "superseded", "substituído": "superseded", "substituido": "superseded",
    "substituída": "superseded", "substituida": "superseded",
    "deprecated": "deprecated", "obsoleto": "deprecated", "obsoleta": "deprecated",
    "depreciado": "deprecated", "descontinuado": "deprecated",
    "rejected": "rejected", "rejeitado": "rejected", "rejeitada": "rejected",
}


# ---------------------------------------------------------------- helpers

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:80] or "doc"


def adr_id(number: int | str, scope: str | None = None) -> str:
    """ID canônico: ADR-014 ou, com escopo, ADR-mobile-0001 (cada stack tem a sua numeração)."""
    n = int(number)
    return f"ADR-{scope.lower()}-{n:04d}" if scope else f"ADR-{n:03d}"


def parse_adr_ref(text: str | None) -> tuple[str | None, int] | None:
    """Primeiro ID de ADR no texto -> (escopo, número). "ADR-mobile-0001: X" -> ("mobile", 1)."""
    m = ADR_REF_RE.search(text or "")
    return ((m.group("scope") or "").lower() or None, int(m.group("num"))) if m else None


def parse_adr_key(text: str | None) -> tuple[str | None, int] | None:
    """Referência digitada pelo usuário: 14 · ADR-014 · mobile-1 · ADR-mobile-0001."""
    m = ADR_KEY_RE.match((text or "").strip())
    return ((m.group("scope") or "").lower() or None, int(m.group("num"))) if m else None


def _adr_ref_id(text) -> str | None:
    r = parse_adr_ref(str(text))
    if r:
        return adr_id(r[1], r[0])
    m = re.search(r"\d+", str(text))
    return adr_id(m.group(0)) if m else None


def normalize_status(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip().strip("*_`[]()").lower()
    words = [w.strip("*_`[]()") for w in re.split(r"[\s,;.:(|]+", s)]
    first = next((w for w in words if w), "")
    if not first:
        return None
    return STATUS_ALIASES.get(first, first[:30])


def split_frontmatter(raw: str) -> tuple[dict, str]:
    m = FM_RE.match(raw)
    if not m:
        return {}, raw
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    return (data if isinstance(data, dict) else {}), raw[m.end():]


def _tags(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = re.split(r"[,;]", value)
    return [str(t).strip() for t in value if str(t).strip()][:20]


def _humanize(stem: str) -> str:
    s = re.sub(r"^\d+[-_ ]+", "", stem)
    s = re.sub(r"[-_]+", " ", s).strip()
    return s[:1].upper() + s[1:] if s else stem


# ---------------------------------------------------------------- overrides

class Overrides:
    """`solarhub.toml` opcional na raiz da fonte:

        ignore = ["drafts/**"]
        [kinds]                          # caminhos -> tipo (embutido ou declarado abaixo)
        adr = ["decisoes/**"]
        guardrail = ["seguranca/obrigatorio/**"]
        [types.runbook]                  # tipo próprio do repositório (vira aba se tiver documentos)
        label = "Runbooks"
        folders = ["runbooks"]
        description = "Procedimentos de operação passo a passo"
        agent = "Em incidentes, siga o runbook do serviço"
    """

    def __init__(self, data: dict | None = None, source: str | None = None, local: dict | None = None):
        data = data or {}
        local = local or {}
        self.types, self.problems = kinds_mod.parse_custom(data.get("types") or {}, source)
        # regras criadas por você no Solarhub (Tipos sugeridos): valem por cima das do repositório
        repo_ids = {k.id for k in self.types}
        mine, _ = kinds_mod.parse_custom({k: v for k, v in (local.get("types") or {}).items() if k not in repo_ids},
                                         source, local=True)
        self.types += mine
        valid = set(kinds_mod.BUILTIN_IDS) | {k.id for k in self.types}
        self.kinds = {}
        for k, v in (local.get("kinds") or {}).items():
            if k in valid and isinstance(v, list):
                self.kinds[k] = list(v)
        for k, v in (data.get("kinds") or {}).items():
            if k in valid and isinstance(v, list):
                self.kinds.setdefault(k, [])
                self.kinds[k] += [p for p in v if p not in self.kinds[k]]
            else:
                self.problems.append(f"[kinds] {k}: tipo desconhecido (declare em [types.{k}] ou use um embutido)")
        self.ignore = list(data.get("ignore") or [])
        self.custom_dirs = {d: k.id for k in self.types for d in k.dirs}

    @classmethod
    def load(cls, root: Path, source: str | None = None) -> "Overrides":
        f = root / OVERRIDE_FILE
        local = _local_rules(source)
        try:
            return cls(tomllib.loads(f.read_text("utf-8")), source, local)
        except OSError:
            return cls(None, source, local)
        except tomllib.TOMLDecodeError as e:
            o = cls(None, source, local)
            o.problems.append(f"solarhub.toml inválido, ignorado: {e}")
            return o

    def ignored(self, rel: str) -> bool:
        return any(fnmatch.fnmatch(rel, p) for p in self.ignore)

    def kind_def(self, kind_id: str) -> kinds_mod.Kind:
        return next((k for k in self.types if k.id == kind_id), None) or kinds_mod.get(kind_id)

    def kind_for(self, rel: str) -> str | None:
        for kind, patterns in self.kinds.items():
            if any(fnmatch.fnmatch(rel, p) for p in patterns):
                return kind
        return None


def _local_rules(source: str | None) -> dict:
    """Regras de tipo que o usuário aceitou no Solarhub para esta fonte (config.toml)."""
    if not source:
        return {}
    try:
        from solarhub import config  # noqa: PLC0415 - evita import circular

        src = config.load().get(source)
    except Exception:  # noqa: BLE001 - config ilegível não pode impedir a indexação
        return {}
    return {"kinds": dict(src.kinds), "types": dict(src.types)} if src else {}


# ---------------------------------------------------------------- classify

_DIR_KIND = {d: k.id for k in kinds_mod.BUILTIN for d in k.dirs}
_FORMAT_KIND = [(re.compile(pat, re.I), k.id) for k in kinds_mod.BUILTIN for pat in k.formats]
_WORD_KIND = [(re.compile(pat, re.I), k.id) for k in kinds_mod.BUILTIN for pat in k.files]


def _guess(rel: str, overrides: Overrides) -> str:
    """Tipo do arquivo, do sinal mais forte ao mais fraco:
    formato do nome (ADR-014-x.md, *.prompt.md, *.puml) > pasta mais próxima de um tipo > palavra no nome
    (guardrail-guidelines.md dentro de guidelines/ é guideline, não guardrail)."""
    p = PurePosixPath(rel)
    name = p.name.lower()
    stem = ORDER_PREFIX_RE.sub("", p.stem.lower())
    if ADR_FILE_RE.match(name):
        return "doc" if NOT_ADR_RE.search(p.stem) else "adr"
    for k in overrides.types:  # padrões de nome declarados pelo repositório
        if any(re.search(pat, name, re.I) for pat in k.files):
            return k.id
    for rx, kid in _FORMAT_KIND:
        if rx.search(name):
            return kid
    parts = p.parent.parts
    for depth in range(len(parts) - 1, -1, -1):  # a pasta mais próxima do arquivo decide
        seg = ORDER_PREFIX_RE.sub("", parts[depth].lower())
        kid = overrides.custom_dirs.get(seg) or _DIR_KIND.get(seg)
        if not kid:
            continue
        if TEMPLATE_RE.search(stem) or any(TEMPLATE_RE.search(s) for s in parts[depth + 1:]):
            return "doc"
        # README/índice direto na pasta do tipo descreve a coleção; ADR nunca é um README
        if INDEX_RE.match(stem) and (depth == len(parts) - 1 or kid == "adr"):
            return "doc"
        return kid
    if not TEMPLATE_RE.search(stem):
        for rx, kid in _WORD_KIND:
            if rx.search(name):
                return kid
    return "doc"


def classify(rel: str, overrides: Overrides | None = None) -> str | None:
    overrides = overrides or Overrides()
    p = PurePosixPath(rel)
    if rel == OVERRIDE_FILE or overrides.ignored(rel):
        return None
    if p.name == SKILL_FILE:
        return "skill"
    ext = p.suffix.lower()
    kind = overrides.kind_for(rel) or _guess(rel, overrides)
    if ext in TEXT_EXT | RICH_EXT:
        return kind
    # código/config/diagrama só entra na pasta de um tipo que aceita (ex.: regras de lint em guardrails/)
    return kind if kind != "doc" and ext in overrides.kind_def(kind).exts else None


def inside_skill(root: Path, rel: str) -> bool:
    """Arquivo auxiliar de uma skill (a pasta inteira é linkada; só o SKILL.md é indexado)."""
    p = PurePosixPath(rel)
    if p.name == SKILL_FILE:
        return False
    parent = p.parent
    while True:
        if (root / parent / SKILL_FILE).is_file():
            return True
        if parent == parent.parent or str(parent) in ("", "."):
            return False
        parent = parent.parent


def iter_files(root: Path) -> Iterator[Path]:
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = sorted(d.iterdir())
        except OSError:
            continue
        if (d / SKILL_FILE).is_file():
            yield d / SKILL_FILE
            continue
        for e in entries:
            if e.is_symlink():  # nunca seguir links para fora do repositório
                continue
            if e.is_dir():
                if e.name not in SKIP_DIRS:
                    stack.append(e)
            elif e.is_file():
                yield e


# ---------------------------------------------------------------- parse

def parse_document(root: Path, rel: str, source: str, kind: str, commit: str | None = None,
                   overrides: Overrides | None = None) -> Document | None:
    f = root / rel
    suffix = PurePosixPath(rel).suffix.lower()
    rich_title = ""
    if suffix == ".pdf":
        res = pdf_to_text(f)
        if not res or not res[1].strip():
            return None
        rich_title, raw = res
    else:
        try:
            if f.stat().st_size > MAX_BYTES:
                return None
            raw = f.read_text("utf-8", errors="replace")
        except OSError:
            return None
        if "\x00" in raw[:2048]:
            return None
        if suffix in (".html", ".htm"):
            rich_title, raw = html_to_markdown(raw)
            if not raw.strip():
                return None
    fm, body = split_frontmatter(raw)
    p = PurePosixPath(rel)
    tags = _tags(fm.get("tags"))
    if kind != "skill":  # "type: guardrail" no cabeçalho do arquivo vale mais que pasta e nome
        declared = next((fm[k] for k in ("type", "kind", "tipo") if isinstance(fm.get(k), str)), None)
        forced = kinds_mod.resolve_name(declared, extra=overrides.types if overrides else None) if declared else None
        if forced:
            kind = forced

    if kind == "skill":
        name = slugify(str(fm.get("name") or p.parent.name or source))
        desc = str(fm.get("description") or "").strip() or None
        return Document(source=source, path=rel, kind="skill", title=str(fm.get("title") or name), body=raw,
                        ref_id=name, description=desc, tags=tags, commit_sha=commit)

    h1 = H1_RE.search(body)
    title = str(fm.get("title") or rich_title or (h1.group(1).strip() if h1 else _humanize(p.stem)))[:200]
    head = body[:4000]
    extra: dict = {}
    status = normalize_status(fm.get("status"))

    if kind == "adr":
        ref_id = None
        for key in ("id", "adr", "number"):
            if fm.get(key) is not None:
                ref_id = _adr_ref_id(fm[key])
                if ref_id:
                    break
        for text in (p.name, title):
            if ref_id is None:
                r = parse_adr_ref(text)
                ref_id = adr_id(r[1], r[0]) if r else None
        if ref_id is None:
            m = LEADING_NUM_RE.match(p.name)
            ref_id = adr_id(m.group(1)) if m else slugify(p.stem)
        parsed = parse_adr_ref(ref_id)
        scope = (parsed[0] if parsed else None) or fm.get("scope") or fm.get("escopo")
        if not scope:
            m = SCOPE_LINE_RE.search(head)
            scope = m.group(1).strip() if m else None
        if scope:
            extra["scope"] = str(scope).strip().lower()
        if not status:
            m = STATUS_LINE_RE.search(head) or STATUS_HEADING_RE.search(head)
            status = normalize_status(m.group(1)) if m else None
        sb = fm.get("superseded_by") or fm.get("superseded-by")
        m = SUPERSEDED_BY_RE.search(head)
        if sb or m:
            target = _adr_ref_id(sb or m.group(1))
            if target:
                extra["superseded_by"] = target
                status = status if status not in (None, "accepted") else "superseded"
        sp = fm.get("supersedes")
        found = [sp] if isinstance(sp, (str, int)) else list(sp or [])
        found += SUPERSEDES_RE.findall(head)
        sup = []
        for item in found:
            target = _adr_ref_id(item)
            if target and target not in sup and target != ref_id:
                sup.append(target)
        if sup:
            extra["supersedes"] = sup
        if fm.get("date"):
            extra["date"] = str(fm.get("date"))
        else:
            m = DATE_LINE_RE.search(head)
            if m:
                extra["date"] = m.group(1)
    else:
        stem = re.sub(r"\.(prompt|instructions)$", "", p.stem, flags=re.I)  # revisao.prompt.md -> revisao
        if stem.lower() in ("readme", "index") and p.parent.name:
            stem = p.parent.name
        ref_id = slugify(fm.get("id") or stem)
        if fm.get("severity"):
            extra["severity"] = str(fm["severity"])
        if kind == "radar":  # anel do tech radar: adopt | trial | assess | hold
            raw_ring = str(fm.get("ring") or fm.get("anel") or fm.get("status") or "")
            if not raw_ring:
                m = RING_LINE_RE.search(head)
                raw_ring = m.group(1) if m else ""
            word = (re.findall(r"[\wçãáéíóú]+", raw_ring.lower()) or [""])[0]
            status = RING_ALIASES.get(word, status)
        elif not status:
            m = STATUS_LINE_RE.search(head)
            status = normalize_status(m.group(1)) if m and kind != "doc" else None

    plain_stem = ORDER_PREFIX_RE.sub("", p.stem.lower())
    if (kind == "doc" and suffix in TEXT_EXT | {".html", ".htm"} and not TEMPLATE_RE.search(plain_stem)
            and not INDEX_RE.match(plain_stem)):  # índices e modelos nunca viram sugestão
        guess = detect.detect(title, body, fm)
        if guess:
            extra["suggest"] = {"kind": guess[0], "score": guess[1], "why": guess[2]}
    return Document(source=source, path=rel, kind=kind, title=title, body=raw, ref_id=ref_id, status=status,
                    tags=tags, description=(str(fm["description"]).strip() if fm.get("description") else None),
                    commit_sha=commit, extra=extra)


def index_file(root: Path, rel: str, source: str, commit: str | None, overrides: Overrides) -> Document | None:
    kind = classify(rel, overrides)
    if kind is None or (kind != "skill" and inside_skill(root, rel)):
        return None
    return parse_document(root, rel, source, kind, commit, overrides)


def index_source(source: str, root: Path, commit: str | None = None) -> list[Document]:
    overrides = Overrides.load(root, source)
    docs = []
    for f in iter_files(root):
        rel = f.relative_to(root).as_posix()
        doc = index_file(root, rel, source, commit, overrides)
        if doc:
            docs.append(doc)
    return docs


def index_paths(source: str, root: Path, rels: list[str], commit: str | None = None) -> list[Document]:
    overrides = Overrides.load(root, source)
    docs = []
    for rel in rels:
        if (root / rel).is_file() and not (root / rel).is_symlink():
            doc = index_file(root, rel, source, commit, overrides)
            if doc:
                docs.append(doc)
    return docs
