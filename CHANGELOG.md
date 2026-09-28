# Changelog

## Site update — 2026-09-29

- **USCG hazards, stated as they are**: the homepage's Hazards section (all five languages) said that USCG boating defects map into the hazard taxonomy. In the 2026.09 edition none do. uscgboating.org has blanked the "Problem" defect text on both its recall list and its detail pages: the text was still there in the Internet Archive capture of 2026-08-04 and was blank in the 2026-09-18 crawl. So all 1,693 USCG recalls have an empty `description` and no `recall_hazards` row. The section now names the four agencies whose text is mapped, and says that USCG recalls are included but carry no hazard class. The replaced sentence was pruned from `locales/*.json` (2026-09-29).

## Site update — 2026-09-28

- **Repository files off the website**: the translation catalogs (`/locales/`), the build scripts (`/scripts/`), `i18n.config.json`, `README.md` and the dotfiles belong to this repository, not to the website, but the site served them as plain files. They now answer the site's normal 404 page (also when requested as `/locales%2Fes.json` or `//locales/es.json`) and stay available here on GitHub. Pages, data files, samples, `llms.txt` and the sitemap are unchanged (2026-09-28).
- **Chart titles on `/stats/`**: every chart's built-in title and description (what a screen reader announces for the chart) used the same two ids, `t` and `d`, repeated once per chart, so the page had duplicate ids and every chart was announced with the first chart's title. The ids now carry the chart's name (`t-recalls-per-year` / `d-recalls-per-year`, and so on) on the page and in the downloadable SVGs under `/stats/charts/`. `scripts/stats_common.py` is the current portfolio copy, which writes them on the next regeneration; the committed page and SVGs were patched to exactly what it writes, without regenerating (no figure, date or `data.json` changes).
- **Counts match the edition buyers receive**: the homepage, README, llms.txt, the 11 hazard and 5 agency pages (all five languages) and the Kaggle sample files now state the counts of the 2026.09 full snapshot on the delivery release, rebuilt by the monthly refresh on 2026-09-20: 128,936 recalls and 294,683 recalled products; per agency CPSC 8,304, FDA 87,387 (87,314 openFDA enforcement reports + 73 FDA Safety Alerts), FSIS 1,236, NHTSA 30,316 and USCG 1,693; 21,054 firms; 519 source pulls; a 384 MB full snapshot. The agency cards, hazard bars, hazard pages and the "All N official recalls" band still showed the July launch figures (127,783 recalls), the headline those of a 2026-09-18 local build (128,933). /stats/ keeps describing that 2026-09-18 build (3 recalls and 3 products fewer) until its next regeneration. `samples/hazards.csv` is now the snapshot's own `csv/hazards.csv` (2026-09-28).
- **claims.json and a claims check**: `/claims.json` records the edition's counts in one place (recalls, products, per agency, per hazard, firms, source pulls, ZIP size, snapshot date). `python scripts/check_claims.py` exits 1 when any hand-written count on the site, README, llms.txt, Kaggle files or `samples/hazards.csv` disagrees with it, and also flags generated pages that were not rebuilt; `--fix` rewrites the hand-written ones and `--fix --claims PATH` adopts a newer edition's claims file (2026-09-28).
- **Release files stay out of the repository**: `.gitignore` now ignores the private files that the monthly claims re-sync downloads into this folder: `recalldb-claims-*.json`, `recalldb-snapshot-*.zip`, the extracted `sqlite/` folder and any `*.sqlite` file, plus the snapshot's full `csv/` tables in case the whole ZIP is extracted here. No tracked file matches these patterns, and no page changes (2026-09-28).

## Site update — 2026-09-27

- **Translated Dataset markup**: on the Spanish, German, French and Portuguese pages the Dataset structured data now names its English original in `sameAs` (next to any existing `sameAs` links), so dataset search can tie the language copies to one canonical entry. English pages and all visible text are unchanged (2026-09-27).
- **Section links**: links to a section (`#pricing`, `#contact`, `#sample`, a /stats/ chart) no longer land with the heading hidden under the sticky header (79 px on desktop, about 180 px on phones, where the header stacks). The homepage (all five languages) and /stats/ carry the shared section-links snippet (`scripts/section_links.py`): the jump offset follows the header's live height, and an arrival from another page is realigned once the sample preview rows, which load after the page, have moved it (`app.js` calls `realignSectionLink()` after the preview renders; cache key `?v=section-links-20260927`). The "Embed this chart" snippets on /stats/ now link `#fig-<slug>` (the chart's own id); 8 of the 9 pointed at ids that did not exist. `scripts/stats_common.py` is synced with the portfolio copy, so a regeneration keeps both. Visible text, figures and dates are unchanged (2026-09-27).

## Site update — 2026-09-20

- **Sale attribution**: every Stripe buy link carries `?client_reference_id=<brand>_<lang>_<surface>` (`home` / `landing`); the i18n build swaps the language token per locale and the delivery worker prints the id in the order email. Stripe does not store UTM parameters, so this is the only per-page attribution that reaches the order record (2026-09-20).

## 2026.07.14

- Added inline sending and success feedback for enterprise custom request submissions.
- Routed the enterprise custom request form through the delivery Worker and Web3Forms for direct email delivery.
- Wired the $49 snapshot tier to Stripe checkout: https://buy.stripe.com/aFacN69Jm2MK8rN5Uk38408
- Converted the $99+ enterprise tier into a freeform custom request email flow.
- Added paid full-dataset access tiers: $49 snapshot and $99+ enterprise custom request.
- Wired dataset requests to recalldb@dataengineered.io and clarified that full exports are privately delivered, not public downloads.
- Initial public RecallDB sample repository.
- Includes static SEO landing page, public sample CSVs, source documentation, Kaggle metadata and starter notebook.
- Sample derived from the v1 expanded RecallDB export with CPSC, FDA, FSIS, NHTSA and USCG coverage.
