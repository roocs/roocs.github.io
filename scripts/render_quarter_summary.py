import argparse
import base64
import gzip
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from extract_stats import parse_month


@dataclass
class SiteTotals:
    requests: int = 0
    downloads_size_mb: int = 0
    max_concurrency: int = 0


@dataclass
class KpiStats:
    total_requests: int
    failed_requests: int

    @property
    def failed_pct(self) -> float:
        return (self.failed_requests / self.total_requests) * 100.0

    @property
    def success_pct(self) -> float:
        return 100.0 - self.failed_pct


@dataclass
class FailureSplit:
    wrong_requests: int = 0
    internal_errors: int = 0

    @property
    def total(self) -> int:
        return self.wrong_requests + self.internal_errors


NUMERIC_DTYPES = {
    "int8": ("b", 1),
    "uint8": ("B", 1),
    "int16": ("h", 2),
    "uint16": ("H", 2),
    "int32": ("i", 4),
    "uint32": ("I", 4),
    "int64": ("q", 8),
    "uint64": ("Q", 8),
    "float32": ("f", 4),
    "float64": ("d", 8),
}

WRONG_REQUEST_PATTERNS = [
    r"not in the list of available data",
    r"no valid data points found",
    r"expand the area covered by the bounding box",
    r"no files found in given time range",
    r"no data (found|available)",
    r"(invalid|unsupported) variable",
    r"(invalid|unsupported) (dataset|collection)",
    r"outside .*time range",
    r"time range",
    r"bbox",
]

INTERNAL_ERROR_PATTERNS = [
    r"internal server error",
    r"service unavailable",
    r"gateway timeout",
    r"timed out",
    r"traceback",
    r"exception",
    r"connection (error|reset|refused)",
    r"broken pipe",
    r"worker",
    r"killed",
    r"out of memory",
]


def quarter_to_months(year: int, quarter: int) -> list[str]:
    if quarter not in {1, 2, 3, 4}:
        raise ValueError("quarter must be one of: 1, 2, 3, 4")

    start_month = (quarter - 1) * 3 + 1
    return [f"{year}-{month:02d}" for month in range(start_month, start_month + 3)]


def halfyear_to_months(year: int, half_year: int) -> list[str]:
    if half_year not in {1, 2}:
        raise ValueError("half-year must be one of: 1, 2")

    start_month = 1 if half_year == 1 else 7
    return [f"{year}-{month:02d}" for month in range(start_month, start_month + 6)]


def mb_to_tb_text(mb_value: int) -> str:
    return f"{mb_value / 1024 / 1024:.2f} TB"


def format_int(value: int) -> str:
    return f"{value:,}"


def build_site_totals(months: list[str], site: str) -> SiteTotals:
    totals = SiteTotals()
    for ym in months:
        row = parse_month(ym, site)
        totals.requests += int(row["requests"])
        totals.downloads_size_mb += int(row["downloads_size"])
        totals.max_concurrency = max(totals.max_concurrency, int(row["max_concurrency"]))
    return totals


def quarter_label(quarter: int) -> str:
    labels = {
        1: "January - March",
        2: "April - June",
        3: "July - September",
        4: "October - December",
    }
    return labels[quarter]


def halfyear_label(half_year: int) -> str:
    labels = {
        1: "January - June",
        2: "July - December",
    }
    return labels[half_year]


def _decode_ndarray(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, dict) or value.get("type") != "ndarray":
        return value

    array_data = value.get("array")
    if isinstance(array_data, list):
        return array_data
    if not isinstance(array_data, dict) or array_data.get("type") != "bytes":
        return value

    dtype = value.get("dtype")
    shape = value.get("shape")
    order = value.get("order", "little")
    if dtype not in NUMERIC_DTYPES or not shape:
        return value

    fmt_char, item_size = NUMERIC_DTYPES[dtype]
    n = int(shape[0])

    raw = base64.b64decode(array_data["data"])
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    expected_size = n * item_size
    payload = raw[:expected_size]
    if len(payload) != expected_size:
        return value

    byte_order = "<" if order == "little" else ">"
    return list(struct.unpack(f"{byte_order}{fmt_char * n}", payload))


