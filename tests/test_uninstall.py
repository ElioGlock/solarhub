"""Desinstalação completa: processos, o próprio programa e skills no Windows sem symlink."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from solarhub import linker, osutil, runtime, setup, uninstaller
from solarhub.cli import app


def test_which_processes_are_closed():
    ours = uninstaller.is_ours
    assert ours(["python", "-m", "solarhub", "mcp"])
    assert ours(["/x/bin/python3", "/x/bin/solarhub", "app"])
    assert ours(["C:\\u\\.local\\bin\\solarhub.exe", "sync"])
    assert ours(["/apps/Solarhub-x86_64.AppImage", "mcp"])
    assert ours(["/x/bin/solarhub-app"])
    assert ours(["/x/opt/python/bin/python3", "-I", "-m", "solarhub"])  # app do AppImage aberto sem comando
    assert not ours(["/x/bin/solarhub", "uninstall"])  # o próprio comando de desinstalar
    assert not ours(["/x/bin/solarhub", "search", "app"])
    assert not ours(["vim", "solarhub.txt", "app"])
    assert not ours([])


def test_windows_never_kills_itself_or_its_parents():
    s = uninstaller.windows_stop_script(4242)
    assert "$cur = 4242" in s and "ParentProcessId" in s  # poupa a cadeia de pais (o solarhub.exe do uv)
    assert "-ceq 'Solarhub.exe'" in s  # o app empacotado, não o atalho solarhub.exe do uv


def test_mcp_on_windows_never_uses_pythonw(tmp_path, monkeypatch):
    for n in ("python.exe", "pythonw.exe"):
        (tmp_path / n).write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime.osutil, "IS_WINDOWS", True)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "pythonw.exe"))  # app aberto pelo atalho
    assert Path(runtime.self_command()[0]).name == "python.exe"  # MCP e terminal
    assert Path(runtime.self_command(background=True)[0]).name == "pythonw.exe"  # agendador e atalho
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    assert Path(runtime.self_command()[0]).name == "python.exe"


def test_skills_are_copied_when_symlinks_are_not_allowed(knowledge_repo, env, monkeypatch):
    from solarhub import actions, config

    monkeypatch.setattr(osutil, "can_symlink", lambda: False)
    actions.add_source(knowledge_repo.as_uri())
    cfg = config.load()
    assert linker.effective_mode(cfg) == "copy"
    skill = linker.target_dir("copilot") / "api-standards"
    assert skill.is_dir() and not osutil.is_link(skill) and (skill / "SKILL.md").is_file()
    assert (skill / linker.COPY_MARKER).is_file()
    linker.unlink_all()
    assert not skill.exists()


def _uv_tool(env):
    prefix = env / ".local" / "share" / "uv" / "tools" / "solarhub"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin" / "solarhub").write_text("#!/bin/sh\n", encoding="utf-8")
    bin_dir = env / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "solarhub").symlink_to(prefix / "bin" / "solarhub")
    (bin_dir / "outro").write_text("x", encoding="utf-8")
    return prefix, bin_dir


@pytest.mark.skipif(osutil.IS_WINDOWS, reason="symlinks de exemplo do Linux")
def test_program_removal_for_uv_tool(env, monkeypatch):
    prefix, bin_dir = _uv_tool(env)
    monkeypatch.setattr(sys, "prefix", str(prefix))
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(uninstaller, "_find", lambda tool: "/opt/uv/bin/uv" if tool == "uv" else None)
    r = uninstaller.program_removal()
    assert r.kind == "uvtool" and r.commands == [["/opt/uv/bin/uv", "tool", "uninstall", "solarhub"]]
    assert prefix in r.paths and bin_dir / "solarhub" in r.paths and bin_dir / "outro" not in r.paths
    # o script espera o processo terminar e remove só o que é do Solarhub (simulado com um PID que já saiu)
    r.commands = []
    r.paths.append(env / "nao-mexer")
    (env / "nao-mexer").mkdir()
    subprocess.run(["sh", "-c", uninstaller.removal_script(r, 999999)], check=True, timeout=30)
    assert not prefix.exists() and not os.path.lexists(bin_dir / "solarhub")
    assert (bin_dir / "outro").exists() and (env / "nao-mexer").exists()


def test_program_removal_other_installs(env, tmp_path, monkeypatch):
    clone = tmp_path / "solarhub-code"
    (clone / "src" / "solarhub").mkdir(parents=True)
    (clone / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(sys, "prefix", str(clone / ".venv"))
    assert uninstaller.program_removal().kind == "source"
    img = tmp_path / "Solarhub-x86_64.AppImage"
    img.write_bytes(b"x")
    monkeypatch.setenv("APPIMAGE", str(img))
    r = uninstaller.program_removal()
    assert (r.kind, r.paths) == ("appimage", [img])
    monkeypatch.delenv("APPIMAGE")
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "qualquer" / "venv"))
    assert uninstaller.program_removal() is None  # Python do sistema: nada a remover


def test_windows_removal_script(monkeypatch):
    monkeypatch.setattr(uninstaller.osutil, "IS_WINDOWS", True)
    r = uninstaller.ProgramRemoval("uvtool", "x", [Path("C:/Users/a/AppData/Roaming/uv/tools/solarhub")],
                                   [["C:/u/uv.exe", "tool", "uninstall", "solarhub"]])
    s = uninstaller.removal_script(r, 77)
    assert "Get-Process -Id 77" in s and "tool' 'uninstall' 'solarhub'" in s and "Remove-Item" in s


def test_cli_uninstall_removes_hub_and_program(env, knowledge_repo, monkeypatch):
    from solarhub import actions, paths

    actions.add_source(knowledge_repo.as_uri())
    launched = []
    removal = uninstaller.ProgramRemoval("uvtool", "o programa", [env / "solarhub-tool"])
    monkeypatch.setattr(uninstaller, "program_removal", lambda: removal)
    monkeypatch.setattr(uninstaller, "launch_removal", launched.append)
    res = CliRunner().invoke(app, ["uninstall", "--yes"])
    assert res.exit_code == 0, res.output
    assert not paths.home().exists() and launched == [removal]
    res = CliRunner().invoke(app, ["uninstall", "--yes", "--keep-program"])
    assert res.exit_code == 0 and launched == [removal]  # não agenda de novo
