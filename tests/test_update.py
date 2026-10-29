"""Atualização dos executáveis e lançamento de versões (sem rede: downloads simulados)."""
import hashlib
import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

from solarhub import __version__, update

SPEC = importlib.util.spec_from_file_location("release", Path(__file__).parent.parent / "scripts" / "release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def _rel(version="99.0.0", files=None):
    files = files or {}
    assets = {}
    for name, data in files.items():
        assets[name] = f"https://x/{name}"
        assets[name + ".sha256"] = f"https://x/{name}.sha256"
    return update.Release(version, "v" + version, "### Adicionado\n- coisa nova", "https://x", assets)


@pytest.fixture
def fake_net(monkeypatch):
    blobs = {}

    def fake_download(url, dest, progress=None):
        name = url.rsplit("/", 1)[-1]
        Path(dest).write_bytes(blobs[name])
        return Path(dest)

    monkeypatch.setattr(update, "download", fake_download)

    def publish(name, data, checksum=None):
        blobs[name] = data
        blobs[name + ".sha256"] = f"{checksum or hashlib.sha256(data).hexdigest()}  {name}\n".encode()

    return publish


def test_versions():
    assert update.is_newer("0.10.0", "0.9.9") and update.is_newer("v1.0.0", "0.4.0")
    assert not update.is_newer("0.4.0", "0.4.0") and not update.is_newer("0.3.9", "0.4.0")


def test_check_caches_and_respects_setting(monkeypatch):
    calls = []
    monkeypatch.setattr(update, "fetch_latest", lambda: calls.append(1) or _rel())
    assert update.check(enabled=False) is None and not calls
    assert update.check().version == "99.0.0"
    assert update.check().version == "99.0.0" and len(calls) == 1  # cache de 12 h
    assert update.check(force=True) and len(calls) == 2
    monkeypatch.setattr(update, "fetch_latest", lambda: _rel(__version__))
    assert update.check(force=True) is None  # mesma versão: nada a fazer


def test_source_install_only_points_to_git(monkeypatch):
    monkeypatch.setattr(update, "install_kind", lambda: "source")
    with pytest.raises(update.UpdateError, match="git pull"):
        update.apply(_rel())


def test_appimage_swap(monkeypatch, tmp_path, fake_net):
    img = tmp_path / "Apps" / "Solarhub-x86_64.AppImage"
    img.parent.mkdir()
    img.write_bytes(b"velho")
    monkeypatch.setenv("APPIMAGE", str(img))
    fake_net("Solarhub-x86_64.AppImage", b"novo")
    done = update.apply(_rel(files={"Solarhub-x86_64.AppImage": b"novo"}))
    assert img.read_bytes() == b"novo" and done.kind == "appimage"
    assert str(img) in done.restart[-1]
    assert not img.with_name(img.name + ".new").exists()


def test_bad_checksum_changes_nothing(monkeypatch, tmp_path, fake_net):
    img = tmp_path / "Solarhub-x86_64.AppImage"
    img.write_bytes(b"velho")
    monkeypatch.setenv("APPIMAGE", str(img))
    fake_net("Solarhub-x86_64.AppImage", b"adulterado", checksum="0" * 64)
    with pytest.raises(update.UpdateError, match="não confere"):
        update.apply(_rel(files={"Solarhub-x86_64.AppImage": b""}))
    assert img.read_bytes() == b"velho"


def _zip(files: dict) -> bytes:
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_windows_zip_prepares_swap(monkeypatch, tmp_path, fake_net):
    install = tmp_path / "Programs" / "Solarhub"
    install.mkdir(parents=True)
    (install / "Solarhub.exe").write_bytes(b"velho")
    monkeypatch.setattr(update, "install_kind", lambda: "windows")
    monkeypatch.setattr(sys, "executable", str(install / "Solarhub.exe"))
    data = _zip({"Solarhub/Solarhub.exe": b"novo", "Solarhub/_internal/x.dll": b"x"})
    fake_net("Solarhub-windows-x64.zip", data)
    done = update.apply(_rel(files={"Solarhub-windows-x64.zip": data}))
    script = Path(done.restart[-1])
    text = script.read_text("utf-8-sig")
    assert str(install) in text and "Rename-Item" in text and "Solarhub.exe" in text
    new_dir = next(script.parent.rglob("Solarhub.exe")).parent
    assert (new_dir / "_internal" / "x.dll").exists()
    assert (install / "Solarhub.exe").read_bytes() == b"velho"  # a troca só acontece depois que o app fecha


def test_windows_zip_slip_rejected(monkeypatch, tmp_path, fake_net):
    install = tmp_path / "Solarhub"
    install.mkdir()
    monkeypatch.setattr(update, "install_kind", lambda: "windows")
    monkeypatch.setattr(sys, "executable", str(install / "Solarhub.exe"))
    data = _zip({"../fora.txt": b"x", "Solarhub/Solarhub.exe": b"novo"})
    fake_net("Solarhub-windows-x64.zip", data)
    with pytest.raises(update.UpdateError, match="caminhos inválidos"):
        update.apply(_rel(files={"Solarhub-windows-x64.zip": data}))


CHANGELOG = """# Changelog

## [Não lançado]

### Adicionado
- botão de atualizar

## [0.4.0] — 2026-10-29

- coisas

[0.4.0]: https://github.com/ElioGlock/solarhub/releases/tag/v0.4.0
"""


def test_release_changelog_and_notes():
    out = release.release_changelog(CHANGELOG, "0.5.0", "2026-11-01")
    assert "## [Não lançado]\n\n## [0.5.0] — 2026-11-01\n\n### Adicionado\n- botão de atualizar" in out
    assert out.rstrip().endswith("[0.5.0]: https://github.com/ElioGlock/solarhub/releases/tag/v0.5.0")
    assert release.notes(out, "0.5.0").strip() == "### Adicionado\n- botão de atualizar"
    assert release.notes(out, "0.4.0").strip() == "- coisas"
    assert release.release_changelog(out, "0.5.0", "x") == out  # idempotente
    with pytest.raises(release.ReleaseError, match="vazia"):
        release.release_changelog(out, "0.6.0", "x")


def test_release_bumps_versions():
    py, init = release.set_versions('name = "solarhub"\nversion = "0.4.0"\n', '__version__ = "0.4.0"\n', "0.5.0")
    assert 'version = "0.5.0"' in py and '__version__ = "0.5.0"' in init


def test_real_changelog_has_current_version_notes():
    root = Path(__file__).parent.parent
    assert release.notes((root / "CHANGELOG.md").read_text("utf-8"), __version__).strip()


def test_install_kind_uv_tool(monkeypatch, tmp_path):
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / ".local" / "share" / "uv" / "tools" / "solarhub"))
    assert update.install_kind() == "uvtool"
    assert "uv tool upgrade solarhub" in update.how_to_update()
    with pytest.raises(update.UpdateError, match="uv tool upgrade"):
        update.apply(_rel())
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "solarhub" / ".venv"))
    assert update.install_kind() == "source"
