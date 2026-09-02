#!/usr/bin/env python3
"""Aggregate one year of monthly ROOCS dashboard HTML exports.

Uses only Python's standard library and writes monthly CSV, Markdown, and five
SVG charts. Requests, failures, and data volume are summed across DKRZ and IPSL.
Overall concurrency is the higher of the two site peaks in each month.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import math
import os
import re
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD_DIR = REPO_ROOT / "docs" / "downloads" / "dashboard"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "downloads" / "stats"
DEFAULT_PAGE_DIR = REPO_ROOT / "docs" / "dashboard"
SITES = ("dkrz", "ipsl")
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DTYPES = {"float64": "d", "int64": "q", "int32": "i", "uint32": "I"}


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


def _docs_json_strings(text: str) -> list[str]:
    return re.findall(r"(?:const|var) docs_json = '(.*?)';", text, re.S)


def _decode_values(value: object) -> list[float]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict) or "__ndarray__" not in value:
        raise ValueError("Unsupported chart data array")
    dtype = str(value["dtype"])
    raw = base64.b64decode(value["__ndarray__"])
    length = int(value["shape"][0])
    return list(struct.unpack(f"<{DTYPES[dtype] * length}", raw))


def _chart_series(path: Path, title_prefix: str) -> dict[str, object]:
    for encoded in _docs_json_strings(path.read_text(encoding="utf-8")):
        document = json.loads(encoded)
        objects = list(_objects(document))
        titles = [
            obj.get("attributes", {}).get("text", "")
            for obj in objects
            if obj.get("type") == "Title" or obj.get("name") == "Title"
        ]
        if not any(str(title).startswith(title_prefix) for title in titles):
            continue
        for obj in objects:
            if obj.get("type") != "ColumnDataSource" and obj.get("name") != "ColumnDataSource":
                continue
            data = obj.get("attributes", {}).get("data", {})
            if "entries" in data:
                data = dict(data["entries"])
            if isinstance(data, dict) and ("time" in data or "datetime" in data):
                return data
    raise RuntimeError(f"Could not find {title_prefix!r} chart data in {path}")


def parse_series_month(path: Path, year: int, month: int) -> Metrics:
    activity = _chart_series(path, "Activity - Requests per day")
    concurrency = _chart_series(path, "Max concurrent requests per day")
    transfer = _chart_series(path, "Data transfer per day")

    def month_indices(series: dict[str, object]) -> list[int]:
        key = "time" if "time" in series else "datetime"
        timestamps = _decode_values(series[key])
        return [
            index
            for index, timestamp in enumerate(timestamps)
            if (date := datetime.fromtimestamp(timestamp / 1000, UTC)).year == year
            and date.month == month
        ]

    activity_indices = month_indices(activity)
    success = _decode_values(activity["success"])
    failed = _decode_values(activity["failed"])
    concurrency_indices = month_indices(concurrency)
    running = _decode_values(concurrency["running"])
    transfer_indices = month_indices(transfer)
    sizes = _decode_values(transfer["size"])
    return Metrics(
        requests=int(sum(success[index] + failed[index] for index in activity_indices)),
        failures=int(sum(failed[index] for index in activity_indices)),
        peak_concurrency=int(max((running[index] for index in concurrency_indices if not math.isnan(running[index])), default=0)),
        subsetted_data_gb=sum(sizes[index] for index in transfer_indices),
    )


def _overview_values(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    for encoded in _docs_json_strings(text):
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


def monthly_dashboard_path(dashboard_dir: Path, year: int, month: int, site: str) -> Path:
    month_id = f"{year}-{month:02d}"
    candidates = (
        dashboard_dir / str(year) / f"dashboard-{month_id}-{site}.html",
        dashboard_dir / str(year) / f"{month_id}-dashboard_{site}.html",
        dashboard_dir / str(year) / f"{month_id}-01-dashboard_{site}.html",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No monthly dashboard found for {month_id} {site}")


def source_override(year: int, month: int, site: str, metrics: Metrics | None) -> Metrics:
    if (year, month, site) == (2022, 1, "ceda"):
        if metrics is None:
            raise RuntimeError("The January 2022 CEDA dashboard is required")
        # January transfer is absent from the monthly export. Complete the
        # published Q1 CEDA total of 420 GB after February and March.
        return Metrics(metrics.requests, metrics.failures, metrics.peak_concurrency, 402.68)
    if (year, month, site) == (2022, 4, "ipsl"):
        # The monthly export is missing. Request outcomes and concurrency come
        # from April in the Q2 daily series. Transfer completes the published
        # Q2 IPSL total of 1,366 GB after May and June.
        return Metrics(12586, 298, 13, 630.49)
    if (year, month, site) == (2022, 9, "ipsl"):
        if metrics is None:
            raise RuntimeError("The September 2022 IPSL dashboard is required")
        # The export contains only 49.88 GB. Use the value implied by the
        # published Q3 IPSL total of 2,340 GB.
        return Metrics(metrics.requests, metrics.failures, metrics.peak_concurrency, 895.82)
    if year == 2022 and site == "ceda" and month >= 5:
        return Metrics(0, 0, 0, 0.0)
    if (year, month, site) == (2023, 1, "ipsl"):
        # The file labelled January spans January and February. Request outcome
        # and concurrency values come from January in the Q1 daily series; the
        # transfer value is the estimate in the published 2023 report.
        return Metrics(17813, 4606, 14, 5339.0)
    if year == 2023 and site == "ipsl" and month in (2, 3):
        if metrics is None:
            raise RuntimeError(f"The {year}-{month:02d} IPSL dashboard is required")
        # The Q1 transfer exports are incomplete. Retain their request metrics
        # and use the monthly transfer estimates from the published report.
        transfer_estimate = {2: 4000.0, 3: 2340.0}[month]
        return Metrics(metrics.requests, metrics.failures, metrics.peak_concurrency, transfer_estimate)
    if (year, month, site) == (2023, 10, "ipsl"):
        # The monthly export is missing. Request outcomes and concurrency come
        # from October in the Q4 daily series; transfer is the published estimate.
        return Metrics(23260, 2263, 31, 500.0)
    if (year, month, site) == (2024, 5, "dkrz"):
        if metrics is None:
            raise RuntimeError("The May 2024 DKRZ dashboard is required")
        # The regular export has the complete request counts but only the final
        # 5.60 GB of transfer data. The partial export contains the accumulated
        # transfer value used by the published quarterly report.
        return Metrics(metrics.requests, metrics.failures, metrics.peak_concurrency, 3328.50)
    if (year, month, site) == (2024, 9, "ipsl"):
        # The monthly export is missing. Requests, failures, and concurrency are
        # recovered from September in the full-year IPSL series. The transfer
        # value is the estimate recorded on the existing 2024 dashboard page.
        return Metrics(7149, 841, 18, 140.0)
    if metrics is None:
        raise FileNotFoundError(f"No metrics or source override for {year}-{month:02d} {site}")
    return metrics


def read_2021(dashboard_dir: Path) -> list[dict[str, object]]:
    year_dir = dashboard_dir / "2021"
    annual_paths = {
        site: year_dir / f"2021-dashboard_{site}.html"
        for site in ("dkrz", "ceda")
    }
    rows = []
    for month in range(1, 13):
        if month < 3:
            combined = Metrics(0, 0, 0, 0.0)
            sites = {site: Metrics(0, 0, 0, 0.0) for site in annual_paths}
        else:
            combined = parse_month(year_dir / f"2021-{month:02d}-01-dashboard.html")
            if month < 7:
                sites = {
                    site: parse_series_month(path, 2021, month)
                    for site, path in annual_paths.items()
                }
            else:
                sites = {
                    site: parse_month(year_dir / f"2021-{month:02d}-01-dashboard_{site}.html")
                    for site in annual_paths
                }
        rows.append({
            "month": f"2021-{month:02d}",
            "dkrz": sites["dkrz"],
            "ceda": sites["ceda"],
            "requests": combined.requests,
            "failures": combined.failures,
            "subsetted_data_gb": combined.subsetted_data_gb,
            "peak_concurrency": combined.peak_concurrency,
        })
    return rows


def read_year(year: int, dashboard_dir: Path) -> list[dict[str, object]]:
    if year == 2021:
        return read_2021(dashboard_dir)
    rows = []
    sites_for_year = (*SITES, "ceda") if year == 2022 else SITES
    for month in range(1, 13):
        month_id = f"{year}-{month:02d}"
        sites = {}
        for site in sites_for_year:
            try:
                metrics = parse_month(monthly_dashboard_path(dashboard_dir, year, month, site))
            except FileNotFoundError:
                metrics = None
            sites[site] = source_override(year, month, site, metrics)
        row = {
            "month": month_id,
            "dkrz": sites["dkrz"],
            "ipsl": sites["ipsl"],
            "requests": sum(item.requests for item in sites.values()),
            "failures": sum(item.failures for item in sites.values()),
            "subsetted_data_gb": sum(item.subsetted_data_gb for item in sites.values()),
            "peak_concurrency": max(item.peak_concurrency for item in sites.values()),
        }
        if "ceda" in sites:
            row["ceda"] = sites["ceda"]
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = ["month", "requests", "successful_requests", "failures", "failure_rate_percent", "subsetted_data_gb", "peak_concurrency", "dkrz_requests", "dkrz_successful_requests", "dkrz_failures", "dkrz_peak_concurrency", "dkrz_subsetted_data_gb", "ipsl_requests", "ipsl_successful_requests", "ipsl_failures", "ipsl_peak_concurrency", "ipsl_subsetted_data_gb"]
    if "ceda" in rows[0]:
        fields.extend(["ceda_requests", "ceda_successful_requests", "ceda_failures", "ceda_peak_concurrency", "ceda_subsetted_data_gb"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            dkrz, ipsl = row["dkrz"], row["ipsl"]
            requests, failures = int(row["requests"]), int(row["failures"])
            output_row = {
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
            }
            if "ceda" in row:
                ceda = row["ceda"]
                output_row.update({
                    "ceda_requests": ceda.requests,
                    "ceda_successful_requests": ceda.requests - ceda.failures,
                    "ceda_failures": ceda.failures,
                    "ceda_peak_concurrency": ceda.peak_concurrency,
                    "ceda_subsetted_data_gb": f"{ceda.subsetted_data_gb:.2f}",
                })
            writer.writerow(output_row)


def _totals(rows: list[dict[str, object]], site: str | None = None) -> Metrics:
    values = [row[site] if site else row for row in rows]
    if site:
        return Metrics(sum(v.requests for v in values), sum(v.failures for v in values), max(v.peak_concurrency for v in values), sum(v.subsetted_data_gb for v in values))
    return Metrics(sum(int(v["requests"]) for v in values), sum(int(v["failures"]) for v in values), max(int(v["peak_concurrency"]) for v in values), sum(float(v["subsetted_data_gb"]) for v in values))


def write_csv_2021(path: Path, rows: list[dict[str, object]]) -> None:
    fields = ["month", "requests", "successful_requests", "failures", "failure_rate_percent", "subsetted_data_gb", "peak_concurrency", "dkrz_requests", "dkrz_successful_requests", "dkrz_failures", "dkrz_peak_concurrency", "dkrz_subsetted_data_gb", "ceda_requests", "ceda_successful_requests", "ceda_failures", "ceda_peak_concurrency", "ceda_subsetted_data_gb"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            dkrz, ceda = row["dkrz"], row["ceda"]
            requests, failures = int(row["requests"]), int(row["failures"])
            writer.writerow({
                "month": row["month"], "requests": requests,
                "successful_requests": requests - failures, "failures": failures,
                "failure_rate_percent": f"{failures / requests * 100:.3f}" if requests else "",
                "subsetted_data_gb": f"{float(row['subsetted_data_gb']):.2f}",
                "peak_concurrency": row["peak_concurrency"],
                "dkrz_requests": dkrz.requests,
                "dkrz_successful_requests": dkrz.requests - dkrz.failures,
                "dkrz_failures": dkrz.failures,
                "dkrz_peak_concurrency": dkrz.peak_concurrency,
                "dkrz_subsetted_data_gb": f"{dkrz.subsetted_data_gb:.2f}",
                "ceda_requests": ceda.requests,
                "ceda_successful_requests": ceda.requests - ceda.failures,
                "ceda_failures": ceda.failures,
                "ceda_peak_concurrency": ceda.peak_concurrency,
                "ceda_subsetted_data_gb": f"{ceda.subsetted_data_gb:.2f}",
            })


def write_markdown_2021(path: Path, rows: list[dict[str, object]], csv_link: str, chart_links: list[str]) -> None:
    total, dkrz, ceda = _totals(rows), _totals(rows, "dkrz"), _totals(rows, "ceda")
    path.write_text(f"""# ROOCS 2021 annual summary

