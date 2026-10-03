import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _submit import REPO_ROOT, submit

JOB_FILE = REPO_ROOT / "src" / "jobs" / "mongo_to_postgres.py"
JARS = [
    "bson-5.1.4.jar",
    "bson-record-codec-5.1.4.jar",
    "mongo-spark-connector_2.12-10.5.0.jar",
    "mongodb-driver-core-5.1.4.jar",
    "mongodb-driver-sync-5.1.4.jar",
    "postgresql.jar",
]


if __name__ == "__main__":
    sys.exit(submit(JOB_FILE, JARS, sys.argv[1:]))
