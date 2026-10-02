import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JOB_FILE = REPO_ROOT / "src" / "jobs" / "mongo_to_postgres.py"
JARS = [
    "bson-5.1.4.jar",
    "bson-record-codec-5.1.4.jar",
    "mongo-spark-connector_2.12-10.4.0.jar",
    "mongodb-driver-core-5.1.4.jar",
    "mongodb-driver-sync-5.1.4.jar",
    "postgresql.jar",
]


# locates spark-submit, preferring the repo venv
def find_spark_submit() -> str:
    venv_submit = REPO_ROOT / ".venv" / "Scripts" / "spark-submit.cmd"
    if venv_submit.exists():
        return str(venv_submit)
    found = shutil.which("spark-submit")
    if found:
        return found
    raise FileNotFoundError("spark-submit not found in .venv or PATH")


# submits the mongo job, forwarding extra args
def main(argv: list[str]) -> int:
    jars = ",".join(str(REPO_ROOT / "jars" / jar) for jar in JARS)
    command = [
        find_spark_submit(),
        "--master",
        os.getenv("SPARK_MASTER", "local[*]"),
        "--driver-memory",
        os.getenv("SPARK_DRIVER_MEMORY", "4g"),
        "--jars",
        jars,
        str(JOB_FILE),
        *argv,
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
