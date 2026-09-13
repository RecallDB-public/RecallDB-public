#!/usr/bin/env python3
"""Build RecallDB's hazard and agency pages from the sample CSVs.

Run from the repo root:  python scripts/generate_seo_pages.py
Then:                    python ../scripts/generate_dir_hubs.py recalldb   (hub index pages)
Then:                    python scripts/generate_seo_pages.py --sitemap-only
"""
import csv, html, json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from seo_common import fit_title, fit_desc, write_sitemap, related_block

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://recalldb.dataengineered.io"
BRAND = "RecallDB"

AGENCIES = {  # slug: (short, full name, domain wording, one-line scope)
    "cpsc": ("CPSC", "Consumer Product Safety Commission", "consumer products", "Consumer product recalls from the CPSC SaferProducts recall API."),
    "fda": ("FDA", "Food and Drug Administration", "food, drugs, devices, cosmetics, biologics, veterinary", "FDA enforcement reports across food, drugs, medical devices, cosmetics, biologics and animal/veterinary products."),
    "fsis": ("FSIS", "USDA Food Safety and Inspection Service", "meat, poultry and egg products", "FSIS recalls and public health alerts for meat, poultry and processed egg products."),
    "nhtsa": ("NHTSA", "National Highway Traffic Safety Administration", "vehicles, tires, child seats and equipment", "NHTSA safety recalls for vehicles, tires, child restraints and motor-vehicle equipment."),
    "uscg": ("USCG", "United States Coast Guard", "recreational boats and marine equipment", "USCG recreational-boat and marine-equipment recall campaigns."),
}
CTA_MARK = '<section class="cta-band"'


def read(name):
    with open(ROOT / "samples" / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def chrome():
    """Header and CTA band copied from an existing page so pricing copy stays byte-identical."""
    src = (ROOT / "hazards" / "chemical_toxic.html").read_text(encoding="utf-8")
    header = src[src.index('<header class="site-nav">'): src.index("</header>") + len("</header>")]
    cta = src[src.index(CTA_MARK): src.index("</section>", src.index(CTA_MARK)) + len("</section>")]
    return header, cta


def hazard_name(key):
    return key.replace("_", " ").capitalize() if key != "other" else "Other / unmapped"


def page(url, title, desc, h1, eyebrow, lede, body, crumbs, header, cta, rel):
    ld = [
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": h1, "description": desc, "url": url,
         "isPartOf": {"@type": "WebSite", "url": BASE}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]},
    ]
    crumb_html = " &rsaquo; ".join(f'<a href="{html.escape(u)}">{html.escape(n)}</a>' if i < len(crumbs) - 1 else html.escape(n)
                                   for i, (n, u) in enumerate(crumbs))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{url}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{BASE}/assets/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html.escape(title)}">
  <meta name="twitter:description" content="{html.escape(desc)}">
  <meta name="theme-color" content="#0b1117">
  <link rel="manifest" href="../site.webmanifest">
  <link rel="stylesheet" href="../index.css">
  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
  <style>.related ul{{list-style:none;padding:0;margin:.5rem 0 0}}.related li{{padding:.3rem 0}}.related-why{{opacity:.6;font-size:.9em}}.crumb{{font-size:.8rem;opacity:.6;margin:0 0 1rem}}</style>
