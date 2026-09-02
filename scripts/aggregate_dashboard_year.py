#!/usr/bin/env python3
"""Aggregate one year of monthly ROOCS dashboard HTML exports.

Uses only Python's standard library and writes monthly CSV, Markdown, and five
SVG charts. Requests, failures, and data volume are summed across DKRZ and IPSL.
Overall concurrency is the higher of the two site peaks in each month.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD_DIR = REPO_ROOT / "docs" / "downloads" / "dashboard"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "downloads" / "stats"
DEFAULT_PAGE_DIR = REPO_ROOT / "docs" / "dashboard"
SITES = ("dkrz", "ipsl")
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass(frozen=True)
class Metrics:
    requests: int
    failures: int
    peak_concurrency: int
    subsetted_data_gb: float


def _objects(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _overview_values(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    for encoded in re.findall(r"const docs_json = '(.*?)';", text, re.S):
        documents = json.loads(encoded)
        for document in documents.values():
            for root in _objects(document.get("roots", [])):
                data = root.get("attributes", {}).get("data", {})
                if not isinstance(data, dict):
                    continue
                entries = dict(data.get("entries", [])) if "entries" in data else data
                properties, values = entries.get("property"), entries.get("value")
                if isinstance(properties, list) and isinstance(values, list) and "Total Requests" in properties:
                    return dict(zip(properties, values))
    raise RuntimeError(f"Could not find overview values in {path}")


def _data_size_gb(value: object) -> float:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(KB|MB|GB|TB)\s*", str(value), re.I)
    if not match:
        raise ValueError(f"Could not parse data size: {value!r}")
    amount, unit = float(match.group(1)), match.group(2).upper()
    return amount * {"KB": 1 / 1024 / 1024, "MB": 1 / 1024, "GB": 1, "TB": 1024}[unit]


def parse_month(path: Path) -> Metrics:
    values = _overview_values(path)
    concurrency = str(values["Concurrency per day (min/max/median)"]).split("/")
    if len(concurrency) < 2:
        raise ValueError(f"Could not parse concurrency in {path}")
    return Metrics(
        requests=int(values["Total Requests"]),
        failures=int(values["Failed Requests"]),
        peak_concurrency=int(float(concurrency[1].strip())),
        subsetted_data_gb=_data_size_gb(values["Total data transfer"]),
    )


def read_year(year: int, dashboard_dir: Path) -> list[dict[str, object]]:
    rows = []
    for month in range(1, 13):
        month_id = f"{year}-{month:02d}"
        sites = {site: parse_month(dashboard_dir / str(year) / f"dashboard-{month_id}-{site}.html") for site in SITES}
        rows.append({
            "month": month_id,
            "dkrz": sites["dkrz"],
            "ipsl": sites["ipsl"],
            "requests": sum(item.requests for item in sites.values()),
            "failures": sum(item.failures for item in sites.values()),
            "subsetted_data_gb": sum(item.subsetted_data_gb for item in sites.values()),
            "peak_concurrency": max(item.peak_concurrency for item in sites.values()),
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = ["month", "requests", "successful_requests", "failures", "failure_rate_percent", "subsetted_data_gb", "peak_concurrency", "dkrz_requests", "dkrz_successful_requests", "dkrz_failures", "dkrz_peak_concurrency", "dkrz_subsetted_data_gb", "ipsl_requests", "ipsl_successful_requests", "ipsl_failures", "ipsl_peak_concurrency", "ipsl_subsetted_data_gb"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            dkrz, ipsl = row["dkrz"], row["ipsl"]
            requests, failures = int(row["requests"]), int(row["failures"])
            writer.writerow({
                "month": row["month"], "requests": requests,
                "successful_requests": requests - failures, "failures": failures,
                "failure_rate_percent": f"{failures / requests * 100:.3f}",
                "subsetted_data_gb": f"{float(row['subsetted_data_gb']):.2f}",
                "peak_concurrency": row["peak_concurrency"],
                "dkrz_requests": dkrz.requests,
                "dkrz_successful_requests": dkrz.requests - dkrz.failures,
                "dkrz_failures": dkrz.failures,
                "dkrz_peak_concurrency": dkrz.peak_concurrency,
                "dkrz_subsetted_data_gb": f"{dkrz.subsetted_data_gb:.2f}",
                "ipsl_requests": ipsl.requests,
                "ipsl_successful_requests": ipsl.requests - ipsl.failures,
                "ipsl_failures": ipsl.failures,
                "ipsl_peak_concurrency": ipsl.peak_concurrency,
                "ipsl_subsetted_data_gb": f"{ipsl.subsetted_data_gb:.2f}",
            })


def _totals(rows: list[dict[str, object]], site: str | None = None) -> Metrics:
    values = [row[site] if site else row for row in rows]
    if site:
        return Metrics(sum(v.requests for v in values), sum(v.failures for v in values), max(v.peak_concurrency for v in values), sum(v.subsetted_data_gb for v in values))
    return Metrics(sum(int(v["requests"]) for v in values), sum(int(v["failures"]) for v in values), max(int(v["peak_concurrency"]) for v in values), sum(float(v["subsetted_data_gb"]) for v in values))


def write_markdown(path: Path, year: int, rows: list[dict[str, object]], csv_link: str, chart_links: list[str]) -> None:
    total, dkrz, ipsl = _totals(rows), _totals(rows, "dkrz"), _totals(rows, "ipsl")
    source_note = ""
    if year == 2025:
        source_note = """