Monthly ROOCS reporting began in March 2021. From March through December, the
available combined exports record **{total.requests:,} requests**, of which
**{total.requests - total.failures:,} were successful**, and **{total.subsetted_data_gb / 1000:.2f} TB**
of subsetted data across DKRZ and CEDA.

| Scope | Requests | Successful | Failures | Recorded subsetted data | Peak concurrency |
| --- | ---: | ---: | ---: | ---: | ---: |
| All sites, March–December | {total.requests:,} | {total.requests - total.failures:,} | {total.failures:,} ({total.failures / total.requests * 100:.2f}%) | {total.subsetted_data_gb / 1000:.2f} TB | {total.peak_concurrency} |
| DKRZ | {dkrz.requests:,} | {dkrz.requests - dkrz.failures:,} | {dkrz.failures:,} ({dkrz.failures / dkrz.requests * 100:.2f}%) | {dkrz.subsetted_data_gb / 1000:.2f} TB | {dkrz.peak_concurrency} |
| CEDA | {ceda.requests:,} | {ceda.requests - ceda.failures:,} | {ceda.failures:,} ({ceda.failures / ceda.requests * 100:.2f}%) | {ceda.subsetted_data_gb / 1000:.2f} TB | {ceda.peak_concurrency} |

The DKRZ and CEDA request figures cover March–December. Their transfer columns
only contain the available site-level July–December values; March–June transfer
cannot be divided reliably between the sites.