def _classify_failure_message(message: str) -> str:
    msg = message.lower()
    for pattern in WRONG_REQUEST_PATTERNS:
        if re.search(pattern, msg):
            return "wrong"
    for pattern in INTERNAL_ERROR_PATTERNS:
        if re.search(pattern, msg):
            return "internal"
    # Default unknowns to internal to keep the requested two-way split complete.
    return "internal"


def _extract_overview_values(html_text: str) -> dict[str, str | int | float]:
    soup = BeautifulSoup(html_text, "lxml")
    for script in soup.find_all("script"):
        script_text = script.get_text() or ""
        match = re.search(r"const docs_json = '(.*?)';", script_text, re.S)
        if not match:
            continue
        parsed = json.loads(match.group(1))
        for doc in parsed.values():
            for root in doc.get("roots", []):
                if root.get("name") != "DataTable":
                    continue
                source = root.get("attributes", {}).get("source", {})
                entries = source.get("attributes", {}).get("data", {}).get("entries", [])
                data_dict = {key: value for key, value in entries}
                properties = data_dict.get("property")
                values = data_dict.get("value")
                if not isinstance(properties, list) or not isinstance(values, list):
                    continue
                if "Total Requests" not in properties:
                    continue
                return dict(zip(properties, values))
    raise RuntimeError("Could not find overview DataTable values in dashboard HTML")


def parse_quarter_kpi(year: int, quarter: int) -> KpiStats | None:
    quarter_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "downloads"
        / "dashboard"
        / str(year)
        / f"dashboard-{year}-q{quarter}-all.html"
    )
    if not quarter_path.exists():
        return None

    overview = _extract_overview_values(quarter_path.read_text(encoding="utf-8"))
    if "Total Requests" not in overview or "Failed Requests" not in overview:
        return None

    return KpiStats(
        total_requests=int(overview["Total Requests"]),
        failed_requests=int(overview["Failed Requests"]),
    )


def parse_quarter_failure_split(year: int, quarter: int) -> FailureSplit | None:
    quarter_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "downloads"
        / "dashboard"
        / str(year)
        / f"dashboard-{year}-q{quarter}-all.html"
    )
    if not quarter_path.exists():
        return None

    soup = BeautifulSoup(quarter_path.read_text(encoding="utf-8"), "lxml")
    split = FailureSplit()
    found = False

    for script in soup.find_all("script"):
        script_text = script.get_text() or ""
        match = re.search(r"const docs_json = '(.*?)';", script_text, re.S)
        if not match:
            continue
        parsed = json.loads(match.group(1))
        for doc in parsed.values():
            for root in doc.get("roots", []):
                if root.get("name") != "DataTable":
                    continue
                columns = root.get("attributes", {}).get("columns", [])
                fields = [c.get("attributes", {}).get("field") for c in columns]
                if fields != ["Message", "First", "Last", "Count"]:
                    continue

                entries = (
                    root.get("attributes", {})
                    .get("source", {})
                    .get("attributes", {})
                    .get("data", {})
                    .get("entries", [])
                )
                data_dict = {k: v for k, v in entries}
                messages = _decode_ndarray(data_dict.get("Message", []))
                counts = _decode_ndarray(data_dict.get("Count", []))

                if not isinstance(messages, list) or not isinstance(counts, list):
                    continue

                for message, count in zip(messages, counts):
                    count_value = int(count)
                    if count_value <= 0:
                        continue
                    category = _classify_failure_message(str(message))
                    if category == "wrong":
                        split.wrong_requests += count_value
                    else:
                        split.internal_errors += count_value
                found = True

    if not found:
        return None
    return split


def parse_halfyear_kpi(year: int, half_year: int) -> KpiStats | None:
    quarters = [1, 2] if half_year == 1 else [3, 4]
    quarter_kpis = [parse_quarter_kpi(year, q) for q in quarters]
    if any(kpi is None for kpi in quarter_kpis):
        return None

    total_requests = sum(kpi.total_requests for kpi in quarter_kpis if kpi is not None)
    failed_requests = sum(kpi.failed_requests for kpi in quarter_kpis if kpi is not None)
    return KpiStats(total_requests=total_requests, failed_requests=failed_requests)


