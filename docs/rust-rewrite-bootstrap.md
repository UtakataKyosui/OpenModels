# Rust Rewrite Bootstrap

This branch starts the Rust migration without deleting the Python reference
implementation.

## Goal

The first Rust milestone is narrower than a full rewrite:

- read OpenAPI `yaml` and `json`
- validate the OpenAPI version boundary
- require top-level `x-openmodels`
- normalize the document into the existing canonical IR
- write the normalized IR as pretty JSON

This gives the project a stable Rust execution path for `loader` and
`normalize`, which are the safest seams to move first.

## Current Boundary

Implemented in Rust:

- workspace bootstrap under `rust/openmodels-rs`
- typed canonical model structs
- OpenAPI loading
- canonical model input loading for OpenAPI and normalized JSON/YAML
- JSON Schema validation for `x-openmodels` and canonical model files
- JSON Pointer and `$ref` resolution
- canonical normalization for the current documented DSL
- Drizzle PostgreSQL schema generation from the canonical model
- SeaORM Rust entity generation from the canonical model
- migration plan generation from canonical model diffs
- DTO mapper and diagnostics generation from OpenAPI plus canonical model
- adapter registry and generic artifact generation for supported targets
- snapshot test against `examples/canonical/blog-model.json`
- snapshot test against `examples/generated/blog-schema.ts`
- snapshot tests against `examples/generated/seaorm-entity/entity/*.rs`
- snapshot test against `examples/migrations/blog-v1-to-v2.json`
- snapshot tests against `examples/generated/blog-dto-mappers.ts` and
  `examples/generated/blog-dto-mappers.diagnostics.json`

Still Python-only:

- example corpus validation via `scripts/validate_examples.py`

## Commands

Run the Rust tests:

```bash
cargo test -p openmodels-rs
```

Normalize the example OpenAPI document and print JSON to stdout:

```bash
cargo run -p openmodels-rs -- normalize \
  --input examples/openapi/blog-api.yaml
```

Generate the Drizzle schema from the same OpenAPI document:

```bash
cargo run -p openmodels-rs -- generate-drizzle \
  --input examples/openapi/blog-api.yaml
```

Generate declared artifacts into a directory through the generic Rust CLI:

```bash
cargo run -p openmodels-rs -- generate \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

Generate a migration plan between two model versions:

```bash
cargo run -p openmodels-rs -- plan-migration \
  --from-input examples/openapi/blog-api-v1.yaml \
  --to-input examples/openapi/blog-api.yaml \
  --out /tmp/blog-v1-to-v2.json
```

Generate DTO mapper artifacts from the OpenAPI document:

```bash
cargo run -p openmodels-rs -- generate-mappers \
  --input examples/openapi/blog-api.yaml \
  --out-dir /tmp/openmodels-rust-mappers \
  --filename blog-dto-mappers.ts \
  --diagnostics-filename blog-dto-mappers.diagnostics.json
```

Write the normalized canonical model to a file:

```bash
cargo run -p openmodels-rs -- normalize \
  --input examples/openapi/blog-api.yaml \
  --out /tmp/blog-model.json
```

## Next Steps

- port `scripts/validate_examples.py` or replace it with a Rust equivalent
- replace Python CLI entrypoints incrementally instead of all at once
- decide when the Rust CLI should become the default user-facing entrypoint
