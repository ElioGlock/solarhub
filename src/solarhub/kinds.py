"""Tipos de artefato que o Solarhub organiza: são as abas do Explorar e os `kind` do MCP/CLI.

Um tipo só existe se passar nos três critérios (não criamos aba para qualquer pasta):

1. Muda o que a IA faz ao escrever código: registra uma decisão, diz o que fazer ou não fazer, impõe uma
   regra, explica como algo é verificado, guia um passo a passo ou ensina uma tarefa. Ficam de fora
   eventos (o que motivou uma decisão), ferramentas e painéis de métricas: não são conhecimento estável
   para consultar.
2. Tem um papel próprio, que nenhum outro tipo cobre (runbook ≈ playbook não vira tipo novo).
3. É reconhecível no repositório por convenção de pasta/nome, ou o próprio repositório declara o tipo
   no `solarhub.toml` ([types.<id>]). Nome de pasta desconhecido nunca vira aba sozinho: o `solarhub lint`
   só sugere declarar.

E a aba só aparece quando existe pelo menos 1 documento daquele tipo nas fontes.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

# grupos dos tipos, na ordem das abas (do que a IA usa direto até a referência geral)
LAYERS = ("agente", "decisão", "boas práticas", "obrigatório", "verificação", "passo a passo", "estrutura",
          "repositório", "referência")

CODE_EXT = frozenset({".py", ".ts", ".tsx", ".js", ".mjs", ".java", ".kt", ".cs", ".go", ".rb", ".rs", ".php",
                      ".sh", ".ps1", ".yaml", ".yml", ".json", ".toml", ".rego", ".xml", ".editorconfig"})
DIAGRAM_EXT = frozenset({".puml", ".plantuml", ".mmd", ".mermaid", ".dsl", ".d2"})
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,23}$")
MAX_CUSTOM = 10


@dataclass(frozen=True)
class Kind:
    id: str
    label: str            # plural (texto da aba)
    singular: str
    layer: str
    description: str      # o que é (tooltip da aba)
    agent: str = ""       # como a IA deve usar (instruções do MCP e da skill solarhub)
    dirs: frozenset = field(default_factory=frozenset)   # nomes de pasta (sem o prefixo "02-")
    files: tuple = ()     # regex de palavra no nome do arquivo (fraco: a pasta do tipo vence)
    formats: tuple = ()   # regex de formato do arquivo (forte: vence a pasta), ex.: *.prompt.md, *.puml
    exts: frozenset = field(default_factory=frozenset)   # extensões aceitas além de .md/.txt/.html/.pdf…
    gender: str = "o"     # para frases: "guardrail novo", "guideline nova"
    custom: bool = False
    source: str | None = None  # fonte onde o tipo foi declarado (tipos próprios)
    local: bool = False        # criado pelo usuário no Solarhub (não está no repositório)


def _d(*names: str) -> frozenset:
    return frozenset(names)


BUILTIN: tuple[Kind, ...] = (
    Kind("skill", "Skills", "skill", "agente",
         "Pasta com SKILL.md: um passo a passo que o agente carrega sozinho quando a tarefa pede.",
         "Use a skill quando a tarefa bater com a descrição dela.", gender="a"),
    Kind("instruction", "Instruções", "instrução", "agente",
         "Regras permanentes para agentes de IA: AGENTS.md, CLAUDE.md, *.instructions.md, regras do Cursor.",
         "Valem para toda tarefa no escopo delas; siga sempre.",
         dirs=_d("instructions", "instrucoes", "instruções", "agent-instructions"),
         formats=(r"\.instructions\.md$", r"^(agents|claude|gemini|copilot-instructions)\.md$", r"\.mdc$"),
         exts=_d(".mdc"), gender="a"),
    Kind("prompt", "Prompts", "prompt", "agente",
         "Prompts reutilizáveis da equipe (*.prompt.md, pasta prompts/).",
         "Quando o usuário pedir um prompt da equipe pelo nome, leia e siga.",
         dirs=_d("prompts", "prompt-library", "prompt-templates"), formats=(r"\.prompt\.md$",)),
    Kind("adr", "ADRs", "ADR", "decisão",
         "Decisões de arquitetura registradas com contexto, alternativas e consequências. Superseded/deprecated "
         "não valem.",
         "Consulte antes de decidir arquitetura/API; só ADRs vigentes valem.",
         dirs=_d("adr", "adrs", "decisions", "decision-records", "architecture-decisions",
                 "architecture-decision-records", "decisoes", "decisões")),
    Kind("radar", "Tech Radar", "item do radar", "decisão",
         "Tecnologias e bibliotecas por anel: adotar, experimentar, avaliar, evitar.",
         "Antes de escolher biblioteca/ferramenta, confira o anel: 'hold/evitar' não deve ser usado.",
         dirs=_d("tech-radar", "techradar", "radar", "technology-radar", "radar-tecnologico", "radar-tecnológico"),
         files=(r"tech[-_ ]?radar",)),
    Kind("guideline", "Guidelines", "guideline", "boas práticas",
         "Como o time escreve código: convenções e boas práticas a seguir.",
         "Siga ao escrever código; cite a guideline usada.",
         dirs=_d("guidelines", "guideline", "standards", "conventions", "rules", "regras", "padroes", "padrões",
                 "diretrizes", "boas-praticas", "boas-práticas", "best-practices", "best-practice", "practices", "praticas",
                 "práticas", "guides", "guias"), gender="a"),
    Kind("antipattern", "Antipatterns", "antipattern", "boas práticas",
         "Padrões a evitar: o \"não faça\" da equipe.",
         "Antes de concluir, confira se a mudança cai em algum antipattern.",
         dirs=_d("antipatterns", "anti-patterns", "anti_patterns", "antipattern", "antipadroes", "antipadrões",
                 "anti-padroes", "anti-padrões"), files=(r"anti-?pattern",)),
    Kind("guardrail", "Guardrails", "guardrail", "obrigatório",
         "Regras obrigatórias (MUST), em geral checadas automaticamente: políticas, regras de lint, bloqueios na CI.",
         "Obrigatórios: nunca gere código que viole um guardrail; se precisar, explique e pare.",
         dirs=_d("guardrails", "guardrail", "guard-rails", "guard_rails", "salvaguardas", "policies", "politicas",
                 "políticas"), files=(r"guard[-_ ]?rails?",), exts=CODE_EXT),
    Kind("fitness", "Fitness Functions", "fitness function", "verificação",
         "Verificações automáticas da arquitetura (testes de arquitetura, checks na CI).",
         "Mostram como a regra é verificada: o código gerado precisa passar nelas.",
         dirs=_d("fitness-functions", "fitness-function", "fitness", "architecture-tests", "arch-tests", "archunit",
                 "testes-de-arquitetura"), files=(r"fitness[-_ ]?functions?",), exts=CODE_EXT, gender="a"),
    Kind("playbook", "Playbooks", "playbook", "passo a passo",
         "Roteiro passo a passo para um tipo de trabalho (ex.: criar um serviço), com as regras que se aplicam.",
         "Para um tipo de trabalho com playbook (ex.: novo serviço), siga o playbook do início ao fim.",
         dirs=_d("playbooks", "playbook", "cookbooks", "cookbook"), files=(r"playbook",)),
    Kind("diagram", "Diagramas", "diagrama", "estrutura",
         "Desenho do sistema (C4: contexto, containers, componentes).",
         "Use para entender onde a mudança se encaixa e não cruzar fronteiras sem motivo.",
         dirs=_d("diagrams", "diagramas", "diagram", "c4", "c4-model", "structurizr"),
         formats=(r"\.(puml|plantuml|mmd|mermaid|dsl|d2)$",), exts=DIAGRAM_EXT),
    Kind("context-map", "Mapa de Contextos", "mapa de contexto", "estrutura",
         "Domínios do sistema, suas fronteiras e o time responsável por cada um (bounded contexts).",
         "Respeite as fronteiras e o dono de cada contexto ao mexer em código de outro time.",
         dirs=_d("context-map", "context-maps", "contexts", "bounded-contexts", "mapa-de-contextos", "contextos"),
         files=(r"context[-_ ]?maps?", r"mapa[-_ ]de[-_ ]contextos?")),
    Kind("doc", "Docs", "documento", "referência",
         "Qualquer outra documentação (.md, .rst, .txt, .adoc, .html, .pdf).",
         "Material de apoio; não é regra."),
)
BUILTIN_IDS = tuple(k.id for k in BUILTIN)
_BY_ID = {k.id: k for k in BUILTIN}


def builtin(kind_id: str) -> Kind | None:
    return _BY_ID.get(kind_id)


# ---------------------------------------------------------------- tipos declarados pelo repositório

def parse_custom(data: dict, source: str | None = None, local: bool = False) -> tuple[list[Kind], list[str]]:
    """[types.<id>] do solarhub.toml (ou criados no Solarhub, local=True) -> (tipos válidos, problemas).
    Problemas viram aviso no `solarhub lint`."""
    out: list[Kind] = []
    problems: list[str] = []
    for kid, spec in (data or {}).items():
        if len(out) >= MAX_CUSTOM:
            problems.append(f"mais de {MAX_CUSTOM} tipos declarados; '{kid}' ignorado")
            continue
        if not isinstance(spec, dict):
            problems.append(f"[types.{kid}] precisa ser uma tabela")
            continue
        if not ID_RE.match(str(kid)):
            problems.append(f"tipo '{kid}': id deve ter 2-24 letras minúsculas, números ou '-'")
            continue
        if kid in _BY_ID:
            problems.append(f"tipo '{kid}' já existe no Solarhub; para mapear pastas use [kinds] {kid} = [...]")
            continue
        label = str(spec.get("label") or "").strip()
        folders = [str(f).strip().lower() for f in spec.get("folders") or [] if str(f).strip()]
        if not label:
            problems.append(f"tipo '{kid}' sem label (nome da aba)")
            continue
        if not folders and not spec.get("files") and not local:
            problems.append(f"tipo '{kid}' sem folders nem files: nada seria reconhecido (ou use [kinds])")
        if not str(spec.get("description") or "").strip():
            problems.append(f"tipo '{kid}' sem description: explique como ajuda a IA")
        files = []
        for pat in spec.get("files") or []:
            try:
                re.compile(str(pat))
                files.append(str(pat))
            except re.error:
                problems.append(f"tipo '{kid}': regex inválida em files: {pat}")
        out.append(Kind(str(kid), label[:30], str(spec.get("singular") or label).strip()[:30], "repositório",
                        str(spec.get("description") or "").strip()[:300], str(spec.get("agent") or "").strip()[:300],
                        dirs=frozenset(folders), files=tuple(files), custom=True, source=source, local=local))
    return out, problems


def dump(kinds: list[Kind]) -> str:
    return json.dumps([{**asdict(k), "dirs": sorted(k.dirs), "exts": sorted(k.exts), "files": list(k.files),
                        "formats": list(k.formats)}
                       for k in kinds], ensure_ascii=False)


def load(text: str | None) -> list[Kind]:
    try:
        rows = json.loads(text or "[]")
    except ValueError:
        return []
    return [Kind(**{**r, "dirs": frozenset(r.get("dirs", [])), "exts": frozenset(r.get("exts", [])),
                    "files": tuple(r.get("files", [])), "formats": tuple(r.get("formats", []))})
            for r in rows if isinstance(r, dict)]


# ---------------------------------------------------------------- registro (embutidos + declarados)

def registry(store=None) -> list[Kind]:
    """Todos os tipos conhecidos, na ordem das abas. Tipos declarados vêm do índice (gravados no sync)."""
    kinds = list(BUILTIN[:-1])
    seen = set(BUILTIN_IDS)
    if store is not None:
        for row in store.conn.execute("SELECT key, value FROM meta WHERE key LIKE 'types:%' ORDER BY key"):
            for k in load(row[1]):
                if k.id not in seen:
                    seen.add(k.id)
                    kinds.append(k)
    kinds.append(BUILTIN[-1])  # Docs por último
    return kinds


def get(kind_id: str | None, store=None) -> Kind:
    k = _BY_ID.get(kind_id or "")
    if k:
        return k
    for k in registry(store):
        if k.id == kind_id:
            return k
    kid = kind_id or "doc"
    return Kind(kid, kid.replace("-", " ").title(), kid.replace("-", " "), "repositório", "", custom=True)


def ids(store=None) -> list[str]:
    return [k.id for k in registry(store)]


def present(store, sources: list[str] | None = None) -> list[tuple[Kind, int]]:
    """Tipos que têm documentos (as abas a mostrar), com a contagem."""
    counts = store.counts_by_kind(sources=sources)
    known = registry(store)
    out = [(k, counts[k.id]) for k in known if counts.get(k.id)]
    known_ids = {k.id for k in known}
    out += [(get(kid), n) for kid, n in sorted(counts.items()) if kid not in known_ids and n]  # órfãos
    return out


def resolve_name(name: str | None, store=None, extra: list[Kind] | None = None) -> str | None:
    """'guardrails', 'Fitness Functions', 'adrs', 'tech radar' -> id. None se não reconhecer."""
    if not name:
        return None
    n = re.sub(r"[\s_]+", "-", str(name).strip().lower())
    for k in [*(extra or []), *registry(store)]:
        names = {k.id, k.id + "s", re.sub(r"\s+", "-", k.label.lower()), re.sub(r"\s+", "-", k.singular.lower())}
        if n in names or n.rstrip("s") == k.id:
            return k.id
    aliases = {"anti-pattern": "antipattern", "anti-patterns": "antipattern", "documentation": "doc",
               "docs": "doc", "tech-radar": "radar", "fitness-function": "fitness", "fitness-functions": "fitness",
               "diagrams": "diagram", "c4": "diagram", "contexts": "context-map", "instructions": "instruction"}
    return aliases.get(n)
