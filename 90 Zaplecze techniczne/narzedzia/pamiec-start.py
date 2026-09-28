#!/usr/bin/env python3
"""SessionStart: przygotuj i przekaż zweryfikowany lokalny kontekst."""

import argparse
import json
from pathlib import Path
import sys

from memory_core import Memory, MemoryProblem, read_bytes, safe_path


MAX_EVENT_BYTES = 256_000


def output_context(context):
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": context}}


def run(root, event, runtime):
    if not isinstance(event, dict) or event.get("hook_event_name", "SessionStart") != "SessionStart":
        return output_context("AIA-OS: status=unavailable; nieznane zdarzenie hooka.")
    sources = ("startup", "resume", "clear", "compact", "fork") if runtime == "claude" \
        else ("startup", "resume", "clear", "compact")
    if event.get("source") not in sources:
        return output_context("AIA-OS: status=unavailable; nieznane źródło uruchomienia sesji.")
    cwd = event.get("cwd")
    if not isinstance(cwd, str):
        return output_context("AIA-OS: status=unavailable; nieznany folder sesji.")
    try:
        current = Path(cwd).resolve()
        current.relative_to(root)
    except (OSError, ValueError):
        return output_context("AIA-OS: status=unavailable; sesja jest poza tym systemem.")
    memory = Memory(root)
    try:
        built = memory.build()
        if built["status"] == "empty":
            return output_context("AIA-OS: status=empty. Dokończ onboarding i zapisz własne źródła przed użyciem pamięci.")
        status = memory.status()
        if status["status"] != "ready" or status.get("revision") != built["revision"]:
            return output_context("AIA-OS: status=unavailable; pakiet nie przeszedł kontroli po zapisie. Odczytaj źródła bezpośrednio.")
        config = memory.config()
        packet = read_bytes(safe_path(memory.root, config["output"]), config["max_context_bytes"])
        return output_context("AIA-OS: status=ready; revision=" + built["revision"] +
                              ". Pakiet przygotowano z lokalnych źródeł. Odczyt i użycie przez model "
                              "wymaga potwierdzenia w rozmowie.\n\n" + packet.decode("utf-8"))
    except (MemoryProblem, OSError, UnicodeError):
        return output_context("AIA-OS: status=unavailable; aktualnego pakietu nie potwierdzono. "
                              "Nie używaj wcześniejszego pakietu jako bieżącego; odczytaj źródła bezpośrednio.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--runtime", choices=("codex", "claude"), required=True)
    parser.add_argument("--memory-hook-id", default="aia-os-memory-v1")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError("event too large")
        event = json.loads(raw)
        result = run(root, event, args.runtime)
    except (ValueError, UnicodeError, OSError, MemoryProblem):
        result = output_context("AIA-OS: status=unavailable; nie można odczytać zdarzenia lub pamięci.")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
