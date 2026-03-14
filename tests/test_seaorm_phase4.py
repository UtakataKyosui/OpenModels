import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


class SeaOrmPhase4Tests(unittest.TestCase):
    def test_prepare_fixture_writes_expected_files(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-seaorm-fixture-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "scripts" / "check_seaorm_fixture.py"),
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--fixture-dir",
                str(ROOT_DIR / "examples" / "fixtures" / "seaorm-blog"),
                "--work-dir",
                str(temp_dir),
                "--prepare-only",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertTrue((temp_dir / "Cargo.toml").exists())
        self.assertTrue((temp_dir / "src" / "lib.rs").exists())
        self.assertTrue((temp_dir / "src" / "entity" / "mod.rs").exists())
        self.assertTrue((temp_dir / "src" / "entity" / "prelude.rs").exists())
        self.assertTrue((temp_dir / "src" / "entity" / "post.rs").exists())
        self.assertTrue((temp_dir / "src" / "entity" / "user.rs").exists())

        expected = (
            ROOT_DIR / "examples" / "generated" / "seaorm-entity" / "entity" / "post.rs"
        ).read_text()
        self.assertEqual(expected, (temp_dir / "src" / "entity" / "post.rs").read_text())

    def test_phase4_docs_and_fixture_exist(self) -> None:
        paths = [
            ROOT_DIR / "docs" / "seaorm-phase-3-relations.md",
            ROOT_DIR / "docs" / "seaorm-phase-4-fixtures.md",
            ROOT_DIR / "examples" / "fixtures" / "seaorm-blog" / "Cargo.toml",
            ROOT_DIR / "examples" / "fixtures" / "seaorm-blog" / "src" / "lib.rs",
            ROOT_DIR / "examples" / "fixtures" / "seaorm-blog" / "README.md",
        ]

        for path in paths:
            self.assertTrue(path.exists(), str(path))


if __name__ == "__main__":
    unittest.main()
