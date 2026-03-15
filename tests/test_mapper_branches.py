import copy
import json
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.mappers import (
    _build_create_mapper,
    _build_read_mapper,
    _build_record_interface,
    _build_update_mapper,
    _create_mapping_diagnostics,
    _mapping_function_name,
    _read_mapping_diagnostics,
    _schema_properties,
    _ts_type_from_openapi_node,
    build_mapper_report,
    generate_mapper_files,
)


def _document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Mapper Test", "version": "0.1.0"},
        "paths": {},
        "components": {
            "schemas": {
                "UserRef": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                    },
                },
                "ThingCreate": {
                    "type": "object",
                    "required": ["name", "createdAt"],
                    "properties": {
                        "name": {"type": "string"},
                        "createdAt": {"type": "string", "format": "date-time"},
                        "metadata": {"type": "object"},
                        "tags": {"type": "array", "items": {"type": "integer"}},
                        "status": {"enum": ["draft", "published"]},
                        "owner": {"$ref": "#/components/schemas/UserRef"},
                        "optionalValue": {"type": ["integer", "null"]},
                        "mixed": {"type": ["string", "number"]},
                    },
                },
                "ThingUpdate": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                },
                "ThingRead": {
                    "type": "object",
                    "required": ["id", "name", "createdAt"],
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "createdAt": {"type": "string", "format": "date-time"},
                        "publishedAt": {
                            "type": "string",
                            "format": "date-time",
                            "nullable": True,
                        },
                        "extra": {"type": "boolean"},
                    },
                },
            }
        },
    }


def _entity() -> dict:
    return {
        "name": "Thing",
        "sourceSchemas": {
            "create": "#/components/schemas/ThingCreate",
            "update": "#/components/schemas/ThingUpdate",
            "read": "#/components/schemas/ThingRead",
        },
        "fields": [
            {
                "name": "id",
                "type": "uuid",
                "persisted": True,
                "generated": "database",
                "primaryKey": True,
                "sourceSchemas": {
                    "read": "#/components/schemas/ThingRead/properties/id",
                },
            },
            {
                "name": "name",
                "type": "varchar",
                "persisted": True,
                "generated": "none",
                "sourceSchemas": {
                    "create": "#/components/schemas/ThingCreate/properties/name",
                    "update": "#/components/schemas/ThingUpdate/properties/name",
                    "read": "#/components/schemas/ThingRead/properties/name",
                },
            },
            {
                "name": "createdAt",
                "type": "timestamp",
                "persisted": True,
                "generated": "none",
                "sourceSchemas": {
                    "create": "#/components/schemas/ThingCreate/properties/createdAt",
                    "read": "#/components/schemas/ThingRead/properties/createdAt",
                },
            },
            {
                "name": "publishedAt",
                "type": "timestamptz",
                "persisted": True,
                "generated": "none",
                "nullable": True,
                "sourceSchemas": {
                    "read": "#/components/schemas/ThingRead/properties/publishedAt",
                },
            },
            {
                "name": "internalNote",
                "type": "text",
                "persisted": False,
                "generated": "none",
            },
            {
                "name": "manualValue",
                "type": "integer",
                "persisted": True,
                "generated": "none",
                "nullable": False,
            },
        ],
    }


