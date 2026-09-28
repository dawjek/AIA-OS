#!/usr/bin/env python3
"""Verify and bundle only the public AIA-OS starter files."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent
ALLOWED_ROOT_FILES = {
    "AGENTS.md", "CLAUDE.md", "README.md", "START.md", "polaczenia.template.md",
    ".gitignore", "LICENSE", "PUBLIC_FILES.json",
}
ALLOWED_DIRECTORIES = {
    ".ai", ".agents", ".claude", "01 Zarząd", "02 Klienci", "03 Nasza firma",
    "04 Warsztat", "05 Wiedza", "90 Zaplecze techniczne", "output", "outputs", "qa",
    "tools",
}
FORBIDDEN_PARTS = {".git", ".codex", "node_modules", "__pycache__", "retencja", "archiwum",
                   "synchronizacja", "kolejka", ".venv", "venv", "tmp", "cache", "sessions"}
PRIVATE_FILES = {
    "polaczenia.md", ".ai/memory.json", ".ai/memory-projects.json",
    ".ai/onboarding.local.md", ".claude/settings.json",
    "01 Zarząd/PORTFOLIO.md", "01 Zarząd/Decyzje/DZIENNIK.md",
    "01 Zarząd/Autodiagnoza pracy AI/REJESTR.md",
    "03 Nasza firma/Brain/brain.config.json",
    "05 Wiedza/Kontekst/wlasciciel.md", "05 Wiedza/Kontekst/firma.md",
    "05 Wiedza/Kontekst/priorytety.md", "05 Wiedza/Kontekst/mapa-pracy.md",
    "05 Wiedza/Kontekst/stan-rozmowy.md", "05 Wiedza/Kontekst/pakiet-startowy.md",
    "05 Wiedza/Kontekst/pakiet-startowy.json", "05 Wiedza/Wiki/INDEKS.md",
    "05 Wiedza/Wiki/DZIENNIK.md", "05 Wiedza/Wiki/wnioski/INDEKS.md",
}
PRIVATE_SUFFIXES = {"profil.md", "plan.md", "stan.md", "notatki.md"}
PRIVATE_BRANCHES = {
    "01 Zarząd/Karty projektów", "01 Zarząd/Rutyny", "02 Klienci",
    "03 Nasza firma/Marketing", "03 Nasza firma/Sprzedaż i CRM",
    "03 Nasza firma/Finanse", "03 Nasza firma/Umowy",
    "03 Nasza firma/Projekty własne", "04 Warsztat/Metody",
    "05 Wiedza/Kontekst", "05 Wiedza/Wiki", "90 Zaplecze techniczne/materialy",
    "90 Zaplecze techniczne/plany", "90 Zaplecze techniczne/audyty",
}
PUBLIC_EXTENSIONS = {".md", ".json", ".py", ".js", ".mjs", ".css", ".html", ".txt", ".svg", ".yml", ".yaml"}
PROHIBITED_PATTERNS = {
    "ścieżka prywatna": re.compile(r"/(?:Users|home|srv)/[A-Za-z0-9_.-]+/", re.I),
    "klucz prywatny": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "token": re.compile(r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
}


def normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def collect_public_files(root: Path = ROOT) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    problems: list[str] = []
    for item in sorted(root.rglob("*"), key=lambda p: normalized(str(p.relative_to(root))).casefold()):
        relative = item.relative_to(root)
        parts = [normalized(part) for part in relative.parts]
        label = normalized(str(relative))
        if parts[0] == ".git":
            continue
        if any(part.casefold() in {"__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"} for part in parts):
            continue
        if item.is_file() and (label in PRIVATE_FILES or item.name.casefold() in PRIVATE_SUFFIXES):
            problems.append(f"Prywatny plik obecny w drzewie wydania: {relative}")
            continue
        if (item.is_file() and any(label.startswith(branch + "/") for branch in PRIVATE_BRANCHES)
                and item.name != "README.md" and not item.name.endswith(".template.md")):
            problems.append(f"Prywatny plik w obszarze użytkownika: {relative}")
            continue
        if any(part.casefold() in FORBIDDEN_PARTS for part in parts):
            if item.is_file() and item.name == "README.md" and parts[0] in ALLOWED_DIRECTORIES:
                files.append(relative)
                continue
            if item.is_file() and not item.name.startswith(".git"):
                problems.append(f"Niepubliczny katalog zawiera plik: {relative}")
            continue
        if item.is_symlink():
            problems.append(f"Symlink w paczce: {relative}")
            continue
        if item.is_dir():
            continue
        if not item.is_file():
            problems.append(f"Nieobsługiwany plik: {relative}")
            continue
        if len(parts) == 1:
            if parts[0] not in ALLOWED_ROOT_FILES:
                problems.append(f"Nieznany plik główny: {relative}")
                continue
        elif parts[0] not in ALLOWED_DIRECTORIES:
            problems.append(f"Nieznany katalog główny: {relative}")
            continue
        if item.suffix.casefold() not in PUBLIC_EXTENSIONS and item.name not in {".gitignore", "LICENSE"}:
            problems.append(f"Nieobsługiwany format: {relative}")
            continue
        if parts[0] in {"output", "outputs", "qa"} and relative.name != "README.md":
            problems.append(f"Wynik użytkownika poza paczką: {relative}")
            continue
        if item.stat().st_size > 2_000_000:
            problems.append(f"Za duży plik do paczki: {relative}")
            continue
        files.append(relative)
    return files, problems


def verify(root: Path = ROOT) -> dict:
    files, problems = collect_public_files(root)
    required = ["README.md", "START.md", "AGENTS.md", "CLAUDE.md", ".gitignore", "LICENSE",
                "polaczenia.template.md", ".ai/memory.template.json", ".ai/memory-projects.template.json",
                "01 Zarząd/PORTFOLIO.template.md", "05 Wiedza/Kontekst/wlasciciel.template.md",
                "90 Zaplecze techniczne/narzedzia/pamiec.py", "03 Nasza firma/Brain/README.md"]
    available = {normalized(str(p)) for p in files}
    for name in required:
        if name not in available:
            problems.append(f"Brak wymaganego pliku: {name}")
    for relative in files:
        path = root / relative
        try:
            value = path.read_text(encoding="utf-8")
        except UnicodeError:
            problems.append(f"Plik nie jest UTF-8: {relative}")
            continue
        for label, pattern in PROHIBITED_PATTERNS.items():
            if pattern.search(value):
                problems.append(f"{label}: {relative}")
    if "PUBLIC_FILES.json" not in available:
        problems.append("Brak jawnej listy plików wydania: PUBLIC_FILES.json")
    else:
        try:
            listed = json.loads((root / "PUBLIC_FILES.json").read_text(encoding="utf-8"))
            if (not isinstance(listed, dict) or listed.get("schema_version") != 1
                    or not isinstance(listed.get("files"), list)
                    or not all(isinstance(p, str) for p in listed["files"])):
                problems.append("Nieprawidłowa lista plików wydania")
            else:
                actual = available - {"PUBLIC_FILES.json"}
                expected = set(listed["files"])
                if len(expected) != len(listed["files"]) or actual != expected:
                    problems.append("Lista plików wydania różni się od zawartości katalogu")
        except (OSError, ValueError, UnicodeError):
            problems.append("Nie można odczytać listy plików wydania")
    return {"status": "PASS" if not problems else "FAIL", "file_count": len(files),
            "files": [str(p) for p in files], "problems": sorted(set(problems))}


def bundle(destination: Path, root: Path = ROOT) -> dict:
    result = verify(root)
    if result["status"] != "PASS":
        return result
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    stamp = datetime.now(timezone.utc)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in result["files"]:
            data = (root / relative).read_bytes()
            item = ZipInfo("AIA-OS/" + relative, date_time=(stamp.year, stamp.month, stamp.day, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, data)
            entries.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        manifest = json.dumps({"schema_version": 1, "files": entries}, ensure_ascii=False, indent=2).encode()
        info = ZipInfo("AIA-OS/MANIFEST.json", date_time=(stamp.year, stamp.month, stamp.day, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, manifest)
    result.update({"zip": str(destination), "zip_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify", "bundle"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "bundle" and args.output is None:
        parser.error("bundle wymaga --output")
    result = verify() if args.action == "verify" else bundle(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
