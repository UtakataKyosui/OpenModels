# SeaORM Phase 3 Relations and Foreign Keys

## Purpose

SeaORM Phase 3 extends the `seaorm-rust` backend from flat entity generation to
relation-aware output.

This phase keeps the Phase 2 entity shape intact while adding canonical
relation wiring where SeaORM can express it directly.

## Generated Surface

Phase 3 adds:

- relation variants inside `pub enum Relation`
- `belongsTo` generation with `from` and `to` column wiring
- foreign key actions on generated `belongsTo` relations when canonical foreign
  key constraints provide `onUpdate` or `onDelete`
- `hasMany` generation
- `hasOne` generation
- `impl Related<...> for Entity` blocks when SeaORM can represent the relation
  unambiguously

## Current Relation Mapping

Supported canonical relation kinds:

- `belongsTo`
- `hasMany`
- `hasOne`

Current behavior:

- `belongsTo` uses `from = "Column::<Field>"` and
  `to = "super::<target>::Column::<Field>"`
- matching canonical foreign key constraints feed `on_update` and `on_delete`
  into the SeaORM relation attribute
- `hasMany` and `hasOne` emit direct SeaORM relation attributes

## Explicitly Unsupported Cases

Phase 3 still does not support:

- `manyToMany`
- generated `Linked` helpers
- multiple auto-generated `impl Related<T>` blocks from one entity to the same
  target entity
- indexes
- unique constraints
- check constraints

Unsupported relation kinds fail explicitly instead of being dropped.

## Escape Hatches

SeaORM-specific relation overrides continue to live under
`adapters.seaorm-rust`.

Phase 3 consumes:

- relation `variantName`
- relation `extraAttributes`
- relation `skipRelatedImpl`

`skipRelatedImpl` is the current escape hatch for cases where SeaORM cannot
express multiple automatic `Related<T>` implementations to the same target from
one entity.

## Constraint Handling

Phase 3 only consumes foreign key constraints when they match a generated
`belongsTo` relation.

Other constraints are still preserved as comments in the generated Rust files:

- indexes
- unique constraints
- check constraints

## Snapshot Shape

Reference SeaORM Phase 3 snapshots live under:

- `examples/generated/seaorm-entity/entity/mod.rs`
- `examples/generated/seaorm-entity/entity/prelude.rs`
- `examples/generated/seaorm-entity/entity/post.rs`
- `examples/generated/seaorm-entity/entity/user.rs`

## Exit Criteria

SeaORM Phase 3 is complete when:

- the blog example emits `Relation` variants and `Related` impls
- canonical foreign key direction is preserved in generated `belongsTo`
  relations
- unsupported relation cases fail explicitly
- snapshot tests lock the generated relation-aware output
