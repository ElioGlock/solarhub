#!/usr/bin/env bash
# Remove do computador tudo o que o Solarhub criou: links de skills, MCP, timer, atalho, comando,
# blocos no ~/.profile, a pasta ~/solarhub e o ambiente .venv deste clone.
#   ./uninstall.sh              # remove tudo (pede confirmação)
#   ./uninstall.sh --keep-data  # mantém ~/solarhub (configuração, clones e índice)
#   ./uninstall.sh --yes        # sem confirmação
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$root/.venv/bin/solarhub" ]; then "$root/.venv/bin/solarhub" uninstall "$@"
elif command -v solarhub >/dev/null; then solarhub uninstall "$@"
else echo "comando solarhub não encontrado; nada a desfazer no sistema"; fi
if command -v uv >/dev/null && uv tool list 2>/dev/null | grep -q '^solarhub '; then uv tool uninstall solarhub; fi
rm -rf "$root/.venv"
echo "✓ Solarhub removido. Sobrou só esta pasta com o código: $root (apague se quiser)"
