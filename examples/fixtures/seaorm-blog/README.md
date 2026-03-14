# SeaORM Blog Fixture

This fixture provides the static Cargo template used to compile-check the
generated SeaORM output from `examples/openapi/blog-api.yaml`.

The generated entity files are written into `src/entity/` by:

```bash
python3 scripts/check_seaorm_fixture.py --prepare-only
```

Run the full compile-oriented check with:

```bash
python3 scripts/check_seaorm_fixture.py
```