class MapperBranchTests(unittest.TestCase):
    def test_ts_type_and_schema_property_helpers_cover_variants(self) -> None:
        document = _document()

        self.assertEqual("unknown", _ts_type_from_openapi_node(None))
        self.assertEqual(
            "UserRef",
            _ts_type_from_openapi_node({"$ref": "#/components/schemas/UserRef"}),
        )
        self.assertEqual(
            '"draft" | "published"',
            _ts_type_from_openapi_node({"enum": ["draft", "published"]}),
        )
        self.assertEqual(
            "number | null",
            _ts_type_from_openapi_node({"type": ["integer", "null"]}),
        )
        self.assertEqual(
            "unknown",
            _ts_type_from_openapi_node({"type": ["string", "number"]}),
        )
        self.assertEqual(
            "Array<number>",
            _ts_type_from_openapi_node({"type": "array", "items": {"type": "integer"}}),
        )
        self.assertEqual(
            "Record<string, unknown>",
            _ts_type_from_openapi_node({"type": "object"}),
        )

        self.assertEqual(([], set()), _schema_properties(document, None))

        properties, required = _schema_properties(
            document,
            "#/components/schemas/ThingCreate",
        )
        property_types = {item["name"]: item["type"] for item in properties}

        self.assertEqual({"name", "createdAt"}, required)
        self.assertEqual("string", property_types["name"])
        self.assertEqual("Record<string, unknown>", property_types["metadata"])
        self.assertEqual("Array<number>", property_types["tags"])
        self.assertEqual('"draft" | "published"', property_types["status"])
        self.assertEqual("Record<string, unknown>", property_types["owner"])
        self.assertEqual("number | null", property_types["optionalValue"])
        self.assertEqual("unknown", property_types["mixed"])

    def test_mapper_generation_helpers_cover_diagnostics_and_edge_cases(self) -> None:
        document = _document()
        entity = _entity()

        record_interface = _build_record_interface(entity)
        self.assertIn("publishedAt: Date | null;", record_interface)
        self.assertNotIn("internalNote", record_interface)

        create_diagnostics = _create_mapping_diagnostics(entity, document)
        self.assertTrue(
            any(
                item["code"] == "unmapped-entity-field"
                and item["field"] == "manualValue"
                for item in create_diagnostics
            )
        )
        self.assertTrue(
            any(
                item["code"] == "unmapped-dto-property"
                and item["property"] == "metadata"
                for item in create_diagnostics
            )
        )

        read_diagnostics = _read_mapping_diagnostics(entity, document)
        self.assertEqual(
            ["extra"],
            [item["property"] for item in read_diagnostics],
        )

        create_mapper = _build_create_mapper(entity, document)
        self.assertIsNotNone(create_mapper)
        self.assertIn("createdAt: new Date(input.createdAt)", create_mapper)
        self.assertIn("TODO(openmodels)", create_mapper)

        update_mapper = _build_update_mapper(entity)
        self.assertIsNotNone(update_mapper)
        self.assertIn(
            "...(input.name !== undefined ? { name: input.name } : {}),",
            update_mapper,
        )

        read_mapper = _build_read_mapper(entity, document)
        self.assertIsNotNone(read_mapper)
        self.assertIn("createdAt: record.createdAt.toISOString()", read_mapper)
        self.assertIn(
            "publishedAt: record.publishedAt ? record.publishedAt.toISOString() : null",
            read_mapper,
        )

        with self.assertRaisesRegex(ValueError, "Unsupported mapping direction"):
            _mapping_function_name("Thing", "delete")

        entity_without_schemas = copy.deepcopy(entity)
        entity_without_schemas["sourceSchemas"] = {}
        self.assertEqual([], _create_mapping_diagnostics(entity_without_schemas, document))
        self.assertEqual([], _read_mapping_diagnostics(entity_without_schemas, document))
        self.assertIsNone(_build_create_mapper(entity_without_schemas, document))
        self.assertIsNone(_build_update_mapper(entity_without_schemas))
        self.assertIsNone(_build_read_mapper(entity_without_schemas, document))

    def test_generate_mapper_files_covers_record_only_output(self) -> None:
        document = _document()
        canonical_model = {
            "version": "0.1",
            "entities": [
                {
                    "name": "RecordOnly",
                    "fields": [
                        {
                            "name": "id",
                            "type": "uuid",
                            "persisted": True,
                            "generated": "none",
                            "primaryKey": True,
                        },
                        {
                            "name": "note",
                            "type": "text",
                            "persisted": False,
                            "generated": "none",
                        },
                    ],
                }
            ],
        }

        generated = {
            item.path: item.content
            for item in generate_mapper_files(
                document,
                canonical_model,
                filename="record-only.ts",
                diagnostics_filename="record-only.json",
            )
        }

        self.assertEqual(
            "// Generated by OpenModels. DTO interfaces are inferred from OpenAPI schemas.\n\n"
            "export interface RecordOnlyRecord {\n"
            "  id: string;\n"
            "}\n",
            generated["record-only.ts"],
        )
        diagnostics = json.loads(generated["record-only.json"])
        self.assertEqual(0, diagnostics["summary"]["totalDiagnostics"])
        self.assertEqual(1, diagnostics["summary"]["entities"])

    def test_build_mapper_report_counts_diagnostics(self) -> None:
        report = build_mapper_report(
            _document(),
            {"version": "0.1", "entities": [_entity()]},
        )

        self.assertEqual("0.1", report["formatVersion"])
        self.assertEqual(1, report["summary"]["entities"])
        self.assertEqual(
            report["summary"]["totalDiagnostics"],
            len(report["diagnostics"]),
        )
        self.assertGreater(report["summary"]["totalDiagnostics"], 0)


if __name__ == "__main__":
    unittest.main()
