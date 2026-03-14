# Release Policy

## Versioning

OpenModels currently has two version surfaces:

- the project release version
- the `x-openmodels.version` inside source documents

### Project Versioning

The project follows semantic versioning goals, with the practical caveat that
`0.x` releases may still change APIs and file formats while the MVP settles.

Rules:

- patch: bug fixes, doc fixes, non-breaking snapshot corrections
- minor: additive features or new generator capabilities
- major: intentional breaking changes once `1.0.0` exists

### Schema Versioning

`x-openmodels.version` tracks the document extension format.

Rules:

- additive compatible DSL changes should bump the minor version
- incompatible DSL or IR changes should bump the major version
- generators should fail explicitly when they cannot support the declared format

## Release Checklist

Before cutting the first public release candidate:

- examples validate and tests pass in CI
- the quickstart can be followed end-to-end from docs alone
- Drizzle generation snapshots are current
- DTO mapper snapshots and diagnostics are current
- migration plan snapshots are current
- open issues for known gaps are triaged into future phases or backlog
- README, quickstart, workflow, and comparison docs are consistent
- the release note explains current scope and non-goals clearly

## Release Candidate Scope

The first public release candidate should present OpenModels as:

- OpenAPI + `x-openmodels`
- canonical IR normalization
- `drizzle-pg` generation
- migration planning
- DTO mapper generation with diagnostics

It should not claim:

- multiple production ORM backends
- automatic migration execution
- lossless automatic mapping for every application-specific transform