Source note: the raw March IPSL export reports 45 requests and 0.19 GB. The
existing 2025 dashboard page instead shows manual estimates of 25,000 requests
and 1,500 GB. Applying those estimates would make the annual totals 1,548,370
requests and 104.80 TB; no corresponding failure estimate is available.
"""
    path.write_text(f"""# ROOCS {year} annual summary

This report summarizes monthly usage of the ROOCS subsetting services operated
by DKRZ and IPSL during {year}. Together, the services processed
**{total.requests:,} requests**, of which **{total.requests - total.failures:,} were successful**,
and delivered **{total.subsetted_data_gb / 1000:.2f} TB** of subsetted data.

| Scope | Requests | Successful | Failures | Subsetted data | Peak concurrency |
| --- | ---: | ---: | ---: | ---: | ---: |
| All sites | {total.requests:,} | {total.requests - total.failures:,} | {total.failures:,} ({total.failures / total.requests * 100:.2f}%) | {total.subsetted_data_gb / 1000:.2f} TB | {total.peak_concurrency} |
| DKRZ | {dkrz.requests:,} | {dkrz.requests - dkrz.failures:,} | {dkrz.failures:,} ({dkrz.failures / dkrz.requests * 100:.2f}%) | {dkrz.subsetted_data_gb / 1000:.2f} TB | {dkrz.peak_concurrency} |
| IPSL | {ipsl.requests:,} | {ipsl.requests - ipsl.failures:,} | {ipsl.failures:,} ({ipsl.failures / ipsl.requests * 100:.2f}%) | {ipsl.subsetted_data_gb / 1000:.2f} TB | {ipsl.peak_concurrency} |

## Monthly request outcomes

The green portion of each bar represents successful requests; failures are
shown in red.

### All sites

![Successful and failed requests for all sites]({chart_links[0]})

[Download this chart as SVG]({chart_links[0]}){{: download }}

### DKRZ

![Successful and failed requests for DKRZ]({chart_links[1]})

[Download this chart as SVG]({chart_links[1]}){{: download }}

### IPSL

![Successful and failed requests for IPSL]({chart_links[2]})

[Download this chart as SVG]({chart_links[2]}){{: download }}

### Understanding the failures

Most failed requests were caused by users accessing the services directly
through the CDS API rather than through the CDS portal. In this workflow there
is no CDS catalogue interface to guide or validate the available parameters, so
users commonly rely on trial and error to discover valid request combinations.
These invalid requests are counted as failures even though the service itself
is operating normally.

A smaller share resulted from temporary infrastructure problems, such as full
temporary disks or unavailable Lustre storage. The statistics also include
genuine processing failures discovered during normal operation, including
issues related to calendar handling. The available dashboard data does not
provide a reliable numerical breakdown among these causes.

## Monthly subsetted data

The monthly values combine the data delivered by DKRZ and IPSL.

![Subsetted data across all sites]({chart_links[3]})

[Download this chart as SVG]({chart_links[3]}){{: download }}

## Monthly peak concurrency

For each month, overall concurrency is the higher of the DKRZ and IPSL peak
values. The site peaks are not added because they may have occurred at different
times.

![Peak concurrency across all sites]({chart_links[4]})

[Download this chart as SVG]({chart_links[4]}){{: download }}

## Data and methodology

Request, failure, and subsetted-data totals are sums of the monthly DKRZ and
IPSL dashboard exports. Successful requests are calculated as total requests
minus failed requests. Peak concurrency is not additive: the combined monthly
series uses the higher site value, and the annual value is its maximum.
{source_note}

