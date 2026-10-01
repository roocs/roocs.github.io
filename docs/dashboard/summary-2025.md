# ROOCS 2025 annual summary

This report summarizes monthly usage of the ROOCS subsetting services operated
by DKRZ and IPSL during 2025. Together, the services processed
**1,523,415 requests**, of which **1,414,708 were successful**,
and delivered **103.30 TB** of subsetted data.

| Scope | Requests | Successful | Failures | Subsetted data | Peak concurrency |
| --- | ---: | ---: | ---: | ---: | ---: |
| All sites | 1,523,415 | 1,414,708 | 108,707 (7.14%) | 103.30 TB | 45 |
| DKRZ | 1,245,557 | 1,152,819 | 92,738 (7.45%) | 87.99 TB | 45 |
| IPSL | 277,858 | 261,889 | 15,969 (5.75%) | 15.31 TB | 34 |

## Monthly request outcomes

The green portion of each bar represents successful requests; failures are
shown in red.

### All sites

![Successful and failed requests for all sites](../downloads/stats/roocs-2025-requests-all.svg)

[Download this chart as SVG](../downloads/stats/roocs-2025-requests-all.svg){: download }

### DKRZ

![Successful and failed requests for DKRZ](../downloads/stats/roocs-2025-requests-dkrz.svg)

[Download this chart as SVG](../downloads/stats/roocs-2025-requests-dkrz.svg){: download }

### IPSL

![Successful and failed requests for IPSL](../downloads/stats/roocs-2025-requests-ipsl.svg)

[Download this chart as SVG](../downloads/stats/roocs-2025-requests-ipsl.svg){: download }

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

![Subsetted data across all sites](../downloads/stats/roocs-2025-subsetted-data-all.svg)

[Download this chart as SVG](../downloads/stats/roocs-2025-subsetted-data-all.svg){: download }

## Monthly peak concurrency

For each month, overall concurrency is the higher of the DKRZ and IPSL peak
values. The site peaks are not added because they may have occurred at different
times.

![Peak concurrency across all sites](../downloads/stats/roocs-2025-concurrency-all.svg)

[Download this chart as SVG](../downloads/stats/roocs-2025-concurrency-all.svg){: download }

## Data and methodology

Request, failure, and subsetted-data totals are sums of the monthly DKRZ and
IPSL dashboard exports. Successful requests are calculated as total requests
minus failed requests. Peak concurrency is not additive: the combined monthly
series uses the higher site value, and the annual value is its maximum.

Source note: the raw March IPSL export reports 45 requests and 0.19 GB. The
existing 2025 dashboard page instead shows manual estimates of 25,000 requests
and 1,500 GB. Applying those estimates would make the annual totals 1,548,370
requests and 104.80 TB; no corresponding failure estimate is available.


[Download the monthly source data as CSV](../downloads/stats/roocs-2025-monthly.csv){: download }
