import copy
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.adapter import AdapterError
from openmodels.seaorm import (
    SEAORM_RUST_ADAPTER,
    _active_enums_for_entity,
    _enum_variant_name,
    _matching_foreign_key_constraint,
    _raw_rust_type,
    _related_impl_lines,
    _relation_attribute_lines,
    _relation_variant_name,
    _render_attribute_lines,
    _render_model,
    _seaorm_column_type,
    _seaorm_reference_action,
    _seaorm_rust_type,
)


def _canonical_model() -> dict:
    return {
        "version": "0.1",
        "enums": [
            {
                "name": "Status",
                "values": ["draft", "2024-ready", "!!!"],
            }
        ],
        "entities": [
            {
                "name": "Profile",
                "table": "profiles",
                "fields": [
                    {
                        "name": "id",
                        "type": "uuid",
                        "persisted": True,
                        "generated": "none",
                        "primaryKey": True,
                    }
                ],
                "relations": [],
                "constraints": [],
                "indexes": [],
            },
            {
                "name": "User",
                "table": "users",
                "fields": [
                    {
                        "name": "id",
                        "type": "uuid",
                        "persisted": True,
                        "generated": "none",
                        "primaryKey": True,
                    }
                ],
                "relations": [],
                "constraints": [],
                "indexes": [],
            },
            {
                "name": "Thing",
                "table": "things",
                "adapters": {
                    "seaorm-rust": {
                        "extraDerives": ["Serialize"],
                        "extraAttributes": ['#[serde(rename_all = "camelCase")]'],
                    }
                },
                "fields": [
                    {
                        "name": "id",
                        "type": "integer",
                        "persisted": True,
                        "generated": "database",
                        "primaryKey": True,
                    },
                    {
                        "name": "userId",
                        "type": "uuid",
                        "persisted": True,
                        "generated": "none",
                    },
                    {
                        "name": "status",
                        "type": "varchar",
                        "persisted": True,
                        "generated": "none",
                        "nullable": True,
                        "enum": "Status",
                    },
                    {
                        "name": "slug",
                        "type": "varchar",
                        "persisted": True,
                        "generated": "none",
                        "default": "draft-slug",
                        "computed": {"expression": "lower(slug)"},
                    },
                ],
                "relations": [
                    {
                        "name": "user",
                        "kind": "belongsTo",
                        "targetEntity": "User",
                        "ownership": "owner",
                        "foreignKey": "userId",
                        "references": "id",
                    },
                    {
                        "name": "profile",
                        "kind": "hasOne",
                        "targetEntity": "Profile",
                        "ownership": "inverse",
                    },
                ],
                "constraints": [
                    {
                        "kind": "foreignKey",
                        "fields": ["userId"],
                        "references": {
                            "entity": "User",
                            "fields": ["id"],
                            "onDelete": "cascade",
                            "onUpdate": "restrict",
                        },
                    },
                    {
                        "kind": "check",
                        "name": "things_slug_ck",
                        "fields": ["slug"],
                        "expression": "slug <> ''",
                    },
                ],
                "indexes": [
                    {
                        "name": "things_slug_idx",
                        "fields": ["slug"],
                        "unique": True,
                    }
                ],
            },
        ],
    }