def parse_halfyear_failure_split(year: int, half_year: int) -> FailureSplit | None:
    quarters = [1, 2] if half_year == 1 else [3, 4]
    quarter_splits = [parse_quarter_failure_split(year, q) for q in quarters]
    if any(split is None for split in quarter_splits):
        return None

    return FailureSplit(
        wrong_requests=sum(split.wrong_requests for split in quarter_splits if split is not None),
        internal_errors=sum(split.internal_errors for split in quarter_splits if split is not None),
    )


def render_quarter_markdown_block(year: int, quarter: int) -> str:
    months = quarter_to_months(year, quarter)
    all_totals = build_site_totals(months, "all")
    dkrz_totals = build_site_totals(months, "dkrz")
    ipsl_totals = build_site_totals(months, "ipsl")
    quarter_kpi = parse_quarter_kpi(year, quarter)
    failure_split = parse_quarter_failure_split(year, quarter)

    total_requests_display = all_totals.requests
    kpi_lines: list[str] = []
    if quarter_kpi is not None:
        total_requests_display = quarter_kpi.total_requests
        kpi_lines = [
            f"    - Successful Requests: `{quarter_kpi.success_pct:.1f}%`",
            (
                "    - Calculation: "
                f"`{format_int(quarter_kpi.failed_requests)} (failed requests) / "
                f"{format_int(quarter_kpi.total_requests)} (total requests) = "
                f"{quarter_kpi.failed_pct:.1f}% failures -> KPI = {quarter_kpi.success_pct:.1f}%`"
            ),
        ]

    if failure_split is not None and total_requests_display > 0:
        internal_errors_ratio = (failure_split.internal_errors / total_requests_display) * 100.0
        kpi_lines.append(
            "    - Internal Errors Ratio: "
            f"`{internal_errors_ratio:.1f}%` "
            f"(`{format_int(failure_split.internal_errors)} / {format_int(total_requests_display)}`)"
        )

    failed_requests_display = quarter_kpi.failed_requests if quarter_kpi is not None else 0
    if failed_requests_display == 0 and failure_split is not None:
        failed_requests_display = failure_split.total

    lines = [
            f"### Q{quarter}: {quarter_label(quarter)} {year}",
            "",
            "- **Dashboards**",
            f"    - 📊 [ALL](/downloads/dashboard/{year}/dashboard-{year}-q{quarter}-all.html)",
            f"    - 📊 [IPSL](/downloads/dashboard/{year}/dashboard-{year}-q{quarter}-ipsl.html)",
            f"    - 📊 [DKRZ](/downloads/dashboard/{year}/dashboard-{year}-q{quarter}-dkrz.html)",
            "",
            "- **Number of Requests**",
            f"    - **Total**: `{format_int(total_requests_display)}`",
            f"        - **DKRZ**: `{format_int(dkrz_totals.requests)}`",
            f"        - **IPSL**: `{format_int(ipsl_totals.requests)}`",
            "",
            f"- **Failed Requests**: `{format_int(failed_requests_display)}`",
    ]

    if failure_split is not None:
        lines.extend(
            [
                f"    - Wrong Requests: `{format_int(failure_split.wrong_requests)}`",
                f"    - Internal Errors: `{format_int(failure_split.internal_errors)}`",
            ]
        )

    if kpi_lines:
        lines.extend(["", "- **KPI**", *kpi_lines])

    lines.extend(
        [
            "",
            "- **Data Transfer (Subsetted Data)**",
            f"    - **Total**: `{mb_to_tb_text(all_totals.downloads_size_mb)}`",
            f"        - **DKRZ**: `{mb_to_tb_text(dkrz_totals.downloads_size_mb)}`",
            f"        - **IPSL**: `{mb_to_tb_text(ipsl_totals.downloads_size_mb)}`",
            "",
            f"- **Max Concurrency**: #`{all_totals.max_concurrency}`",
        ]
    )

    return "\n".join(lines)


