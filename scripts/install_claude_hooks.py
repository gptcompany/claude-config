#!/usr/bin/env python3
"""Install versioned Claude hooks without replacing the user's profile."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LEGACY_CLAUDE_FLOW_MARKERS = (
    "@claude-flow/",
    "claude-flow",
    ".claude-flow",
    "ruflo",
    "claudeflow-sync.js",
    "cf-session-workers.js",
)
OBSOLETE_PERMISSION_RULES = {
    "MultiEdit(//home/sam/**)",
    "MultiEdit(//media/sam/1TB/**)",
    "MultiEdit(//media/sam/1TB1/**)",
    "Write(//media/sam/1TB/**)",
    "Write(//media/sam/1TB1/**)",
    "mcp__context7__get-library-docs",
}
ASSET_ROOTS = (
    (Path("scripts/hooks"), Path("scripts/hooks")),
    (Path("scripts/lib"), Path("scripts/lib")),
)
ASSET_FILES = (
    (Path("commands/pipeline.gsd.md"), Path("commands/pipeline.gsd.md")),
    (Path("commands/pipeline.speckit.md"), Path("commands/pipeline.speckit.md")),
    (Path("commands/pipeline.status.md"), Path("commands/pipeline.status.md")),
    (Path("commands/research.md"), Path("commands/research.md")),
    (
        Path("commands/speckit.implement-sync.md"),
        Path("commands/speckit.implement-sync.md"),
    ),
    (Path("hooks/gsd-check-update.js"), Path("hooks/gsd-check-update.js")),
    (
        Path("scripts/statusline/context-monitor.js"),
        Path("scripts/statusline/context-monitor.js"),
    ),
    (
        Path("scripts/statusline/ui-components.js"),
        Path("scripts/statusline/ui-components.js"),
    ),
    (Path("skills/auto-pipeline/SKILL.md"), Path("skills/auto-pipeline/SKILL.md")),
    (
        Path("skills/confidence-gate/SKILL.md"),
        Path("skills/confidence-gate/SKILL.md"),
    ),
    (Path("skills/context-action/SKILL.md"), Path("skills/context-action/SKILL.md")),
    (Path("skills/swarm/SKILL.md"), Path("skills/swarm/SKILL.md")),
)
RETIRED_ASSETS = (
    Path("scripts/hooks/metrics/claudeflow-sync.js"),
    Path("scripts/hooks/intelligence/cf-session-workers.js"),
    Path("scripts/statusline/update-cf-status.sh"),
)
IGNORED_PARTS = {"node_modules", "__pycache__"}


class InstallError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise InstallError(f"refusing symlinked JSON file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"expected a JSON object: {path}")
    return value


def _asset_pairs(source_root: Path, target_root: Path) -> Iterable[tuple[Path, Path]]:
    for source_rel, target_rel in ASSET_ROOTS:
        source_dir = source_root / source_rel
        for source in sorted(source_dir.rglob("*")):
            relative = source.relative_to(source_dir)
            if (
                not source.is_file()
                or source.suffix != ".js"
                or source.name.endswith(".test.js")
                or any(part in IGNORED_PARTS for part in relative.parts)
            ):
                continue
            yield source, target_root / target_rel / relative
    for source_rel, target_rel in ASSET_FILES:
        yield source_root / source_rel, target_root / target_rel


def _hook_identity(command: str) -> str:
    normalized = re.sub(r"/(?:home|Users)/[^/]+/\.claude/", "$HOME/.claude/", command)
    normalized = normalized.replace("${HOME}/.claude/", "$HOME/.claude/")
    match = re.search(r"\$HOME/\.claude/[^\"' ]+", normalized)
    return match.group(0) if match else normalized


def _merge_hooks(active: dict[str, Any], canonical: dict[str, Any]) -> None:
    active_hooks = active.setdefault("hooks", {})
    if not isinstance(active_hooks, dict):
        raise InstallError("active settings hooks must be an object")

    for event, groups in list(active_hooks.items()):
        if not isinstance(groups, list):
            raise InstallError(f"active hook event {event} must be a list")
        cleaned_groups: list[dict[str, Any]] = []
        for group in groups:
            if not isinstance(group, dict):
                raise InstallError(f"active hook group in {event} must be an object")
            hooks = group.get("hooks", [])
            if not isinstance(hooks, list):
                raise InstallError(f"active hook list in {event} must be a list")
            cleaned = [
                hook
                for hook in hooks
                if not (
                    isinstance(hook, dict)
                    and any(
                        marker in str(hook.get("command") or "").lower()
                        for marker in LEGACY_CLAUDE_FLOW_MARKERS
                    )
                )
            ]
            if cleaned:
                cleaned_groups.append({**group, "hooks": cleaned})
        active_hooks[event] = cleaned_groups

    canonical_hooks = canonical.get("hooks", {})
    for event, groups in canonical_hooks.items():
        event_groups = active_hooks.setdefault(event, [])
        for canonical_group in groups:
            matcher = canonical_group.get("matcher")
            target_group = next(
                (
                    group
                    for group in event_groups
                    if group.get("matcher") == matcher
                    and ("matcher" in group) == ("matcher" in canonical_group)
                ),
                None,
            )
            if target_group is None:
                target_group = {key: value for key, value in canonical_group.items() if key != "hooks"}
                target_group["hooks"] = []
                event_groups.append(target_group)
            target_hooks = target_group["hooks"]
            for canonical_hook in canonical_group.get("hooks", []):
                identity = _hook_identity(str(canonical_hook.get("command") or ""))
                index = next(
                    (
                        i
                        for i, hook in enumerate(target_hooks)
                        if isinstance(hook, dict)
                        and _hook_identity(str(hook.get("command") or "")) == identity
                    ),
                    None,
                )
                if index is None:
                    target_hooks.append(canonical_hook)
                else:
                    target_hooks[index] = canonical_hook


def _merge_settings(active: dict[str, Any], canonical: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(active))
    _merge_hooks(merged, canonical)
    merged["enableAllProjectMcpServers"] = bool(
        canonical.get("enableAllProjectMcpServers", False)
    )
    permissions = merged.get("permissions", {})
    if isinstance(permissions, dict) and isinstance(permissions.get("allow"), list):
        permissions["allow"] = [
            rule for rule in permissions["allow"] if rule not in OBSOLETE_PERMISSION_RULES
        ]
    return merged


def _verify_registered_assets(
    settings: dict[str, Any],
    target_root: Path,
    planned_targets: set[Path] | None = None,
) -> None:
    planned_targets = planned_targets or set()
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                command = str(hook.get("command") or "")
                match = re.search(
                    r"(?:\$HOME|\$\{HOME\}|/(?:home|Users)/[^/]+)/\.claude/([^\"' ]+)",
                    command,
                )
                if not match:
                    continue
                target = target_root / match.group(1)
                if not target.is_file() and target not in planned_targets:
                    raise InstallError(
                        f"registered {event} hook asset is missing: {match.group(1)}"
                    )


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_asset(source: Path, target: Path) -> None:
    if target.is_symlink():
        raise InstallError(f"refusing symlinked asset: {target}")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.install-{os.getpid()}")
    shutil.copyfile(source, temporary)
    os.chmod(temporary, stat.S_IMODE(source.stat().st_mode))
    os.replace(temporary, target)


def _snapshot_files(paths: Iterable[Path]) -> dict[Path, tuple[bytes, int] | None]:
    snapshots: dict[Path, tuple[bytes, int] | None] = {}
    for path in paths:
        if path.exists():
            snapshots[path] = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        else:
            snapshots[path] = None
    return snapshots


def _restore_files(snapshots: dict[Path, tuple[bytes, int] | None]) -> None:
    for path, snapshot in reversed(tuple(snapshots.items())):
        if snapshot is None:
            path.unlink(missing_ok=True)
            continue
        content, mode = snapshot
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.rollback-{os.getpid()}")
        temporary.write_bytes(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)


def _backup_file(source: Path, target: Path) -> None:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(source.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def _reject_symlinked_path(target_root: Path, target: Path, *, label: str) -> None:
    try:
        relative = target.relative_to(target_root)
    except ValueError as exc:
        raise InstallError(f"{label} escapes target root: {target}") from exc
    current = target_root
    for part in relative.parts:
        if current.is_symlink():
            raise InstallError(f"refusing symlinked {label} path: {current}")
        current = current / part
    if current.is_symlink():
        raise InstallError(f"refusing symlinked {label} path: {current}")


def install(source_root: Path, target_root: Path, *, check: bool) -> tuple[int, bool]:
    canonical = _read_json(source_root / "settings.json")
    settings_path = target_root / "settings.json"
    _reject_symlinked_path(target_root, settings_path, label="settings")
    active = _read_json(settings_path) if settings_path.exists() else {}
    merged = _merge_settings(active, canonical)
    settings_changed = merged != active

    changed_assets: list[tuple[Path, Path]] = []
    asset_pairs = list(_asset_pairs(source_root, target_root))
    for source, target in asset_pairs:
        if not source.exists():
            raise InstallError(f"missing source asset: {source}")
        if not target.exists() or target.read_bytes() != source.read_bytes():
            _reject_symlinked_path(target_root, target, label="asset")
            changed_assets.append((source, target))
    retired_assets = [
        target_root / relative
        for relative in RETIRED_ASSETS
        if (target_root / relative).exists() or (target_root / relative).is_symlink()
    ]
    for target in retired_assets:
        _reject_symlinked_path(target_root, target, label="retired asset")
        if not target.is_file():
            raise InstallError(f"refusing unsafe retired asset: {target}")

    _verify_registered_assets(
        merged,
        target_root,
        set() if check else {target for _source, target in asset_pairs},
    )
    if check:
        if settings_changed or changed_assets or retired_assets:
            raise InstallError(
                f"Claude hook drift: settings={'yes' if settings_changed else 'no'}, "
                f"assets={len(changed_assets)}, retired={len(retired_assets)}"
            )
        return 0, False

    backup: Path | None = None
    if settings_changed and settings_path.exists():
        backup_dir = target_root / "backups" / "claude-config"
        backup = backup_dir / (
            f"settings-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
            f"-{time.time_ns()}.json"
        )
        _reject_symlinked_path(target_root, backup, label="backup")
    touched = [target for _source, target in changed_assets]
    if settings_changed:
        touched.append(settings_path)
    touched.extend(retired_assets)
    snapshots = _snapshot_files(touched)
    try:
        if backup is not None:
            _backup_file(settings_path, backup)
        for source, target in changed_assets:
            _copy_asset(source, target)
        if settings_changed:
            _atomic_json(settings_path, merged)
        for target in retired_assets:
            target.unlink()
    except Exception as exc:
        rollback_errors: list[str] = []
        try:
            _restore_files(snapshots)
        except Exception as rollback_exc:
            rollback_errors.append(f"profile: {rollback_exc}")
        if backup is not None:
            try:
                backup.unlink(missing_ok=True)
            except Exception as backup_exc:
                rollback_errors.append(f"backup: {backup_exc}")
        if rollback_errors:
            raise InstallError(
                f"install failed ({exc}); rollback failed ({'; '.join(rollback_errors)})"
            ) from exc
        raise InstallError(f"install failed and was rolled back: {exc}") from exc
    return len(changed_assets), settings_changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--target", type=Path, default=Path.home() / ".claude")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        assets, settings_changed = install(
            args.source.expanduser().resolve(),
            args.target.expanduser().absolute(),
            check=args.check,
        )
    except InstallError as exc:
        parser.error(str(exc))
    if args.check:
        print("Claude hooks: aligned")
    else:
        print(f"Claude hooks: assets_updated={assets} settings_updated={'yes' if settings_changed else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
