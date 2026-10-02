import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _submit import REPO_ROOT, submit

JOB_FILE = REPO_ROOT / "src" / "jobs" / "databricks_to_postgres.py"
JARS = [
    "postgresql.jar",
]


if __name__ == "__main__":
    sys.exit(submit(JOB_FILE, JARS, sys.argv[1:]))
