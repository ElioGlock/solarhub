"""Detecção das ferramentas: só sinais da própria ferramenta, nunca o que o Solarhub cria."""
import pytest

from solarhub import clients, config, setup


@pytest.fixture(autouse=True)
def no_commands(tmp_path, monkeypatch):
    empty = tmp_path / "sem-comandos"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))  # nenhum `claude`, `code`, `cursor`… no PATH


def test_solarhub_folders_do_not_count(env):
    (env / ".claude" / "skills" / "solarhub").mkdir(parents=True)
    (env / ".cursor").mkdir()
    (env / ".cursor" / "mcp.json").write_text("{}", encoding="utf-8")
    (env / ".copilot" / "skills").mkdir(parents=True)
    for key in ("claude", "cursor", "copilot-cli", "vscode", "gemini"):
        assert clients.get(key).detection() is None, key


def _reason(key: str) -> str:
    """Motivo da detecção com "/" em qualquer sistema (no Windows o caminho vem com "\\")."""
    return (clients.get(key).detection() or "").replace("\\", "/")


def test_real_signals_count_and_explain(env):
    (env / ".claude.json").write_text("{}", encoding="utf-8")
    assert "arquivo ~/.claude.json" in _reason("claude")
    (env / ".claude.json").unlink()
    (env / ".claude" / "projects").mkdir(parents=True)
    assert "pasta ~/.claude com projects" in _reason("claude")
    (env / ".cursor" / "extensions").mkdir(parents=True)
    assert clients.get("cursor").detected()


def test_command_on_path(env, tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o755)
    (bin_dir / "claude.cmd").write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(bin_dir))
    assert "comando `claude`" in clients.get("claude").detection()


def test_fresh_setup_only_links_detected_tools(env):
    setup.setup(launcher=False)
    assert config.load().settings.link_targets == ["copilot"]
    assert not (env / ".claude").exists()
