import copy
import io
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT_DIR))

from openmodels.adapter import AdapterError
from openmodels.generate import generate_artifacts
from openmodels.loader import load_openapi_document
from openmodels.model_io import load_canonical_model
from openmodels.normalize import (
    NormalizationError,
    normalize_openapi_document,
    resolve_json_pointer,
    resolve_schema_node,
)
from openmodels.registry import get_adapter


def _write_yaml(payload: object, suffix: str = ".yaml") -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False)
    with handle:
        yaml.safe_dump(payload, handle)
    return Path(handle.name)


def _base_document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Test", "version": "0.1.0"},
        "paths": {},
        "components": {
            "schemas": {
                "ThingInput": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                    },
                }
            }
        },
        "x-openmodels": {
            "version": "0.1",
            "entities": {
                "Thing": {
                    "table": "things",
                    "fields": {
                        "value": {
                            "schema": {
                                "create": "#/components/schemas/ThingInput/properties/value"
                            },
                            "column": {"type": "varchar", "length": 255},
                        }
                    },
                }
            },
        },
    }


class ErrorPathTests(unittest.TestCase):
    def test_loader_rejects_invalid_extension_and_shape(self) -> None:
        invalid_suffix = _write_yaml({}, suffix=".txt")
        invalid_list = _write_yaml(["not", "an", "object"])
        missing_openapi = _write_yaml({"x-openmodels": {"version": "0.1", "entities": {}}})
        unsupported_version = _write_yaml(
            {
                "openapi": "2.0.0",
                "info": {"title": "Test", "version": "0.1.0"},
                "paths": {},
                "x-openmodels": {"version": "0.1", "entities": {}},
            }
        )
        missing_extension = _write_yaml(
            {
                "openapi": "3.1.0",
                "info": {"title": "Test", "version": "0.1.0"},
                "paths": {},
            }
        )
        self.addCleanup(invalid_suffix.unlink, missing_ok=True)
        self.addCleanup(invalid_list.unlink, missing_ok=True)
        self.addCleanup(missing_openapi.unlink, missing_ok=True)
        self.addCleanup(unsupported_version.unlink, missing_ok=True)
        self.addCleanup(missing_extension.unlink, missing_ok=True)

        with self.assertRaisesRegex(ValueError, "Unsupported input file type"):
            load_openapi_document(invalid_suffix)
        with self.assertRaisesRegex(ValueError, "must be an object"):
            load_openapi_document(invalid_list)
        with self.assertRaisesRegex(ValueError, "missing the top-level 'openapi'"):
            load_openapi_document(missing_openapi)
        with self.assertRaisesRegex(ValueError, "Unsupported OpenAPI version"):
            load_openapi_document(unsupported_version)
        with self.assertRaisesRegex(ValueError, "missing the top-level 'x-openmodels'"):
            load_openapi_document(missing_extension)

    def test_model_io_rejects_invalid_input_forms(self) -> None:
        invalid_suffix = _write_yaml({}, suffix=".txt")
        invalid_list = _write_yaml(["bad"])
        invalid_object = _write_yaml({"title": "not a model"})
        self.addCleanup(invalid_suffix.unlink, missing_ok=True)
        self.addCleanup(invalid_list.unlink, missing_ok=True)
        self.addCleanup(invalid_object.unlink, missing_ok=True)

        with self.assertRaisesRegex(ValueError, "Unsupported input file type"):
            load_canonical_model(invalid_suffix)
        with self.assertRaisesRegex(ValueError, "must be a JSON or YAML object"):
            load_canonical_model(invalid_list)
        with self.assertRaisesRegex(ValueError, "Input must be either an OpenAPI document"):
            load_canonical_model(invalid_object)

    def test_generate_and_registry_error_paths(self) -> None:
        default_model = {"version": "0.1", "entities": []}
        generated = generate_artifacts(default_model)
        self.assertEqual(["schema.ts"], [item.path for item in generated])

        multi_output_model = {
            "version": "0.1",
            "entities": [],
            "outputs": [
                {"target": "drizzle-pg", "filename": "schema.ts"},
                {"target": "seaorm-rust", "options": {"moduleRoot": "entity"}},
            ],
        }
        with self.assertRaisesRegex(ValueError, "single output target"):
            generate_artifacts(multi_output_model, filename="override.ts")
        with self.assertRaisesRegex(AdapterError, "Unknown adapter target"):
            get_adapter("missing-target")

    def test_json_pointer_and_schema_resolution_errors(self) -> None:
        document = {
            "items": [1],
            "components": {
                "schemas": {
                    "Node": {"$ref": "#/components/schemas/Child"},
                    "Child": {"$ref": "#/components/schemas/Node"},
                }
            },
        }

        self.assertIs(document, resolve_json_pointer(document, "#"))
        with self.assertRaisesRegex(NormalizationError, "Unsupported JSON pointer"):
            resolve_json_pointer(document, "/bad")
        with self.assertRaisesRegex(NormalizationError, "Invalid list pointer segment"):
            resolve_json_pointer(document, "#/items/not-an-index")
        with self.assertRaisesRegex(NormalizationError, "Pointer not found"):
            resolve_json_pointer(document, "#/missing")
        with self.assertRaisesRegex(NormalizationError, "Cyclic \\$ref detected"):
            resolve_schema_node(document, "#/components/schemas/Node")

    def test_normalize_rejects_unsupported_schema_constructs(self) -> None:
        for keyword in ("anyOf", "allOf", "discriminator"):
            with self.subTest(keyword=keyword):
                document = _base_document()
                document["components"]["schemas"]["ThingInput"]["properties"]["value"] = {
                    keyword: [{"type": "string"}] if keyword != "discriminator" else {"propertyName": "kind"}
                }
                with self.assertRaisesRegex(NormalizationError, keyword):
                    normalize_openapi_document(document)

    def test_normalize_rejects_invalid_model_metadata(self) -> None:
        unknown_enum = _base_document()
        unknown_enum["x-openmodels"]["entities"]["Thing"]["fields"]["value"]["enum"] = "MissingEnum"

        with self.assertRaisesRegex(NormalizationError, "references unknown enum"):
            normalize_openapi_document(unknown_enum)

        invalid_index = _base_document()
        invalid_index["x-openmodels"]["entities"]["Thing"]["indexes"] = [
            {"fields": ["missingField"]}
        ]
        with self.assertRaisesRegex(NormalizationError, "Index references unknown field"):
            normalize_openapi_document(invalid_index)

        missing_fk_references = _base_document()
        missing_fk_references["x-openmodels"]["entities"]["Thing"]["constraints"] = [
            {"kind": "foreignKey", "fields": ["value"]}
        ]
        with self.assertRaisesRegex(NormalizationError, "must define references"):
            normalize_openapi_document(missing_fk_references)

        unknown_fk_target = _base_document()
        unknown_fk_target["x-openmodels"]["entities"]["Thing"]["constraints"] = [
            {
                "kind": "foreignKey",
                "fields": ["value"],
                "references": {"entity": "Missing", "fields": ["id"]},
            }
        ]
        with self.assertRaisesRegex(NormalizationError, "references unknown entity"):
            normalize_openapi_document(unknown_fk_target)

        unknown_fk_field = _base_document()
        unknown_fk_field["x-openmodels"]["entities"]["Other"] = {
            "table": "others",
            "fields": {
                "id": {
                    "column": {"type": "uuid", "primaryKey": True},
                }
            },
        }
        unknown_fk_field["x-openmodels"]["entities"]["Thing"]["constraints"] = [
            {
                "kind": "foreignKey",
                "fields": ["value"],
                "references": {"entity": "Other", "fields": ["missing"]},
            }
        ]
        with self.assertRaisesRegex(NormalizationError, "references unknown field 'Other.missing'"):
            normalize_openapi_document(unknown_fk_field)

    def test_normalize_tracks_nullable_persistence_and_metadata(self) -> None:
        document = _base_document()
        document["x-openmodels"]["adapters"] = {"drizzle-pg": {"imports": {"orm": ["sql"]}}}
        document["x-openmodels"]["outputs"] = [{"target": "drizzle-pg", "filename": "schema.ts"}]
        document["components"]["schemas"]["ThingInput"]["required"] = ["value"]
        document["components"]["schemas"]["ThingInput"]["properties"]["value"] = {
            "type": ["string", "null"]
        }
        field = document["x-openmodels"]["entities"]["Thing"]["fields"]["value"]
        field["column"]["type"] = "timestamp"
        field["column"]["precision"] = 3
        field["column"]["scale"] = 1
        field["computed"] = {"expression": "lower(value)", "stored": False}
        field["adapters"] = {"seaorm-rust": {"rustType": "CustomValue"}}
        document["x-openmodels"]["entities"]["Thing"]["adapters"] = {
            "seaorm-rust": {"moduleName": "thing"}
        }

        normalized = normalize_openapi_document(document)
        normalized_field = normalized["entities"][0]["fields"][0]

        self.assertTrue(normalized_field["nullable"])
        self.assertFalse(normalized_field["persisted"])
        self.assertEqual(3, normalized_field["precision"])
        self.assertEqual(1, normalized_field["scale"])
        self.assertEqual("CustomValue", normalized_field["adapters"]["seaorm-rust"]["rustType"])
        self.assertEqual("schema.ts", normalized["outputs"][0]["filename"])
        self.assertIn("seaorm-rust", normalized["entities"][0]["adapters"])


if __name__ == "__main__":
    unittest.main()
