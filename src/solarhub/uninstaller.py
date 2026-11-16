"""Desinstalação completa: processos do Solarhub e o próprio programa.

`setup.uninstall` desfaz o que o Solarhub configurou (skills, MCP, agendador, atalho, ~/solarhub).
Este módulo cuida do que sobra:

- fechar os outros processos do Solarhub (app aberto, servidor MCP iniciado pelo editor, sync agendado),
  sem nunca derrubar o próprio processo nem quem o iniciou (no Windows o `solarhub.exe` do uv é o pai);
- remover o programa depois que este processo terminar: `uv tool uninstall`, pipx, o AppImage, a pasta do
  .zip do Windows ou o `.venv` de um clone. O Python e o uv nunca são removidos.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from solarhub import osutil, runtime

ROLES = ("app", "mcp", "sync", "gui")
ENTRY_POINTS = ("solarhub", "solarhub-app")


# ------------------------------------------------------------------ processos

def is_ours(args: list[str]) -> bool:
    """Linha de comando de um processo do Solarhub que deve ser fechado (app, MCP, sync)?"""
    names = [re.split(r"[\\/]", a)[-1].lower() for a in args]
    start = None
    for i, n in enumerate(names):
        if n in ("solarhub", "solarhub.exe", "solarhub-cli.exe") or (n.startswith("solarhub-") and n.endswith(".appimage")):
            start = i + 1
            break
        if n in ("solarhub-app", "solarhub-app.exe"):
            return True  # o app aberto pelo atalho
        if n == "-m" and i + 1 < len(args) and args[i + 1] == "solarhub":
            start = i + 2
            break
    if start is None:
        return False
    rest = iter(args[start:])
    for a in rest:
        if a == "--home":
            next(rest, None)
        elif not a.startswith("-"):
            return a in ROLES  # o primeiro comando decide: `solarhub search app` não é o app
    return names[0] != "solarhub" and "-m" in args  # `python -m solarhub` sem comando: o app do AppImage


def _ancestors_posix(pid: int) -> set[int]:
    seen = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            pid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return seen


def windows_stop_script(me: int) -> str:
    """PowerShell que fecha os processos do Solarhub, poupando este processo e toda a cadeia de pais."""
    return "\n".join([
        "$all = Get-CimInstance Win32_Process",
        "$byId = @{}; foreach ($p in $all) { $byId[[int]$p.ProcessId] = $p }",
        "$skip = New-Object 'System.Collections.Generic.HashSet[int]'",
        f"$cur = {int(me)}",
        "while ($cur -and $byId.ContainsKey($cur) -and $skip.Add($cur)) { $cur = [int]$byId[$cur].ParentProcessId }",
        "$re = '(?i)((-m\\s+solarhub)|(solarhub(-cli|-app)?(\\.exe)?\"?))\\s+(app|mcp|sync|gui)\\b'",
        "foreach ($p in $all) {",
        "  if ($skip.Contains([int]$p.ProcessId)) { continue }",
        "  $cl = [string]$p.CommandLine",
        "  if ($p.Name -ceq 'Solarhub.exe' -or $p.Name -ieq 'solarhub-app.exe' -or $cl -match $re) {",
        "    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; 'x'",
        "  }",
        "}",
    ])


def stop_other_processes() -> int:
    """Fecha app, servidores MCP e sync em andamento (senão seguram arquivos ou recriam ~/solarhub)."""
    if os.environ.get("SOLARHUB_TESTING"):
        return 0  # nos testes, nunca mexer em processos reais da máquina
    me = os.getpid()
    if osutil.IS_WINDOWS:
        try:
            p = osutil.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", windows_stop_script(me)],
                           capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return 0
        return (p.stdout or "").count("x")
    proc = Path("/proc")
    if not proc.is_dir():
        return 0
    import signal  # noqa: PLC0415

    skip = _ancestors_posix(me)
    n = 0
    for d in proc.iterdir():
        if not d.name.isdigit() or int(d.name) in skip:
            continue
        try:
            args = [a.decode("utf-8", "replace") for a in (d / "cmdline").read_bytes().split(b"\0") if a]
        except OSError:
            continue
        if is_ours(args):
            try:
                os.kill(int(d.name), signal.SIGTERM)
                n += 1
            except OSError:
                pass
    return n


# ------------------------------------------------------------------ o programa

@dataclass
class ProgramRemoval:
    kind: str
    description: str
    paths: list[Path] = field(default_factory=list)       # apagados depois que este processo sair
    commands: list[list[str]] = field(default_factory=list)  # rodados antes (ex.: uv tool uninstall)


def _find(tool: str) -> str | None:
    exe = tool + (".exe" if osutil.IS_WINDOWS else "")
    found = shutil.which(tool)
    if found:
        return found
    home = Path.home()
    cands = [home / ".local" / "bin" / exe, home / ".cargo" / "bin" / exe]
    if osutil.IS_WINDOWS:
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        cands += [local / "Microsoft" / "WinGet" / "Links" / exe, local / "Programs" / tool / exe]
    return next((str(c) for c in cands if c.is_file()), None)


def _tool_bin_dir(env_var: str) -> Path:
    if os.environ.get(env_var):
        return Path(os.environ[env_var])
    if os.environ.get("XDG_BIN_HOME") and env_var == "UV_TOOL_BIN_DIR":
        return Path(os.environ["XDG_BIN_HOME"])
    return Path.home() / ".local" / "bin"


def _shims(bin_dir: Path, tool_dir: Path) -> list[Path]:
    out = []
    for name in ENTRY_POINTS:
        for p in (bin_dir / name, bin_dir / f"{name}.exe", bin_dir / f"{name}.cmd"):
            if osutil.is_link(p):
                target = osutil.link_target(p) or ""
                if str(tool_dir) in target:
                    out.append(p)
            elif p.is_file() and (osutil.IS_WINDOWS or "solarhub" in p.read_text("utf-8", "replace")[:400]):
                out.append(p)
    return out


def _parts(p: Path) -> list[str]:
    return [x.lower() for x in p.parts]


def program_removal() -> ProgramRemoval | None:
    """O que remove o programa nesta instalação (calculado antes de apagar qualquer coisa)."""
    img = runtime.appimage()
    if img:
        return ProgramRemoval("appimage", f"o AppImage ({img})", [Path(img)])
    if runtime.is_frozen() and osutil.IS_WINDOWS:
        folder = Path(sys.executable).resolve().parent
        return ProgramRemoval("windows", f"a pasta do programa ({folder})", [folder])
    prefix = Path(sys.prefix)
    parts = _parts(prefix)
    pairs = [parts[i:i + 2] for i in range(len(parts))]
    if ["uv", "tools"] in pairs and prefix.name.lower() == "solarhub":
        uv = _find("uv")
        cmds = [[uv, "tool", "uninstall", "solarhub"]] if uv else []
        return ProgramRemoval("uvtool", "o programa instalado com `uv tool` (o Python e o uv continuam)",
                              [prefix, *_shims(_tool_bin_dir("UV_TOOL_BIN_DIR"), prefix)], cmds)
    if ["pipx", "venvs"] in pairs and prefix.name.lower() == "solarhub":
        pipx = _find("pipx")
        cmds = [[pipx, "uninstall", "solarhub"]] if pipx else []
        return ProgramRemoval("pipx", "o programa instalado com `pipx` (o Python continua)",
                              [prefix, *_shims(_tool_bin_dir("PIPX_BIN_DIR"), prefix)], cmds)
    clone = prefix.parent
    if prefix.name == ".venv" and (clone / "pyproject.toml").is_file() and (clone / "src" / "solarhub").is_dir():
        return ProgramRemoval("source", f"o ambiente .venv do clone ({prefix}); a pasta do código fica, apague se "
                                        "quiser", [prefix])
    return None


def _safe(p: Path) -> bool:
    """Só apaga o que é claramente do Solarhub."""
    s = str(p).lower()
    return "solarhub" in s and len(p.parts) > 2


def _ps(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def removal_script(r: ProgramRemoval, pid: int) -> str:
    targets = [p for p in r.paths if _safe(p)]
    if osutil.IS_WINDOWS:
        lines = ["$ErrorActionPreference = 'SilentlyContinue'",
                 f"for ($i = 0; $i -lt 200 -and (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue); $i++) "
                 "{ Start-Sleep -Milliseconds 300 }",
                 "Start-Sleep -Milliseconds 800"]
        lines += ["& " + " ".join(_ps(c) for c in cmd) + " *> $null" for cmd in r.commands]
        lines += [f"$targets = @({', '.join(_ps(str(p)) for p in targets)})",
                  "for ($i = 0; $i -lt 40; $i++) {",
                  "  foreach ($t in $targets) { Remove-Item -LiteralPath $t -Recurse -Force }",
                  "  if (-not ($targets | Where-Object { Test-Path -LiteralPath $_ })) { break }",
                  "  Start-Sleep -Milliseconds 700",
                  "}",
                  "Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force"]
        return "\r\n".join(lines) + "\r\n"
    q = lambda s: "'" + s.replace("'", "'\\''") + "'"  # noqa: E731
    parts = [f"while kill -0 {int(pid)} 2>/dev/null; do sleep 0.3; done", "sleep 0.5"]
    parts += [" ".join(q(c) for c in cmd) + " >/dev/null 2>&1" for cmd in r.commands]
    if targets:
        parts.append("rm -rf -- " + " ".join(q(str(p)) for p in targets))
    return "; ".join(parts)


def launch_removal(r: ProgramRemoval) -> None:
    """Dispara a remoção do programa num processo separado, que espera este terminar."""
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                "cwd": tempfile.gettempdir()}
    script = removal_script(r, os.getpid())
    if osutil.IS_WINDOWS:
        f = Path(tempfile.gettempdir()) / f"solarhub-remover-{os.getpid()}.ps1"
        f.write_text(script, "utf-8-sig")
        kw["creationflags"] = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(f)]
    else:
        kw["start_new_session"] = True
        cmd = ["sh", "-c", script]
    subprocess.Popen(cmd, **kw)  # noqa: S603
