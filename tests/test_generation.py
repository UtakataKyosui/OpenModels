import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.cli import generate_artifacts_to_directory, generate_to_directory
from openmodels.common import load_json
from openmodels.drizzle import generate_drizzle_schema
from openmodels.generate import generate_artifacts
from openmodels.loader import load_openapi_document
from openmodels.normalize import normalize_openapi_document
from openmodels.registry import get_adapter


class GenerationTests(unittest.TestCase):
    def test_normalize_matches_canonical_snapshot(self) -> None:
        document = load_openapi_document(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml")
        normalized = normalize_openapi_document(document)
        expected = load_json(ROOT_DIR / "examples" / "canonical" / "blog-model.json")

        self.assertEqual(expected, normalized)

    def test_generate_drizzle_matches_snapshot(self) -> None:
        canonical_model = load_json(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )
        generated = generate_drizzle_schema(canonical_model)
        expected = (ROOT_DIR / "examples" / "generated" / "blog-schema.ts").read_text()

        self.assertEqual(expected, generated)

    def test_declared_outputs_generate_expected_artifact(self) -> None:
        document = load_openapi_document(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml")
        canonical_model = normalize_openapi_document(document)

        generated_files = generate_artifacts(canonical_model)

        self.assertEqual(["blog-schema.ts"], [item.path for item in generated_files])
        expected = (ROOT_DIR / "examples" / "generated" / "blog-schema.ts").read_text()
        self.assertEqual(expected, generated_files[0].content)

    def test_cli_writes_declared_output_file(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-cli-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        written_paths = generate_artifacts_to_directory(
            ROOT_DIR / "examples" / "openapi" / "blog-api.yaml",
            temp_dir,
        )

        self.assertEqual([temp_dir / "blog-schema.ts"], written_paths)
        expected = (ROOT_DIR / "examples" / "generated" / "blog-schema.ts").read_text()
        self.assertEqual(expected, written_paths[0].read_text())

    def test_drizzle_wrapper_can_override_filename(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-drizzle-wrapper-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        target_path = generate_to_directory(
            ROOT_DIR / "examples" / "openapi" / "blog-api.yaml",
            temp_dir,
            filename="schema.ts",
        )

        self.assertEqual(temp_dir / "schema.ts", target_path)
        self.assertTrue(target_path.exists())

    def test_registry_exposes_drizzle_adapter(self) -> None:
        adapter = get_adapter("drizzle-pg")

        self.assertEqual("drizzle-pg", adapter.key)
        self.assertEqual("schema.ts", adapter.default_filename)


if __name__ == "__main__":
    unittest.main()
