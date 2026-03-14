# Phase 3: ORM Adapters and Code Generation

## Purpose

Phase 3 turns the canonical IR into a backend adapter surface rather than a
single hard-coded generator.

The current MVP proves this with a Drizzle PostgreSQL adapter, while keeping the
shape open enough for additional ORM backends later.

## Adapter Contract

Each backend adapter is responsible for:

- declaring a stable target key such as `drizzle-pg`
- exposing a default output filename
- generating one or more files from the canonical IR

See:

- [adapter.py](../openmodels/adapter.py)
- [registry.py](../openmodels/registry.py)

## Output Declaration

The source document can now declare generation targets directly in
`x-openmodels.outputs`.

Example:

```yaml
x-openmodels:
  version: "0.1"
  outputs:
    - target: drizzle-pg
      filename: blog-schema.ts
```

This keeps output intent inside the OpenAPI document instead of pushing it into
CLI-only configuration.

The CLI may still override the target for ad hoc generation, but the document is
the default source of truth.

## Escape Hatches

Backend-specific metadata is carried through the DSL and canonical IR under
`adapters`.

Example:

```yaml
slug:
  column:
    type: varchar
    length: 240
  adapters:
    drizzle-pg:
      chain:
        - ".$type<string>()"
```

Current Drizzle PostgreSQL support recognizes these escape hatches:

- entity `adapters.drizzle-pg.tableFactory`
- field `adapters.drizzle-pg.columnFactory`
- field `adapters.drizzle-pg.chain`
- `adapters.drizzle-pg.imports.pgCore`
- `adapters.drizzle-pg.imports.orm`

This is intentionally narrow. The goal is to unblock backend-specific features
without collapsing the canonical model into adapter-specific syntax.

## Current Backend

The first production target is:

- `drizzle-pg`

Implemented in:

- [drizzle.py](../openmodels/drizzle.py)

## Exit Criteria

Phase 3 is complete when:

- at least one backend is generated end-to-end from the canonical IR
- output targets can be declared in the source YAML
- adapter-specific metadata has a defined escape hatch
- the backend registry can accept a second adapter without redesign
