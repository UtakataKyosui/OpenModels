# Quickstart

## Prerequisites

- Python `3.11` or newer
- the repository checked out locally

## Install

```bash
python3 -m pip install -r requirements-dev.txt
```

## Validate the Reference Examples

```bash
python3 scripts/validate_examples.py
python3 -m unittest discover -s tests
```

## Generate ORM Models

The blog example declares its default output target in
`examples/openapi/blog-api.yaml` under `x-openmodels.outputs`.

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

Expected file:

- `generated/blog-schema.ts`

## Generate DTO Mappers

```bash
python3 scripts/generate_mappers.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated \
  --filename blog-dto-mappers.ts \
  --diagnostics-filename blog-dto-mappers.diagnostics.json
```

Expected files:

- `generated/blog-dto-mappers.ts`
- `generated/blog-dto-mappers.diagnostics.json`

## Plan a Migration

Use the versioned example fixtures to compare two model revisions.

```bash
python3 scripts/plan_migration.py \
  --from-input examples/openapi/blog-api-v1.yaml \
  --to-input examples/openapi/blog-api.yaml \
  --out generated/blog-v1-to-v2.json
```

Expected file:

- `generated/blog-v1-to-v2.json`

## Next Reads

- [workflows.md](./workflows.md)
- [openapi-first-comparison.md](./openapi-first-comparison.md)
- [release-policy.md](./release-policy.md)
