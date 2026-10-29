import pytest
import json

from typer.testing import CliRunner

from solarhub import osutil
from solarhub import blocks, clients, mcp_server, setup
from solarhub.cli import app


def test_vscode_mcp_install_keeps_existing(env):
    f = osutil.vscode_user_dir() / "mcp.json"
    f.parent.mkdir(parents=True)
    f.write_text('{\n  // comentário\n  "servers": {"outro": {"command": "x"}},\n}\n', encoding="utf-8")
    (f.parent.parent / "logs").mkdir()  # pasta que o próprio VS Code cria
    c = clients.get("vscode")
    assert c.detected()
    clients.install(c)
    data = json.loads(f.read_text(encoding="utf-8"))
    assert set(data["servers"]) == {"outro", "solarhub"}
    assert data["servers"]["solarhub"]["args"] == ["-m", "solarhub", "mcp"]
    assert clients.installed(c)
    assert list(f.parent.glob("mcp.json.solarhub-bak-*"))
    clients.uninstall(c)
    assert set(json.loads(f.read_text(encoding="utf-8"))["servers"]) == {"outro"}


@pytest.mark.skipif(osutil.IS_WINDOWS, reason="blocos de shell são do Linux/macOS")
def test_blocks_and_uninstall(env):
    p = env / ".profile"
    p.write_text("export A=1\n", encoding="utf-8")
    setup.setup()
    setup.setup()  # idempotente
    text = p.read_text(encoding="utf-8")
    assert text.count(blocks.SHELL[0]) == 1 and "SOLARHUB_HOME" in text and text.startswith("export A=1")
    setup.uninstall()
    assert p.read_text(encoding="utf-8").strip() == "export A=1"


def test_cli_flow(knowledge_repo):
    r = CliRunner()
    res = r.invoke(app, ["add", knowledge_repo.as_uri()])
    assert res.exit_code == 0, res.output
    res = r.invoke(app, ["search", "cursor", "--kind", "adr"])
    assert "ADR-014" in res.output
    res = r.invoke(app, ["get", "adr:14", "--raw"])
    assert "cursor opaco" in res.output
    res = r.invoke(app, ["context", "listagem paginada", "--skill", "api-standards"])
    assert "api-standards" in res.output and "ADR-014" in res.output
    res = r.invoke(app, ["list"])
    assert "eng-knowledge" in res.output


def test_mcp_tools(knowledge_repo):
    import asyncio

    CliRunner().invoke(app, ["add", knowledge_repo.as_uri()])
    run = asyncio.run
    out = run(mcp_server.solar_get_adr("9"))
    assert "ADR-009" in out and "substituído por ADR-014" in out and "Toda API de listagem" in out
    assert "<solarhub-document" in run(mcp_server.solar_get("skill:api-standards"))
    assert "ADR-014" in run(mcp_server.solar_search("paginação", kind="adr"))
    assert "God object" in run(mcp_server.solar_check_antipatterns("classe de serviço com regras demais"))
    assert "eng-knowledge" in run(mcp_server.solar_status())
    assert "não encontrada" in run(mcp_server.solar_get("adr:999"))
    assert "fonte eng-knowledge vinculada" in run(mcp_server.solar_changes(7))
    assert "desligado" in run(mcp_server.solar_propose_adr("Usar Kafka", "c", "d", "e"))


def test_uninstall_removes_everything(env, knowledge_repo):
    from solarhub import actions, linker, paths

    actions.add_source(knowledge_repo.as_uri())
    setup.setup()
    mine = env / ".claude" / "skills" / "minha-skill"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("x", encoding="utf-8")
    for t in linker.TARGET_DIRS:
        linker.target_dir(t).mkdir(parents=True, exist_ok=True)
    setup.uninstall()
    assert not paths.home().exists()
    assert (mine / "SKILL.md").exists()  # o que é do usuário fica
    assert not (env / ".copilot").exists()  # pasta criada só pelo Solarhub e vazia some
    assert not (env / ".local" / "share" / "applications" / "solarhub.desktop").exists()


def test_uninstall_keep_data(env, knowledge_repo):
    from solarhub import paths

    setup.setup()
    setup.uninstall(keep_data=True)
    assert paths.home().exists()


def test_cli_survives_cp1252_console(tmp_path):
    """No Windows o console costuma ser cp1252; ✓ e → não podem derrubar o comando."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    example = tmp_path / "kb"
    (example / "adrs").mkdir(parents=True)
    (example / "adrs" / "0001-x.md").write_text("# ADR-001: Usar Postgres\n\n- Status: Aceito\n\nTexto da decisão.\n",
                                                encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    p = subprocess.run([sys.executable, "-m", "solarhub", "lint", str(example), "--strict"],
                       capture_output=True, env=env, timeout=120)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
    assert "nenhum problema" in p.stdout.decode("utf-8", "replace")


@pytest.mark.skipif(osutil.IS_WINDOWS, reason="atalho .desktop é do Linux")
def test_launcher_has_icon_files(env):
    from pathlib import Path

    entry = Path(setup.install_launcher())
    icon_line = next(ln for ln in entry.read_text("utf-8").splitlines() if ln.startswith("Icon="))
    icon = Path(icon_line[5:])
    assert icon.is_absolute() and icon.is_file() and icon.suffix == ".png"
    hicolor = env / ".local" / "share" / "icons" / "hicolor"
    assert (hicolor / "scalable" / "apps" / "solarhub.svg").is_file()
    assert (hicolor / "48x48" / "apps" / "solarhub.png").is_file()
