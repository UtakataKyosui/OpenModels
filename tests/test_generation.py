import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.cli import generate_to_directory
from openmodels.common import load_json
from openmodels.drizzle import generate_drizzle_schema
from openmodels.loader import load_openapi_document
from openmodels.normalize import normalize_openapi_document


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

    def test_cli_writes_schema_file(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-cli-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        target_path = generate_to_directory(
            ROOT_DIR / "examples" / "openapi" / "blog-api.yaml",
            temp_dir,
            filename="blog-schema.ts",
        )

        self.assertTrue(target_path.exists())
        expected = (ROOT_DIR / "examples" / "generated" / "blog-schema.ts").read_text()
        self.assertEqual(expected, target_path.read_text())


if __name__ == "__main__":
    unittest.main()
