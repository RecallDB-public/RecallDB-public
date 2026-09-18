#!/usr/bin/env python3
"""
RecallDB statistics page generator (`RecallDB-public`).

Reads the FULL private snapshot (the private pipeline's recalldb.sqlite, never the
public sample) and writes a citable, embeddable statistics page:

    stats/index.html          the page (URL /stats/)
    stats/charts/<slug>.svg   one standalone SVG per chart (for <img> embeds elsewhere)
    stats/data.json           every figure on the page, machine-readable

Only aggregates leave the private database -- no row-level data is written (the
"largest recalls" table quotes public agency record titles, which are already on the
agencies' own sites). Every figure states its denominator and source.

Re-run after each data refresh, then `python scripts/generate_seo_pages.py --sitemap-only`,
`python scripts/i18n_common.py build` and `... check`.

Usage:
    python scripts/generate_stats.py                 # ../../07_Product_Recalls_RecallDB/recalldb.sqlite
    python scripts/generate_stats.py --db PATH       # or RECALLDB_SQLITE=PATH
"""
import argparse
import datetime as dt
import os
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats_common import (Site, esc, n, pct, data, svg_hbar, svg_line, figure, table, section, toc, tiles,
                          article_ld, COPY_JS, STATS_CSS, write_outputs)

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "stats"
FIRST_PUBLISHED = "2026-09-18"
DEFAULT_DB = BASE_DIR.parent / "07_Product_Recalls_RecallDB" / "recalldb.sqlite"
FULL_COVERAGE_FROM = 2012  # openFDA enforcement reports are published in bulk from 2012

SITE = Site(base_url="https://recalldb.dataengineered.io", brand="RecallDB",
            snippet_label="RecallDB U.S. recall statistics",
            surface="#0b1117", surface2="#0f1b24", ink="#e8f3f2", muted="#9eb3ba", grid="#1c2b36", accent="#14b8a6",
            font="'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif",
            mono="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace")

