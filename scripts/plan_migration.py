#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from openmodels.model_io import load_canonical_model
from openmodels.migration import plan_migration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a migration plan between two OpenModels inputs."
    )
    parser.add_argument("--from-input", required=True, help="Previous model input path.")
    parser.add_argument("--to-input", required=True, help="Next model input path.")
    parser.add_argument("--out", required=True, help="Output JSON file path.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    before_model = load_canonical_model(args.from_input)
    after_model = load_canonical_model(args.to_input)
    plan = plan_migration(before_model, after_model)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(f"Generated migration plan: {out_path}")


if __name__ == "__main__":
    main()
