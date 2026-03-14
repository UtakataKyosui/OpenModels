import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


class Phase5WorkflowTests(unittest.TestCase):
    def test_end_to_end_blog_workflow(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-phase5-e2e-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "scripts" / "generate_models.py"),
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out-dir",
                str(temp_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "scripts" / "generate_mappers.py"),
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out-dir",
                str(temp_dir),
                "--filename",
                "blog-dto-mappers.ts",
                "--diagnostics-filename",
                "blog-dto-mappers.diagnostics.json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "scripts" / "plan_migration.py"),
                "--from-input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api-v1.yaml"),
                "--to-input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out",
                str(temp_dir / "blog-v1-to-v2.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertTrue((temp_dir / "blog-schema.ts").exists())
        self.assertTrue((temp_dir / "seaorm-entity" / "mod.rs").exists())
        self.assertTrue((temp_dir / "seaorm-entity" / "prelude.rs").exists())
        self.assertTrue((temp_dir / "seaorm-entity" / "post.rs").exists())
        self.assertTrue((temp_dir / "seaorm-entity" / "user.rs").exists())
        self.assertTrue((temp_dir / "blog-dto-mappers.ts").exists())
        self.assertTrue((temp_dir / "blog-dto-mappers.diagnostics.json").exists())
        self.assertTrue((temp_dir / "blog-v1-to-v2.json").exists())

    def test_phase5_docs_exist(self) -> None:
        paths = [
            ROOT_DIR / "docs" / "quickstart.md",
            ROOT_DIR / "docs" / "workflows.md",
            ROOT_DIR / "docs" / "openapi-first-comparison.md",
            ROOT_DIR / "docs" / "release-policy.md",
            ROOT_DIR / "examples" / "README.md",
            ROOT_DIR / "examples" / "end-to-end" / "blog" / "README.md",
        ]

        for path in paths:
            self.assertTrue(path.exists(), str(path))


if __name__ == "__main__":
    unittest.main()
