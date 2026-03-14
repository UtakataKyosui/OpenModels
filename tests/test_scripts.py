import io
import json
import runpy
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels import cli as openmodels_cli
from scripts import check_seaorm_fixture, generate_mappers, plan_migration, validate_examples


class ScriptTests(unittest.TestCase):
    def test_openmodels_cli_main_prints_declared_outputs(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-cli-main-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        stdout = io.StringIO()

        with mock.patch.object(
            sys,
            "argv",
            [
                "openmodels.cli",
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out-dir",
                str(temp_dir),
            ],
        ), redirect_stdout(stdout):
            openmodels_cli.main()

        output = stdout.getvalue()
        self.assertIn("Generated declared artifact:", output)
        self.assertTrue((temp_dir / "blog-schema.ts").exists())
        self.assertTrue((temp_dir / "seaorm-entity" / "post.rs").exists())

    def test_openmodels_cli_main_prints_explicit_target(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-cli-target-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        stdout = io.StringIO()

        with mock.patch.object(
            sys,
            "argv",
            [
                "openmodels.cli",
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out-dir",
                str(temp_dir),
                "--target",
                "drizzle-pg",
            ],
        ), redirect_stdout(stdout):
            openmodels_cli.main()

        self.assertIn("Generated drizzle-pg artifact:", stdout.getvalue())
        self.assertTrue((temp_dir / "schema.ts").exists() or (temp_dir / "blog-schema.ts").exists())

    def test_generate_models_wrapper_runs_main(self) -> None:
        with mock.patch("openmodels.cli.main") as mocked_main:
            runpy.run_module("scripts.generate_models", run_name="__main__")

        mocked_main.assert_called_once()

    def test_generate_drizzle_wrapper_injects_default_target(self) -> None:
        argv = ["scripts.generate_drizzle", "--input", "in.yaml", "--out-dir", "out"]
        with mock.patch("openmodels.cli.main") as mocked_main, mock.patch.object(
            sys,
            "argv",
            argv,
        ):
            runpy.run_module("scripts.generate_drizzle", run_name="__main__")

        mocked_main.assert_called_once()
        self.assertIn("--target", argv)
        self.assertIn("drizzle-pg", argv)

    def test_generate_drizzle_wrapper_preserves_explicit_target(self) -> None:
        argv = [
            "scripts.generate_drizzle",
            "--input",
            "in.yaml",
            "--out-dir",
            "out",
            "--target",
            "seaorm-rust",
        ]
        with mock.patch("openmodels.cli.main") as mocked_main, mock.patch.object(
            sys,
            "argv",
            argv,
        ):
            runpy.run_module("scripts.generate_drizzle", run_name="__main__")

        mocked_main.assert_called_once()
        self.assertEqual(1, argv.count("--target"))
        self.assertIn("seaorm-rust", argv)

    def test_generate_mappers_main_writes_files(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-script-mappers-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        stdout = io.StringIO()

        with mock.patch.object(
            sys,
            "argv",
            [
                "generate_mappers.py",
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out-dir",
                str(temp_dir),
                "--filename",
                "mappers.ts",
                "--diagnostics-filename",
                "mappers.json",
            ],
        ), redirect_stdout(stdout):
            generate_mappers.main()

        self.assertIn("Generated mapper artifact:", stdout.getvalue())
        self.assertTrue((temp_dir / "mappers.ts").exists())
        self.assertTrue((temp_dir / "mappers.json").exists())

    def test_plan_migration_main_writes_plan(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-script-plan-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        out_path = temp_dir / "plan.json"
        stdout = io.StringIO()

        with mock.patch.object(
            sys,
            "argv",
            [
                "plan_migration.py",
                "--from-input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api-v1.yaml"),
                "--to-input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--out",
                str(out_path),
            ],
        ), redirect_stdout(stdout):
            plan_migration.main()

        self.assertIn("Generated migration plan:", stdout.getvalue())
        self.assertTrue(out_path.exists())
        self.assertIn("changes", json.loads(out_path.read_text()))

    def test_check_seaorm_fixture_main_prepare_only_and_compile_path(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="openmodels-script-fixture-"))
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        stdout = io.StringIO()

        with mock.patch.object(
            sys,
            "argv",
            [
                "check_seaorm_fixture.py",
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--fixture-dir",
                str(ROOT_DIR / "examples" / "fixtures" / "seaorm-blog"),
                "--work-dir",
                str(temp_dir),
                "--prepare-only",
            ],
        ), redirect_stdout(stdout):
            check_seaorm_fixture.main()

        self.assertIn("Prepared SeaORM fixture at:", stdout.getvalue())
        self.assertTrue((temp_dir / "src" / "entity" / "post.rs").exists())

        compile_dir = Path(tempfile.mkdtemp(prefix="openmodels-script-fixture-compile-"))
        self.addCleanup(lambda: shutil.rmtree(compile_dir, ignore_errors=True))
        stdout = io.StringIO()
        with mock.patch.object(
            sys,
            "argv",
            [
                "check_seaorm_fixture.py",
                "--input",
                str(ROOT_DIR / "examples" / "openapi" / "blog-api.yaml"),
                "--fixture-dir",
                str(ROOT_DIR / "examples" / "fixtures" / "seaorm-blog"),
                "--work-dir",
                str(compile_dir),
            ],
        ), mock.patch("scripts.check_seaorm_fixture.cargo_check_fixture") as mocked_check, redirect_stdout(stdout):
            check_seaorm_fixture.main()

        mocked_check.assert_called_once()
        self.assertIn("cargo check passed for fixture:", stdout.getvalue())

    def test_validate_examples_main_success_and_failure(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            validate_examples.main()
        self.assertIn("Validation passed", stdout.getvalue())

        stdout = io.StringIO()
        with mock.patch(
            "scripts.validate_examples.validate_examples",
            return_value=[
                validate_examples.Diagnostic(
                    code="broken",
                    path="x.y",
                    message="not good",
                )
            ],
        ), redirect_stdout(stdout), self.assertRaises(SystemExit) as exc:
            validate_examples.main()

        self.assertEqual(1, exc.exception.code)
        self.assertIn("broken: x.y: not good", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
