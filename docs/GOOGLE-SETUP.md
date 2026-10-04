# Google Analytics and AdSense setup

This site's public identifiers are configured: Analytics `G-JMK4H2LRD3` and AdSense `ca-pub-7254853329853324`. Public pages offer opt-in Analytics and publish AdSense verification and ads.txt. Advertising remains disabled until explicitly enabled. Environment variables override the IDs; set an empty value to disable either integration. Local mode never loads these services. Identifiers are public configuration, not passwords. Never supply your Google password or account recovery codes.

## Google Analytics

1. Open https://analytics.google.com/ and create an account and a GA4 property for PostSav.
2. In Admin, open Data streams, add a Web stream and enter your final site URL.
3. Copy its Measurement ID, which starts with `G-`.
4. In the web stream's Enhanced measurement settings, disable enhanced measurement. This integration sends a page view explicitly; disabling automatic form and outbound-link events helps prevent submitted post URLs or media links from being collected. Keep Google Signals and advertising personalization disabled unless you intentionally redesign the consent flow.
5. In Render, open the web service, Environment, and set `GA_MEASUREMENT_ID` to your real ID. Save and deploy.
6. Open the site, choose Allow analytics and check Analytics Realtime or Google Tag Assistant. Rejecting analytics must cause no Analytics script or collection requests. Analytics preferences at the bottom lets visitors change their choice.

The script does not load Google's Analytics library before acceptance. It sends a page URL without query strings or fragments and a referrer origin without its path/query. It does not add download, form, caption, uploader or submitted-link events. A visitor's preference is stored locally for 180 days; browser storage restrictions may require choosing again. Withdrawal stops future collection and does not remove previously processed data or existing Google cookies.

## Google AdSense

1. Open https://www.google.com/adsense/start/ and create an account with accurate payee information. Add the final site URL for review.
2. Find the publisher ID in Account, Settings, Account information. The integration expects `ca-pub-` followed by 16 digits; prepend `ca-` if the account shows `pub-…`.
3. Set `ADSENSE_PUBLISHER_ID` in Render. Leave `ADSENSE_ENABLED` unset or `0` during review. Deploy: the verification meta tag appears and `/ads.txt` publishes the correct seller record. Choose the meta-tag verification method in AdSense and request site review.
4. In AdSense, configure Privacy & messaging, including Google's certified European regulations consent message for visitors in the EEA, UK and Switzerland. Configure other applicable regional privacy messages. The site's Analytics preference panel is separate and is not an advertising CMP.
5. After approval and consent-message configuration, enable Auto ads for this site in AdSense. Set `ADSENSE_ENABLED=1` in Render and deploy to load the AdSense script. Verify the advertising privacy message and reject/accept flows using Google's testing guidance before treating the setup as ready.
6. Use Auto ads preview and excluded areas to keep ads away from the URL input, permission checkbox and download controls. Visitors should be able to distinguish advertisements from download buttons. Disable intrusive formats if they interfere with the tool.

AdSense approval and earnings are determined by Google, traffic and content quality; adding code does not ensure approval or revenue. Google's publisher policies specifically disallow pages that help download streaming videos when prohibited by the content provider. This downloader therefore has a material eligibility risk; a permission checkbox alone does not establish eligibility. Review its supported uses against the content providers' terms before applying. Use only content you have rights to, keep substantive original guides and do not encourage ad clicks.

The application does not create Google accounts, select payout details, submit an AdSense application or configure Google's hosted consent messages for you. Those actions happen in your Google account.

## Official references

- [Set up Google Analytics](https://support.google.com/analytics/answer/9304153)
- [Find your publisher ID](https://support.google.com/adsense/answer/105516)
- [Ads.txt setup](https://support.google.com/adsense/answer/12171612)
- [Google advertising consent requirements](https://support.google.com/adsense/answer/13554020)
- [Google Publisher Policies](https://support.google.com/publisherpolicies/answer/10502938)
