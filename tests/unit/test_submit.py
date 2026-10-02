import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from _submit import FILTERED_PATTERNS, handle_stderr_line


def test_handle_stderr_line_filters_jdk_warning(capsys):
    handle_stderr_line("WARNING: Using incubator modules: jdk.incubator.vector\n")
    assert capsys.readouterr().err == ""


def test_handle_stderr_line_filters_pandas_warning(capsys):
    handle_stderr_line(
        "FutureWarning: PySpark does not yet fully support pandas >= 3\n"
    )
    assert capsys.readouterr().err == ""


def test_handle_stderr_line_filters_jvm_info(capsys):
    handle_stderr_line("26/10/02 15:41:22 INFO ContextHandler: Started foo\n")
    assert capsys.readouterr().err == ""


def test_handle_stderr_line_keeps_jvm_errors(capsys):
    handle_stderr_line("26/10/02 15:41:22 ERROR ContextHandler: boom\n")
    assert "boom" in capsys.readouterr().err


def test_handle_stderr_line_keeps_python_logs(capsys):
    handle_stderr_line("2026-10-02 15:41:22 INFO [src.utils.connection] connected\n")
    assert "connected" in capsys.readouterr().err


def test_filtered_patterns_match_jvm_info_format():
    assert all(
        p.match("26/10/02 15:41:22 INFO Server: stopped") for p in FILTERED_PATTERNS
    )
