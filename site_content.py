"""Single source of truth for page copy, structured data, sitemap and llms.txt.

Every factual claim here is something this project verified: supported content types, limits, file formats and
the dated real-world test results. Update UPDATED/TESTED_ON when the copy or the test results change.

Inline markup allowed in text: [label](url), **bold**, `code`.
"""
import os

BRAND = os.environ.get('SITE_NAME', '').strip() or 'PostSav'
TAGLINE = 'Free Instagram, LinkedIn & Pinterest post downloader'
UPDATED = '2026-10-03'
LEGAL_UPDATED = '2026-10-02'
TESTED_ON = '2 October 2026'
GITHUB_URL = os.environ.get('GITHUB_URL', 'https://github.com/progcode05-sketch/postsav').strip()
# Mirrors app.py (a test keeps the two in sync).
LIMITS = dict(file_mb=250, zip_mb=500, attachments=100, session_minutes=15, lookups_per_min=10, downloads_per_min=30)

B = BRAND

HELP = dict(
    instagram_link=('Instagram Help Center: Get a link to a photo or video', 'https://help.instagram.com/372819389498306'),
    instagram_terms=('Instagram Terms of Use', 'https://help.instagram.com/581066165581870'),
    linkedin_share=('LinkedIn Help: Share a post from LinkedIn', 'https://www.linkedin.com/help/linkedin/answer/a7443434'),
    linkedin_public=('LinkedIn Help: Sharing public posts on and off LinkedIn', 'https://www.linkedin.com/help/linkedin/answer/a523372'),
    linkedin_terms=('LinkedIn User Agreement', 'https://www.linkedin.com/legal/user-agreement'),
    pinterest_share=('Pinterest Help: Share Pins, boards, and profiles', 'https://help.pinterest.com/en/article/send-pins-boards-and-profiles'),
    pinterest_pins=('Pinterest Help: Interact with Pins', 'https://help.pinterest.com/en/article/interact-with-pins'),
    pinterest_terms=('Pinterest Terms of Service', 'https://policy.pinterest.com/en/terms-of-service'),
)


def source(key, note):
    title, url = HELP[key]
    return (title, url, note)


NAV = [
    ('LinkedIn', '/linkedin-downloader'),
    ('Pinterest', '/pinterest-downloader'),
    ('Instagram', '/instagram-downloader'),
    ('How it works', '/#how'),
    ('FAQ', '/#faq'),
]

FOOTER_GROUPS = [
    ('Downloaders', [('LinkedIn downloader', '/linkedin-downloader'), ('Pinterest downloader', '/pinterest-downloader'), ('Instagram downloader', '/instagram-downloader')]),
    (B, [('About and how it works', '/about'), ('Contact', '/contact')]),
    ('Legal', [('Terms of use', '/terms'), ('Privacy policy', '/privacy'), ('Copyright and takedown', '/copyright')]),
]

PLATFORM_CARDS = [
    ('li', 'in', 'LinkedIn downloader', '/linkedin-downloader', 'Carousel slides, document posts, videos and images, including lnkd.in share links.'),
    ('pin', 'P', 'Pinterest downloader', '/pinterest-downloader', 'Original-size images and MP4 video pins, including pin.it share links.'),
    ('ig', 'IG', 'Instagram downloader', '/instagram-downloader', 'Reels, photos and carousel posts from a public link.'),
]

FEATURES = [
    ('feature-images', 'Hands holding a phone showing an Instagram feed', 720, 1080, '50% 38%', 'JPG · PNG · WebP', 'Images and photo carousels',
     'Single photos and multi-image posts from Instagram and LinkedIn, plus full-size Pinterest pin images.'),
    ('feature-video', 'A presenter being filmed with a cinema camera in a studio', 720, 484, '50% 50%', 'MP4', 'Videos and reels',
     'Instagram reels, LinkedIn videos and Pinterest video pins as standard MP4 files.'),
    ('feature-slides', 'A laptop showing a LinkedIn profile next to a phone', 720, 480, '50% 45%', 'Slide by slide', 'LinkedIn document slides',
     'Carousel documents saved slide by slide as images, kept in their original order.'),
    ('feature-zip', 'A person using a laptop and a phone together', 720, 480, '50% 40%', 'bundle.zip', 'One-click ZIP',
     'Everything in a post in a single download, named and ordered so it is easy to sort.'),
]

