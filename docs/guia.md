# Guia do Solarhub

Referência completa. Para a visão geral e a instalação rápida, veja o [README](../README.md).

- [Instalação no Windows](#windows)
- [AppImage (Linux, sem clonar)](#sem-clonar-appimage-linux)
- [O app](#o-app)
- [Atualizações e versões](#atualizações-e-versões)
- [Comandos](#comandos)
- [Referências no prompt](#referências-que-você-pode-usar-no-prompt)
- [Como o conteúdo é reconhecido](#como-o-conteúdo-é-reconhecido)
- [Recursos](#recursos)
- [Servidor MCP](#servidor-mcp)

## Instalação

### Windows

Precisa do **Git** (`winget install Git.Git`). O Python não precisa: o `app.cmd` baixa um se faltar.

```powershell
git clone https://github.com/ElioGlock/solarhub
cd solarhub
.\app.cmd            # ou duplo clique no app.cmd
```

Na primeira vez ele prepara tudo (sem administrador) e abre o app. Depois: **Solarhub** no Menu Iniciar, `solarhub` em
terminais novos. `.\app.cmd --install` só instala/atualiza; `.\uninstall.cmd` remove tudo, inclusive `%USERPROFILE%\solarhub` (`--keep-data` mantém o hub).

| No Windows | Como funciona |
|---|---|
| Atualização automática | Agendador de Tarefas (tarefa `\Solarhub\Sync`, oculta, sem console; também roda no logon) |
| Skills nas ferramentas | symlink se o modo desenvolvedor estiver ligado; senão *junction* (não precisa de administrador) |
| Comando `solarhub` | `solarhub.cmd` em `%LOCALAPPDATA%\Solarhub\bin`, adicionado ao PATH do usuário |
| Atalho | Menu Iniciar (`Solarhub.lnk`) |
| MCP | mesmos clientes; o VS Code fica em `%APPDATA%\Code\User\mcp.json` |
| Notificações | notificação do Windows; ícone do sol na bandeja |

Sem clonar: cada release traz **`Solarhub-windows-x64.zip`**. Extraia numa pasta fixa (ex.:
`%LOCALAPPDATA%\Programs\Solarhub`) e abra o `Solarhub.exe`. Na versão em .zip (e no AppImage) a busca por significado
ainda não está disponível.

### Sem clonar: AppImage (Linux)

Cada versão publicada (tag `v*`) gera um **`Solarhub-x86_64.AppImage`** na página de Releases do GitHub:
um arquivo só, com Python, Qt e o Solarhub dentro. Baixe, dê permissão e abra:

```bash
chmod +x Solarhub-x86_64.AppImage
./Solarhub-x86_64.AppImage          # abre o app e cria o atalho no menu e o comando `solarhub`
```

Guarde o arquivo num lugar fixo (ex.: `~/Applications`): o MCP, o timer e o atalho apontam para ele. Se mudar de
lugar, abra uma vez pelo novo caminho e tudo é reapontado. Para gerar localmente: `packaging/appimage/build.sh`.

## O app

| Tela | O que faz |
|---|---|
| **Fontes** | adicionar/remover repositórios, sincronizar, ver erro de acesso e atividade |
| **Explorar** | busca (por texto e, se ligada, por significado) e filtro por tipo; documento renderizado, status do ADR, copia a referência, abre o arquivo |
| **Atividade** | novidades de cada sync (ADR novo, ADR que virou superseded, skill nova…) e o uso do agente: mais lidos, buscas sem resposta, nunca lidos |
| **Integrações** | pastas de skills, MCP por ferramenta, timer, recursos (notificações, busca por significado, propostas de ADR, bandeja), qualidade das fontes, diagnóstico |

Ícone na **bandeja**: abrir, sincronizar agora, ver a próxima verificação. Fechar a janela mantém o Solarhub na bandeja
(dá para desligar em Integrações).

Atalhos: `Ctrl+1..4` (telas), `Ctrl+F` (buscar), `Ctrl+R` (sincronizar tudo), `F5` (recarregar).

## Atualizações e versões

**Instalado com `uv tool`.** Atualize com `uv tool upgrade solarhub`; o app avisa quando sai versão nova. Para ficar numa versão, instale com `@vX.Y.Z` no fim da URL.

**Executáveis.** O AppImage e o `.zip` consultam as Releases do GitHub no máximo a cada 12 horas. Havendo versão
nova, aparece **Atualizar para vX** na barra de baixo do app (e um aviso na bandeja). O Solarhub baixa o arquivo,
confere o SHA-256 publicado junto e:

- **Linux:** troca o AppImage no mesmo lugar e reabre. O atalho, o MCP e a sincronização continuam apontando para ele.
- **Windows:** extrai a nova versão, fecha o app, troca a pasta (guardando a antiga até dar certo) e reabre. O servidor
  MCP aberto pelo editor é encerrado e o editor o reinicia na próxima consulta.

`solarhub update` faz o mesmo no terminal (`--check` só verifica). Para não consultar o GitHub:
`solarhub config check_updates false`. Quem instalou pelo código atualiza com `git pull` e `source app`.

**Para quem mantém (lançar uma versão).**

1. Trabalhe normalmente na `main`: cada push roda os testes no Linux e no Windows. Nada chega a quem usa ainda.
2. Anote o que mudou na seção `## [Não lançado]` do `CHANGELOG.md`.
3. Lance: `python scripts/release.py 0.5.0 --push`. O script ajusta a versão, fecha a seção do changelog, faz o
   commit e a tag e envia.
4. O GitHub Actions testa, gera o AppImage e o `.zip` com o SHA-256 de cada um e publica a Release com as notas do
   changelog. Em até 12 horas quem usa o app vê o botão de atualizar.

## Comandos

```bash
solarhub add https://github.com/acme/adrs          # vincula (clona + indexa + publica skills)
solarhub add git@github.com:acme/guias.git -b main --priority 10
solarhub add ~/notas/kb                            # pasta local, sem clone
solarhub add ~/Downloads/confluence-export.zip     # export do Confluence/Notion (HTML, Markdown, PDF)
solarhub list                                      # fontes e situação
solarhub sync                                      # fetch/ff-only, reindexa o que mudou, religa skills
solarhub search "paginação" --kind adr
solarhub get adr:14                                # imprime o documento (bom para pipe)
solarhub context "endpoint de pedidos" --adr 14 --skill api-standards | xclip -sel clip
solarhub install-mcp --detected                    # registra o MCP nos clientes detectados
solarhub link --targets copilot,claude --mode symlink
solarhub init-project .                            # bloco curto no AGENTS.md / copilot-instructions.md
solarhub timer enable --interval 5                  # a checagem é barata: dá para conferir a cada poucos minutos
solarhub changes --days 7                          # o que mudou nas fontes
solarhub usage                                     # o que o agente consultou, buscas sem resposta, nunca lidos
solarhub lint                                      # qualidade das fontes (ou: solarhub lint pasta/ na CI)
solarhub semantic on                               # busca por significado (baixa um modelo local de ~220 MB)
solarhub propose-adr -t "Usar Kafka" --context … --decision … --consequences …
solarhub init-project . --sources eng-guidelines,architecture-adrs   # perfil do projeto (.solarhub.toml)
solarhub config allow_proposals true               # configurações (sem argumentos lista todas)
solarhub doctor
solarhub app                                       # abre o app de desktop
```

## Referências que você pode usar no prompt

`adr:14` · `ADR-014` · `ADR-mobile-0001` · `adr:mobile-1` · `skill:api-standards` · `guideline:rest-naming` · `antipattern:god-object` ·
`doc:setup` · `<fonte>:<caminho/arquivo.md>`

## Como o conteúdo é reconhecido

Cada tipo de artefato vira uma aba no Explorar e um `kind` no MCP/CLI (`solarhub kinds` lista). A aba só aparece
quando há documentos daquele tipo. Um tipo só entra no Solarhub se (1) muda o que a IA faz ao escrever código,
(2) tem papel próprio e (3) é reconhecível por pasta/nome ou declarado pelo repositório. Por isso eventos (o
que motivou uma decisão), ferramentas e painéis de métricas ficam de fora: não são conhecimento estável para
consultar.

Sem configuração, por convenção (pastas numeradas como `05-guardrails/` também valem; a pasta mais próxima
do arquivo decide):

| Tipo (`kind`) | Detectado por | Como a IA usa |
|---|---|---|
| skill | pasta com `SKILL.md` (a pasta inteira é publicada) | carrega quando a tarefa bate |
| instruction | `AGENTS.md`, `CLAUDE.md`, `*.instructions.md`, `.mdc` do Cursor, `instructions/` | segue sempre |
| prompt | `*.prompt.md`, `prompts/` | usa quando pedido pelo nome |
| adr | `adr/`, `adrs/`, `decisions/`, `decisoes/` ou `ADR-NNN-*.md` / `ADR-<stack>-NNNN-*.md` | só vigentes valem |
| radar | `tech-radar/`, `radar/` (anel: adotar, experimentar, avaliar, evitar) | `hold` = não usar |
| guideline | `guidelines/`, `standards/`, `conventions/`, `rules/`, `padroes/`, `diretrizes/`, `guias/` | segue e cita |
| antipattern | `antipatterns/`, `anti-patterns/`, `antipadroes/` | confere antes de concluir |
| guardrail | `guardrails/`, `policies/`, `politicas/` (aceita também regras em `.yml`, `.json`, `.rego`…) | obrigatório |
| fitness | `fitness-functions/`, `architecture-tests/`, `archunit/` (aceita testes em código) | o código precisa passar |
| playbook | `playbooks/`, `cookbooks/` | segue do início ao fim |
| diagram | `diagrams/`, `diagramas/`, `c4/`, arquivos `.puml`, `.mmd`, `.dsl`, `.d2` | entende onde a mudança entra |
| context-map | `context-map/`, `bounded-contexts/`, `mapa-de-contextos/` | respeita fronteiras e donos |
| doc | qualquer outro `.md`, `.rst`, `.txt`, `.adoc`, `.html` e `.pdf` com texto | material de apoio |

`README`/`index` direto na pasta de um tipo e modelos (`template`, `modelo`, `exemplo`) ficam como doc.

### Repositórios fora do padrão de nomes

Nada muda sozinho, mas você não precisa conhecer as convenções:

1. **Cabeçalho do arquivo**: `type: guardrail` (ou `kind:`/`tipo:`) no front matter vale mais que pasta e nome.
   Valores que não são um tipo conhecido (ex.: `type: architecture`) são ignorados.
2. **Pelo conteúdo**: o Solarhub lê o que caiu em Docs e reconhece ADRs (seções Contexto/Decisão/Consequências),
   guardrails (MUST, NUNCA, proibido), antipatterns (Sintomas/Como corrigir), tech radar (anel), playbooks
   (passos/checklist), guidelines (Faça/Não faça), diagramas (mermaid/PlantUML/C4), mapas de contexto,
   prompts e instruções para agentes.
3. **Tipos sugeridos**: no Explorar aparece "O Solarhub achou N pastas que parecem tipos…". Para cada pasta você
   aceita (vira aba), ignora (não pergunta de novo) ou, se for algo sem tipo conhecido, dá um nome e cria uma
   aba nova. A regra fica só no seu Solarhub (`config.toml`), o repositório não muda, e dá para desfazer.
   No terminal: `solarhub suggest`, `solarhub suggest accept N [--label Nome]`, `solarhub suggest ignore N`,
   `solarhub suggest undo N`.

### Tipos próprios de um repositório

Para algo que não está na lista (ex.: runbooks), o repositório declara no `solarhub.toml` da raiz. Pastas
desconhecidas nunca viram aba sozinhas: o `solarhub lint` só sugere declarar quando uma pasta tem 3+ documentos
sem tipo.

```toml
[types.runbook]
label = "Runbooks"                      # nome da aba
folders = ["runbooks"]                  # nomes de pasta (ou files = ["regex do nome"])
description = "Procedimentos de operação passo a passo"
agent = "Em incidentes, siga o runbook do serviço"   # vai para as instruções do MCP

[kinds]                                  # caminhos -> tipo (embutido ou declarado)
guardrail = ["seguranca/obrigatorio/**"]
```

ADRs em formato livre: o número vem do front matter (`id:`), do nome do arquivo (`0014-...`, `ADR-014`,
`ADR-mobile-0001`) ou do título. Com escopo (`ADR-mobile-0001`, `ADR-backend-0001`) cada stack tem a sua numeração
e `adr:1` sem escopo mostra todos os "0001"; o status vem de `status:` no front matter, de uma linha `Status: Aceito` ou de uma seção `## Status`.
Termos em português (aceito, proposto, substituído, obsoleto, rejeitado) são reconhecidos.

Para outro layout, coloque um `solarhub.toml` na raiz do repositório de conhecimento:

```toml
ignore = ["rascunhos/**"]

[kinds]
adr = ["arquitetura/registros/**"]
guideline = ["docs/como-fazemos/**"]
```

## Recursos

**Novidades.** Cada sync registra o que mudou: documento novo, removido, alterado e **mudança de status** de ADR.
Aparece em Atividade, em `solarhub changes`, no `solar_changes` do agente e numa notificação do sistema quando o timer traz algo.

**Checagem barata.** Antes de baixar, o Solarhub pergunta ao remoto só o último commit de cada branch (`git ls-remote`).
Sem mudança, não há download: dá para usar intervalos de 1–5 minutos.

**Perfis por projeto.** Um `.solarhub.toml` na raiz do projeto define quais fontes valem ali; CLI e MCP respeitam
(o editor informa a pasta do projeto ao MCP; também dá para usar `SOLARHUB_PROJECT`). `--all` ignora o perfil.

```toml
sources = ["eng-guidelines", "time-pagamentos-*"]
exclude = ["rascunhos"]
```

As pastas de skills são globais (cada ferramenta lê `~/.copilot/skills` etc.); o perfil filtra o que o MCP devolve.

**Qualidade (`solarhub lint`).** ADR sem número ou status, número repetido, "substituído por" um ADR que não existe,
ADR que diz substituir outro que continua aceito, skill sem `description`, documento vazio, link relativo quebrado.
Na CI do repositório de conhecimento:

```yaml
- uses: actions/setup-python@v5
  with: { python-version: "3.12" }
- run: pip install "solarhub @ git+https://github.com/ElioGlock/solarhub" && solarhub lint .
```

**Busca por significado.** Opcional e local: `solarhub semantic on` (ou em Integrações) instala o `fastembed` e baixa
um modelo multilíngue (~220 MB, uma vez). A busca passa a combinar texto e significado.

**Propostas de ADR.** Com `solarhub config allow_proposals true`, o agente pode chamar `solar_propose_adr` quando nada
cobre uma decisão: o Solarhub segue o formato dos ADRs do repositório (pasta, numeração, template), cria a branch
num `git worktree` separado, envia e abre o PR com o `gh` (ou mostra o link de comparação). O clone gerenciado não é tocado.

**Uso do agente.** Toda consulta pelo MCP é registrada localmente: mais lidos, buscas sem resposta (lacunas na
documentação) e documentos que ninguém lê. Veja em Atividade ou `solarhub usage`.

## Servidor MCP

`solarhub mcp` (stdio). Ferramentas: `solar_search`, `solar_get`, `solar_get_adr`, `solar_list`, `solar_check_antipatterns`,
`solar_changes`, `solar_kinds`, `solar_status` e `solar_propose_adr` (a única que escreve, desligada por padrão); recurso
`solarhub://{kind}/{key}`. Configuração manual, se preferir:

```json
{ "servers": { "solarhub": { "type": "stdio", "command": "solarhub", "args": ["mcp"] } } }
```