[Download the monthly source data as CSV]({csv_link}){{: download }}
""", encoding="utf-8")


def _text(x: float, y: float, value: object, size: int = 14, anchor: str = "start", color: str = "#243447", weight: int = 400) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-weight="{weight}">{html.escape(str(value))}</text>'


def _axes(parts: list[str], x: int, y: int, width: int, height: int, maximum: float, formatter) -> None:
    for step in range(5):
        value, py = maximum * step / 4, y + height - height * step / 4
        parts.append(f'<line x1="{x}" y1="{py:.1f}" x2="{x + width}" y2="{py:.1f}" stroke="#e7edf3"/>')
        parts.append(_text(x - 8, py + 5, formatter(value), 11, "end", "#627386"))
    for index, month in enumerate(MONTH_NAMES):
        parts.append(_text(x + width * (index + .5) / 12, y + height + 22, month, 11, "middle", "#627386"))


def _chart_base(title: str, subtitle: str) -> tuple[list[str], tuple[int, int, int, int]]:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="560" viewBox="0 0 1200 560">',
        '<rect width="100%" height="100%" fill="#f5f7fa"/>',
        '<rect x="32" y="28" width="1136" height="500" rx="14" fill="#fff" stroke="#dce4ec"/>',
        _text(64, 72, title, 26, weight=700),
        _text(64, 99, subtitle, 14, color="#627386"),
    ]
    return parts, (126, 135, 998, 330)


def write_request_svg(path: Path, year: int, rows: list[dict[str, object]], site: str | None) -> None:
    label = site.upper() if site else "All sites"
    metrics = [row[site] if site else row for row in rows]
    requests = [item.requests if site else int(item["requests"]) for item in metrics]
    failures = [item.failures if site else int(item["failures"]) for item in metrics]
    successful = [request - failure for request, failure in zip(requests, failures)]
    parts, (px, py, pw, ph) = _chart_base(
        f"{label}: monthly request outcomes · {year}",
        f"{sum(successful):,} successful requests · {sum(failures):,} failures",
    )
    maximum = max(requests) * 1.1 or 1
    _axes(parts, px, py, pw, ph, maximum, lambda v: f"{v / 1000:.0f}k")
    slot, bar_width = pw / 12, pw / 12 * .58
    for index, (success, failure) in enumerate(zip(successful, failures)):
        x = px + slot * index + (slot - bar_width) / 2
        success_height, failure_height = ph * success / maximum, ph * failure / maximum
        parts.append(f'<rect x="{x:.1f}" y="{py + ph - success_height:.1f}" width="{bar_width:.1f}" height="{success_height:.1f}" fill="#2E8B57"/>')
        parts.append(f'<rect x="{x:.1f}" y="{py + ph - success_height - failure_height:.1f}" width="{bar_width:.1f}" height="{failure_height:.1f}" fill="#D64545"/>')
    for x, text_value, color in [(820, "Successful", "#2E8B57"), (980, "Failures", "#D64545")]:
        parts.append(f'<rect x="{x}" y="61" width="18" height="12" fill="{color}"/>')
        parts.append(_text(x + 26, 72, text_value, 13, color="#4d5966"))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_series_svg(path: Path, title: str, subtitle: str, values: list[float], formatter, color: str, line: bool = False) -> None:
    parts, (px, py, pw, ph) = _chart_base(title, subtitle)
    maximum = max(values) * 1.12 or 1
    _axes(parts, px, py, pw, ph, maximum, formatter)
    if line:
        points = " ".join(f"{px + pw * (i + .5) / 12:.1f},{py + ph - ph * value / maximum:.1f}" for i, value in enumerate(values))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="4"/>')
        for index, value in enumerate(values):
            x, y = px + pw * (index + .5) / 12, py + ph - ph * value / maximum
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"/>')
    else:
        slot, bar_width = pw / 12, pw / 12 * .58
        for index, value in enumerate(values):
            x = px + slot * index + (slot - bar_width) / 2
            height = ph * value / maximum
            parts.append(f'<rect x="{x:.1f}" y="{py + ph - height:.1f}" width="{bar_width:.1f}" height="{height:.1f}" fill="{color}"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dashboard-dir", type=Path, default=DEFAULT_DASHBOARD_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--page-dir", type=Path, default=DEFAULT_PAGE_DIR)
    args = parser.parse_args()
    rows = read_year(args.year, args.dashboard_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.page_dir.mkdir(parents=True, exist_ok=True)
    stem = f"roocs-{args.year}"
    csv_path = args.output_dir / f"{stem}-monthly.csv"
    markdown_path = args.page_dir / f"summary-{args.year}.md"
    chart_paths = [
        args.output_dir / f"{stem}-requests-all.svg",
        args.output_dir / f"{stem}-requests-dkrz.svg",
        args.output_dir / f"{stem}-requests-ipsl.svg",
        args.output_dir / f"{stem}-subsetted-data-all.svg",
        args.output_dir / f"{stem}-concurrency-all.svg",
    ]
    write_csv(csv_path, rows)
    write_request_svg(chart_paths[0], args.year, rows, None)
    write_request_svg(chart_paths[1], args.year, rows, "dkrz")
    write_request_svg(chart_paths[2], args.year, rows, "ipsl")
    data_values = [float(row["subsetted_data_gb"]) for row in rows]
    write_series_svg(chart_paths[3], f"All sites: monthly subsetted data · {args.year}", f"Annual total: {sum(data_values) / 1000:.2f} TB", data_values, lambda v: f"{v / 1000:.0f} TB", "#0072B2")
    concurrency_values = [float(row["peak_concurrency"]) for row in rows]
    write_series_svg(chart_paths[4], f"All sites: monthly peak concurrency · {args.year}", "Higher of the DKRZ and IPSL peak values in each month", concurrency_values, lambda v: f"{v:.0f}", "#6F4EAA", line=True)
    csv_link = Path(os.path.relpath(csv_path, markdown_path.parent)).as_posix()
    chart_links = [Path(os.path.relpath(item, markdown_path.parent)).as_posix() for item in chart_paths]
    write_markdown(markdown_path, args.year, rows, csv_link, chart_links)
    print(markdown_path, csv_path, *chart_paths, sep="\n")


if __name__ == "__main__":
    main()
