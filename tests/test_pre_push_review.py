from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess


MODULE_PATH = Path(__file__).parents[1] / "hooks" / "pre-push-review.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pre_push_review", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_chain_uses_current_reviewers(monkeypatch):
    monkeypatch.delenv("PREPUSH_REVIEWERS", raising=False)
    module = load_module()

    assert module.REVIEWER_CHAIN == ["codex", "claude"]


def test_codex_uses_ephemeral_read_only_exec(monkeypatch):
    module = load_module()
    calls = []
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="OK", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._review_codex("review") == "[codex] OK"
    assert calls[0][0] == [
        "/usr/bin/codex",
        "exec",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--color",
        "never",
        "review",
    ]


def test_agy_uses_plan_print_mode_and_user_bin_fallback(monkeypatch, tmp_path):
    module = load_module()
    agy = tmp_path / ".local" / "bin" / "agy"
    agy.parent.mkdir(parents=True)
    agy.write_text("#!/bin/sh\n", encoding="utf-8")
    agy.chmod(0o700)
    monkeypatch.setattr(module.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="OK", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._review_agy("review") == "[agy] OK"
    assert calls[0][0][:8] == [
        str(agy),
        "--print",
        "--mode",
        "plan",
        "--output-format",
        "text",
        "--print-timeout",
        f"{module.REVIEWER_TIMEOUT}s",
    ]
    assert calls[0][0][-1] == "review"
