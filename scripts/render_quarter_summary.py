import argparse
from dataclasses import dataclass
from pathlib import Path

from extract_stats import parse_month


@dataclass
class SiteTotals:
    requests: int = 0
    downloads_size_mb: int = 0
    max_concurrency: int = 0


def quarter_to_months(year: int, quarter: int) -> list[str]:
    if quarter not in {1, 2, 3, 4}:
        raise ValueError("quarter must be one of: 1, 2, 3, 4")

    start_month = (quarter - 1) * 3 + 1
    return [f"{year}-{month:02d}" for month in range(start_month, start_month + 3)]


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


def render_markdown_block(year: int, quarter: int) -> str:
    months = quarter_to_months(year, quarter)
    all_totals = build_site_totals(months, "all")
    dkrz_totals = build_site_totals(months, "dkrz")
    ipsl_totals = build_site_totals(months, "ipsl")

    return "\n".join(
        [
            f"### Q{quarter}: {quarter_label(quarter)} {year}",
            "",
            "- **Dashboards**",
            f"    - 📊 [ALL](/downloads/dashboard/{year}/dashboard-{year}-q{quarter}-all.html)",
            f"    - 📊 [IPSL](/downloads/dashboard/{year}/dashboard-{year}-q{quarter}-ipsl.html)",
            f"    - 📊 [DKRZ](/downloads/dashboard/{year}/dashboard-{year}-q{quarter}-dkrz.html)",
            "",
            "- **Number of Requests**",
            f"    - **Total**: `{format_int(all_totals.requests)}`",
            f"        - **DKRZ**: `{format_int(dkrz_totals.requests)}`",
            f"        - **IPSL**: `{format_int(ipsl_totals.requests)}`",
            "",
            "- **Data Transfer (Subsetted Data)**",
            f"    - **Total**: `{mb_to_tb_text(all_totals.downloads_size_mb)}`",
            f"        - **DKRZ**: `{mb_to_tb_text(dkrz_totals.downloads_size_mb)}`",
            f"        - **IPSL**: `{mb_to_tb_text(ipsl_totals.downloads_size_mb)}`",
            "",
            f"- **Max Concurrency**: #`{all_totals.max_concurrency}`",
        ]
    )


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


def main() -> None:
    examples = "\n".join(
        [
            "Examples:",
            "  python scripts/render_quarter_summary.py 2026 2",
            "  python scripts/render_quarter_summary.py 2026 2 --update-file",
            "  python scripts/render_quarter_summary.py 2026 2 --update-file --print-block",
            "  python scripts/render_quarter_summary.py 2026 2 --dashboard-md docs/dashboard/dashboard-2026.md --update-file",
        ]
    )

    parser = argparse.ArgumentParser(
        description=(
            "Render a quarterly markdown summary block from monthly dashboard HTML files "
            "and optionally update the yearly dashboard markdown file in-place."
        ),
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("year", type=int, help="Year to summarize, e.g. 2026")
    parser.add_argument("quarter", type=int, choices=[1, 2, 3, 4], help="Quarter number (1-4)")
    parser.add_argument(
        "--update-file",
        action="store_true",
        help="Update docs/dashboard/dashboard-<year>.md in-place with the rendered quarter block",
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

    try:
        block = render_markdown_block(args.year, args.quarter)

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