## Monthly request outcomes

The green portion of each bar represents successful requests; failures are
shown in red. January and February are empty because monthly reporting had not
yet started.

### All sites

![Successful and failed requests for all sites]({chart_links[0]})

[Download this chart as SVG]({chart_links[0]}){{: download }}

### DKRZ

![Successful and failed requests for DKRZ]({chart_links[1]})

[Download this chart as SVG]({chart_links[1]}){{: download }}

### CEDA

![Successful and failed requests for CEDA]({chart_links[2]})

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

The chart shows the transfer volume recorded in the combined monthly exports.

![Subsetted data across all sites]({chart_links[3]})

[Download this chart as SVG]({chart_links[3]}){{: download }}

## Monthly peak concurrency

The chart uses the combined monthly export because the site split is not
available for the first part of the reporting period.

![Peak concurrency across all sites]({chart_links[4]})

[Download this chart as SVG]({chart_links[4]}){{: download }}

## Data and methodology

Combined monthly exports provide the overall request, failure, transfer, and
concurrency series. DKRZ and CEDA request outcomes for March–June were recovered
from the corresponding daily series in the full-year site exports; monthly site
exports are available from July onward.

The archived monthly files record 6.62 TB for July–December, while the existing
2021 dashboard page reports a rounded total of 11 TB for that period. This
summary retains the reproducible monthly values and therefore describes its
7.62 TB annual figure as recorded data rather than a complete transfer total.

