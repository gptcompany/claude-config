from __future__ import annotations

import importlib.util
from pathlib import Path
import stat
import sys
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "scripts/install_codex_mcp.py"
    spec = importlib.util.spec_from_file_location("install_codex_mcp", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _install(module, target: Path, *, check: bool = False):
    return module.install(
        ROOT / "templates/codex-mcp.toml",
        target,
        check=check,
        executable=lambda path: path in {"/usr/bin/env", "serena"},
    )


def test_install_replaces_global_mcp_only_and_preserves_serena_tool_policy(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = tmp_path / ".codex/config.toml"
    target.parent.mkdir()
    original = (
        'model = "gpt-5.6-sol"\n'
        'approval_policy = "never"\n\n'
        '[features]\napps = true\n\n'
        '[mcp_servers.context7]\ncommand = "npx"\n'
        'args = ["-y", "@upstash/context7-mcp"]\n'
        'startup_timeout_sec = 120.0\n\n'
        '[mcp_servers.serena]\ncommand = "serena"\n'
        'args = ["start-mcp-server", "--context", "ide-assistant"]\n'
        'startup_timeout_sec = 30.0\n\n'
        '[mcp_servers.serena.tools.activate_project]\nenabled = true\n\n'
        '[mcp_servers.openmemory]\nurl = "http://192.168.1.100:8080/mcp"\n\n'
        '[profiles.fast]\nmodel = "gpt-5.6-mini"\n'
    )
    target.write_text(original, encoding="utf-8")
    target.chmod(0o644)

    assert _install(module, target) is True
    installed = tomllib.loads(target.read_text(encoding="utf-8"))

    assert installed["model"] == "gpt-5.6-sol"
    assert installed["approval_policy"] == "never"
    assert installed["features"] == {"apps": True}
    assert installed["profiles"]["fast"]["model"] == "gpt-5.6-mini"
    assert set(installed["mcp_servers"]) == {"context7", "serena"}
    assert installed["mcp_servers"]["context7"] == {
        "url": "https://mcp.context7.com/mcp",
        "startup_timeout_sec": 30.0,
    }
    serena = installed["mcp_servers"]["serena"]
    assert serena["startup_timeout_sec"] == 30.0
    assert serena["command"] == "/usr/bin/env"
    assert serena["tools"]["activate_project"] == {"enabled": True}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    backups = list((target.parent / "backups/claude-config").glob("*.toml"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == original
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600

    assert _install(module, target, check=True) is False
    assert _install(module, target) is False
    assert len(list((target.parent / "backups/claude-config").glob("*.toml"))) == 1


def test_install_rejects_bad_template_and_symlinked_target(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "config.toml"
    real = tmp_path / "real.toml"
    real.write_text('model = "gpt"\n', encoding="utf-8")
    target.symlink_to(real)

    with pytest.raises(module.InstallError, match="symlinked"):
        _install(module, target)

    target.unlink()
    bad_template = tmp_path / "bad.toml"
    bad_template.write_text('[mcp_servers.openmemory]\nurl = "http://host"\n')
    with pytest.raises(module.InstallError, match="exactly context7 and serena"):
        module.install(
            bad_template,
            target,
            check=False,
            executable=lambda _path: True,
        )


def test_check_detects_config_and_mode_drift(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "config.toml"
    target.write_text('model = "gpt"\n', encoding="utf-8")
    target.chmod(0o600)
    with pytest.raises(module.InstallError, match="config=yes"):
        _install(module, target, check=True)

    _install(module, target)
    target.chmod(0o644)
    with pytest.raises(module.InstallError, match="mode=yes"):
        _install(module, target, check=True)


def test_install_detects_concurrent_change(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    target = tmp_path / "config.toml"
    target.write_text('model = "gpt"\n', encoding="utf-8")
    target.chmod(0o600)
    real_snapshot = module._snapshot
    calls = 0

    def changed_snapshot(path: Path):
        nonlocal calls
        value = real_snapshot(path)
        if path == target:
            calls += 1
        if path == target and calls == 2 and value is not None:
            return (*value[:-1], value[-1] + 1)
        return value

    monkeypatch.setattr(module, "_snapshot", changed_snapshot)
    with pytest.raises(module.InstallError, match="changed concurrently"):
        _install(module, target)
    assert target.read_text(encoding="utf-8") == 'model = "gpt"\n'
