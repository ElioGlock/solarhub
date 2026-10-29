# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: gera dist/Solarhub/ com
#   Solarhub.exe      app de desktop (sem console); também roda o sync do Agendador de Tarefas
#   solarhub-cli.exe  terminal e servidor MCP (stdio)
#
#   pip install ".[app]" pyinstaller
#   pyinstaller packaging/windows/solarhub.spec --noconfirm
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
ICON = os.path.join(ROOT, "src", "solarhub", "desktop", "solarhub.ico")

hidden = collect_submodules("solarhub") + collect_submodules("mcp")
datas = collect_data_files("solarhub")

a = Analysis(
    [os.path.join(SPECPATH, "solarhub_entry.py")],
    hiddenimports=hidden,
    datas=datas,
    excludes=["tkinter", "fastembed", "onnxruntime", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Solarhub", console=False, icon=ICON)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="solarhub-cli", console=True, icon=ICON)
coll = COLLECT(gui, cli, a.binaries, a.datas, strip=False, upx=False, name="Solarhub")
