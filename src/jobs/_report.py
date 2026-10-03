import re

from src.utils.logger import get_logger

logger = get_logger(__name__)


# collapses a traceback into one readable line for console display
def short_error(exc: BaseException, max_len: int = 220) -> str:
    lines = str(exc).strip().splitlines()
    kept_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("at ", 'File "')) or re.match(
            r"^\.{3}\s*\d+\s*more$", line
        ):
            break
        kept_lines.append(line)
        if len(kept_lines) >= 2:
            break
    message = (
        " -- ".join(kept_lines)
        if kept_lines
        else (lines or [exc.__class__.__name__])[0]
    )
    message = re.sub(r"\s+", " ", message).strip(": ")
    if len(message) > max_len:
        message = message[: max_len - 3].rstrip() + "..."
    return f"{exc.__class__.__name__}: {message}"


# renders a compact ASCII end-of-run summary
def render_report(
    title: str,
    source: str,
    target_schema: str,
    run_id: str,
    dry_run: bool,
    results: list[dict],
    elapsed: float,
    unit: str,
    job_name: str,
    name_column: str = "Collection",
) -> bool:
    failed_results = [
        result
        for result in results
        if result["status"] in ("FAILED", "VALIDATION FAILED")
    ]
    validation_failures = [
        result for result in results if result["validation"] == "FAIL"
    ]
    skipped = sum(1 for result in results if "SKIPPED" in result["status"])
    succeeded = sum(1 for result in results if result["status"] == "SUCCESS")
    has_issues = bool(failed_results) or bool(validation_failures)
    mode_suffix = " dry-run" if dry_run else ""
    logger.info("%s%s", title, mode_suffix)
    logger.info("Source=%s TargetSchema=%s RunId=%s", source, target_schema, run_id)
    for result in results:
        logger.info(
            "%s=%s Status=%s Mode=%s Total=%s Inserted=%s Updated=%s Skipped=%s After=%s Validation=%s Seconds=%.2f",
            name_column,
            result["name"],
            result["status"],
            result["mode"],
            f"{result['total']:,}",
            f"{result['inserted']:,}",
            f"{result['updated']:,}",
            f"{result['skipped']:,}",
            f"{result['after']:,}",
            result["validation"],
            result["seconds"],
        )
        if result["error"]:
            logger.error("Error=%s", result["error"])
    logger.info(
        "Summary %s=%d Succeeded=%d Skipped=%d Failed=%d ValidationFailures=%d TotalRows=%s Inserted=%s Updated=%s NowInPostgres=%s Seconds=%.2f",
        unit,
        len(results),
        succeeded,
        skipped,
        len(failed_results),
        len(validation_failures),
        f"{sum(result['total'] for result in results):,}",
        f"{sum(result['inserted'] for result in results):,}",
        f"{sum(result['updated'] for result in results):,}",
        f"{sum(result['after'] for result in results):,}",
        elapsed,
    )
    logger.info("Result=%s", "COMPLETED_WITH_ISSUES" if has_issues else "SUCCESS")
    return has_issues
