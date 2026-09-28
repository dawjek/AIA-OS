#!/usr/bin/env python3
"""Lista, odczyt i bezpieczny checkpoint lokalnego projektu."""

import argparse
import json
from pathlib import Path
import sys

from memory_core import Memory, MemoryProblem


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    show = commands.add_parser("show")
    show.add_argument("project")
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("project")
    checkpoint.add_argument("--input", required=True)
    checkpoint.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        memory = Memory(args.root)
        if args.command == "list":
            result = memory.project_list()
        elif args.command == "show":
            result = memory.project_show(args.project)
        else:
            if args.input != "-":
                raise MemoryProblem("invalid_input", "Checkpoint czyta JSON ze standardowego wejścia (--input -).")
            raw = sys.stdin.buffer.read(128_001)
            if len(raw) > 128_000:
                raise MemoryProblem("invalid_payload", "Checkpoint przekracza limit wejścia.")
            try:
                payload = json.loads(raw)
            except (ValueError, UnicodeError):
                raise MemoryProblem("invalid_payload", "Nieprawidłowy JSON checkpointu.") from None
            result = memory.checkpoint(payload, check_only=args.check_only, project=args.project)
    except MemoryProblem as error:
        result = {"status": "rejected" if error.reason in ("secret_detected", "invalid_payload")
                  else "unavailable", "reason": error.reason, "message": str(error)}
    except OSError:
        result = {"status": "unavailable", "reason": "io_error",
                  "message": "Nie można bezpiecznie odczytać lub zapisać pamięci."}
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["status"] in ("unavailable", "conflict", "rejected") else 0


if __name__ == "__main__":
    sys.exit(main())