AGENCY = {"CPSC": "Consumer Product Safety Commission", "FDA": "Food and Drug Administration",
          "FSIS": "USDA Food Safety and Inspection Service", "NHTSA": "National Highway Traffic Safety Administration",
          "USCG": "United States Coast Guard"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def hazard_name(key):
    return key.replace("_", " ").capitalize() if key != "other" else "Other / unmapped"


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------

def compute(db_path):
    con = sqlite3.connect(str(db_path))
    q = lambda sql, *a: con.execute(sql, a).fetchall()
    s = {}
    s["snapshot_date"] = q("select max(date(retrieved_at)) from data_sources")[0][0]
    s["recalls"] = q("select count(*) from recalls")[0][0]
    s["products"] = q("select count(*) from recalled_products")[0][0]
    s["firms"] = q("select count(distinct recalling_firm_id) from recalls where recalling_firm_id is not null")[0][0]
    s["first_date"], s["last_date"] = q("select min(recall_date), max(recall_date) from recalls")[0]
    s["last_year"] = int(s["last_date"][:4])
    s["last_month"] = int(s["last_date"][5:7])

    # agencies
    ag = q("select source_agency, count(*), min(recall_date), max(recall_date) from recalls group by 1 order by 2 desc")
    s["by_agency"] = [(a, c, pct(c, s["recalls"]), lo, hi) for a, c, lo, hi in ag]

    # per year (full-coverage years only in the chart; last year is partial)
    yr = dict(q("select cast(substr(recall_date,1,4) as int), count(*) from recalls group by 1"))
    s["per_year"] = [(y, yr.get(y, 0)) for y in range(FULL_COVERAGE_FROM, s["last_year"])]
    s["partial_year"] = (s["last_year"], yr.get(s["last_year"], 0))
    s["mean_per_year"] = int(round(statistics.mean(v for _, v in s["per_year"])))
    s["mean_per_day"] = round(s["mean_per_year"] / 365.0, 1)
    ay = defaultdict(dict)
    for y, a, c in q("select cast(substr(recall_date,1,4) as int), source_agency, count(*) from recalls "
                     "where recall_date >= ? group by 1,2", f"{s['last_year'] - 10}-01-01"):
        ay[y][a] = c
    s["agency_years"] = [(y, {a: ay[y].get(a, 0) for a in AGENCY}) for y in sorted(ay)]

    # hazards
    hz = q("select h.hazard_key, h.description, count(*) from recall_hazards rh join hazards h using(hazard_key) group by 1 order by 3 desc")
    total_h = sum(c for _, _, c in hz)
    other = next((c for k, _, c in hz if k == "other"), 0)
    classified = total_h - other
    s["hazard_rows"], s["hazard_other"], s["hazard_classified"] = total_h, other, classified
    s["hazard_other_pct"] = pct(other, total_h)
    s["hazards"] = [(hazard_name(k), d, c, pct(c, classified)) for k, d, c in hz if k != "other"]
    hz_ag = defaultdict(dict)
    for a, k, c in q("select r.source_agency, rh.hazard_key, count(*) from recall_hazards rh join recalls r using(recall_id) "
                     "where rh.hazard_key <> 'other' group by 1,2"):
        hz_ag[a][k] = c
    s["top_hazard_by_agency"] = []
    for a in AGENCY:
        d = hz_ag.get(a, {})
        if d:
            k, c = max(d.items(), key=lambda t: t[1])
            s["top_hazard_by_agency"].append((a, hazard_name(k), c, pct(c, sum(d.values()))))

    # FDA classification
    fda = dict(q("select severity, count(*) from recalls where source_agency='FDA' and severity like 'Class %' group by 1"))
    fda_total = sum(fda.values())
    s["fda_classes"] = [(k, fda[k], pct(fda[k], fda_total)) for k in ("Class I", "Class II", "Class III") if k in fda]
    s["fda_classified"] = fda_total
    c1 = defaultdict(int); ct = defaultdict(int)
    for y, sev, c in q("select cast(substr(recall_date,1,4) as int), severity, count(*) from recalls "
                       "where source_agency='FDA' and severity like 'Class %' and recall_date >= ? group by 1,2",
                       f"{s['last_year'] - 11}-01-01"):
        ct[y] += c
        if sev == "Class I":
            c1[y] += c
    s["fda_class1_by_year"] = [(y, c1[y], ct[y], pct(c1[y], ct[y])) for y in sorted(ct) if y < s["last_year"]]

    # firms
    s["top_firms"] = [(nm, c, ", ".join(sorted(a.split(","))))
                      for nm, c, a in q("select f.display_name, count(*) c, group_concat(distinct r.source_agency) "
                                        "from recalls r join firms f on f.firm_id=r.recalling_firm_id group by f.firm_id order by c desc limit 15")]

    # units affected (only CPSC and NHTSA publish them)
    s["units"] = []
    for a in ("NHTSA", "CPSC"):
        vals = [v for (v,) in q("select units_affected from recalls where source_agency=? and units_affected is not null and units_affected > 0", a)]
        if vals:
            s["units"].append(dict(agency=a, campaigns=len(vals), total=sum(vals), median=int(statistics.median(vals)),
                                   over_100k=sum(1 for v in vals if v >= 100000), over_100k_pct=pct(sum(1 for v in vals if v >= 100000), len(vals)),
                                   over_1m=sum(1 for v in vals if v >= 1000000)))
    s["largest"] = [(a, d, t[:90] + ("…" if len(t) > 90 else ""), u) for a, d, t, u in q(
        "select source_agency, recall_date, title, units_affected from recalls where units_affected is not null order by units_affected desc limit 10")]

    # vehicle model years (NHTSA product rows)
    my = dict(q("select model_year, count(*) from recalled_products p join recalls r using(recall_id) "
                "where r.source_agency='NHTSA' and model_year between 1990 and 2030 group by 1"))
    s["model_years"] = [(y, my.get(y, 0)) for y in range(2000, s["last_year"] + 1)]
    s["model_year_rows"] = sum(my.values())
    s["vehicle_rows"] = q("select count(*) from recalled_products p join recalls r using(recall_id) where r.source_agency='NHTSA'")[0][0]
    s["products_per_nhtsa_recall"] = round(s["vehicle_rows"] / next(c for a, c, *_ in s["by_agency"] if a == "NHTSA"), 2)

    # timing (full-coverage years, whole years only)
    since = f"{FULL_COVERAGE_FROM}-01-01"; until = f"{s['last_year']}-01-01"
    mo = dict(q("select cast(substr(recall_date,6,2) as int), count(*) from recalls where recall_date >= ? and recall_date < ? group by 1", since, until))
    s["by_month"] = [(MONTHS[m - 1], mo.get(m, 0)) for m in range(1, 13)]
    wd = dict(q("select cast(strftime('%w', recall_date) as int), count(*) from recalls where recall_date >= ? and recall_date < ? group by 1", since, until))
    s["by_weekday"] = [(WEEKDAYS[d], wd.get(d, 0)) for d in range(7)]
    s["timing_n"] = sum(mo.values())
    s["timing_years"] = (FULL_COVERAGE_FROM, s["last_year"] - 1)

    # NHTSA urgent advisories
    adv = q("select severity, count(*), min(recall_date) from recalls where source_agency='NHTSA' and severity is not null group by 1")
    s["nhtsa_advisories"] = dict(do_not_drive=sum(c for sv, c, _ in adv if "do_not_drive" in sv),
                                 park_outside=sum(c for sv, c, _ in adv if "park_outside" in sv),
                                 since=min((d for _, _, d in adv), default=None))
    con.close()
    return s


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

CSS = """
    :root { --bg-paper: #0b1117; --bg-paper-2: #0f1b24; --text-ink: #e8f3f2; --text-muted: #9eb3ba;
            --rule-color: rgba(124, 243, 223, 0.16); --accent: #14b8a6; --radius: 8px; }
    .stats-wrap { max-width: 1000px; margin: 0 auto; padding: 44px clamp(18px, 4vw, 40px) 64px; }
    .stats-wrap h1 { font-size: clamp(2rem, 3.6vw, 2.8rem); line-height: 1.08; margin: 0 0 8px; }
    .stats-wrap h2 { font-size: 1.5rem; margin: 0; }
    .stats-wrap h3 { font-size: 1.05rem; margin: 24px 0 0; }
    .stats-wrap .lede { font-size: 1.05rem; margin-top: 12px; max-width: 76ch; }
    .stats-wrap a { color: #b6f7ed; }
    .crumb { font-size: .8rem; opacity: .6; margin: 0 0 1rem; }
    .cta-inline { margin-top: 56px; padding: 28px; border: 1px solid var(--rule-color); border-radius: var(--radius); background: linear-gradient(180deg, rgba(18,35,47,.86), rgba(12,22,30,.9)); }
    .cta-inline p { color: var(--text-muted); margin: 8px 0 16px; }
"""


def chrome():
    """Header copied from an existing page so the nav stays byte-identical."""
    src = (BASE_DIR / "hazards" / "chemical_toxic.html").read_text(encoding="utf-8")
    return src[src.index('<header class="site-nav">'): src.index("</header>") + len("</header>")]


def build_page(s, charts):
    site = SITE
    snap = s["snapshot_date"]
    ly = s["last_year"]
    src_note = f"Source: RecallDB, recalldb.dataengineered.io/stats · snapshot {snap} · CC BY 4.0"
    sections = []

    # 1. per year
    py = s["per_year"]
    peak_y, peak_v = max(py, key=lambda t: t[1])
    charts["recalls-per-year"] = svg_line(site, f"U.S. product recalls per year, {py[0][0]} to {py[-1][0]}",
                                          "Official recalls issued by CPSC, FDA, FSIS, NHTSA and USCG",
                                          [(str(y), v) for y, v in py], lambda v: n(v), src_note,
                                          peak_label=f"{n(peak_v)} ({peak_y})", last_label=n(py[-1][1]), right=80)
    sections.append(section(
        site, "per-year", "How many recalls the U.S. issues",
        f"Across the five federal agencies, the United States issued an average of <strong>{n(s['mean_per_year'])} recalls a year</strong> "
        f"from {py[0][0]} to {py[-1][0]}, about {s['mean_per_day']} a day. The peak year was {peak_y} with {n(peak_v)}; "
        f"{py[-1][0]} closed at {n(py[-1][1])}, and {s['partial_year'][0]} stands at {n(s['partial_year'][1])} through {MONTHS[s['last_month'] - 1]}.",
        figure(site, "recalls-per-year", charts["recalls-per-year"], f"U.S. product recalls per year, {py[0][0]} to {py[-1][0]}", f"{n(sum(v for _, v in py))} recalls over {len(py)} full years"),
        table(["Year"] + list(AGENCY) + ["Total"],
              [(str(y),) + tuple(n(d[a]) for a in AGENCY) + (n(sum(d.values())),) for y, d in s["agency_years"]],
              set(range(1, len(AGENCY) + 2))),
        f"One row per official recall record (a vehicle campaign, an FDA enforcement entry, a CPSC recall notice, an FSIS recall or alert, a USCG campaign). "
        f"FDA enforcement reports are published in bulk from {FULL_COVERAGE_FROM}, so the chart starts there; earlier years hold mostly NHTSA, CPSC and USCG records back to {s['first_date'][:4]}. "
        f"{s['partial_year'][0]} is partial (to {s['last_date']}). The table shows the last {len(s['agency_years'])} years by agency."))

    # 2. by agency
    ba = s["by_agency"]
    charts["by-agency"] = svg_hbar(site, "Which agency issues the recalls", f"Share of {n(s['recalls'])} recalls, {s['first_date'][:4]} to {ly}",
                                   [(f"{a}", c, f"{p}%") for a, c, p, _, _ in ba], src_note)
    sections.append(section(
        site, "agencies", "Which agency issues the recalls",
        f"The {data('FDA')} accounts for <strong>{ba[0][2]}%</strong> of all recall records, {data(ba[1][0])} for {ba[1][2]}% and {data(ba[2][0])} for {ba[2][2]}%. "
        f"Food-safety recalls from {data('FSIS')} are the smallest feed at {next(p for a, _, p, _, _ in ba if a == 'FSIS')}%; "
        f"{next(p for a, h, _, p in s['top_hazard_by_agency'] if a == 'FSIS')}% of their classified hazards are microbial contamination.",
        figure(site, "by-agency", charts["by-agency"], "Which agency issues the recalls", f"{n(s['recalls'])} recalls"),
        table(["Agency", "Full name", "Recalls", "Share", "Earliest", "Latest"],
              [(a, AGENCY[a], n(c), f"{p}%", lo, hi) for a, c, p, lo, hi in ba], {2, 3}),
        "Each agency publishes in its own format and granularity: one NHTSA campaign can cover many makes and model years, while FDA files one enforcement "
        "entry per product lot, which inflates FDA's share relative to distinct events. Compare within an agency, not across."))

    # 3. hazards
    hz = s["hazards"]
    charts["hazards"] = svg_hbar(site, "What the recalls are for", f"Share of {n(s['hazard_classified'])} classified hazard assignments",
                                 [(nm, c, f"{p}%") for nm, _, c, p in hz], src_note, label_w=210)
    sections.append(section(
        site, "hazards", "What the recalls are for",
        f"{data(hz[0][0])} is the largest hazard class at <strong>{hz[0][3]}%</strong> of classified hazard assignments, "
        f"followed by {data(hz[1][0])} ({hz[1][3]}%) and {data(hz[2][0])} ({hz[2][3]}%). "
        f"{s['hazard_other_pct']}% of assignments are not yet mapped to the taxonomy and are excluded from the shares.",
        figure(site, "hazards", charts["hazards"], "What the recalls are for", f"{n(s['hazard_classified'])} classified assignments"),
        table(["Hazard class", "Definition", "Assignments", "Share"], [(nm, d, n(c), f"{p}%") for nm, d, c, p in hz], {2, 3})
        + f'<h3>Leading hazard per agency</h3>'
        + table(["Agency", "Leading hazard class", "Assignments", "Share of the agency's classified hazards"],
                [(a, h, n(c), f"{p}%") for a, h, c, p in s["top_hazard_by_agency"]], {2, 3}),
        f"Agency free-text hazard descriptions are mapped by a deterministic keyword table to {len(hz)} controlled classes; the original text is kept beside the class. "
        f"A recall can carry several classes. Denominator: {n(s['hazard_classified'])} of {n(s['hazard_rows'])} hazard assignments that map to a class."))

    # 4. FDA classification
    fc = s["fda_classes"]
    c1 = s["fda_class1_by_year"]
    charts["fda-class-i"] = svg_line(site, "Share of FDA recalls that are Class I", "Class I = reasonable probability of serious health consequences or death",
                                     [(str(y), p) for y, _, _, p in c1], lambda v: f"{v:g}%", src_note,
                                     peak_label=f"{max(c1, key=lambda t: t[3])[3]}% ({max(c1, key=lambda t: t[3])[0]})", last_label=f"{c1[-1][3]}%", right=72)
    class1 = next((p for k, _, p in fc if k == "Class I"), 0)
    sections.append(section(
        site, "fda-severity", "How serious FDA recalls are",
        f"<strong>{class1}%</strong> of the {n(s['fda_classified'])} classified FDA recalls are Class I, the most serious category. "
        f"The Class I share peaked at {max(c1, key=lambda t: t[3])[3]}% in {max(c1, key=lambda t: t[3])[0]} and was {c1[-1][3]}% in {c1[-1][0]}.",
        figure(site, "fda-class-i", charts["fda-class-i"], "Share of FDA recalls that are Class I", f"{n(sum(t for _, _, t, _ in c1))} classified FDA recalls, {c1[0][0]} to {c1[-1][0]}"),
        table(["Classification", "Recalls", "Share"], [(k, n(c), f"{p}%") for k, c, p in fc], {1, 2})
        + "<h3>Class I share by year</h3>"
        + table(["Year", "Class I", "All classified", "Class I share"], [(str(y), n(a), n(t), f"{p}%") for y, a, t, p in c1], {1, 2, 3}),
        "FDA assigns Class I, II or III to each enforcement entry (I: serious health consequences or death; II: temporary or reversible effects; III: unlikely to cause harm). "
        f"Only FDA rows with a class are counted; {ly} is excluded from the yearly series as a partial year."))

    # 5. units
    un = {u["agency"]: u for u in s["units"]}
    nh, cp = un.get("NHTSA"), un.get("CPSC")
    lg = s["largest"]
    charts["largest-recalls"] = svg_hbar(site, "The largest recalls by units affected", "Units reported by the issuing agency, top 10 on record",
                                         [(f"{a} · {d[:4]}", u, n(u)) for a, d, _, u in lg], src_note, label_w=110)
    sections.append(section(
        site, "units", "How many units a recall touches",
        f"NHTSA campaigns report the number of vehicles affected: <strong>{n(nh['total'])}</strong> vehicle-units across {n(nh['campaigns'])} campaigns, "
        f"a median of {n(nh['median'])} per campaign, with {nh['over_100k_pct']}% of campaigns above 100,000 units and {n(nh['over_1m'])} above one million. "
        f"CPSC recalls report {n(cp['total'])} units across {n(cp['campaigns'])} recalls, median {n(cp['median'])}. "
        f"The largest single recall on record is a {data(lg[0][0])} action from {lg[0][1][:4]} covering {n(lg[0][3])} units.",
        figure(site, "largest-recalls", charts["largest-recalls"], "The largest recalls by units affected", "top 10 by reported units"),
        table(["Agency", "Date", "Recall", "Units affected"], [(a, d, t, n(u)) for a, d, t, u in lg], {3})
        + "<h3>Units by agency</h3>"
        + table(["Agency", "Recalls with units", "Total units", "Median units", "Over 100k", "Over 1M"],
                [(u["agency"], n(u["campaigns"]), n(u["total"]), n(u["median"]), f"{n(u['over_100k'])} ({u['over_100k_pct']}%)", n(u["over_1m"])) for u in s["units"]], {1, 2, 3, 4, 5}),
        "Only CPSC and NHTSA publish a units-affected figure; FDA, FSIS and USCG records carry none, and RecallDB leaves those blank rather than estimating. "
        "Units are the agency's own figure at the time of the notice (vehicles for NHTSA, product units for CPSC) and may be revised later in the source."))

    # 6. vehicle model years
    my = s["model_years"]
    top_my = max(my, key=lambda t: t[1])
    charts["vehicle-model-years"] = svg_line(site, "Vehicle model years with the most recall entries", "NHTSA recall entries (make, model and model year) per model year",
                                             [(str(y), v) for y, v in my], lambda v: n(v), src_note,
                                             peak_label=f"{n(top_my[1])} ({top_my[0]})", last_label=n(my[-1][1]), right=80)
    sections.append(section(
        site, "model-years", "Which vehicle model years get recalled most",
        f"Model year <strong>{top_my[0]}</strong> carries the most recall entries, {n(top_my[1])}, of the {n(s['model_year_rows'])} NHTSA make-model-year entries with a model year. "
        f"Recent model years are still accumulating recalls, so {ly} and {ly - 1} will keep rising.",
        figure(site, "vehicle-model-years", charts["vehicle-model-years"], "Vehicle model years with the most recall entries", f"{n(s['model_year_rows'])} entries, model years {my[0][0]} to {my[-1][0]}"),
        table(["Model year", "Recall entries"], [(str(y), n(v)) for y, v in my], {1}),
        f"An NHTSA campaign lists every make, model and model year it covers; RecallDB stores each as one entry ({s['products_per_nhtsa_recall']} per campaign on average), "
        f"so this counts how often a model year appears in recall campaigns, not distinct vehicles or distinct campaigns."))

    # 7. timing
    bm = s["by_month"]
    bw = s["by_weekday"]
    top_m = max(bm, key=lambda t: t[1]); low_m = min(bm, key=lambda t: t[1])
    top_w = max(bw, key=lambda t: t[1])
    charts["by-month"] = svg_hbar(site, "Recalls by month of the year", f"{n(s['timing_n'])} recalls, {s['timing_years'][0]} to {s['timing_years'][1]}",
                                  [(m, v, n(v)) for m, v in bm], src_note, label_w=80)
    charts["by-weekday"] = svg_hbar(site, "Recalls by day of the week", f"{n(s['timing_n'])} recalls, {s['timing_years'][0]} to {s['timing_years'][1]}",
                                    [(d, v, n(v)) for d, v in bw], src_note, label_w=110)
    weekend = sum(v for d, v in bw if d in ("Saturday", "Sunday"))
    sections.append(section(
        site, "timing", "When recalls are announced",
        f"<strong>{data(top_m[0])}</strong> is the busiest recall month with {n(top_m[1])} recalls over the period, {round(top_m[1] / low_m[1], 2)} times {data(low_m[0])}, the quietest. "
        f"<strong>{data(top_w[0])}</strong> is the busiest weekday; only {pct(weekend, s['timing_n'])}% of recalls are dated on a weekend.",
        figure(site, "by-month", charts["by-month"], "Recalls by month of the year", f"{n(s['timing_n'])} recalls")
        + figure(site, "by-weekday", charts["by-weekday"], "Recalls by day of the week", f"{n(s['timing_n'])} recalls"),
        table(["Month", "Recalls"], [(m, n(v)) for m, v in bm], {1}) + "<h3>By weekday</h3>" + table(["Weekday", "Recalls"], [(d, n(v)) for d, v in bw], {1}),
        f"Whole calendar years {s['timing_years'][0]} to {s['timing_years'][1]} only, all agencies, using each record's official recall date. "
        f"FDA dates are the recall initiation date reported by the firm, which is why some fall on weekends."))

    # 8. firms
    tf = s["top_firms"]
    charts["top-firms"] = svg_hbar(site, "Firms with the most recall records", f"Recalls attributed to the recalling firm, all agencies, {s['first_date'][:4]} to {ly}",
                                   [((nm[:31].rstrip() + "…") if len(nm) > 32 else nm, c, n(c)) for nm, c, _ in tf], src_note, label_w=250)
    sections.append(section(
        site, "firms", "Firms with the most recall records",
        f"{data(tf[0][0])} has the most recall records on file with <strong>{n(tf[0][1])}</strong>, ahead of {data(tf[1][0])} ({n(tf[1][1])}) and {data(tf[2][0])} ({n(tf[2][1])}). "
        f"Vehicle makers lead because NHTSA files one campaign per defect across a whole fleet; medical-device makers follow because FDA files one entry per affected lot.",
        figure(site, "top-firms", charts["top-firms"], "Firms with the most recall records", f"top 15 of {n(s['firms'])} recalling firms"),
        table(["Recalling firm", "Recalls", "Agencies"], [(nm, n(c), a) for nm, c, a in tf], {1}),
        "Firm names are as recorded by the issuing agency, with spelling variants merged by a deterministic rule; subsidiaries and regional entities of one corporation stay separate, "
        "so a group's true total can be higher. A high count reflects fleet size and filing conventions as much as product quality."))

    adv = s["nhtsa_advisories"]
    contents = toc([("per-year", "Recalls per year"), ("agencies", "Recalls by agency"), ("hazards", "Hazard classes"),
                    ("fda-severity", "FDA severity"), ("units", "Units affected and the largest recalls"), ("model-years", "Vehicle model years"),
                    ("timing", "Months and weekdays"), ("firms", "Firms with the most recalls"), ("method", "Method, reuse and citation")])
    tile_html = tiles([("Official recalls", n(s["recalls"])), ("Recalled products", n(s["products"])), ("Recalling firms", n(s["firms"])),
                       ("Agencies", "5"), ("Records from", s["first_date"][:4]), ("Snapshot", snap)], date_labels=("Snapshot", "Records from"))
    title_tag = f"U.S. Product Recall Statistics {snap[:4]} — Recalls per Year, Agencies, Hazards | RecallDB"
    desc = (f"U.S. product recalls in numbers: {n(s['recalls'])} official recalls from CPSC, FDA, FSIS, NHTSA and USCG. Recalls per year, agency shares, "
            f"hazard classes, FDA Class I share, largest recalls by units, vehicle model years, busiest months. Free to cite and embed.")
    ld = article_ld(site, "U.S. product recalls in numbers: statistics from the RecallDB ledger", desc, FIRST_PUBLISHED,
                    f"{site.base_url}/assets/og-image.png", ["product recalls", "CPSC", "FDA", "NHTSA", "FSIS", "product safety"])
    header = chrome()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title_tag)}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{site.page_url}">
  <link rel="alternate" hreflang="en" href="{site.page_url}">
  <meta property="og:title" content="U.S. product recalls in numbers — RecallDB statistics {snap[:4]}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{site.page_url}">
  <meta property="og:image" content="{site.base_url}/assets/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="theme-color" content="#0b1117">
  <link rel="manifest" href="../site.webmanifest">
  <link rel="stylesheet" href="../index.css">
{ld}
  <style>{CSS}{STATS_CSS}  </style>
