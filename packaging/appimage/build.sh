#!/usr/bin/env bash
# Gera dist/Solarhub-<versão>-<arch>.AppImage: Python portátil + Solarhub + Qt num arquivo só.
#
#   packaging/appimage/build.sh            # Python 3.12
#   PYVER=3.13 packaging/appimage/build.sh
#
# Usa o Python portátil do python-build-standalone (via uv) e o appimagetool.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYVER="${PYVER:-3.12}"
ARCH="${ARCH:-x86_64}"
WORK="${WORK:-$ROOT/build/appimage}"
OUT="$ROOT/dist"
VERSION="$(sed -n 's/^version *= *"\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)"

say() { printf '\033[1;33m→\033[0m %s\n' "$*"; }

if ! command -v uv >/dev/null 2>&1; then
  say "instalando uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
  export PATH="$HOME/.local/bin:$PATH"
fi

rm -rf "$WORK"
mkdir -p "$WORK/AppDir/opt" "$OUT"
cd "$WORK"

say "Python $PYVER portátil"
uv python install --quiet --install-dir "$WORK/py" "$PYVER"
PYHOME="$(find "$WORK/py" -maxdepth 1 -mindepth 1 -type d -name "cpython-$PYVER*" | head -1)"
cp -a "$PYHOME" AppDir/opt/python
PY="AppDir/opt/python/bin/python3"

say "Solarhub $VERSION + Qt"
uv pip install --quiet --python "$PY" --break-system-packages --no-cache "$ROOT[app]"

say "atalho, ícone e AppRun"
cp "$ROOT/src/solarhub/desktop/solarhub.svg" AppDir/solarhub.svg
cp AppDir/solarhub.svg AppDir/.DirIcon
cat > AppDir/solarhub.desktop <<DESKTOP
[Desktop Entry]
Type=Application
Name=Solarhub
Comment=Skills, ADRs, guidelines e antipatterns sincronizados para agentes de IA
Exec=solarhub app
Icon=solarhub
Terminal=false
Categories=Development;Utility;
X-AppImage-Version=$VERSION
DESKTOP
cat > AppDir/AppRun <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/opt/python/bin/python3" -I -m solarhub "$@"
APPRUN
chmod +x AppDir/AppRun

say "empacotando"
curl -fsSL -o appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
chmod +x appimagetool
ARCH="$ARCH" ./appimagetool --appimage-extract-and-run --no-appstream AppDir "$OUT/Solarhub-$VERSION-$ARCH.AppImage" >/dev/null 2>&1
printf '\033[1;32m✓\033[0m %s (%s)\n' "$OUT/Solarhub-$VERSION-$ARCH.AppImage" "$(du -h "$OUT/Solarhub-$VERSION-$ARCH.AppImage" | cut -f1)"