The full-year overview reports 95,096 requests and 4,179 failures, compared
with 94,254 requests and 4,141 failures obtained by summing the monthly combined
exports. The site-level series also differ slightly from the combined series.
This summary consistently uses the monthly combined values for the overall
totals and charts, while showing the available site-series values separately.

[Download the monthly source data as CSV]({csv_link}){{: download }}
""", encoding="utf-8")


def write_markdown(path: Path, year: int, rows: list[dict[str, object]], csv_link: str, chart_links: list[str]) -> None:
    total, dkrz, ipsl = _totals(rows), _totals(rows, "dkrz"), _totals(rows, "ipsl")
    ceda = _totals(rows, "ceda") if "ceda" in rows[0] else None
    site_names = "DKRZ, IPSL, and CEDA" if ceda else "DKRZ and IPSL"
    ceda_table = ""
    ceda_chart = ""
    if ceda:
        ceda_table = f"\n| CEDA | {ceda.requests:,} | {ceda.requests - ceda.failures:,} | {ceda.failures:,} ({ceda.failures / ceda.requests * 100:.2f}%) | {ceda.subsetted_data_gb / 1000:.2f} TB | {ceda.peak_concurrency} |"
        ceda_chart = f"""### CEDA

![Successful and failed requests for CEDA]({chart_links[5]})