</head>
<body>
{header}<main class="stats-wrap">
  <p class="crumb"><a href="/">Home</a> &rsaquo; <span>Statistics</span></p>
  <p class="eyebrow">Market statistics · snapshot {esc(snap)}</p>
  <h1>U.S. product recalls in numbers</h1>
  <p class="lede">Aggregate statistics computed from the full RecallDB ledger: {n(s['recalls'])} official recalls and {n(s['products'])} recalled products joined from the five federal recall feeds (CPSC, FDA, FSIS, NHTSA, USCG), every row carrying its agency ID, source URL and retrieval time. Every figure is free to cite, quote and embed with a link to this page.</p>
  <ul class="tiles">{tile_html}</ul>
  <nav class="toc" aria-label="Contents"><strong>On this page</strong><ol>{contents}</ol></nav>

{"".join(sections)}

  <section class="stat" id="method">
    <h2>Method, reuse and citation</h2>
    <ul class="method">
      <li><strong>Source.</strong> The full RecallDB snapshot of {snap}: {n(s['recalls'])} recall records pulled from the CPSC SaferProducts API, NHTSA's recall flat file, openFDA enforcement reports plus FDA Safety Alerts, the USDA FSIS recall API and the USCG recall list. All five are U.S. federal publications in the public domain. Every row keeps the agency's own ID, record URL, retrieval timestamp and raw-payload fingerprint; see <a href="/SOURCES.md">Sources</a>.</li>
      <li><strong>Nothing is estimated.</strong> Units, classifications, dates and firm names are the agency's own values; where an agency publishes no value the field is blank and excluded from the figure's denominator, which every section states.</li>
      <li><strong>Agencies are not directly comparable.</strong> One NHTSA campaign covers a fleet; FDA files one entry per lot; CPSC one notice per product. Counts describe records, not distinct safety events.</li>
      <li><strong>Refresh.</strong> RecallDB is refreshed on a manual cadence; this page and its charts are regenerated with each snapshot, so figures move. Cite the snapshot date. {("NHTSA has flagged " + n(adv['do_not_drive']) + " campaigns as do-not-drive and " + n(adv['park_outside']) + " as park-outside since " + adv['since'][:4] + ".") if adv.get('since') else ""}</li>
      <li><strong>Reuse.</strong> The figures and charts on this page are published under <a href="https://creativecommons.org/licenses/by/4.0/" rel="license">CC BY 4.0</a>: use them in articles, slides and posts with a link to <span translate="no">{site.page_url}</span>. The machine-readable version is <a href="/stats/data.json">data.json</a>. The underlying row-level ledger is a separate <a href="/#pricing">commercial product</a>; a free 200-row sample is in the <a href="https://github.com/RecallDB-public/RecallDB-public">public repository</a>.</li>
      <li><strong>Suggested citation.</strong> <span translate="no">RecallDB ({snap[:4]}). <em>U.S. product recalls in numbers</em>, snapshot {snap}. DataEngineered. {site.page_url}</span></li>
      <li><strong>Questions or corrections:</strong> <a href="/#contact">contact form</a> or recalldb@dataengineered.io.</li>
    </ul>
  </section>

  <div class="cta-inline">
    <h3 style="margin:0">Need the row-level ledger behind these numbers?</h3>
    <p>Every recall with its agency ID, source URL, hazard classes, products, lots and firms, as CSV and SQLite with the provenance ledger.</p>
    <a class="button primary" href="/#pricing">Get the full dataset ($49)</a>
  </div>
