# Service status

Open a Rook service's status report to see its latest health checks, including
process activity, server resources, output storage, and configured filesystem
checks.

| Service | Status report |
| --- | --- |
| DKRZ — CDS production (rook8) | [View CDS production status](http://rook8.cloud.dkrz.de/status) |
| DKRZ — rook.dkrz.de | [View service status](http://rook.dkrz.de/status) |

Each report shows an overall state and individual checks with **green** (OK),
**yellow** (warning), or **red** (failure) indicators. Read the check messages
for details: a warning does not necessarily mean the service is unavailable.

Reports are cached by nginx. Check the **Measured at** timestamp in the report
to see when the checks ran; refreshing the page may return the same cached
result.

For historical request counts, outcomes, and data volumes, see the
[usage Dashboard](dashboard/summary-all-years.md).