[Download this chart as SVG]({chart_links[5]}){{: download }}

"""
    if ceda:
        concurrency_explanation = f"""For each month, overall concurrency is the highest peak reported by
{site_names}. The site peaks are not added because they may have
occurred at different times."""
        methodology_text = """Request, failure, and subsetted-data totals are sums of the monthly DKRZ,
IPSL, and CEDA dashboard exports. Successful requests are calculated as total
requests minus failed requests. Peak concurrency is not additive: the combined
monthly series uses the higher site value, and the annual value is its maximum."""
    else:
        concurrency_explanation = """For each month, overall concurrency is the higher of the DKRZ and IPSL peak
values. The site peaks are not added because they may have occurred at different
times."""
        methodology_text = """Request, failure, and subsetted-data totals are sums of the monthly DKRZ and
IPSL dashboard exports. Successful requests are calculated as total requests
minus failed requests. Peak concurrency is not additive: the combined monthly
series uses the higher site value, and the annual value is its maximum."""
    source_note = ""
    if year == 2025:
        source_note = """
Source note: the raw March IPSL export reports 45 requests and 0.19 GB. The
existing 2025 dashboard page instead shows manual estimates of 25,000 requests
and 1,500 GB. Applying those estimates would make the annual totals 1,548,370
requests and 104.80 TB; no corresponding failure estimate is available.
"""
    elif year == 2024:
        source_note = """
Source note: the September IPSL monthly export is missing. Its 7,149 requests,
841 failures, and peak concurrency of 18 were recovered from the corresponding
daily series in the full-year IPSL export. The 140 GB transfer value is the
estimate recorded in the existing 2024 dashboard report. For May DKRZ, the
regular monthly export contains the complete request totals but only 5.60 GB of
transfer data; this summary uses the accumulated 3,328.50 GB value from its
partial export, consistent with the published quarterly report.
"""
    elif year == 2023:
        source_note = """
Source note: the January IPSL file spans both January and February, and the
October IPSL monthly export is missing. January and October request outcomes
and concurrency were therefore recovered from the daily series in the Q1 and
Q4 exports. The IPSL transfer exports are incomplete for those periods, so this
summary uses the monthly estimates recorded in the existing 2023 dashboard:
5,339 GB for January, 4,000 GB for February, 2,340 GB for March, and 500 GB for
October.
"""
    elif year == 2022:
        source_note = """
Source note: CEDA contributed during the service transition through April. Its
January export omits transfer volume, so the value is inferred from the
published Q1 CEDA total of 420 GB. The April IPSL monthly export is missing;
request outcomes and concurrency were recovered from the Q2 daily series, and
its transfer value completes the published Q2 IPSL total of 1,366 GB. The
September IPSL export contains only 49.88 GB, so this summary uses the value
implied by the published Q3 IPSL total of 2,340 GB. The unusually high peaks of
143 for CEDA in January and 97 for IPSL in October come directly from the raw
monthly exports.
"""
    path.write_text(f"""# ROOCS {year} annual summary

This report summarizes monthly usage of the ROOCS subsetting services operated
by {site_names} during {year}. Together, the services processed
**{total.requests:,} requests**, of which **{total.requests - total.failures:,} were successful**,
and delivered **{total.subsetted_data_gb / 1000:.2f} TB** of subsetted data.

| Scope | Requests | Successful | Failures | Subsetted data | Peak concurrency |
| --- | ---: | ---: | ---: | ---: | ---: |
| All sites | {total.requests:,} | {total.requests - total.failures:,} | {total.failures:,} ({total.failures / total.requests * 100:.2f}%) | {total.subsetted_data_gb / 1000:.2f} TB | {total.peak_concurrency} |
| DKRZ | {dkrz.requests:,} | {dkrz.requests - dkrz.failures:,} | {dkrz.failures:,} ({dkrz.failures / dkrz.requests * 100:.2f}%) | {dkrz.subsetted_data_gb / 1000:.2f} TB | {dkrz.peak_concurrency} |
| IPSL | {ipsl.requests:,} | {ipsl.requests - ipsl.failures:,} | {ipsl.failures:,} ({ipsl.failures / ipsl.requests * 100:.2f}%) | {ipsl.subsetted_data_gb / 1000:.2f} TB | {ipsl.peak_concurrency} |{ceda_table}

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

