# Segurança

## Versões com correção

| Versão | Recebe correções de segurança |
|---|---|
| 0.4.x | sim |
| < 0.4 | não, atualize pelo app ou com `solarhub update` |

## Como reportar uma vulnerabilidade

Não abra uma issue pública. Use o **reporte privado do GitHub**: aba **Security → Report a vulnerability**
neste repositório. Conte o que encontrou, como reproduzir e o impacto que imagina.

Você recebe uma resposta em até 7 dias. Corrigido o problema, a falha é publicada no changelog com crédito a
quem reportou (se quiser).

## O que o Solarhub faz no seu computador

O Solarhub é uma ferramenta local e de código aberto. Para avaliar o risco, vale saber exatamente o que ele toca:

- **Rede:** o `git` (clonar e atualizar os repositórios que você vinculou, com as suas credenciais); a consulta à
  API pública do GitHub, no máximo a cada 12 horas, para saber se há versão nova do Solarhub (desligue com
  `solarhub config check_updates false`); e, se você ligar a busca por significado, o download único de um modelo de
  embeddings. Não há telemetria, conta nem servidor do Solarhub.
- **Atualizações:** só são baixadas das Releases deste repositório e instaladas depois de conferir o SHA-256
  publicado junto. Se não conferir, nada é alterado.
- **Arquivos:** tudo o que ele cria fica listado em `~/solarhub/.state/manifest.json` e sai com `./uninstall.sh`
  (ou `uninstall.cmd`). Antes de editar um arquivo de configuração de outra ferramenta (ex.: `mcp.json` do VS Code),
  ele guarda uma cópia (`*.solarhub-bak-*`).
- **Agentes de IA:** o servidor MCP só lê o índice local. A única ferramenta que escreve (`solar_propose_adr`, que
  abre um PR) vem desligada e só funciona se você ligar.
- **Conteúdo dos repositórios:** é tratado como material de referência para o agente, nunca executado. Skills
  publicadas são pastas dos seus repositórios: revise skills de fontes em que você não confia, como faria com
  qualquer código de terceiros.
