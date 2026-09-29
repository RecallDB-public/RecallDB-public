// Old Cloudflare Pages host -> canonical domain. Exact-host match so branch-preview
// hosts and the custom domain are never redirected; everything else falls through
// to the static assets (404.html, _headers, _redirects unchanged).
const OLD_HOST = "recalldb-public.pages.dev";
const NEW_HOST = "recalldb.dataengineered.io";

// Repo-only files. Pages serves the whole repository root, so without this the
// translation catalogs, the build scripts, their config, the README and dotfiles
// would be downloadable from the site. They get the site's normal 404 instead
// (they stay in the GitHub repository).
const REPO_ONLY_PREFIXES = ["/locales/", "/scripts/"];
const REPO_ONLY_FILES = new Set(["/i18n.config.json", "/readme.md", "/vercel.json", "/requirements.txt"]);

// Images deleted from the repository (2026-09-29, replaced by the count-free -v2 files).
// Pages still answered them with the old bytes from a cache that a zone purge does not
// reach (they were served as immutable for a year), so they are refused here instead.
const RETIRED_FILES = new Set(["/assets/og-image.png", "/assets/recalldb-hero.png"]);

// Matched on the decoded, slash-collapsed, lower-cased path, because the asset
// server also answers /locales%2Fes.json and //locales/es.json.
function isRepoOnly(pathname) {
  let path;
  try {
    path = decodeURIComponent(pathname);
  } catch {
    return true; // malformed escapes never name a real page
  }
  path = path.replace(/\/{2,}/g, "/").toLowerCase();
  if (REPO_ONLY_FILES.has(path) || RETIRED_FILES.has(path)) return true;
  if (REPO_ONLY_PREFIXES.some((prefix) => path.startsWith(prefix))) return true;
  // dotfiles and dot-segments (.gitignore, .github/, ..), but keep /.well-known/ usable
  return path.split("/").some((seg) => seg.startsWith(".") && seg !== ".well-known");
}

export async function onRequest({ request, env, next }) {
  const url = new URL(request.url);
  if (url.hostname === OLD_HOST) {
    url.hostname = NEW_HOST;
    return Response.redirect(url.toString(), 301);
  }
  if (isRepoOnly(url.pathname)) {
    // A path that cannot exist makes Pages answer with 404.html, as for any unknown URL.
    const missing = await env.ASSETS.fetch(new URL("/__not_found__", url).toString());
    return new Response(missing.body, { status: 404, headers: missing.headers });
  }
  return next();
}
