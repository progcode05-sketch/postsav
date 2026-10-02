# SEO and GEO runbook

How the site is built to be found by search engines (SEO) and recommended by AI assistants (GEO), what is automated, and what only a person with the right accounts can do. Written 2026-10-03.

## 1. What people search, and the page that answers it

Autocomplete data from Google and Bing (2026-10-03) shows people search **platform + media type + "downloader"**, not generic brand words. Each platform therefore has its own page, and the home page targets the umbrella terms.

| Page | Primary queries (seen in autocomplete) |
|---|---|
| `/` | instagram linkedin pinterest downloader, social media post downloader |
| `/linkedin-downloader` | linkedin carousel downloader (free, online, post, image), download linkedin carousel (pdf, images), linkedin post / video / image downloader, linkedin document downloader |
| `/pinterest-downloader` | pinterest video downloader (online, free, link, hd), pinterest image downloader, pin.it downloader, download pinterest video from link, download pinterest image full size |
| `/instagram-downloader` | instagram reel downloader (online, free, link), instagram photo downloader, instagram carousel downloader |
| `/about` | brand and trust queries, "how does PostSav work" |

Competition (search results checked 2026-10-03): **LinkedIn carousel** results are mostly small tools and tutorials (winnable, and the site's strongest feature); **Pinterest** is crowded with mid-size dedicated tools; **Instagram** is dominated by large, long-established sites. Expect LinkedIn and Pinterest long-tail queries to respond first. Nobody can promise a top ranking: new sites usually need weeks to be indexed and months to rank, and a free `onrender.com` subdomain carries little authority.

## 2. Brand name

Recommended: **PostSav**. It is a unique token (clean for search and for AI entity recognition), contains no Instagram/LinkedIn/Pinterest trademarks, is the name of the GitHub repo, and the `postsav` domains in `.com`, `.app`, `.io`, `.net`, `.co` and `.me` showed no registration on 2026-10-03 (RDAP). Rejected: *PostSave* (an existing social-content product uses it, and `post_save` is a Django signal), *Savelo* (existing apps), *CatchPost* / *PullPost* (hardware noise), anything containing "Insta", "Pin" or "Linked" (trademark and platform-policy risk).

Change it with one setting: `SITE_NAME=Other Name`. All titles, schema, `llms.txt` and legal pages follow. The favicon set and the social card are images: edit `tools/og-image.html` if the name changes, then run `python tools/make_og_image.py` (needs Chrome or Edge) and `python tools/make_icons.py`.

## 3. What is implemented

**Crawlability and indexing**
- `robots.txt` welcomes Googlebot, Bingbot and the AI crawlers (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, PerplexityBot, Perplexity-User, Google-Extended, Applebot(-Extended), DuckDuckBot, DuckAssistBot, MistralAI-User, Amazonbot, Meta-ExternalAgent, CCBot). `/api/`, `/healthz`, `/readyz` are disallowed in every group and also send `X-Robots-Tag: noindex, nofollow`.
- `sitemap.xml` (absolute URLs, accurate `lastmod`), linked from `robots.txt`.
- Canonical tags on every page; 301 from trailing-slash URLs and, when `SITE_URL` is set, from any other host (health checks excluded). Friendly `noindex` 404 page.
- ETag and `Cache-Control` on pages (conditional requests return 304), hashed CSS/JS URLs, 7-day static caching.

**On-page**
- One H1 per page containing the target phrase, titles at most 60 characters, descriptions 70-160 characters, all unique (enforced by tests).
- Definition paragraph first, then a key-facts block, step-by-step guide, tables, FAQ with natural-language questions, and cited official sources. Visible "last updated" dates.
- Open Graph and Twitter cards with a 1200 x 630 image, favicon set (ICO, SVG, PNG, Apple touch icon), web manifest.
- Breadcrumbs (visible and in schema), descriptive internal links from every page, no orphan pages.

**Structured data (JSON-LD, generated from the same data as the visible text)**
- `Organization`, `WebSite`, `WebApplication` (free offer), `WebPage` / `AboutPage` / `ContactPage`, `BreadcrumbList`, `FAQPage`, `HowTo`. No ratings or reviews are ever invented.

**GEO (AI assistants)**
- `llms.txt` (summary and key links), `llms-full.txt` (every page as markdown), `pricing.md` (free, with limits), `/.well-known/security.txt`.
- Answer-first copy, first-party dated test results ("17 of 17 real public post links, 2 October 2026"), comparison tables, authoritative outbound links to Instagram, LinkedIn and Pinterest help pages and terms.
- IndexNow key file and `indexnow.py` so Bing (which feeds Copilot and ChatGPT search) learns about changes quickly.

## 4. Settings

| Variable | Purpose |
|---|---|
| `SITE_URL` | Canonical origin, e.g. `https://postsav.com`. Used in canonical tags, sitemap, schema and `llms.txt`. When set, other hosts 301 to it. Falls back to Render's `RENDER_EXTERNAL_URL`, then to the request's own origin. |
| `SITE_NAME` | Brand name (default `PostSav`). |
| `GITHUB_URL` | Source repository linked from the footer and `sameAs`. |
| `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION` | Content of the verification meta tags from Search Console / Bing Webmaster Tools. |
| `INDEXNOW_KEY` | Override the IndexNow key (default is built in; the key is public by design). |
| `CONTACT_EMAIL` | Shown on the contact page, in `security.txt` and in the Organization schema. |

## 5. After every deploy

1. `python verify_seo.py https://your-site.example --external` (crawler files, per-page metadata, schema, outbound link status).
2. `python indexnow.py https://your-site.example` to notify Bing and other IndexNow engines.
3. Open the page in a private window and check the title, favicon and share preview.

## 6. One-time actions that need your accounts

1. **Google Search Console** (search.google.com/search-console): add a URL-prefix property, choose the HTML tag method, put the token in `GOOGLE_SITE_VERIFICATION`, redeploy, verify, then submit `sitemap.xml` and request indexing for the five main pages.
2. **Bing Webmaster Tools** (bing.com/webmasters): add the site (or import from Search Console), put the token in `BING_SITE_VERIFICATION`, submit the sitemap. Bing's index feeds Copilot and ChatGPT search, so this matters for GEO.
3. **Brave Search** (the index Claude's web search uses): there is no console. Search `site:your-site.example` at search.brave.com after a week or two to confirm the pages are present.
4. **Keep the service awake.** Render serves `Disallow: /` for `robots.txt` while a free service is asleep, which can make crawlers drop pages. Keep the uptime monitor on `/healthz` (every 5 minutes) running, and avoid redeploys during the day when you can.

## 7. Custom domain (recommended, not free)

A brandable domain is the biggest single authority and trust upgrade. Registering `postsav.com` (or `.app`) costs roughly the price of a coffee per year. Render supports custom domains with managed TLS on the free plan.

1. Register the domain at any registrar.
2. Render dashboard, the service, **Settings > Custom Domains**, add `postsav.com` and `www.postsav.com`, then create the DNS records Render shows.
3. Set `SITE_URL=https://postsav.com` in the service's environment. The old `onrender.com` host then 301-redirects to the new one (health checks excepted) and every canonical URL, the sitemap, schema and `llms.txt` switch automatically.
4. Add the new domain to Search Console (DNS verification is available for domains) and Bing, resubmit the sitemap, and run `indexnow.py`.
5. Regenerate the social card (`python tools/make_og_image.py`) only if the brand name changed.

## 8. Monthly routine (freshness matters: ChatGPT cites recently updated pages far more often)

1. Re-run `python verify_live.py` and `python verify_seo.py`, then update `UPDATED`, `TESTED_ON` and the "17 of 17" figures in `site_content.py` (a test checks the counts against `verify_live.py`).
2. Add a row to "Recent changes" on `/about` whenever something user-visible changes.
3. Run the AI visibility check below and log the results in a spreadsheet.

**Queries to check in ChatGPT, Perplexity, Google (AI Overviews), Gemini, Copilot and Claude**

1. best LinkedIn carousel downloader
2. how to download a LinkedIn carousel as images
3. can you download a LinkedIn carousel as a PDF
4. LinkedIn video downloader online free
5. how to download a Pinterest video from a pin.it link
6. Pinterest image downloader original size
7. download Pinterest video with sound
8. free Instagram Reel downloader no login
9. how to download Instagram carousel photos
10. tool to download Instagram, LinkedIn and Pinterest posts
11. is there a free social media post downloader
12. PostSav
13. is PostSav safe
14. lnkd.in link downloader
15. how to save LinkedIn document post slides
16. best Pinterest downloader without watermark
17. download images from a LinkedIn post
18. how to copy a LinkedIn post link
19. why does my Pinterest video download have no sound
20. download all slides of a LinkedIn carousel as a ZIP

Record whether PostSav is cited, which page, and who is cited instead. Examine the winners' structure and freshness, then improve the matching page.

## 9. Third-party presence (AI assistants cite where you appear, not only your own site)

Done by a person, honestly and without spam: a short "Show HN" or Product Hunt launch; helpful answers (with disclosure) on Reddit and Quora threads about downloading LinkedIn carousels or Pinterest videos; listings on AlternativeTo and SaaSHub; a dev.to or LinkedIn write-up of the technical approach; the GitHub repo with a clear description, website URL and topics. Brands are far more likely to be cited through third-party mentions than through their own domain.

## 10. Do not

- Invent ratings, reviews or user counts, or mark up content that is not visible on the page.
- Repeat keywords unnaturally (keyword stuffing lowers AI visibility); a test caps density.
- Create near-duplicate "doorway" pages for every keyword variation. Add a page only when it holds genuinely different, useful content.
- Claim support that was not tested (stories, boards, private accounts, 4K).
- Block AI crawlers and then expect to be cited.

## 11. Measured results (Lighthouse 12, mobile emulation, Edge)

| | Performance | Accessibility | Best practices | SEO |
|---|---|---|---|---|
| Live site before (2026-10-03) | 98 | 100 | 96 (favicon 404 console error) | 100 |
| New pages, local build (home and LinkedIn) | 100 | 100 | 100 | 100 |

Lighthouse's SEO score only checks basics (title, description, crawlability). The real gains are the items in section 3, which it does not measure; `test_seo.py` and `verify_seo.py` cover them.
