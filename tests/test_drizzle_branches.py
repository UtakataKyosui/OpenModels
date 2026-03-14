import copy
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.drizzle import (
    _collect_adapter_imports,
    _render_column_type,
    _render_constraint,
    _render_relation,
    generate_drizzle_schema,
)


class DrizzleBranchTests(unittest.TestCase):
    def test_render_column_type_variants_and_errors(self) -> None:
        self.assertEqual(
            'jsonb("metadata")',
            _render_column_type(
                {
                    "name": "metadata",
                    "type": "json",
                    "adapters": {"drizzle-pg": {"columnFactory": "jsonb"}},
                }
            ),
        )
        self.assertEqual(
            'varchar("title")',
            _render_column_type({"name": "title", "type": "varchar"}),
        )
        self.assertEqual(
            'timestamp("created_at", { precision: 3, mode: "date" })',
            _render_column_type({"name": "createdAt", "storageName": "created_at", "type": "timestamp", "precision": 3}),
        )
        self.assertEqual(
            'integer("count")',
            _render_column_type({"name": "count", "type": "integer"}),
        )
        self.assertEqual(
            'boolean("enabled")',
            _render_column_type({"name": "enabled", "type": "boolean"}),
        )
        with self.assertRaisesRegex(ValueError, "Unsupported Drizzle PostgreSQL type"):
            _render_column_type({"name": "payload", "type": "json"})

    def test_render_constraint_variants(self) -> None:
        tables_by_entity = {"Thing": "things", "Other": "others"}

        self.assertEqual(
            'uniqueIndex("things_name_key").on(table.name)',
            _render_constraint(
                {"kind": "unique", "name": "things_name_key", "fields": ["name"]},
                tables_by_entity,
            ),
        )
        self.assertEqual(
            'check("things_name_check", sql`name <> \'\'`)',
            _render_constraint(
                {"kind": "check", "name": "things_name_check", "expression": "name <> ''"},
                tables_by_entity,
            ),
        )
        self.assertIsNone(
            _render_constraint(
                {
                    "kind": "foreignKey",
                    "name": "inline_fk",
                    "fields": ["otherId"],
                    "references": {"entity": "Other", "fields": ["id"]},
                },
                tables_by_entity,
            )
        )
        self.assertEqual(
            'foreignKey({ name: "compound_fk", columns: [table.id, table.slug], foreignColumns: [others.id, others.slug] }).onDelete("cascade").onUpdate("restrict")',
            _render_constraint(
                {
                    "kind": "foreignKey",
                    "name": "compound_fk",
                    "fields": ["id", "slug"],
                    "references": {
                        "entity": "Other",
                        "fields": ["id", "slug"],
                        "onDelete": "cascade",
                        "onUpdate": "restrict",
                    },
                },
                tables_by_entity,
            ),
        )
        self.assertEqual(
            'primaryKey({ name: "things_pk", columns: [table.id, table.slug] })',
            _render_constraint(
                {"kind": "primaryKey", "name": "things_pk", "fields": ["id", "slug"]},
                tables_by_entity,
            ),
        )
        self.assertEqual(
            "primaryKey({ columns: [table.id] })",
            _render_constraint(
                {"kind": "primaryKey", "fields": ["id"]},
                tables_by_entity,
            ),
        )
        self.assertIsNone(_render_constraint({"kind": "custom"}, tables_by_entity))

    def test_render_relation_variants(self) -> None:
        tables_by_entity = {
            "Thing": "things",
            "Profile": "profiles",
            "Team": "teams",
        }

        self.assertIsNone(_render_relation({"table": "things", "relations": []}, tables_by_entity))

        rendered = _render_relation(
            {
                "table": "things",
                "relations": [
                    {
                        "name": "profileOwner",
                        "kind": "hasOne",
                        "ownership": "owner",
                        "targetEntity": "Profile",
                        "foreignKey": "profileId",
                        "references": "id",
                    },
                    {
                        "name": "profileInverse",
                        "kind": "hasOne",
                        "ownership": "inverse",
                        "targetEntity": "Profile",
                    },
                    {
                        "name": "teams",
                        "kind": "manyToMany",
                        "ownership": "inverse",
                        "targetEntity": "Team",
                        "throughEntity": "ThingTeam",
                    },
                ],
            },
            tables_by_entity,
        )

        assert rendered is not None
        self.assertIn("profileOwner: one(profiles, {", rendered)
        self.assertIn("fields: [things.profileId]", rendered)
        self.assertIn("references: [profiles.id]", rendered)
        self.assertIn("profileInverse: one(profiles)", rendered)
        self.assertIn("TODO: wire many-to-many relation 'teams' through ThingTeam", rendered)

    def test_generate_drizzle_schema_honors_adapter_imports_and_custom_factories(self) -> None:
        canonical_model = {
            "version": "0.1",
            "enums": [],
            "entities": [
                {
                    "name": "Metric",
                    "table": "metrics",
                    "relations": [],
                    "indexes": [],
                    "constraints": [],
                    "adapters": {
                        "drizzle-pg": {
                            "tableFactory": "customTable",
                            "imports": {
                                "pgCore": ["customTable"],
                                "orm": ["customOrmHelper"],
                            },
                        }
                    },
                    "fields": [
                        {
                            "name": "id",
                            "type": "uuid",
                            "nullable": False,
                            "persisted": True,
                            "generated": "database",
                            "primaryKey": True,
                        },
                        {
                            "name": "payload",
                            "type": "json",
                            "nullable": False,
                            "persisted": True,
                            "generated": "database",
                            "computed": {"expression": "build_payload()", "stored": True},
                            "adapters": {
                                "drizzle-pg": {
                                    "columnFactory": "jsonb",
                                    "imports": {
                                        "pgCore": ["jsonb"],
                                        "orm": ["sql"],
                                    },
                                }
                            },
                        },
                    ],
                }
            ],
        }

        generated = generate_drizzle_schema(copy.deepcopy(canonical_model))

        self.assertIn('import { customOrmHelper, sql } from "drizzle-orm";', generated)
        self.assertIn('import { customTable, jsonb, pgTable, uuid } from "drizzle-orm/pg-core";', generated)
        self.assertIn('export const metrics = customTable(', generated)
        self.assertIn(
            'payload: jsonb("payload").notNull().generatedAlwaysAs(sql`build_payload()`),',
            generated,
        )

    def test_collect_adapter_imports_reads_both_import_sets(self) -> None:
        pg_core_imports: set[str] = set()
        orm_imports: set[str] = set()

        _collect_adapter_imports(
            {
                "adapters": {
                    "drizzle-pg": {
                        "imports": {
                            "pgCore": ["uuid", "jsonb"],
                            "orm": ["sql", "desc"],
                        }
                    }
                }
            },
            pg_core_imports,
            orm_imports,
        )

        self.assertEqual({"jsonb", "uuid"}, pg_core_imports)
        self.assertEqual({"desc", "sql"}, orm_imports)


if __name__ == "__main__":
    unittest.main()
