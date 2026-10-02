# LinkedIn media extraction research

Researched and checked on 2026-10-01, with public requests from this Windows environment.

## What a LinkedIn post can contain

LinkedIn's [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api) distinguishes images, video, documents, multi-image posts and sponsored carousels. The familiar organic swipeable PDF post is a document; it must be handled separately from a set of uploaded images. A post's author avatar, external link preview, video poster and related posts are not attachments to download.

## Options considered

| Approach | Coverage | Access and tradeoff | Decision |
|---|---|---|---|
| Official LinkedIn API | Structured post/media references; Images/Videos/Documents APIs | Member read permission is restricted to approved applications. Organization reads require qualifying roles. Does not provide unrestricted access to any pasted post URL. | Unsuitable as the sole public-link backend. Useful later for authorized owned-account integrations. |
| yt-dlp | LinkedIn native post video | Its post extractor parses the public video element's `data-sources`. Does not collect images/document slides. | Preserve yt-dlp for existing Instagram videos; use the same publicly exposed LinkedIn video source pattern. |
| Public HTML plus document manifests | Native video, image attachments, available carousel pages | No API key needed; works only for content exposed by LinkedIn's public page and media endpoints. HTML/CDN contracts can change and requests may be blocked. | Implemented local baseline. |
| Authenticated browser/Voyager requests | Potentially more signed-in content | Requires sessions, dynamic rendering and undocumented endpoints; creates account/session management and operational complexity. | Not implemented; no login-wall bypass or personal LinkedIn cookie deployment. |
| Managed extraction provider | Provider-dependent | Requires evaluating actual image, video, document page coverage, availability, cost and retention. Marketing claims do not prove complete carousel support. | A replaceable provider boundary is the future hosting path; no paid service chosen or purchased. |

Primary references: [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api), [Documents API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/documents-api), [Images API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api), [Videos API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api), [yt-dlp LinkedIn source](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/linkedin.py).

## Evidence from actual public pages

The [MathWorks video sample](https://www.linkedin.com/posts/the-mathworks_2_what-is-mathworks-cloud-center-activity-7151241570371948544-4Gu7) exposes a video element containing multiple MP4 sources and bitrates. We select the highest exposed bitrate for that video, retaining audio in the platform's combined MP4. The real app route downloaded a 5.6 MB MP4 successfully.

The [Rhea image sample](https://www.linkedin.com/posts/rhea-space-activity_spacephotography-photography-nasa-activity-6986886128238784512-QUyP) exposes a post image on LinkedIn's CDN. The real app route downloaded a JPEG. The subsequent audit verified an eight-image Friends of NASA post and a four-image NASA Goddard feed URL. LinkedIn's public grid showed only five of eight images; the primary post's JSON-LD contained all eight in order. Attachment paths include `feedshare-shrink`, `feedshare-image-high-res`, and newer `image-shrink` within native image containers. Extraction now uses both metadata and scoped HTML, excluding avatars, article previews and related pictures.

The [Richard van der Blom document sample](https://www.linkedin.com/posts/richardvanderblom_how-to-create-the-perfect-carousel-post-on-activity-7138425457561006080-VOAi) exposes `data-native-document-config`, with a master manifest URL and total page count. The master manifest lists resolution-specific image manifests. Selecting the largest width yielded 12 page URLs in order. The real app route downloaded a roughly 4.9 MB ZIP with 12 images; ZIP integrity checking passed. The manifest also flags `scanRequiredForDownload: true`, so the app does not offer its original PDF. This observation is a current implementation detail, not a documented stable LinkedIn API contract.

## Instagram image support

[Instaloader's Python interface](https://instaloader.github.io/as-module.html) provides post metadata and carousel nodes. It complements yt-dlp, which focuses on video. Photo/mixed-carousel extraction uses those nodes and imports optional local Instagram cookies. Reel extraction keeps its established yt-dlp path and reuses an extracted combined MP4 URL when possible. The audit successfully downloaded a NASA photo, all six images of an azcentral carousel and all three videos of an Instagram carousel, individually and in ZIPs. Mixed image/video handling has fixture coverage but still needs a real mixed-post example. See `docs/TESTING.md` for URLs and verification limits.

## Pinterest (added 2026-10-02)

Findings from the five links supplied for this feature: `pin.it/<code>` returns 308 to `api.pinterest.com/url_shortener/<code>/redirect/`, which returns 302 to `www.pinterest.com/pin/<id>/sent/?invite_code=...&sender=...&sfo=1` (the sender and invite code identify a person and are dropped). Pin pages are ~1.2 MB and carry `SocialMediaPosting` (headline, author, original-size `image` on `i.pinimg.com/originals/`) and, for video pins, `VideoObject` (`contentUrl`, `thumbnailUrl`) JSON-LD at the very end of the document. Four of the five pins were videos (direct H.264 + AAC MP4s, 720 px wide) and one was an image (3.7 MB original PNG). Canonical/`og:url` links of repinned pins point at a different (original) pin ID, so no identity check is made on them; the fetch is by the requested ID.

Page variants differ between requests (sizes 1.26-1.49 MB). In sampling, about 1 in 12 responses listed an HLS playlist (`.../hls/....m3u8`) as the `VideoObject.contentUrl` instead of the MP4; the same page still contains the MP4 URL, keyed by the same 32-character video ID, so the extractor recovers it from there and only uses yt-dlp (separate HLS video/audio muxed by ffmpeg, format `bv*+ba/b`) if no MP4 is present. The original pin ID of a repinned image (`/pin/396739048447882369/`) returned an empty page shell to signed-out clients, and Pinterest's `PinResource` JSON endpoint answered 403, so neither is used. yt-dlp's Pinterest extractor handles video pins but reports "No video formats found" for image pins, which is why structured data is the primary source.

Security boundaries: input hosts are matched against Pinterest's regional domain pattern only to read the pin ID; requests go to `www.pinterest.com` (page) and `pinimg.com` (media) with every redirect revalidated, https only, no credentials, standard port.

## 

`media_sources.py` owns extraction and trusted media fetching; Flask owns presentation and expiring session tokens. Client requests specify a session and attachment ID rather than arbitrary media URLs. CDN fetching validates HTTPS and hostnames on every redirect, bounds response size, uses timeouts and checks returned media MIME types. This reduces arbitrary URL proxy exposure; it is not a substitute for full production egress controls or abuse limits. Instagram's yt-dlp network path has its own upstream redirect handling.

Sessions expire after 15 minutes and live in Redis when `REDIS_URL` is set, otherwise in one process (capped at 100). Server downloads and ZIPs are written to temporary disk and streamed in 64 KiB chunks; only browser-side saving still buffers the full file as a Blob. A public deployment should use queued jobs, shared state, quotas and storage-backed delivery. No public deployment was performed.

Public requests can return sign-in pages, throttling or unavailable media. The app reports those limits instead of presenting unrelated preview images as a successful extraction. It cannot promise to extract every visual from every URL. Downloads of gated originals are not bypassed. A deployment/provider decision should be based on real user post samples for single image, multi-image, video and document carousel cases, including partial and blocked responses.
