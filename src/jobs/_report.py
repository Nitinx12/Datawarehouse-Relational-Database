import re


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
    print(f"\n{title}{mode_suffix}")
    print(f"Source={source} TargetSchema={target_schema} RunId={run_id}")
    for result in results:
        print(
            f"{name_column}={result['name']} Status={result['status']} "
            f"Mode={result['mode']} Total={result['total']:,} "
            f"Inserted={result['inserted']:,} Updated={result['updated']:,} "
            f"Skipped={result['skipped']:,} After={result['after']:,} "
            f"Validation={result['validation']} Seconds={result['seconds']:.2f}"
        )
        if result["error"]:
            print(f"  Error={result['error']}")
    print(
        f"Summary {unit}={len(results)} Succeeded={succeeded} Skipped={skipped} "
        f"Failed={len(failed_results)} ValidationFailures={len(validation_failures)} "
        f"TotalRows={sum(result['total'] for result in results):,} "
        f"Inserted={sum(result['inserted'] for result in results):,} "
        f"Updated={sum(result['updated'] for result in results):,} "
        f"NowInPostgres={sum(result['after'] for result in results):,} "
        f"Seconds={elapsed:.2f}"
    )
    print("Result=COMPLETED_WITH_ISSUES" if has_issues else "Result=SUCCESS")
    return has_issues
