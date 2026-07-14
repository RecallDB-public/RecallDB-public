# RecallDB Data Dictionary

## recalls.csv

- `recall_id`: RecallDB surrogate key.
- `source_agency`: CPSC, FDA, FSIS, NHTSA or USCG.
- `external_id`: Agency-native recall identifier or namespaced FDA alert ID.
- `source_id`: Foreign key into `data_sources.csv`.
- `title`: Agency-published recall title or product description.
- `description`: Agency-published reason, summary or hazard text.
- `recalling_firm_canonical`: Normalized firm key.
- `recalling_firm_display`: Display spelling preserved from source.
- `recall_date`: ISO date.
- `severity`: Agency classification where available.
- `remedy`: Agency-published remedy where available.
- `units_affected`: Agency-published affected units where available.
- `distribution_pattern`: Geography or distribution pattern.
- `hazard_keys`: Pipe-delimited normalized hazard keys.
- `raw_hazard_texts`: Pipe-delimited source hazard phrases.
- `source_url`: Record-level agency URL or API lookup URL.
- `source_endpoint_url`: Source pull endpoint.
- `retrieved_at`: Archive timestamp.

## data_sources.csv

- `source_id`: Source-pull key joined from `recalls.csv`.
- `source_agency`: Source agency.
- `endpoint_url`: Exact API/download/page URL.
- `retrieved_at`: Archive timestamp.
- `raw_payload_bytes`: Size of archived raw payload.
- `raw_payload_sha256`: SHA-256 hash of archived raw payload.

## recalled_products.csv

Product, vehicle, lot, UPC, model, category and model-year rows linked to `recalls.csv`.

## firms.csv

Canonical firm names and observed aliases.

## hazards.csv

Controlled hazard taxonomy and full-release recall counts.
