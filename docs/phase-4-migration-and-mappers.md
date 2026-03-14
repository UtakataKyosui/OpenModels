# Phase 4: Migration Planning and DTO Mappers

## Purpose

Phase 4 turns canonical model changes into reviewable migration plans and makes
the API DTO to persistence entity boundary executable.

The output of this phase is:

- a schema diff engine over canonical models
- JSON migration plans with destructive-change warnings
- generated TypeScript mapper files for DTO and entity boundaries
- explicit diagnostics for fields and DTO properties that do not map losslessly

## Migration Planning

Migration planning compares two canonical models and produces a plan with:

- change records such as `addColumn`, `alterColumn`, `dropColumn`, `addIndex`
- destructive-change flags on unsafe operations
- warning records for cases that need human review

Current destructive or review-heavy cases include:

- dropping tables or columns
- changing column type
- renaming the storage column
- tightening nullability
- shrinking a varchar length
- adding a required non-generated column without a default

See:

- [migration.py](../openmodels/migration.py)
- [plan_migration.py](../scripts/plan_migration.py)

## DTO Mapper Generation

Mapper generation reads the OpenAPI document plus the canonical model and emits:

- `dto-mappers.ts`
- `dto-mappers.diagnostics.json`

The generated TypeScript keeps DTO and persistence types separate on purpose.

Current mapper generation supports:

- create DTO to persistence record mapping
- update DTO to partial persistence patch mapping
- persistence record to read DTO mapping
- lightweight scalar conversions such as `Date -> ISO string`

See:

- [mappers.py](../openmodels/mappers.py)
- [generate_mappers.py](../scripts/generate_mappers.py)

## Lossy Mapping Diagnostics

OpenModels now reports when the mapper cannot safely invent a transform.

Examples:

- a required persistence field has no direct create DTO property
- a DTO property exists but is not mapped to any persistence field

This makes cases like `password -> passwordHash` explicit instead of silently
pretending they are direct assignments.

## Fixture Corpus

Phase 4 adds versioned fixtures to prove schema evolution:

- [blog-api-v1.yaml](../examples/openapi/blog-api-v1.yaml)
- [blog-api.yaml](../examples/openapi/blog-api.yaml)
- [blog-v1-to-v2.json](../examples/migrations/blog-v1-to-v2.json)

It also adds mapper snapshots:

- [blog-dto-mappers.ts](../examples/generated/blog-dto-mappers.ts)
- [blog-dto-mappers.diagnostics.json](../examples/generated/blog-dto-mappers.diagnostics.json)

## Exit Criteria

Phase 4 is complete when:

- schema changes can be explained before code generation
- DTO and persistence boundaries are generated as explicit mapping code
- unsafe migration and mapping cases are surfaced for human review
