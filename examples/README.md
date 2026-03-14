# Example Corpus

The repository ships with a single blog domain modeled across multiple outputs
and revisions.

## Files

- `openapi/blog-api.yaml`: current OpenAPI + `x-openmodels` source
- `openapi/blog-api-v1.yaml`: previous revision used for migration planning
- `canonical/blog-model.json`: normalized canonical model snapshot
- `generated/blog-schema.ts`: generated Drizzle snapshot
- `generated/seaorm-contract/entity/*.rs`: SeaORM Phase 1 contract snapshots
- `generated/blog-dto-mappers.ts`: generated mapper snapshot
- `generated/blog-dto-mappers.diagnostics.json`: mapper diagnostics snapshot
- `migrations/blog-v1-to-v2.json`: migration plan snapshot

## End-to-End Walkthrough

See [end-to-end/blog/README.md](./end-to-end/blog/README.md) for the full flow.
