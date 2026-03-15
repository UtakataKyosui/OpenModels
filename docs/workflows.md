# Developer Workflows

## 1. Author a Model

1. Start with an OpenAPI document.
2. Add top-level `x-openmodels`.
3. Define entities, fields, relations, indexes, constraints, and outputs.
4. Validate with `python3 scripts/validate_examples.py` or
   `cargo run -p openmodels-rs -- validate-examples`.

## 2. Generate ORM Output

Use `scripts/generate_models.py` to generate the outputs declared in
`x-openmodels.outputs`.

Use `scripts/generate_drizzle.py` only when you want to force the Drizzle target
directly.

## 3. Review DTO Boundaries

Generate mapper files with `scripts/generate_mappers.py`.

Review `dto-mappers.diagnostics.json` before treating the mapper as production
ready. Diagnostics mean OpenModels found a boundary that needs an explicit human
decision or custom transform.

Typical examples:

- hashing a password before writing `passwordHash`
- assigning `authorId` from auth context rather than request body
- formatting date or enum values for API compatibility

## 4. Review Schema Evolution

When the canonical model changes, generate a migration plan:

```bash
python3 scripts/plan_migration.py \
  --from-input old.yaml \
  --to-input new.yaml \
  --out migration-plan.json
```

Treat any warning as a review gate. A warning means the tool believes the change
may be destructive or require a backfill.

## 5. CI Workflow

The repository CI currently enforces:

- JSON Schema and semantic validation of examples
- regression tests for normalization, generation, migration plans, and mappers

Use local commands before pushing:

```bash
python3 scripts/validate_examples.py
cargo run -p openmodels-rs -- validate-examples
python3 -m unittest discover -s tests
```
