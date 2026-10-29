"""Pacote de contexto para colar em ferramentas sem MCP."""
from __future__ import annotations

from solarhub import resolver
from solarhub import search as search_mod
from solarhub.render import header
from solarhub.store import Store


def build(store: Store, task: str = "", refs: list[str] | None = None, priorities: dict | None = None,
          per_kind: int = 3, sources: list[str] | None = None) -> tuple[str, list[str]]:
    parts = ["# Contexto do Solarhub", ""]
    if task:
        parts += [f"Tarefa: {task}", ""]
    missing: list[str] = []
    seen: set[str] = set()
    for ref in refs or []:
        doc, _ = resolver.resolve(store, ref, priorities, sources)
        if not doc:
            missing.append(ref)
            continue
        seen.add(doc.uid)
        parts += [f"## {doc.title}", f"_{header(doc)}_", "", doc.body.strip(), ""]
    if task:
        for kind, label in (("guardrail", "Guardrails (obrigatórios)"), ("adr", "ADRs relacionados"),
                            ("guideline", "Guidelines relacionadas"), ("antipattern", "Antipatterns a evitar"),
                            ("playbook", "Playbooks"), ("radar", "Tech radar")):
            hits = [(d, s) for d, s in search_mod.search(store, task, kind=kind, limit=per_kind + len(seen), sources=sources) if d.uid not in seen]
            if hits:
                parts.append(f"## {label}")
                for d, s in hits[:per_kind]:
                    st = f" [{d.status}]" if d.status else ""
                    parts.append(f"- **{d.ref}** {d.title}{st} ({d.source}/{d.path}): {s}")
                parts.append("")
    parts.append("Regras: guardrails são obrigatórios; siga ADRs aceitos (ignore os substituídos) e as guidelines; evite os "
                 "antipatterns e o que o radar marca como hold; cite as referências usadas e diga quando nada cobrir o caso.")
    return "\n".join(parts).strip() + "\n", missing