TRUST = [
    ('Three platforms', 'Instagram, LinkedIn, Pinterest'),
    ('No sign-up', 'No account or login needed'),
    ('Not stored', 'Files deleted when done'),
    ('Free beta', 'No ads, no trackers'),
]

SHARE_STEPS = (
    'On Instagram, tap Send and choose Copy link (on desktop, use Options next to the post). On LinkedIn, open the More menu and choose '
    'Copy link to post. On Pinterest, open the pin, choose Share, then Copy link, which usually gives a pin.it link.'
)

PAGES = {}

# ----------------------------------------------------------------------------------------------------------------
PAGES['/'] = dict(
    path='/', template='index.html', kind='home', updated=UPDATED, tool=True,
    title=f'Free Instagram, LinkedIn & Pinterest Downloader | {B}',
    description='Download images, videos and carousel slides from public Instagram, LinkedIn and Pinterest posts. Paste a link, get the files or a ZIP. No sign-up.',
    eyebrow='Instagram + LinkedIn + Pinterest · free beta',
    h1_soft='Free Instagram, LinkedIn & Pinterest', h1_hi='post downloader',
    lead=(f'{B} is a free web tool that saves the images, videos and carousel slides from public Instagram, LinkedIn and Pinterest posts. '
          'Paste a post link, preview what is available, then download each file or everything as one ZIP. No account, no app, nothing stored.'),
    tool_placeholder='Paste an Instagram, LinkedIn or Pinterest link',
    tool_label='Instagram, LinkedIn or Pinterest post URL',
    breadcrumb=[],
    sections=[
        dict(type='steps', id='how', kicker='How it works', heading='How to download an Instagram, LinkedIn or Pinterest post',
             intro='Three steps, no sign-up, nothing to install.', howto_name='How to download an Instagram, LinkedIn or Pinterest post',
             items=[
                 ('Copy the post link', SHARE_STEPS),
                 ('Paste it and confirm permission', f'Paste the link into the box at the top of this page and tick the box to confirm you own the content or have permission to download it. {B} reads the public post only and never asks for your login.'),
                 ('Preview and download', 'Check the previews, then download single files or choose Download all · ZIP. Slides and files are numbered in post order, so they sort correctly.'),
             ]),
        dict(type='features', id='features', kicker='What you can save', heading='Built for the posts you actually share', items=FEATURES, trust=TRUST),
        dict(type='table', id='supported', kicker='Support at a glance', heading=f'What can {B} download from each platform?',
             intro='This is exactly what the tool supports today. Each platform name links to a page with details and a step-by-step guide.',
             columns=['Platform', 'Images', 'Videos', 'Carousels and slides', 'Link types', 'Not supported'],
             rows=[
                 ['[Instagram](/instagram-downloader)', 'Photos', 'Reels and videos (MP4)', 'Photo and video carousels', 'instagram.com/p/, /reel/, /tv/', 'Stories, private accounts, sign-in-only posts'],
                 ['[LinkedIn](/linkedin-downloader)', 'Single and multi-image posts', 'Videos (MP4)', 'Document slides as ordered images; PDF only when LinkedIn allows it', 'linkedin.com posts, lnkd.in/p/', 'Text-only posts, articles, LinkedIn Learning, restricted posts'],
                 ['[Pinterest](/pinterest-downloader)', 'Original-size images', 'Video pins (MP4, with sound when the pin has it)', 'Multi-image pins when Pinterest exposes them', 'pinterest.com/pin/, pin.it', 'Boards, profiles, search pages, pins hidden from signed-out visitors'],
             ]),
        dict(type='cards', id='platforms', kicker='Guides by platform', heading='Pick your platform', items=PLATFORM_CARDS),
        dict(type='facts', id='at-a-glance', kicker='Key facts', heading=f'{B} at a glance', items=[
            ('Cost', 'Free during the beta. No account, subscription or browser extension.'),
            ('Works with', 'Public posts on Instagram, LinkedIn and Pinterest, including lnkd.in and pin.it share links.'),
            ('What you get', 'The image and video files the platform serves, one by one or as an ordered ZIP. No watermark is added.'),
            ('Limits', f"Up to {LIMITS['file_mb']} MB per file, {LIMITS['zip_mb']} MB per ZIP and {LIMITS['attachments']} attachments per post."),
            ('Privacy', f"No accounts, cookies, ads or analytics. Files are deleted when the transfer ends; post details are kept for at most {LIMITS['session_minutes']} minutes."),
            ('Last tested', f'On {TESTED_ON}, 17 of 17 real public post links (7 LinkedIn, 4 Instagram, 6 Pinterest) downloaded and validated, every attachment and every ZIP.'),
        ]),
        dict(type='faq', id='faq', kicker='FAQ', heading='Frequently asked questions', items=[
            (f'What is {B}?', f'{B} is a free web tool that saves the images, videos and carousel slides from public Instagram, LinkedIn and Pinterest posts. You paste a post link, preview what is available and download each file or a ZIP. It needs no account and keeps no copy of your files.'),
            ('How do I download a video or image from Instagram, LinkedIn or Pinterest?', 'Copy the link to the post, paste it into the box at the top of this page, confirm you have permission to download the content, and choose Fetch media. Then download any file individually, or take everything with Download all · ZIP.'),
            (f'Is {B} free, and do I need an account?', f"{B} is free during its beta and needs no account, app or browser extension. To keep it fast for everyone it limits each visitor to {LIMITS['lookups_per_min']} lookups and {LIMITS['downloads_per_min']} downloads per minute, up to {LIMITS['file_mb']} MB per file and {LIMITS['zip_mb']} MB per ZIP."),
            ('Can I download a LinkedIn carousel as images or a PDF?', 'As images, yes: every slide LinkedIn exposes is saved as a numbered image or together as a ZIP. A PDF is offered only when LinkedIn lets viewers download the original document. See the [LinkedIn downloader](/linkedin-downloader) for details.'),
            (f'Does {B} work with lnkd.in and pin.it short links?', 'Yes. Short links from LinkedIn (lnkd.in) and Pinterest (pin.it) are followed to the original post one redirect at a time, and tracking details such as the sender ID in Pinterest links are discarded.'),
            (f'Why can\'t {B} download some posts?', f'{B} only reads public posts and never uses a login. Private accounts, sign-in-only posts, text-only posts, stories and boards cannot be fetched, and a platform may occasionally limit requests. Try again later, or open the post and copy its link again.'),
            (f'Does {B} store my files or links?', f"No. Downloads are written to temporary storage, streamed to your browser and deleted when the transfer finishes. Post details are kept for at most {LIMITS['session_minutes']} minutes so your download links work. There are no accounts, cookies, ads or analytics. Read the [privacy policy](/privacy)."),
            ('What quality are the downloads?', 'You get the files the platform serves, without re-encoding or watermarks: original-size images on Pinterest, MP4 videos from all three platforms and every slide of a LinkedIn carousel. Quality cannot exceed what the platform makes public.'),
            ('Is it legal to download content from social media?', 'It depends on who owns the content and how you use it. Save posts you created or have permission to use; other people\'s posts are protected by copyright and by each platform\'s terms. This is general information, not legal advice. See the [terms](/terms) and [copyright and takedown](/copyright) pages.'),
        ]),
        dict(type='sources', id='sources', kicker='Sources', heading='Official guides and terms', items=[
            source('instagram_link', 'How to copy the link to a post or Reel.'),
            source('linkedin_share', 'How to copy the link to a LinkedIn post.'),
            source('pinterest_share', 'How to copy the link to a pin.'),
            source('instagram_terms', 'The rules that apply to Instagram content.'),
            source('linkedin_terms', 'The rules that apply to LinkedIn content.'),
            source('pinterest_terms', 'The rules that apply to Pinterest content.'),
        ]),
    ],
)

