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
- `raw_payload_bytes`: Size of archived raw payload. For the NHTSA ODI bulk ZIPs (since edition 2026.10), which are not archived, the size of the ZIP as downloaded.
- `raw_payload_sha256`: SHA-256 hash of archived raw payload. For the NHTSA ODI bulk ZIPs, the SHA-256 of the ZIP as downloaded.

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

## NHTSA defect investigations, manufacturer communications and complaint counts (since edition 2026.10)

Seven tables built from NHTSA's Office of Defects Investigation (ODI) bulk files, the same
official public-domain source tree as the recall flat files. They are in the full snapshot; the
Vehicle Cut carries the investigations and the complaint counts. The free sample (`samples/`) has
rows of all seven, taken from NHTSA's files of 2026-10-04 around the NHTSA vehicles in the sample's
`recalled_products.csv`. In the sample, `nhtsa_investigation_recalls.csv` `recall_id` points into the
full release (the sample's `recalls.csv` is an older extract), so join on `campaign_number` =
`external_id` there.
All three sources use NHTSA's make, model and model-year vocabulary, so they join to NHTSA rows
of `recalled_products.csv` on `brand` = `make`, `model_number` = `model`, `model_year` =
`model_year`. A match means the same vehicle, not that a complaint or bulletin concerns that
recall: only investigations link to recalls directly, by campaign number. Every row carries the
`source_id` of the NHTSA file it was read from. Model year `9999` (unknown) becomes empty. A full
17-character VIN in NHTSA's text that identifies one specific vehicle (an owner letter, an incident
report, a list of affected vehicles) is masked as `[VIN]`; production breakpoints and ranges
("vehicles built before VIN ...", "VIN start: ... VIN end: ...") stay as published.

### nhtsa_investigations.csv

One row per defect investigation.

- `action_number`: NHTSA action number, e.g. `PE24031` (PE preliminary evaluation, EA engineering analysis, DP defect petition, RQ recall query, AQ audit query, ...).
- `opened_date`, `closed_date`: ISO dates; `closed_date` is empty while the investigation is open.
- `subject`: NHTSA's summary description.
- `summary`: NHTSA's summary detail.
- `source_id`: Foreign key into `data_sources.csv`.

### nhtsa_investigation_vehicles.csv

Vehicles and equipment named in an investigation: `action_number`, `make`, `model`,
`model_year`, `component`, `manufacturer_name` (one investigation can name several
manufacturers), `source_id`.

### nhtsa_investigation_recalls.csv

Recall campaigns an investigation led to.

- `action_number`: The investigation.
- `campaign_number_published`: The campaign number exactly as NHTSA prints it.
- `campaign_number`: The matching NHTSA recall's `external_id` in `recalls.csv`. NHTSA sometimes prints a 6-character number (`14V668`); it matches when the recall exists with NHTSA's `000` suffix (`14V668000`). Empty when no recall matches.
- `recall_id`: Foreign key into `recalls.csv`; empty when unmatched.
- `match_method`: `exact`, `padded_000`, or empty.
- `source_id`: Foreign key into `data_sources.csv`.

### nhtsa_mfr_communications.csv

One row per manufacturer communication filed with NHTSA: technical service bulletins, service
campaigns, warranty extensions, over-the-air updates, emissions and other communications.

- `nhtsa_id`: NHTSA ID number.
- `document_id`: The manufacturer's identifier, e.g. its bulletin number.
- `communication_type`: `Service Bulletin/Repair Instructions`, `Service Campaign`, `Warranty Program/Extension`, `Over The Air`, `Emissions` or `Other`.
- `communication_date`: Date the manufacturer issued it. `date_added`: date NHTSA added it.
- `replacement_bulletin_number`: Replacement bulletin number (deprecated by NHTSA).
- `mfr_campaign_id`: The manufacturer's internal campaign ID or software version, when related.
- `mfr_component_system`, `mfr_component_subsystem`: The manufacturer's component.
- `summary`: NHTSA's summary of the communication.
- `source_id`: Foreign key into `data_sources.csv`.

