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

- `product_id`: RecallDB surrogate key.
- `recall_id`: Foreign key into `recalls.csv`.
- `source_agency`: Agency of the parent recall.
- `external_id`: Agency-native identifier of the parent recall.
- `name`: Agency-published product, SKU, lot or vehicle name.
- `brand`: Product brand when the agency publishes it separately. NHTSA: the vehicle or equipment make.
- `model_number`: Agency-published model, SKU or equivalent identifier. NHTSA: the vehicle or equipment model.
- `upc`: Checksum-valid UPC-A extracted from agency text.
- `lot_codes`: Agency-published lot, code, serial or batch text (NHTSA: the recalled component id).
- `category`: Normalized category (`consumer_product`, `vehicle`, `food`, `drug`, `device`, `boat`, ...).
- `model_year`: Agency-published model year (NHTSA vehicles and equipment, USCG boats).

### NHTSA rows: make, model and model year

NHTSA's recall flat file publishes make, model and model year as separate columns, and
RecallDB copies them unchanged:

| RecallDB column | NHTSA flat-file field | Notes |
| :-- | :-- | :-- |
| `brand` | `MAKETXT` (vehicle/equipment make) | Not the recalling manufacturer, which is `recalling_firm_*` in `recalls.csv` (`MFGNAME`). |
| `model_number` | `MODELTXT` (vehicle/equipment model) | |
| `model_year` | `YEARTXT` | NHTSA's `9999` (unknown or not applicable) becomes empty. |
| `name` | `MAKETXT MODELTXT YEARTXT` | Joined as published, so an unknown year reads `9999`. |

- **Upfitted vehicles** (wheelchair-accessible vans, ambulances, truck bodies): NHTSA often
  names the upfitter as the make and puts the base vehicle in the model, e.g. `BRAUN` /
  `CHEVROLET TRAVERSE`. RecallDB keeps both as published and does not split the base
  vehicle's make out of the model text, because that text cannot be split reliably
  (`DODGE` / `RAM 1500` is a make and a model).
- **Vehicle or equipment**: the third character of an NHTSA `external_id` (campaign number)
  is NHTSA's recall type: `V` vehicle, `E` equipment, `T` tire, `C` child seat (`I` and `X`
  are rare other codes). For example, `26V434000` is a vehicle recall and `26E043000`
  (KENWAY lights) is an equipment recall. All NHTSA product rows have `category` `vehicle`,
  so use the campaign number to tell them apart. Equipment, tire and child-seat rows often
  have no model year.
- **Coverage (2026.09 edition)**: make and model are filled on every NHTSA row. Model year is
  filled on 99.7% of vehicle-campaign rows; the empty ones are NHTSA's own `9999`. Every
  monthly build checks these shares and stops if they drop (make or model below 99%, model
  year below 97%), so an edition with broken make/model/year columns cannot ship.

Example: find a vehicle's recalls by make, model and year, with `recalls.csv` and
`recalled_products.csv` loaded as tables (for example in DuckDB or SQLite):

```sql
SELECT p.external_id, p.brand, p.model_number, p.model_year, r.recalling_firm_display
FROM recalled_products p
JOIN recalls r ON r.recall_id = p.recall_id
WHERE p.source_agency = 'NHTSA'
  AND substr(p.external_id, 3, 1) = 'V'
  AND p.brand = 'TOYOTA' AND p.model_number = 'TUNDRA' AND p.model_year = 2026;
```

## firms.csv

Canonical firm names and observed aliases.

## hazards.csv

Controlled hazard taxonomy and full-release recall counts.
