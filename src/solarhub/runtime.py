"""Como chamar o próprio Solarhub: venv do app, uv tool, AppImage (Linux) ou executável (Windows)."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from solarhub import osutil, paths

GUI_EXE = "Solarhub"        # Windows empacotado: app sem console
CLI_EXE = "solarhub-cli"    # Windows empacotado: console (MCP via stdio, terminal)


def appimage() -> str | None:
    """Caminho do .AppImage quando o Solarhub roda empacotado (o AppImage define APPIMAGE)."""
    p = os.environ.get("APPIMAGE")
    return p if p and Path(p).is_file() else None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_gui_exe() -> bool:
    return is_frozen() and Path(sys.executable).stem.lower() == GUI_EXE.lower()


def _home_args() -> list[str]:
    return [] if paths.is_default_home() else ["--home", str(paths.home())]


def self_command(background: bool = False) -> list[str]:
    """Comando estável para `solarhub <args>`.

    background=True: para o agendador e o atalho (no Windows, sem janela de console);
    background=False: para o MCP via stdio e o terminal.
    """
    img = appimage()
    if img:
        return [img, *_home_args()]
    if is_frozen():
        folder = Path(sys.executable).parent
        exe = folder / f"{GUI_EXE if background else CLI_EXE}.exe"
        return [str(exe if exe.exists() else sys.executable), *_home_args()]
    py = Path(sys.executable)
    if osutil.IS_WINDOWS and background:
        pyw = py.with_name("pythonw.exe")
        py = pyw if pyw.exists() else py
    return [str(py), "-m", "solarhub", *_home_args()]


def shell_command(*args: str, background: bool = False) -> str:
    parts = [*self_command(background), *args]
    return subprocess.list2cmdline(parts) if osutil.IS_WINDOWS else " ".join(shlex.quote(a) for a in parts)


def cli_entry() -> Path | None:
    """Executável `solarhub` deste ambiente, quando existe (venv/uv tool)."""
    name = "solarhub.exe" if osutil.IS_WINDOWS else "solarhub"
    exe = Path(sys.executable).parent / name
    return exe if exe.exists() else None
