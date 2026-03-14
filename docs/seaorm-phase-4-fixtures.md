# SeaORM Phase 4 Fixtures and Compile Checks

## Purpose

SeaORM Phase 4 hardens the relation-aware generator with a compile-oriented
validation workflow, fixture template, and CI coverage.

The generator surface itself remains the Phase 3 relation-aware output. Phase 4
is about making that output easier to trust and review.

## Fixture Layout

The repository now includes a minimal Cargo fixture template under:

- `examples/fixtures/seaorm-blog/Cargo.toml`
- `examples/fixtures/seaorm-blog/src/lib.rs`
- `examples/fixtures/seaorm-blog/README.md`

Generated SeaORM modules are written into `src/entity/` during validation.

## Compile Check Script

Use the SeaORM fixture helper to prepare or compile-check the generated output:

```bash
python3 scripts/check_seaorm_fixture.py --prepare-only
python3 scripts/check_seaorm_fixture.py
```

The script:

1. reads `examples/openapi/blog-api.yaml`
2. generates `seaorm-rust` output with the current generator
3. writes the generated modules into the fixture `src/entity/`
4. runs `cargo check` unless `--prepare-only` is passed

## CI Coverage

GitHub Actions now runs the SeaORM fixture check in addition to the Python
validation suite.

This gives the project two complementary guardrails:

- Python regression tests for normalization, generation, and snapshots
- Rust `cargo check` for the generated SeaORM fixture

## Current Limitations

Phase 4 still does not claim:

- runtime database integration tests
- query execution tests
- migration compatibility tests
- many-to-many relation codegen
- `Linked` helper generation

The current goal is compile-oriented confidence, not full runtime verification.

## Exit Criteria

SeaORM Phase 4 is complete when:

- a user can generate and compile-check the SeaORM blog fixture from docs alone
- CI runs the fixture preparation and `cargo check`
- generated SeaORM snapshots, docs, and the compile workflow stay in sync
