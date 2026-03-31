import argparse
import base64
import csv
import gzip
import json
import re
import struct
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE = REPO_ROOT / "docs" / "downloads" / "dashboard"
DEFAULT_START = "2025-04"
DEFAULT_END = "2026-02"
DEFAULT_SITE = "dkrz"

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


def _extract_docs_json_strings(text: str) -> list[str]:
    soup = BeautifulSoup(text, "lxml")
    docs_json_strings = []
    for script in soup.find_all("script"):
        script_text = script.get_text() or ""
        for match in re.finditer(r"const docs_json = '(.*?)';", script_text, re.S):
            docs_json_strings.append(match.group(1))
    return docs_json_strings


def _iter_roots(text: str):
    for docs_json in _extract_docs_json_strings(text):
        parsed = json.loads(docs_json)
        for _, doc in parsed.items():
            for root in doc.get("roots", []):
                yield root


def _entries_to_dict(entries: list) -> dict:
    return {key: value for key, value in entries}


def _decode_ndarray(array_meta: dict, shape: list[int], dtype: str, order: str) -> list[int | float]:
    if len(shape) != 1:
        raise RuntimeError(f"Unsupported ndarray shape: {shape}")

    if dtype not in NUMERIC_DTYPES:
        raise RuntimeError(f"Unsupported ndarray dtype: {dtype}")

    fmt_char, item_size = NUMERIC_DTYPES[dtype]
    n = int(shape[0])

    raw = base64.b64decode(array_meta["data"])
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    expected_size = n * item_size
    payload = raw[:expected_size]
    if len(payload) != expected_size:
        raise RuntimeError(
            f"Unexpected ndarray payload size for dtype={dtype}: "
            f"expected {expected_size}, got {len(payload)}"
        )

    byte_order = "<" if order == "little" else ">"
    return list(struct.unpack(f"{byte_order}{fmt_char * n}", payload))


def _extract_overview_values(text: str) -> dict[str, str | int | float]:
    for root in _iter_roots(text):
        if root.get("name") != "DataTable":
            continue
        source = root.get("attributes", {}).get("source", {})
        data = source.get("attributes", {}).get("data", {})
        entries = data.get("entries", [])
        data_dict = _entries_to_dict(entries)
        properties = data_dict.get("property")
        values = data_dict.get("value")
        if not isinstance(properties, list) or not isinstance(values, list):
            continue
        if "Total Requests" not in properties:
            continue
        return dict(zip(properties, values))

    raise RuntimeError("Could not find overview DataTable values")


def _extract_download_counts(text: str) -> list[int | float]:
    for root in _iter_roots(text):
        if root.get("name") != "Figure":
            continue

        attrs = root.get("attributes", {})
        title = attrs.get("title", {}).get("attributes", {}).get("text", "")
        if title != "Downloads per day":
            continue

        for renderer in attrs.get("renderers", []):
            renderer_attrs = renderer.get("attributes", {})
            source = renderer_attrs.get("data_source", {})
            source_attrs = source.get("attributes", {})
            data = source_attrs.get("data", {})
            entries = data.get("entries", [])
            data_dict = _entries_to_dict(entries)
            request_type = data_dict.get("request_type")
            if not isinstance(request_type, dict):
                continue

            arr = request_type.get("array", {})
            dtype = request_type.get("dtype")
            shape = request_type.get("shape")
            order = request_type.get("order", "little")
            if arr.get("type") != "bytes" or not dtype or not shape:
                continue

            return _decode_ndarray(arr, shape, dtype, order)

    raise RuntimeError("Could not find request_type download series")


def build_months(start: str, end: str) -> list[str]:
    try:
        current = datetime.strptime(start, "%Y-%m")
        end_dt = datetime.strptime(end, "%Y-%m")
    except ValueError as exc:
        raise ValueError("Use YYYY-MM format for --start and --end") from exc

    if current > end_dt:
        raise ValueError("--start must be earlier than or equal to --end")

    months: list[str] = []
    while current <= end_dt:
        months.append(current.strftime("%Y-%m"))
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        current = current.replace(year=year, month=month)

    return months


def parse_month(ym: str, site: str) -> dict[str, int | float | str]:
    year = ym[:4]
    fpath = BASE / year / f"dashboard-{ym}-{site}.html"
    if not fpath.exists():
        raise FileNotFoundError(f"Missing dashboard file: {fpath}")
    text = fpath.read_text(encoding="utf-8")

    overview = _extract_overview_values(text)
    requests = int(overview["Total Requests"])

    transfer_str = str(overview["Total data transfer"])
    transfer_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", transfer_str)
    if not transfer_match:
        raise RuntimeError(f"Could not parse total data transfer in {fpath}")
    total_transfer_gb = float(transfer_match.group(1))

    downloads = int(sum(_extract_download_counts(text)))
    date_ts = f"{ym}-01T00:00:00"

    return {
        "date": date_ts,
        "requests": requests,
        "downloads": downloads,
        "downloads_size": f"{total_transfer_gb} GB",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract monthly request/download stats from dashboard HTML files."
    )
    parser.add_argument("--start", default=DEFAULT_START, help="Start month (YYYY-MM)")
    parser.add_argument("--end", default=DEFAULT_END, help="End month (YYYY-MM)")
    parser.add_argument("--site", default=DEFAULT_SITE, help="Site suffix in file name (e.g. dkrz, ipsl, all)")
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: docs/downloads/dashboard/<site>-monthly-<start>_to_<end>.csv)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the output CSV path",
    )
    args = parser.parse_args()

    months = build_months(args.start, args.end)
    rows = [parse_month(ym, args.site) for ym in months]

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = BASE / f"{args.site}-monthly-{args.start}_to_{args.end}.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "requests", "downloads", "downloads_size"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(out_path.as_posix())
    if not args.quiet:
        for row in rows:
            print(row)


if __name__ == "__main__":
    main()
