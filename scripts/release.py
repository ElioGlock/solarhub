#!/usr/bin/env python3
"""Publica uma versão nova do Solarhub.

    python scripts/release.py 0.5.0           # prepara: versão, changelog, commit e tag (só local)
    python scripts/release.py 0.5.0 --push    # e envia: o GitHub gera o AppImage e o .zip e publica a Release
    python scripts/release.py --notes 0.5.0   # imprime as notas da versão (usado pela automação)

Antes, escreva o que mudou na seção "## [Não lançado]" do CHANGELOG.md.
Quem usa o app recebe o aviso "Atualizar para v0.5.0" em até 12 horas.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "solarhub" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
REPO_URL = "https://github.com/ElioGlock/solarhub"
UNRELEASED = "## [Não lançado]"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class ReleaseError(RuntimeError):
    pass


def current_version(pyproject: str) -> str:
    m = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    if not m:
        raise ReleaseError("não achei a versão no pyproject.toml")
    return m.group(1)


def set_versions(pyproject: str, init: str, version: str) -> tuple[str, str]:
    return (re.sub(r'^version = "[^"]+"', f'version = "{version}"', pyproject, count=1, flags=re.M),
            re.sub(r'^__version__ = "[^"]+"', f'__version__ = "{version}"', init, count=1, flags=re.M))


def _section(text: str, heading_re: str) -> tuple[int, int] | None:
    m = re.search(heading_re, text, re.M)
    if not m:
        return None
    nxt = re.search(r"^## ", text[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(text)
    link = re.search(r"^\[[^\]]+\]: ", text[m.end():end], re.M)  # links de referência no fim do arquivo
    if link:
        end = m.end() + link.start()
    return m.start(), end


def notes(changelog: str, version: str) -> str:
    """Corpo da seção da versão (vira o texto da Release no GitHub e o que o app mostra)."""
    span = _section(changelog, rf"^## \[{re.escape(version)}\].*$")
    if not span:
        raise ReleaseError(f"o CHANGELOG.md não tem a seção [{version}]")
    body = changelog[span[0]:span[1]].split("\n", 1)[1] if "\n" in changelog[span[0]:span[1]] else ""
    return body.strip() + "\n"


def release_changelog(changelog: str, version: str, today: str) -> str:
    """Transforma "## [Não lançado]" em "## [x.y.z] — data" e abre uma seção vazia nova."""
    if re.search(rf"^## \[{re.escape(version)}\]", changelog, re.M):
        return changelog  # já preparado à mão
    span = _section(changelog, rf"^{re.escape(UNRELEASED)}\s*$")
    if not span:
        raise ReleaseError(f'o CHANGELOG.md precisa da seção "{UNRELEASED}" com o que mudou')
    body = changelog[span[0]:span[1]].split("\n", 1)[1].strip() if "\n" in changelog[span[0]:span[1]] else ""
    if not body:
        raise ReleaseError(f'a seção "{UNRELEASED}" do CHANGELOG.md está vazia: escreva o que mudou')
    new = f"{UNRELEASED}\n\n## [{version}] — {today}\n\n{body}\n\n"
    out = changelog[:span[0]] + new + changelog[span[1]:].lstrip("\n")
    link = f"[{version}]: {REPO_URL}/releases/tag/v{version}"
    if link not in out:
        out = out.rstrip("\n") + "\n" + link + "\n"
    return out


def git(*args: str, capture: bool = True) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=capture)
    if p.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)}: {(p.stderr or p.stdout or '').strip()}")
    return (p.stdout or "").strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", help="nova versão, ex.: 0.5.0")
    ap.add_argument("--push", action="store_true", help="envia o commit e a tag (dispara a publicação)")
    ap.add_argument("--notes", action="store_true", help="só imprime as notas dessa versão")
    a = ap.parse_args(argv)
    version = a.version.lstrip("vV")
    try:
        if a.notes:
            sys.stdout.write(notes(CHANGELOG.read_text("utf-8"), version))
            return 0
        if not SEMVER.match(version):
            raise ReleaseError("use o formato X.Y.Z, ex.: 0.5.0")
        if git("status", "--porcelain"):
            raise ReleaseError("há alterações sem commit; faça o commit antes de lançar a versão")
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        if branch != "main":
            raise ReleaseError(f"você está na branch {branch}; lance versões a partir da main")
        if git("tag", "--list", f"v{version}"):
            raise ReleaseError(f"a tag v{version} já existe")
        pyproject, init = PYPROJECT.read_text("utf-8"), INIT.read_text("utf-8")
        cur = current_version(pyproject)
        if tuple(map(int, version.split("."))) < tuple(map(int, re.findall(r"\d+", cur)[:3])):
            raise ReleaseError(f"{version} é menor que a versão atual ({cur})")
        changelog = release_changelog(CHANGELOG.read_text("utf-8"), version, date.today().isoformat())
        notes(changelog, version)  # garante que há o que publicar
        pyproject, init = set_versions(pyproject, init, version)
        PYPROJECT.write_text(pyproject, "utf-8")
        INIT.write_text(init, "utf-8")
        CHANGELOG.write_text(changelog, "utf-8")
        git("add", str(PYPROJECT), str(INIT), str(CHANGELOG))
        if git("status", "--porcelain"):
            git("commit", "-m", f"Solarhub {version}")
        git("tag", "-a", f"v{version}", "-m", f"Solarhub {version}")
    except ReleaseError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    print(f"✓ versão {version} preparada (commit + tag v{version})")
    if a.push:
        git("push", "origin", "main", capture=False)
        git("push", "origin", f"v{version}", capture=False)
        print(f"✓ enviado. Acompanhe a publicação em {REPO_URL}/actions")
    else:
        print(f"  para publicar: git push origin main && git push origin v{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
