<div align="center">

# RecallDB - U.S. Product Recall Database

**127,783 official recalls - 292,790 recalled products - CPSC, FDA, FSIS, NHTSA, USCG - 100% source-linked**

[![Sample CSV](https://img.shields.io/badge/Public%20sample-CSV-brightgreen.svg)](samples/recalls.csv)
[![Full dataset](https://img.shields.io/badge/Full%20dataset-$49%20snapshot-14b8a6.svg)](https://recalldb-public.pages.dev/#pricing)
[![Contact](https://img.shields.io/badge/Contact-recalldb.shorthand343%40aleeas.com-blue.svg)](mailto:recalldb.shorthand343@aleeas.com)
[![Cloudflare Pages](https://img.shields.io/badge/Landing%20page-Cloudflare%20Pages-14b8a6.svg)](https://recalldb-public.pages.dev/)
[![License](https://img.shields.io/badge/Sample%20license-CC0-blue.svg)](LICENSE)

**[View the landing page](https://recalldb-public.pages.dev/)**

</div>

RecallDB is a normalized, provenance-tracked dataset of official U.S. federal product recalls. It joins five official source families into one CSV/SQLite model: CPSC consumer products, NHTSA vehicles, FDA/openFDA plus FDA Safety Alerts enrichment, USDA FSIS food safety recalls, and USCG boating recalls.

## Public sample vs paid full dataset

This public repository contains only the sample files, documentation, SEO pages, and Kaggle sample metadata. The full CSV + SQLite dataset is not published in this repo, on Cloudflare Pages, or through a free Kaggle download.

| Table | Paid full dataset | Public sample |
| :--- | ---: | ---: |
| Recalls | 127,783 | 200 |
| Recalled products | 292,790 | 428 |
| Source pulls | 521 | 11 |
| Firms | 20,886 | 147 |
| Hazard taxonomy | 11 | 11 |

## Full dataset access

| Tier | Includes | Price |
| :--- | :--- | ---: |
| Dataset Snapshot | Current full CSV + SQLite export with provenance ledger and source links. Stripe checkout routes to the verified delivery worker. | [$49 one-time](https://buy.stripe.com/aFacN69Jm2MK8rN5Uk38408) |
| Enterprise Custom Request | Snapshot plus custom joins, refresh cadence, retail matching, enrichment, or schema work. | $99+ |

Buy the $49 snapshot through **[Stripe checkout](https://buy.stripe.com/aFacN69Jm2MK8rN5Uk38408)**. For $99+ enterprise custom work, use the landing page request form or email **[recalldb.shorthand343@aleeas.com](mailto:recalldb.shorthand343@aleeas.com)**.

## Public sample files

- [`samples/recalls.csv`](samples/recalls.csv) - balanced sample of recalls from all five agencies.
- [`samples/recalled_products.csv`](samples/recalled_products.csv) - linked products, vehicles, lots and categories.
- [`samples/data_sources.csv`](samples/data_sources.csv) - endpoint URLs, retrieval timestamps and raw payload hashes.
- [`samples/firms.csv`](samples/firms.csv) - canonical firm names observed in the sample.
- [`samples/hazards.csv`](samples/hazards.csv) - hazard taxonomy with recall counts.

## Provenance

Every recall has:

- `source_agency`
- `external_id`
- `source_url`
- `source_id`

`source_id` joins into `data_sources.csv`, which exposes `endpoint_url`, `retrieved_at`, `raw_payload_bytes`, and `raw_payload_sha256`. The paid SQLite release also stores the archived raw payload for replay and audit.

## Source coverage

| Agency | Full rows | Domain |
| :--- | ---: | :--- |
| CPSC | 8,179 | Consumer product recalls |
| FDA | 86,476 | Food, drugs, devices, cosmetics, biologics, animal/veterinary alerts |
| FSIS | 1,222 | Meat, poultry and egg product recalls |
| NHTSA | 30,143 | Vehicle and equipment recalls |
| USCG | 1,763 | Recreational boating recalls |

EPA is intentionally not included in v1 because no stable official recall-specific structured feed was identified.

## Quick start

```python
import csv

with open("samples/recalls.csv", encoding="utf-8", newline="") as f:
    recalls = list(csv.DictReader(f))

print(len(recalls), recalls[0]["source_agency"], recalls[0]["title"])
```

See [`examples/load_sample.py`](examples/load_sample.py) and [`SAMPLE_PREVIEW.md`](SAMPLE_PREVIEW.md).

## License

The public sample is released under CC0-1.0. Source records originate from U.S. federal government publications. Attribution is appreciated and useful for auditability; see [`SOURCES.md`](SOURCES.md).

The full dataset is not included in this public repository. Snapshot and enterprise deliveries are paid/private and may carry separate commercial terms.
