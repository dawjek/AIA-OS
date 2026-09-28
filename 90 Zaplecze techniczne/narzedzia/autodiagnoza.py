#!/usr/bin/env python3
"""Lokalna kolejka korekt AI i potwierdzony zapis do lokalnego rejestru."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid

from memory_core import (Memory, MemoryProblem, atomic_write, contains_secret,
                         json_bytes, local_lock, read_bytes, safe_path, sha)


QUEUE = "01 Zarząd/Autodiagnoza pracy AI/kolejka"
REGISTER = "01 Zarząd/Autodiagnoza pracy AI/REJESTR.md"
EVENT_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


def read_payload():
    raw = sys.stdin.buffer.read(64_001)
    if len(raw) > 64_000:
        raise MemoryProblem("invalid_payload", "Wejście przekracza limit.")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise MemoryProblem("invalid_payload", "Nieprawidłowy JSON.") from None


def event_path(root, identifier):
    if not isinstance(identifier, str) or not EVENT_ID.fullmatch(identifier):
        raise MemoryProblem("invalid_payload", "Nieprawidłowy event_id.")
    return safe_path(root, QUEUE + "/" + identifier + ".json")


def checked_text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise MemoryProblem("invalid_payload", field + " musi mieć 1–4000 znaków.")
    if "<!-- aia-os-diagnosis:" in value:
        raise MemoryProblem("invalid_payload", "Treść zawiera zastrzeżony znacznik.")
    if contains_secret(value):
        raise MemoryProblem("secret_detected", "Treść zawiera możliwy sekret.")
    return value


def load_event(path):
    try:
        event = json.loads(read_bytes(path, 32_000))
    except (ValueError, UnicodeError):
        raise MemoryProblem("invalid_queue", "Nieprawidłowy plik kolejki.") from None
    if not isinstance(event, dict) or event.get("schema_version") != 1 \
            or event.get("status") not in ("pending", "recorded") \
            or not isinstance(event.get("event_id"), str):
        raise MemoryProblem("invalid_queue", "Nieprawidłowy wpis kolejki.")
    try:
        if not EVENT_ID.fullmatch(event["event_id"]):
            raise ValueError("invalid ID")
        content = {key: event[key] for key in ("event_id", "observation", "evidence", "correction")}
        for key in ("observation", "evidence", "correction"):
            checked_text(content[key], key)
        if sha(json_bytes(content)) != event.get("payload_sha256"):
            raise ValueError("changed payload")
        if event["status"] == "recorded":
            checked_text(event.get("outcome"), "outcome")
    except (KeyError, ValueError, MemoryProblem):
        raise MemoryProblem("invalid_queue", "Wpis kolejki zmienił się lub jest niepełny.") from None
    return event


def enqueue(root, payload):
    required = {"event_id", "observation", "evidence", "correction"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise MemoryProblem("invalid_payload", "Wpis wymaga event_id, observation, evidence i correction.")
    path = event_path(root, payload["event_id"])
    for key in ("observation", "evidence", "correction"):
        checked_text(payload[key], key)
    content_hash = sha(json_bytes(payload))
    with local_lock(root):
        if path.is_file():
            existing = load_event(path)
            if existing.get("payload_sha256") != content_hash:
                return {"status": "conflict", "reason": "event_id_reused", "event_id": payload["event_id"]}
            return {"status": "ok", "event_id": payload["event_id"],
                    "idempotent": True, "queue_saved": False, "revision": sha(read_bytes(path))}
        event = {"schema_version": 1, "status": "pending", **payload,
                 "payload_sha256": content_hash,
                 "queued_at": datetime.now(timezone.utc).isoformat()}
        atomic_write(path, json_bytes(event))
        return {"status": "ok", "event_id": payload["event_id"],
                "idempotent": False, "queue_saved": True, "revision": sha(read_bytes(path))}


def listing(root):
    folder = safe_path(root, QUEUE)
    if not folder.is_dir():
        return {"status": "ok", "items": []}
    items = []
    for path in sorted(folder.glob("*.json")):
        if path.is_symlink():
            raise MemoryProblem("invalid_queue", "Kolejka zawiera dowiązanie symboliczne.")
        event = load_event(path)
        items.append({"event_id": event["event_id"], "status": event["status"],
                      "observation": event["observation"], "revision": sha(read_bytes(path))})
    return {"status": "ok", "items": items}


def record(root, payload):
    if not isinstance(payload, dict) or set(payload) != {"event_id", "expected_revision", "outcome"}:
        raise MemoryProblem("invalid_payload", "Zapis wymaga event_id, expected_revision i outcome.")
    path = event_path(root, payload["event_id"])
    expected = payload["expected_revision"]
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise MemoryProblem("invalid_payload", "expected_revision musi być SHA-256 wpisu kolejki.")
    outcome = checked_text(payload["outcome"], "outcome")
    register_path = safe_path(root, REGISTER)
    with local_lock(root):
        queued_raw = read_bytes(path, 32_000, "missing_event")
        event = load_event(path)
        if event["event_id"] != payload["event_id"]:
            raise MemoryProblem("invalid_queue", "ID pliku kolejki nie zgadza się z treścią.")
        outcome_hash = sha(json_bytes({"event_id": event["event_id"], "outcome": outcome}))
        marker_prefix = "<!-- aia-os-diagnosis:" + event["event_id"] + ":"
        marker = marker_prefix + outcome_hash + " -->"
        if event["status"] == "recorded":
            if event.get("outcome") != outcome:
                return {"status": "conflict", "reason": "event_id_reused", "event_id": event["event_id"]}
            registered = read_bytes(register_path, 1_000_000, "missing_register")
            if marker.encode("utf-8") not in registered:
                return {"status": "unavailable", "reason": "register_unverified",
                        "event_id": event["event_id"], "register_verified": False}
            return {"status": "ok", "event_id": event["event_id"], "idempotent": True,
                    "register_verified": True}
        if sha(queued_raw) != expected:
            return {"status": "conflict", "reason": "revision_changed", "event_id": event["event_id"],
                    "revision": sha(queued_raw)}
        register_raw = read_bytes(register_path, 1_000_000, "missing_register")
        register_text = register_raw.decode("utf-8")
        if marker_prefix in register_text and marker not in register_text:
            return {"status": "conflict", "reason": "register_has_other_outcome",
                    "event_id": event["event_id"]}
        if marker not in register_text:
            entry = (("\n" if register_text.endswith("\n") else "\n\n") + marker +
                     "\n\n## Korekta " + event["event_id"] + "\n\n" +
                     "**Obserwacja:** " + event["observation"] + "\n\n" +
                     "**Dowód:** " + event["evidence"] + "\n\n" +
                     "**Korekta:** " + event["correction"] + "\n\n" +
                     "**Wynik:** " + outcome + "\n")
            new_register = (register_text + entry).encode("utf-8")
            if len(new_register) > 1_000_000:
                raise MemoryProblem("register_too_large", "Rejestr przekroczył limit odczytu.")
            retained = safe_path(root, ".ai/synchronizacja/pamiec/retencja/autodiagnoza/" +
                                 datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") +
                                 "-" + uuid.uuid4().hex + ".md")
            atomic_write(retained, register_raw)
            if read_bytes(register_path) != register_raw:
                return {"status": "conflict", "reason": "register_changed", "event_id": event["event_id"]}
            atomic_write(register_path, new_register)
        verified = read_bytes(register_path)
        if marker.encode("utf-8") not in verified:
            return {"status": "unavailable", "reason": "register_unverified", "event_id": event["event_id"]}
        event.update({"status": "recorded", "outcome": outcome,
                      "register_revision": sha(verified),
                      "recorded_at": datetime.now(timezone.utc).isoformat()})
        atomic_write(path, json_bytes(event))
        return {"status": "ok", "event_id": event["event_id"], "idempotent": False,
                "register_verified": True, "revision": sha(read_bytes(path))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    for name in ("enqueue", "record"):
        command = commands.add_parser(name)
        command.add_argument("--input", required=True)
    args = parser.parse_args()
    try:
        root = Memory(args.root).root
        if args.command == "list":
            result = listing(root)
        else:
            if args.input != "-":
                raise MemoryProblem("invalid_input", "Dane JSON należy przekazać na standardowe wejście (--input -).")
            payload = read_payload()
            result = enqueue(root, payload) if args.command == "enqueue" else record(root, payload)
    except MemoryProblem as error:
        result = {"status": "rejected" if error.reason in ("invalid_payload", "secret_detected")
                  else "unavailable", "reason": error.reason, "message": str(error)}
    except (OSError, UnicodeError):
        result = {"status": "unavailable", "reason": "io_error",
                  "message": "Nie można bezpiecznie odczytać lub zapisać lokalnej korekty."}
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["status"] in ("unavailable", "rejected", "conflict") else 0


if __name__ == "__main__":
    sys.exit(main())