### nhtsa_mfr_communication_vehicles.csv

`nhtsa_id`, `make`, `model`, `model_year`, `source_id`: one row per vehicle a communication applies to.

### nhtsa_mfr_communication_components.csv

`nhtsa_id`, `component`, `source_id`: NHTSA components a communication names, as published.
Component names can contain commas (`FUEL SYSTEM, GASOLINE`), so each row holds one whole name.

### nhtsa_complaint_counts.csv

Consumer complaint counts. RecallDB does not include complaint rows: NHTSA's complaint records
contain consumers' own words and details that can identify them, so only counts are published.

- `make`, `model`, `model_year`, `component`: As NHTSA publishes them.
- `product_type`: `V` vehicle, `T` tires, `E` equipment, `C` child restraint.
- `complaints`: Number of complaints (distinct NHTSA ODI numbers). A complaint naming two components counts under each.
- `complaints_crash`, `complaints_fire`: Of those, how many report a crash or a fire.
- `injured`, `deaths`: Persons injured and deaths reported, summed over those complaints.
- `first_received_date`, `last_received_date`: First and latest date NHTSA received one of them (full snapshot only; the Vehicle Cut omits these two columns for size).
- `source_id`: Foreign key into `data_sources.csv`.

Example: complaints, bulletins and investigations next to the recalls of one vehicle, with the
CSVs loaded as tables (for example in DuckDB or SQLite):

```sql
SELECT DISTINCT p.external_id AS recall,
       (SELECT SUM(complaints) FROM nhtsa_complaint_counts c
         WHERE c.make = p.brand AND c.model = p.model_number AND c.model_year = p.model_year) AS complaints,
       (SELECT COUNT(DISTINCT v.nhtsa_id) FROM nhtsa_mfr_communication_vehicles v
         WHERE v.make = p.brand AND v.model = p.model_number AND v.model_year = p.model_year) AS bulletins,
       (SELECT COUNT(DISTINCT i.action_number) FROM nhtsa_investigation_vehicles i
         WHERE i.make = p.brand AND i.model = p.model_number AND i.model_year = p.model_year) AS investigations
FROM recalled_products p
WHERE p.source_agency = 'NHTSA' AND p.brand = 'HONDA' AND p.model_number = 'ACCORD' AND p.model_year = 2018;
```

## Fault & Recall bundle: bulletin index (bundle only)

Ships only in the $179 Fault & Recall bundle, as one archive (`csv/`, `parquet/` and
`fault-recall-bulletins.sqlite`). It holds the NHTSA manufacturer communications whose summary
cites a diagnostic trouble code. The rows come from the tables above, filtered to those bulletins.
Codes are read from NHTSA's summary text only, not the bulletin documents. The archive README
gives the rule, a dated precision check, and SQL that joins it to MechanicDB OEM Complete.

| Table | Columns |
| :-- | :-- |
| `bulletins` | `nhtsa_id` (PK), `document_id`, `communication_type`, `communication_date`, `date_added`, `mfr_campaign_id`, `mfr_component_system`, `mfr_component_subsystem`, `summary` (single-vehicle VINs masked as `[VIN]`), `source_id` |
| `bulletin_vehicles` | `nhtsa_id`, `make`, `model`, `model_year` (NHTSA's 9999 is NULL) |
| `bulletin_components` | `nhtsa_id`, `component` |
| `bulletin_codes` | `nhtsa_id`, `dtc_code` (5 characters, upper case), `code_scope` (`sae` or `manufacturer`, by SAE J2012 code range), `cued` (1 when a cue word such as DTC, CODE or MIL precedes the code, or it is part of a code list), `first_position` (offset of its first mention in the summary). PK (`nhtsa_id`, `dtc_code`) |
| `data_sources` | `source_id`, `source_agency`, `endpoint_url`, `retrieved_at`, `raw_payload_bytes`, `raw_payload_sha256`: the NHTSA bulk file each bulletin came from |

A manufacturer code joined on make is the same code string, not a verified meaning for that
model year.