# ----------------------------------------------------------------------------------------------------------------
PAGES['/linkedin-downloader'] = dict(
    path='/linkedin-downloader', template='platform.html', kind='platform', updated=UPDATED, tool=True,
    title=f'LinkedIn Carousel, Video & Image Downloader | {B}',
    description='Download LinkedIn carousel slides, document posts, videos and images from a post link. Save slides as images or a ZIP. Works with lnkd.in links. Free.',
    eyebrow='LinkedIn downloader',
    h1_soft='Free LinkedIn', h1_hi='carousel, video & image downloader',
    lead=(f"{B}'s LinkedIn downloader saves the images, videos and carousel (document) slides from a public LinkedIn post. Paste the post link or a lnkd.in share link, "
          'then download each slide as an image or every slide together as an ordered ZIP. The original PDF is offered only when LinkedIn allows downloading it.'),
    tool_placeholder='Paste a LinkedIn post link (linkedin.com or lnkd.in)',
    tool_label='LinkedIn post URL',
    breadcrumb=[('Home', '/'), ('LinkedIn downloader', '/linkedin-downloader')],
    sections=[
        dict(type='facts', id='at-a-glance', kicker='Key facts', heading='LinkedIn downloader at a glance', items=[
            ('Saves', 'Images (including multi-image posts), videos as MP4, and carousel or document slides as numbered images.'),
            ('PDF', 'Offered only when LinkedIn exposes a download for that document. Many documents require sign-in, and the tool never bypasses that.'),
            ('Accepted links', 'linkedin.com/posts/…, linkedin.com/feed/update/urn:li:activity:… and lnkd.in/p/… share links.'),
            ('Not supported', 'Text-only posts, article link previews, LinkedIn Learning, live events and posts LinkedIn shows only to signed-in members.'),
            ('Login', f'None. {B} reads the public post page and never asks for your LinkedIn credentials or cookies.'),
            ('Last tested', f'7 of 7 public LinkedIn links passed on {TESTED_ON}: a single image, 4 images, 8 images, a video, a 12-slide document and two lnkd.in links.'),
        ]),
        dict(type='steps', id='how', kicker='How it works', heading='How to download a LinkedIn carousel (document post)',
             intro='A LinkedIn carousel is a document post: a series of slides. These steps save every slide LinkedIn exposes.',
             howto_name='How to download a LinkedIn carousel',
             items=[
                 ('Copy the post link', 'On the LinkedIn post, open the More menu and choose Copy link to post. [LinkedIn\'s Help Center](https://www.linkedin.com/help/linkedin/answer/a7443434) describes the same steps.'),
                 ('Paste it into the box above', 'Paste the link and confirm you own the content or have permission to download it.'),
                 ('Check the slide previews', f'{B} lists every slide LinkedIn exposes for the document, in order. If only the cover slides are available, a warning says so.'),
                 ('Download the slides', 'Save slides one at a time, or choose Download all · ZIP for a single archive with numbered files.'),
             ]),
        dict(type='table', id='post-types', kicker='What you get', heading='What you get from each LinkedIn post type',
             columns=['Post type', 'What you get', 'Notes'],
             rows=[
                 ['Image post', 'Each image at the size LinkedIn serves', 'Multi-image posts keep their order'],
                 ['Video post', 'An MP4 file (the highest-bitrate version LinkedIn exposes)', 'Plays offline in any standard video player'],
                 ['Document or carousel post', 'Slide images in order, plus a PDF when LinkedIn allows it', 'A warning appears if only some slides are exposed'],
                 ['Text-only post, article or link preview', 'Nothing to save', 'Not supported'],
             ]),
        dict(type='prose', id='pdf', heading='Why you may not get the original PDF', paragraphs=[
            'LinkedIn lets the author of a document post decide who can download the original file. For documents that require sign-in, '
            f'{B} can still save the public slides as images, and it does not try to get around the restriction. If you are signed in to LinkedIn, '
            'the document viewer on LinkedIn itself may offer its own download option for some documents.',
            'Need a single file anyway? Open the downloaded slide images in any PDF or image tool and combine them in order. The numbered filenames keep the slides in sequence.',
        ]),
        dict(type='faq', id='faq', kicker='FAQ', heading='LinkedIn downloader: frequently asked questions', items=[
            ('How do I download a LinkedIn carousel?', f'Copy the post link (More menu, then Copy link to post), paste it into {B}, confirm you have permission, and download the slides one by one or as a ZIP. LinkedIn carousels are document posts, and each slide is listed as a numbered image.'),
            ('Can I download a LinkedIn carousel as a PDF?', f'Only when LinkedIn exposes the original document for download. In that case {B} shows a PDF option next to the slides. When LinkedIn requires sign-in for the PDF, you get the slides as images and a ZIP instead, and the restriction is not bypassed.'),
            ('Can I download LinkedIn videos?', f'Yes, for public video posts. {B} saves the highest-bitrate MP4 that LinkedIn exposes for the video, as a normal file you can play offline.'),
            (f'Does {B} work with lnkd.in links?', 'Yes. lnkd.in/p/ share links are followed safely to the original post, and tracking parameters are removed before the post is fetched.'),
            ('Do I need to log in to LinkedIn?', f'No. {B} reads the public version of a post and never asks for your LinkedIn password or cookies. Posts that LinkedIn only shows to signed-in members cannot be fetched.'),
            (f'Why does {B} say there is nothing to download?', 'Text-only posts, article link previews, LinkedIn Learning items and live events have no image, video or document attachment to save. Private or restricted posts are also unavailable.'),
            ('Is it okay to download someone else\'s LinkedIn post?', 'Only save content you own or have permission to use. Posts are protected by copyright and by LinkedIn\'s terms. See our [terms](/terms) and the [LinkedIn User Agreement](https://www.linkedin.com/legal/user-agreement).'),
        ]),
        dict(type='sources', id='sources', kicker='Sources', heading='LinkedIn guides and terms', items=[
            source('linkedin_share', 'Official steps to copy a post link.'),
            source('linkedin_public', 'How public posts are shared on and off LinkedIn.'),
            source('linkedin_terms', 'The rules that apply to LinkedIn content.'),
        ]),
        dict(type='cards', id='more', kicker='More downloaders', heading='Other platforms', items=[c for c in PLATFORM_CARDS if c[3] != '/linkedin-downloader']),
    ],
)

