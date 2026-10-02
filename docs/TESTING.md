# Bug audit and verification — 2026-10-01

All source files, templates, launchers, requirements, ignore rules and documentation were reviewed. Results below describe tested samples, not guaranteed platform-wide availability.

## Fixed during the audit

- LinkedIn multi-image posts returned only two of eight attachments: high-resolution paths were omitted, and hidden images were absent from the visible grid. Extraction now reads the full ordered JSON-LD image list, includes both image path generations and deduplicates grid entries.
- A real LinkedIn feed URL used newer `image-shrink` paths. Native images now work without collecting external article preview images.
- Very long numeric attachment IDs could raise a Python conversion error outside the error handler. IDs now accept at most three ASCII digits and invalid values return JSON 400 responses.
- Oversized requests returned HTML 413 responses that confused the browser. They now return a clear JSON error; the browser also handles non-JSON server failures.
- Different posts by the same author could produce identical filenames. Filenames now include the post ID/shortcode and attachment position.
- Empty extractions could be reported as a successful zero-item session. They now fail before creating a session.
- Incorrect LinkedIn post identity could be accepted. Target IDs are checked against the returned post.
- Re-extracting Instagram videos during download could produce avoidable extra platform requests. Combined MP4 URLs from successful extraction are reused; merging still uses yt-dlp where necessary.
- Other buttons appeared actionable during a download, duplicate fetches could be initiated, and broken thumbnails stayed broken. Download controls now reflect busy state, identical in-flight fetches are ignored, and failed previews get a placeholder.
- The Windows launcher could open the browser before the server started and continue after dependency errors. It now checks installation failures; both launchers let the app open the browser after its first successful response. Documented Python minimum corrected from 3.9 to 3.10, matching yt-dlp.

## Real URL cases

Exact URLs and machine-readable outcomes are in [live-test-results.json](live-test-results.json).

| Sample | Expected attachments | Result |
|---|---|---|
| LinkedIn `lnkd.in/p/dSMQHtWn` short link | 1 video | PASS |
| LinkedIn `lnkd.in/p/dEm7VwWv` short link | 1 image | PASS |
| LinkedIn Rhea Space Activity | 1 image | PASS |
| LinkedIn Friends of NASA | 8 images | PASS |
| LinkedIn NASA Goddard feed URL | 4 images | PASS |
| LinkedIn MathWorks | 1 video | PASS |
| LinkedIn Richard van der Blom | 12 document slides | PASS |
| Instagram Kallaway | 1 reel | PASS |
| Instagram NASA black-hole photo | 1 image | PASS |
| Instagram multi-video post BQ0eAlwhDrw | 3 videos | PASS |
| Instagram azcentral DJS2jZXptzr | 6 images | PASS |

37 individual attachments downloaded and validated. All five multi-attachment ZIPs passed entry-count, CRC and member-file checks. Pillow verified image integrity; MP4 checks verified container signatures and media/metadata atoms. This is not a complete playback/decode or audio-quality test.

## Pinterest (2026-10-02)

Offline: `test_pinterest.py` covers URL normalization and lookalike rejection, `pin.it` hop-by-hop resolution (unsafe redirects, loops, outages), extraction from fixtures (video MP4, HLS-to-MP4 recovery by video ID, yt-dlp fallback, untrusted hosts, image originals with reduced fallbacks, multi-image pins, malformed JSON-LD, entities, HTTP error mapping) and download behaviour (fallback only on 404/403, size-limit errors do not fall back, cleanup, ZIP order, yt-dlp options). Live: all five supplied `pin.it` links (four videos, one image) downloaded and validated, plus a regional slug URL; `python verify_live.py Pinterest` runs just these. The yt-dlp fallback was run for real inside the Docker image (ffmpeg present) and produced an H.264 + AAC MP4.

## Environment and UI

Fifty-four offline tests pass (`test_app`, `test_production`, `test_public`). Python compilation passes. Tests also run in the `.venv` created by the actual Windows batch launcher; `pip check` reports no broken project requirements. The batch launcher successfully starts the site and opens the browser. The Mac/Linux script was reviewed but cannot be executed as a native launcher on this Windows machine.

Server-memory verification used unbuffered response iteration with real media. A 10.3 MB LinkedIn MP4 produced about 0.42 MB peak traced Python allocation; a 4.9 MB 12-slide ZIP produced about 0.58 MB. Both job directories were empty after transfer. These figures measure Python allocations during the download route, not total process RSS or ffmpeg's separate-process memory.

In-app browser checks confirmed the eight-image LinkedIn and six-image Instagram previews, enabled/disabled download controls, inline invalid-URL errors and expired-session errors after a server restart. A browser image download reached its ready state with no console errors; the in-app browser did not expose the Blob download through its download-event API, so a native saved-file check was not confirmed through that tool. API downloads were validated independently as described above.

## Remaining platform limits

Private/restricted content and platform blocking can still prevent extraction. LinkedIn originals with a sign-in-gated PDF remain unavailable; their exposed slide images work. A real mixed photo/video Instagram carousel is still unverified, although the mixed-node fixture passes. This version remains local; public hosting requirements are recorded in README and RESEARCH.
