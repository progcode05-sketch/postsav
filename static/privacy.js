/* Optional GA4 collection starts only after a visitor opts in. */
(function () {
 'use strict';
 const id = document.currentScript.dataset.measurementId;
 const panel = document.getElementById('analytics-consent');
 const key = 'postsav-analytics-consent-v1';
 const lifetime = 180 * 24 * 60 * 60 * 1000;
 let loaded = false;
 window.dataLayer = window.dataLayer || [];
 window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
 window.gtag('consent', 'default', {
  analytics_storage: 'denied', ad_storage: 'denied',
  ad_user_data: 'denied', ad_personalization: 'denied'
 });
 function cleanReferrer() {
  try { return document.referrer ? new URL(document.referrer).origin + '/' : ''; }
  catch (_) { return ''; }
 }
 function allow() {
  window['ga-disable-' + id] = false;
  window.gtag('consent', 'update', { analytics_storage: 'granted' });
  if (loaded) return;
  loaded = true;
  window.gtag('js', new Date());
  const location = window.location.origin + window.location.pathname;
  window.gtag('config', id, {
   send_page_view: false, page_location: location, page_referrer: cleanReferrer(),
   allow_google_signals: false, allow_ad_personalization_signals: false
  });
  window.gtag('event', 'page_view', { page_location: location, page_referrer: cleanReferrer() });
  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id);
  document.head.append(script);
 }
 function choose(accepted) {
  try { localStorage.setItem(key, JSON.stringify({ accepted, expires: Date.now() + lifetime })); }
  catch (_) { /* Browsers may disallow storage; the choice still applies to this page. */ }
  panel.hidden = true;
  if (accepted) allow();
  else {
   window['ga-disable-' + id] = true;
   window.gtag('consent', 'update', { analytics_storage: 'denied' });
  }
 }
 let saved;
 try { saved = JSON.parse(localStorage.getItem(key)); } catch (_) { saved = null; }
 if (saved && saved.expires > Date.now() && typeof saved.accepted === 'boolean') {
  if (saved.accepted) allow();
 } else panel.hidden = false;
 document.getElementById('analytics-accept').addEventListener('click', () => choose(true));
 document.getElementById('analytics-reject').addEventListener('click', () => choose(false));
 document.getElementById('analytics-settings').addEventListener('click', () => {
  panel.hidden = false;
  document.getElementById('analytics-reject').focus();
 });
})();
