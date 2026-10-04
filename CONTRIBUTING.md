# Contributing

## Setup

```powershell
uv sync --group dev --frozen
Copy-Item .env.example .env
```

Python 3.11 is required (see `.python-version`).

## Workflow

1. Create a branch from `main`.
2. Run one pipeline stage at a time: `python main.py --only staging`.
3. Run checks before pushing (see below).
4. Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
   `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `build:`, `perf:`, `style:`, `revert:`.
5. Open a PR against `main` and fill in the template.

## Checks

```powershell
uv run ruff check main.py scripts/ tests/ dashboard/ airflow/dags/ src/
uv run ruff format --check main.py scripts/ tests/ dashboard/ airflow/dags/ src/
uv run sqlfluff lint sql/ src/jobs/ tests/
uv run pytest tests/unit -q
docker compose config --quiet
```

SQL changes also need `sqlfluff format` awareness: keywords UPPERCASE, 4-space indent,
`::VARCHAR` casts, one column per line (see `AGENTS.md`).

## Tests

- `tests/unit` runs anywhere, no database needed.
- `tests/data_quality` and `tests/gx` need Postgres running (`docker compose up -d postgres`).
- Full suite: `python scripts/run_all_tests.py`.

## Code style

See `AGENTS.md`: one short comment above each function/class/SQL model, type-hint every
Python signature, keep transforms pure (DataFrame in, DataFrame out).
