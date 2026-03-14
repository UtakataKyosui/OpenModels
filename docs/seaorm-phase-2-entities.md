# SeaORM Phase 2 Entity Generation

## Purpose

SeaORM Phase 2 upgrades the `seaorm-rust` backend from a layout-only contract to
real Rust entity generation.

The goal of this phase is to emit practical `Entity` modules from the canonical
model without redesigning the generic adapter surface introduced earlier.

Phase 3 builds on this output and adds relation-aware generation. Keep this
document as the entity-shape baseline, and see
`docs/seaorm-phase-3-relations.md` for the current relation surface.

## Generated Surface

The adapter now generates:

- `mod.rs`
- `prelude.rs`
- one Rust module per entity
- `Model` definitions using `DeriveEntityModel`
- `ActiveModel` via SeaORM derives
- `Column` and `PrimaryKey` via SeaORM derives
- Active enums for canonical enum-backed fields

For the blog example the default output looks like this:

```text
entity/
  mod.rs
  prelude.rs
  post.rs
  user.rs
```

## Field Strategy

Phase 2 supports these canonical field shapes directly:

- `uuid` -> `Uuid`
- `varchar` -> `String`
- `text` -> `String`
- `integer` -> `i32`
- `boolean` -> `bool`
- `timestamp` -> `DateTime`
- `timestamptz` -> `DateTimeWithTimeZone`
- nullable fields -> `Option<T>`
- enum-backed fields -> generated `DeriveActiveEnum`

The adapter emits explicit `column_type` attributes so the SeaORM output keeps
the normalized storage shape instead of relying on Rust type inference alone.

## Defaults, Generated Fields, and Computed Fields

Phase 2 keeps default and generated behavior explicit without pretending that
all canonical semantics map cleanly into SeaORM attributes.

Current behavior:

- primary keys are emitted as SeaORM primary keys
- non-integer primary keys are marked with `auto_increment = false`
- database-generated and application-generated fields are preserved as comments
- computed expressions are preserved as comments
- literal defaults are preserved as comments

This keeps the generated module honest about what exists in the canonical model
while avoiding silently invented ORM behavior.

## Escape Hatches

SeaORM-specific overrides continue to live under `adapters.seaorm-rust`.

Phase 2 consumes:

- entity `moduleName`
- entity `extraDerives`
- entity `extraAttributes`
- field `rustType`
- field `columnType`
- field `extraAttributes`

## Deferred to Later Phases

Phase 2 still does not emit:

- `RelationTrait` variants from canonical relations
- foreign key relation wiring
- indexes
- unique constraints
- check constraints
- composite primary keys
- compile validation against a real Cargo fixture

Relations, indexes, and constraints are left as comments in the generated files
so their intent remains visible until the later phases land.

## Snapshot Shape

Reference SeaORM Phase 2 snapshots live under:

- `examples/generated/seaorm-entity/entity/mod.rs`
- `examples/generated/seaorm-entity/entity/prelude.rs`
- `examples/generated/seaorm-entity/entity/post.rs`
- `examples/generated/seaorm-entity/entity/user.rs`

## Exit Criteria

SeaORM Phase 2 is complete when:

- the blog example generates Rust entity modules end-to-end
- snapshot tests lock the emitted structure and content
- `x-openmodels.outputs` can declare `seaorm-rust` next to `drizzle-pg`
- the generated files preserve unsupported metadata explicitly instead of
  dropping it silently