def render_halfyear_markdown_block(year: int, half_year: int) -> str:
    months = halfyear_to_months(year, half_year)
    all_totals = build_site_totals(months, "all")
    dkrz_totals = build_site_totals(months, "dkrz")
    ipsl_totals = build_site_totals(months, "ipsl")
    halfyear_kpi = parse_halfyear_kpi(year, half_year)
    failure_split = parse_halfyear_failure_split(year, half_year)

    total_requests_display = all_totals.requests
    kpi_lines: list[str] = []
    if halfyear_kpi is not None:
        total_requests_display = halfyear_kpi.total_requests
        kpi_lines = [
            f"    - Successful Requests: `{halfyear_kpi.success_pct:.1f}%`",
            (
                "    - Calculation: "
                f"`{format_int(halfyear_kpi.failed_requests)} (failed requests) / "
                f"{format_int(halfyear_kpi.total_requests)} (total requests) = "
                f"{halfyear_kpi.failed_pct:.1f}% failures -> KPI = {halfyear_kpi.success_pct:.1f}%`"
            ),
        ]

    if failure_split is not None and total_requests_display > 0:
        internal_errors_ratio = (failure_split.internal_errors / total_requests_display) * 100.0
        kpi_lines.append(
            "    - Internal Errors Ratio: "
            f"`{internal_errors_ratio:.1f}%` "
            f"(`{format_int(failure_split.internal_errors)} / {format_int(total_requests_display)}`)"
        )

    failed_requests_display = halfyear_kpi.failed_requests if halfyear_kpi is not None else 0
    if failed_requests_display == 0 and failure_split is not None:
        failed_requests_display = failure_split.total

    lines = [
        f"### H{half_year}: {halfyear_label(half_year)} {year}",
        "",
        "- **Number of Requests**",
        f"    - **Total**: `{format_int(total_requests_display)}`",
        f"        - **DKRZ**: `{format_int(dkrz_totals.requests)}`",
        f"        - **IPSL**: `{format_int(ipsl_totals.requests)}`",
        "",
        f"- **Failed Requests**: `{format_int(failed_requests_display)}`",
    ]

    if failure_split is not None:
        lines.extend(
            [
                f"    - Wrong Requests: `{format_int(failure_split.wrong_requests)}`",
                f"    - Internal Errors: `{format_int(failure_split.internal_errors)}`",
            ]
        )

    if kpi_lines:
        lines.extend(["", "- **KPI**", *kpi_lines])

    lines.extend(
        [
            "",
            "- **Data Transfer (Subsetted Data)**",
            f"    - **Total**: `{mb_to_tb_text(all_totals.downloads_size_mb)}`",
            f"        - **DKRZ**: `{mb_to_tb_text(dkrz_totals.downloads_size_mb)}`",
            f"        - **IPSL**: `{mb_to_tb_text(ipsl_totals.downloads_size_mb)}`",
            "",
            f"- **Max Concurrency**: #`{all_totals.max_concurrency}`",
        ]
    )

    return "\n".join(lines)


def upsert_quarter_block(markdown_path: Path, quarter: int, block: str) -> bool:
    text = markdown_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    quarter_prefix = f"### Q{quarter}:"
    start_idx = None
    for idx, line in enumerate(lines):
        if line.startswith(quarter_prefix):
            start_idx = idx
            break

    block_lines = block.splitlines()

    if start_idx is not None:
        end_idx = None
        for idx in range(start_idx + 1, len(lines)):
            if lines[idx].startswith("### Q") or lines[idx].startswith("## Monthly Reports"):
                end_idx = idx
                break
        if end_idx is None:
            end_idx = len(lines)

        new_lines = lines[:start_idx] + block_lines + ["", "---", ""] + lines[end_idx:]
    else:
        insert_idx = None
        for idx, line in enumerate(lines):
            if line.strip() == "## Quarterly Reports":
                insert_idx = idx + 1
                break
        if insert_idx is None:
            raise RuntimeError("Could not locate '## Quarterly Reports' section")

        if insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1

        new_lines = lines[:insert_idx] + [""] + block_lines + ["", "---", ""] + lines[insert_idx:]

    new_text = "\n".join(new_lines).rstrip() + "\n"
    changed = new_text != text
    if changed:
        markdown_path.write_text(new_text, encoding="utf-8")
    return changed