{ceda_chart}### Understanding the failures

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

The monthly values combine the data delivered by {site_names}.

![Subsetted data across all sites]({chart_links[3]})

[Download this chart as SVG]({chart_links[3]}){{: download }}

## Monthly peak concurrency

{concurrency_explanation}

![Peak concurrency across all sites]({chart_links[4]})

[Download this chart as SVG]({chart_links[4]}){{: download }}

## Data and methodology

{methodology_text}
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
    data_values = [float(row["subsetted_data_gb"]) for row in rows]
    concurrency_values = [float(row["peak_concurrency"]) for row in rows]
    if args.year == 2021:
        chart_paths = [
            args.output_dir / f"{stem}-requests-all.svg",
            args.output_dir / f"{stem}-requests-dkrz.svg",
            args.output_dir / f"{stem}-requests-ceda.svg",
            args.output_dir / f"{stem}-subsetted-data-all.svg",
            args.output_dir / f"{stem}-concurrency-all.svg",
        ]
        write_csv_2021(csv_path, rows)
        write_request_svg(chart_paths[0], args.year, rows, None)
        write_request_svg(chart_paths[1], args.year, rows, "dkrz")
        write_request_svg(chart_paths[2], args.year, rows, "ceda")
        write_series_svg(chart_paths[3], "All sites: monthly recorded subsetted data · 2021", f"Recorded total: {sum(data_values) / 1000:.2f} TB", data_values, lambda v: f"{v / 1000:.1f} TB", "#0072B2")
        write_series_svg(chart_paths[4], "All sites: monthly peak concurrency · 2021", "Combined monthly dashboard values · reporting began in March", concurrency_values, lambda v: f"{v:.0f}", "#6F4EAA", line=True)
    else:
        chart_paths = [
            args.output_dir / f"{stem}-requests-all.svg",
            args.output_dir / f"{stem}-requests-dkrz.svg",
            args.output_dir / f"{stem}-requests-ipsl.svg",
            args.output_dir / f"{stem}-subsetted-data-all.svg",
            args.output_dir / f"{stem}-concurrency-all.svg",
        ]
        if "ceda" in rows[0]:
            chart_paths.append(args.output_dir / f"{stem}-requests-ceda.svg")
        write_csv(csv_path, rows)
        write_request_svg(chart_paths[0], args.year, rows, None)
        write_request_svg(chart_paths[1], args.year, rows, "dkrz")
        write_request_svg(chart_paths[2], args.year, rows, "ipsl")
        if "ceda" in rows[0]:
            write_request_svg(chart_paths[5], args.year, rows, "ceda")
        write_series_svg(chart_paths[3], f"All sites: monthly subsetted data · {args.year}", f"Annual total: {sum(data_values) / 1000:.2f} TB", data_values, lambda v: f"{v / 1000:.0f} TB", "#0072B2")
        concurrency_subtitle = "Highest of the DKRZ, IPSL, and CEDA peak values in each month" if "ceda" in rows[0] else "Higher of the DKRZ and IPSL peak values in each month"
        write_series_svg(chart_paths[4], f"All sites: monthly peak concurrency · {args.year}", concurrency_subtitle, concurrency_values, lambda v: f"{v:.0f}", "#6F4EAA", line=True)
    csv_link = Path(os.path.relpath(csv_path, markdown_path.parent)).as_posix()
    chart_links = [Path(os.path.relpath(item, markdown_path.parent)).as_posix() for item in chart_paths]
    if args.year == 2021:
        write_markdown_2021(markdown_path, rows, csv_link, chart_links)
    else:
        write_markdown(markdown_path, args.year, rows, csv_link, chart_links)
    print(markdown_path, csv_path, *chart_paths, sep="\n")


if __name__ == "__main__":
    main()
