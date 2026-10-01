# ROOCS 2024 annual summary

This report summarizes monthly usage of the ROOCS subsetting services operated
by DKRZ and IPSL during 2024. Together, the services processed
**1,536,287 requests**, of which **1,463,457 were successful**,
and delivered **55.32 TB** of subsetted data.

| Scope | Requests | Successful | Failures | Subsetted data | Peak concurrency |
| --- | ---: | ---: | ---: | ---: | ---: |
| All sites | 1,536,287 | 1,463,457 | 72,830 (4.74%) | 55.32 TB | 46 |
| DKRZ | 1,293,214 | 1,228,930 | 64,284 (4.97%) | 45.35 TB | 40 |
| IPSL | 243,073 | 234,527 | 8,546 (3.52%) | 9.97 TB | 46 |

## Monthly request outcomes

The green portion of each bar represents successful requests; failures are
shown in red.

### All sites

![Successful and failed requests for all sites](../downloads/stats/roocs-2024-requests-all.svg)

[Download this chart as SVG](../downloads/stats/roocs-2024-requests-all.svg){: download }

### DKRZ

![Successful and failed requests for DKRZ](../downloads/stats/roocs-2024-requests-dkrz.svg)

[Download this chart as SVG](../downloads/stats/roocs-2024-requests-dkrz.svg){: download }

### IPSL

![Successful and failed requests for IPSL](../downloads/stats/roocs-2024-requests-ipsl.svg)

[Download this chart as SVG](../downloads/stats/roocs-2024-requests-ipsl.svg){: download }

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

![Subsetted data across all sites](../downloads/stats/roocs-2024-subsetted-data-all.svg)

[Download this chart as SVG](../downloads/stats/roocs-2024-subsetted-data-all.svg){: download }

## Monthly peak concurrency

For each month, overall concurrency is the higher of the DKRZ and IPSL peak
values. The site peaks are not added because they may have occurred at different
times.

![Peak concurrency across all sites](../downloads/stats/roocs-2024-concurrency-all.svg)

[Download this chart as SVG](../downloads/stats/roocs-2024-concurrency-all.svg){: download }

## Data and methodology

Request, failure, and subsetted-data totals are sums of the monthly DKRZ and
IPSL dashboard exports. Successful requests are calculated as total requests
minus failed requests. Peak concurrency is not additive: the combined monthly
series uses the higher site value, and the annual value is its maximum.

Source note: the September IPSL monthly export is missing. Its 7,149 requests,
841 failures, and peak concurrency of 18 were recovered from the corresponding
daily series in the full-year IPSL export. The 140 GB transfer value is the
estimate recorded in the existing 2024 dashboard report. For May DKRZ, the
regular monthly export contains the complete request totals but only 5.60 GB of
transfer data; this summary uses the accumulated 3,328.50 GB value from its
partial export, consistent with the published quarterly report.


[Download the monthly source data as CSV](../downloads/stats/roocs-2024-monthly.csv){: download }
