import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.loader import load_openapi_document
from openmodels.normalize import NormalizationError, normalize_openapi_document


def _write_document(payload: dict) -> Path:
    temp_file = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    with temp_file:
        yaml.safe_dump(payload, temp_file)
    return Path(temp_file.name)


class IngestionTests(unittest.TestCase):
    def test_loader_accepts_openapi_3_0(self) -> None:
        path = _write_document(
            {
                "openapi": "3.0.3",
                "info": {"title": "Test", "version": "0.1.0"},
                "paths": {},
                "components": {
                    "schemas": {
                        "ThingInput": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
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
                                "name": {
                                    "schema": {
                                        "create": "#/components/schemas/ThingInput/properties/name"
                                    },
                                    "column": {"type": "varchar", "length": 120},
                                }
                            },
                        }
                    },
                },
            }
        )
        self.addCleanup(path.unlink, missing_ok=True)

        document = load_openapi_document(path)

        self.assertEqual("3.0.3", document["openapi"])

    def test_normalize_respects_openapi_3_0_nullable(self) -> None:
        path = _write_document(
            {
                "openapi": "3.0.3",
                "info": {"title": "Test", "version": "0.1.0"},
                "paths": {},
                "components": {
                    "schemas": {
                        "ThingInput": {
                            "type": "object",
                            "properties": {
                                "nickname": {"type": "string", "nullable": True},
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
                                "nickname": {
                                    "schema": {
                                        "create": "#/components/schemas/ThingInput/properties/nickname"
                                    },
                                    "column": {"type": "varchar", "length": 120},
                                }
                            },
                        }
                    },
                },
            }
        )
        self.addCleanup(path.unlink, missing_ok=True)

        document = load_openapi_document(path)
        normalized = normalize_openapi_document(document)

        self.assertTrue(normalized["entities"][0]["fields"][0]["nullable"])

    def test_normalize_rejects_one_of(self) -> None:
        path = _write_document(
            {
                "openapi": "3.1.0",
                "info": {"title": "Test", "version": "0.1.0"},
                "paths": {},
                "components": {
                    "schemas": {
                        "ThingInput": {
                            "type": "object",
                            "properties": {
                                "value": {
                                    "oneOf": [{"type": "string"}, {"type": "integer"}]
                                },
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
        )
        self.addCleanup(path.unlink, missing_ok=True)

        document = load_openapi_document(path)

        with self.assertRaises(NormalizationError) as exc:
            normalize_openapi_document(document)

        self.assertIn("oneOf", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
