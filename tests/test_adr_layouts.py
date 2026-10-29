"""ADRs em pastas numeradas e com escopo por time (ex.: docs/03-adrs/times/mobile/ADR-mobile-0001-x.md)."""
from conftest import commit, git, write

from solarhub import config, indexer, resolver, sync
from solarhub.store import Store

MOBILE = """# ADR-mobile-0001: Navegação por rotas nomeadas

Metadados

- Status: proposed
- Data: 2026-10-01
- Escopo: mobile

## Contexto

As telas chamam umas às outras diretamente.
"""
BACKEND_2 = """# ADR-backend-0002: Logs estruturados com OpenTelemetry

- Status: accepted
- Data: 2026-09-10

Substitui ADR-backend-0001.
"""
BACKEND_1 = """# ADR-backend-0001: Logs em texto livre

- Status: superseded

Substituído por ADR-backend-0002.
"""


def test_classify_numbered_and_scoped():
    c = indexer.classify
    assert c("docs/03-adrs/times/mobile/ADR-mobile-0001-navegacao.md") == "adr"
    assert c("docs/03-adrs/times/backend/qualquer-nome.md") == "adr"  # pasta "03-adrs"
    assert c("docs/03-adrs/README.md") == "doc"
    assert c("docs/03-adrs/times/mobile/README.md") == "doc"
    assert c("docs/03-adrs/template.md") == "doc"
    assert c("docs/03-adrs/ADR-0000-template.md") == "doc"
    assert c("notas/ADR-backend-0003-filas.md") == "adr"  # nome já diz que é ADR
    assert c("docs/04-guidelines/x.md") == "guideline"
    assert c("docs/05-antipatterns/x.md") == "antipattern"
    assert c("docs/adr-guide-notes.md") == "doc"
    assert c("docs/2024-adrs-notes.md") == "doc"


def test_scoped_ids():
    assert indexer.parse_adr_ref("ADR-mobile-0001: X") == ("mobile", 1)
    assert indexer.parse_adr_ref("ADR-014") == (None, 14)
    assert indexer.parse_adr_ref("ADR 14") == (None, 14)
    assert indexer.parse_adr_ref("adr_front-end_0003") == ("front-end", 3)
    assert indexer.parse_adr_ref("ADR de 2025") is None
    assert indexer.adr_id(1, "Mobile") == "ADR-mobile-0001"
    assert indexer.parse_adr_key("mobile-1") == ("mobile", 1)
    assert indexer.parse_adr_key("12") == (None, 12)


def _repo(tmp_path):
    repo = tmp_path / "remote" / "padroes"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    write(repo, "docs/03-adrs/README.md", "# ADRs\n\nÍndice das decisões por time.\n")
    write(repo, "docs/03-adrs/times/mobile/ADR-mobile-0001-navegacao.md", MOBILE)
    write(repo, "docs/03-adrs/times/backend/ADR-backend-0001-logs-texto.md", BACKEND_1)
    write(repo, "docs/03-adrs/times/backend/ADR-backend-0002-logs-estruturados.md", BACKEND_2)
    commit(repo, "inicial")
    return repo


def test_parse_scoped_adrs(tmp_path):
    docs = {d.path: d for d in indexer.index_source("p", _repo(tmp_path))}
    f = docs["docs/03-adrs/times/mobile/ADR-mobile-0001-navegacao.md"]
    assert (f.kind, f.ref_id, f.status) == ("adr", "ADR-mobile-0001", "proposed")
    assert f.extra["scope"] == "mobile" and f.extra["date"] == "2026-10-01"
    b1 = docs["docs/03-adrs/times/backend/ADR-backend-0001-logs-texto.md"]
    b2 = docs["docs/03-adrs/times/backend/ADR-backend-0002-logs-estruturados.md"]
    assert (b1.status, b1.extra["superseded_by"]) == ("superseded", "ADR-backend-0002")
    assert b2.extra["supersedes"] == ["ADR-backend-0001"]
    assert docs["docs/03-adrs/README.md"].kind == "doc"


def test_resolve_scoped(tmp_path):
    repo = _repo(tmp_path)
    cfg = config.load()
    cfg.add(config.Source(name="p", url=repo.as_uri()))
    with Store() as st:
        sync.sync_all(cfg, st, relink=False)
        for ref in ("ADR-mobile-0001", "adr:mobile-1", "adr:ADR-MOBILE-1", "mobile-0001"):
            doc, _ = resolver.resolve(st, ref if not ref.startswith("mobile") else "adr:" + ref)
            assert doc and doc.ref_id == "ADR-mobile-0001", ref
        doc, others = resolver.resolve(st, "adr:1")  # sem escopo: os dois "0001"
        assert {doc.ref_id, *[o.ref_id for o in others]} == {"ADR-mobile-0001", "ADR-backend-0001"}


def test_upgrade_reindexes_quietly(tmp_path):
    repo = _repo(tmp_path)
    cfg = config.load()
    cfg.add(config.Source(name="p", url=repo.as_uri()))
    with Store() as st:
        sync.sync_all(cfg, st, relink=False)
        st.conn.execute("UPDATE documents SET kind = 'doc'")  # índice de uma versão antiga
        st.conn.commit()
        st.meta_set("indexer:p", "1")
        n_changes = len(st.conn.execute("SELECT * FROM changes").fetchall())
        results, _ = sync.sync_all(cfg, st, relink=False)
        assert results[0].ok
        assert len(st.list(kind="adr")) == 3
        assert len(st.conn.execute("SELECT * FROM changes").fetchall()) == n_changes  # nada de "novidades"
        assert st.meta_get("indexer:p") == indexer.VERSION