</head>
<body>
{header}<main class="band"><p class="crumb">{crumb_html}</p><p class="eyebrow">{html.escape(eyebrow)}</p><h1>{html.escape(h1)}</h1><p class="lede">{html.escape(lede)}</p>{body}{rel}{cta}</main>
</body>
</html>
"""


def main(write_pages=True, write_sm=True):
    hazards = read("hazards.csv"); recalls = read("recalls.csv"); sources = read("data_sources.csv")
    header, cta = chrome()
    total_classified = sum(int(h["recall_count"]) for h in hazards)
    by_key = {h["hazard_key"]: h for h in hazards}
    ranked = sorted(hazards, key=lambda h: -int(h["recall_count"]))
    # sample cross-tabs (200-row sample only — labelled as such in copy)
    ag_hz = Counter(); hz_ag = defaultdict(Counter); ex = defaultdict(list); ag_sev = defaultdict(Counter); ag_rows = Counter()
    for r in recalls:
        ag = r["source_agency"].strip(); ag_rows[ag] += 1
        if r.get("severity", "").strip(): ag_sev[ag][r["severity"].strip()] += 1
        for k in [k.strip() for k in r["hazard_keys"].split("|") if k.strip()]:
            ag_hz[(ag, k)] += 1; hz_ag[k][ag] += 1
            if len(ex[k]) < 3 and r.get("title", "").strip(): ex[k].append(r)
    endpoints = {s["source_agency"].strip(): s for s in sources}
    entries = [(BASE + "/", ROOT / "index.html", "weekly", "1.0"),
               (BASE + "/agencies/", ROOT / "agencies" / "index.html", "monthly", "0.8"),
               (BASE + "/hazards/", ROOT / "hazards" / "index.html", "monthly", "0.8")]

    for h in hazards:
        key, name, n = h["hazard_key"], hazard_name(h["hazard_key"]), int(h["recall_count"])
        url = f"{BASE}/hazards/{key}"; fp = ROOT / "hazards" / f"{key}.html"
        entries.append((url, fp, "weekly", "0.7"))
        if not write_pages: continue
        share = 100.0 * n / total_classified
        rank = ranked.index(h) + 1
        agencies = hz_ag[key].most_common()
        ag_txt = ", ".join(f"{AGENCIES[a.lower()][0]} ({c})" for a, c in agencies) if agencies else "no agency in the free sample"
        title = fit_title(f"{name} recalls", f"{n:,} records", BRAND)
        desc = fit_desc(f"{n:,} {name.lower()} recalls in RecallDB ({share:.1f}% of classified rows, rank {rank} of {len(hazards)}). "
                        f"{h['description']} Issued by {', '.join(AGENCIES[a.lower()][0] for a, _ in agencies) or 'federal agencies'}.")
        prose = (f"<p>RecallDB classifies <strong>{n:,}</strong> official recalls under <em>{html.escape(name.lower())}</em>, "
                 f"{share:.1f}% of the {total_classified:,} classified hazard rows and the #{rank} hazard bucket of {len(hazards)}. "
                 f"The bucket is defined as: {html.escape(h['description'])}.</p>"
                 f"<p>In the free 200-row sample, this hazard appears in rows issued by {html.escape(ag_txt)}. "
                 f"Agency free text is kept verbatim in <code>raw_hazard_texts</code>; the normalized key is <code>{key}</code>.</p>")
        exs = "".join(f'<li><a href="{html.escape(r["source_url"])}" rel="noopener">{html.escape(r["title"][:110])}</a>'
                      f' <span class="related-why">— {html.escape(r["source_agency"])}, {html.escape(r["recall_date"][:10])}</span></li>'
                      for r in ex[key] if r.get("source_url"))
        body = prose + (f'<h2>Sample recalls in this bucket</h2><ul class="related">{exs}</ul>' if exs else "")
        neighbours = [x for x in ranked if x is not h][max(0, rank - 2): rank + 1][:2]
        rel_items = [(f"../agencies/{a.lower()}", f"{AGENCIES[a.lower()][0]} recall data", f"{c} sample rows carry this hazard") for a, c in agencies[:3]]
        rel_items += [(f"../hazards/{x['hazard_key']}", f"{hazard_name(x['hazard_key'])} recalls", f"{int(x['recall_count']):,} records") for x in neighbours]
        rel_items.append(("../hazards/", "All hazard categories", None))
        fp.write_text(page(url, title, desc, f"{name} recalls", "Hazard taxonomy", h["description"], body,
                           [("Home", BASE + "/"), ("Hazards", BASE + "/hazards/"), (f"{name} recalls", url)], header, cta,
                           related_block(rel_items, "Related pages")), encoding="utf-8", newline="\n")

    for slug, (short, full, domain, scope) in AGENCIES.items():
        url = f"{BASE}/agencies/{slug}"; fp = ROOT / "agencies" / f"{slug}.html"
        entries.append((url, fp, "weekly", "0.7"))
        if not write_pages: continue
        hz = [(k, c) for (a, k), c in ag_hz.items() if a == short]; hz.sort(key=lambda t: -t[1])
        sev = ag_sev[short].most_common(3)
        ep = endpoints.get(short)
        title = fit_title(f"{short} recall data", domain, BRAND)
        desc = fit_desc(f"{full} ({short}) recalls in RecallDB: {domain}. Top hazards in the sample: "
                        f"{', '.join(hazard_name(k).lower() for k, _ in hz[:3]) or 'see hazard pages'}. Rows link to their source URL.")
        prose = (f"<p>{html.escape(scope)} RecallDB normalizes the {html.escape(full)} feed into the same schema as the other four agencies, "
                 f"keeping every row's <code>source_url</code> and a <code>source_id</code> that resolves to <code>data_sources.csv</code>.</p>"
                 f"<p>The free sample holds {ag_rows[short]} {short} rows. Their leading hazard buckets are "
                 f"{', '.join(f'{hazard_name(k).lower()} ({c})' for k, c in hz[:3]) or 'not yet classified'}"
                 + (f"; severity labels present: {', '.join(f'{s} ({c})' for s, c in sev)}" if sev else "") + ".</p>"
                 + (f"<p>Source endpoint: <code>{html.escape(ep['endpoint_url'])}</code>, retrieved {html.escape(ep['retrieved_at'][:10])} "
                    f"({int(ep['raw_payload_bytes']):,} bytes raw).</p>" if ep else ""))
        rows = "".join(f'<div class="schema-row"><strong>{k}</strong><span>{html.escape(v)}</span></div>'
                       for k, v in (("Agency", full), ("Domain", domain), ("Traceability", "Rows link to source_url and data_sources.csv through source_id.")))
        body = f'<div class="schema-card">{rows}</div>' + prose
        rel_items = [(f"../hazards/{k}", f"{hazard_name(k)} recalls", f"{c} sample rows") for k, c in hz[:4]]
        rel_items += [(f"../agencies/{o}", f"{AGENCIES[o][0]} recall data", None) for o in AGENCIES if o != slug][:2]
        fp.write_text(page(url, title, desc, f"{short} recall data", "Agency source", scope, body,
                           [("Home", BASE + "/"), ("Agencies", BASE + "/agencies/"), (f"{short} recall data", url)], header, cta,
                           related_block(rel_items, "Related pages")), encoding="utf-8", newline="\n")

    if write_sm:
        print("sitemap URLs:", write_sitemap(ROOT, entries))


if __name__ == "__main__":
    main(write_pages="--sitemap-only" not in sys.argv, write_sm="--pages-only" not in sys.argv)
