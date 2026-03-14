import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.common import load_json
from openmodels.loader import load_openapi_document
from openmodels.mappers import generate_mapper_files
from openmodels.migration import plan_migration
from openmodels.model_io import load_canonical_model
from openmodels.normalize import normalize_openapi_document


class Phase4Tests(unittest.TestCase):
    def test_load_canonical_model_accepts_openapi_and_canonical_json(self) -> None:
        from_openapi = load_canonical_model(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml")
        from_canonical = load_canonical_model(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )

        self.assertEqual(from_canonical, from_openapi)

    def test_migration_plan_matches_snapshot(self) -> None:
        before_model = load_canonical_model(
            ROOT_DIR / "examples" / "openapi" / "blog-api-v1.yaml"
        )
        after_model = load_canonical_model(
            ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"
        )

        plan = plan_migration(before_model, after_model)
        expected = load_json(
            ROOT_DIR / "examples" / "migrations" / "blog-v1-to-v2.json"
        )

        self.assertEqual(expected, plan)

    def test_mapper_files_match_snapshots(self) -> None:
        document = load_openapi_document(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml")
        canonical_model = normalize_openapi_document(document)

        generated_files = {
            item.path: item.content
            for item in generate_mapper_files(document, canonical_model)
        }

        expected_mapper = (
            ROOT_DIR / "examples" / "generated" / "blog-dto-mappers.ts"
        ).read_text()
        expected_diagnostics = (
            ROOT_DIR / "examples" / "generated" / "blog-dto-mappers.diagnostics.json"
        ).read_text()

        self.assertEqual(expected_mapper, generated_files["dto-mappers.ts"])
        self.assertEqual(
            expected_diagnostics, generated_files["dto-mappers.diagnostics.json"]
        )

    def test_plan_migration_cli_writes_snapshot(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-migration-cli-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        out_path = temp_dir / "plan.json"

        subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "scripts" / "plan_migration.py"),
                "--from-input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api-v1.yaml"),
                "--to-input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out",
                str(out_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        expected = load_json(ROOT_DIR / "examples" / "migrations" / "blog-v1-to-v2.json")
        self.assertEqual(expected, json.loads(out_path.read_text()))

    def test_generate_mappers_cli_writes_snapshots(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-mappers-cli-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

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

        expected_mapper = (
            ROOT_DIR / "examples" / "generated" / "blog-dto-mappers.ts"
        ).read_text()
        expected_diagnostics = (
            ROOT_DIR / "examples" / "generated" / "blog-dto-mappers.diagnostics.json"
        ).read_text()

        self.assertEqual(
            expected_mapper, (temp_dir / "blog-dto-mappers.ts").read_text()
        )
        self.assertEqual(
            expected_diagnostics,
            (temp_dir / "blog-dto-mappers.diagnostics.json").read_text(),
        )


if __name__ == "__main__":
    unittest.main()
