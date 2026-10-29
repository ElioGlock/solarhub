"""Reconhece o tipo de um documento pelo conteúdo (para repositórios que não seguem convenção de nomes).

Nunca muda o tipo sozinho: o resultado vira uma *sugestão* (doc.extra["suggest"]) que o usuário aceita
ou ignora em "Tipos sugeridos" (app) ou `solarhub suggest` (terminal). Só roda em documentos que, pelo
caminho, cairiam em Docs.

Cada regra devolve uma pontuação: >= 1 é sugestão; >= 2 é sinal forte (sugere até para um arquivo só).
"""
from __future__ import annotations

import re
import unicodedata

HEAD_RE = re.compile(r"^[ \t]{0,3}(?:#{1,6}[ \t]+(.+?)[ \t#]*|\*\*(.+?)\*\*[ \t]*:?[ \t]*)$", re.M)
STATUS_RE = re.compile(r"^[ \t>*_|-]*(?:status|situa[çc][ãa]o|estado)[*_]*[ \t]*[:：]", re.I | re.M)
MUST_RE = re.compile(r"\b(?:MUST(?: NOT)?|SHALL(?: NOT)?|NEVER|NUNCA|PROIBIDO|OBRIGAT[ÓO]RIO)\b")
MUST_PT_RE = re.compile(r"\b(?:é proibido|não é permitido|é obrigatório|obrigatoriamente|is (?:not )?allowed|"
                        r"bloquead[oa] (?:na|no) (?:ci|pipeline|pr)|quebra o build|fails? the build)\b", re.I)
RING_RE = re.compile(r"^[ \t>*_|-]*(?:ring|anel)[*_]*[ \t]*[:：][ \t]*[*_]*[ \t]*(adopt|trial|assess|hold|adotar|"
                     r"experimentar|avaliar|evitar)\b", re.I | re.M)
STEP_HEAD_RE = re.compile(r"^(?:passo|etapa|step|fase|phase)\s*\d+", re.I)
CHECK_RE = re.compile(r"^[ \t]*[-*][ \t]+\[[ xX]\]", re.M)
FENCE_RE = re.compile(r"```[ \t]*(mermaid|plantuml|puml|structurizr|d2)\b|@startuml", re.I)
C4_RE = re.compile(r"\b(?:C4|System Context|Container Diagram|Component Diagram|Person\(|System\(|Container\()", re.I)
CONTEXT_TERMS = ("bounded context", "contexto delimitado", "subdominio", "subdomain", "upstream", "downstream",
                 "context map", "mapa de contexto", "anticorrup", "shared kernel", "customer/supplier")
PLACEHOLDER_RE = re.compile(r"\{\{\s*[\w.-]+\s*\}\}|\$\{input:[\w.-]+")
AI_INTRO_RE = re.compile(r"^\s*(?:você é (?:um|uma)|you are (?:an?|the) )", re.I | re.M)
INSTR_TITLE_RE = re.compile(r"instru[çc](?:õ|o)es|instructions|regras para (?:o |os )?agentes?|system prompt", re.I)
AP_TITLE_RE = re.compile(r"^(?:evite|n[ãa]o fa[çc]a|avoid|don'?t)\b|anti-?padr[ãa]o|anti-?pattern", re.I)

