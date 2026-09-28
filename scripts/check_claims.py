#!/usr/bin/env python3
"""check_claims.py -- every hand-written RecallDB count must equal claims.json.

claims.json (repo root, served at /claims.json) records the edition buyers actually
receive: the counts of the full snapshot ZIP on the private release (recalls, recalled
products, recalls per agency with the FDA Safety Alerts folded into FDA, recall_count per
hazard key from the ZIP's csv/hazards.csv, firms.csv rows, data_sources.csv rows, ZIP
size). The private monthly refresh writes the same schema as recalldb-claims-latest.json.

Nothing on the site reads claims.json at runtime; this script is what keeps the copy in
step with it. It checks, and with --fix rewrites, the hand-written surfaces:

  index.html                   data-agencies / data-hazards (unformatted JSON), hero lede,
                               hero stats, pricing list, "the N MB full snapshot"
  README.md                    headline, intro, sample-vs-full table, source-coverage table
  llms.txt                     totals and the per-source counts
  kaggle/dataset-metadata.json description (headline, both tables)
  kaggle/starter_notebook.ipynb  "N recalls . M products" (2 cells)
  samples/hazards.csv          recall_count column (the input of the hazard pages)
  hazards/chemical_toxic.html  CTA band "All N official recalls" (generate_seo_pages.py
                               copies it into all 16 hazard and agency pages)

and reports (never rewrites) the generated pages that derive from them: the 11 hazard
pages' counts and "of the N classified hazard rows", the CTA band on all 16 pages, and the
data-* attributes of the locale home pages. /stats/ is generated from the full SQLite by
scripts/generate_stats.py; a snapshot mismatch there is printed as a note, not an error.

Usage (from anywhere):
  python scripts/check_claims.py                        # exit 1 with a list of mismatches
  python scripts/check_claims.py --fix                  # rewrite the surfaces from claims.json
  python scripts/check_claims.py --fix --claims PATH    # adopt PATH (e.g. the private CI's
                                                        # recalldb-claims-latest.json): rewrites
                                                        # claims.json too, then every surface
After --fix, rebuild what derives from the surfaces (the script prints these steps):
  python scripts/generate_seo_pages.py
  python scripts/generate_seo_pages.py --sitemap-only
  python scripts/i18n_common.py build && python scripts/i18n_common.py check
  python ../scripts/sitemap_keep_lastmod.py
  python scripts/check_claims.py                        # must print OK

Formats are kept as they are today: thousands separators in prose, unformatted integers
in the data-* JSON, the file's own line endings. Standard library only.

Exit codes: 0 ok (or fixed), 1 mismatches, 2 unusable claims file or arguments.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "claims.json"
AGENCIES = ("CPSC", "FDA", "FSIS", "NHTSA", "USCG")
KEYS = ("dataset", "edition", "snapshot", "recalls", "recalled_products", "by_agency",
        "fda_safety_alerts", "hazards", "firms", "data_sources", "zip_bytes")
INT_KEYS = ("recalls", "recalled_products", "fda_safety_alerts", "firms", "data_sources", "zip_bytes")
DOT = "(?:" + chr(0xB7) + r"|\\u00b7)"  # a middle dot (U+00B7), raw or JSON-escaped (the notebook escapes it)
N = r"\d[\d,]*"
CTA = r"All (?P<v>\d[\d,]*) official recalls with the provenance ledger"
NEXT_STEPS = """next: rebuild what derives from the surfaces, then re-check:
  python scripts/generate_seo_pages.py
  python scripts/generate_seo_pages.py --sitemap-only
  python scripts/i18n_common.py build && python scripts/i18n_common.py check
  python ../scripts/sitemap_keep_lastmod.py
  python scripts/check_claims.py"""


def fmt(n):
    return f"{n:,}"


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate(c):
    """Schema problems that make the claims unusable (exit 2)."""
    if not isinstance(c, dict):
        return ["claims must be a JSON object"]
    errs = []
    missing = [k for k in KEYS if k not in c]
    extra = [k for k in c if k not in KEYS]
    if missing:
        errs.append(f"missing keys: {', '.join(missing)}")
    if extra:
        errs.append(f"unknown keys: {', '.join(extra)} (update the schema here and in the private emitter together)")
    if errs:
        return errs
    if c["dataset"] != "RecallDB":
        errs.append(f"dataset is {c['dataset']!r}, expected 'RecallDB'")
    if not (isinstance(c["edition"], str) and re.fullmatch(r"\d{4}\.\d{2}", c["edition"])):
        errs.append("edition must look like YYYY.MM")
    if not (isinstance(c["snapshot"], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["snapshot"])):
        errs.append("snapshot must look like YYYY-MM-DD")
    for k in INT_KEYS:
        if not is_int(c[k]) or c[k] < 0:
            errs.append(f"{k} must be a non-negative integer")
    ba = c["by_agency"]
    if not isinstance(ba, dict) or sorted(ba) != sorted(AGENCIES) or not all(is_int(v) and v >= 0 for v in ba.values()):
        errs.append(f"by_agency must map exactly {', '.join(AGENCIES)} to non-negative integers")
    hz = c["hazards"]
    good_key = re.compile(r"[a-z_]+")
    if not isinstance(hz, dict) or not hz or not all(isinstance(k, str) and good_key.fullmatch(k) and is_int(v) and v >= 0
                                                     for k, v in hz.items()):
        errs.append("hazards must map hazard keys (a-z, _) to non-negative integers")
    return errs


def consistency(c):
    """Internal contradictions in otherwise well-formed claims (reported as mismatches)."""
    out = []
    total = sum(c["by_agency"].values())
    if total != c["recalls"]:
        out.append(f"claims: sum(by_agency) = {fmt(total)} but recalls = {fmt(c['recalls'])}")
    if c["fda_safety_alerts"] > c["by_agency"]["FDA"]:
        out.append("claims: fda_safety_alerts exceeds the FDA count it is folded into")
    if c["zip_bytes"] <= 0:
        out.append("claims: zip_bytes must be positive")
    return out


def canonical(c):
    """claims.json layout: schema key order, agencies and hazards sorted, 2-space indent."""
    out = {k: c[k] for k in KEYS}
    out["by_agency"] = {k: c["by_agency"][k] for k in sorted(c["by_agency"])}
    out["hazards"] = {k: c["hazards"][k] for k in sorted(c["hazards"])}
    return json.dumps(out, indent=2) + "\n"


def hand_written(c):
    """(file, label, regex with group v, expected, occurrences) for every hand-written count."""
    r, p, a = fmt(c["recalls"]), fmt(c["recalled_products"]), c["by_agency"]
    mb = str(round(c["zip_bytes"] / 1e6))
    ba_json = {k: a[k] for k in sorted(a)}
    hz_json = {k: c["hazards"][k] for k in sorted(c["hazards"])}
    lede = [(f"(?P<v>{N}) official recalls, {N} linked products", r, "intro recalls"),
            (f"{N} official recalls, (?P<v>{N}) linked products", p, "intro products")]
    tables = [(rf"\| Recalls \| (?P<v>{N}) \|", r, "table: Recalls"),
              (rf"\| Recalled products \| (?P<v>{N}) \|", p, "table: Recalled products"),
              (rf"\| Source pulls \| (?P<v>{N}) \|", fmt(c["data_sources"]), "table: Source pulls"),
              (rf"\| Firms \| (?P<v>{N}) \|", fmt(c["firms"]), "table: Firms"),
              (r"\| Hazard taxonomy \| (?P<v>\d+) \|", str(len(c["hazards"])), "table: Hazard taxonomy")]
    tables += [(rf"\| {k} \| (?P<v>{N}) \|", fmt(a[k]), f"source coverage: {k}") for k in AGENCIES]
    specs = [
        ("index.html", "data-agencies", r"data-agencies='(?P<v>[^']*)'", ba_json, 1),
        ("index.html", "data-hazards", r"data-hazards='(?P<v>[^']*)'", hz_json, 1),
        *[("index.html", f"hero lede: {lab}", rx, exp, 1) for rx, exp, lab in lede],
        ("index.html", "hero stat: recalls", f"<dt>(?P<v>{N})</dt><dd>official recalls</dd>", r, 1),
        ("index.html", "hero stat: products", f"<dt>(?P<v>{N})</dt><dd>linked products</dd>", p, 1),
        ("index.html", "pricing: recalls", f"<li>(?P<v>{N}) normalized recall records</li>", r, 1),
        ("index.html", "pricing: products", f"<li>(?P<v>{N}) linked recalled products</li>", p, 1),
        ("index.html", "pricing: full snapshot MB", r"unlike the (?P<v>\d[\d,.]*) MB full snapshot", mb, 1),
        ("README.md", "headline: recalls", f"(?P<v>{N}) official recalls - {N} recalled products", r, 1),
        ("README.md", "headline: products", f"{N} official recalls - (?P<v>{N}) recalled products", p, 1),
        *[("README.md", lab, rx, exp, 1) for rx, exp, lab in lede + tables],
        ("llms.txt", "summary: recalls", f"dataset of (?P<v>{N}) official U\\.S\\. federal product recall records", r, 1),
        ("llms.txt", "summary: products", f"covering (?P<v>{N}) linked recalled products", p, 1),
        ("llms.txt", "sources: CPSC", rf"CPSC \((?P<v>{N})\)", fmt(a["CPSC"]), 1),
        ("llms.txt", "sources: FDA", rf"FDA/openFDA \+ FDA Safety Alerts \((?P<v>{N})\)", fmt(a["FDA"]), 1),
        ("llms.txt", "sources: NHTSA", rf"NHTSA \((?P<v>{N})\)", fmt(a["NHTSA"]), 1),
        ("llms.txt", "sources: FSIS", rf"USDA FSIS \((?P<v>{N})\)", fmt(a["FSIS"]), 1),
        ("llms.txt", "sources: USCG", rf"USCG \((?P<v>{N})\)", fmt(a["USCG"]), 1),
        ("kaggle/dataset-metadata.json", "headline: recalls", f"(?P<v>{N}) official recalls {DOT} {N} recalled products", r, 1),
        ("kaggle/dataset-metadata.json", "headline: products", f"{N} official recalls {DOT} (?P<v>{N}) recalled products", p, 1),
        *[("kaggle/dataset-metadata.json", lab, rx, exp, 1) for rx, exp, lab in tables],
        ("kaggle/starter_notebook.ipynb", "recalls", f"(?P<v>{N}) recalls {DOT} {N} products", r, 2),
        ("kaggle/starter_notebook.ipynb", "products", f"{N} recalls {DOT} (?P<v>{N}) products", p, 2),
        ("hazards/chemical_toxic.html", "CTA band (source of all 16 pages)", CTA, r, 1),
    ]
    return specs


def generated(c, locales):
    """Counts in generated pages: reported, rebuilt by the generators rather than by --fix."""
    r, hz = fmt(c["recalls"]), c["hazards"]
    specs = []
    for key, n in sorted(hz.items()):
        page = f"hazards/{key}.html"
        specs += [(page, "hazard count", f"RecallDB classifies <strong>(?P<v>{N})</strong> official recalls under", fmt(n), 1),
                  (page, "classified-rows total", f"% of the (?P<v>{N}) classified hazard rows", fmt(sum(hz.values())), 1),
                  (page, "CTA band", CTA, r, 1)]
    specs += [(f"agencies/{a.lower()}.html", "CTA band", CTA, r, 1) for a in AGENCIES]
    for lang in locales:
        if (ROOT / lang / "index.html").exists():
            specs += [(f"{lang}/index.html", "data-agencies", r"data-agencies='(?P<v>[^']*)'",
                       {k: c["by_agency"][k] for k in sorted(c["by_agency"])}, 1),
                      (f"{lang}/index.html", "data-hazards", r"data-hazards='(?P<v>[^']*)'",
                       {k: hz[k] for k in sorted(hz)}, 1)]
    return specs


def read(rel):
    with open(ROOT / rel, encoding="utf-8", newline="") as f:  # keep the file's own line endings
        return f.read()


def write(rel, text):
    with open(ROOT / rel, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def same(found, expected):
    if isinstance(expected, dict):
        try:
            return json.loads(found) == expected
        except ValueError:
            return False
    return found == expected


def render(expected):
    return json.dumps(expected) if isinstance(expected, dict) else expected


def describe(found, expected):
    """'found X, expected Y'; for the data-* JSON, only the keys that differ."""
    if isinstance(expected, dict):
        try:
            got = json.loads(found)
        except ValueError:
            return f"not valid JSON, expected {render(expected)}"
        if isinstance(got, dict):
            keys = sorted(set(got) | set(expected))
            return "differs: " + ", ".join(f"{k} {got.get(k, '-')} -> {expected.get(k, '-')}"
                                           for k in keys if got.get(k) != expected.get(k))
    return f"found {found}, expected {render(expected)}"


def apply_specs(specs, fix, problems, stuck, fixed):
    """Check (and with fix=True rewrite) every spec. Fills problems (value mismatches),
    stuck (what --fix cannot repair: a missing file, copy whose shape changed) and fixed."""
    by_file = {}
    for spec in specs:
        by_file.setdefault(spec[0], []).append(spec)
    for rel, file_specs in by_file.items():
        if not (ROOT / rel).exists():
            stuck.append(f"{rel}: file missing")
            continue
        text = original = read(rel)
        for _, label, rx, expected, count in file_specs:
            matches = list(re.finditer(rx, text))
            if len(matches) != count:
                stuck.append(f"{rel}: {label}: pattern found {len(matches)} time(s), expected {count} "
                             "(the copy changed shape; update it or scripts/check_claims.py by hand)")
                continue
            bad = [m for m in matches if not same(m.group("v"), expected)]
            for m in bad:
                problems.append(f"{rel}:{line_of(text, m.start('v'))}: {label}: {describe(m.group('v'), expected)}")
            if fix and bad:
                for m in reversed(bad):
                    text = text[:m.start("v")] + render(expected) + text[m.end("v"):]
        if fix and text != original:
            write(rel, text)
            fixed.append(rel)


HZ_LINE = re.compile(r"^(?P<key>[a-z_]+),.*,(?P<v>\d+)\r?$", re.M)


def check_hazards_csv(c, fix, problems, stuck, fixed):
    rel = "samples/hazards.csv"
    if not (ROOT / rel).exists():
        stuck.append(f"{rel}: file missing")
        return
    text = original = read(rel)
    if not text.startswith("hazard_key,description,recall_count"):
        stuck.append(f"{rel}: header is not hazard_key,description,recall_count")
        return
    rows = {m.group("key"): m for m in HZ_LINE.finditer(text)}
    want = c["hazards"]
    if set(rows) != set(want):
        only_csv, only_claims = sorted(set(rows) - set(want)), sorted(set(want) - set(rows))
        stuck.append(f"{rel}: hazard keys differ from claims (only in the CSV: {only_csv or '-'}; only in claims: "
                     f"{only_claims or '-'}); copy csv/hazards.csv from the snapshot ZIP by hand")
        return
    bad = [(k, m) for k, m in rows.items() if int(m.group("v")) != want[k]]
    for k, m in bad:
        problems.append(f"{rel}:{line_of(text, m.start('v'))}: recall_count {k}: found {m.group('v')}, expected {want[k]}")
    if fix and bad:
        for k, m in sorted(bad, key=lambda t: -t[1].start("v")):
            text = text[:m.start("v")] + str(want[k]) + text[m.end("v"):]
        if text != original:
            write(rel, text)
            fixed.append(rel)


def stats_note(c):
    """/stats/ is regenerated from the full SQLite, not by this script: say when it lags."""
    try:
        data = json.loads(read("stats/data.json"))
        snap, recalls = data["snapshot"], data["totals"]["recalls"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if snap == c["snapshot"] and recalls == c["recalls"]:
        return None
    return (f"note: /stats/ describes snapshot {snap} ({fmt(recalls)} recalls); claims.json is {c['edition']} snapshot "
            f"{c['snapshot']} ({fmt(c['recalls'])} recalls). Regenerate it from that edition's recalldb.sqlite with "
            "scripts/generate_stats.py when possible (not an error).")


def locales():
    try:
        return json.loads(read("i18n.config.json")).get("locales", [])
    except (OSError, ValueError):
        return []


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="Check (or --fix) every hand-written RecallDB count against claims.json.")
    ap.add_argument("--fix", action="store_true", help="rewrite the hand-written surfaces (and claims.json with --claims)")
    ap.add_argument("--claims", metavar="PATH", help="claims file to use instead of ./claims.json, e.g. the private "
                    "CI's recalldb-claims-latest.json; with --fix it replaces claims.json")
    args = ap.parse_args(argv)

    src = Path(args.claims).resolve() if args.claims else CLAIMS
    try:
        claims = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"cannot read claims from {src}: {e}")
        return 2
    errs = validate(claims)
    if errs:
        print(f"{src}: unusable claims:\n  " + "\n  ".join(errs))
        return 2

    problems, stuck, fixed = [], [], []
    inconsistent = consistency(claims)
    if inconsistent:
        if args.fix:
            print("refusing to --fix from inconsistent claims:\n  " + "\n  ".join(inconsistent))
            return 1
        stuck += inconsistent

    if args.fix:
        # dry pass first: when anything needs a person (copy changed shape, hazard taxonomy
        # changed), write nothing at all rather than leave a half-updated site
        apply_specs(hand_written(claims), False, [], stuck, [])
        check_hazards_csv(claims, False, [], stuck, [])
        if stuck:
            print("could not fix (nothing written):\n  " + "\n  ".join(stuck))
            return 1
        if src != CLAIMS and (not CLAIMS.exists() or CLAIMS.read_text(encoding="utf-8") != canonical(claims)):
            with open(CLAIMS, "w", encoding="utf-8", newline="\n") as f:
                f.write(canonical(claims))
            fixed.append("claims.json")
        apply_specs(hand_written(claims), True, problems, stuck, fixed)
        check_hazards_csv(claims, True, problems, stuck, fixed)
        for rel in fixed:
            print(f"fixed: {rel}")
        if not fixed:
            print("nothing to change: every hand-written surface already matches")
            return 0
        print(NEXT_STEPS)
        return 0

    if src != CLAIMS and (not CLAIMS.exists() or CLAIMS.read_text(encoding="utf-8") != canonical(claims)):
        problems.append(f"claims.json: differs from {src}")
    apply_specs(hand_written(claims), False, problems, stuck, fixed)
    check_hazards_csv(claims, False, problems, stuck, fixed)

    hand = len(problems) + len(stuck)
    apply_specs(generated(claims, locales()), False, problems, stuck, fixed)
    problems = stuck + problems
    note = stats_note(claims)
    if problems:
        print(f"{len(problems)} claim mismatch(es) against {src.name} ({claims['edition']}, snapshot {claims['snapshot']}):")
        for p in problems:
            print(f"  {p}")
        if hand:
            print("fix the hand-written ones with: python scripts/check_claims.py --fix  (then rebuild the generated pages)")
        else:
            print("the hand-written surfaces match but the generated pages are stale; " + NEXT_STEPS[len("next: "):])
        if note:
            print(note)
        return 1
    print(f"OK: every checked count matches {src.name} ({claims['edition']}, snapshot {claims['snapshot']}): "
          f"{fmt(claims['recalls'])} recalls, {fmt(claims['recalled_products'])} products")
    if note:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
