# Phase 1: Canonical DSL and IR

## Purpose

Phase 1 turns `x-openmodels` from a loose extension idea into a generator-safe
definition model. The output of this phase is:

- a stable DSL shape for `x-openmodels`
- explicit semantics for ambiguous field states
- a canonical IR for generators
- validation rules that reject unsafe ambiguity

## DSL Shape

The source DSL remains:

- OpenAPI 3.1
- plus top-level `x-openmodels`

The v0.1 Phase 1 shape includes:

- `enums`
- `entities`
- entity `fields`
- entity `relations`
- entity `indexes`
- entity `constraints`

See [x-openmodels.schema.json](../schemas/x-openmodels.schema.json) for the
machine-readable definition.

## Field Semantics

### Optional

Optionality is an API concern. It is determined by the OpenAPI schema selected
for a given operation shape such as `create`, `read`, or `update`.

OpenModels does not treat "not required in OpenAPI" as equivalent to database
nullability.

### Nullable

Nullability is a persistence concern and is represented in `column.nullable`.
If persistence nullability cannot be derived safely, it must be declared.

### Default

`column.default` means the persistence layer may provide a value when one is not
supplied on insert. This is distinct from OpenAPI optionality.

### Generated

`column.generated` describes who creates the persisted value:

- `database`
- `application`

This is intended for identifiers, timestamps, and other system-managed fields.

### Computed

`computed` describes a field whose value is derived from other fields.

- `expression` is an opaque expression string for generators or adapters
- `stored: true` means the computed value is persisted
- `stored: false` means the field is derived at runtime and not persisted

Computed fields may also be generated. For example, a slug computed by the
application and stored in a column is both `computed` and `generated:
application`.

## Enums

Enums are declared under top-level `x-openmodels.enums`. They provide a named
logical enum that fields can reference through `field.enum`.

This prevents backend adapters from re-deriving enum semantics from raw string
columns or scattered OpenAPI enum declarations.

## Constraints

Phase 1 supports four constraint kinds:

- `primaryKey`
- `unique`
- `foreignKey`
- `check`

Relations and foreign key constraints are intentionally separate:

- relations describe model semantics
- constraints describe storage rules

This separation keeps the IR useful for both ORM code generation and future DDL
planning.

## Canonical IR

Generators do not consume raw `x-openmodels`. They consume a normalized
backend-agnostic IR.

The IR is designed to:

- flatten maps into ordered entity and field collections
- make ownership explicit for relations
- normalize generated/default/computed field state
- carry enough information for multiple backend adapters

See [canonical-model.schema.json](../schemas/canonical-model.schema.json) for
the machine-readable shape.

## Validation Rules

The validator should reject or diagnose at least the following:

- unknown enum references
- unknown relation targets
- unknown field references in indexes or constraints
- foreign key constraints without target entity and field data
- conflicting schema mappings for a field across create/read/update shapes
- computed fields that claim to be non-persisted while requiring a storage-only
  column contract
- ambiguous ownership for relations

## Edge Cases Included in Examples

The Phase 1 examples cover:

- enum-backed fields
- persistence-only fields
- generated fields
- computed stored fields
- relations plus explicit foreign key constraints
- multi-column indexes
- separate API DTOs and persistence entities

## Exit Criteria

Phase 1 is complete when:

- the DSL can represent required persistence concepts without OpenAPI hacks
- ambiguity is rejected via diagnostics instead of inferred silently
- the IR is stable enough for Drizzle adapter implementation
