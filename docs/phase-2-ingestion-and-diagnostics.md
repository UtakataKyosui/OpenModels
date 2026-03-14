# Phase 2: OpenAPI Ingestion and Diagnostics

## Scope

Phase 2 defines how OpenModels ingests OpenAPI documents and turns them into a
usable normalized model without making unsafe guesses.

## Supported Input Versions

The current implementation supports:

- OpenAPI `3.0.x`
- OpenAPI `3.1.x`

Other versions should fail fast.

## Mapping Strategy

OpenModels reads:

- the top-level OpenAPI document
- the top-level `x-openmodels` extension
- JSON Pointer references from `x-openmodels` back into OpenAPI schema nodes

The normalizer resolves those references and builds the canonical IR used by the
Drizzle generator.

## Nullable Strategy

OpenModels accepts both nullable forms:

- OpenAPI 3.0 style `nullable: true`
- OpenAPI 3.1 style `type: ["string", "null"]`

If persistence nullability is explicitly declared in `column.nullable`, that
wins. Otherwise the normalizer uses OpenAPI metadata only when it can do so
safely.

## Unsupported Constructs

The current MVP does not attempt to infer persistence semantics from:

- `oneOf`
- `anyOf`
- `allOf`
- `discriminator`

If any of these appear on a schema node referenced by `x-openmodels`, the
normalizer raises an explicit error instead of guessing.

## Vendor Extension Strategy

Persistence-only metadata lives under top-level `x-openmodels`. This keeps the
OpenAPI document valid for existing tooling while making the persistence layer
explicit and colocated.

## Diagnostics Rule

The system should prefer explicit failure over silent lossy transforms. The
current implementation therefore fails when:

- a JSON Pointer cannot be resolved
- an unsupported OpenAPI construct is encountered
- a referenced enum, entity, field, or constraint target does not exist
