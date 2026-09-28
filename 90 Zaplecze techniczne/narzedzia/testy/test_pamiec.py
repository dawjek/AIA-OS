"""Kontrakt pamięci na osobnych, fikcyjnych instalacjach."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1]
MEMORY = TOOLS / "pamiec.py"
PROJECT = TOOLS / "pamiec-projekt.py"
HOOK = TOOLS / "pamiec-start.py"
INSTALLER = TOOLS / "instaluj-pamiec.py"
DIAGNOSIS = TOOLS / "autodiagnoza.py"


def digest(data):
    return hashlib.sha256(data).hexdigest()


class MemoryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="starter pamięć ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Nowy OS Żanety"
        (self.root / ".ai").mkdir(parents=True)
        (self.root / "05 Wiedza/Kontekst").mkdir(parents=True)
        (self.root / "05 Wiedza/Wiki").mkdir(parents=True)
        self.owner = self.root / "05 Wiedza/Kontekst/wlasciciel.md"
        self.state = self.root / "05 Wiedza/Kontekst/stan-rozmowy.md"
        self.owner.write_text("", encoding="utf-8")
        self.state.write_text("# Stan rozmowy\n", encoding="utf-8")
        self.config = {
            "schema_version": 1,
            "configured": False,
            "max_context_bytes": 18000,
            "sources": [{"path": "05 Wiedza/Kontekst/wlasciciel.md", "required": True},
                        {"path": "05 Wiedza/Kontekst/stan-rozmowy.md", "required": True}],
            "search_roots": ["05 Wiedza/Kontekst", "05 Wiedza/Wiki"],
            "checkpoint_path": "05 Wiedza/Kontekst/stan-rozmowy.md",
            "output": "05 Wiedza/Kontekst/pakiet-startowy.md",
            "manifest": ".ai/synchronizacja/pamiec/manifest.json",
        }
        self.registry = {"schema_version": 1, "max_state_bytes": 12000, "projects": []}
        self.save_config()
        self.save_registry()

    def save_config(self):
        (self.root / ".ai/memory.json").write_text(
            json.dumps(self.config, ensure_ascii=False), encoding="utf-8")

    def save_registry(self):
        (self.root / ".ai/memory-projects.json").write_text(
            json.dumps(self.registry, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, script, *args, payload=None):
        call = [sys.executable, str(script), "--root", str(self.root), *args]
        result = subprocess.run(call, input=None if payload is None else json.dumps(payload),
                                text=True, capture_output=True, timeout=12)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"Brak wyniku JSON: {result.stdout!r} {result.stderr!r}")
        return result.returncode, data


class PackageTests(MemoryFixture):
    def test_config_cannot_publish_private_packet_to_public_readme(self):
        readme = self.root / "README.md"
        readme.write_text("# Publiczny starter\n", encoding="utf-8")
        self.config["configured"] = True
        self.config["output"] = "README.md"
        self.save_config()
        self.owner.write_text("# Żaneta\nPrywatny plan atlasu.\n", encoding="utf-8")
        code, result = self.run_cli(MEMORY, "build")
        self.assertEqual((code, result["status"], result["reason"]),
                         (2, "unavailable", "invalid_config"))
        self.assertEqual(readme.read_text(encoding="utf-8"), "# Publiczny starter\n")

    def test_config_cannot_use_public_paths_for_manifest_or_global_checkpoint(self):
        readme = self.root / "README.md"
        readme.write_text("# Publiczny starter\n", encoding="utf-8")
        for key in ("manifest", "checkpoint_path"):
            with self.subTest(key=key):
                self.config[key] = "README.md"
                self.save_config()
                code, result = self.run_cli(MEMORY, "status")
                self.assertEqual((code, result["status"], result["reason"]),
                                 (2, "unavailable", "invalid_config"))
                self.assertEqual(readme.read_text(encoding="utf-8"), "# Publiczny starter\n")
                self.config[key] = (".ai/synchronizacja/pamiec/manifest.json" if key == "manifest"
                                    else "05 Wiedza/Kontekst/stan-rozmowy.md")

    def test_canonical_output_rejects_hardlink_to_public_readme(self):
        readme = self.root / "README.md"
        readme.write_text("# Publiczny starter\n", encoding="utf-8")
        target = self.root / self.config["output"]
        try:
            os.link(readme, target)
        except OSError:
            self.skipTest("System plików nie obsługuje hardlinków w tej lokalizacji")
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("Prywatna decyzja.\n", encoding="utf-8")
        code, result = self.run_cli(MEMORY, "build")
        self.assertEqual((code, result["status"], result["reason"]),
                         (2, "unavailable", "unsafe_path"))
        self.assertEqual(readme.read_text(encoding="utf-8"), "# Publiczny starter\n")

    def test_canonical_output_rejects_symlink_to_public_readme(self):
        readme = self.root / "README.md"
        readme.write_text("# Publiczny starter\n", encoding="utf-8")
        target = self.root / self.config["output"]
        try:
            target.symlink_to(readme)
        except OSError:
            self.skipTest("System plików nie obsługuje symlinków w tej lokalizacji")
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("Prywatna decyzja.\n", encoding="utf-8")
        code, result = self.run_cli(MEMORY, "build")
        self.assertEqual((code, result["status"], result["reason"]),
                         (2, "unavailable", "unsafe_path"))
        self.assertEqual(readme.read_text(encoding="utf-8"), "# Publiczny starter\n")

    def test_public_templates_need_no_personal_sources_or_local_config(self):
        (self.root / ".ai/memory.template.json").write_text(
            json.dumps(self.config, ensure_ascii=False), encoding="utf-8")
        (self.root / ".ai/memory-projects.template.json").write_text(
            json.dumps(self.registry, ensure_ascii=False), encoding="utf-8")
        (self.root / ".ai/memory.json").unlink()
        (self.root / ".ai/memory-projects.json").unlink()
        self.owner.unlink()
        self.state.unlink()
        self.assertEqual(self.run_cli(MEMORY, "status")[1]["status"], "empty")
        self.assertEqual(self.run_cli(MEMORY, "build")[1]["status"], "empty")
        self.assertEqual(self.run_cli(PROJECT, "list")[1]["projects"], [])
        self.assertFalse((self.root / ".ai/memory.json").exists())

    def test_fresh_installation_is_empty_and_build_does_not_create_package(self):
        code, status = self.run_cli(MEMORY, "status")
        self.assertEqual((code, status["status"]), (0, "empty"))
        code, result = self.run_cli(MEMORY, "build")
        self.assertEqual((code, result["status"]), (0, "empty"))
        self.assertFalse((self.root / self.config["output"]).exists())
        self.assertFalse((self.root / ".ai/synchronizacja/pamiec").exists())

    def test_build_uses_full_sources_and_reports_stale_after_edit(self):
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("# Żaneta\nCel: stworzyć atlas roślin.\n", encoding="utf-8")
        code, built = self.run_cli(MEMORY, "build")
        self.assertEqual((code, built["status"]), (0, "ready"))
        packet = (self.root / self.config["output"]).read_text(encoding="utf-8")
        self.assertIn("Cel: stworzyć atlas roślin.", packet)
        self.assertIn("# Stan rozmowy", packet)
        self.assertEqual(self.run_cli(MEMORY, "status")[1]["status"], "ready")
        self.owner.write_text("# Żaneta\nCel: napisać atlas roślin i mapę.\n", encoding="utf-8")
        self.assertEqual(self.run_cli(MEMORY, "status")[1]["status"], "stale")

    def test_missing_source_and_overflow_are_visible_without_publishing(self):
        self.config["configured"] = True
        self.save_config()
        self.owner.unlink()
        code, missing = self.run_cli(MEMORY, "build")
        self.assertEqual((code, missing["status"]), (2, "unavailable"))
        self.assertEqual(missing["reason"], "missing_source")
        self.owner.write_text("Dużo danych. " * 3000, encoding="utf-8")
        code, overflow = self.run_cli(MEMORY, "build")
        self.assertEqual((code, overflow["status"]), (2, "unavailable"))
        self.assertEqual(overflow["reason"], "limit_exceeded")
        self.assertFalse((self.root / self.config["output"]).exists())

    def test_search_uses_configured_roots_and_returns_source_path(self):
        self.owner.write_text("Najważniejsze są storczyki.\n", encoding="utf-8")
        code, result = self.run_cli(MEMORY, "search", "storczyki")
        self.assertEqual((code, result["status"]), (0, "ok"))
        self.assertEqual(result["matches"][0]["path"], "05 Wiedza/Kontekst/wlasciciel.md")
        self.assertEqual(result["matches"][0]["line"], 1)


class CheckpointTests(MemoryFixture):
    def payload(self, revision, event="decyzja-1", summary="Wybrano atlas roślin."):
        return {"event_id": event, "expected_revision": revision,
                "summary": summary, "done": ["Sprawdzono trzy źródła."],
                "next": ["Dodać szkic mapy."],
                "sources": ["05 Wiedza/Kontekst/wlasciciel.md"]}

    def test_preflight_then_save_keeps_previous_document_and_replay_is_idempotent(self):
        original = self.state.read_bytes()
        revision = digest(original)
        payload = self.payload(revision)
        code, preview = self.run_cli(MEMORY, "checkpoint", "--input", "-", "--check-only",
                                     payload=payload)
        self.assertEqual((code, preview["status"], preview["check_only"]), (0, "ok", True))
        self.assertEqual(self.state.read_bytes(), original)
        self.assertFalse((self.root / ".ai/synchronizacja/pamiec").exists())
        code, saved = self.run_cli(MEMORY, "checkpoint", "--input", "-", payload=payload)
        self.assertEqual((code, saved["status"], saved["checkpoint_saved"]), (0, "ok", True))
        self.assertEqual(saved["revision"], preview["candidate_revision"])
        self.assertIn("# Stan rozmowy", self.state.read_text(encoding="utf-8"))
        self.assertIn("Wybrano atlas roślin.", self.state.read_text(encoding="utf-8"))
        retained = list((self.root / ".ai/synchronizacja/pamiec/retencja/global").glob("*.md"))
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].read_bytes(), original)
        code, replay = self.run_cli(MEMORY, "checkpoint", "--input", "-", payload=payload)
        self.assertEqual((code, replay["status"], replay["idempotent"]), (0, "ok", True))
        self.owner.unlink()
        code, late_replay = self.run_cli(MEMORY, "checkpoint", "--input", "-", payload=payload)
        self.assertEqual((code, late_replay["status"], late_replay["idempotent"]), (0, "ok", True))
        self.assertEqual(len(list((self.root / ".ai/synchronizacja/pamiec/retencja/global").glob("*.md"))), 1)

    def test_old_revision_conflicts_and_possible_secret_is_rejected(self):
        revision = digest(self.state.read_bytes())
        self.assertEqual(self.run_cli(MEMORY, "checkpoint", "--input", "-",
                                      payload=self.payload(revision))[1]["status"], "ok")
        before = self.state.read_bytes()
        code, conflict = self.run_cli(MEMORY, "checkpoint", "--input", "-",
                                      payload=self.payload(revision, event="decyzja-2"))
        self.assertEqual((code, conflict["status"]), (2, "conflict"))
        self.assertEqual(self.state.read_bytes(), before)
        secret = self.payload(digest(before), event="decyzja-3",
                              summary="api_key=abcdefghijklmnopqrst123456")
        code, rejected = self.run_cli(MEMORY, "checkpoint", "--input", "-", payload=secret)
        self.assertEqual((code, rejected["status"], rejected["reason"]),
                         (2, "rejected", "secret_detected"))
        self.assertNotIn("abcdefghijkl", json.dumps(rejected))
        self.assertEqual(self.state.read_bytes(), before)


class ProjectTests(MemoryFixture):
    def setUp(self):
        super().setUp()
        for name in ("Atlas", "Książka"):
            folder = self.root / "03 Nasza firma/Projekty własne" / name
            folder.mkdir(parents=True)
            (folder / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        self.registry["projects"] = [
            {"id": "atlas", "name": "Atlas", "root": "03 Nasza firma/Projekty własne/Atlas",
             "state_path": "03 Nasza firma/Projekty własne/Atlas/README.md"},
            {"id": "ksiazka", "name": "Książka", "root": "03 Nasza firma/Projekty własne/Książka",
             "state_path": "03 Nasza firma/Projekty własne/Książka/README.md"},
        ]
        self.save_registry()

    def test_list_show_and_independent_project_checkpoints(self):
        code, listing = self.run_cli(PROJECT, "list")
        self.assertEqual((code, [row["id"] for row in listing["projects"]]),
                         (0, ["atlas", "ksiazka"]))
        code, initial = self.run_cli(PROJECT, "show", "atlas")
        self.assertEqual((code, initial["status"]), (0, "empty"))
        book = self.root / self.registry["projects"][1]["state_path"]
        book_before = book.read_bytes()
        payload = {"event_id": "atlas-1", "expected_revision": initial["revision"],
                   "project": "atlas", "summary": "Zebrano rośliny z ogrodu.",
                   "done": ["Zdjęcia są opisane."], "next": ["Ułożyć rozdziały."],
                   "sources": ["05 Wiedza/Kontekst/wlasciciel.md"]}
        code, preview = self.run_cli(PROJECT, "checkpoint", "atlas", "--input", "-",
                                     "--check-only", payload=payload)
        self.assertEqual((code, preview["status"]), (0, "ok"))
        self.assertEqual(self.run_cli(PROJECT, "show", "atlas")[1]["status"], "empty")
        code, saved = self.run_cli(PROJECT, "checkpoint", "atlas", "--input", "-",
                                   payload=payload)
        self.assertEqual((code, saved["status"]), (0, "ok"))
        self.assertEqual(book.read_bytes(), book_before)
        code, shown = self.run_cli(PROJECT, "show", "atlas")
        self.assertEqual((code, shown["status"], shown["revision"]), (0, "ok", saved["revision"]))
        self.assertIn("Zebrano rośliny", shown["state"])
        self.assertEqual(self.run_cli(PROJECT, "show", "ksiazka")[1]["status"], "empty")

    def test_registry_rejects_state_outside_project_folder(self):
        self.registry["projects"][0]["state_path"] = "05 Wiedza/Kontekst/stan-rozmowy.md"
        self.save_registry()
        code, result = self.run_cli(PROJECT, "show", "atlas")
        self.assertEqual((code, result["status"]), (2, "unavailable"))
        self.assertEqual(result["reason"], "invalid_registry")

    def test_registry_rejects_hardlink_to_protected_document(self):
        target = self.root / self.registry["projects"][0]["state_path"]
        target.unlink()
        try:
            import os
            os.link(self.owner, target)
        except OSError:
            self.skipTest("System plików nie obsługuje hardlinków w tej lokalizacji")
        code, result = self.run_cli(PROJECT, "show", "atlas")
        self.assertEqual((code, result["status"], result["reason"]),
                         (2, "unavailable", "invalid_registry"))

    def test_registry_rejects_public_brain_readme_as_project_state(self):
        brain = self.root / "03 Nasza firma/Brain/README.md"
        brain.parent.mkdir(parents=True)
        brain.write_text("# Publiczny kokpit\n", encoding="utf-8")
        self.registry["projects"][0]["root"] = "03 Nasza firma/Brain"
        self.registry["projects"][0]["state_path"] = "03 Nasza firma/Brain/README.md"
        self.save_registry()
        code, result = self.run_cli(PROJECT, "show", "atlas")
        self.assertEqual((code, result["status"], result["reason"]),
                         (2, "unavailable", "invalid_registry"))


class HookTests(MemoryFixture):
    def hook_event(self, cwd=None):
        event = {"hook_event_name": "SessionStart", "source": "startup",
                 "cwd": str(self.root if cwd is None else cwd)}
        return self.run_cli(HOOK, "--runtime", "codex", payload=event)

    def test_empty_hook_then_ready_context_from_real_sources(self):
        code, empty = self.hook_event()
        self.assertEqual(code, 0)
        self.assertIn("status=empty", empty["hookSpecificOutput"]["additionalContext"])
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("# Żaneta\nPamiętaj o atlasie roślin.\n", encoding="utf-8")
        code, ready = self.hook_event()
        self.assertEqual(code, 0)
        context = ready["hookSpecificOutput"]["additionalContext"]
        self.assertIn("status=ready", context)
        self.assertIn("Pamiętaj o atlasie roślin.", context)
        self.assertEqual(self.run_cli(MEMORY, "status")[1]["status"], "ready")

    def test_hook_refuses_foreign_workspace_and_does_not_emit_stale_content(self):
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("To jest poprzedni cel.", encoding="utf-8")
        self.assertEqual(self.hook_event()[1]["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.owner.unlink()
        code, failed = self.hook_event()
        self.assertEqual(code, 0)
        text = failed["hookSpecificOutput"]["additionalContext"]
        self.assertIn("status=unavailable", text)
        self.assertNotIn("poprzedni cel", text)
        foreign = Path(self.temp.name) / "Inny projekt"
        foreign.mkdir()
        code, wrong = self.hook_event(cwd=foreign)
        self.assertEqual(code, 0)
        self.assertIn("status=unavailable", wrong["hookSpecificOutput"]["additionalContext"])

    def test_decision_written_in_session_a_is_in_fresh_session_context(self):
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("# Żaneta\nPracuje nad atlasem.\n", encoding="utf-8")
        revision = digest(self.state.read_bytes())
        event = {"event_id": "sesja-a-001", "expected_revision": revision,
                 "summary": "Decyzja: atlas ma opisywać rośliny miejskie.",
                 "done": ["Wybrano zakres."], "next": ["Sprawdzić trzy parki."],
                 "sources": ["05 Wiedza/Kontekst/wlasciciel.md"]}
        code, saved = self.run_cli(MEMORY, "checkpoint", "--input", "-", payload=event)
        self.assertEqual((code, saved["status"]), (0, "ok"))
        code, next_session = self.hook_event()
        self.assertEqual(code, 0)
        context = next_session["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Decyzja: atlas ma opisywać rośliny miejskie.", context)
        self.assertIn("Sprawdzić trzy parki.", context)

    def test_claude_fork_refreshes_context_and_codex_does_not_match_fork(self):
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("# Żaneta\nCel: atlas roślin.\n", encoding="utf-8")
        event = {"hook_event_name": "SessionStart", "source": "fork", "cwd": str(self.root)}
        code, claude = self.run_cli(HOOK, "--runtime", "claude", payload=event)
        self.assertEqual(code, 0)
        self.assertIn("status=ready", claude["hookSpecificOutput"]["additionalContext"])
        code, codex = self.run_cli(HOOK, "--runtime", "codex", payload=event)
        self.assertEqual(code, 0)
        self.assertIn("status=unavailable", codex["hookSpecificOutput"]["additionalContext"])


class InstallerTests(MemoryFixture):
    def test_only_claude_matcher_includes_fork(self):
        self.assertEqual(self.run_cli(INSTALLER, "--runtime", "both", "install")[0], 0)
        codex = json.loads((self.root / ".codex/hooks.json").read_text(encoding="utf-8"))
        claude = json.loads((self.root / ".claude/settings.json").read_text(encoding="utf-8"))
        codex_matcher = codex["hooks"]["SessionStart"][0]["matcher"]
        claude_matcher = claude["hooks"]["SessionStart"][0]["matcher"]
        self.assertNotIn("fork", codex_matcher)
        self.assertIn("fork", claude_matcher)

    @unittest.skipIf(os.name == "nt", "Parsowanie POSIX; Windows wymaga osobnego hosta")
    def test_installed_codex_command_runs_in_unicode_path_without_shell_script(self):
        destination = self.root / "90 Zaplecze techniczne/narzedzia"
        destination.mkdir(parents=True)
        shutil.copyfile(HOOK, destination / HOOK.name)
        shutil.copyfile(TOOLS / "memory_core.py", destination / "memory_core.py")
        self.config["configured"] = True
        self.save_config()
        self.owner.write_text("# Żaneta\nCel: atlas miejskich roślin.\n", encoding="utf-8")
        self.assertEqual(self.run_cli(INSTALLER, "--runtime", "codex", "install")[0], 0)
        settings = json.loads((self.root / ".codex/hooks.json").read_text(encoding="utf-8"))
        command = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        args = shlex.split(command)
        event = {"hook_event_name": "SessionStart", "source": "startup", "cwd": str(self.root)}
        process = subprocess.run(args, input=json.dumps(event), text=True,
                                 capture_output=True, timeout=12)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertIn("Cel: atlas miejskich roślin.",
                      result["hookSpecificOutput"]["additionalContext"])

    def test_install_and_uninstall_preserve_other_settings_and_are_repeatable(self):
        codex_path = self.root / ".codex/hooks.json"
        claude_path = self.root / ".claude/settings.json"
        codex_path.parent.mkdir()
        claude_path.parent.mkdir()
        other_handler = {"type": "command", "command": "echo existing"}
        codex_original = {"description": "Moje reguły", "hooks": {"SessionStart": [
            {"matcher": "resume", "hooks": [other_handler]}],
            "Stop": [{"hooks": [other_handler]}]}, "custom": {"keep": True}}
        claude_original = {"permissions": {"allow": ["Read"]}, "hooks": {"SessionStart": [
            {"matcher": "resume", "hooks": [other_handler]}]}, "env": {"EXAMPLE": "safe"}}
        codex_path.write_text(json.dumps(codex_original), encoding="utf-8")
        claude_path.write_text(json.dumps(claude_original), encoding="utf-8")
        code, installed = self.run_cli(INSTALLER, "--runtime", "both", "install")
        self.assertEqual((code, installed["status"]), (0, "ok"))
        codex = json.loads(codex_path.read_text(encoding="utf-8"))
        claude = json.loads(claude_path.read_text(encoding="utf-8"))
        self.assertEqual(codex["custom"], {"keep": True})
        self.assertEqual(codex["hooks"]["Stop"], codex_original["hooks"]["Stop"])
        self.assertEqual(claude["permissions"], claude_original["permissions"])
        self.assertEqual(claude["env"], claude_original["env"])
        self.assertEqual(codex["hooks"]["SessionStart"][0]["hooks"], [other_handler])
        codex_own = codex["hooks"]["SessionStart"][-1]["hooks"][0]
        self.assertEqual(codex_own["additionalContextLimit"], 0)
        claude_own = claude["hooks"]["SessionStart"][-1]["hooks"][0]
        self.assertEqual(claude_own["command"], sys.executable)
        self.assertEqual(claude_own["args"][0], str((self.root / "90 Zaplecze techniczne/narzedzia/pamiec-start.py").resolve()))
        self.assertIn(str(self.root.resolve()), claude_own["args"])
        codex_bytes, claude_bytes = codex_path.read_bytes(), claude_path.read_bytes()
        self.assertEqual(self.run_cli(INSTALLER, "--runtime", "both", "install")[0], 0)
        self.assertEqual((codex_path.read_bytes(), claude_path.read_bytes()),
                         (codex_bytes, claude_bytes))
        code, status = self.run_cli(INSTALLER, "--runtime", "both", "status")
        self.assertEqual((code, status["codex"]["configured"], status["claude"]["configured"]),
                         (0, True, True))
        self.assertFalse(status["codex"]["execution_confirmed"])
        code, removed = self.run_cli(INSTALLER, "--runtime", "both", "uninstall")
        self.assertEqual((code, removed["status"]), (0, "ok"))
        self.assertEqual(json.loads(codex_path.read_text(encoding="utf-8")), codex_original)
        self.assertEqual(json.loads(claude_path.read_text(encoding="utf-8")), claude_original)

    def test_invalid_existing_settings_are_not_replaced(self):
        codex_path = self.root / ".codex/hooks.json"
        codex_path.parent.mkdir()
        codex_path.write_text("{wrong json", encoding="utf-8")
        code, result = self.run_cli(INSTALLER, "--runtime", "codex", "install")
        self.assertEqual((code, result["status"]), (2, "unavailable"))
        self.assertEqual(codex_path.read_text(encoding="utf-8"), "{wrong json")


class DiagnosisTests(MemoryFixture):
    def setUp(self):
        super().setUp()
        self.register = self.root / "01 Zarząd/Autodiagnoza pracy AI/REJESTR.md"
        self.register.parent.mkdir(parents=True)
        self.register.write_text("# Rejestr korekt\n", encoding="utf-8")

    def test_local_queue_records_once_with_readback_and_keeps_source(self):
        event = {"event_id": "korekta-001", "observation": "Pominięto źródło.",
                 "evidence": "Wynik kontroli był pusty.",
                 "correction": "Dodano odczyt pliku przed odpowiedzią."}
        code, queued = self.run_cli(DIAGNOSIS, "enqueue", "--input", "-", payload=event)
        self.assertEqual((code, queued["status"], queued["queue_saved"]), (0, "ok", True))
        code, pending = self.run_cli(DIAGNOSIS, "list")
        self.assertEqual((code, len(pending["items"]), pending["items"][0]["status"]),
                         (0, 1, "pending"))
        self.assertEqual(self.run_cli(DIAGNOSIS, "enqueue", "--input", "-",
                                      payload=event)[1]["idempotent"], True)
        before = self.register.read_bytes()
        record = {"event_id": "korekta-001", "expected_revision": pending["items"][0]["revision"],
                  "outcome": "Sprawdzone w ponownej próbie."}
        code, saved = self.run_cli(DIAGNOSIS, "record", "--input", "-", payload=record)
        self.assertEqual((code, saved["status"], saved["register_verified"]), (0, "ok", True))
        self.assertIn("Sprawdzone w ponownej próbie.", self.register.read_text(encoding="utf-8"))
        self.assertIn(before, [file.read_bytes() for file in
                             (self.root / ".ai/synchronizacja/pamiec/retencja/autodiagnoza").glob("*.md")])
        after = self.register.read_bytes()
        code, repeat = self.run_cli(DIAGNOSIS, "record", "--input", "-", payload=record)
        self.assertEqual((code, repeat["idempotent"]), (0, True))
        self.assertEqual(self.register.read_bytes(), after)
        self.register.unlink()
        code, missing = self.run_cli(DIAGNOSIS, "record", "--input", "-", payload=record)
        self.assertEqual((code, missing["status"]), (2, "unavailable"))
        self.assertNotEqual(missing.get("register_verified"), True)

    def test_changed_queue_content_is_not_reported_as_valid(self):
        event = {"event_id": "korekta-002", "observation": "Pominięto źródło.",
                 "evidence": "Kontrola wykazała brak.", "correction": "Dodać odczyt."}
        self.assertEqual(self.run_cli(DIAGNOSIS, "enqueue", "--input", "-",
                                      payload=event)[1]["status"], "ok")
        path = self.root / "01 Zarząd/Autodiagnoza pracy AI/kolejka/korekta-002.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["correction"] = "Inna treść po zapisie."
        path.write_text(json.dumps(data), encoding="utf-8")
        code, result = self.run_cli(DIAGNOSIS, "list")
        self.assertEqual((code, result["status"], result["reason"]),
                         (2, "unavailable", "invalid_queue"))


if __name__ == "__main__":
    unittest.main()
