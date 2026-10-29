"""Repositórios fora do padrão: tipo pelo cabeçalho do arquivo, pelo conteúdo (sugestão) e regras aceitas."""
import subprocess

from conftest import commit, git, write

from solarhub import actions, config, detect, indexer, kinds, suggest, sync
from solarhub.store import Store

ADR = "# Usar Postgres\n\n## Contexto\n\nPrecisamos de transações.\n\n## Decisão\n\nPostgres.\n\n## Consequências\n\nOperar backups.\n"
RULE = "# Segredos\n\nNUNCA commitar segredos. É proibido logar tokens. MUST usar o cofre. MUST NOT expor chaves.\n"
AP = "# Classe Deus\n\n## Sintomas\n\nUma classe faz tudo.\n\n## Como corrigir\n\nQuebre por responsabilidade.\n"


def test_detect_by_content():
    assert detect.detect("Usar Postgres", ADR)[0] == "adr"
    assert detect.detect("Segredos", RULE)[0] == "guardrail"
    assert detect.detect("Classe Deus", AP)[0] == "antipattern"
    assert detect.detect("Moment", "# Moment\n\n- Anel: Evitar\n")[0] == "radar"
    assert detect.detect("Novo serviço", "# X\n\n## Passo 1\n\na\n\n## Passo 2\n\nb\n\n## Passo 3\n\nc\n")[0] == "playbook"
    assert detect.detect("Logs", "# Logs\n\n## Faça\n\nx\n\n## Não faça\n\ny\n")[0] == "guideline"
    assert detect.detect("C4", "# Containers\n\n```mermaid\nC4Container\n```\n")[0] == "diagram"
    assert detect.detect("Mapa", "Pagamentos é upstream de Pedidos; bounded context com shared kernel.")[0] == "context-map"
    assert detect.detect("Review", "Revise {{arquivo}} contra {{guia}}.")[0] == "prompt"
    # não inventa
    assert detect.detect("Leia-me", "# Projeto\n\n## Documentação\n\nComo rodar.\n\n## Evite\n\nnada\n") is None
    assert detect.detect("Notas", "# Reunião\n\nFalamos de prazos. Devemos entregar.\n") is None



def _repo(tmp_path):
    repo = tmp_path / "remote" / "conhecimento"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    for i in range(3):
        write(repo, f"regras-seguranca/regra-{i}.md", RULE.replace("Segredos", f"Regra {i}"))
        write(repo, f"time/onboarding/passo-{i}.md", f"# Passo {i}\n\nTexto de onboarding suficiente.\n")
    write(repo, "registros-tecnicos/banco.md", ADR)
    write(repo, "registros-tecnicos/fila.md", ADR.replace("Postgres", "RabbitMQ"))
    write(repo, "solto/limite.md", "---\ntype: guardrail\n---\n# Limite de payload\n\nAté 1 MB.\n")
    write(repo, "solto/outro.md", "---\ntype: architecture\n---\n# Visão geral\n\nTexto.\n")
    commit(repo, "inicial")
    return repo


def test_nonstandard_repo_flow(tmp_path):
    repo = _repo(tmp_path)
    actions.add_source(repo.as_uri())
    with Store() as st:
        assert st.get("conhecimento:solto/limite.md").kind == "guardrail"  # front matter
        assert st.get("conhecimento:solto/outro.md").kind == "doc"  # "architecture" não é tipo: ignora
        assert st.get("conhecimento:regras-seguranca/regra-0.md").kind == "doc"  # nada muda sozinho
        items = {s.scope: s for s in suggest.suggestions(config.load(), st)}
    assert items["regras-seguranca/"].kind == "guardrail" and items["regras-seguranca/"].count == 3
    assert items["registros-tecnicos/"].kind == "adr"
    assert items["time/onboarding/"].kind == "new" and items["time/onboarding/"].label == "Onboarding"

    actions.accept_suggestion(items["regras-seguranca/"].key)
    actions.accept_suggestion(items["time/onboarding/"].key, "Onboarding do time")
    actions.dismiss_suggestion(items["registros-tecnicos/"].key)
    with Store() as st:
        assert st.get("conhecimento:regras-seguranca/regra-1.md").kind == "guardrail"
        present = {k.id: k for k, _ in kinds.present(st)}
        assert present["onboarding-do-time"].local and present["onboarding-do-time"].label == "Onboarding do time"
        assert st.count(kind="onboarding-do-time") == 3
        assert suggest.suggestions(config.load(), st) == []  # aceitas e ignoradas somem
    # o repositório não foi tocado
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout == ""

    rules = suggest.rules(config.load())
    r = next(r for r in rules if r.kind == "onboarding-do-time")
    actions.undo_rule(r.source, r.kind, r.glob)
    with Store() as st:
        assert "onboarding-do-time" not in {k.id for k, _ in kinds.present(st)}
        assert st.get("conhecimento:time/onboarding/passo-0.md").kind == "doc"
    assert "onboarding-do-time" not in config.load().get("conhecimento").types
