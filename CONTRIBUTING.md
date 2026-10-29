# Como contribuir

Obrigado pelo interesse! Issues, ideias e PRs são bem-vindos.

## Antes de começar

- **Primeira contribuição?** Procure issues com o rótulo `good first issue`.
- **Dúvidas e ideias abertas:** use as Discussions; issues ficam para bugs e propostas concretas.

- **Bug:** abra uma issue com o modelo "Bug" (versão, sistema, o que esperava e o que aconteceu, saída do `solarhub doctor`).
- **Ideia ou mudança grande:** abra uma issue "Sugestão" antes do PR, para alinharmos o caminho.
- **Novo tipo de artefato:** explique como ele muda o que a IA faz ao escrever código. Os critérios estão no topo de
  [`src/solarhub/kinds.py`](src/solarhub/kinds.py).

## Ambiente

```bash
git clone https://github.com/ElioGlock/solarhub && cd solarhub
source app --install                  # cria .venv/ com o app (Windows: .\app.cmd --install)
.venv/bin/pip install -e ".[app,dev]"
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

Os testes não usam rede: criam repositórios Git temporários. A CI roda em Linux e Windows, Python 3.10 e 3.12.

## Mapa do código

| Onde | O quê |
|---|---|
| `src/solarhub/sync.py`, `git.py` | clonar, atualizar e decidir o que reindexar |
| `src/solarhub/indexer.py`, `kinds.py`, `detect.py` | reconhecer tipos (pasta, nome, cabeçalho, conteúdo) |
| `src/solarhub/store.py`, `search.py`, `resolver.py` | índice SQLite/FTS5, busca e referências (`adr:14`) |
| `src/solarhub/mcp_server.py`, `linker.py`, `clients.py` | entrega aos agentes: MCP, skills, configuração das ferramentas |
| `src/solarhub/desktop/` | app Qt |
| `src/solarhub/cli.py` | comandos `solarhub …` |

Decisões de arquitetura: [ARCHITECTURE.md](ARCHITECTURE.md).

## Pull requests

- Um assunto por PR, com teste para o que mudou.
- `pytest` passando em Linux e, se tocar em caminhos, links ou agendador, pense no Windows (`osutil.py`).
- Texto de interface em português claro, sem jargão; mensagens de erro dizem o que fazer.
- Anote a mudança em `## [Não lançado]` no `CHANGELOG.md`. Versões são lançadas com
  `python scripts/release.py X.Y.Z --push` (veja o [guia](docs/guia.md#atualizações-e-versões)).
