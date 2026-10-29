"""Atualizações dos executáveis a partir das Releases do GitHub.

- AppImage (Linux): baixa o novo arquivo ao lado do atual e troca (o processo em uso continua com o antigo).
- .zip (Windows): baixa, extrai numa pasta temporária e um script troca a pasta quando o app fecha.
- `uv tool install` (o jeito recomendado): só avisa; atualiza com `uv tool upgrade solarhub`.
- Instalação pelo código (clone + `source app`): só avisa; atualiza com `git pull && source app`.

Todo download é conferido pelo SHA-256 publicado junto (`<arquivo>.sha256`). A verificação de versão
consulta a API pública do GitHub no máximo a cada 12 horas e pode ser desligada (`check_updates`).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from solarhub import __version__, osutil, paths, runtime

REPO = "ElioGlock/solarhub"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSETS = {"appimage": "Solarhub-x86_64.AppImage", "windows": "Solarhub-windows-x64.zip"}
CHECK_EVERY = timedelta(hours=12)
TIMEOUT = 8


class UpdateError(RuntimeError):
    pass


@dataclass
class Release:
    version: str
    tag: str
    notes: str = ""
    url: str = RELEASES_PAGE
    assets: dict = field(default_factory=dict)  # nome -> URL de download

    @property
    def newer(self) -> bool:
        return is_newer(self.version, __version__)


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", (v or "").lstrip("vV").split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def install_kind() -> str:
    """appimage | windows | uvtool (uv tool install) | source (clone/venv: atualiza com git pull)."""
    if runtime.appimage():
        return "appimage"
    if runtime.is_frozen() and osutil.IS_WINDOWS:
        return "windows"
    parts = [p.lower() for p in Path(sys.prefix).parts]
    if any(parts[i:i + 2] == ["uv", "tools"] for i in range(len(parts))):
        return "uvtool"
    return "source"


MANUAL = {
    "uvtool": "atualize com `uv tool upgrade solarhub`",
    "source": "instalado pelo código: atualize com `git pull` e `source app` (Windows: `.\\app.cmd`)",
}


def how_to_update() -> str | None:
    """Comando que a pessoa roda para atualizar (quando o Solarhub não se troca sozinho)."""
    return MANUAL.get(install_kind())


# ------------------------------------------------------------------ rede

def _open(url: str, timeout: int = TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": f"solarhub/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - só https do GitHub


def fetch_latest() -> Release:
    try:
        with _open(API_LATEST) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("ainda não há versão publicada nas Releases do GitHub") from e
        raise UpdateError(f"não consegui consultar as versões no GitHub (HTTP {e.code})") from e
    except Exception as e:  # noqa: BLE001
        raise UpdateError(f"não consegui consultar as versões no GitHub ({e})") from e
    tag = str(data.get("tag_name") or "")
    if not tag:
        raise UpdateError("o GitHub não informou a versão mais recente")
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets") or []
              if a.get("name") and a.get("browser_download_url")}
    return Release(tag.lstrip("vV"), tag, str(data.get("body") or ""), str(data.get("html_url") or RELEASES_PAGE), assets)


def _cache() -> Path:
    return paths.state_dir() / "update.json"


def check(force: bool = False, enabled: bool = True) -> Release | None:
    """Versão nova disponível, ou None. Sem `force`, consulta no máximo a cada 12 h e nunca levanta erro."""
    if not enabled and not force:
        return None
    now = datetime.now(timezone.utc)
    if not force:
        try:
            cached = json.loads(_cache().read_text("utf-8"))
            if now - datetime.fromisoformat(cached["checked_at"]) < CHECK_EVERY:
                rel = Release(**cached["release"]) if cached.get("release") else None
                return rel if rel and rel.newer else None
        except (OSError, ValueError, KeyError, TypeError):
            pass
    try:
        rel = fetch_latest()
    except UpdateError:
        if force:
            raise
        return None
    try:
        _cache().parent.mkdir(parents=True, exist_ok=True)
        _cache().write_text(json.dumps({"checked_at": now.isoformat(), "release": asdict(rel)}), "utf-8")
    except OSError:
        pass
    return rel if rel.newer else None


def download(url: str, dest: Path, progress: Callable[[int, int], None] | None = None) -> Path:
    try:
        with _open(url, timeout=60) as r, open(dest, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(1 << 16):
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise UpdateError(f"falha ao baixar {url.rsplit('/', 1)[-1]} ({e})") from e
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path, rel: Release, name: str) -> None:
    url = rel.assets.get(name + ".sha256")
    if not url:
        raise UpdateError(f"a versão {rel.version} não publicou o checksum de {name}; atualize pela página de Releases")
    tmp = path.with_name(path.name + ".sha256")
    download(url, tmp)
    expected = tmp.read_text("utf-8", errors="replace").split()[0].strip().lower() if tmp.stat().st_size else ""
    tmp.unlink(missing_ok=True)
    if sha256(path) != expected:
        path.unlink(missing_ok=True)
        raise UpdateError("o arquivo baixado não confere com o checksum publicado; nada foi alterado")


# ------------------------------------------------------------------ aplicar

@dataclass
class Applied:
    kind: str
    message: str
    restart: list[str] = field(default_factory=list)  # comando para reabrir depois que este processo sair


def apply(rel: Release, progress: Callable[[int, int], None] | None = None) -> Applied:
    kind = install_kind()
    if kind in MANUAL:
        raise UpdateError(MANUAL[kind])
    name = ASSETS[kind]
    url = rel.assets.get(name)
    if not url:
        raise UpdateError(f"a versão {rel.version} não tem o arquivo {name}")
    return _apply_appimage(rel, name, url, progress) if kind == "appimage" else _apply_windows(rel, name, url, progress)


def _apply_appimage(rel: Release, name: str, url: str, progress) -> Applied:
    target = Path(runtime.appimage())
    if not os.access(target.parent, os.W_OK):
        raise UpdateError(f"sem permissão para escrever em {target.parent}")
    tmp = target.with_name(target.name + ".new")
    download(url, tmp, progress)
    verify(tmp, rel, name)
    tmp.chmod(0o755)
    os.replace(tmp, target)  # quem está rodando continua com o arquivo antigo até fechar
    wait = (f"while kill -0 {os.getpid()} 2>/dev/null; do sleep 0.3; done; "
            f"exec {_sh(str(target))} app >/dev/null 2>&1")
    return Applied("appimage", f"Solarhub {rel.version} instalado em {target}", ["sh", "-c", wait])


def _sh(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def _ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _apply_windows(rel: Release, name: str, url: str, progress) -> Applied:
    install = Path(sys.executable).resolve().parent
    if not os.access(install.parent, os.W_OK):
        raise UpdateError(f"sem permissão para escrever em {install.parent}; mova a pasta do Solarhub para "
                          r"%LOCALAPPDATA%\Programs\Solarhub")
    work = Path(tempfile.mkdtemp(prefix="solarhub-update-"))
    z = download(url, work / name, progress)
    verify(z, rel, name)
    out = work / "x"
    with zipfile.ZipFile(z) as zf:
        for m in zf.namelist():  # nada de caminhos fora da pasta
            if m.startswith(("/", "\\")) or ".." in Path(m).parts:
                raise UpdateError("o .zip tem caminhos inválidos; nada foi alterado")
        zf.extractall(out)
    exe = next(out.rglob("Solarhub.exe"), None)
    if exe is None:
        raise UpdateError("o .zip não contém o Solarhub.exe")
    script = work / "trocar.ps1"
    script.write_text(windows_script(os.getpid(), install, exe.parent, work), "utf-8-sig")
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script)]
    return Applied("windows", f"Solarhub {rel.version} baixado; a troca acontece quando o app fechar", cmd)


def windows_script(pid: int, install: Path, new: Path, work: Path) -> str:
    """Espera o Solarhub fechar, troca a pasta (guardando a antiga até dar certo) e reabre o app."""
    return "\r\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$dir = {_ps(str(install))}; $new = {_ps(str(new))}; $work = {_ps(str(work))}",
        "$log = Join-Path $env:TEMP 'solarhub-update.log'",
        f"for ($i = 0; $i -lt 100 -and (Get-Process -Id {pid} -ErrorAction SilentlyContinue); $i++) "
        "{ Start-Sleep -Milliseconds 300 }",
        "# outros processos do Solarhub dessa pasta (servidor MCP do editor, sync agendado): o editor reinicia o MCP",
        "Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($dir + '\\') } | "
        "Stop-Process -Force -ErrorAction SilentlyContinue",
        "$old = $dir + '.old'",
        "Remove-Item -LiteralPath $old -Recurse -Force -ErrorAction SilentlyContinue",
        "$ok = $false",
        "for ($i = 0; $i -lt 40 -and -not $ok; $i++) {",
        "  try { Rename-Item -LiteralPath $dir -NewName (Split-Path $old -Leaf); $ok = $true }",
        "  catch { Start-Sleep -Milliseconds 500 }",
        "}",
        "if (-not $ok) { \"$(Get-Date) pasta em uso, atualização adiada\" | Add-Content $log; "
        "Start-Process -FilePath (Join-Path $dir 'Solarhub.exe'); exit 1 }",
        "try { Move-Item -LiteralPath $new -Destination $dir }",
        "catch { Rename-Item -LiteralPath $old -NewName (Split-Path $dir -Leaf); "
        "\"$(Get-Date) falhou: $_\" | Add-Content $log; Start-Process -FilePath (Join-Path $dir 'Solarhub.exe'); exit 1 }",
        "Start-Process -FilePath (Join-Path $dir 'Solarhub.exe')",
        "Remove-Item -LiteralPath $old -Recurse -Force -ErrorAction SilentlyContinue",
        "Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue",
        "",
    ])


def launch_after_exit(applied: Applied) -> None:
    """Dispara a reabertura (e, no Windows, a troca da pasta) num processo separado."""
    if not applied.restart:
        return
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if osutil.IS_WINDOWS:
        kwargs["creationflags"] = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(applied.restart, **kwargs)  # noqa: S603
