# ROOCS usage by year

This overview shows the total number of requests processed and the recorded
volume of subsetted data for each reporting year. Detailed request outcomes,
site breakdowns, and monthly charts are available from the linked annual pages.

For the latest cached health checks, see [Service status](../status.md).

| Year | Coverage | Requests | Subsetted data |
| --- | --- | ---: | ---: |
| [2021](summary-2021.md) | March–December (recorded) | 94,254 | 7.62 TB |
| [2022](summary-2022.md) | January–December | 357,821 | 27.16 TB |
| [2023](summary-2023.md) | January–December | 738,432 | 81.97 TB |
| [2024](summary-2024.md) | January–December | 1,536,287 | 55.32 TB |
| [2025](summary-2025.md) | January–December | 1,523,415 | 103.30 TB |
| [2026](summary-2026.md) | January–September (year to date) | 1,743,361 | 89.45 TB |

ROOCS is designed to subset large datasets before delivery. Transferred volume
is therefore not a metric to maximize: for equivalent scientific requests,
less data transferred generally means more effective subsetting and lower
network and storage costs.

## Requests

![ROOCS requests by year](../downloads/stats/roocs-all-years-requests.svg)

[Download this chart as SVG](../downloads/stats/roocs-all-years-requests.svg){: download }

## Subsetted data

![ROOCS subsetted data by year](../downloads/stats/roocs-all-years-subsetted-data.svg)

[Download this chart as SVG](../downloads/stats/roocs-all-years-subsetted-data.svg){: download }

## Downloads

[Download monthly DKRZ usage statistics (CSV)](../downloads/stats/dkrz-monthly.csv){: download }

[Download daily DKRZ usage statistics (CSV)](../downloads/stats/dkrz-daily.csv){: download }

These continuously updated files contain one row per month or calendar day for
**DKRZ only**, currently covering **2025-01 through 2026-09**. Both start
in January 2025. Each frequency has a single CSV spanning all reporting years;
the download addresses stay the same as new months are added. IPSL and CEDA are excluded;
an IPSL export may be added separately in future.

Both CSVs use semicolons and the following columns:

| Column | Meaning |
| --- | --- |
| `date` | First day of the reporting month, or the reporting day (UTC) in the daily file, in `YYYY-MM-DD` format. |
| `country` | `GB`, the agreed attribution for CDS gateway traffic; this does not identify the countries of individual CDS users. |
| `requests` | WPS Execute processing requests, including successful and failed jobs. |
| `downloads` | Recorded result-file fetches; repeated fetches are counted separately. |
| `downloads_size` | Recorded transfer volume in MB, using the previous exports' conversion of 1 GB = 1024 MB. Source totals are rounded. |
| `visits` | Distinct users during the reporting period; empty because the dashboards do not provide this information. |

Missing measurements are empty, rather than zero. Some source exports omit
individual days; those dates remain in the daily file with the missing metrics
left empty. Monthly totals sum the available records and may be incomplete.
Daily transfer values come from the daily chart; monthly transfer totals are
rounded independently, so small rounding differences are expected when summing
daily sizes. The latest year contains only the available reporting months,
without extrapolation. Earlier years remain available in the annual reports.

[Download source and coverage notes](../downloads/stats/dkrz-usage-notes.txt){: download }

## Comparability

The 2021 series starts in March, and its transfer total reflects the values
recorded in the archived monthly exports; those exports are known to be
incomplete. The 2026 figure currently covers January through
September and will grow as later reports are added.
See the individual annual pages for source-specific notes.
