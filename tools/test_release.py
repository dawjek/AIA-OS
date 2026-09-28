"""Release boundary tests use only temporary fictional files."""

import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from release import bundle, verify


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "AIA-OS"
        self.root.mkdir()
        for name in ["README.md", "START.md", "AGENTS.md", "CLAUDE.md", ".gitignore", "LICENSE",
                     "polaczenia.template.md", ".ai/memory.template.json",
                     ".ai/memory-projects.template.json", "01 Zarząd/PORTFOLIO.template.md",
                     "05 Wiedza/Kontekst/wlasciciel.template.md",
                     "90 Zaplecze techniczne/narzedzia/pamiec.py",
                     "03 Nasza firma/Brain/README.md", "output/README.md"]:
            self.write(name, "Neutralna zawartość.\n")
        self.write(".git/config", "private local git metadata")
        files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")
                       if p.is_file() and ".git" not in p.parts)
        self.write("PUBLIC_FILES.json", json.dumps({"schema_version": 1, "files": files}, ensure_ascii=False))

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_clean_bundle_contains_exact_public_files_and_manifest(self):
        destination = Path(self.temp.name) / "AIA-OS.zip"
        result = bundle(destination, self.root)
        self.assertEqual(result["status"], "PASS", result["problems"])
        with ZipFile(destination) as archive:
            names = archive.namelist()
            self.assertIn("AIA-OS/MANIFEST.json", names)
            self.assertIn("AIA-OS/05 Wiedza/Kontekst/wlasciciel.template.md", names)
            self.assertFalse(any(".git/" in name for name in names))
            manifest = json.loads(archive.read("AIA-OS/MANIFEST.json"))
            self.assertEqual(len(manifest["files"]), result["file_count"])

    def test_personal_generated_files_prevent_a_public_bundle(self):
        for name in [".ai/memory.json", "05 Wiedza/Kontekst/wlasciciel.md",
                     "03 Nasza firma/Marketing/profil.md", "02 Klienci/Klient A/README.md",
                     "03 Nasza firma/Brain/brain.config.json", ".ai/onboarding.local.md",
                     "01 Zarząd/Autodiagnoza pracy AI/kolejka/private.json"]:
            with self.subTest(name=name):
                path = self.root / name
                self.write(name, "Prywatny fakt.\n")
                self.assertEqual(verify(self.root)["status"], "FAIL")
                path.unlink()

    def test_unlisted_file_and_user_path_are_rejected_without_echoing_content(self):
        self.write("04 Warsztat/README.md", "Nowy, nieprzejrzany plik.\n")
        result = verify(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("Lista plików" in p for p in result["problems"]))
        (self.root / "04 Warsztat/README.md").unlink()
        private_example = "/" + "Users/aleksander/praca/projekt."
        self.write("README.md", "Prywatna ścieżka: " + private_example + "\n")
        result = verify(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("ścieżka prywatna" in p for p in result["problems"]))
        self.assertNotIn("aleksander", json.dumps(result["problems"]))


if __name__ == "__main__":
    unittest.main()
