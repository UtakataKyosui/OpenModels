import copy
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_examples import (
    ROOT,
    load_json,
    load_yaml,
    validate_canonical_model_semantics,
    validate_examples,
    validate_x_openmodels_semantics,
)


class ValidationTests(unittest.TestCase):
    def test_examples_pass_validation(self) -> None:
        diagnostics = validate_examples()
        self.assertEqual([], diagnostics)

    def test_x_openmodels_reports_unknown_enum(self) -> None:
        document = load_yaml(ROOT / "examples" / "openapi" / "blog-api.yaml")
        extension = copy.deepcopy(document["x-openmodels"])
        extension["entities"]["Post"]["fields"]["status"]["enum"] = "MissingStatus"

        diagnostics = validate_x_openmodels_semantics(extension)

        self.assertEqual(["unknown-enum"], [item.code for item in diagnostics])

    def test_x_openmodels_reports_unknown_index_field(self) -> None:
        document = load_yaml(ROOT / "examples" / "openapi" / "blog-api.yaml")
        extension = copy.deepcopy(document["x-openmodels"])
        extension["entities"]["Post"]["indexes"][0]["fields"].append("missingField")

        diagnostics = validate_x_openmodels_semantics(extension)

        self.assertEqual(["unknown-index-field"], [item.code for item in diagnostics])

    def test_x_openmodels_reports_unknown_output_target(self) -> None:
        document = load_yaml(ROOT / "examples" / "openapi" / "blog-api.yaml")
        extension = copy.deepcopy(document["x-openmodels"])
        extension["outputs"][0]["target"] = "missing-target"

        diagnostics = validate_x_openmodels_semantics(extension)

        self.assertEqual(["unknown-output-target"], [item.code for item in diagnostics])

    def test_canonical_model_reports_unknown_relation_target(self) -> None:
        model = load_json(ROOT / "examples" / "canonical" / "blog-model.json")
        broken_model = copy.deepcopy(model)
        broken_model["entities"][1]["relations"][0]["targetEntity"] = "MissingUser"

        diagnostics = validate_canonical_model_semantics(broken_model)

        self.assertEqual(
            ["unknown-relation-target"], [item.code for item in diagnostics]
        )

    def test_canonical_model_reports_unknown_constraint_field(self) -> None:
        model = load_json(ROOT / "examples" / "canonical" / "blog-model.json")
        broken_model = copy.deepcopy(model)
        broken_model["entities"][1]["constraints"][0]["fields"] = ["missingField"]

        diagnostics = validate_canonical_model_semantics(broken_model)

        self.assertEqual(
            ["unknown-constraint-field"], [item.code for item in diagnostics]
        )

    def test_canonical_model_reports_unknown_output_target(self) -> None:
        model = load_json(ROOT / "examples" / "canonical" / "blog-model.json")
        broken_model = copy.deepcopy(model)
        broken_model["outputs"][0]["target"] = "missing-target"

        diagnostics = validate_canonical_model_semantics(broken_model)

        self.assertEqual(["unknown-output-target"], [item.code for item in diagnostics])


if __name__ == "__main__":
    unittest.main()
