import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import TextIO

REPO_ROOT = Path(__file__).resolve().parents[1]
JARS_DIR = REPO_ROOT / "jars"

FILTERED_LINES = (
    "jdk.incubator.vector",
    "PySpark does not yet fully support pandas",
)
SPARK_TEMP_DIR_MARKER = "Exception while deleting Spark temp dir:"
FILTERED_PATTERNS = (re.compile(r"^\d\d/\d\d/\d\d \d\d:\d\d:\d\d INFO "),)
# the jvm must run in UTC before it starts, builder configs are too late for the driver
JVM_TZ_OPTION = "-Duser.timezone=UTC"


# locates spark-submit next to the running interpreter, then the repo venv, then PATH
def find_spark_submit() -> str:
    names = ("spark-submit.cmd", "spark-submit")
    interpreter_dir = Path(sys.executable).resolve().parent
    venv = REPO_ROOT / ".venv"
    for folder in (interpreter_dir, venv / "Scripts", venv / "bin"):
        for name in names:
            candidate = folder / name
            if candidate.exists():
                return str(candidate)
    found = shutil.which("spark-submit")
    if found:
        return found
    raise FileNotFoundError("spark-submit not found next to python, in .venv or PATH")


# resolves jar names under jars/ and fails early when any is missing
def resolve_jars(jars: list[str]) -> list[str]:
    paths = [JARS_DIR / jar for jar in jars]
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing jars in {JARS_DIR}: {', '.join(missing)}")
    return [str(path) for path in paths]


# forwards one stderr line unless it is known harmless noise
def handle_stderr_line(line: str) -> None:
    if any(token in line for token in FILTERED_LINES):
        return
    if any(pattern.match(line) for pattern in FILTERED_PATTERNS):
        return
    sys.stderr.write(line)
    sys.stderr.flush()


# pumps subprocess stderr while omitting a harmless Windows cleanup traceback
def pump_stderr(stream: TextIO) -> None:
    suppress_cleanup_trace = False
    for line in iter(stream.readline, ""):
        if SPARK_TEMP_DIR_MARKER in line:
            suppress_cleanup_trace = True
            continue
        if suppress_cleanup_trace:
            if not line.strip():
                suppress_cleanup_trace = False
            continue
        handle_stderr_line(line)


# submits a job file with jars and streams its output
def submit(job_file: Path, jars: list[str], argv: list[str]) -> int:
    if not job_file.exists():
        raise FileNotFoundError(f"job file not found: {job_file}")
    command = [
        find_spark_submit(),
        "--master",
        os.getenv("SPARK_MASTER", "local[*]"),
        "--driver-memory",
        os.getenv("SPARK_DRIVER_MEMORY", "4g"),
        "--driver-java-options",
        JVM_TZ_OPTION,
        "--conf",
        f"spark.executor.extraJavaOptions={JVM_TZ_OPTION}",
        "--jars",
        ",".join(resolve_jars(jars)),
        str(job_file),
        *argv,
    ]
    env = os.environ.copy()
    # workers and driver must use the same interpreter as this venv
    env.setdefault("PYSPARK_PYTHON", sys.executable)
    env.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.Popen(
        command,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=REPO_ROOT,
    )
    if proc.stderr is None:
        raise RuntimeError("could not capture spark-submit stderr")
    pump = threading.Thread(target=pump_stderr, args=(proc.stderr,), daemon=True)
    pump.start()
    try:
        code = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        code = 130
    finally:
        pump.join(timeout=5)
    return code
