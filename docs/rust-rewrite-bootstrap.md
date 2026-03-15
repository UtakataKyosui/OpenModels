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
- JSON Pointer and `$ref` resolution
- canonical normalization for the current documented DSL
- snapshot test against `examples/canonical/blog-model.json`

Still Python-only:

- Drizzle generation
- SeaORM generation
- migration planning
- DTO mapper generation
- JSON Schema validation against `schemas/x-openmodels.schema.json`

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

Write the normalized canonical model to a file:

```bash
cargo run -p openmodels-rs -- normalize \
  --input examples/openapi/blog-api.yaml \
  --out /tmp/blog-model.json
```

## Next Steps

- add JSON Schema validation parity with the Python loader
- port Drizzle generation behind the same canonical model types
- port adapter registry and target selection
- replace Python CLI entrypoints incrementally instead of all at once
