# Changelog

## Site update — 2026-09-28

- **Repository files off the website**: the translation catalogs (`/locales/`), the build scripts (`/scripts/`), `i18n.config.json`, `README.md` and the dotfiles belong to this repository, not to the website, but the site served them as plain files. They now answer the site's normal 404 page (also when requested as `/locales%2Fes.json` or `//locales/es.json`) and stay available here on GitHub. Pages, data files, samples, `llms.txt` and the sitemap are unchanged (2026-09-28).

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
