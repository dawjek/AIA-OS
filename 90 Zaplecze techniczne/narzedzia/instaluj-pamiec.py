#!/usr/bin/env python3
"""Dodaj lub usuń tylko własny SessionStart w lokalnych ustawieniach Codex/Claude."""

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from memory_core import Memory, MemoryProblem, atomic_write, json_bytes, read_bytes, safe_path


MARKER = "aia-os-memory-v1"
SETTINGS = {"codex": ".codex/hooks.json", "claude": ".claude/settings.json"}


def hook_command(root, runtime):
    script = root / "90 Zaplecze techniczne/narzedzia/pamiec-start.py"
    words = [sys.executable, str(script), "--root", str(root), "--runtime", runtime,
             "--memory-hook-id", MARKER]
    return subprocess.list2cmdline(words) if os.name == "nt" else shlex.join(words)


def own_handler(root, runtime):
    if runtime == "claude":
        script = root / "90 Zaplecze techniczne/narzedzia/pamiec-start.py"
        return {"type": "command", "command": sys.executable,
                "args": [str(script), "--root", str(root), "--runtime", runtime,
                         "--memory-hook-id", MARKER]}
    handler = {"type": "command", "command": hook_command(root, runtime),
               "additionalContextLimit": 0}
    if os.name == "nt":
        handler["commandWindows"] = hook_command(root, runtime)
    return handler


def is_own_handler(handler):
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    args = handler.get("args")
    if isinstance(args, list) and len(args) >= 2:
        return any(args[index:index + 2] == ["--memory-hook-id", MARKER]
                   for index in range(len(args) - 1))
    command = handler.get("command")
    return isinstance(command, str) and "--memory-hook-id " + MARKER in command


def load_settings(root, runtime):
    path = safe_path(root, SETTINGS[runtime])
    if not path.exists():
        return path, {}
    try:
        data = json.loads(read_bytes(path, 256_000))
    except (ValueError, UnicodeError):
        raise MemoryProblem("invalid_settings", "Ustawienia hooków nie są poprawnym JSON.") from None
    if not isinstance(data, dict):
        raise MemoryProblem("invalid_settings", "Ustawienia hooków muszą być obiektem JSON.")
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        raise MemoryProblem("invalid_settings", "Pole hooks musi być obiektem JSON.")
    return path, data


def remove_own_handler(data):
    hooks = data.get("hooks")
    if hooks is None:
        return data
    groups = hooks.get("SessionStart", [])
    if not isinstance(groups, list):
        raise MemoryProblem("invalid_settings", "SessionStart musi być listą.")
    kept = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            raise MemoryProblem("invalid_settings", "Nieprawidłowy wpis SessionStart.")
        remaining = []
        for handler in group["hooks"]:
            if not isinstance(handler, dict):
                raise MemoryProblem("invalid_settings", "Nieprawidłowy handler SessionStart.")
            if not is_own_handler(handler):
                remaining.append(handler)
        if remaining:
            kept.append({**group, "hooks": remaining})
    if kept:
        hooks["SessionStart"] = kept
    else:
        hooks.pop("SessionStart", None)
    return data


def count_own_handlers(data):
    hooks = data.get("hooks", {})
    groups = hooks.get("SessionStart", [])
    if not isinstance(groups, list):
        raise MemoryProblem("invalid_settings", "SessionStart musi być listą.")
    return sum(1 for group in groups if isinstance(group, dict)
               for handler in group.get("hooks", []) if is_own_handler(handler))


def install_one(data, root, runtime):
    remove_own_handler(data)
    hooks = data.setdefault("hooks", {})
    hooks.setdefault("SessionStart", []).append({
        "matcher": "startup|resume|clear|compact|fork" if runtime == "claude"
        else "startup|resume|clear|compact", "hooks": [own_handler(root, runtime)]})
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--runtime", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("command", choices=("install", "status", "uninstall"))
    args = parser.parse_args()
    try:
        root = Memory(args.root).root
        runtimes = ("codex", "claude") if args.runtime == "both" else (args.runtime,)
        prepared = []
        for runtime in runtimes:
            path, data = load_settings(root, runtime)
            if args.command == "status":
                prepared.append((runtime, path, data, None))
                continue
            old = json.dumps(data, ensure_ascii=False, sort_keys=True)
            if args.command == "install":
                new = install_one(data, root, runtime)
            else:
                new = remove_own_handler(data)
            prepared.append((runtime, path, new,
                             json_bytes(new) if json.dumps(new, ensure_ascii=False, sort_keys=True) != old else None))
        if args.command == "status":
            result = {"status": "ok"}
            for runtime, _, data, _ in prepared:
                result[runtime] = {"configured": count_own_handlers(data) == 1,
                                   "execution_confirmed": False,
                                   "trust_confirmed": False}
        else:
            for _, path, _, raw in prepared:
                if raw is not None:
                    atomic_write(path, raw)
            result = {"status": "ok", "action": args.command,
                      "runtimes": list(runtimes), "trust_changed": False}
    except MemoryProblem as error:
        result = {"status": "unavailable", "reason": error.reason, "message": str(error)}
    except OSError:
        result = {"status": "unavailable", "reason": "io_error",
                  "message": "Nie można bezpiecznie odczytać lub zapisać ustawień hooków."}
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["status"] == "unavailable" else 0


if __name__ == "__main__":
    sys.exit(main())
