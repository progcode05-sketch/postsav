/* Run with node tools/test_privacy.cjs. No external packages required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'privacy.js'), 'utf8');
function setup(saved, blocked = false) {
 const elements = {};
 for (const id of ['analytics-consent', 'analytics-accept', 'analytics-reject', 'analytics-settings']) {
  elements[id] = { hidden: true, addEventListener(event, callback) { this[event] = callback; }, focus() {} };
 }
 const scripts = [];
 const storage = { value: saved ? JSON.stringify(saved) : null,
  getItem() { if (blocked) throw Error('blocked'); return this.value; },
  setItem(key, value) { if (blocked) throw Error('blocked'); this.value = value; } };
 const window = { location: { origin: 'https://postsav.example', pathname: '/instagram-downloader', search: '?session=SECRET', hash: '#SECRET' } };
 const document = { currentScript: { dataset: { measurementId: 'G-ABCD123456' } },
  referrer: 'https://example.com/private?session=SECRET', head: { append(script) { scripts.push(script); } },
  createElement() { return {}; }, getElementById(id) { return elements[id]; } };
 vm.runInNewContext(source, { window, document, localStorage: storage, Date, URL, encodeURIComponent });
 return { elements, scripts, storage, window };
}
const first = setup();
assert.equal(first.scripts.length, 0);
assert.equal(first.elements['analytics-consent'].hidden, false);
first.elements['analytics-reject'].click();
assert.equal(first.scripts.length, 0);
assert.equal(first.window['ga-disable-G-ABCD123456'], true);
first.elements['analytics-settings'].click();
first.elements['analytics-accept'].click();
assert.equal(first.scripts.length, 1);
assert.ok(!JSON.stringify(first.window.dataLayer).includes('SECRET'));
assert.ok(JSON.stringify(first.window.dataLayer).includes('https://example.com/'));
first.elements['analytics-accept'].click();
assert.equal(first.scripts.length, 1);
first.elements['analytics-reject'].click();
assert.equal(first.window['ga-disable-G-ABCD123456'], true);
assert.equal(setup({ accepted: true, expires: Date.now() + 10000 }).scripts.length, 1);
assert.equal(setup({ accepted: false, expires: Date.now() + 10000 }).scripts.length, 0);
const expired = setup({ accepted: true, expires: Date.now() - 10000 });
assert.equal(expired.scripts.length, 0);
assert.equal(expired.elements['analytics-consent'].hidden, false);
const blocked = setup(null, true);
blocked.elements['analytics-accept'].click();
assert.equal(blocked.scripts.length, 1);
console.log('Consent checks passed: default/reject, accept, withdrawal, stored choices, expiry, blocked storage and URL sanitization.');
