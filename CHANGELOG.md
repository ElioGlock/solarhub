# Changelog

Todas as mudanças relevantes do Solarhub. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto usa [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.4.0] — 2026-10-29

### Adicionado
- **Abas por tipo de artefato** no Explorar, montadas a partir do que existe nas fontes: Instruções, Prompts,
  Tech Radar, Guardrails, Fitness Functions, Playbooks, Diagramas e Mapa de Contextos, além de Skills, ADRs,
  Guidelines, Antipatterns e Docs. Uma aba só aparece quando há documentos daquele tipo.
- **Tipos próprios por repositório** (`[types.<id>]` no `solarhub.toml`), com nome da aba, pastas e instrução para a IA.
- **Tipos sugeridos**: o Solarhub lê o conteúdo do que caiu em Docs (seções de ADR, regras MUST/NUNCA, anel do radar,
  passos de playbook…) e propõe abas. Nada muda sem aprovação; a regra fica só no seu Solarhub e pode ser desfeita.
  Também em `solarhub suggest`.
- `type: guardrail` (ou `kind:`/`tipo:`) no front matter define o tipo de um arquivo.
- MCP: ferramenta `solar_kinds`; `solar_check_antipatterns` também confere guardrails; instruções do agente listam os
  tipos da base e como usar cada um.
- `solarhub kinds` lista os tipos com quantidade e uso pela IA.
- ADRs com escopo por stack (`ADR-mobile-0001`, `ADR-backend-0002`) e pastas numeradas (`03-adrs/`).
- `SECURITY.md`, `CONTRIBUTING.md`, modelos de issue e PR, Dependabot e CodeQL.
- **Executáveis que se atualizam sozinhos**: AppImage (Linux) e `.zip` (Windows) com nomes fixos para baixar
  direto da página de Releases. O app avisa quando há versão nova ("Atualizar para vX") e troca sozinho, conferindo o
  SHA-256 do arquivo. Também `solarhub update` e `solarhub config check_updates false` para desligar.
- `scripts/release.py X.Y.Z --push`: lança uma versão em um comando (versão, changelog, tag; o GitHub faz o resto).
- Instalação recomendada sem clonar: `uv tool install "solarhub[app] @ git+https://github.com/ElioGlock/solarhub"`;
  o app faz o setup na primeira vez e indica `uv tool upgrade solarhub` quando há versão nova.

### Alterado
- Desinstalação remove tudo o que o Solarhub criou, inclusive `~/solarhub` e o `.venv` do clone (`--keep-data` mantém o hub).
- Classificação: formato do arquivo > pasta mais próxima > palavra no nome. `docs/adr/0002-guardrails-no-ci.md` é ADR,
  e `guidelines/guardrail-guidelines.md` é guideline.
- Atualizar o Solarhub reindexa as fontes sozinho no próximo sync, sem gerar "novidades" falsas.

### Corrigido
- "Claude Code detectado" no Windows sem a ferramenta instalada (detecção agora exige sinal real).
- Testes no Windows: leitura de configs em UTF-8 com BOM/cp1252, remoção de `.git` somente leitura, nomes com acento.

## 0.3.0 — 2026-10-18

### Adicionado
- Suporte a **Windows**: `app.cmd`, Agendador de Tarefas, junctions para skills, notificações e executável `.zip`.
- **AppImage** para Linux e pipeline de release no GitHub Actions.
- Novidades por sync (ADR novo, mudança de status), notificações e tela Atividade.
- Perfis por projeto (`.solarhub.toml`), busca por significado opcional, propostas de ADR por PR, uso do agente,
  `solarhub lint`, ícone na bandeja, checagem barata com `git ls-remote`.
- Fontes em `.zip` (exports de Confluence/Notion) com HTML e PDF.
- Variações da mesma origem em outra branch indexam só as diferenças.

## 0.2.0 — 2026-10-18

### Adicionado
- App de desktop nativo (Qt), instalação com `source app`.
- Servidor MCP, publicação de skills por symlink, sincronização automática (systemd) e CLI.

[0.4.0]: https://github.com/ElioGlock/solarhub/releases/tag/v0.4.0
