# PostSav: free Instagram, LinkedIn & Pinterest post downloader

**Live site:** https://social-downloader-75g8.onrender.com. Paste the link of a public Instagram, LinkedIn or Pinterest post and download its images, videos and carousel slides, one by one or as a ZIP. No account, no watermark, and files are deleted when the transfer ends. Platform guides: [LinkedIn carousel, video and image downloader](https://social-downloader-75g8.onrender.com/linkedin-downloader), [Pinterest video and image downloader (pin.it)](https://social-downloader-75g8.onrender.com/pinterest-downloader), [Instagram Reel, photo and carousel downloader](https://social-downloader-75g8.onrender.com/instagram-downloader).

A local Flask website for downloading available post attachments. Start it with `start-windows.bat` or `start-mac-linux.sh`. The launcher installs dependencies automatically and opens the browser after the server responds; Python 3.10+ is required. Optional ffmpeg enables merging separate video/audio streams.

## Use

1. Paste an Instagram reel/post URL, a LinkedIn post URL or a Pinterest pin URL (`pin.it` and `lnkd.in` share links work too).
2. Check the attachment previews.
3. Download an individual image/video, or choose **Download all · ZIP** for multiple attachments.

LinkedIn document carousels are offered as numbered slide images. A PDF option appears only when the source explicitly permits document download. LinkedIn may require sign-in for the original PDF even when its slides are publicly visible. The app does not bypass that restriction. If only cover slides are exposed, it shows a warning.

Instagram reels use yt-dlp; photo and mixed carousel posts use Instaloader. Some posts require a login session or are blocked by the platform. External article previews, text-only posts, LinkedIn Learning and live events are not supported. LinkedIn `lnkd.in/p/...` post short links and full post URLs both work. LinkedIn support currently reads the public post view; personal LinkedIn login cookies are not used.

Accepted LinkedIn links (Instagram and Pinterest links are described in their own paragraphs): `https://www.linkedin.com/posts/...-activity-1234-abcd`, `https://www.linkedin.com/feed/update/urn:li:activity:1234/` (also share/ugcPost URNs), and LinkedIn post share links such as `https://lnkd.in/p/AbCd1234`. Short links are safely resolved to their full LinkedIn post URL and tracking parameters are removed.

Pinterest pins are read from the public pin page's structured data (`schema.org` JSON-LD), so no login or API key is needed. Image pins download the original-size file from `i.pinimg.com` (falling back to the 736 px copy only if the original is unavailable); video pins download the pin's own MP4 from `v1.pinimg.com`, including audio. If a page lists only a streaming playlist, the MP4 is taken from the same page by the video's own ID, and as a last resort yt-dlp assembles it (needs ffmpeg). Accepted links: `https://www.pinterest.com/pin/<id>/`, regional hosts (`in.pinterest.com`, `pinterest.co.uk`, ...), slug forms such as `/pin/some-title--<id>/`, and `https://pin.it/<code>` share links. Share links are followed hop by hop (`pin.it` → `api.pinterest.com` → the pin), and the `sender`/`invite_code` details in the final URL are discarded. Only the pin ID is used: the page is always fetched from `www.pinterest.com` and media only from `pinimg.com`. Boards, profiles and search pages are not supported, and a few pins that Pinterest hides from signed-out visitors return a clear error.

Download sessions expire after 15 minutes or a server restart. Fetch the post again to refresh. Individual files are capped at 250 MB, ZIP bundles at 500 MB, and posts at 100 attachments. Media is streamed into a per-request temporary directory and streamed back to the browser in 64 KB chunks; completed, failed, and disconnected transfers clean up their directory, with a one-hour stale-job sweep as a restart fallback. The ZIP preserves post/slide order using numbered filenames. These are available platform renditions, not a guarantee of original upload quality.

## Start manually

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Keep the terminal open. Restart the app after changing Python files. `HOST` and `PORT` environment variables override the local defaults; the launchers open port 5000.

## Production server

Linux hosting uses Gunicorn through the included `Procfile`:

```bash
gunicorn --config gunicorn.conf.py wsgi:application
```