LABEL = {"adr": "ADR", "guardrail": "guardrail", "antipattern": "antipattern", "radar": "item do tech radar",
         "playbook": "playbook", "guideline": "guideline", "diagram": "diagrama", "context-map": "mapa de contexto",
         "instruction": "instrução para agentes", "prompt": "prompt", "fitness": "fitness function"}


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[*_`:]+", "", s).strip()


class _Head(str):
    """Título normalizado (sem acento, minúsculo) que lembra o texto original para mostrar ao usuário."""
    raw: str = ""

    def title(self) -> str:  # noqa: D102
        return self.raw


def _heads(body: str) -> list[_Head]:
    out = []
    for a, b in HEAD_RE.findall(body):
        h = _Head(_plain(a or b))
        h.raw = (a or b).strip(" *_:")
        out.append(h)
    return out


def _has(heads: list[str], *prefixes: str) -> str | None:
    for h in heads:
        for p in prefixes:
            if h == p or h.startswith(p + " ") or (len(p) >= 5 and h.startswith(p)):
                return h
    return None


def detect(title: str, body: str, fm: dict | None = None) -> tuple[str, float, str] | None:
    """-> (tipo, pontuação, motivo legível) ou None."""
    fm = fm or {}
    heads = _heads(body)
    text = body[:20000]
    scores: list[tuple[float, str, str]] = []

    dec = _has(heads, "decisao", "decision", "decisoes", "decisions")
    ctx = _has(heads, "contexto", "context", "problema", "problem", "motivacao", "motivation")
    con = _has(heads, "consequencias", "consequences", "impactos", "trade-offs", "tradeoffs")
    if dec and (ctx or con):
        found = [x for x in (ctx, dec, con) if x]
        s = 1.0 + 0.5 * (len(found) - 2) + (0.5 if STATUS_RE.search(text[:3000]) else 0) + (0.5 if len(found) == 3 else 0)
        scores.append((s, "adr", "tem as seções " + ", ".join(f"“{x.title()}”" for x in found)))

    must = MUST_RE.findall(text) + MUST_PT_RE.findall(text)
    if len(must) >= 3:
        words = sorted({m.strip().upper() for m in must})[:4]
        scores.append((len(must) / 3, "guardrail", f"{len(must)} regras obrigatórias ({', '.join(words)})"))

    sym = _has(heads, "sintoma", "symptom", "sinais", "signs", "como identificar", "how to spot")
    why = _has(heads, "por que e ruim", "por que e um problema", "why it", "why its bad", "problema", "problem",
               "consequencias", "consequences")
    fix = _has(heads, "solucao", "solution", "refatoracao", "refactoring", "como corrigir", "como evitar", "how to fix",
               "how to avoid", "alternativa", "alternative", "em vez disso", "instead")
    ap_title = bool(AP_TITLE_RE.search(title or ""))
    groups = [x for x in (sym, why, fix) if x]
    if (sym and len(groups) >= 2) or (ap_title and groups):
        scores.append((1.0 + 0.5 * (len(groups) - 2) + (0.5 if ap_title else 0), "antipattern",
                       "descreve " + " e ".join(g for g in ("sintomas" if sym else "", "o problema" if why else "",
                                                             "como corrigir" if fix else "") if g)))

    if RING_RE.search(text):
        scores.append((2.0, "radar", "tem o anel do radar (adotar/experimentar/avaliar/evitar)"))
    else:
        rings = [h for h in heads if h in ("adopt", "adotar", "trial", "experimentar", "assess", "avaliar", "hold", "evitar")]
        if len(set(rings)) >= 3:
            scores.append((1.5, "radar", "seções por anel: " + ", ".join(sorted(set(rings)))))

    steps = [h for h in heads if STEP_HEAD_RE.match(h)]
    checks = CHECK_RE.findall(text)
    if len(steps) >= 3 or len(checks) >= 5:
        why_pb = f"{len(steps)} passos" if len(steps) >= 3 else f"checklist com {len(checks)} itens"
        scores.append((1.0 + (0.5 if len(steps) >= 5 or len(checks) >= 8 else 0), "playbook", why_pb))

    do = _has(heads, "faca", "do", "recomendado", "recommended", "use", "prefira", "prefer", "boas praticas")
    dont = _has(heads, "nao faca", "dont", "don't", "evite", "avoid", "nao use", "nao recomendado")
    if (do and dont and do != dont) or ("✅" in text and "❌" in text):
        scores.append((1.0, "guideline", "separa o que fazer e o que não fazer"))

    if FENCE_RE.search(text):
        prose = len(re.sub(r"```.*?```", "", text, flags=re.S).strip())
        if C4_RE.search(text) or prose < 300:
            scores.append((1.5 if C4_RE.search(text) else 1.0, "diagram", "é principalmente um diagrama (mermaid/PlantUML/C4)"))

    low = _plain(text)
    terms = sorted({t for t in CONTEXT_TERMS if t in low})
    if len(terms) >= 2:
        scores.append((len(terms) / 2, "context-map", "fala de " + ", ".join(terms[:3])))

    if str(fm.get("mode", "")).lower() in ("agent", "ask", "edit") or len(PLACEHOLDER_RE.findall(text)) >= 2:
        scores.append((1.5, "prompt", "é um prompt com variáveis/modo de execução"))
    elif INSTR_TITLE_RE.search(title or "") or AI_INTRO_RE.search(text[:600]):
        scores.append((1.0, "instruction", "é escrito como instrução para um agente de IA"))

    if re.search(r"fitness[ -]functions?", low) and "```" in text:
        scores.append((1.0, "fitness", "descreve uma fitness function com o código da verificação"))

    if not scores:
        return None
    s, kind, why = max(scores, key=lambda x: x[0])
    return (kind, round(min(s, 3.0), 2), why) if s >= 1.0 else None
