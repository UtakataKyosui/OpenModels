# SeaORM Phase 1 Contract

## Purpose

SeaORM Phase 1 defines the backend contract and output layout before OpenModels
attempts real Rust entity generation.

This phase is intentionally planning-oriented. It fixes file structure, target
key, type mapping direction, and escape hatch shape so SeaORM can be implemented
incrementally without redesigning the generic adapter surface.

## Target Key

The stable backend target key is:

- `seaorm-rust`

This keeps the naming aligned with the existing `drizzle-pg` style:

- ORM identity
- implementation language or ecosystem

## Output Layout

SeaORM is modeled as a multi-file backend. The planned default layout is:

```text
entity/
  mod.rs
  prelude.rs
  <entity-module>.rs
```

For the blog example this becomes:

```text
entity/
  mod.rs
  prelude.rs
  post.rs
  user.rs
```

The adapter currently emits contract placeholder files in this layout. These
files are snapshots of the planned structure, not the final SeaORM codegen.

## Type Mapping Matrix

Initial canonical type direction for SeaORM is:

- `uuid` -> `Uuid`
- `varchar` -> `String`
- `text` -> `String`
- `integer` -> `i32`
- `boolean` -> `bool`
- `timestamp` -> `DateTime`
- `timestamptz` -> `DateTimeWithTimeZone`
- enum-backed fields -> Rust enum named from the logical OpenModels enum

Anything outside this set should fail explicitly in later phases rather than
being guessed.

## Escape Hatch Strategy

SeaORM-specific metadata continues to live under `adapters.seaorm-rust`.

Planned keys:

- entity `moduleName`
- entity `extraDerives`
- entity `extraAttributes`
- field `rustType`
- field `columnType`
- field `extraAttributes`
- relation `variantName`
- relation `extraAttributes`

Phase 1 only consumes:

- entity `moduleName`
- field `rustType`

These are enough to fix file naming and type-shape planning without claiming the
full generator already exists.

## Unsupported in Phase 1

Phase 1 does not generate:

- `Entity`, `Model`, or `ActiveModel`
- `RelationTrait`
- indexes or uniqueness declarations
- check constraints
- generated/computed column behavior
- compile-ready SeaORM modules

These are deferred to SeaORM Phases 2 through 4.

## Snapshot Shape

Reference contract snapshots live under:

- `examples/generated/seaorm-contract/entity/mod.rs`
- `examples/generated/seaorm-contract/entity/prelude.rs`
- `examples/generated/seaorm-contract/entity/post.rs`
- `examples/generated/seaorm-contract/entity/user.rs`

## Exit Criteria

SeaORM Phase 1 is complete when:

- the target key and output layout are stable
- the adapter can coexist with `drizzle-pg` in the same registry
- unsupported areas are explicit
- snapshot tests lock the layout contract
