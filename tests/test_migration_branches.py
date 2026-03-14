import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT_DIR))

from openmodels.migration import plan_migration


def _field(name: str, field_type: str, *, nullable: bool, generated: str = "none", persisted: bool = True, **extra):
    payload = {
        "name": name,
        "type": field_type,
        "nullable": nullable,
        "persisted": persisted,
        "generated": generated,
    }
    payload.update(extra)
    return payload


class MigrationBranchTests(unittest.TestCase):
    def test_plan_migration_covers_table_column_index_and_constraint_changes(self) -> None:
        before_model = {
            "version": "0.1",
            "entities": [
                {
                    "name": "Alpha",
                    "table": "alpha",
                    "fields": [
                        _field("id", "uuid", nullable=False, generated="database", primaryKey=True),
                        _field("name", "varchar", nullable=True, length=20),
                        _field("legacy", "varchar", nullable=False, length=50, default="legacy"),
                    ],
                    "relations": [],
                    "indexes": [
                        {"name": "alpha_name_idx", "fields": ["name"], "unique": False},
                        {"name": "alpha_unique_idx", "fields": ["name"], "unique": True},
                    ],
                    "constraints": [
                        {"kind": "check", "name": "alpha_name_check", "expression": "name <> ''"},
                        {"kind": "unique", "name": "alpha_name_unique", "fields": ["name"]},
                        {
                            "kind": "foreignKey",
                            "name": "alpha_fk_multi",
                            "fields": ["name", "legacy"],
                            "references": {"entity": "Gamma", "fields": ["name", "legacy"]},
                        },
                    ],
                },
                {
                    "name": "Gamma",
                    "table": "gamma",
                    "fields": [
                        _field("id", "uuid", nullable=False, generated="database", primaryKey=True),
                        _field("name", "varchar", nullable=False, length=20),
                        _field("legacy", "varchar", nullable=False, length=20),
                    ],
                    "relations": [],
                    "indexes": [],
                    "constraints": [],
                },
                {
                    "name": "DropMe",
                    "table": "drop_me",
                    "fields": [
                        _field("id", "uuid", nullable=False, generated="database", primaryKey=True),
                    ],
                    "relations": [],
                    "indexes": [],
                    "constraints": [],
                },
            ],
        }
        after_model = {
            "version": "0.2",
            "entities": [
                {
                    "name": "Alpha",
                    "table": "alpha_new",
                    "fields": [
                        _field("id", "uuid", nullable=False, generated="database", primaryKey=True),
                        _field(
                            "name",
                            "text",
                            nullable=False,
                            length=10,
                            storageName="name_v2",
                        ),
                        _field("requiredField", "integer", nullable=False),
                    ],
                    "relations": [],
                    "indexes": [
                        {
                            "name": "alpha_name_idx",
                            "fields": ["name", "requiredField"],
                            "unique": False,
                        },
                        {"name": "alpha_new_idx", "fields": ["requiredField"], "unique": False},
                    ],
                    "constraints": [
                        {
                            "kind": "check",
                            "name": "alpha_name_check",
                            "expression": "char_length(name_v2) > 0",
                        },
                        {
                            "kind": "foreignKey",
                            "name": "alpha_fk_multi",
                            "fields": ["name", "requiredField"],
                            "references": {"entity": "Gamma", "fields": ["name", "legacy"]},
                        },
                        {"kind": "primaryKey", "name": "alpha_pk", "fields": ["id"]},
                    ],
                },
                {
                    "name": "Gamma",
                    "table": "gamma",
                    "fields": [
                        _field("id", "uuid", nullable=False, generated="database", primaryKey=True),
                        _field("name", "varchar", nullable=False, length=20),
                        _field("legacy", "varchar", nullable=False, length=20),
                    ],
                    "relations": [],
                    "indexes": [],
                    "constraints": [],
                },
                {
                    "name": "Beta",
                    "table": "beta",
                    "fields": [
                        _field("id", "uuid", nullable=False, generated="database", primaryKey=True),
                        _field("value", "varchar", nullable=False, length=20, default="x"),
                    ],
                    "relations": [],
                    "indexes": [],
                    "constraints": [],
                },
            ],
        }

        plan = plan_migration(before_model, after_model)

        change_kinds = {change["kind"] for change in plan["changes"]}
        warning_codes = {warning["code"] for warning in plan["warnings"]}

        self.assertTrue(
            {
                "createTable",
                "dropTable",
                "renameTable",
                "addColumn",
                "dropColumn",
                "alterColumn",
                "addIndex",
                "dropIndex",
                "alterIndex",
                "addConstraint",
                "dropConstraint",
                "alterConstraint",
            }.issubset(change_kinds)
        )
        self.assertTrue(
            {
                "drop-table",
                "rename-table",
                "add-required-column-without-default",
                "drop-column",
                "change-column-type",
                "rename-column",
                "tighten-nullability",
                "shrink-column-length",
            }.issubset(warning_codes)
        )
        self.assertEqual("0.1", plan["fromModelVersion"])
        self.assertEqual("0.2", plan["toModelVersion"])
        self.assertGreaterEqual(plan["summary"]["destructiveChanges"], 3)
        self.assertGreaterEqual(plan["summary"]["warnings"], 8)


if __name__ == "__main__":
    unittest.main()
