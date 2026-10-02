# Historical handoff — superseded

**Read [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) for the complete, current handoff updated 2026-10-02. The summary below is historical and includes stale statements.**

Updated 2026-10-01. Local Flask app supports Instagram and LinkedIn. Public hosting remains planned, not deployed.

## Current implementation

- `app.py`: URL validation, API routes, expiring bounded download sessions, disk-backed streaming downloads, automatic temporary-job cleanup and ordered ZIP bundles.
- `media_sources.py`: LinkedIn public-page image/video/document-slide extraction, Instaloader photo/mixed-carousel support, yt-dlp Instagram videos, CDN restrictions and bounded requests.
- `templates/index.html`: revised Instagram + LinkedIn wording, responsive attachment grid, inline download errors, individual and ZIP controls, cancellation of stale fetches.
- `test_app.py`: offline regression tests; `verify_live.py`: opt-in public network smoke checks.
- `RESEARCH.md`: sources, evidence, provider comparison, limitations and public-hosting decisions.
- Both existing launchers still install dependencies and launch the app on port 5000.
- Production WSGI entry point, Gunicorn configuration and `Procfile` are included. The 512 MB profile uses one `gthread` worker with four threads.
- `Dockerfile` builds a non-root Python 3.12 Bookworm image with ffmpeg and Gunicorn; `.dockerignore` excludes secrets, local state, tests and documentation.
- LinkedIn `lnkd.in/p/...` share links are resolved through validated HTTPS redirects to a supported full LinkedIn post URL.

## Verified

Nine real-URL cases passed, covering LinkedIn single/eight/four-image posts, video and a 12-slide document, plus Instagram reel, single photo, three-video carousel and six-image carousel. Every individual attachment and five ZIPs validated. Sixteen offline regressions passed. Windows batch launcher ran successfully in a fresh `.venv`; project dependency checks passed. Browser previews, inline invalid/expired-session errors and completed download UI states were checked. See `docs/TESTING.md` and `docs/live-test-results.json`. Public behavior can change.

## Outstanding

Real mixed photo/video carousel coverage remains outstanding (offline fixture passes). Original LinkedIn PDF is offered only when its manifest permits download; the gated sample was verified to expose slides but no PDF option. LinkedIn restricted content and short links are unsupported. Public hosting needs an extraction-access decision, production server, rate/concurrency limits, shared sessions, background jobs and bounded storage-backed delivery. Do not upload personal login cookies into a shared public deployment.

Run with `start-windows.bat`, or `python app.py`. Run regressions with `python -m unittest -v test_app`. Refer to README for cookie setup and download limits.
