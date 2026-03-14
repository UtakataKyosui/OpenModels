# Blog End-to-End Example

This example uses the shared fixture at `../../openapi/blog-api.yaml`.

## 1. Generate ORM Output

```bash
python3 scripts/generate_models.py \
  --input examples/openapi/blog-api.yaml \
  --out-dir generated
```

Expected file:

- `generated/blog-schema.ts`

## 2. Generate DTO Mappers

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

## 3. Plan a Migration from the Previous Revision

```bash
python3 scripts/plan_migration.py \
  --from-input examples/openapi/blog-api-v1.yaml \
  --to-input examples/openapi/blog-api.yaml \
  --out generated/blog-v1-to-v2.json
```

Expected file:

- `generated/blog-v1-to-v2.json`

## 4. Validate Everything

```bash
python3 scripts/validate_examples.py
python3 -m unittest discover -s tests
```
