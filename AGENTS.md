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