# ----------------------------------------------------------------------------------------------------------------
PAGES['/pinterest-downloader'] = dict(
    path='/pinterest-downloader', template='platform.html', kind='platform', updated=UPDATED, tool=True,
    title=f'Pinterest Video & Image Downloader (pin.it) | {B}',
    description='Download Pinterest videos and original-size images from a pin link or pin.it share link. MP4 with sound, no watermark, no login. Free, nothing stored.',
    eyebrow='Pinterest downloader',
    h1_soft='Free Pinterest', h1_hi='video & image downloader',
    lead=(f"{B}'s Pinterest downloader saves the original-size image or the MP4 video from a public pin. Paste a pinterest.com pin link or a pin.it share link, "
          'preview the pin, and download the file. Videos keep their sound when the pin has any, and no watermark is added.'),
    tool_placeholder='Paste a Pinterest pin link (pinterest.com or pin.it)',
    tool_label='Pinterest pin URL',
    breadcrumb=[('Home', '/'), ('Pinterest downloader', '/pinterest-downloader')],
    sections=[
        dict(type='facts', id='at-a-glance', kicker='Key facts', heading='Pinterest downloader at a glance', items=[
            ('Saves', 'The original-size image (for example a 2000 × 3000 px PNG instead of the 736 px preview) or a video pin as an MP4 with H.264 video and AAC audio.'),
            ('Accepted links', 'pinterest.com/pin/…, regional versions such as in.pinterest.com and pinterest.co.uk, and pin.it share links.'),
            ('Share-link privacy', f'pin.it links carry the sender\'s Pinterest ID and an invite code. {B} follows the link to the pin and discards both before fetching anything.'),
            ('Not supported', 'Boards, profiles, search results and a few pins that Pinterest hides from signed-out visitors.'),
            ('Login', f'None. {B} reads the public pin page only.'),
            ('Last tested', f'5 of 5 pin links passed on {TESTED_ON}: four video pins (0.4 to 5.0 MB MP4 files, 720 to 736 px wide) and one image pin (a 3.7 MB, 2000 × 3000 px PNG).'),
        ]),
        dict(type='steps', id='how', kicker='How it works', heading='How to download a Pinterest video or image from a link',
             intro='Works the same for image pins and video pins, with a pin.it short link or a full pinterest.com link.',
             howto_name='How to download a Pinterest video or image from a link',
             items=[
                 ('Copy the pin link', 'Open the pin, choose Share, then Copy link. The copied link is usually a pin.it short link. [Pinterest\'s Help Center](https://help.pinterest.com/en/article/send-pins-boards-and-profiles) covers sharing Pins.'),
                 ('Paste it into the box above', 'Paste the pin.it or pinterest.com link and confirm you own the content or have permission to download it.'),
                 ('Preview the pin', 'You see the video thumbnail or a lightweight preview of the image. The download itself is the full original file.'),
                 ('Download', 'Choose Download video or Download image. The file is named after the pin, so it is easy to find later.'),
             ]),
        dict(type='table', id='pin-types', kicker='What you get', heading='What you get from each pin type',
             columns=['Pin type', 'What you get', 'Notes'],
             rows=[
                 ['Image pin', 'The original file Pinterest stores (for example PNG or JPG), not the 736 px preview', 'If the original is ever unavailable, the 736 px version is used instead'],
                 ['Video pin', 'An MP4 file (H.264) with the pin\'s audio track; 720 to 736 px wide in our tests', 'Some pins are silent: the file contains exactly what Pinterest provides'],
                 ['Board, profile or search page', 'Not supported', 'Open a single pin and copy its link instead'],
             ]),
        dict(type='faq', id='faq', kicker='FAQ', heading='Pinterest downloader: frequently asked questions', items=[
            ('How do I download a Pinterest video?', f'Copy the pin\'s link (Share, then Copy link), paste it into {B}, and choose Download video. The file is an MP4 you can play on any device, and it keeps the pin\'s sound when the pin has an audio track.'),
            ('How do I download a Pinterest image in full size?', f'Paste the pin link and choose Download image. {B} fetches the original file from Pinterest\'s image server, which is often far larger than the 736 px version shown on the page. One test pin was 2000 × 3000 pixels.'),
            (f'Does {B} work with pin.it links?', 'Yes. pin.it share links are followed to the pin, and the sender and invite details that Pinterest adds to the final URL are discarded.'),
            ('Why does my downloaded Pinterest video have no sound?', f'Some pins are published without an audio track. {B} saves exactly what Pinterest provides: one of our test pins was a silent video, while the other three video pins included sound.'),
            ('Can I download a whole Pinterest board?', f'No. {B} works on individual pins. Open a pin and copy its link to save its image or video.'),
            ('Do I need a Pinterest account?', f'No. {B} reads the public pin page and never asks for your Pinterest login. A few pins that Pinterest hides from signed-out visitors cannot be fetched; if that happens, try the pin\'s pin.it share link.'),
            ('Can I use downloaded pins however I like?', 'No. Pins are usually someone else\'s work. Download content you own or have permission to use, and check the creator\'s rights and the [Pinterest Terms of Service](https://policy.pinterest.com/en/terms-of-service).'),
        ]),
        dict(type='sources', id='sources', kicker='Sources', heading='Pinterest guides and terms', items=[
            source('pinterest_share', 'Official steps to copy a pin link.'),
            source('pinterest_pins', 'How pins can be shared and interacted with.'),
            source('pinterest_terms', 'The rules that apply to Pinterest content.'),
        ]),
        dict(type='cards', id='more', kicker='More downloaders', heading='Other platforms', items=[c for c in PLATFORM_CARDS if c[3] != '/pinterest-downloader']),
    ],
)

