"""Cross-language parity tests.

These tests verify that the Rust CLI produces output identical to the Python
reference implementation for the same inputs. They serve as the "language-agnostic
contract" described in ADR-001: whenever both implementations agree, a subsequent
Python retirement cannot break the generated artefacts.

Tests are skipped automatically when the Rust binary is not available (e.g. in
pure-Python CI environments that have not built the crate).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.common import load_json
from openmodels.drizzle import generate_drizzle_schema
from openmodels.loader import load_openapi_document
from openmodels.mappers import generate_mapper_files
from openmodels.normalize import normalize_openapi_document
from openmodels.rust_cli import run_rust_cli


def _rust_available() -> bool:
    """Return True if the Rust binary can be invoked."""
    try:
        run_rust_cli(["--version"])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


RUST_AVAILABLE = _rust_available()
skip_without_rust = unittest.skipUnless(RUST_AVAILABLE, "Rust binary not available")

BLOG_OPENAPI = ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"
BLOG_CANONICAL = ROOT_DIR / "examples" / "canonical" / "blog-model.json"
BLOG_V1_OPENAPI = ROOT_DIR / "examples" / "openapi" / "blog-api-v1.yaml"
MIGRATION_SNAPSHOT = ROOT_DIR / "examples" / "migrations" / "blog-v1-to-v2.json"


class NormalizationParityTests(unittest.TestCase):
    """Python and Rust must produce identical canonical models."""

    @skip_without_rust
    def test_rust_normalize_matches_python_for_blog_api(self) -> None:
        # Python output
        document = load_openapi_document(BLOG_OPENAPI)
        python_canonical = normalize_openapi_document(document)

        # Rust output (via CLI: normalize --input <path>)
        result = run_rust_cli(["normalize", "--input", str(BLOG_OPENAPI)])
        rust_canonical = json.loads(result.stdout)

        self.assertEqual(python_canonical, rust_canonical)

    @skip_without_rust
    def test_rust_canonical_matches_committed_snapshot(self) -> None:
        """Rust normalize agrees with the checked-in canonical snapshot."""
        result = run_rust_cli(["normalize", "--input", str(BLOG_OPENAPI)])
        rust_canonical = json.loads(result.stdout)
        expected = load_json(BLOG_CANONICAL)

        self.assertEqual(expected, rust_canonical)


class DrizzleGenerationParityTests(unittest.TestCase):
    """Python and Rust must produce identical Drizzle schema files."""

    @skip_without_rust
    def test_rust_drizzle_matches_python_for_blog_api(self) -> None:
        # Python output
        canonical = load_json(BLOG_CANONICAL)
        python_schema = generate_drizzle_schema(canonical)

        # Rust output (via CLI: generate-drizzle --input <path>)
        result = run_rust_cli(["generate-drizzle", "--input", str(BLOG_OPENAPI)])
        rust_schema = result.stdout

        self.assertEqual(python_schema, rust_schema)


class MapperGenerationParityTests(unittest.TestCase):
    """Python and Rust must produce identical DTO mapper files."""

    @skip_without_rust
    def test_rust_mappers_match_python_for_blog_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mappers_ts = tmp_path / "dto-mappers.ts"
            mappers_json = tmp_path / "dto-mappers.diagnostics.json"

            # Python output (document is a plain dict in the Python API)
            document = load_openapi_document(BLOG_OPENAPI)
            canonical = normalize_openapi_document(document)
            python_files = {
                item.path: item.content
                for item in generate_mapper_files(document, canonical)
            }

            # Rust output (via CLI: generate-mappers --input ... --out-dir ...)
            run_rust_cli(
                [
                    "generate-mappers",
                    "--input",
                    str(BLOG_OPENAPI),
                    "--out-dir",
                    tmp,
                ]
            )

            rust_ts = mappers_ts.read_text()
            rust_json = mappers_json.read_text()

            self.assertEqual(python_files.get("dto-mappers.ts"), rust_ts)
            self.assertEqual(
                python_files.get("dto-mappers.diagnostics.json"), rust_json
            )


class MigrationParityTests(unittest.TestCase):
    """Python and Rust must produce identical migration plans."""

    @skip_without_rust
    def test_rust_migration_matches_committed_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "migration.json"
            run_rust_cli(
                [
                    "plan-migration",
                    "--from-input",
                    str(BLOG_V1_OPENAPI),
                    "--to-input",
                    str(BLOG_OPENAPI),
                    "--out",
                    str(out_path),
                ]
            )
            rust_plan = json.loads(out_path.read_text())
            expected = load_json(MIGRATION_SNAPSHOT)

        self.assertEqual(expected, rust_plan)


class RustUnitConventionTests(unittest.TestCase):
    """Verify that the Rust CLI binary is reachable and returns expected output."""

    @skip_without_rust
    def test_rust_cli_responds_to_version_flag(self) -> None:
        result = run_rust_cli(["--version"])
        self.assertEqual(0, result.returncode)
        self.assertIn("openmodels", result.stdout.lower())

    @skip_without_rust
    def test_rust_validate_examples_passes(self) -> None:
        result = run_rust_cli(["validate-examples"])
        self.assertEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