</main>
<footer><div class="catalog-line" style="text-align:center; margin-top:14px; font-size:0.85rem; opacity:0.85;"><a href="https://dataengineered.io/">Part of the DataEngineered catalog &rarr;</a> &middot; <a href="https://dataengineered.io/about">About</a> &middot; <a href="https://dataengineered.io/terms">Terms</a> &middot; <a href="https://dataengineered.io/privacy">Privacy</a> &middot; <a href="https://dataengineered.io/refund-policy">Refund policy</a></div></footer>
{COPY_JS}
</body>
</html>
"""


def build_data_json(s):
    return {
        "dataset": SITE.brand, "page": SITE.page_url, "generated": dt.date.today().isoformat(), "snapshot": s["snapshot_date"],
        "license": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) - attribute with a link to the page; source records are U.S. federal public domain",
        "totals": {k: s[k] for k in ("recalls", "products", "firms", "first_date", "last_date")},
        "recalls_per_year": {"full_coverage_from": FULL_COVERAGE_FROM, "mean_per_year": s["mean_per_year"],
                             "years": [dict(year=y, recalls=v) for y, v in s["per_year"]],
                             "partial_year": dict(year=s["partial_year"][0], recalls=s["partial_year"][1], through=s["last_date"]),
                             "by_agency_last_years": [dict(year=y, **d) for y, d in s["agency_years"]]},
        "by_agency": [dict(agency=a, full_name=AGENCY[a], recalls=c, share_pct=p, earliest=lo, latest=hi) for a, c, p, lo, hi in s["by_agency"]],
        "hazards": {"classified_assignments": s["hazard_classified"], "unmapped_assignments": s["hazard_other"], "unmapped_pct": s["hazard_other_pct"],
                    "classes": [dict(hazard=nm, definition=d, assignments=c, share_pct=p) for nm, d, c, p in s["hazards"]],
                    "leading_by_agency": [dict(agency=a, hazard=h, assignments=c, share_pct=p) for a, h, c, p in s["top_hazard_by_agency"]]},
        "fda_classification": {"classified": s["fda_classified"], "classes": [dict(classification=k, recalls=c, share_pct=p) for k, c, p in s["fda_classes"]],
                               "class_i_share_by_year": [dict(year=y, class_i=a, classified=t, share_pct=p) for y, a, t, p in s["fda_class1_by_year"]]},
        "units_affected": {"by_agency": s["units"], "largest": [dict(agency=a, date=d, title=t, units=u) for a, d, t, u in s["largest"]]},
        "vehicle_model_years": {"entries_with_model_year": s["model_year_rows"], "entries_per_nhtsa_campaign": s["products_per_nhtsa_recall"],
                                "rows": [dict(model_year=y, entries=v) for y, v in s["model_years"]]},
        "timing": {"years": list(s["timing_years"]), "recalls": s["timing_n"], "by_month": [dict(month=m, recalls=v) for m, v in s["by_month"]],
                   "by_weekday": [dict(weekday=d, recalls=v) for d, v in s["by_weekday"]]},
        "top_firms": [dict(firm=nm, recalls=c, agencies=a) for nm, c, a in s["top_firms"]],
        "nhtsa_advisories": s["nhtsa_advisories"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.environ.get("RECALLDB_SQLITE", str(DEFAULT_DB)))
    args = ap.parse_args()
    db = Path(args.db)
    if not db.is_file():
        raise SystemExit(f"SQLite snapshot not found: {db}")
    s = compute(db)
    charts = {}
    page = build_page(s, charts)
    write_outputs(OUT_DIR, page, charts, build_data_json(s))
    print(f"stats/index.html + {len(charts)} charts + data.json  (snapshot {s['snapshot_date']}, {s['recalls']:,} recalls)")


if __name__ == "__main__":
    main()
