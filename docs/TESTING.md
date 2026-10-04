# Testing

Four tiers, run in order. Each tier gates the next: unit failure skips smoke,
smoke failure skips DQ, DQ failure skips GX for that layer.

## Tiers

| Tier | Location | Needs DB | Command |
| ---- | -------- | -------- | ------- |
| Unit | `tests/unit/` | No | `python -m pytest tests/unit -q` |
| Smoke | `tests/smoke/` | Yes | `python -m pytest tests/smoke -q` |
| DQ | `tests/data_quality/<layer>/` | Yes | `python scripts/run_dq_checks.py --layer staging` |
| GX | `tests/gx/test_*_layer.py` | Yes | `python scripts/run_gx_validations.py` |

Full suite in order: `python scripts/run_all_tests.py`
(`--skip` accepts `unit,smoke,dq,gx`). CI runs ruff, SQLFluff, and unit only.

## DQ checks

One SQL file per check in `tests/data_quality/<layer>/`, named
`NN_descriptive_name.sql` (`source`, `staging`, `warehouse`, `analytics`).
Each file loops its assertions and fails the run on violation; the pass
threshold is `DQ_GATE_MIN_PASS_PCT` in `.env` (default 98.0).

Add a check by copying the nearest-numbered file in the same layer and
keeping the one-assertion-per-file layout.

## GX validations

Table specs live in `scripts/setup_gx_project.py` (`table_specs()`, `LAYERS`);
validation definitions are committed under `gx/validation_definitions/`.
Rebuild the GX project from specs after changing expectations:

```powershell
python scripts/setup_gx_project.py
python scripts/run_gx_validations.py
```

The `master` stage (`run_master()`) validates every table at once and is the
final pipeline gate — it never retries.

## Conventions

- Transforms stay pure functions (DataFrame in, DataFrame out) so unit tests
  never need Spark or Postgres; see `AGENTS.md`.
- SQL checks follow the production style: UPPERCASE keywords, `::VARCHAR`
  casts, one column per line, verified with `sqlfluff lint` before commit.