The configuration binds to the hosting platform's `PORT`, uses one process with four threads for the 512 MB beta target, allows media requests up to five minutes, and periodically recycles the worker. The Windows launcher intentionally continues to use Flask for local development because Gunicorn does not support Windows.

## Docker and ffmpeg

The production image uses the official Python 3.12 slim Bookworm base, installs ffmpeg and CA certificates, runs as an unprivileged `downloader` user, and starts Gunicorn on `PORT` (default `10000`). Secrets, cookies, local environments, test output and documentation are excluded from the Docker build context.

```bash
docker build -t social-downloader .
docker run --rm -p 10000:10000 social-downloader
```

Open http://127.0.0.1:10000. Temporary media exists only inside the container's writable layer and is deleted after transfer. Stopping a container keeps that layer; removing it (for example with `--rm`) discards it. Abandoned jobs are swept at startup and every few minutes.

## Local Instagram cookies

If Instagram requests sign-in, export your Instagram cookies in Netscape format to `cookies.txt` beside `app.py`, or set `IG_BROWSER=firefox` (also supports Chrome/Edge/Brave/Safari through yt-dlp). Cookies are imported into Instaloader for photo posts too. Browser-cookie extraction can fail when the browser locks or encrypts its database.

Windows cmd: `set IG_BROWSER=firefox`, then `python app.py`.
PowerShell: `$env:IG_BROWSER='firefox'`, then `python app.py`.
Mac/Linux: `IG_BROWSER=firefox python app.py`.

Treat cookies as credentials. `.gitignore` excludes cookies and environment files. Do not upload a personal login session to a public server. Only download content you own or have permission to use.

## Verification

```powershell
python -m unittest -v test_app test_production test_public test_pinterest test_seo
python -m pip install -r requirements-dev.txt
python verify_live.py
```

The unit suite uses fixtures/mocks. `verify_live.py` is an explicit manual network smoke check; public sample availability can change. It fails on incorrect counts, broken individual files or invalid ZIPs and saves results in `docs/live-test-results.json`. The latest saved run (2026-10-02) passed all eleven real-URL cases, including two `lnkd.in` short links. Earlier, nine passed: LinkedIn single/eight/four-image posts, a video, a 12-slide document, an Instagram reel, a photo, a three-video carousel and a six-image carousel. Mixed photo/video carousel handling has fixture coverage; no real mixed post has been verified yet. See `docs/TESTING.md` for the audit.

## Public mode and configuration

The Docker image sets `PUBLIC_MODE=1`. In public mode the app never reads `cookies.txt` or `IG_BROWSER`, requires an ownership/permission acknowledgment (`ack: true`) on `/api/info`, and enables rate and concurrency limits. Locally (no `PUBLIC_MODE`) behavior is unchanged.

| Variable | Default (public) | Purpose |
|---|---|---|
| `REDIS_URL` | unset | Shared session store. Unset: process memory, so keep one worker. If Redis fails the app falls back to memory and `/readyz` reports `degraded` |
| `RATE_INFO_PER_MIN` / `RATE_DOWNLOAD_PER_MIN` | 10 / 30 | Per-IP requests per minute (0 = off) |
| `MAX_CONCURRENT_DOWNLOADS` / `MAX_DOWNLOADS_PER_CLIENT` | 2 / 1 | Simultaneous download jobs, total and per IP; excess gets 503 + `Retry-After` |
| `DISK_BUDGET_MB` / `MIN_FREE_DISK_MB` | 1536 / 300 | New jobs are refused (503) above the budget or below free space |
| `STALE_DOWNLOAD_AGE` / `CLEANUP_INTERVAL` | 900 / 300 s | Abandoned job lifetime and sweep period |
| `TRUSTED_PROXY_HOPS` | 1 | Number of proxies whose `X-Forwarded-For` is trusted for client IPs. Set to 0 when not behind a proxy |
| `CLIENT_IP_HEADER` | unset | Header holding the real client IP behind a CDN (Render: `CF-Connecting-IP`); invalid values fall back to the socket address |
| `CONTACT_EMAIL`, `OPERATOR_NAME` | unset | Shown on the legal pages; the pages warn until `CONTACT_EMAIL` is set. `OPERATOR_NAME` is optional |

