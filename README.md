# OpenModels

[English](./README.md) | [日本語](./README.ja.md)

OpenModels is an entity-schema-first toolkit that extends OpenAPI 3.1 with
`x-openmodels` metadata. The goal is to keep OpenAPI as the public API contract
while adding the persistence details needed to generate ORM models, migration
plans, and DTO mappers.

Start with [docs/quickstart.md](./docs/quickstart.md) if you want the fastest
path from clone to generated artifacts.

## Why

OpenAPI is strong at describing request and response shapes, but it cannot fully
express persistence concerns such as:

- relation ownership
- join tables
- indexes and unique constraints
- database-only fields
- generated and audit columns
- DTO-to-entity separation

OpenModels does not replace OpenAPI with a new language. It keeps one source
file and adds the missing metadata through `x-openmodels`.

## Approach

```text
OpenAPI 3.1 + x-openmodels
        |
        v
Normalization and validation
        |
        v
Canonical IR
        |
        +--> ORM generators
        +--> migration planners
        +--> DTO mapper generators
```

## Design Principles

- Keep OpenAPI valid. A document should remain usable by normal OpenAPI tools.
- Do not create a custom DSL unless existing formats prove insufficient.
- Treat API schemas and persistence entities as related but separate concepts.
- Prefer explicit metadata over silent inference when persistence semantics are
  ambiguous.
- Normalize to a backend-agnostic IR before generating framework-specific code.

## Current Scope

The first draft focuses on:

- a document-level `x-openmodels` extension
- entity, field, relation, and index declarations
- references back to OpenAPI schema and property paths
- enough structure to drive ORM, migration, and mapper generation later

## First Release Target

The first release is successful when OpenModels can generate Drizzle model
definition code and write it to files.

## Example

```yaml
openapi: 3.1.0
info:
  title: OpenModels Example
  version: 0.1.0
paths: {}
components:
  schemas:
    UserResponse:
      type: object
      required: [id, email]
      properties:
        id:
          type: string
          format: uuid
        email:
          type: string
          format: email
x-openmodels:
  version: "0.1"
  outputs:
    - target: drizzle-pg
      filename: schema.ts
  entities:
    User:
      table: users
      sourceSchemas:
        read: "#/components/schemas/UserResponse"
      fields:
        id:
          schema:
            read: "#/components/schemas/UserResponse/properties/id"
          column:
            type: uuid
            primaryKey: true
            generated: database
        email:
          schema:
            read: "#/components/schemas/UserResponse/properties/email"
          column:
            type: varchar
            length: 255
            unique: true
```

## Repository Layout

- `docs/phase-0-foundation.md`: problem framing, release boundary, and ADR
- `docs/phase-1-dsl-and-ir.md`: DSL and canonical IR decisions for Phase 1
- `docs/phase-2-ingestion-and-diagnostics.md`: OpenAPI ingestion rules and diagnostics
- `docs/phase-3-orm-adapters.md`: adapter contract and code-generation rules
- `docs/phase-4-migration-and-mappers.md`: migration planning and DTO mapper rules
- `docs/phase-5-release-readiness.md`: release-readiness summary
- `docs/seaorm-phase-1-contract.md`: SeaORM target contract and layout decisions
- `docs/seaorm-phase-2-entities.md`: SeaORM entity generation scope and limitations
- `docs/seaorm-phase-3-relations.md`: SeaORM relation and foreign-key generation
- `docs/seaorm-phase-4-fixtures.md`: SeaORM fixture, compile-check, and CI workflow
- `docs/quickstart.md`: end-to-end getting-started guide
- `docs/workflows.md`: day-to-day generator workflows
- `docs/openapi-first-comparison.md`: comparison with plain OpenAPI-first usage
- `docs/release-policy.md`: versioning policy and release checklist
- `docs/rust-rewrite-bootstrap.md`: Rust bootstrap scope and migration entrypoint
- `docs/spec.md`: extension draft and normalization rules
- `openmodels/`: loader, normalizer, adapter registry, and generators
- `rust/openmodels-rs/`: Rust bootstrap workspace for loader, normalization, generators, migration planning, and mapper generation
- `schemas/canonical-model.schema.json`: JSON Schema for the normalized IR
- `schemas/x-openmodels.schema.json`: JSON Schema for `x-openmodels`
- `scripts/generate_models.py`: generic CLI wrapper that reads `x-openmodels.outputs`
- `scripts/generate_mappers.py`: DTO mapper generator
- `scripts/plan_migration.py`: migration plan generator
- `scripts/generate_drizzle.py`: CLI wrapper to generate Drizzle files
- `scripts/check_seaorm_fixture.py`: prepare or compile-check the SeaORM blog fixture
- `scripts/validate_examples.py`: example validator for DSL and IR samples
- `tests/test_generation.py`: normalization and Drizzle generation tests
- `tests/test_ingestion.py`: OpenAPI ingestion and diagnostics tests
- `tests/test_phase4.py`: migration planning and DTO mapper tests
- `tests/test_phase5.py`: end-to-end workflow and release-readiness docs tests
- `tests/test_seaorm_phase3.py`: SeaORM relation-aware generation and snapshot tests
- `tests/test_validation.py`: regression tests for DSL and IR validation
- `examples/canonical/blog-model.json`: normalized IR example
- `examples/README.md`: example corpus overview
- `examples/end-to-end/blog/README.md`: end-to-end walkthrough
- `examples/fixtures/seaorm-blog/`: Cargo fixture template for SeaORM compile checks
- `examples/generated/blog-dto-mappers.ts`: generated mapper snapshot
- `examples/generated/blog-dto-mappers.diagnostics.json`: mapper diagnostics snapshot
- `examples/generated/blog-schema.ts`: generated Drizzle snapshot
- `examples/generated/seaorm-contract/`: SeaORM Phase 1 contract snapshots
- `examples/generated/seaorm-entity/`: generated SeaORM Phase 3 relation-aware snapshots
- `examples/migrations/blog-v1-to-v2.json`: migration plan snapshot
- `examples/openapi/blog-api-v1.yaml`: previous version fixture for schema evolution
- `examples/openapi/blog-api.yaml`: sample OpenAPI document using OpenModels