# ----------------------------------------------------------------------------------------------------------------
PAGES['/instagram-downloader'] = dict(
    path='/instagram-downloader', template='platform.html', kind='platform', updated=UPDATED, tool=True,
    title=f'Instagram Reel, Photo & Carousel Downloader | {B}',
    description='Download public Instagram Reels, photos and carousel posts from a link. Save videos as MP4 and photos as images, one by one or as a ZIP. Free, no login.',
    eyebrow='Instagram downloader',
    h1_soft='Free Instagram', h1_hi='Reel, photo & carousel downloader',
    lead=(f"{B}'s Instagram downloader saves the video from a public Reel, or the photos and videos from a public post or carousel. Paste the post link, preview each item, "
          'then download it individually or as an ordered ZIP. It works without an Instagram login and never adds a watermark.'),
    tool_placeholder='Paste an Instagram Reel or post link',
    tool_label='Instagram post URL',
    breadcrumb=[('Home', '/'), ('Instagram downloader', '/instagram-downloader')],
    sections=[
        dict(type='facts', id='at-a-glance', kicker='Key facts', heading='Instagram downloader at a glance', items=[
            ('Saves', 'Reels and videos as MP4 (with audio when the video has it), photos as images, and carousels item by item.'),
            ('Accepted links', 'instagram.com/reel/…, instagram.com/p/… and instagram.com/tv/…, with or without a username in the path.'),
            ('Login', f'None. {B} reads public posts only and never asks for your Instagram login or cookies.'),
            ('Not supported', 'Stories, highlights, private accounts and posts Instagram only shows to signed-in users.'),
            ('Last tested', f'4 of 4 public Instagram links passed on {TESTED_ON}: a Reel (a 720 × 1280 MP4 with audio), a photo, a 3-video carousel and a 6-photo carousel.'),
        ]),
        dict(type='steps', id='how', kicker='How it works', heading='How to download an Instagram Reel or photo',
             intro='The same steps work for Reels, single photos and multi-item carousels.',
             howto_name='How to download an Instagram Reel or photo',
             items=[
                 ('Copy the post link', 'On the post, tap Send and choose Copy link. On desktop, use Options next to the post, then Copy link. [Instagram\'s Help Center](https://help.instagram.com/372819389498306) explains it.'),
                 ('Paste it into the box above', 'Paste the link and confirm you own the content or have permission to download it.'),
                 ('Preview each item', 'Every photo or video in the post appears as its own card. A Reel shows a single video.'),
                 ('Download', 'Save items one by one, or choose Download all · ZIP for a single archive with numbered files.'),
             ]),
        dict(type='table', id='post-types', kicker='What you get', heading='What you get from each Instagram post type',
             columns=['Post type', 'What you get', 'Notes'],
             rows=[
                 ['Reel', 'One MP4 video', 'H.264 video with AAC audio in our test (720 × 1280)'],
                 ['Photo post', 'The image', 'One file'],
                 ['Carousel', 'Every photo and video, in order', 'Download items separately or as a ZIP; very old carousel videos can be silent in the source'],
                 ['Story, highlight or private account', 'Not supported', 'These need an Instagram login'],
             ]),
        dict(type='faq', id='faq', kicker='FAQ', heading='Instagram downloader: frequently asked questions', items=[
            ('How do I download an Instagram Reel?', f'Copy the Reel\'s link (Send, then Copy link), paste it into {B}, confirm you have permission, and choose Download video. The file is an MP4 you can play offline.'),
            ('Can I download Instagram photos and carousels?', f'Yes, for public posts. Each photo and video in a carousel is listed separately, so you can save individual items or take everything with Download all · ZIP.'),
            ('Do I need to log in to Instagram?', f'No. {B} only reads public posts and never asks for your Instagram password or cookies.'),
            (f'Can {B} download Instagram Stories or private posts?', 'No. Stories, highlights and private accounts require an Instagram login, and this tool does not use or ask for one.'),
            (f'Why can\'t {B} fetch my Instagram link?', 'The post may be private or removed, or Instagram may be showing a sign-in wall or limiting requests from servers. Because no login session is used, those posts cannot be fetched. Try again later, or try a different public post.'),
            ('Is it okay to save someone else\'s Reel?', 'Only save content you own or have permission to use. Reels and photos are protected by copyright and by Instagram\'s terms. See our [terms](/terms) and the [Instagram Terms of Use](https://help.instagram.com/581066165581870).'),
        ]),
        dict(type='sources', id='sources', kicker='Sources', heading='Instagram guides and terms', items=[
            source('instagram_link', 'Official steps to copy a post or Reel link.'),
            source('instagram_terms', 'The rules that apply to Instagram content.'),
        ]),
        dict(type='cards', id='more', kicker='More downloaders', heading='Other platforms', items=[c for c in PLATFORM_CARDS if c[3] != '/instagram-downloader']),
    ],
)

