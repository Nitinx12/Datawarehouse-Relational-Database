## Comments

Applies to every language in this repo: Python, PySpark, SQL, R, shell.

- One short comment line above a function, class, or SQL model, stating what it does. Nothing more.
- No comments inside a function body. If a line needs explaining, rename the variable or split the function instead of adding a comment.
- No docstrings longer than one line. No comment blocks. No restating the code in prose.
- Good: `# builds the gold fact_orders table`
- Bad: a comment above every line, a paragraph explaining the approach, a TODO essay.

## Python

- Format and lint with `ruff` before every commit.
- Type hint every function signature.
- Keep transforms as pure functions, input DataFrame in, output DataFrame out, so they stay unit testable.
- PySpark: prefer broadcast joins for small dimension tables, write partitioned Delta, never `.collect()` a large DataFrame to the driver.

## SQL

- Casts use `::VARCHAR` style, not `CAST(x AS VARCHAR)`, to satisfy SQLFluff.
- Run SQLFluff format before committing any `.sql` file.
- Keywords UPPERCASE, 4-space indent, one selected column per line, trailing commas.
- One JOIN per line with indented ON; one WHERE condition per line; multi-expression GROUP BY / ORDER BY one per line.
- No `SELECT *` in production SQL; explicit JOIN conditions only; snake_case descriptive aliases, never `x` / `tmp` / `data`.
- CTEs, CASE, and window functions use the multi-line layout in `src/jobs/proc_staging_cust_info.sql`; separate SELECT / JOIN / WHERE / GROUP BY / HAVING / ORDER BY with blank lines.
- Comments use `===` divider headers for file or procedure purpose, otherwise only for non-obvious business logic.
- Never change logic merely for formatting; prefer readable over clever.
- Before returning SQL verify: syntax, JOINs, GROUP BY coverage, ambiguous columns, NULL handling, duplicate-row risk, aggregation, date/time logic, aliases.