## Status

The MVP surface is implemented. The current focus is preparing the first public
release candidate around the documented `drizzle-pg` flow, migration planning,
and mapper diagnostics.

A Rust rewrite bootstrap now exists in parallel with the Python reference
implementation. The first Rust milestone covers `loader + normalize + canonical
JSON output`, and now includes `drizzle-pg`, `seaorm-rust`, migration-plan
generation, DTO mapper generation, JSON Schema validation, and example
validation; see
[docs/rust-rewrite-bootstrap.md](./docs/rust-rewrite-bootstrap.md).

## Testing

Run the current validation tests with:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests
```

Run the Rust bootstrap tests with:

```bash
cargo test -p openmodels-rs
```

Run the Rust example validation command with:

```bash
cargo run -p openmodels-rs -- validate-examples
```

See [docs/workflows.md](./docs/workflows.md) for the day-to-day commands and
[docs/release-policy.md](./docs/release-policy.md) for release expectations.

Generate files declared in `x-openmodels.outputs` with:

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

Override the adapter target explicitly when needed with:

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated \
  --target drizzle-pg
```

Generate only the SeaORM files with:

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated \
  --target seaorm-rust
```

Generate DTO mappers from the OpenAPI document with:

```bash
python3 scripts/generate_mappers.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

Generate a migration plan between two model versions with:

```bash
python3 scripts/plan_migration.py \
  --from-input examples/openapi/blog-api-v1.yaml \
  --to-input examples/openapi/blog-api.yaml \
  --out generated/blog-v1-to-v2.json
```

GitHub Actions runs the same checks on every push to `main` and on pull
requests via `.github/workflows/ci.yml`.

You can also normalize the example OpenAPI document through the Rust CLI:

```bash
cargo run -p openmodels-rs -- normalize \
  --input examples/openapi/blog-api.yaml
```

Generate the Drizzle schema through the Rust CLI with:

```bash
cargo run -p openmodels-rs -- generate-drizzle \
  --input examples/openapi/blog-api.yaml
```

Use the generic Rust artifact generator against declared outputs like this:

```bash
cargo run -p openmodels-rs -- generate \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

Generate a migration plan through the Rust CLI with:

```bash
cargo run -p openmodels-rs -- plan-migration \
  --from-input examples/openapi/blog-api-v1.yaml \
  --to-input examples/openapi/blog-api.yaml \
  --out generated/blog-v1-to-v2.json
```

Generate DTO mappers through the Rust CLI with:

```bash
cargo run -p openmodels-rs -- generate-mappers \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated \
  --filename blog-dto-mappers.ts \
  --diagnostics-filename blog-dto-mappers.diagnostics.json
```

Validate the example corpus through the Rust CLI with:

```bash
cargo run -p openmodels-rs -- validate-examples
```

SeaORM currently includes Phase 4 fixture and compile-check coverage around the
Phase 3 relation-aware generator. See
[docs/seaorm-phase-4-fixtures.md](./docs/seaorm-phase-4-fixtures.md) for the
validation workflow,
[docs/seaorm-phase-3-relations.md](./docs/seaorm-phase-3-relations.md) for the
relation surface and current limitations, and keep
[docs/seaorm-phase-2-entities.md](./docs/seaorm-phase-2-entities.md) for the
entity-generation baseline, and keep
[docs/seaorm-phase-1-contract.md](./docs/seaorm-phase-1-contract.md) as the
layout contract reference.

## License

MIT