# ----------------------------------------------------------------------------------------------------------------
PAGES['/about'] = dict(
    path='/about', template='platform.html', kind='about', updated=UPDATED, tool=False,
    title=f'About {B}: How This Free Post Downloader Works',
    description=f'How {B} works, what it will and will not download, how files and links are handled, and what changed recently. An independent, free tool.',
    eyebrow=f'About {B}',
    h1_soft='How the free', h1_hi=f'{B} downloader works',
    lead=(f'{B} is an independent, free tool that saves images, videos and carousel slides from public Instagram, LinkedIn and Pinterest posts. This page explains how it works, '
          'what it deliberately does not do, and what has changed recently.'),
    breadcrumb=[('Home', '/'), ('About', '/about')],
    sections=[
        dict(type='steps', id='how', kicker='How it works', heading=f'How {B} works, step by step',
             intro='Each step is built to keep the tool narrow: it reads public pages, accepts media only from the platforms\' own servers, and keeps nothing afterwards.',
             items=[
                 ('You paste a link', 'Only Instagram, LinkedIn and Pinterest post URLs are accepted. Share links (lnkd.in and pin.it) are followed one redirect at a time, and every hop is checked before the next request.'),
                 ('The server reads the public post', f'{B} requests the same public page a signed-out visitor would see and looks for the addresses of that post\'s own images, videos or slides. It never uses a login, a cookie or a paid API.'),
                 ('You preview and choose', 'Only media from the platforms\' own image and video servers (for example licdn.com, pinimg.com and cdninstagram.com) is accepted. You pick single files or a ZIP.'),
                 ('Files stream through, then disappear', 'Each download is written to temporary storage, streamed to your browser in small chunks and deleted when the transfer finishes. Abandoned files are swept automatically every few minutes.'),
             ]),
        dict(type='prose', id='principles', heading='What it will not do', paragraphs=[
            f'{B} does not download private or sign-in-only content, does not bypass document download restrictions such as LinkedIn\'s PDF gate, and does not add watermarks, ads or trackers. '
            'It is not affiliated with, or endorsed by, Instagram, Meta, LinkedIn or Pinterest.',
            'Downloaded files belong to their creators. The tool is meant for saving content you own or have permission to use. See the [terms](/terms) and the [copyright and takedown](/copyright) page.',
        ]),
        dict(type='facts', id='limits', kicker='Limits', heading='Limits and fair use', items=[
            ('Per file', f"Up to {LIMITS['file_mb']} MB."),
            ('Per ZIP', f"Up to {LIMITS['zip_mb']} MB, with at most {LIMITS['attachments']} attachments per post."),
            ('Request rate', f"Each visitor can make {LIMITS['lookups_per_min']} lookups and {LIMITS['downloads_per_min']} downloads per minute."),
            ('Download links', f"Expire after {LIMITS['session_minutes']} minutes. Paste the link again for a fresh one."),
        ]),
        dict(type='table', id='changes', kicker='Recently', heading='Recent changes',
             columns=['Date', 'Change'],
             rows=[
                 ['3 October 2026', 'Added dedicated LinkedIn, Pinterest and Instagram pages, FAQs, structured data, a sitemap, robots.txt and llms.txt.'],
                 ['2 October 2026', 'Added Pinterest pins and pin.it links. Public beta launched with health checks, rate limits and shared sessions.'],
                 ['1 October 2026', 'First version: LinkedIn images, videos and carousel slides; Instagram Reels, photos and carousels.'],
             ]),
        dict(type='prose', id='contact', heading='Questions, takedown requests and bug reports', paragraphs=[
            'Use the [contact page](/contact) for takedown requests, privacy questions, abuse reports and bug reports. When reporting a problem, include the post link and never send passwords or login cookies.',
        ]),
        dict(type='cards', id='more', kicker='Downloaders', heading='Try it on your platform', items=PLATFORM_CARDS),
    ],
)