def upsert_halfyear_block(markdown_path: Path, half_year: int, block: str) -> bool:
    text = markdown_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    halfyear_prefix = f"### H{half_year}:"
    start_idx = None
    for idx, line in enumerate(lines):
        if line.startswith(halfyear_prefix):
            start_idx = idx
            break

    block_lines = block.splitlines()

    if start_idx is not None:
        end_idx = None
        for idx in range(start_idx + 1, len(lines)):
            if lines[idx].startswith("### H") or lines[idx].startswith("## Quarterly Reports"):
                end_idx = idx
                break
        if end_idx is None:
            end_idx = len(lines)

        new_lines = lines[:start_idx] + block_lines + ["", "---", ""] + lines[end_idx:]
    else:
        section_idx = None
        for idx, line in enumerate(lines):
            if line.strip() == "## Half-Year Reports":
                section_idx = idx
                break

        if section_idx is None:
            q_idx = None
            for idx, line in enumerate(lines):
                if line.strip() == "## Quarterly Reports":
                    q_idx = idx
                    break
            if q_idx is None:
                raise RuntimeError("Could not locate insertion point for half-year section")

            new_lines = (
                lines[:q_idx]
                + ["## Half-Year Reports", "", *block_lines, "", "---", ""]
                + lines[q_idx:]
            )
        else:
            insert_idx = section_idx + 1
            if insert_idx < len(lines) and lines[insert_idx].strip() == "":
                insert_idx += 1
            new_lines = lines[:insert_idx] + ["", *block_lines, "", "---", ""] + lines[insert_idx:]

    new_text = "\n".join(new_lines).rstrip() + "\n"
    changed = new_text != text
    if changed:
        markdown_path.write_text(new_text, encoding="utf-8")
    return changed


def main() -> None:
    examples = "\n".join(
        [
            "Examples:",
            "  python scripts/render_quarter_summary.py 2026 2",
            "  python scripts/render_quarter_summary.py 2026 --half-year 1",
            "  python scripts/render_quarter_summary.py 2026 2 --update-file",
            "  python scripts/render_quarter_summary.py 2026 --half-year 1 --update-file",
            "  python scripts/render_quarter_summary.py 2026 2 --update-file --print-block",
            "  python scripts/render_quarter_summary.py 2026 2 --dashboard-md docs/dashboard/dashboard-2026.md --update-file",
        ]
    )

    parser = argparse.ArgumentParser(
        description=(
            "Render quarterly or half-year markdown summary blocks from monthly dashboard HTML files "
            "and optionally update the yearly dashboard markdown file in-place."
        ),
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("year", type=int, help="Year to summarize, e.g. 2026")
    parser.add_argument(
        "quarter",
        nargs="?",
        type=int,
        choices=[1, 2, 3, 4],
        help="Quarter number (1-4). Omit when using --half-year.",
    )
    parser.add_argument(
        "--half-year",
        type=int,
        choices=[1, 2],
        default=None,
        help="Half-year number (1 or 2).",
    )
    parser.add_argument(
        "--update-file",
        action="store_true",
        help="Update docs/dashboard/dashboard-<year>.md in-place with the rendered summary block",
    )
    parser.add_argument(
        "--write",
        dest="update_file",
        action="store_true",
        help="Alias for --update-file",
    )
    parser.add_argument(
        "--dashboard-md",
        default=None,
        help="Path to dashboard markdown file (default: docs/dashboard/dashboard-<year>.md)",
    )
    parser.add_argument(
        "--print-block",
        action="store_true",
        help="Print the rendered markdown block even when using --update-file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="When used with --update-file, only print the dashboard markdown path",
    )
    args = parser.parse_args()

    if args.quarter is None and args.half_year is None:
        parser.error("Provide either <quarter> or --half-year")
    if args.quarter is not None and args.half_year is not None:
        parser.error("Use either <quarter> or --half-year, not both")

    try:
        if args.half_year is not None:
            block = render_halfyear_markdown_block(args.year, args.half_year)
        else:
            block = render_quarter_markdown_block(args.year, args.quarter)

        if args.update_file:
            md_path = (
                Path(args.dashboard_md)
                if args.dashboard_md
                else Path(__file__).resolve().parents[1] / "docs" / "dashboard" / f"dashboard-{args.year}.md"
            )
            if not md_path.exists():
                raise FileNotFoundError(
                    f"Dashboard markdown file not found: {md_path}. "
                    "Create it first or pass --dashboard-md."
                )

            if args.half_year is not None:
                changed = upsert_halfyear_block(md_path, args.half_year, block)
            else:
                changed = upsert_quarter_block(md_path, args.quarter, block)
            if args.quiet:
                print(md_path)
            else:
                status = "updated" if changed else "no changes"
                print(f"{md_path} ({status})")

            if args.print_block:
                print()
                print(block)
            return

        print(block)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()