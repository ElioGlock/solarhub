"""Tipos de artefato (abas): embutidos, critérios de reconhecimento e tipos declarados pelo repositório."""
from conftest import commit, git, write

from solarhub import config, indexer, kinds, lint, resolver, sync
from solarhub.store import Store

c = indexer.classify


def test_builtin_kinds_by_folder_and_name():
    assert c("docs/05-guardrails/sem-segredos.md") == "guardrail"
    assert c("docs/05-guardrails/semgrep.yml") == "guardrail"  # config aceita só em pasta de guardrail
    assert c("src/app.py") is None and c("docs/x.yml") is None
    assert c("fitness-functions/test_dependencias.py") == "fitness"
    assert c("playbooks/novo-servico/README.md") == "playbook"  # README de um playbook é o playbook
    assert c("playbooks/README.md") == "doc"  # README da coleção é índice
    assert c("guidelines/templates/x.md") == "doc" and c("guardrails/template.md") == "doc"
    assert c("tech-radar/react-query.md") == "radar"
    assert c(".github/prompts/revisao.prompt.md") == "prompt"
    assert c("AGENTS.md") == "instruction" and c(".github/instructions/py.instructions.md") == "instruction"
    assert c(".cursor/rules/estilo.mdc") == "instruction"
    assert c("diagrams/containers.puml") == "diagram" and c("arquitetura/c4-contexto.mmd") == "diagram"
    assert c("docs/mapa-de-contextos/pagamentos.md") == "context-map"
    assert c("guidelines/antipatterns/x.md") == "antipattern"  # a pasta mais próxima decide
    assert c("adrs/guardrails/x.md") == "guardrail"
    assert c("onboarding/x.md") == "doc"  # pasta desconhecida não vira tipo


def _repo(tmp_path, toml: str = ""):
    repo = tmp_path / "remote" / "arch"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    if toml:
        write(repo, "solarhub.toml", toml)
    write(repo, "tech-radar/moment.md", "# Moment.js\n\n- Anel: Evitar\n\nUse date-fns.\n")
    write(repo, "guardrails/sem-segredos.md", "# Sem segredos no código\n\nMUST usar parâmetros.\n")
    write(repo, "runbooks/fila-parada.md", "# Fila parada\n\n1. Ver o consumidor\n")
    for i in range(3):
        write(repo, f"onboarding/passo-{i}.md", f"# Passo {i}\n\nTexto suficiente para não ser vazio.\n")
    commit(repo, "inicial")
    return repo


RUNBOOK = """
[types.runbook]
label = "Runbooks"
folders = ["runbooks"]
description = "Procedimentos de operação passo a passo"
agent = "Em incidentes, siga o runbook do serviço"
"""


def test_radar_and_custom_type(tmp_path):
    repo = _repo(tmp_path, RUNBOOK)
    docs = {d.path: d for d in indexer.index_source("arch", repo)}
    assert (docs["tech-radar/moment.md"].kind, docs["tech-radar/moment.md"].status) == ("radar", "hold")
    assert docs["runbooks/fila-parada.md"].kind == "runbook"
    cfg = config.load()
    cfg.add(config.Source(name="arch", url=repo.as_uri()))
    with Store() as st:
        sync.sync_all(cfg, st, relink=False)
        present = {k.id: (k, n) for k, n in kinds.present(st)}
        assert set(present) == {"radar", "guardrail", "runbook", "doc"}  # só tipos com documentos
        rb, n = present["runbook"]
        assert (rb.label, rb.custom, rb.source, n) == ("Runbooks", True, "arch", 1)
        assert kinds.resolve_name("runbooks", st) == "runbook"
        assert kinds.resolve_name("Fitness Functions", st) == "fitness"
        doc, _ = resolver.resolve(st, "runbook:fila-parada")
        assert doc and doc.kind == "runbook"
        doc, _ = resolver.resolve(st, "guardrail:sem-segredos")
        assert doc and doc.kind == "guardrail"
        # tipo some quando o repositório deixa de declarar
        write(repo, "solarhub.toml", "")
        commit(repo, "tira tipo")
        sync.sync_all(cfg, st, relink=False)
        assert "runbook" not in {k.id for k, _ in kinds.present(st)}
        assert st.get("arch:runbooks/fila-parada.md").kind == "doc"


def test_custom_type_validation():
    ok, problems = kinds.parse_custom({
        "runbook": {"label": "Runbooks", "folders": ["runbooks"], "description": "x"},
        "adr": {"label": "Outros ADRs", "folders": ["x"]},
        "Bad Id": {"label": "X", "folders": ["x"]},
        "semlabel": {"folders": ["x"]},
        "semdesc": {"label": "Sem desc", "folders": ["y"]},
    })
    assert [k.id for k in ok] == ["runbook", "semdesc"]
    text = " ".join(problems)
    assert "'adr' já existe" in text and "Bad Id" in text and "sem label" in text and "sem description" in text


def test_lint_suggests_but_never_creates(tmp_path):
    repo = _repo(tmp_path)  # sem [types]: runbooks/ e onboarding/ ficam como doc
    issues = lint.lint_path(repo, "arch")
    infos = {i.path for i in issues if i.level == "info"}
    assert "onboarding/" in infos  # 3 documentos numa pasta sem tipo -> sugestão
    assert "runbooks/" not in infos  # só 1 documento: não sugere
    assert all(i.level == "info" for i in issues if i.path.endswith("/"))


def test_folder_beats_word_in_name():
    # pasta do tipo vence palavra solta no nome (repositório real: docs/adr/0002-guardrails-no-ci.md)
    assert c("docs/adr/0002-guardrails-no-ci.md") == "adr"
    assert c("docs/guidelines/anti-pattern-guidelines.md") == "guideline"
    assert c("docs/guidelines/tech-radar-guidelines.md") == "guideline"
    assert c("docs/best-practices/0001-x.md") == "guideline"
    assert c("notas/guardrail-sql.md") == "guardrail"  # sem pasta de tipo, a palavra ainda vale
    assert c("notas/guardrail-template.md") == "doc"
    assert c("docs/adr/fluxo.puml") == "diagram"  # formato vence a pasta
    assert c("docs/guidelines/revisao.prompt.md") == "prompt"


def test_templates_and_indexes_never_suggested(tmp_path):
    from conftest import write as w

    w(tmp_path, "docs/x/template.md", "# T\n\n## Contexto\n\n## Decisão\n\n## Consequências\n\n- Status: x\n")
    w(tmp_path, "docs/x/README.md", "# Índice\n\n## Contexto\n\n## Decisão\n\n## Consequências\n")
    docs = indexer.index_source("s", tmp_path)
    assert all("suggest" not in d.extra for d in docs)
