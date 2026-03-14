import copy
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.adapter import AdapterError
from openmodels.common import load_json
from openmodels.generate import generate_artifacts
from openmodels.registry import get_adapter


class SeaOrmPhase3Tests(unittest.TestCase):
    def test_registry_exposes_seaorm_target(self) -> None:
        adapter = get_adapter("seaorm-rust")

        self.assertEqual("seaorm-rust", adapter.key)
        self.assertEqual("entity/mod.rs", adapter.default_filename)

    def test_seaorm_generation_matches_snapshots(self) -> None:
        canonical_model = load_json(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )

        generated_files = {
            item.path: item.content
            for item in generate_artifacts(canonical_model, target="seaorm-rust")
        }

        expected_paths = [
            "entity/mod.rs",
            "entity/post.rs",
            "entity/prelude.rs",
            "entity/user.rs",
        ]
        self.assertEqual(expected_paths, sorted(generated_files))

        for relative_path in expected_paths:
            expected = (
                ROOT_DIR / "examples" / "generated" / "seaorm-entity" / relative_path
            ).read_text()
            self.assertEqual(expected, generated_files[relative_path])

    def test_seaorm_generation_supports_module_root_option(self) -> None:
        canonical_model = load_json(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )
        configured_model = copy.deepcopy(canonical_model)
        configured_model["outputs"] = [
            {
                "target": "seaorm-rust",
                "options": {
                    "moduleRoot": "seaorm_entities",
                },
            }
        ]

        generated_files = generate_artifacts(configured_model)

        self.assertEqual(
            [
                "seaorm_entities/mod.rs",
                "seaorm_entities/post.rs",
                "seaorm_entities/prelude.rs",
                "seaorm_entities/user.rs",
            ],
            sorted(item.path for item in generated_files),
        )

    def test_seaorm_generation_rejects_filename_override(self) -> None:
        canonical_model = load_json(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )

        with self.assertRaises(AdapterError):
            generate_artifacts(
                canonical_model,
                target="seaorm-rust",
                filename="entity.rs",
            )

    def test_seaorm_rejects_multiple_related_impls_to_same_target(self) -> None:
        canonical_model = load_json(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )
        configured_model = copy.deepcopy(canonical_model)
        post_entity = next(
            entity for entity in configured_model["entities"] if entity["name"] == "Post"
        )
        post_entity["relations"].append(
            {
                "name": "reviewer",
                "kind": "belongsTo",
                "targetEntity": "User",
                "ownership": "owner",
                "foreignKey": "authorId",
                "references": "id",
            }
        )

        with self.assertRaisesRegex(AdapterError, "multiple SeaORM relations to 'User'"):
            generate_artifacts(configured_model, target="seaorm-rust")

    def test_seaorm_can_skip_related_impl_generation_per_relation(self) -> None:
        canonical_model = load_json(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )
        configured_model = copy.deepcopy(canonical_model)
        post_entity = next(
            entity for entity in configured_model["entities"] if entity["name"] == "Post"
        )
        post_entity["relations"].append(
            {
                "name": "reviewer",
                "kind": "belongsTo",
                "targetEntity": "User",
                "ownership": "owner",
                "foreignKey": "authorId",
                "references": "id",
                "adapters": {
                    "seaorm-rust": {
                        "skipRelatedImpl": True,
                        "variantName": "Reviewer",
                    }
                },
            }
        )

        generated_files = {
            item.path: item.content
            for item in generate_artifacts(configured_model, target="seaorm-rust")
        }
        post_source = generated_files["entity/post.rs"]

        self.assertIn("Reviewer,", post_source)
        self.assertEqual(1, post_source.count("impl Related<super::user::Entity> for Entity"))

    def test_seaorm_rejects_many_to_many_relations_for_now(self) -> None:
        canonical_model = load_json(
            ROOT_DIR / "examples" / "canonical" / "blog-model.json"
        )
        configured_model = copy.deepcopy(canonical_model)
        user_entity = next(
            entity for entity in configured_model["entities"] if entity["name"] == "User"
        )
        user_entity["relations"][0]["kind"] = "manyToMany"
        user_entity["relations"][0]["throughEntity"] = "UserPostLink"

        with self.assertRaisesRegex(AdapterError, "does not support relation kind 'manyToMany'"):
            generate_artifacts(configured_model, target="seaorm-rust")


if __name__ == "__main__":
    unittest.main()