LEGAL = {
    '/terms': dict(path='/terms', title=f'Terms of Use | {B}', name='Terms of Use',
                   description=f'Terms of use for {B}, a free tool for saving images, videos and carousel slides from public Instagram, LinkedIn and Pinterest posts.'),
    '/privacy': dict(path='/privacy', title=f'Privacy Policy | {B}', name='Privacy Policy',
                     description=f'How {B} handles links, files, logs and cookies: no accounts, no ads or trackers, and downloads are deleted when the transfer ends.'),
    '/copyright': dict(path='/copyright', title=f'Copyright and Takedown | {B}', name='Copyright and Takedown',
                       description=f'How rights holders can report content and request blocks on {B}, a downloader for public Instagram, LinkedIn and Pinterest posts.'),
    '/contact': dict(path='/contact', title=f'Contact {B}', name='Contact',
                     description=f'Contact {B} for takedown requests, privacy questions, abuse reports and bug reports.'),
}
for _page in LEGAL.values():
    _page.update(kind='legal', updated=LEGAL_UPDATED, breadcrumb=[('Home', '/'), (_page['name'], _page['path'])])

SITEMAP_PRIORITY = {'/': '1.0', '/linkedin-downloader': '0.9', '/pinterest-downloader': '0.9', '/instagram-downloader': '0.8', '/about': '0.5'}

FEATURE_LIST = [
    'Download images from public Instagram, LinkedIn and Pinterest posts',
    'Download videos and Reels as MP4 files',
    'Save LinkedIn carousel (document) slides as images or an ordered ZIP',
    'Original-size Pinterest images and MP4 video pins',
    'Supports lnkd.in and pin.it share links',
    'No account, no login, no watermark, files not stored',
]
