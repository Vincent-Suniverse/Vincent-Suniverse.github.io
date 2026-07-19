# CLAUDE.md

Guidance for AI assistants (and humans) working in this repository.

> Content is primarily in **German**. Preserve the existing language in page
> copy unless explicitly asked to translate.

## What this is

The personal GitHub Pages site for **Vincent / "Chaos ex Ordo"** — an artist and
author of the **3-6-9 Universal Neutrality Framework**. It is a set of
**hand-written, standalone static HTML pages**: a landing/linktree plus a
collection of interactive, animated pages that illustrate ideas from the
framework (`V̂ = π⁴ + π³ + π`, the 3-6-9 field, number-theoretic patterns).

There is **no build step, no framework, no bundler, no package manager**. Each
`.html` file is self-contained: inline `<style>` and inline `<script>`, vanilla
JS and Canvas/SVG. Editing a page means editing that one file.

## Deployment

- Served by **GitHub Pages** directly from the repository root of the default
  branch (`main`). Pushing to `main` publishes; there is no CI/build.
- The live URL is the GitHub Pages domain for this repo.
- Because there is no build, **what you see in the file is exactly what ships.**
  Test by opening the HTML file in a browser.

## Pages and how they connect

```
index.html    Landing / linktree ("Chaos ex Ordo"). Hub for external links
              (Spotify, Instagram, X, Telegram, GitHub, Zenodo) and → feld.html
feld.html     The main "3-6-9 Feld" — interactive multi-node field; links to
              index / fau / spielfeld
spielfeld.html   "Das Feld · 3—6—9" — index of the animated node pages below
fau.html      "FAU — Freedom · Anarchy · Union"

Animated node pages (opened from spielfeld.html):
  anim_1008.html            1008 = 846 + 162 (the frame)
  anim_142857.html          142857 — the cycle of sevenths
  anim_3plus4.html          The 3+4 fraction
  anim_alpha_beta_gamma.html α · β · γ — the π-stream (integer spigot)
  anim_antarktis_these.html  Earthquake chain 25.6.2026 — fact & thesis
```

Navigation is a small manual web of relative `href="*.html"` links — there is no
router or shared nav component. If you add a page, wire its links by hand
(typically add it to `spielfeld.html` and give it a back-link).

## Conventions

- **One file per page, everything inlined.** Keep CSS in the page's `<style>`
  and JS in the page's `<script>`. Do not introduce shared external `.css`/`.js`
  assets or a build tool — the project's whole model is self-contained pages.
- **Shared visual language.** Pages use a consistent palette defined as CSS
  custom properties on `:root` (deep warm backgrounds, `--gold`, `--red`,
  `--teal`, `--cream`) and serif typography (Palatino / Cormorant Garamond via
  Google Fonts). Match the existing look when adding or editing pages; copy the
  `:root` block from a nearby page as a starting point.
- **External dependencies** are limited to Google Fonts `<link>`s on some pages.
  Avoid adding CDN scripts unless a page genuinely needs one.
- **Responsive.** Pages set `overflow-x: hidden` and target mobile; recent
  commits were mobile-layout fixes (text panels overlapping nav on narrow
  screens). Check narrow/short viewports when touching layout.
- Keep German page copy and the framework's notation/vocabulary intact.

## Related repositories

Part of the same project family:
- `universal-neutrality-framework` — the written framework + a public linktree
  page and the CEXO chatbot.
- `cexo-engine` — the private deterministic engine ("the Orca").
- `Public-project` — the UVB-76 transmission database
  (`/public-project/` Pages site).

## Gitignore

`__pycache__/`, `*.pyc`, `sphere_state.json`, `cache/` — leftovers from
engine experiments; the site itself has no such runtime artifacts.
