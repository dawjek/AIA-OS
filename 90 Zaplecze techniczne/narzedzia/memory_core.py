"""Przenośna, plikowa pamięć startera. Bez usług i zależności zewnętrznych."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import time
import unicodedata
import uuid


STATE_DIR = ".ai/synchronizacja/pamiec"
PRIVATE_OUTPUT = "05 Wiedza/Kontekst/pakiet-startowy.md"
PRIVATE_MANIFEST = STATE_DIR + "/manifest.json"
PRIVATE_CHECKPOINT = "05 Wiedza/Kontekst/stan-rozmowy.md"
PRIVATE_PROJECT_PARENTS = (
    "01 Zarząd/Karty projektów",
    "02 Klienci",
    "03 Nasza firma/Projekty własne",
)
MAX_SOURCE_BYTES = 1_000_000
MAX_CONFIG_BYTES = 64_000
BEGIN = "<!-- aia-os-checkpoint:begin -->"
END = "<!-- aia-os-checkpoint:end -->"
DENIED_PARTS = {".git", ".codex", ".claude", "node_modules", "__pycache__",
                "secrets", "secret", "credentials", "sessions", "cache", "retencja",
                "archive", "archiwum"}
SECRET_PATTERNS = (
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b",
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
    r"(?i)(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{16,}",
)


class MemoryProblem(Exception):
    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def normalized(value):
    text = unicodedata.normalize("NFKD", value.casefold().replace("ł", "l"))
    return "".join(char for char in text if not unicodedata.combining(char))


def contains_secret(text):
    return any(re.search(pattern, text) for pattern in SECRET_PATTERNS)


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise MemoryProblem("invalid_path", "Ścieżka musi być względna wobec głównego folderu.")
    if any(ord(char) < 32 for char in value):
        raise MemoryProblem("invalid_path", "Ścieżka zawiera niedozwolone znaki.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise MemoryProblem("invalid_path", "Ścieżka wychodzi poza główny folder.")
    return value


def denied_path(value):
    parts = PurePosixPath(value).parts
    return any(normalized(part) in DENIED_PARTS or part.lower().startswith(".env")
               for part in parts)


def safe_path(root, value):
    relative_path(value)
    path = root
    for part in PurePosixPath(value).parts:
        path = path / part
        if path.is_symlink():
            raise MemoryProblem("unsafe_path", "Źródło lub jego katalog jest dowiązaniem symbolicznym.")
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except ValueError:
        raise MemoryProblem("unsafe_path", "Ścieżka wychodzi poza główny folder.") from None
    if resolved != path.absolute():
        raise MemoryProblem("unsafe_path", "Ścieżka wskazuje alias innego pliku lub katalogu.")
    return path


def read_bytes(path, limit=MAX_SOURCE_BYTES, missing_reason="missing_source"):
    try:
        if path.is_symlink():
            raise MemoryProblem("unsafe_path", "Odmowa odczytu dowiązania symbolicznego.")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise MemoryProblem("unavailable_source", "Wymagany jest zwykły plik.")
        if info.st_size > limit:
            raise MemoryProblem("source_too_large", "Plik przekracza limit odczytu; treść nie została skrócona.")
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise MemoryProblem("source_too_large", "Plik przekracza limit odczytu; treść nie została skrócona.")
        return raw
    except FileNotFoundError:
        raise MemoryProblem(missing_reason, "Brakuje wskazanego pliku.") from None
    except OSError:
        raise MemoryProblem("unavailable_source", "Nie można odczytać wskazanego pliku.") from None


def decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeError:
        raise MemoryProblem("invalid_encoding", "Plik musi być zapisany jako UTF-8.") from None


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise MemoryProblem("unsafe_path", "Odmowa nadpisania dowiązania symbolicznego.")
    descriptor, temporary = tempfile.mkstemp(prefix=".aia-os-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise MemoryProblem("unsafe_path", "Odmowa nadpisania dowiązania symbolicznego.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def local_lock(root):
    """Przenośna blokada kooperujących procesów przez wyłączny plik."""
    path = safe_path(root, STATE_DIR + "/memory.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 3.0
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise MemoryProblem("busy", "Pamięć jest zajęta; spróbuj ponownie lub sprawdź blokadę.") from None
            time.sleep(0.05)
        except OSError:
            raise MemoryProblem("unavailable_state", "Nie można założyć lokalnej blokady.") from None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


class Memory:
    def __init__(self, root):
        candidate = Path(root).expanduser()
        if candidate.is_symlink() or not candidate.is_dir():
            raise MemoryProblem("invalid_root", "Wskaż istniejący główny folder bez dowiązania.")
        self.root = candidate.resolve()

    def _config(self):
        path = safe_path(self.root, ".ai/memory.json")
        if not path.exists():
            path = safe_path(self.root, ".ai/memory.template.json")
        raw = read_bytes(path, MAX_CONFIG_BYTES, "missing_config")
        try:
            config = json.loads(raw)
        except (ValueError, UnicodeError):
            raise MemoryProblem("invalid_config", "Nieprawidłowy plik .ai/memory.json.") from None
        if not isinstance(config, dict) or config.get("schema_version") != 1:
            raise MemoryProblem("invalid_config", "Nieobsługiwana wersja konfiguracji pamięci.")
        if type(config.get("configured")) is not bool:
            raise MemoryProblem("invalid_config", "Pole configured musi mieć wartość true lub false.")
        maximum = config.get("max_context_bytes")
        if type(maximum) is not int or not 1024 <= maximum <= 100_000:
            raise MemoryProblem("invalid_config", "max_context_bytes musi wynosić 1024–100000.")
        sources = config.get("sources")
        if not isinstance(sources, list) or not sources or len(sources) > 32:
            raise MemoryProblem("invalid_config", "sources wymaga od 1 do 32 wpisów.")
        paths = set()
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"path", "required"}:
                raise MemoryProblem("invalid_config", "Źródło wymaga path i required.")
            value = relative_path(source["path"])
            if denied_path(value) or value in paths or type(source["required"]) is not bool:
                raise MemoryProblem("invalid_config", "Nieprawidłowe lub powtórzone źródło.")
            paths.add(value)
        roots = config.get("search_roots")
        if not isinstance(roots, list) or len(roots) > 32:
            raise MemoryProblem("invalid_config", "search_roots musi być listą do 32 katalogów.")
        for value in roots:
            if denied_path(relative_path(value)):
                raise MemoryProblem("invalid_config", "Niedozwolony katalog wyszukiwania.")
        targets = [config.get(key) for key in ("checkpoint_path", "output", "manifest")]
        for value in targets:
            relative_path(value)
        if len(set(targets)) != 3 or config["output"] in paths or config["manifest"] in paths:
            raise MemoryProblem("invalid_config", "Ścieżki stanu, pakietu i manifestu muszą być rozłączne.")
        if (config["checkpoint_path"] != PRIVATE_CHECKPOINT or
                config["output"] != PRIVATE_OUTPUT or
                config["manifest"] != PRIVATE_MANIFEST):
            raise MemoryProblem("invalid_config", "Cele zapisu pamięci muszą używać prywatnych ścieżek startera.")
        for value in targets:
            target = safe_path(self.root, value)
            if target.is_file() and target.stat().st_nlink > 1:
                raise MemoryProblem("unsafe_path", "Cel zapisu jest aliasem innego pliku.")
        return config, sha(raw)

    def config(self):
        return self._config()[0]

    def checkpoint_revision(self, path):
        target = safe_path(self.root, path)
        if not target.exists():
            return None
        return sha(read_bytes(target))

    def _packet(self, config):
        if not config["configured"]:
            return {"status": "empty", "reason": "onboarding_not_finished"}
        parts = ["# Pakiet startowy\n\nŹródła poniżej są pełne i pochodzą z tej instalacji.\n"]
        entries = []
        meaningful = False
        for source in config["sources"]:
            relative = source["path"]
            path = safe_path(self.root, relative)
            try:
                raw = read_bytes(path)
            except MemoryProblem as error:
                if error.reason == "missing_source" and not source["required"]:
                    continue
                raise
            content = decode(raw)
            if contains_secret(content):
                raise MemoryProblem("secret_detected", "Wskazane źródło zawiera możliwy sekret; pakietu nie zapisano.")
            meaningful |= bool(content.strip())
            entries.append({"path": relative, "sha256": sha(raw), "bytes": len(raw)})
            parts.append(f"\n## Źródło: {relative}\nSHA-256: {sha(raw)}\n\n{content}")
            if not content.endswith("\n"):
                parts.append("\n")
        if not meaningful:
            return {"status": "empty", "reason": "sources_empty"}
        packet = "".join(parts).encode("utf-8")
        if len(packet) > config["max_context_bytes"]:
            raise MemoryProblem("limit_exceeded", "Pakiet przekracza max_context_bytes; źródeł nie skrócono.")
        return {"status": "ready", "packet": packet, "sources": entries,
                "bytes": len(packet), "revision": sha(packet)}

    def status(self):
        config, config_revision = self._config()
        result = {"status": "empty", "checkpoint_revision": self.checkpoint_revision(config["checkpoint_path"]),
                  "configured": config["configured"]}
        try:
            prepared = self._packet(config)
        except MemoryProblem as error:
            return dict(result, status="unavailable", reason=error.reason)
        if prepared["status"] == "empty":
            return dict(result, reason=prepared["reason"])
        output = safe_path(self.root, config["output"])
        manifest = safe_path(self.root, config["manifest"])
        if not output.is_file() or not manifest.is_file():
            return dict(result, status="stale", reason="build_required")
        try:
            raw_output = read_bytes(output)
            data = json.loads(read_bytes(manifest, MAX_CONFIG_BYTES))
        except (MemoryProblem, ValueError, UnicodeError):
            return dict(result, status="stale", reason="invalid_snapshot")
        expected = {"config_sha256": config_revision, "snapshot_sha256": prepared["revision"],
                    "sources": prepared["sources"], "bytes": prepared["bytes"]}
        if not isinstance(data, dict) or any(data.get(key) != value for key, value in expected.items()) \
                or raw_output != prepared["packet"]:
            return dict(result, status="stale", reason="source_changed")
        return dict(result, status="ready", revision=prepared["revision"],
                    bytes=prepared["bytes"], max_context_bytes=config["max_context_bytes"],
                    sources=prepared["sources"])

    def build(self):
        initial, _ = self._config()
        if not initial["configured"]:
            return {"status": "empty", "reason": "onboarding_not_finished"}
        with local_lock(self.root):
            config, config_revision = self._config()
            prepared = self._packet(config)
            if prepared["status"] == "empty":
                return {"status": "empty", "reason": prepared["reason"]}
            manifest = {"schema_version": 1, "status": "ready", "config_sha256": config_revision,
                        "snapshot_sha256": prepared["revision"], "bytes": prepared["bytes"],
                        "sources": prepared["sources"],
                        "built_at": datetime.now(timezone.utc).isoformat()}
            output_path = safe_path(self.root, config["output"])
            manifest_path = safe_path(self.root, config["manifest"])
            if not output_path.exists() or read_bytes(output_path) != prepared["packet"]:
                atomic_write(output_path, prepared["packet"])
            atomic_write(manifest_path, json_bytes(manifest))
            return {"status": "ready", "revision": prepared["revision"],
                    "bytes": prepared["bytes"], "sources": prepared["sources"]}

    def search(self, query):
        config, _ = self._config()
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise MemoryProblem("invalid_query", "Podaj zapytanie o długości 1–200 znaków.")
        needle = normalized(query.strip())
        matches, skipped = [], []
        seen = set()
        for relative in config["search_roots"]:
            folder = safe_path(self.root, relative)
            if not folder.is_dir():
                skipped.append({"path": relative, "reason": "missing_root"})
                continue
            for path in folder.rglob("*.md"):
                source = path.relative_to(self.root).as_posix()
                if source in seen or denied_path(source) or path.is_symlink():
                    continue
                seen.add(source)
                try:
                    content = decode(read_bytes(path))
                except MemoryProblem as error:
                    skipped.append({"path": source, "reason": error.reason})
                    continue
                if contains_secret(content):
                    skipped.append({"path": source, "reason": "secret_detected"})
                    continue
                for number, line in enumerate(content.splitlines(), start=1):
                    if needle in normalized(line):
                        matches.append({"path": source, "line": number, "text": line[:500]})
                        if len(matches) >= 50:
                            return {"status": "ok", "matches": matches, "skipped": skipped,
                                    "truncated_results": True}
        return {"status": "ok", "matches": matches, "skipped": skipped,
                "truncated_results": False}

    def registry(self):
        path = safe_path(self.root, ".ai/memory-projects.json")
        if not path.exists():
            path = safe_path(self.root, ".ai/memory-projects.template.json")
        raw = read_bytes(path, MAX_CONFIG_BYTES, "missing_registry")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise MemoryProblem("invalid_registry", "Nieprawidłowy rejestr projektów.") from None
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise MemoryProblem("invalid_registry", "Nieobsługiwana wersja rejestru projektów.")
        maximum = data.get("max_state_bytes", 12000)
        entries = data.get("projects")
        if type(maximum) is not int or not 1 <= maximum <= 100_000 \
                or not isinstance(entries, list) or len(entries) > 200:
            raise MemoryProblem("invalid_registry", "Nieprawidłowe limity lub lista projektów.")
        config, _ = self._config()
        protected = {".ai/memory.json", ".ai/memory.template.json",
                     ".ai/memory-projects.json", ".ai/memory-projects.template.json",
                     config["checkpoint_path"],
                     config["output"], config["manifest"]}
        protected.update(source["path"] for source in config["sources"])
        protected_keys = {value.casefold() for value in protected}
        protected_identity = set()
        for value in protected:
            path = safe_path(self.root, value)
            if path.is_file():
                info = path.stat()
                protected_identity.add((info.st_dev, info.st_ino))
        ids, targets, identities = set(), set(), set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"id", "name", "root", "state_path"}:
                raise MemoryProblem("invalid_registry", "Projekt wymaga id, name, root i state_path.")
            identifier = entry["id"]
            if not isinstance(identifier, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", identifier) \
                    or identifier in ids:
                raise MemoryProblem("invalid_registry", "Nieprawidłowe lub powtórzone ID projektu.")
            name = entry["name"]
            if not isinstance(name, str) or not name.strip() or len(name) > 200 \
                    or any(ord(char) < 32 for char in name):
                raise MemoryProblem("invalid_registry", "Nieprawidłowa nazwa projektu.")
            folder = relative_path(entry["root"])
            target = relative_path(entry["state_path"])
            private_folder = any(folder.casefold().startswith(parent.casefold() + "/")
                                 for parent in PRIVATE_PROJECT_PARENTS)
            if not private_folder or denied_path(folder) or denied_path(target) \
                    or not target.casefold().startswith(folder.casefold() + "/") \
                    or not target.lower().endswith(".md") or target.casefold() in protected_keys \
                    or PurePosixPath(target).name.casefold() in ("agents.md", "claude.md"):
                raise MemoryProblem("invalid_registry", "Stan projektu musi być plikiem Markdown wewnątrz projektu.")
            project_folder = safe_path(self.root, folder)
            state_file = safe_path(self.root, target)
            if not project_folder.is_dir() or not state_file.is_file():
                raise MemoryProblem("invalid_registry", "Brakuje folderu lub dokumentu stanu projektu.")
            key = target.casefold()
            info = state_file.stat()
            identity = (info.st_dev, info.st_ino)
            if key in targets or identity in identities or identity in protected_identity \
                    or info.st_nlink > 1:
                raise MemoryProblem("invalid_registry", "Dwa projekty wskazują ten sam dokument stanu.")
            ids.add(identifier)
            targets.add(key)
            identities.add(identity)
        return data, sha(raw)

    def project_list(self):
        registry, _ = self.registry()
        return {"status": "ok", "projects": [
            {"id": entry["id"], "name": entry["name"], "root": entry["root"],
             "source": entry["state_path"]} for entry in registry["projects"]]}

    def project_entry(self, identifier):
        registry, revision = self.registry()
        for entry in registry["projects"]:
            if entry["id"] == identifier:
                return registry, revision, entry
        raise MemoryProblem("unknown_project", "Nieznane ID projektu.")

    def project_show(self, identifier):
        _, _, entry = self.project_entry(identifier)
        raw = read_bytes(safe_path(self.root, entry["state_path"]))
        body, _ = parse_checkpoint_block(decode(raw))
        if body and contains_secret(body):
            raise MemoryProblem("secret_detected", "Stan projektu zawiera możliwy sekret.")
        return {"status": "ok" if body else "empty", "project_id": identifier,
                "name": entry["name"], "source": entry["state_path"],
                "revision": sha(raw), "state": body}

    def checkpoint(self, payload, check_only=False, project=None):
        if check_only:
            return self._checkpoint_prepared(payload, project)["result"] | {"check_only": True}
        with local_lock(self.root):
            prepared = self._checkpoint_prepared(payload, project)
            result = prepared["result"]
            if result["status"] != "ok" or result.get("idempotent"):
                if prepared.get("repair_receipt"):
                    try:
                        atomic_write(prepared["receipt_path"], json_bytes(prepared["receipt"]))
                    except OSError:
                        return dict(result, status="unavailable", reason="receipt_failed",
                                    checkpoint_saved=True, event_recorded=False)
                return result
            target = prepared["target"]
            current = prepared["current"]
            if self._read_optional(target) != current:
                return dict(result, status="conflict", reason="revision_changed",
                            checkpoint_saved=False)
            if project is not None and self.registry()[1] != prepared["registry_revision"]:
                return dict(result, status="conflict", reason="registry_changed",
                            checkpoint_saved=False)
            if current is not None:
                retained = safe_path(self.root, STATE_DIR + "/retencja/" +
                                     (project if project is not None else "global") + "/" +
                                     datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") +
                                     "-" + uuid.uuid4().hex + ".md")
                atomic_write(retained, current)
            if self._read_optional(target) != current:
                return dict(result, status="conflict", reason="revision_changed",
                            checkpoint_saved=False)
            try:
                atomic_write(target, prepared["candidate"])
            except OSError:
                return dict(result, status="unavailable", reason="write_failed",
                            checkpoint_saved=False)
            try:
                atomic_write(prepared["receipt_path"], json_bytes(prepared["receipt"]))
            except OSError:
                return dict(result, status="unavailable", reason="receipt_failed",
                            checkpoint_saved=True, event_recorded=False,
                            revision=sha(prepared["candidate"]))
            return dict(result, checkpoint_saved=True, event_recorded=True,
                        revision=sha(prepared["candidate"]))

    def _read_optional(self, path):
        if not path.exists():
            return None
        return read_bytes(path)

    def _checkpoint_prepared(self, payload, project):
        content_hash = self._validate_payload(payload, project)
        config, _ = self._config()
        registry_revision = None
        if project is None:
            relative = config["checkpoint_path"]
            limit = config.get("max_checkpoint_bytes", 12000)
            if type(limit) is not int or not 1 <= limit <= 100_000:
                raise MemoryProblem("invalid_config", "max_checkpoint_bytes musi wynosić 1–100000.")
            namespace = "global"
        else:
            registry, registry_revision, entry = self.project_entry(project)
            relative = entry["state_path"]
            limit = registry.get("max_state_bytes", 12000)
            namespace = project
        target = safe_path(self.root, relative)
        current = self._read_optional(target)
        revision = sha(current) if current is not None else None
        body, metadata = parse_checkpoint_block(decode(current)) if current is not None else (None, None)
        receipt_path = safe_path(self.root, STATE_DIR + "/events/" + namespace + "/" +
                                 sha(payload["event_id"].encode("utf-8")) + ".json")
        receipt = None
        if receipt_path.is_file():
            try:
                receipt = json.loads(read_bytes(receipt_path, 5000))
            except (ValueError, UnicodeError):
                raise MemoryProblem("invalid_receipt", "Nieprawidłowe potwierdzenie zdarzenia.") from None
            if not isinstance(receipt, dict) or set(receipt) != {"event_id", "payload_sha256", "revision"}:
                raise MemoryProblem("invalid_receipt", "Nieprawidłowy format potwierdzenia zdarzenia.")
        if receipt is not None or metadata is not None and metadata.get("event_id") == payload["event_id"]:
            source = receipt if receipt is not None else metadata
            if source["payload_sha256"] != content_hash:
                return {"result": {"status": "conflict", "reason": "event_id_reused",
                                   "source": relative, "revision": revision, "checkpoint_saved": False}}
            event_revision = receipt["revision"] if receipt is not None else revision
            new_receipt = {"event_id": payload["event_id"], "payload_sha256": content_hash,
                           "revision": event_revision}
            return {"result": {"status": "ok", "source": relative, "revision": revision,
                               "event_revision": event_revision, "idempotent": True,
                               "checkpoint_saved": False},
                    "repair_receipt": receipt is None, "receipt_path": receipt_path,
                    "receipt": new_receipt}
        if payload["expected_revision"] != revision:
            return {"result": {"status": "conflict", "reason": "revision_changed",
                               "source": relative, "revision": revision, "checkpoint_saved": False}}
        for source in payload["sources"]:
            if not safe_path(self.root, source).is_file():
                raise MemoryProblem("invalid_payload", "Źródło checkpointu musi być istniejącym plikiem w systemie.")
        rendered = render_checkpoint(payload, content_hash)
        if len(rendered.encode("utf-8")) > limit:
            return {"result": {"status": "rejected", "reason": "state_limit_exceeded",
                               "source": relative, "revision": revision, "checkpoint_saved": False}}
        text = decode(current) if current is not None else ""
        candidate = replace_checkpoint_block(text, rendered).encode("utf-8")
        if len(candidate) > MAX_SOURCE_BYTES:
            return {"result": {"status": "rejected", "reason": "document_too_large",
                               "source": relative, "revision": revision, "checkpoint_saved": False}}
        new_revision = sha(candidate)
        new_receipt = {"event_id": payload["event_id"], "payload_sha256": content_hash,
                       "revision": new_revision}
        return {"result": {"status": "ok", "source": relative, "revision": revision,
                           "candidate_revision": new_revision, "idempotent": False,
                           "checkpoint_saved": False},
                "target": target, "current": current, "candidate": candidate,
                "receipt_path": receipt_path, "receipt": new_receipt,
                "registry_revision": registry_revision}

    def _validate_payload(self, payload, project):
        required = {"event_id", "expected_revision", "summary", "done", "next", "sources"}
        if project is not None:
            required.add("project")
        if not isinstance(payload, dict) or set(payload) != required:
            raise MemoryProblem("invalid_payload", "Checkpoint wymaga event_id, expected_revision, summary, done, next i sources.")
        identifier = payload["event_id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier):
            raise MemoryProblem("invalid_payload", "Nieprawidłowy event_id.")
        expected = payload["expected_revision"]
        if expected is not None and (not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)):
            raise MemoryProblem("invalid_payload", "expected_revision musi być SHA-256 lub null.")
        if project is not None and payload["project"] != project:
            raise MemoryProblem("invalid_payload", "Pole project musi wskazywać wybrany projekt.")
        summary = payload["summary"]
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 5000:
            raise MemoryProblem("invalid_payload", "Podsumowanie musi mieć 1–5000 znaków.")
        for key in ("done", "next", "sources"):
            items = payload[key]
            if not isinstance(items, list) or len(items) > 20 or any(
                    not isinstance(item, str) or not item.strip() or len(item) > 1000 for item in items):
                raise MemoryProblem("invalid_payload", "Pola done, next i sources są listami do 20 wpisów.")
        contents = [summary, *payload["done"], *payload["next"], *payload["sources"]]
        if any(BEGIN in item or END in item for item in contents):
            raise MemoryProblem("invalid_payload", "Treść zawiera zastrzeżony znacznik stanu.")
        if contains_secret("\n".join(contents)):
            raise MemoryProblem("secret_detected", "Checkpoint zawiera możliwy sekret.")
        for source in payload["sources"]:
            if denied_path(relative_path(source)):
                raise MemoryProblem("invalid_payload", "Niedozwolona ścieżka źródła checkpointu.")
        relevant = {key: payload[key] for key in sorted(required - {"expected_revision"})}
        return sha(json_bytes(relevant))


def parse_checkpoint_block(text):
    if BEGIN not in text and END not in text:
        return None, None
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        raise MemoryProblem("invalid_block", "Stan zawiera uszkodzony lub powtórzony znacznik.")
    body = text[text.index(BEGIN) + len(BEGIN):text.index(END)].strip("\n")
    lines = body.splitlines()
    if not lines or not lines[0].startswith("<!-- meta: ") or not lines[0].endswith(" -->"):
        raise MemoryProblem("invalid_block", "Brakuje metadanych checkpointu.")
    try:
        metadata = json.loads(lines[0][11:-4])
    except ValueError:
        raise MemoryProblem("invalid_block", "Nieprawidłowe metadane checkpointu.") from None
    if not isinstance(metadata, dict) or set(metadata) != {"event_id", "payload_sha256"}:
        raise MemoryProblem("invalid_block", "Nieprawidłowe metadane checkpointu.")
    return body, metadata


def replace_checkpoint_block(text, block):
    parse_checkpoint_block(text)
    if BEGIN not in text:
        separator = "\n" if text.endswith("\n") or not text else "\n\n"
        return text + separator + BEGIN + "\n" + block + "\n" + END + "\n"
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    return text[:start] + BEGIN + "\n" + block + "\n" + END + text[end:]


def render_checkpoint(payload, content_hash):
    meta = json.dumps({"event_id": payload["event_id"], "payload_sha256": content_hash},
                      ensure_ascii=False, sort_keys=True)
    lines = ["<!-- meta: " + meta + " -->", "", "## Ostatni sprawdzony stan", "", payload["summary"]]
    for field, heading in (("done", "Wykonane"), ("next", "Następne kroki"),
                           ("sources", "Źródła")):
        lines.extend(["", "### " + heading, ""])
        lines.extend("- " + item.replace("\n", "\n  ") for item in payload[field])
        if not payload[field]:
            lines.append("Brak wpisów.")
    return "\n".join(lines)
