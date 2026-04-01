import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template

REPO_ROOT = Path(__file__).resolve().parents[1]
STATS_DIR = REPO_ROOT / "docs" / "downloads" / "stats"
DASHBOARD_HTML_DIR = REPO_ROOT / "docs" / "downloads" / "dashboard"
DASHBOARD_MD_DIR = REPO_ROOT / "docs" / "dashboard"


@dataclass
class QuarterRow:
    quarter: str
    requests: int
    downloads: int
    downloads_size_mb: int
    max_concurrency: int


def _read_quarterly_rows(site: str, year: int) -> dict[str, QuarterRow]:
    rows: dict[str, QuarterRow] = {}
    pattern = f"{site}-quarterly-*_metrics.csv"

    for csv_path in sorted(STATS_DIR.glob(pattern)):
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                quarter_key = row["date"]
                if not quarter_key.startswith(f"{year}-Q"):
                    continue
                rows[quarter_key] = QuarterRow(
                    quarter=quarter_key,
                    requests=int(row["requests"]),
                    downloads=int(row["downloads"]),
                    downloads_size_mb=int(row["downloads_size"]),
                    max_concurrency=int(row["max_concurrency"]),
                )

    return rows


def _dashboard_link(year: int, quarter_or_month: str, site: str) -> str:
    if quarter_or_month.startswith("Q"):
        return f"/downloads/dashboard/{year}/dashboard-{year}-{quarter_or_month.lower()}-{site}.html"
    return f"/downloads/dashboard/{year}/dashboard-{year}-{quarter_or_month}-{site}.html"


def _existing_link(path_suffix: str) -> str | None:
    fs_path = REPO_ROOT / "docs" / path_suffix.lstrip("/")
    return path_suffix if fs_path.exists() else None


def _format_int(value: int) -> str:
    return f"{value:,}"


def _month_name(month: int, year: int) -> str:
    names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    return f"{names[month - 1]} {year}"


def _quarter_label(year: int, quarter: str) -> str:
    mapping = {
        "Q1": "January - March",
        "Q2": "April - June",
        "Q3": "July - September",
        "Q4": "October - December",
    }
    return f"{quarter}: {mapping.get(quarter, '')} {year}".strip()


def _mb_to_tb_text(mb_value: int) -> str:
    tb = mb_value / 1024 / 1024
    return f"{tb:,.2f} TB"


def build_report(year: int) -> str:
    dkrz = _read_quarterly_rows("dkrz", year)
    ipsl = _read_quarterly_rows("ipsl", year)
    all_ = _read_quarterly_rows("all", year)

    quarter_ids = sorted(
        {k.split("-")[1] for k in (set(dkrz) | set(ipsl) | set(all_))},
        reverse=True,
    )

    quarter_rows = []
    for qid in quarter_ids:
        key = f"{year}-{qid}"
        d = dkrz.get(key)
        i = ipsl.get(key)
        a = all_.get(key)

        total_requests = a.requests if a else (d.requests if d else 0) + (i.requests if i else 0)
        total_downloads_size_mb = (
            a.downloads_size_mb
            if a
            else (d.downloads_size_mb if d else 0) + (i.downloads_size_mb if i else 0)
        )
        max_concurrency = a.max_concurrency if a else max(
            d.max_concurrency if d else 0, i.max_concurrency if i else 0
        )

        quarter_rows.append(
            {
                "quarter": qid,
                "quarter_label": _quarter_label(year, qid),
                "total_requests": _format_int(total_requests),
                "dkrz_requests": _format_int(d.requests) if d else "-",
                "ipsl_requests": _format_int(i.requests) if i else "-",
                "total_downloads_size": _mb_to_tb_text(total_downloads_size_mb),
                "dkrz_downloads_size": _mb_to_tb_text(d.downloads_size_mb) if d else "-",
                "ipsl_downloads_size": _mb_to_tb_text(i.downloads_size_mb) if i else "-",
                "max_concurrency": _format_int(max_concurrency),
                "all_link": _existing_link(_dashboard_link(year, qid, "all")),
                "dkrz_link": _existing_link(_dashboard_link(year, qid, "dkrz")),
                "ipsl_link": _existing_link(_dashboard_link(year, qid, "ipsl")),
            }
        )

    months = []
    for month in range(12, 0, -1):
        mm = f"{month:02d}"
        all_link = _existing_link(_dashboard_link(year, mm, "all"))
        dkrz_link = _existing_link(_dashboard_link(year, mm, "dkrz"))
        ipsl_link = _existing_link(_dashboard_link(year, mm, "ipsl"))
        if any([all_link, dkrz_link, ipsl_link]):
            months.append(
                {
                    "label": _month_name(month, year),
                    "all_link": all_link,
                    "dkrz_link": dkrz_link,
                    "ipsl_link": ipsl_link,
                }
            )

        template = Template(
                """# Usage Statistics for {{ year }}

## Quarterly Reports
    {% if quarter_rows %}
    {% for row in quarter_rows %}
### {{ row.quarter_label }}

- **Dashboards**
    - 📊 [IPSL]({{ row.ipsl_link if row.ipsl_link else '#' }})
    - 📊 [DKRZ]({{ row.dkrz_link if row.dkrz_link else '#' }})

- **Number of Requests**
    - **Total**: `{{ row.total_requests }}`
        - **DKRZ**: `{{ row.dkrz_requests }}`
        - **IPSL**: `{{ row.ipsl_requests }}`

- **Data Transfer (Subsetted Data)**
    - **Total**: `{{ row.total_downloads_size }}`
        - **DKRZ**: `{{ row.dkrz_downloads_size }}`
        - **IPSL**: `{{ row.ipsl_downloads_size }}`

- **Max Concurrency**: #`{{ row.max_concurrency }}`

{% endfor %}
{% else %}
No quarterly statistics found for {{ year }}.
{% endif %}

---

## Monthly Reports

| Month | IPSL | DKRZ |
|------------------|----------------|----------------|
{% for row in months %}
| **{{ row.label }}** | {% if row.ipsl_link %}[View]({{ row.ipsl_link }}){% else %}-{% endif %} | {% if row.dkrz_link %}[View]({{ row.dkrz_link }}){% else %}-{% endif %} |
{% endfor %}
""",
    trim_blocks=True,
    lstrip_blocks=True,
        )

    return template.render(year=year, quarter_rows=quarter_rows, months=months)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate docs/dashboard/dashboard-<year>.md from quarterly stats CSV files."
    )
    parser.add_argument("year", type=int, help="Report year (e.g. 2026)")
    args = parser.parse_args()

    content = build_report(args.year)
    out_path = DASHBOARD_MD_DIR / f"dashboard-{args.year}.md"
    out_path.write_text(content, encoding="utf-8")
    print(out_path.as_posix())


if __name__ == "__main__":
    main()
