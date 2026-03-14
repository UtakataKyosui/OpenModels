# OpenModels

[English](./README.md) | [日本語](./README.ja.md)

OpenModels is an entity-schema-first toolkit that extends OpenAPI 3.1 with
`x-openmodels` metadata. The goal is to keep OpenAPI as the public API contract
while adding the persistence details needed to generate ORM models, migration
plans, and DTO mappers.

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
- `docs/spec.md`: extension draft and normalization rules
- `schemas/canonical-model.schema.json`: JSON Schema for the normalized IR
- `schemas/x-openmodels.schema.json`: JSON Schema for `x-openmodels`
- `scripts/validate_examples.py`: example validator for DSL and IR samples
- `tests/test_validation.py`: regression tests for DSL and IR validation
- `examples/canonical/blog-model.json`: normalized IR example
- `examples/openapi/blog-api.yaml`: sample OpenAPI document using OpenModels

## Status

This repository is still in the design phase. The current deliverables are the
draft format and examples needed to start building a parser, validator, and IR.

## Testing

Run the current validation tests with:

```bash
python3 -m unittest discover -s tests
```

## License

MIT