`GET /healthz` is a cheap liveness check for a free uptime monitor; `GET /readyz` checks storage, Redis and reports active downloads. The Gunicorn access log omits query strings, so session tokens are not logged. Rate limits and concurrency caps are per process (one worker).

## Deploy on Render (free)

`render.yaml` is a Blueprint for a free Docker web service plus a free Key Value (Redis-compatible) instance in the same region, wired together through `REDIS_URL`.

1. Push this folder to a GitHub repository (cookies, `.env` and `.venv` are git-ignored).
2. In the Render dashboard choose **New > Blueprint**, select the repository, and apply.
3. Open `https://<service>.onrender.com/readyz`: it should report `ready` with `redis: true`.
4. Optionally point a free uptime monitor at `/healthz`. Without traffic the free service sleeps after 15 minutes and takes about a minute to wake; a monitor ping keeps it awake (750 free hours cover one always-on service).

Free-tier facts checked on 2026-10-02 (Render docs): web service 512 MB RAM and 0.1 CPU; spins down after 15 idle minutes; ephemeral filesystem; 750 free instance hours per month; 5 GB outbound bandwidth per month included, and with no payment method Render suspends free services when it runs out; Key Value free plan is 25 MB, in-memory, 50 connections, one per workspace, and loses data on restart (sessions only live 15 minutes). Render is behind Cloudflare, so the blueprint sets `CLIENT_IP_HEADER=CF-Connecting-IP` for per-client limits instead of trusting `X-Forwarded-For`. Render says free instances are not for production use; this is a beta.

## SEO and AI visibility

Pages are server-rendered from `site_content.py` (one source for the visible text, the JSON-LD, `sitemap.xml`, `llms.txt` and `llms-full.txt`) and wired up by `seo.py`. Crawler files: `/robots.txt` (welcomes search and AI crawlers, hides the API), `/sitemap.xml`, `/llms.txt`, `/llms-full.txt`, `/pricing.md`, `/.well-known/security.txt`, `/site.webmanifest` and an IndexNow key file. Settings: `SITE_URL` (canonical origin; other hosts 301 to it), `SITE_NAME` (default PostSav), `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION`, `GITHUB_URL`, `INDEXNOW_KEY`.

```powershell
python verify_seo.py https://your-site.example --external   # crawler files, metadata, schema, outbound links
python indexnow.py https://your-site.example                 # tell Bing and other IndexNow engines
```

The full strategy, keyword map, custom-domain steps and monthly routine are in [docs/SEO.md](docs/SEO.md).

## Optional Google Analytics and AdSense

See [docs/GOOGLE-SETUP.md](docs/GOOGLE-SETUP.md) for account setup, consent configuration and activation.
Set `GA_MEASUREMENT_ID=G-...` to enable opt-in Analytics on public pages.
Set `ADSENSE_PUBLISHER_ID=ca-pub-...` to publish the verification tag and `/ads.txt`;
set `ADSENSE_ENABLED=1` only after AdSense approval and advertising consent setup.
Both integrations are off by default and never load in local mode or on error pages.
Consent behavior can be checked with `node tools/test_privacy.cjs`.

## Future public hosting

The app is structured for extension. Remaining work before a public launch:

- Choose a dependable extraction provider or managed access strategy; public-page extraction can fail from datacenter IPs or when platforms change.
- Choose free hosting and a free Redis service, set `OPERATOR_NAME`/`CONTACT_EMAIL`, and review the legal pages (they are plain-language drafts, not legal advice).
- For multiple workers, move rate limits and the download gate into Redis too; sessions already support it.
- For higher traffic, move temporary downloads to object storage with quotas. The beta server no longer buffers complete media files in Python memory, although the current browser UI still creates a client-side Blob before saving.
- Add monitoring, privacy/retention rules, and abuse controls. Keep end-user login and personal cookies out of the shared service.

See [RESEARCH.md](RESEARCH.md) for the source comparison and implementation decisions.