class SeaOrmBranchTests(unittest.TestCase):
    def test_type_helpers_cover_overrides_and_errors(self) -> None:
        custom_field = {
            "name": "customValue",
            "type": "text",
            "nullable": True,
            "adapters": {
                "seaorm-rust": {
                    "rustType": "CustomValue",
                    "columnType": "CustomColumn",
                }
            },
        }

        self.assertEqual("CustomValue", _raw_rust_type(custom_field))
        self.assertEqual("Option<CustomValue>", _seaorm_rust_type(custom_field))
        self.assertEqual("CustomColumn", _seaorm_column_type(custom_field))
        self.assertEqual(
            "String(StringLen::None)",
            _seaorm_column_type({"name": "slug", "type": "varchar"}),
        )
        self.assertEqual("Value", _enum_variant_name("!!!"))
        self.assertEqual("Value2024Ready", _enum_variant_name("2024-ready"))

        with self.assertRaisesRegex(AdapterError, "Unsupported SeaORM Rust type mapping"):
            _raw_rust_type({"name": "payload", "type": "json"})
        with self.assertRaisesRegex(AdapterError, "Unsupported SeaORM column type mapping"):
            _seaorm_column_type({"name": "payload", "type": "json"})
        with self.assertRaisesRegex(AdapterError, "non-empty strings"):
            _render_attribute_lines([""], "bad attributes")
        with self.assertRaisesRegex(AdapterError, "non-empty strings"):
            _render_attribute_lines([1], "bad attributes")

    def test_model_rendering_covers_comments_and_validation(self) -> None:
        entity = next(
            item for item in _canonical_model()["entities"] if item["name"] == "Thing"
        )

        rendered = _render_model(entity)

        self.assertIn("#[derive(Clone, Debug, PartialEq, Eq, DeriveEntityModel, Serialize)]", rendered)
        self.assertIn('#[serde(rename_all = "camelCase")]', rendered)
        self.assertIn("// OpenModels: default = \"draft-slug\"", rendered)
        self.assertIn("// OpenModels: computed = lower(slug)", rendered)
        self.assertIn("pub status: Option<Status>,", rendered)

        invalid_derives = copy.deepcopy(entity)
        invalid_derives["adapters"]["seaorm-rust"]["extraDerives"] = [""]
        with self.assertRaisesRegex(AdapterError, "extraDerives must contain only non-empty strings"):
            _render_model(invalid_derives)

        no_persisted = copy.deepcopy(entity)
        for field in no_persisted["fields"]:
            field["persisted"] = False
        with self.assertRaisesRegex(AdapterError, "has no persisted fields"):
            _render_model(no_persisted)

        composite_pk = copy.deepcopy(entity)
        composite_pk["fields"][1]["primaryKey"] = True
        with self.assertRaisesRegex(AdapterError, "requires exactly one primary key field"):
            _render_model(composite_pk)

        invalid_field_attributes = copy.deepcopy(entity)
        invalid_field_attributes["fields"][0]["adapters"] = {
            "seaorm-rust": {"extraAttributes": [""]}
        }
        with self.assertRaisesRegex(AdapterError, "extraAttributes"):
            _render_model(invalid_field_attributes)

    def test_relation_helpers_cover_fk_actions_has_one_and_validation(self) -> None:
        model = _canonical_model()
        entity = next(item for item in model["entities"] if item["name"] == "Thing")
        entity_by_name = {item["name"]: item for item in model["entities"]}

        belongs_to = entity["relations"][0]
        has_one = entity["relations"][1]

        self.assertIsNotNone(_matching_foreign_key_constraint(entity, belongs_to))
        self.assertIsNone(_matching_foreign_key_constraint(entity, has_one))

        belongs_to_lines = _relation_attribute_lines(belongs_to, entity, entity_by_name)
        self.assertIn('belongs_to = "super::user::Entity"', belongs_to_lines[-1])
        self.assertIn('on_delete = "Cascade"', belongs_to_lines[-1])
        self.assertIn('on_update = "Restrict"', belongs_to_lines[-1])

        has_one_lines = _relation_attribute_lines(has_one, entity, entity_by_name)
        self.assertEqual(
            '#[sea_orm(has_one = "super::profile::Entity")]',
            has_one_lines[-1],
        )

        invalid_variant = copy.deepcopy(belongs_to)
        invalid_variant["adapters"] = {"seaorm-rust": {"variantName": ""}}
        with self.assertRaisesRegex(AdapterError, "variantName must be a non-empty string"):
            _relation_variant_name(invalid_variant)

        invalid_relation = copy.deepcopy(belongs_to)
        invalid_relation.pop("foreignKey")
        with self.assertRaisesRegex(AdapterError, "requires foreignKey and references"):
            _relation_attribute_lines(invalid_relation, entity, entity_by_name)

        invalid_skip = copy.deepcopy(entity)
        invalid_skip["relations"][0]["adapters"] = {
            "seaorm-rust": {"skipRelatedImpl": "yes"}
        }
        with self.assertRaisesRegex(AdapterError, "skipRelatedImpl must be boolean"):
            _related_impl_lines(invalid_skip, entity_by_name)

        with self.assertRaisesRegex(AdapterError, "Unsupported SeaORM foreign key action"):
            _seaorm_reference_action("archive")

    def test_adapter_generation_covers_enum_validation_and_module_root(self) -> None:
        model = _canonical_model()
        entity = next(item for item in model["entities"] if item["name"] == "Thing")
        enums_by_name = {item["name"]: item for item in model["enums"]}

        active_enums = _active_enums_for_entity(entity, enums_by_name)
        self.assertEqual([("Status", "String(StringLen::None)")], [(item["name"], db_type) for item, db_type in active_enums])

        unknown_enum = copy.deepcopy(entity)
        unknown_enum["fields"][2]["enum"] = "MissingEnum"
        with self.assertRaisesRegex(AdapterError, "references unknown enum"):
            _active_enums_for_entity(unknown_enum, enums_by_name)

        inconsistent_enum = copy.deepcopy(entity)
        inconsistent_enum["fields"].append(
            {
                "name": "statusCode",
                "type": "varchar",
                "persisted": True,
                "generated": "none",
                "enum": "Status",
                "adapters": {"seaorm-rust": {"columnType": "Text"}},
            }
        )
        with self.assertRaisesRegex(AdapterError, "incompatible SeaORM db types"):
            _active_enums_for_entity(inconsistent_enum, enums_by_name)

        generated_files = {
            item.path: item.content
            for item in SEAORM_RUST_ADAPTER.generate_files(model, options={"moduleRoot": "entity"})
        }
        self.assertIn("// Planned indexes:", generated_files["entity/thing.rs"])
        self.assertIn("// Planned constraints:", generated_files["entity/thing.rs"])
        self.assertIn(
            "impl Related<super::profile::Entity> for Entity {",
            generated_files["entity/thing.rs"],
        )

        with self.assertRaisesRegex(AdapterError, "non-empty string for options.moduleRoot"):
            SEAORM_RUST_ADAPTER.generate_files(model, options={"moduleRoot": ""})


if __name__ == "__main__":
    unittest.main()
